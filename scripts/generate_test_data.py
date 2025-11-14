"""
Bitcoin価格のテストデータを生成するスクリプト
実際のBitcoin価格の特徴を模倣した時系列データを生成
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import os


def generate_bitcoin_price_data(
    start_date: str = "2023-01-01",
    days: int = 365,
    initial_price: float = 30000.0,
    volatility: float = 0.02,
    trend: float = 0.0001
) -> pd.DataFrame:
    """
    Bitcoin価格のテストデータを生成
    
    Args:
        start_date: 開始日（YYYY-MM-DD形式）
        days: 生成する日数
        initial_price: 初期価格（USD）
        volatility: ボラティリティ（1日の変動率の標準偏差）
        trend: 1日あたりのトレンド（上昇率）
        
    Returns:
        DataFrame: timestampとpriceカラムを持つデータ
    """
    # 日付範囲を生成（1時間ごと）
    start = datetime.strptime(start_date, "%Y-%m-%d")
    dates = [start + timedelta(hours=i) for i in range(days * 24)]
    
    # 価格データを生成（幾何ブラウン運動を模倣）
    prices = []
    current_price = initial_price
    
    for i in range(len(dates)):
        # ランダムウォーク + トレンド + ボラティリティ
        # 実際のBitcoin価格の特徴を模倣
        random_change = np.random.normal(0, volatility)
        
        # 週末や夜間はボラティリティが低い傾向を模倣
        hour = dates[i].hour
        if 2 <= hour <= 6:  # 深夜は低ボラティリティ
            random_change *= 0.5
        
        # トレンドを追加
        price_change = trend + random_change
        
        # 価格を更新（対数正規分布を模倣）
        current_price *= (1 + price_change)
        
        # 価格が極端に下がらないようにする
        current_price = max(current_price, initial_price * 0.3)
        
        prices.append(current_price)
    
    # DataFrameを作成
    df = pd.DataFrame({
        'timestamp': dates,
        'price': prices
    })
    
    return df


def add_realistic_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    より現実的な特徴を追加（オプション）
    - 価格の急激な変動（イベント）
    - 周期的なパターン
    """
    prices = df['price'].values.copy()
    
    # ランダムなイベント（急激な価格変動）を追加
    num_events = len(prices) // 100  # 約1%の確率でイベント
    event_indices = np.random.choice(len(prices), num_events, replace=False)
    
    for idx in event_indices:
        # ±5%から±15%の変動
        change = np.random.choice([-1, 1]) * np.random.uniform(0.05, 0.15)
        prices[idx] *= (1 + change)
    
    df['price'] = prices
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Bitcoin price test data')
    parser.add_argument('--output', type=str, default='data/btc_prices.csv', help='Output CSV path')
    parser.add_argument('--start-date', type=str, default='2023-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=365, help='Number of days to generate')
    parser.add_argument('--initial-price', type=float, default=30000.0, help='Initial price in USD')
    parser.add_argument('--volatility', type=float, default=0.02, help='Daily volatility (std dev)')
    parser.add_argument('--trend', type=float, default=0.0001, help='Daily trend (growth rate)')
    parser.add_argument('--realistic', action='store_true', help='Add realistic features (events, patterns)')
    
    args = parser.parse_args()
    
    print(f"Generating Bitcoin price data...")
    print(f"  Start date: {args.start_date}")
    print(f"  Days: {args.days}")
    print(f"  Initial price: ${args.initial_price:,.2f}")
    print(f"  Volatility: {args.volatility*100:.2f}%")
    print(f"  Trend: {args.trend*100:.2f}% per day")
    
    # データ生成
    df = generate_bitcoin_price_data(
        start_date=args.start_date,
        days=args.days,
        initial_price=args.initial_price,
        volatility=args.volatility,
        trend=args.trend
    )
    
    # 現実的な特徴を追加（オプション）
    if args.realistic:
        print("Adding realistic features...")
        df = add_realistic_features(df)
    
    # 出力ディレクトリを作成
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # CSVに保存
    df.to_csv(args.output, index=False)
    
    print(f"\nData generated successfully!")
    print(f"  Output: {args.output}")
    print(f"  Total records: {len(df):,}")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  Price range: ${df['price'].min():,.2f} to ${df['price'].max():,.2f}")
    print(f"  Average price: ${df['price'].mean():,.2f}")

