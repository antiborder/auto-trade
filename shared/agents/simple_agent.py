"""
移動平均ベースの取引エージェント
"""
from datetime import datetime
from shared.agents.base_agent import BaseAgent
from shared.models.trading import Action, PriceData, TradingDecision


class MaAgent(BaseAgent):
    """移動平均クロスオーバー戦略のエージェント"""
    
    def __init__(self, agent_id: str, trader_id: str = None, short_window: int = 5, long_window: int = 20):
        super().__init__(agent_id, trader_id)
        self.short_window = short_window
        self.long_window = long_window
    
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """移動平均クロスオーバー戦略"""
        if len(historical_data) < self.long_window:
            return TradingDecision(
                agent_id=self.agent_id,
                timestamp=datetime.utcnow(),
                action=Action.HOLD,
                confidence=0.5,
                price=price_data.price,
                reason="Insufficient historical data"
            )
        
        # 移動平均計算
        recent_prices = [d.price for d in historical_data[-self.long_window:]]
        short_ma = sum(recent_prices[-self.short_window:]) / self.short_window
        long_ma = sum(recent_prices) / self.long_window
        
        # 判断ロジック
        if short_ma > long_ma:
            action = Action.BUY
            confidence = min(0.9, 0.5 + (short_ma - long_ma) / long_ma)
            reason = f"Short MA ({short_ma:.2f}) > Long MA ({long_ma:.2f})"
        elif short_ma < long_ma:
            action = Action.SELL
            confidence = min(0.9, 0.5 + (long_ma - short_ma) / long_ma)
            reason = f"Short MA ({short_ma:.2f}) < Long MA ({long_ma:.2f})"
        else:
            action = Action.HOLD
            confidence = 0.5
            reason = "MA crossover neutral"
        
        return TradingDecision(
            agent_id=self.agent_id,
            timestamp=datetime.utcnow(),
            action=action,
            confidence=confidence,
            price=price_data.price,
            reason=reason
        )
    
    def get_agent_type(self) -> str:
        return "MA"


