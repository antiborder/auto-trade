"""
Bybit取引所用トレーダー
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


class BybitTrader(BaseTrader):
    """Bybit取引所用トレーダー"""
    
    def __init__(self, trader_id: str, api_key: Optional[str] = None, api_secret: Optional[str] = None, testnet: bool = False):
        super().__init__(trader_id, api_key, api_secret)
        self.testnet = testnet
        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
    
    def _generate_signature(self, params: dict, timestamp: str, recv_window: str = "5000") -> str:
        """API署名を生成"""
        if not self.api_secret:
            return ""
        
        # パラメータをソートしてクエリ文字列を作成
        sorted_params = sorted(params.items())
        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
        
        # Bybit API v5の署名形式: timestamp + api_key + recv_window + query_string
        signature_string = f"{timestamp}{self.api_key}{recv_window}{query_string}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def get_current_price(self, symbol: str = "BTCUSDT") -> Optional[PriceData]:
        """
        現在の価格を取得
        
        Args:
            symbol: 取引ペア（デフォルト: BTCUSDT）
            
        Returns:
            PriceData: 価格データ
        """
        try:
            # Bybit Public API: Get Ticker
            url = f"{self.base_url}/v5/market/tickers"
            params = {
                "category": "spot",
                "symbol": symbol
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                ticker = data["result"]["list"][0]
                
                return PriceData(
                    timestamp=datetime.utcnow(),
                    price=float(ticker.get("lastPrice", 0)),
                    volume=float(ticker.get("volume24h", 0)),
                    high=float(ticker.get("highPrice24h", 0)),
                    low=float(ticker.get("lowPrice24h", 0)),
                    open=float(ticker.get("prevPrice24h", 0)),
                    close=float(ticker.get("lastPrice", 0))
                )
            else:
                print(f"Bybit API error: {data.get('retMsg', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"Error fetching price from Bybit: {str(e)}")
            return None
    
    def get_klines(self, symbol: str = "BTCUSDT", interval: str = "5", limit: int = 100) -> List[PriceData]:
        """
        K線データ（ローソク足）を取得
        
        Args:
            symbol: 取引ペア（デフォルト: BTCUSDT）
            interval: 時間間隔（1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, M, W）
            limit: 取得件数（最大200）
            
        Returns:
            List[PriceData]: 価格データのリスト
        """
        try:
            url = f"{self.base_url}/v5/market/kline"
            params = {
                "category": "spot",
                "symbol": symbol,
                "interval": interval,
                "limit": min(limit, 200)
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                klines = data["result"]["list"]
                price_data_list = []
                
                # K線データは時系列順（古い順）
                for kline in reversed(klines):  # 新しい順に並び替え
                    # [startTime, open, high, low, close, volume, turnover]
                    timestamp_ms = int(kline[0])
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                    
                    price_data_list.append(PriceData(
                        timestamp=timestamp,
                        price=float(kline[4]),  # close price
                        volume=float(kline[5]),  # volume
                        high=float(kline[2]),  # high
                        low=float(kline[3]),  # low
                        open=float(kline[1]),  # open
                        close=float(kline[4])  # close
                    ))
                
                return price_data_list
            else:
                print(f"Bybit API error: {data.get('retMsg', 'Unknown error')}")
                return []
                
        except Exception as e:
            print(f"Error fetching klines from Bybit: {str(e)}")
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
            timestamp = str(int(time.time() * 1000))
            symbol = "BTCUSDT"
            
            # 注文パラメータ
            params = {
                "category": "spot",
                "symbol": symbol,
                "side": "Buy" if action == Action.BUY else "Sell",
                "orderType": "Limit" if price else "Market",
                "qty": str(amount),
            }
            
            if price:
                params["price"] = str(price)
            
            # 署名を生成
            recv_window = "5000"
            signature = self._generate_signature(params, timestamp, recv_window)
            
            # リクエストヘッダー
            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-SIGN": signature,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window,
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/v5/order/create"
            response = requests.post(url, json=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("retCode") == 0:
                result = data.get("result", {})
                order_id = result.get("orderId", f"{self.trader_id}_{datetime.utcnow().isoformat()}")
                
                return Order(
                    order_id=str(order_id),
                    agent_id="",
                    action=action,
                    amount=amount,
                    price=price or 0.0,
                    timestamp=datetime.utcnow(),
                    status=OrderStatus.EXECUTED,
                    trader_id=self.trader_id,
                    execution_price=float(result.get("avgPrice", price or 0.0)),
                    execution_timestamp=datetime.utcnow()
                )
            else:
                error_msg = data.get("retMsg", "Unknown error")
                return Order(
                    order_id=f"{self.trader_id}_{datetime.utcnow().isoformat()}",
                    agent_id="",
                    action=action,
                    amount=amount,
                    price=price or 0.0,
                    timestamp=datetime.utcnow(),
                    status=OrderStatus.FAILED,
                    trader_id=self.trader_id,
                    error_message=f"Bybit API error: {error_msg}"
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
            timestamp = str(int(time.time() * 1000))
            recv_window = "5000"
            params = {
                "accountType": "UNIFIED"
            }
            
            signature = self._generate_signature(params, timestamp, recv_window)
            
            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-SIGN": signature,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": recv_window,
                "Content-Type": "application/json"
            }
            
            url = f"{self.base_url}/v5/account/wallet-balance"
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # デバッグ用: Bybitからのレスポンスをログ出力
            print(f"Bybit API response: {data}")
            
            if data.get("retCode") == 0:
                result = data.get("result", {})
                return result
            else:
                error_msg = data.get("retMsg", "Unknown error")
                print(f"Bybit API error: retCode={data.get('retCode')}, retMsg={error_msg}")
                return {"error": error_msg}
                
        except Exception as e:
            return {"error": str(e)}
    
    def get_trader_type(self) -> str:
        """トレーダータイプを返す"""
        return "Bybit"

