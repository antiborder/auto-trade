"""
損失確定機能付きRSI+MACD+ボリンジャーバンドエージェント
"""
from datetime import datetime
from typing import Optional
from shared.agents.rsi_macd_bb_agent import RSIMACDBBAgent
from shared.models.trading import Action, PriceData, TradingDecision


class RSIMACDBBAgentWithStopLoss(RSIMACDBBAgent):
    """
    損失確定機能（パーセンテージベース）とトレーリングストップロス（利益確定）機能付き
    RSI+MACD+ボリンジャーバンドエージェント
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
        bb_num_std_dev: float = 2.0,
        stop_loss_percentage: float = 0.07,  # デフォルト -7%
        trailing_stop_percentage: Optional[float] = None  # オプション: トレーリングストップロス
    ):
        """
        初期化
        """
        super().__init__(agent_id, trader_id, rsi_period, rsi_oversold, rsi_overbought,
                        macd_fast, macd_slow, macd_signal, bb_period, bb_num_std_dev)
        self.stop_loss_percentage = stop_loss_percentage
        self.trailing_stop_percentage = trailing_stop_percentage
        
        # ポジション管理
        self.entry_price: Optional[float] = None
        self.position_btc: float = 0.0
        self.highest_price: Optional[float] = None
    
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """
        取引判断を行う（損失確定とトレーリングストップロス機能付き）
        """
        current_price = price_data.price
        
        # ポジションを持っている場合のチェック
        if self.entry_price is not None and self.position_btc > 0:
            # 最高価格を更新（トレーリングストップロス用）
            if self.highest_price is None:
                self.highest_price = current_price
            else:
                self.highest_price = max(self.highest_price, current_price)
            
            # 1. 損失確定チェック（最優先）
            loss_percentage = (current_price - self.entry_price) / self.entry_price
            
            if loss_percentage <= -self.stop_loss_percentage:
                # 損失確定トリガー
                entry = self.entry_price
                self.entry_price = None
                self.highest_price = None
                return TradingDecision(
                    agent_id=self.agent_id,
                    timestamp=datetime.utcnow(),
                    action=Action.SELL,
                    confidence=1.0,
                    price=current_price,
                    reason=f"Stop Loss triggered: {loss_percentage*100:.2f}% loss (entry: ${entry:.2f}, current: ${current_price:.2f})"
                )
            
            # 2. トレーリングストップロスチェック（利益確定）
            if self.trailing_stop_percentage is not None and self.highest_price is not None:
                decline_from_high = (current_price - self.highest_price) / self.highest_price
                
                if decline_from_high <= -self.trailing_stop_percentage:
                    # トレーリングストップロストリガー
                    entry = self.entry_price
                    highest = self.highest_price
                    profit_percentage = (current_price - entry) / entry
                    self.entry_price = None
                    self.highest_price = None
                    return TradingDecision(
                        agent_id=self.agent_id,
                        timestamp=datetime.utcnow(),
                        action=Action.SELL,
                        confidence=1.0,
                        price=current_price,
                        reason=f"Trailing Stop triggered: {decline_from_high*100:.2f}% decline from high ${highest:.2f} (entry: ${entry:.2f}, current: ${current_price:.2f}, profit: {profit_percentage*100:.2f}%)"
                    )
        
        # 通常のRSI+MACD+ボリンジャーバンド戦略
        decision = super().decide(price_data, historical_data)
        
        # 買い注文の場合は最高価格を初期化
        if decision.action == Action.BUY:
            self.highest_price = current_price
        # 売り注文の場合は最高価格をリセット
        elif decision.action == Action.SELL:
            self.highest_price = None
        
        return decision
    
    def update_position(self, entry_price: Optional[float], btc_holdings: float, current_price: Optional[float] = None):
        """
        ポジション情報を更新
        """
        self.entry_price = entry_price
        self.position_btc = btc_holdings
        
        if entry_price is None or btc_holdings <= 0:
            self.highest_price = None
        elif current_price is not None:
            if self.highest_price is None:
                self.highest_price = current_price
            else:
                self.highest_price = max(self.highest_price, current_price)
    
    def get_agent_type(self) -> str:
        return "RSI_MACD_BB_StopLoss"

