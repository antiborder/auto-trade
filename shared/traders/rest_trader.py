"""
REST APIを使用するトレーダー
"""
import os
import requests
from datetime import datetime
from typing import Optional
from shared.traders.base_trader import BaseTrader
from shared.models.trading import Action, Order, OrderStatus


class RESTTrader(BaseTrader):
    """REST API経由で注文を実行するトレーダー"""
    
    def __init__(self, trader_id: str, api_endpoint: str, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        super().__init__(trader_id, api_key, api_secret)
        self.api_endpoint = api_endpoint
    
    def execute_order(self, action: Action, amount: float, price: float) -> Order:
        """REST APIで注文を実行"""
        order_id = f"{self.trader_id}_{datetime.utcnow().isoformat()}"
        
        try:
            # REST APIリクエスト
            payload = {
                "action": action.value,
                "amount": amount,
                "price": price,
                "order_id": order_id
            }
            
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            if self.api_secret:
                headers["X-API-Secret"] = self.api_secret
            
            response = requests.post(
                f"{self.api_endpoint}/orders",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return Order(
                    order_id=order_id,
                    agent_id="",  # 呼び出し元で設定
                    action=action,
                    amount=amount,
                    price=price,
                    timestamp=datetime.utcnow(),
                    status=OrderStatus.EXECUTED,
                    trader_id=self.trader_id,
                    execution_price=result.get("execution_price", price),
                    execution_timestamp=datetime.utcnow()
                )
            else:
                return Order(
                    order_id=order_id,
                    agent_id="",
                    action=action,
                    amount=amount,
                    price=price,
                    timestamp=datetime.utcnow(),
                    status=OrderStatus.FAILED,
                    trader_id=self.trader_id,
                    error_message=f"API returned status {response.status_code}: {response.text}"
                )
        except Exception as e:
            return Order(
                order_id=order_id,
                agent_id="",
                action=action,
                amount=amount,
                price=price,
                timestamp=datetime.utcnow(),
                status=OrderStatus.FAILED,
                trader_id=self.trader_id,
                error_message=str(e)
            )
    
    def get_balance(self) -> dict:
        """残高を取得"""
        try:
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            
            response = requests.get(
                f"{self.api_endpoint}/balance",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to get balance: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_trader_type(self) -> str:
        return "REST"


