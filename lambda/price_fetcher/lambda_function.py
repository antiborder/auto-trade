"""
価格取得Lambda関数
EventBridgeから定期的にトリガーされ、最新の価格を取得してDynamoDBに保存
"""
import json
import os
import sys
from datetime import datetime
import requests

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))
from dynamodb.client import DynamoDBClient


def fetch_bitcoin_price() -> dict:
    """Bitcoinの現在価格を取得（例: CoinGecko API）"""
    try:
        # CoinGecko APIの例
        response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true',
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            btc_data = data.get('bitcoin', {})
            return {
                'price': btc_data.get('usd', 0),
                'volume_24h': btc_data.get('usd_24h_vol', 0),
                'change_24h': btc_data.get('usd_24h_change', 0)
            }
        else:
            raise Exception(f"API returned status {response.status_code}")
    except Exception as e:
        print(f"Error fetching price: {e}")
        raise


def lambda_handler(event, context):
    """
    Lambdaハンドラー
    
    EventBridgeからトリガーされ、価格を取得してDynamoDBに保存
    """
    try:
        # 価格取得
        price_data = fetch_bitcoin_price()
        timestamp = datetime.utcnow()
        
        # DynamoDBに保存
        db_client = DynamoDBClient()
        db_client.put_price(
            timestamp=timestamp,
            price=price_data['price'],
            volume_24h=price_data.get('volume_24h'),
            change_24h=price_data.get('change_24h')
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Price fetched and saved successfully',
                'timestamp': timestamp.isoformat(),
                'price': price_data['price']
            })
        }
    except Exception as e:
        print(f"Error in price_fetcher: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


