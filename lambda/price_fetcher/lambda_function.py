"""
価格取得Lambda関数
Bitcoinの価格を取得してDynamoDBに保存
"""
import json
import os
from datetime import datetime
from decimal import Decimal
import boto3
import requests

# DynamoDBクライアント
dynamodb = boto3.resource('dynamodb')
prices_table = dynamodb.Table(os.environ['PRICES_TABLE'])

def fetch_bitcoin_price():
    """Bitcoinの現在価格をBybitから取得"""
    try:
        # Bybit Public APIを使用（認証不要）
        # テストネットかどうかを環境変数から取得（デフォルトは本番環境）
        use_testnet = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'
        base_url = "https://api-testnet.bybit.com" if use_testnet else "https://api.bybit.com"
        
        url = f"{base_url}/v5/market/tickers"
        params = {
            "category": "spot",
            "symbol": "BTCUSDT"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("retCode") == 0 and data.get("result", {}).get("list"):
            ticker = data["result"]["list"][0]
            
            price = float(ticker.get("lastPrice", 0))
            volume_24h = float(ticker.get("volume24h", 0))
            prev_price_24h = float(ticker.get("prevPrice24h", price))
            
            # 24時間変動率を計算（%）
            if prev_price_24h > 0:
                change_24h = ((price - prev_price_24h) / prev_price_24h) * 100
            else:
                change_24h = 0.0
            
            return {
                'price': price,
                'volume_24h': volume_24h,
                'change_24h': change_24h
            }
        else:
            error_msg = data.get("retMsg", "Unknown error")
            raise Exception(f"Bybit API error: {error_msg}")
            
    except Exception as e:
        print(f"Error fetching price from Bybit: {str(e)}")
        raise

def lambda_handler(event, context):
    """
    Lambdaハンドラー
    Bitcoinの価格を取得してDynamoDBに保存
    """
    try:
        # 価格を取得
        price_data = fetch_bitcoin_price()
        
        # タイムスタンプ
        timestamp = datetime.utcnow().isoformat()
        
        # DynamoDBに保存（数値はDecimal型に変換）
        item = {
            'timestamp': timestamp,
            'price': Decimal(str(price_data['price'])),
            'volume_24h': Decimal(str(price_data.get('volume_24h', 0))),
            'change_24h': Decimal(str(price_data.get('change_24h', 0)))
        }
        
        # DynamoDBに保存（明示的なエラーハンドリング）
        try:
            print(f"Attempting to save item: {json.dumps({k: str(v) for k, v in item.items()}, default=str)}")
            response = prices_table.put_item(Item=item)
            print(f"DynamoDB put_item response: {json.dumps(response, default=str)}")
            
            # Verify the item was actually saved by reading it back
            verify_response = prices_table.get_item(Key={'timestamp': timestamp})
            if 'Item' in verify_response:
                print(f"✅ Verified: Item exists in DynamoDB")
            else:
                print(f"❌ WARNING: Item not found in DynamoDB after put_item!")
                
        except Exception as db_error:
            print(f"Error saving to DynamoDB: {str(db_error)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise
        
        print(f"Price saved successfully: timestamp={timestamp}, price={price_data['price']}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Price saved successfully',
                'timestamp': timestamp,
                'price': price_data['price']
            })
        }
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


