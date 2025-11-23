"""
MACD（Moving Average Convergence Divergence）とボリンジャーバンド（Bollinger Bands）を
組み合わせた取引エージェント
2つの指標すべてが同じ方向のシグナルを出す場合のみ取引
"""
from datetime import datetime
from typing import Optional
from shared.agents.base_agent import BaseAgent
from shared.models.trading import Action, PriceData, TradingDecision
import statistics


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


def calculate_bollinger_bands(prices: list[float], period: int = 20, num_std_dev: float = 2.0) -> Optional[dict]:
    """
    ボリンジャーバンドを計算
    
    Args:
        prices: 価格のリスト
        period: 移動平均期間（デフォルト: 20）
        num_std_dev: 標準偏差の倍数（デフォルト: 2.0）
    
    Returns:
        {'middle': float, 'upper': float, 'lower': float, 'bandwidth': float}、データが不足している場合はNone
    """
    if len(prices) < period:
        return None
    
    # 最近のperiod期間の価格を取得
    recent_prices = prices[-period:]
    
    # 中央バンド（移動平均）
    middle_band = sum(recent_prices) / period
    
    # 標準偏差を計算
    variance = sum((p - middle_band) ** 2 for p in recent_prices) / period
    std_dev = variance ** 0.5
    
    # 上バンドと下バンド
    upper_band = middle_band + (num_std_dev * std_dev)
    lower_band = middle_band - (num_std_dev * std_dev)
    
    # バンド幅（ボラティリティの指標）
    bandwidth = (upper_band - lower_band) / middle_band if middle_band > 0 else 0
    
    return {
        'middle': middle_band,
        'upper': upper_band,
        'lower': lower_band,
        'bandwidth': bandwidth
    }


class MACDBBAgent(BaseAgent):
    """
    MACDとボリンジャーバンドを組み合わせた取引エージェント
    2つの指標すべてが同じ方向のシグナルを出す場合のみ取引
    """
    
    def __init__(
        self,
        agent_id: str,
        trader_id: str = None,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_num_std_dev: float = 2.0
    ):
        """
        初期化
        
        Args:
            agent_id: エージェントID
            trader_id: トレーダーID
            macd_fast: MACD短期EMA期間
            macd_slow: MACD長期EMA期間
            macd_signal: MACDシグナルライン期間
            bb_period: ボリンジャーバンドの期間
            bb_num_std_dev: ボリンジャーバンドの標準偏差倍数
        """
        super().__init__(agent_id, trader_id)
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_num_std_dev = bb_num_std_dev
    
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """
        取引判断を行う（MACD + ボリンジャーバンド戦略）
        2つの指標すべてが同じ方向のシグナルを出す場合のみ取引
        """
        # 十分なデータがない場合
        min_period = max(self.macd_slow + self.macd_signal, self.bb_period)
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
        current_price = price_data.price
        
        # MACDを計算
        macd_data = calculate_macd(prices, self.macd_fast, self.macd_slow, self.macd_signal)
        
        # ボリンジャーバンドを計算
        bb_data = calculate_bollinger_bands(prices, self.bb_period, self.bb_num_std_dev)
        
        if macd_data is None or bb_data is None:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=Action.HOLD,
                confidence=0.5,
                price=current_price,
                reason="MACD or Bollinger Bands calculation failed"
            )
        
        macd = macd_data['macd']
        signal = macd_data['signal']
        histogram = macd_data['histogram']
        
        upper_band = bb_data['upper']
        lower_band = bb_data['lower']
        middle_band = bb_data['middle']
        
        # 各指標のシグナルを判定
        # MACDシグナル
        macd_buy_signal = histogram > 0 and macd > signal
        macd_sell_signal = histogram < 0 and macd < signal
        
        # ボリンジャーバンドシグナル
        # 価格が下バンドを下回る → 買いシグナル（過小評価）
        # 価格が上バンドを上回る → 売りシグナル（過大評価）
        bb_buy_signal = current_price <= lower_band
        bb_sell_signal = current_price >= upper_band
        
        # 2つの指標すべてが同じ方向のシグナルを出す場合のみ取引
        if macd_buy_signal and bb_buy_signal:
            # 両方が買いシグナル
            action = Action.BUY
            confidence = 0.9
            reason = (f"MACD bullish (MACD={macd:.2f} > Signal={signal:.2f}, Hist={histogram:.2f}) AND "
                     f"BB buy signal (Price=${current_price:.2f} <= Lower=${lower_band:.2f})")
        elif macd_sell_signal and bb_sell_signal:
            # 両方が売りシグナル
            action = Action.SELL
            confidence = 0.9
            reason = (f"MACD bearish (MACD={macd:.2f} < Signal={signal:.2f}, Hist={histogram:.2f}) AND "
                     f"BB sell signal (Price=${current_price:.2f} >= Upper=${upper_band:.2f})")
        else:
            # シグナルが一致しない場合はHOLD
            action = Action.HOLD
            confidence = 0.5
            signals_summary = f"MACD:{'B' if macd_buy_signal else 'S' if macd_sell_signal else 'N'}, "
            signals_summary += f"BB:{'B' if bb_buy_signal else 'S' if bb_sell_signal else 'N'}"
            reason = f"Not all 2 signals align - {signals_summary} (MACD={macd:.2f}, BB: ${current_price:.2f} between ${lower_band:.2f}-${upper_band:.2f})"
        
        return TradingDecision(
            agent_id=self.agent_id,
            timestamp=datetime.utcnow(),
            action=action,
            confidence=confidence,
            price=current_price,
            reason=reason
        )
    
    def get_agent_type(self) -> str:
        return "MACD_BB"

