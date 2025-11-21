#!/usr/bin/env python3
"""
SimpleAgentを使ってシミュレーションを実行するスクリプト
"""
import sys
import os
import csv
from datetime import datetime
import json

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.agents.ma_agent import MaAgent
from shared.models.trading import PriceData
from simulation.engine.simulator import TradingSimulator


def load_price_data_from_csv(csv_path: str) -> list[PriceData]:
    """
    CSVファイルから価格データを読み込む
    
    Args:
        csv_path: CSVファイルのパス
        
    Returns:
        PriceDataのリスト
    """
    price_data = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # timestampをdatetimeに変換
            timestamp_str = row['timestamp'].strip()
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
            except ValueError:
                # フォーマットが異なる場合は別の方法を試す
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    print(f"警告: タイムスタンプの解析に失敗しました: {timestamp_str}")
                    continue
            
            # priceをfloatに変換
            try:
                price = float(row['price'].strip())
            except (ValueError, KeyError):
                print(f"警告: 価格の解析に失敗しました: {row.get('price', 'N/A')}")
                continue
            
            price_data.append(PriceData(
                timestamp=timestamp,
                price=price,
                volume=None,
                high=None,
                low=None
            ))
    
    return price_data


def run_simple_agent_simulation(
    csv_path: str,
    agent_id: str = "simple_agent_test",
    short_window: int = 5,
    long_window: int = 20,
    initial_balance: float = 10000.0,
    lookback_window: int = 60
):
    """
    SimpleAgentを使ってシミュレーションを実行
    
    Args:
        csv_path: 価格データのCSVファイルパス
        agent_id: エージェントID
        short_window: 短期移動平均のウィンドウサイズ
        long_window: 長期移動平均のウィンドウサイズ
        initial_balance: 初期残高
        lookback_window: エージェントが参照する過去データのウィンドウサイズ
    """
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    if len(price_data) < lookback_window + 10:
        print(f"エラー: 価格データが不足しています（必要: {lookback_window + 10}, 実際: {len(price_data)}）")
        return None
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print(f"初期価格: ${price_data[0].price:.2f}")
    print(f"最終価格: ${price_data[-1].price:.2f}")
    print()
    
    # MaAgentを作成
    print(f"MaAgentを作成しています...")
    print(f"  エージェントID: {agent_id}")
    print(f"  短期移動平均: {short_window}")
    print(f"  長期移動平均: {long_window}")
    print()
    
    agent = MaAgent(
        agent_id=agent_id,
        short_window=short_window,
        long_window=long_window
    )
    
    # シミュレーターを作成
    simulator = TradingSimulator(initial_balance=initial_balance)
    
    # シミュレーション実行
    print("シミュレーションを実行しています...")
    result = simulator.run_simulation(agent, price_data, lookback_window=lookback_window)
    
    # 結果を表示
    print("\n" + "="*60)
    print("シミュレーション結果")
    print("="*60)
    print(f"初期残高: ${result['initial_balance']:,.2f}")
    print(f"最終残高: ${result['final_balance']:,.2f}")
    print(f"最終BTC保有量: {result['final_btc']:.8f} BTC")
    print(f"最終価値: ${result['final_value']:,.2f}")
    print(f"利益: ${result['total_profit']:,.2f}")
    print(f"利益率: {result['profit_percentage']:.2f}%")
    print(f"総取引数: {result['total_trades']}")
    print(f"  買い注文: {result['buy_trades']}")
    print(f"  売り注文: {result['sell_trades']}")
    print()
    
    # 価格変動との比較
    initial_price = price_data[0].price
    final_price = price_data[-1].price
    price_change = ((final_price - initial_price) / initial_price) * 100
    print(f"期間中の価格変動: {price_change:.2f}%")
    print(f"  （${initial_price:.2f} → ${final_price:.2f}）")
    print()
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SimpleAgentでシミュレーションを実行")
    parser.add_argument(
        "--csv",
        type=str,
        default="data/btc_prices.csv",
        help="価格データのCSVファイルパス（デフォルト: data/btc_prices.csv）"
    )
    parser.add_argument(
        "--agent-id",
        type=str,
        default="simple_agent_test",
        help="エージェントID（デフォルト: simple_agent_test）"
    )
    parser.add_argument(
        "--short-window",
        type=int,
        default=5,
        help="短期移動平均のウィンドウサイズ（デフォルト: 5）"
    )
    parser.add_argument(
        "--long-window",
        type=int,
        default=20,
        help="長期移動平均のウィンドウサイズ（デフォルト: 20）"
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        default=10000.0,
        help="初期残高（デフォルト: 10000.0）"
    )
    parser.add_argument(
        "--lookback-window",
        type=int,
        default=60,
        help="エージェントが参照する過去データのウィンドウサイズ（デフォルト: 60）"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="結果をJSONファイルに保存するパス（オプション）"
    )
    
    args = parser.parse_args()
    
    # CSVファイルのパスを確認
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(project_root, csv_path)
    
    if not os.path.exists(csv_path):
        print(f"エラー: CSVファイルが見つかりません: {csv_path}")
        sys.exit(1)
    
    # シミュレーション実行
    result = run_simple_agent_simulation(
        csv_path=csv_path,
        agent_id=args.agent_id,
        short_window=args.short_window,
        long_window=args.long_window,
        initial_balance=args.initial_balance,
        lookback_window=args.lookback_window
    )
    
    # 結果をJSONファイルに保存（オプション）
    if args.output and result:
        output_path = args.output
        if not os.path.isabs(output_path):
            output_path = os.path.join(project_root, output_path)
        
        # datetimeオブジェクトを文字列に変換
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        # 結果をJSONに変換して保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=json_serializer, ensure_ascii=False)
        
        print(f"結果を保存しました: {output_path}")



