"""
RSI、MACD、ボリンジャーバンド（Bollinger Bands）を組み合わせた取引エージェント
3つの指標すべてが同じ方向のシグナルを出す場合のみ取引
"""
from datetime import datetime
from typing import Optional
from shared.agents.rsi_macd_agent import RSIMACDAgent, calculate_rsi, calculate_macd
from shared.models.trading import Action, PriceData, TradingDecision
import statistics


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


class RSIMACDBBAgent(RSIMACDAgent):
    """
    RSI、MACD、ボリンジャーバンドを組み合わせた取引エージェント
    3つの指標すべてが同じ方向のシグナルを出す場合のみ取引
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
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_num_std_dev: float = 2.0
    ):
        """
        初期化
        
        Args:
            agent_id: エージェントID
            trader_id: トレーダーID
            rsi_period: RSI期間
            rsi_oversold: RSIのオーバーソールド閾値
            rsi_overbought: RSIのオーバーボート閾値
            macd_fast: MACD短期EMA期間
            macd_slow: MACD長期EMA期間
            macd_signal: MACDシグナルライン期間
            bb_period: ボリンジャーバンドの期間
            bb_num_std_dev: ボリンジャーバンドの標準偏差倍数
        """
        super().__init__(agent_id, trader_id, rsi_period, rsi_oversold, rsi_overbought,
                        macd_fast, macd_slow, macd_signal)
        self.bb_period = bb_period
        self.bb_num_std_dev = bb_num_std_dev
    
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """
        取引判断を行う（RSI + MACD + ボリンジャーバンド戦略）
        3つの指標すべてが同じ方向のシグナルを出す場合のみ取引
        """
        # 十分なデータがない場合
        min_period = max(
            self.macd_slow + self.macd_signal,
            self.rsi_period + 1,
            self.bb_period
        )
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
        
        # RSIを計算
        rsi = calculate_rsi(prices, self.rsi_period)
        
        # MACDを計算
        macd_data = calculate_macd(prices, self.macd_fast, self.macd_slow, self.macd_signal)
        
        # ボリンジャーバンドを計算
        bb_data = calculate_bollinger_bands(prices, self.bb_period, self.bb_num_std_dev)
        
        if rsi is None or macd_data is None or bb_data is None:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=Action.HOLD,
                confidence=0.5,
                price=current_price,
                reason="RSI, MACD, or Bollinger Bands calculation failed"
            )
        
        macd = macd_data['macd']
        signal = macd_data['signal']
        histogram = macd_data['histogram']
        
        upper_band = bb_data['upper']
        lower_band = bb_data['lower']
        middle_band = bb_data['middle']
        
        # 各指標のシグナルを判定
        # RSIシグナル
        rsi_buy_signal = rsi < self.rsi_oversold
        rsi_sell_signal = rsi > self.rsi_overbought
        
        # MACDシグナル
        macd_buy_signal = histogram > 0 and macd > signal
        macd_sell_signal = histogram < 0 and macd < signal
        
        # ボリンジャーバンドシグナル
        # 価格が下バンドを下回る → 買いシグナル（過小評価）
        # 価格が上バンドを上回る → 売りシグナル（過大評価）
        bb_buy_signal = current_price <= lower_band
        bb_sell_signal = current_price >= upper_band
        
        # 3つの指標すべてが同じ方向のシグナルを出す場合のみ取引
        buy_signals_count = sum([rsi_buy_signal, macd_buy_signal, bb_buy_signal])
        sell_signals_count = sum([rsi_sell_signal, macd_sell_signal, bb_sell_signal])
        
        if buy_signals_count == 3:
            # 3つすべてが買いシグナル
            action = Action.BUY
            confidence = 0.9
            reason = (f"RSI oversold ({rsi:.2f} < {self.rsi_oversold}) AND "
                     f"MACD bullish (MACD={macd:.2f} > Signal={signal:.2f}, Hist={histogram:.2f}) AND "
                     f"BB buy signal (Price=${current_price:.2f} <= Lower=${lower_band:.2f})")
        elif sell_signals_count == 3:
            # 3つすべてが売りシグナル
            action = Action.SELL
            confidence = 0.9
            reason = (f"RSI overbought ({rsi:.2f} > {self.rsi_overbought}) AND "
                     f"MACD bearish (MACD={macd:.2f} < Signal={signal:.2f}, Hist={histogram:.2f}) AND "
                     f"BB sell signal (Price=${current_price:.2f} >= Upper=${upper_band:.2f})")
        else:
            # シグナルが一致しない場合はHOLD
            action = Action.HOLD
            confidence = 0.5
            signals_summary = f"RSI:{'B' if rsi_buy_signal else 'S' if rsi_sell_signal else 'N'}, "
            signals_summary += f"MACD:{'B' if macd_buy_signal else 'S' if macd_sell_signal else 'N'}, "
            signals_summary += f"BB:{'B' if bb_buy_signal else 'S' if bb_sell_signal else 'N'}"
            reason = f"Not all 3 signals align - {signals_summary} (RSI={rsi:.2f}, MACD={macd:.2f}, BB: ${current_price:.2f} between ${lower_band:.2f}-${upper_band:.2f})"
        
        return TradingDecision(
            agent_id=self.agent_id,
            timestamp=datetime.utcnow(),
            action=action,
            confidence=confidence,
            price=current_price,
            reason=reason
        )
    
    def get_agent_type(self) -> str:
        return "RSI_MACD_BB"

