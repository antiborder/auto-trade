#!/usr/bin/env python3
"""
Gate.io APIの残高取得エンドポイントをテストするスクリプト
"""
import hmac
import hashlib
import time
import requests
import sys
import os

# API認証情報（環境変数または引数から取得）
api_key = os.getenv('GATEIO_API_KEY') or (sys.argv[1] if len(sys.argv) > 1 else None)
api_secret = os.getenv('GATEIO_API_SECRET') or (sys.argv[2] if len(sys.argv) > 2 else None)

if not api_key or not api_secret:
    print("Error: API key and secret are required")
    print("Usage: python3 test_gateio_balance.py <api_key> <api_secret>")
    print("Or set environment variables: GATEIO_API_KEY and GATEIO_API_SECRET")
    sys.exit(1)

def generate_signature(method, url_path, query_string='', payload=''):
    """Gate.io API署名を生成"""
    timestamp = str(time.time())
    payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest() if payload else ''
    sign_string = f'{method}\n{url_path}\n{query_string}\n{payload_hash}\n{timestamp}'
    signature = hmac.new(
        api_secret.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()
    return {
        'KEY': api_key,
        'Timestamp': timestamp,
        'SIGN': signature
    }

# エンドポイント情報
base_url = "https://api.gateio.ws/api/v4"
url_path = "/spot/accounts"
url = f"{base_url}{url_path}"

print(f"Testing Gate.io API endpoint: {url}")
print(f"Method: GET")
print(f"API Key: {api_key[:10]}...")

# 署名を生成
headers = generate_signature('GET', url_path)
print(f"Timestamp: {headers['Timestamp']}")
print(f"Signature: {headers['SIGN'][:20]}...")

# リクエストを送信
try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Success! Response data:")
        print(f"Type: {type(data)}")
        if isinstance(data, list):
            print(f"Number of accounts: {len(data)}")
            for account in data[:5]:  # 最初の5件を表示
                print(f"  - {account}")
        else:
            print(f"Data: {data}")
    else:
        print(f"\n❌ Error: {response.status_code}")
        print(f"Response: {response.text}")
        
except requests.exceptions.RequestException as e:
    print(f"\n❌ Request failed: {str(e)}")
    sys.exit(1)

