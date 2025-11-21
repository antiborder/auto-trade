"""
RSI（Relative Strength Index）とMACD（Moving Average Convergence Divergence）を
組み合わせた取引エージェント
"""
from datetime import datetime
from typing import Optional
from shared.agents.base_agent import BaseAgent
from shared.models.trading import Action, PriceData, TradingDecision


def calculate_rsi(prices: list[float], period: int = 14) -> Optional[float]:
    """
    RSI（Relative Strength Index）を計算
    
    Args:
        prices: 価格のリスト
        period: RSI期間（デフォルト: 14）
    
    Returns:
        RSI値（0-100）、データが不足している場合はNone
    """
    if len(prices) < period + 1:
        return None
    
    # 価格変動を計算
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # 過去のperiod期間の変動を取得
    recent_deltas = deltas[-period:]
    
    # 上昇分と下降分を分離
    gains = [d if d > 0 else 0 for d in recent_deltas]
    losses = [-d if d < 0 else 0 for d in recent_deltas]
    
    # 平均を計算
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0:
        return 100.0  # 損失がない場合
    
    # RS（Relative Strength）を計算
    rs = avg_gain / avg_loss
    
    # RSIを計算
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_macd(prices: list[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Optional[dict]:
    """
    MACD（Moving Average Convergence Divergence）を計算
    
    Args:
        prices: 価格のリスト
        fast_period: 短期EMA期間（デフォルト: 12）
        slow_period: 長期EMA期間（デフォルト: 26）
        signal_period: シグナルライン期間（デフォルト: 9）
    
    Returns:
        {'macd': float, 'signal': float, 'histogram': float}、データが不足している場合はNone
    """
    if len(prices) < slow_period + signal_period:
        return None
    
    # EMA（Exponential Moving Average）を計算
    def calculate_ema(prices: list[float], period: int) -> list[float]:
        """指数移動平均を計算"""
        ema = []
        multiplier = 2.0 / (period + 1)
        
        # 最初のEMAは単純移動平均
        sma = sum(prices[:period]) / period
        ema.append(sma)
        
        # 以降はEMA計算
        for i in range(period, len(prices)):
            ema_value = (prices[i] * multiplier) + (ema[-1] * (1 - multiplier))
            ema.append(ema_value)
        
        return ema
    
    # 短期EMAと長期EMAを計算
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)
    
    # MACDライン = 短期EMA - 長期EMA
    # slow_emaの方が長いので、同じ長さになるように調整
    macd_line = []
    offset = len(fast_ema) - len(slow_ema)
    for i in range(len(slow_ema)):
        macd_line.append(fast_ema[offset + i] - slow_ema[i])
    
    # シグナルライン = MACDラインのEMA
    if len(macd_line) < signal_period:
        return None
    
    signal_line = calculate_ema(macd_line, signal_period)
    
    # ヒストグラム = MACDライン - シグナルライン
    offset_signal = len(macd_line) - len(signal_line)
    histogram = []
    for i in range(len(signal_line)):
        histogram.append(macd_line[offset_signal + i] - signal_line[i])
    
    return {
        'macd': macd_line[-1],
        'signal': signal_line[-1],
        'histogram': histogram[-1] if histogram else 0
    }


class RSIMACDAgent(BaseAgent):
    """
    RSIとMACDを組み合わせた取引エージェント
    """
    
    def __init__(
        self,
        agent_id: str,
        trader_id: str = None,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9
    ):
        """
        初期化
        
        Args:
            agent_id: エージェントID
            trader_id: トレーダーID
            rsi_period: RSI期間（デフォルト: 14）
            rsi_oversold: RSIのオーバーソールド閾値（デフォルト: 30）
            rsi_overbought: RSIのオーバーボート閾値（デフォルト: 70）
            macd_fast: MACD短期EMA期間（デフォルト: 12）
            macd_slow: MACD長期EMA期間（デフォルト: 26）
            macd_signal: MACDシグナルライン期間（デフォルト: 9）
        """
        super().__init__(agent_id, trader_id)
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
    
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """
        取引判断を行う（RSI + MACD戦略）
        
        Args:
            price_data: 現在の価格データ
            historical_data: 過去の価格データ
        
        Returns:
            TradingDecision: 取引判断
        """
        # 十分なデータがない場合
        min_period = max(self.macd_slow + self.macd_signal, self.rsi_period + 1)
        if len(historical_data) < min_period:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason="Insufficient historical data"
            )
        
        # 価格リストを取得
        prices = [d.price for d in historical_data] + [price_data.price]
        
        # RSIを計算
        rsi = calculate_rsi(prices, self.rsi_period)
        
        # MACDを計算
        macd_data = calculate_macd(prices, self.macd_fast, self.macd_slow, self.macd_signal)
        
        if rsi is None or macd_data is None:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason="RSI or MACD calculation failed"
            )
        
        macd = macd_data['macd']
        signal = macd_data['signal']
        histogram = macd_data['histogram']
        
        # 判断ロジック: RSIとMACDの両方が同じ方向のシグナルを出す場合のみ取引
        rsi_buy_signal = rsi < self.rsi_oversold
        rsi_sell_signal = rsi > self.rsi_overbought
        
        # MACDシグナル: MACDがシグナルラインを上抜け（ゴールデンクロス）→ 買い
        #              MACDがシグナルラインを下抜け（デッドクロス）→ 売り
        macd_buy_signal = histogram > 0 and macd > signal
        macd_sell_signal = histogram < 0 and macd < signal
        
        # 両方が同じ方向のシグナルを出す場合のみ取引
        if rsi_buy_signal and macd_buy_signal:
            # RSIとMACDの両方が買いシグナル
            action = Action.BUY
            confidence = 0.8
            reason = f"RSI oversold ({rsi:.2f} < {self.rsi_oversold}) AND MACD bullish (MACD={macd:.2f} > Signal={signal:.2f}, Hist={histogram:.2f})"
        elif rsi_sell_signal and macd_sell_signal:
            # RSIとMACDの両方が売りシグナル
            action = Action.SELL
            confidence = 0.8
            reason = f"RSI overbought ({rsi:.2f} > {self.rsi_overbought}) AND MACD bearish (MACD={macd:.2f} < Signal={signal:.2f}, Hist={histogram:.2f})"
        else:
            # シグナルが一致しない、またはシグナルがない場合はHOLD
            action = Action.HOLD
            confidence = 0.5
            rsi_status = "oversold" if rsi_buy_signal else ("overbought" if rsi_sell_signal else f"neutral ({rsi:.2f})")
            macd_status = "bullish" if macd_buy_signal else ("bearish" if macd_sell_signal else "neutral")
            reason = f"RSI {rsi_status} AND MACD {macd_status} - signals do not align"
        
        return TradingDecision(
            agent_id=self.agent_id,
            timestamp=datetime.utcnow(),
            action=action,
            confidence=confidence,
            price=price_data.price,
            reason=f"RSI={rsi:.2f}, MACD={macd:.2f}, Signal={signal:.2f} | {reason}"
        )
    
    def get_agent_type(self) -> str:
        return "RSI_MACD"

