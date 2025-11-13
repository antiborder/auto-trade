"""
取引エージェントの基底クラス
"""
from abc import ABC, abstractmethod
from typing import Optional
from shared.models.trading import Action, PriceData, TradingDecision


class BaseAgent(ABC):
    """取引エージェントの基底クラス"""
    
    def __init__(self, agent_id: str, trader_id: Optional[str] = None):
        self.agent_id = agent_id
        self.trader_id = trader_id
    
    @abstractmethod
    def decide(self, price_data: PriceData, historical_data: list[PriceData]) -> TradingDecision:
        """
        取引判断を行う
        
        Args:
            price_data: 現在の価格データ
            historical_data: 過去の価格データ
            
        Returns:
            TradingDecision: 取引判断
        """
        pass
    
    @abstractmethod
    def get_agent_type(self) -> str:
        """エージェントタイプを返す"""
        pass


