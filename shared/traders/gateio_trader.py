"""
Gate.io取引所用トレーダー
"""
import os
import json
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
    
    def __init__(self, trader_id: str, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = True):
        super().__init__(trader_id, api_key, api_secret)
        # Testnet用のAPIエンドポイントを使用
        if testnet:
            self.base_url = "https://api-testnet.gateapi.io/api/v4"
        else:
            self.base_url = "https://api.gateio.ws/api/v4"
    
    def _generate_signature(self, method: str, url_path: str, query_string: str = "", payload: str = "") -> dict:
        """
        Gate.io API署名を生成
        
        Signature string format:
        METHOD\nURL\nQuery String\nHexEncode(SHA512(Payload))\nTimestamp
        
        Reference: https://www.gate.io/docs/developers/apiv4/
        """
        if not self.api_key or not self.api_secret:
            return {}
        
        # タイムスタンプはUnix時間（秒）の整数値（ドキュメントの例に従う）
        timestamp = str(int(time.time()))
        
        # PayloadをSHA512でハッシュしてHexEncode
        # 空のペイロードの場合は空文字列のハッシュ結果を使用
        m = hashlib.sha512()
        m.update((payload or "").encode('utf-8'))
        payload_hash = m.hexdigest()
        
        # 署名文字列を作成
        # Format: METHOD\nURL\nQuery String\nHexEncode(SHA512(Payload))\nTimestamp
        # ドキュメントの例に従い、query_stringがNoneの場合は空文字列を使用
        query_str = query_string if query_string else ""
        sign_string = f"{method}\n{url_path}\n{query_str}\n{payload_hash}\n{timestamp}"
        
        # デバッグ: 署名文字列の形式を確認（改行を\\nで表示）
        print(f"Signature string (repr): {repr(sign_string)}")
        print(f"Signature string length: {len(sign_string)}")
        print(f"Payload hash: {payload_hash}")
        print(f"Query string: '{query_str}'")
        print(f"Timestamp: {timestamp}")
        
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
            # Gate.io APIの署名文字列には /api/v4 を含める必要がある
            url_path = "/api/v4/spot/orders"
            url = f"{self.base_url}/spot/orders"
            
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
            
            # 注文データをJSON文字列に変換（署名生成用）
            payload_string = json.dumps(order_data)
            query_string = ""
            
            # 署名を生成（payloadはJSON文字列）
            headers = self._generate_signature("POST", url_path, query_string, payload_string)
            headers["Content-Type"] = "application/json"
            
            # リクエストボディはJSON文字列として送信
            response = requests.post(url, data=payload_string, headers=headers, timeout=10)
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
        """
        残高を取得
        
        Returns:
            dict: Gate.io APIの残高レスポンス形式
            [
                {
                    "currency": "USDT",
                    "available": "1000.0",
                    "locked": "0.0"
                },
                {
                    "currency": "BTC",
                    "available": "0.1",
                    "locked": "0.0"
                }
            ]
        """
        if not self.api_key or not self.api_secret:
            return {"error": "API key or secret not configured"}
        
        try:
            # Gate.io APIの署名文字列には /api/v4 を含める必要がある
            url_path = "/api/v4/spot/accounts"
            url = f"{self.base_url}/spot/accounts"
            query_string = ""
            payload = ""
            
            print(f"Getting balance from Gate.io: {url}")
            headers = self._generate_signature("GET", url_path, query_string, payload)
            print(f"Headers: KEY={headers.get('KEY', 'N/A')[:10]}..., Timestamp={headers.get('Timestamp', 'N/A')}, SIGN={headers.get('SIGN', 'N/A')[:20]}...")
            
            response = requests.get(url, headers=headers, timeout=10)
            print(f"Response status: {response.status_code}")
            if response.status_code != 200:
                print(f"Response body: {response.text[:500]}")
            response.raise_for_status()
            data = response.json()
            
            # Gate.io APIは直接coinのリストを返す
            if isinstance(data, list):
                return data
            else:
                return {"error": "Invalid response format"}
                
        except Exception as e:
            print(f"Error getting balance from Gate.io: {str(e)}")
            return {"error": str(e)}
    
    def get_trader_type(self) -> str:
        """トレーダータイプを返す"""
        return "Gate.io"

