#!/usr/bin/env python3
"""
SimpleAgentの最適な移動平均ウィンドウサイズを探索するスクリプト
様々なshort_windowとlong_windowの組み合わせをテストして最適なパラメータを見つける
"""
import sys
import os
import csv
from datetime import datetime
import json
from typing import List, Tuple, Dict, Optional
import itertools

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.agents.simple_agent import SimpleAgent
from shared.models.trading import PriceData, Action, TradingDecision, Order, OrderStatus
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


class FullPositionSimulator(TradingSimulator):
    """全額取引シミュレーター（買いは全残高、売りは全BTC保有量を使用）"""
    
    def execute_trade(self, decision: TradingDecision, current_price: float, fee_rate: float = 0.001) -> Optional[Order]:
        """取引をシミュレート（全額取引版）"""
        if decision.action == Action.HOLD:
            return None
        
        # 注文数量を計算（全額使用）
        if decision.action == Action.BUY:
            # 買い: 全残高を使用
            if self.balance <= 0:
                return None
            
            # 手数料を考慮して使用可能な最大額を計算
            # balance = order_amount_usd + fee = order_amount_usd * (1 + fee_rate)
            # order_amount_usd = balance / (1 + fee_rate)
            order_amount_usd = self.balance / (1 + fee_rate)
            btc_amount = order_amount_usd / current_price
            fee = order_amount_usd * fee_rate
            
            # 残高とBTC保有量を更新
            self.balance = 0  # 全額使用
            self.btc_holdings += btc_amount
            
        elif decision.action == Action.SELL:
            # 売り: 全BTC保有量を売却
            if self.btc_holdings <= 0:
                return None
            
            btc_amount = self.btc_holdings
            order_amount_usd = btc_amount * current_price
            fee = order_amount_usd * fee_rate
            
            # 残高とBTC保有量を更新
            self.btc_holdings = 0  # 全額売却
            self.balance += (order_amount_usd - fee)
        else:
            return None
        
        order = Order(
            order_id=f"sim_{datetime.utcnow().isoformat()}",
            agent_id=decision.agent_id,
            action=decision.action,
            amount=btc_amount,
            price=current_price,
            timestamp=decision.timestamp,
            status=OrderStatus.EXECUTED,
            trader_id="simulator",
            execution_price=current_price,
            execution_timestamp=decision.timestamp
        )
        
        self.trades.append(order)
        self.decisions.append(decision)
        
        return order


def run_single_simulation(
    price_data: List[PriceData],
    agent_id: str,
    short_window: int,
    long_window: int,
    initial_balance: float,
    lookback_window: int,
    use_full_position: bool = True
) -> Dict:
    """
    単一のシミュレーションを実行
    
    Args:
        use_full_position: Trueの場合、全額取引（買いは全残高、売りは全BTC保有量）を使用
    
    Returns:
        シミュレーション結果の辞書
    """
    # エージェント作成
    agent = SimpleAgent(
        agent_id=agent_id,
        short_window=short_window,
        long_window=long_window
    )
    
    # シミュレーター作成
    if use_full_position:
        simulator = FullPositionSimulator(initial_balance=initial_balance)
    else:
        simulator = TradingSimulator(initial_balance=initial_balance)
    
    # シミュレーション実行
    result = simulator.run_simulation(agent, price_data, lookback_window=lookback_window)
    
    # パラメータを結果に追加
    result['short_window'] = short_window
    result['long_window'] = long_window
    result['lookback_window'] = lookback_window
    result['trade_strategy'] = 'full_position' if use_full_position else 'partial_10pct'
    
    return result


def find_best_window_sizes(
    csv_path: str,
    short_window_range: Tuple[int, int] = (5, 200),
    long_window_range: Tuple[int, int] = (50, 5000),
    initial_balance: float = 10000.0,
    short_window_step: int = 5,
    long_window_step: int = 50,
    min_ratio: float = 1.5,  # long_window / short_window の最小比率
    use_full_position: bool = True
):
    """
    最適なウィンドウサイズを探索
    
    Args:
        csv_path: 価格データのCSVファイルパス
        short_window_range: (最小, 最大) のタプル
        long_window_range: (最小, 最大) のタプル
        initial_balance: 初期残高
        short_window_step: short_windowの増分
        long_window_step: long_windowの増分
        min_ratio: long_window / short_window の最小比率
    """
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    if len(price_data) < 1000:
        print(f"エラー: 価格データが不足しています（必要: 1000, 実際: {len(price_data)}）")
        return None
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print()
    
    # ウィンドウサイズの組み合わせを生成
    short_windows = list(range(short_window_range[0], short_window_range[1] + 1, short_window_step))
    long_windows = list(range(long_window_range[0], long_window_range[1] + 1, long_window_step))
    
    # 有効な組み合わせをフィルタリング
    valid_combinations = []
    for short, long_w in itertools.product(short_windows, long_windows):
        if short < long_w and long_w / short >= min_ratio:
            # lookback_windowはlong_windowより大きい必要がある
            # long_windowが大きい場合でも適切に動作するよう余裕を持たせる
            min_lookback = max(long_w + 50, 60)  # long_window + 50の余裕、最低60
            # データが十分にあることを確認（lookback + 100ポイント以上のデータが必要）
            if min_lookback + 100 < len(price_data):
                valid_combinations.append((short, long_w, min_lookback))
    
    total_combinations = len(valid_combinations)
    print(f"テストする組み合わせ数: {total_combinations}")
    print(f"  short_window範囲: {short_window_range[0]} ~ {short_window_range[1]} (step: {short_window_step})")
    print(f"  long_window範囲: {long_window_range[0]} ~ {long_window_range[1]} (step: {long_window_step})")
    print(f"  最小比率 (long/short): {min_ratio}")
    if use_full_position:
        print(f"  取引戦略: 全額取引（買いは全残高、売りは全BTC保有量）")
    else:
        print(f"  取引戦略: 部分取引（残高/BTC保有量の10%）")
    print()
    
    results = []
    best_profit_pct = float('-inf')
    best_result = None
    
    for idx, (short, long_w, lookback) in enumerate(valid_combinations, 1):
        agent_id = f"simple_agent_{short}_{long_w}"
        
        try:
            result = run_single_simulation(
                price_data=price_data,
                agent_id=agent_id,
                short_window=short,
                long_window=long_w,
                initial_balance=initial_balance,
                lookback_window=lookback,
                use_full_position=use_full_position
            )
            
            results.append(result)
            
            # 最良の結果を更新
            if result['profit_percentage'] > best_profit_pct:
                best_profit_pct = result['profit_percentage']
                best_result = result
            
            # 進捗表示（10%ごと）
            if idx % max(1, total_combinations // 10) == 0 or idx == total_combinations:
                progress = (idx / total_combinations) * 100
                print(f"進捗: {idx}/{total_combinations} ({progress:.1f}%) - "
                      f"現在の最良: {best_profit_pct:.2f}% "
                      f"(short={best_result['short_window']}, long={best_result['long_window']})")
        
        except Exception as e:
            print(f"エラー: short={short}, long={long_w}, lookback={lookback}: {e}")
            continue
    
    # 結果をソート（利益率で降順）
    results.sort(key=lambda x: x['profit_percentage'], reverse=True)
    
    # 結果を表示
    print("\n" + "="*80)
    print("探索結果サマリー")
    print("="*80)
    print(f"総テスト数: {len(results)}")
    print()
    
    # トップ10を表示
    print("トップ10の結果:")
    print("-" * 80)
    print(f"{'Rank':<5} {'Short':<8} {'Long':<8} {'Lookback':<10} {'Profit%':<12} {'Profit$':<12} {'Trades':<8}")
    print("-" * 80)
    
    for rank, result in enumerate(results[:10], 1):
        print(f"{rank:<5} "
              f"{result['short_window']:<8} "
              f"{result['long_window']:<8} "
              f"{result['lookback_window']:<10} "
              f"{result['profit_percentage']:>10.2f}% "
              f"${result['total_profit']:>10,.2f} "
              f"{result['total_trades']:<8}")
    
    print()
    
    # 最良の結果の詳細
    if best_result:
        print("="*80)
        print("最良の結果（詳細）")
        print("="*80)
        print(f"短期移動平均: {best_result['short_window']}")
        print(f"長期移動平均: {best_result['long_window']}")
        print(f"Lookbackウィンドウ: {best_result['lookback_window']}")
        print(f"利益率: {best_result['profit_percentage']:.2f}%")
        print(f"利益: ${best_result['total_profit']:,.2f}")
        print(f"最終価値: ${best_result['final_value']:,.2f}")
        print(f"総取引数: {best_result['total_trades']}")
        print(f"  買い注文: {best_result['buy_trades']}")
        print(f"  売り注文: {best_result['sell_trades']}")
        print()
        
        # 価格変動との比較
        initial_price = price_data[0].price
        final_price = price_data[-1].price
        price_change = ((final_price - initial_price) / initial_price) * 100
        print(f"期間中の価格変動: {price_change:.2f}%")
        print(f"  （${initial_price:.2f} → ${final_price:.2f}）")
        
        # 相対パフォーマンス
        relative_performance = best_result['profit_percentage'] / price_change if price_change != 0 else 0
        print(f"相対パフォーマンス（利益率/価格変動率）: {relative_performance:.3f}")
        print()
    
    return results, best_result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SimpleAgentの最適なウィンドウサイズを探索")
    parser.add_argument(
        "--csv",
        type=str,
        default="data/btc_prices.csv",
        help="価格データのCSVファイルパス"
    )
    parser.add_argument(
        "--short-min",
        type=int,
        default=5,
        help="short_windowの最小値（デフォルト: 5）"
    )
    parser.add_argument(
        "--short-max",
        type=int,
        default=200,
        help="short_windowの最大値（デフォルト: 200）"
    )
    parser.add_argument(
        "--short-step",
        type=int,
        default=5,
        help="short_windowの増分（デフォルト: 5）"
    )
    parser.add_argument(
        "--long-min",
        type=int,
        default=50,
        help="long_windowの最小値（デフォルト: 50）"
    )
    parser.add_argument(
        "--long-max",
        type=int,
        default=5000,
        help="long_windowの最大値（デフォルト: 5000）"
    )
    parser.add_argument(
        "--long-step",
        type=int,
        default=50,
        help="long_windowの増分（デフォルト: 50）"
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=1.5,
        help="long_window / short_window の最小比率（デフォルト: 1.5）"
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        default=10000.0,
        help="初期残高（デフォルト: 10000.0）"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="結果をJSONファイルに保存するパス（オプション）"
    )
    parser.add_argument(
        "--full-position",
        action="store_true",
        default=True,
        help="全額取引を使用（買いは全残高、売りは全BTC保有量、デフォルト: True）"
    )
    parser.add_argument(
        "--partial-position",
        action="store_false",
        dest="full_position",
        help="部分取引を使用（残高/BTC保有量の10%）"
    )
    
    args = parser.parse_args()
    
    # CSVファイルのパスを確認
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(project_root, csv_path)
    
    if not os.path.exists(csv_path):
        print(f"エラー: CSVファイルが見つかりません: {csv_path}")
        sys.exit(1)
    
    # 探索実行
    results, best_result = find_best_window_sizes(
        csv_path=csv_path,
        short_window_range=(args.short_min, args.short_max),
        long_window_range=(args.long_min, args.long_max),
        initial_balance=args.initial_balance,
        short_window_step=args.short_step,
        long_window_step=args.long_step,
        min_ratio=args.min_ratio,
        use_full_position=args.full_position
    )
    
    # 結果をJSONファイルに保存（オプション）
    if args.output and results:
        output_path = args.output
        if not os.path.isabs(output_path):
            output_path = os.path.join(project_root, output_path)
        
        # datetimeオブジェクトを文字列に変換
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        # 結果をJSONに変換して保存
        output_data = {
            'all_results': results,
            'best_result': best_result,
            'summary': {
                'total_tests': len(results),
                'best_profit_percentage': best_result['profit_percentage'] if best_result else None,
                'best_short_window': best_result['short_window'] if best_result else None,
                'best_long_window': best_result['long_window'] if best_result else None,
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=json_serializer, ensure_ascii=False)
        
        print(f"結果を保存しました: {output_path}")

