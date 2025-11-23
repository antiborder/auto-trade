#!/usr/bin/env python3
"""
Bitcoinの過去価格データを取得するスクリプト
2021年1月から2025年10月までの1時間ごとの価格データを取得
"""
import sys
import os
import csv
import requests
from datetime import datetime, timedelta
import time
from typing import List

# CoinGecko APIを使用（無料、レート制限あり）
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"


def fetch_historical_prices_coingecko(start_date: str, end_date: str, interval: str = "hourly") -> List[dict]:
    """
    CoinGecko APIから過去の価格データを取得
    
    Args:
        start_date: 開始日（YYYY-MM-DD形式）
        end_date: 終了日（YYYY-MM-DD形式）
        interval: データ間隔（"hourly"または"daily"）
    
    Returns:
        価格データのリスト
    """
    # CoinGeckoの市場データエンドポイントを使用
    # 1時間ごとのデータを取得するために、日付範囲を分割して取得する必要がある
    print(f"CoinGecko APIから価格データを取得中...")
    print(f"期間: {start_date} ～ {end_date}")
    
    all_data = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    # CoinGecko APIは一度に90日分のデータしか取得できないため、分割して取得
    current_date = start
    batch_days = 90  # 90日ごとに分割
    
    while current_date < end:
        batch_end = min(current_date + timedelta(days=batch_days), end)
        
        start_timestamp = int(current_date.timestamp())
        end_timestamp = int(batch_end.timestamp())
        
        print(f"  取得中: {current_date.strftime('%Y-%m-%d')} ～ {batch_end.strftime('%Y-%m-%d')}")
        
        url = f"{COINGECKO_API_URL}/coins/bitcoin/market_chart/range"
        params = {
            "vs_currency": "usd",
            "from": start_timestamp,
            "to": end_timestamp
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # prices配列からデータを取得（[timestamp, price]形式）
            if "prices" in data:
                for timestamp_ms, price in data["prices"]:
                    timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                    all_data.append({
                        "timestamp": timestamp,
                        "price": price
                    })
            
            # APIレート制限を避けるため、少し待機
            time.sleep(1)
            
        except Exception as e:
            print(f"  エラー: {e}")
            time.sleep(2)  # エラー時は少し長めに待機
            continue
        
        current_date = batch_end
    
    # タイムスタンプでソート
    all_data.sort(key=lambda x: x["timestamp"])
    
    return all_data


def fetch_historical_prices_binance(start_date: str, end_date: str, interval: str = "1h") -> List[dict]:
    """
    Binance APIから過去の価格データを取得（代替案）
    
    Args:
        start_date: 開始日（YYYY-MM-DD形式）
        end_date: 終了日（YYYY-MM-DD形式）
        interval: データ間隔（"15m" = 15分、"1h" = 1時間、"1d" = 1日）
    
    Returns:
        価格データのリスト
    """
    print(f"Binance APIから価格データを取得中...")
    print(f"期間: {start_date} ～ {end_date}")
    print(f"間隔: {interval}")
    
    BINANCE_API_URL = "https://api.binance.com/api/v3/klines"
    
    all_data = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Binance APIは一度に1000件まで取得可能
    current_date = start
    limit = 1000  # 1回あたりの最大件数
    
    # 間隔に応じて次のバッチの計算方法を変更
    if interval == "15m":
        time_delta = timedelta(minutes=15 * (limit - 1))
    elif interval == "1h":
        time_delta = timedelta(hours=limit - 1)
    elif interval == "1d":
        time_delta = timedelta(days=limit - 1)
    else:
        time_delta = timedelta(hours=limit - 1)  # デフォルト
    
    while current_date < end:
        # 次の1000件分の終了日を計算
        batch_end = min(current_date + time_delta, end)
        
        start_timestamp = int(current_date.timestamp() * 1000)  # ミリ秒
        end_timestamp = int(batch_end.timestamp() * 1000)
        
        print(f"  取得中: {current_date.strftime('%Y-%m-%d %H:%M')} ～ {batch_end.strftime('%Y-%m-%d %H:%M')}")
        
        params = {
            "symbol": "BTCUSDT",
            "interval": interval,
            "startTime": start_timestamp,
            "endTime": end_timestamp,
            "limit": limit
        }
        
        try:
            response = requests.get(BINANCE_API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                print(f"  警告: データが取得できませんでした。次のバッチに進みます。")
                current_date = batch_end
                continue
            
            for kline in data:
                # Binance kline形式: [open_time, open, high, low, close, volume, ...]
                timestamp_ms = int(kline[0])
                price = float(kline[4])  # close価格を使用
                
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                all_data.append({
                    "timestamp": timestamp,
                    "price": price
                })
            
            # APIレート制限を避けるため、少し待機
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  エラー: {e}")
            time.sleep(2)
            # エラー時は次のバッチに進む
            current_date = batch_end
            continue
        
        # 次のバッチの開始日を設定（最後のタイムスタンプの次）
        if data:
            last_timestamp_ms = int(data[-1][0])
            last_timestamp = datetime.fromtimestamp(last_timestamp_ms / 1000)
            
            # 間隔に応じて次の開始時刻を計算
            if interval == "15m":
                current_date = last_timestamp + timedelta(minutes=15)
            elif interval == "1h":
                current_date = last_timestamp + timedelta(hours=1)
            elif interval == "1d":
                current_date = last_timestamp + timedelta(days=1)
            else:
                current_date = last_timestamp + timedelta(hours=1)
        else:
            current_date = batch_end
    
    # タイムスタンプでソート
    all_data.sort(key=lambda x: x["timestamp"])
    
    return all_data


def save_to_csv(data: List[dict], output_path: str):
    """データをCSVファイルに保存"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'price'])
        
        for item in data:
            writer.writerow([
                item['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                item['price']
            ])


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Bitcoinの過去価格データを取得")
    parser.add_argument(
        "--start-date",
        type=str,
        default="2021-01-01",
        help="開始日（YYYY-MM-DD形式、デフォルト: 2021-01-01）"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2025-10-31",
        help="終了日（YYYY-MM-DD形式、デフォルト: 2025-10-31）"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/btc_prices_2021_2025.csv",
        help="出力CSVファイルパス"
    )
    parser.add_argument(
        "--api",
        type=str,
        choices=["binance", "coingecko"],
        default="binance",
        help="使用するAPI（デフォルト: binance）"
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="1h",
        choices=["15m", "1h", "4h", "1d"],
        help="データ間隔（15m=15分、1h=1時間、4h=4時間、1d=1日、デフォルト: 1h）"
    )
    
    args = parser.parse_args()
    
    # プロジェクトルートを取得
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.join(project_root, output_path)
    
    # 出力ディレクトリを作成
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # データを取得
    if args.api == "binance":
        data = fetch_historical_prices_binance(args.start_date, args.end_date, interval=args.interval)
    else:
        # CoinGeckoは間隔オプションをサポートしていないため、hourlyのみ
        data = fetch_historical_prices_coingecko(args.start_date, args.end_date, interval="hourly")
    
    if not data:
        print("エラー: データが取得できませんでした")
        sys.exit(1)
    
    print(f"\n取得したデータ件数: {len(data)}")
    print(f"期間: {data[0]['timestamp']} ～ {data[-1]['timestamp']}")
    print(f"初期価格: ${data[0]['price']:,.2f}")
    print(f"最終価格: ${data[-1]['price']:,.2f}")
    
    # CSVに保存
    save_to_csv(data, output_path)
    print(f"\nデータを保存しました: {output_path}")

