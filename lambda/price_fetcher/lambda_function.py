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
    """Bitcoinの現在価格を取得"""
    try:
        # CoinGecko APIを使用（無料、認証不要）
        response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        bitcoin_data = data.get('bitcoin', {})
        price = bitcoin_data.get('usd', 0)
        volume_24h = bitcoin_data.get('usd_24h_vol', 0)
        change_24h = bitcoin_data.get('usd_24h_change', 0)
        
        return {
            'price': price,
            'volume_24h': volume_24h,
            'change_24h': change_24h
        }
    except Exception as e:
        print(f"Error fetching price: {str(e)}")
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
        
        prices_table.put_item(Item=item)
        
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


