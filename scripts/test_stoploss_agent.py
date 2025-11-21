#!/usr/bin/env python3
"""
損失確定機能付きMaAgentのシミュレーションを実行するスクリプト
様々な損失確定パラメータをテストしてパフォーマンスを比較
"""
import sys
import os
import csv
from datetime import datetime
import json
from typing import List, Dict

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.agents.ma_agent import MaAgent
from shared.agents.ma_agent_with_stoploss import MaAgentWithStopLoss
from shared.models.trading import PriceData
from simulation.engine.simulator import TradingSimulator


def load_price_data_from_csv(csv_path: str) -> list[PriceData]:
    """CSVファイルから価格データを読み込む"""
    price_data = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp_str = row['timestamp'].strip()
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
            except ValueError:
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
            
            try:
                price = float(row['price'].strip())
            except (ValueError, KeyError):
                continue
            
            price_data.append(PriceData(
                timestamp=timestamp,
                price=price,
                volume=None,
                high=None,
                low=None
            ))
    
    return price_data


def run_simulation_with_stoploss(
    csv_path: str,
    agent_id: str,
    short_window: int,
    long_window: int,
    stop_loss_percentage: float,
    initial_balance: float = 10000.0,
    lookback_window: int = 60,
    use_full_position: bool = True
) -> Dict:
    """
    損失確定機能付きエージェントでシミュレーションを実行
    
    Args:
        csv_path: 価格データのCSVファイルパス
        agent_id: エージェントID
        short_window: 短期移動平均のウィンドウサイズ
        long_window: 長期移動平均のウィンドウサイズ
        stop_loss_percentage: 損失確定パーセンテージ（例: 0.07 = 7%）
        initial_balance: 初期残高
        lookback_window: エージェントが参照する過去データのウィンドウサイズ
        use_full_position: Trueの場合、全額取引を使用
    
    Returns:
        シミュレーション結果の辞書
    """
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    if len(price_data) < lookback_window + 10:
        print(f"エラー: 価格データが不足しています")
        return None
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print()
    
    # 損失確定機能付きエージェントを作成
    agent = MaAgentWithStopLoss(
        agent_id=agent_id,
        short_window=short_window,
        long_window=long_window,
        stop_loss_percentage=stop_loss_percentage
    )
    
    # シミュレーターを作成
    simulator = TradingSimulator(initial_balance=initial_balance)
    
    # シミュレーション実行（損失確定パラメータを渡す）
    result = simulator.run_simulation(
        agent,
        price_data,
        lookback_window=lookback_window,
        stop_loss_percentage=stop_loss_percentage
    )
    
    # パラメータを結果に追加
    result['short_window'] = short_window
    result['long_window'] = long_window
    result['stop_loss_percentage'] = stop_loss_percentage
    result['lookback_window'] = lookback_window
    result['trade_strategy'] = 'full_position' if use_full_position else 'partial_10pct'
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="損失確定機能付きMaAgentでシミュレーションを実行")
    parser.add_argument(
        "--csv",
        type=str,
        default="data/btc_prices_2021_2025.csv",
        help="価格データのCSVファイルパス"
    )
    parser.add_argument(
        "--agent-id",
        type=str,
        default="ma_agent_stoploss_test",
        help="エージェントID"
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
        default=1050,
        help="長期移動平均のウィンドウサイズ（デフォルト: 1050）"
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        default=0.07,
        help="損失確定パーセンテージ（デフォルト: 0.07 = 7%）"
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
        default=1100,
        help="Lookbackウィンドウサイズ（デフォルト: 1100）"
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
    print(f"損失確定機能付きMaAgentでシミュレーションを実行しています...")
    print(f"  短期移動平均: {args.short_window}")
    print(f"  長期移動平均: {args.long_window}")
    print(f"  損失確定パーセンテージ: {args.stop_loss * 100:.1f}%")
    print()
    
    result = run_simulation_with_stoploss(
        csv_path=csv_path,
        agent_id=args.agent_id,
        short_window=args.short_window,
        long_window=args.long_window,
        stop_loss_percentage=args.stop_loss,
        initial_balance=args.initial_balance,
        lookback_window=args.lookback_window
    )
    
    if result:
        # 結果を表示
        print("=" * 80)
        print("シミュレーション結果")
        print("=" * 80)
        print(f"初期残高: ${result['initial_balance']:,.2f}")
        print(f"最終価値: ${result['final_value']:,.2f}")
        print(f"利益: ${result['total_profit']:,.2f}")
        print(f"利益率: {result['profit_percentage']:.2f}%")
        print(f"総取引数: {result['total_trades']}")
        print(f"  買い注文: {result['buy_trades']}")
        print(f"  売り注文: {result['sell_trades']}")
        print(f"  損失確定取引: {result.get('stop_loss_trades', 0)}")
        print()
        
        # 価格変動との比較
        initial_price = price_data[0].price
        final_price = price_data[-1].price
        price_change = ((final_price - initial_price) / initial_price) * 100
        print(f"期間中の価格変動: {price_change:.2f}%")
        print(f"  相対パフォーマンス: {result['profit_percentage'] / price_change:.3f}")
        print()
        
        # 結果をJSONファイルに保存（オプション）
        if args.output:
            output_path = args.output
            if not os.path.isabs(output_path):
                output_path = os.path.join(project_root, output_path)
            
            def json_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, default=json_serializer, ensure_ascii=False)
            
            print(f"結果を保存しました: {output_path}")

