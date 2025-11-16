"""
Gate.io取引所用トレーダー
"""
import os
import requests
import hmac
import hashlib
import time
from datetime import datetime
from typing import Optional, List
from shared.traders.base_trader import BaseTrader
from shared.models.trading import Action, Order, OrderStatus, PriceData


class GateIOTrader(BaseTrader):
    """Gate.io取引所用トレーダー"""
    
    def __init__(self, trader_id: str, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        super().__init__(trader_id, api_key, api_secret)
        self.base_url = "https://api.gateio.ws/api/v4"
    
    def _generate_signature(self, method: str, url_path: str, query_string: str = "", payload: str = "") -> dict:
        """Gate.io API署名を生成"""
        if not self.api_key or not self.api_secret:
            return {}
        
        timestamp = str(time.time())
        
        # 署名文字列を作成
        # Format: METHOD\nURL\nQuery String\nSHA256 Payload\nTimestamp
        payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest() if payload else ""
        sign_string = f"{method}\n{url_path}\n{query_string}\n{payload_hash}\n{timestamp}"
        
        # HMAC-SHA512で署名
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return {
            "KEY": self.api_key,
            "Timestamp": timestamp,
            "SIGN": signature
        }
    
    def get_current_price(self, symbol: str = "BTC_USDT") -> Optional[PriceData]:
        """
        現在の価格を取得
        
        Args:
            symbol: 取引ペア（デフォルト: BTC_USDT、Gate.ioはアンダースコア区切り）
            
        Returns:
            PriceData: 価格データ
        """
        try:
            # Gate.io Public API: Get Ticker
            url = f"{self.base_url}/spot/tickers"
            params = {"currency_pair": symbol}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                ticker = data[0]
                
                return PriceData(
                    timestamp=datetime.utcnow(),
                    price=float(ticker.get("last", 0)),
                    volume=float(ticker.get("base_volume", 0)),
                    high=float(ticker.get("high_24h", 0)),
                    low=float(ticker.get("low_24h", 0)),
                    open=float(ticker.get("open_24h", 0)),
                    close=float(ticker.get("last", 0))
                )
            else:
                print(f"Gate.io API error: Invalid response format")
                return None
                
        except Exception as e:
            print(f"Error fetching price from Gate.io: {str(e)}")
            return None
    
    def get_klines(self, symbol: str = "BTC_USDT", interval: str = "5m", limit: int = 100) -> List[PriceData]:
        """
        K線データ（ローソク足）を取得
        
        Args:
            symbol: 取引ペア（デフォルト: BTC_USDT）
            interval: 時間間隔（1m, 5m, 15m, 30m, 1h, 4h, 1d）
            limit: 取得件数（最大1000）
            
        Returns:
            List[PriceData]: 価格データのリスト
        """
        try:
            url = f"{self.base_url}/spot/candlesticks"
            params = {
                "currency_pair": symbol,
                "interval": interval,
                "limit": min(limit, 1000)
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                price_data_list = []
                
                # K線データは時系列順（古い順）
                for kline in reversed(data):  # 新しい順に並び替え
                    # [timestamp, volume, close, high, low, open]
                    timestamp_s = int(kline[0])
                    timestamp = datetime.fromtimestamp(timestamp_s)
                    
                    price_data_list.append(PriceData(
                        timestamp=timestamp,
                        price=float(kline[2]),  # close price
                        volume=float(kline[1]),  # volume
                        high=float(kline[3]),  # high
                        low=float(kline[4]),  # low
                        open=float(kline[5]),  # open
                        close=float(kline[2])  # close
                    ))
                
                return price_data_list
            else:
                print(f"Gate.io API error: Invalid response format")
                return []
                
        except Exception as e:
            print(f"Error fetching klines from Gate.io: {str(e)}")
            return []
    
    def execute_order(self, action: Action, amount: float, price: Optional[float] = None) -> Order:
        """
        注文を実行
        
        Args:
            action: 買い/売り
            amount: 数量
            price: 価格（Noneの場合は成行注文）
            
        Returns:
            Order: 注文結果
        """
        if not self.api_key or not self.api_secret:
            return Order(
                order_id=f"{self.trader_id}_{datetime.utcnow().isoformat()}",
                agent_id="",
                action=action,
                amount=amount,
                price=price or 0.0,
                timestamp=datetime.utcnow(),
                status=OrderStatus.FAILED,
                trader_id=self.trader_id,
                error_message="API key or secret not configured"
            )
        
        try:
            symbol = "BTC_USDT"
            url_path = "/spot/orders"
            url = f"{self.base_url}{url_path}"
            
            # 注文パラメータ
            order_data = {
                "currency_pair": symbol,
                "side": "buy" if action == Action.BUY else "sell",
                "amount": str(amount),
            }
            
            if price:
                order_data["price"] = str(price)
                order_data["type"] = "limit"
            else:
                order_data["type"] = "market"
            
            payload = ""
            query_string = ""
            
            # 署名を生成
            headers = self._generate_signature("POST", url_path, query_string, payload)
            headers["Content-Type"] = "application/json"
            
            response = requests.post(url, json=order_data, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "id" in data:
                order_id = data.get("id", f"{self.trader_id}_{datetime.utcnow().isoformat()}")
                status_str = data.get("status", "open")
                
                # Gate.ioのステータスをOrderStatusに変換
                if status_str in ["filled", "closed"]:
                    order_status = OrderStatus.EXECUTED
                elif status_str == "cancelled":
                    order_status = OrderStatus.CANCELLED
                else:
                    order_status = OrderStatus.PENDING
                
                return Order(
                    order_id=str(order_id),
                    agent_id="",
                    action=action,
                    amount=amount,
                    price=price or float(data.get("price", 0)),
                    timestamp=datetime.utcnow(),
                    status=order_status,
                    trader_id=self.trader_id,
                    execution_price=float(data.get("filled_total", price or 0)) / amount if amount > 0 else price or 0.0,
                    execution_timestamp=datetime.utcnow() if order_status == OrderStatus.EXECUTED else None
                )
            else:
                error_msg = data.get("label", "Unknown error")
                return Order(
                    order_id=f"{self.trader_id}_{datetime.utcnow().isoformat()}",
                    agent_id="",
                    action=action,
                    amount=amount,
                    price=price or 0.0,
                    timestamp=datetime.utcnow(),
                    status=OrderStatus.FAILED,
                    trader_id=self.trader_id,
                    error_message=f"Gate.io API error: {error_msg}"
                )
                
        except Exception as e:
            return Order(
                order_id=f"{self.trader_id}_{datetime.utcnow().isoformat()}",
                agent_id="",
                action=action,
                amount=amount,
                price=price or 0.0,
                timestamp=datetime.utcnow(),
                status=OrderStatus.FAILED,
                trader_id=self.trader_id,
                error_message=str(e)
            )
    
    def get_balance(self) -> dict:
        """残高を取得"""
        if not self.api_key or not self.api_secret:
            return {"error": "API key or secret not configured"}
        
        try:
            url_path = "/spot/accounts"
            url = f"{self.base_url}{url_path}"
            query_string = ""
            payload = ""
            
            headers = self._generate_signature("GET", url_path, query_string, payload)
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                # Gate.ioの残高レスポンスをBybit形式に変換（互換性のため）
                result = {
                    "result": {
                        "list": [{
                            "coin": data  # Gate.ioは直接coinのリストを返す
                        }]
                    }
                }
                return result
            else:
                return {"error": "Invalid response format"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def get_trader_type(self) -> str:
        """トレーダータイプを返す"""
        return "Gate.io"

