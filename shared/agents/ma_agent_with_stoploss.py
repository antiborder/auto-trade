"""
損失確定機能付き移動平均エージェント
"""
from datetime import datetime
from typing import Optional
from shared.agents.ma_agent import MaAgent
from shared.models.trading import Action, PriceData, TradingDecision


class MaAgentWithStopLoss(MaAgent):
    """損失確定機能（パーセンテージベース）付き移動平均エージェント"""
    
    def __init__(
        self,
        agent_id: str,
        trader_id: str = None,
        short_window: int = 5,
        long_window: int = 20,
        stop_loss_percentage: float = 0.07  # デフォルト -7%
    ):
        """
        初期化
        
        Args:
            agent_id: エージェントID
            trader_id: トレーダーID
            short_window: 短期移動平均のウィンドウサイズ
            long_window: 長期移動平均のウィンドウサイズ
            stop_loss_percentage: 損失確定パーセンテージ（0.07 = 7%）
        """
        super().__init__(agent_id, trader_id, short_window, long_window)
        self.stop_loss_percentage = stop_loss_percentage
        
        # ポジション管理
        self.entry_price: Optional[float] = None  # エントリー価格
        self.position_btc: float = 0.0  # 現在のBTC保有量
        
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """
        取引判断を行う（損失確定機能付き）
        
        Args:
            price_data: 現在の価格データ
            historical_data: 過去の価格データ
        
        Returns:
            TradingDecision: 取引判断
        """
        # 損失確定判定（優先度が最も高い）
        # エントリー価格が設定されており、BTC保有している場合
        if self.entry_price is not None and self.position_btc > 0:
            current_price = price_data.price
            loss_percentage = (current_price - self.entry_price) / self.entry_price
            
            if loss_percentage <= -self.stop_loss_percentage:
                # 損失確定トリガー
                entry = self.entry_price
                self.entry_price = None  # ポジションをリセット
                return TradingDecision(
                    agent_id=self.agent_id,
                    timestamp=datetime.utcnow(),
                    action=Action.SELL,
                    confidence=1.0,
                    price=current_price,
                    reason=f"Stop Loss triggered: {loss_percentage*100:.2f}% loss (entry: ${entry:.2f}, current: ${current_price:.2f})"
                )
        
        # 通常の移動平均クロスオーバー戦略
        decision = super().decide(price_data, historical_data)
        
        return decision
    
    def update_position(self, entry_price: Optional[float], btc_holdings: float):
        """
        ポジション情報を更新
        
        Args:
            entry_price: エントリー価格（Noneの場合はポジションなし）
            btc_holdings: 現在のBTC保有量
        """
        self.entry_price = entry_price
        self.position_btc = btc_holdings
    
    def check_stop_loss(self, current_price: float) -> Optional[TradingDecision]:
        """
        損失確定条件をチェック（外部から呼び出す用）
        
        Args:
            current_price: 現在の価格
        
        Returns:
            損失確定の場合はTradingDecision、そうでなければNone
        """
        if self.entry_price is not None and self.position_btc > 0:
            loss_percentage = (current_price - self.entry_price) / self.entry_price
            
            if loss_percentage <= -self.stop_loss_percentage:
                entry = self.entry_price
                self.entry_price = None
                return TradingDecision(
                    agent_id=self.agent_id,
                    timestamp=datetime.utcnow(),
                    action=Action.SELL,
                    confidence=1.0,
                    price=current_price,
                    reason=f"Stop Loss triggered: {loss_percentage*100:.2f}% loss (entry: ${entry:.2f}, current: ${current_price:.2f})"
                )
        return None
    
    def get_agent_type(self) -> str:
        return "MA_StopLoss"

