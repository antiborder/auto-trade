"""
マルチタイムフレームエージェント
15分足データからRSIとボリンジャーバンドを計算
1時間足データからMACDを計算
3つの指標すべてが同じ方向のシグナルを出す場合のみ取引
"""
from datetime import datetime, timezone
from typing import Optional, List
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


class MultiTimeframeAgent(BaseAgent):
    """
    マルチタイムフレームエージェント
    15分足データからRSIとボリンジャーバンドを計算
    1時間足データからMACDを計算
    3つの指標すべてが同じ方向のシグナルを出す場合のみ取引
    """
    
    def __init__(
        self,
        agent_id: str,
        trader_id: str = None,
        # 15分足用パラメータ（RSI + BB）
        rsi_period: int = 10,
        rsi_oversold: float = 35.0,
        rsi_overbought: float = 80.0,
        bb_period: int = 22,
        bb_num_std_dev: float = 2.5,
        # 1時間足用パラメータ（MACD）
        macd_fast: int = 12,
        macd_slow: int = 20,
        macd_signal: int = 11
    ):
        """
        初期化
        
        Args:
            agent_id: エージェントID
            trader_id: トレーダーID
            rsi_period: RSI期間（15分足用）
            rsi_oversold: RSIのオーバーソールド閾値（15分足用）
            rsi_overbought: RSIのオーバーボート閾値（15分足用）
            bb_period: ボリンジャーバンドの期間（15分足用）
            bb_num_std_dev: ボリンジャーバンドの標準偏差倍数（15分足用）
            macd_fast: MACD短期EMA期間（1時間足用）
            macd_slow: MACD長期EMA期間（1時間足用）
            macd_signal: MACDシグナルライン期間（1時間足用）
        """
        super().__init__(agent_id, trader_id)
        # 15分足用パラメータ
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_period = bb_period
        self.bb_num_std_dev = bb_num_std_dev
        # 1時間足用パラメータ
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
    
    def decide(
        self,
        price_data: PriceData,
        historical_data: List[PriceData],
        historical_data_1h: Optional[List[PriceData]] = None
    ) -> TradingDecision:
        """
        取引判断を行う（マルチタイムフレーム戦略）
        15分足データからRSIとBBを計算、1時間足データからMACDを計算
        3つの指標すべてが同じ方向のシグナルを出す場合のみ取引
        
        Args:
            price_data: 現在の価格データ（15分足）
            historical_data: 過去の価格データ（15分足）
            historical_data_1h: 過去の価格データ（1時間足、オプション）
        
        Returns:
            TradingDecision: 取引判断
        """
        # 15分足データのチェック
        min_period_15m = max(self.rsi_period + 1, self.bb_period)
        if len(historical_data) < min_period_15m:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.now(timezone.utc),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason="Insufficient 15-minute historical data"
            )
        
        # 1時間足データのチェック
        if historical_data_1h is None or len(historical_data_1h) == 0:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.now(timezone.utc),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason="No 1-hour historical data provided"
            )
        
        min_period_1h = self.macd_slow + self.macd_signal
        if len(historical_data_1h) < min_period_1h:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.now(timezone.utc),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason="Insufficient 1-hour historical data"
            )
        
        # 15分足データからRSIとBBを計算
        prices_15m = [d.price for d in historical_data] + [price_data.price]
        current_price = price_data.price
        
        rsi = calculate_rsi(prices_15m, self.rsi_period)
        bb_data = calculate_bollinger_bands(prices_15m, self.bb_period, self.bb_num_std_dev)
        
        # 1時間足データからMACDを計算
        prices_1h = [d.price for d in historical_data_1h]
        # 最新の1時間足データの価格を追加（現在時刻に対応する1時間足がない場合は最後の価格を使用）
        if historical_data_1h:
            prices_1h.append(historical_data_1h[-1].price)
        
        macd_data = calculate_macd(prices_1h, self.macd_fast, self.macd_slow, self.macd_signal)
        
        if rsi is None or bb_data is None or macd_data is None:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.now(timezone.utc),
                action=Action.HOLD,
                confidence=0.5,
                price=current_price,
                reason="RSI, Bollinger Bands, or MACD calculation failed"
            )
        
        upper_band = bb_data['upper']
        lower_band = bb_data['lower']
        macd = macd_data['macd']
        signal = macd_data['signal']
        histogram = macd_data['histogram']
        
        # 各指標のシグナルを判定
        # RSIシグナル（15分足）
        rsi_buy_signal = rsi < self.rsi_oversold
        rsi_sell_signal = rsi > self.rsi_overbought
        
        # ボリンジャーバンドシグナル（15分足）
        bb_buy_signal = current_price <= lower_band
        bb_sell_signal = current_price >= upper_band
        
        # MACDシグナル（1時間足）
        macd_buy_signal = histogram > 0 and macd > signal
        macd_sell_signal = histogram < 0 and macd < signal
        
        # 3つの指標すべてが同じ方向のシグナルを出す場合のみ取引
        buy_signals_count = sum([rsi_buy_signal, bb_buy_signal, macd_buy_signal])
        sell_signals_count = sum([rsi_sell_signal, bb_sell_signal, macd_sell_signal])
        
        if buy_signals_count == 3:
            # 3つすべてが買いシグナル
            action = Action.BUY
            confidence = 0.9
            reason = (f"RSI oversold ({rsi:.2f} < {self.rsi_oversold}) [15m] AND "
                     f"BB buy signal (Price=${current_price:.2f} <= Lower=${lower_band:.2f}) [15m] AND "
                     f"MACD bullish (MACD={macd:.2f} > Signal={signal:.2f}, Hist={histogram:.2f}) [1h]")
        elif sell_signals_count == 3:
            # 3つすべてが売りシグナル
            action = Action.SELL
            confidence = 0.9
            reason = (f"RSI overbought ({rsi:.2f} > {self.rsi_overbought}) [15m] AND "
                     f"BB sell signal (Price=${current_price:.2f} >= Upper=${upper_band:.2f}) [15m] AND "
                     f"MACD bearish (MACD={macd:.2f} < Signal={signal:.2f}, Hist={histogram:.2f}) [1h]")
        else:
            # シグナルが一致しない場合はHOLD
            action = Action.HOLD
            confidence = 0.5
            signals_summary = f"RSI:{'B' if rsi_buy_signal else 'S' if rsi_sell_signal else 'N'}, "
            signals_summary += f"BB:{'B' if bb_buy_signal else 'S' if bb_sell_signal else 'N'}, "
            signals_summary += f"MACD:{'B' if macd_buy_signal else 'S' if macd_sell_signal else 'N'}"
            reason = (f"Not all 3 signals align - {signals_summary} "
                     f"(RSI={rsi:.2f} [15m], BB: ${current_price:.2f} between ${lower_band:.2f}-${upper_band:.2f} [15m], "
                     f"MACD={macd:.2f} [1h])")
        
        return TradingDecision(
            agent_id=self.agent_id,
            timestamp=datetime.now(timezone.utc),
            action=action,
            confidence=confidence,
            price=current_price,
            reason=reason
        )
    
    def get_agent_type(self) -> str:
        return "MULTI_TIMEFRAME"

