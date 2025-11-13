"""
トレーダーの基底クラス
"""
from abc import ABC, abstractmethod
from typing import Optional
from shared.models.trading import Action, Order, OrderStatus


class BaseTrader(ABC):
    """トレーダーの基底クラス"""
    
    def __init__(self, trader_id: str, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.trader_id = trader_id
        self.api_key = api_key
        self.api_secret = api_secret
    
    @abstractmethod
    def execute_order(self, action: Action, amount: float, price: float) -> Order:
        """
        注文を実行
        
        Args:
            action: 買い/売り
            amount: 数量
            price: 価格
            
        Returns:
            Order: 注文結果
        """
        pass
    
    @abstractmethod
    def get_balance(self) -> dict:
        """残高を取得"""
        pass
    
    @abstractmethod
    def get_trader_type(self) -> str:
        """トレーダータイプを返す"""
        pass


