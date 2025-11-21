#!/usr/bin/env python3
"""
トレーリングストップロス機能付きエージェントのグリッドサーチ
全額取引シミュレーターを使用
"""
import sys
import os
import csv
from datetime import datetime
import json
from typing import List, Dict, Tuple, Optional
import itertools

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.agents.ma_agent import MaAgent
from shared.agents.ma_agent_with_stoploss import MaAgentWithStopLoss
from shared.agents.ma_agent_with_trailing_stop import MaAgentWithTrailingStop
from shared.models.trading import PriceData, Action, TradingDecision, Order, OrderStatus
from simulation.engine.simulator import TradingSimulator


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
            order_amount_usd = self.balance / (1 + fee_rate)
            btc_amount = order_amount_usd / current_price
            fee = order_amount_usd * fee_rate
            
            # 残高とBTC保有量を更新
            self.balance = 0  # 全額使用
            self.btc_holdings += btc_amount
            
            # エントリー価格を更新（損失確定用）
            if self.entry_price is None:
                self.entry_price = current_price
            else:
                # 既存ポジションと新しいポジションの加重平均
                total_btc = self.btc_holdings
                old_btc = self.btc_holdings - btc_amount
                if total_btc > 0:
                    self.entry_price = (old_btc * self.entry_price + btc_amount * current_price) / total_btc
            
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
            
            # ポジションがなくなったらエントリー価格をリセット
            self.entry_price = None
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


def run_single_simulation(
    price_data: List[PriceData],
    agent_id: str,
    short_window: int,
    long_window: int,
    stop_loss_percentage: Optional[float],
    trailing_stop_percentage: Optional[float],
    initial_balance: float,
    lookback_window: int
) -> Dict:
    """
    単一のシミュレーションを実行
    
    Args:
        stop_loss_percentage: Noneの場合は損失確定なし
        trailing_stop_percentage: Noneの場合はトレーリングストップロスなし
    
    Returns:
        シミュレーション結果の辞書
    """
    # エージェント作成
    if trailing_stop_percentage is not None and stop_loss_percentage is not None:
        # トレーリングストップロス付きエージェント
        agent = MaAgentWithTrailingStop(
            agent_id=agent_id,
            short_window=short_window,
            long_window=long_window,
            stop_loss_percentage=stop_loss_percentage,
            trailing_stop_percentage=trailing_stop_percentage
        )
    elif stop_loss_percentage is not None:
        # 損失確定のみ
        agent = MaAgentWithStopLoss(
            agent_id=agent_id,
            short_window=short_window,
            long_window=long_window,
            stop_loss_percentage=stop_loss_percentage
        )
    else:
        # 損失確定なし
        agent = MaAgent(
            agent_id=agent_id,
            short_window=short_window,
            long_window=long_window
        )
    
    # 全額取引シミュレーター作成
    simulator = FullPositionSimulator(initial_balance=initial_balance)
    
    # シミュレーション実行
    result = simulator.run_simulation(
        agent,
        price_data,
        lookback_window=lookback_window,
        stop_loss_percentage=stop_loss_percentage
    )
    
    # トレーリングストップロス取引数をカウント
    trailing_stop_trades = len([d for d in result['decisions'] if 'Trailing Stop triggered' in d.get('reason', '')])
    result['trailing_stop_trades'] = trailing_stop_trades
    
    # パラメータを結果に追加
    result['short_window'] = short_window
    result['long_window'] = long_window
    result['stop_loss_percentage'] = stop_loss_percentage
    result['trailing_stop_percentage'] = trailing_stop_percentage
    result['lookback_window'] = lookback_window
    
    return result


def grid_search(
    csv_path: str,
    stop_loss_percentages: List[float],
    trailing_stop_percentages: List[float],
    short_windows: List[int],
    long_windows: List[int],
    initial_balance: float = 10000.0,
    min_ratio: float = 1.5
):
    """
    グリッドサーチを実行
    
    Args:
        csv_path: 価格データのCSVファイルパス
        stop_loss_percentages: テストする損失確定パーセンテージのリスト
        trailing_stop_percentages: テストするトレーリングストップロスパーセンテージのリスト
        short_windows: テストする短期移動平均のウィンドウサイズのリスト
        long_windows: テストする長期移動平均のウィンドウサイズのリスト
        initial_balance: 初期残高
        min_ratio: long_window / short_window の最小比率
    """
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    if len(price_data) < 1000:
        print(f"エラー: 価格データが不足しています")
        return None
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print()
    
    # 有効な組み合わせをフィルタリング
    valid_combinations = []
    for short, long_w in itertools.product(short_windows, long_windows):
        if short < long_w and long_w / short >= min_ratio:
            # lookback_windowはlong_windowより大きい必要がある
            min_lookback = max(long_w + 50, 60)
            if min_lookback + 100 < len(price_data):
                for stop_loss in stop_loss_percentages:
                    for trailing_stop in trailing_stop_percentages:
                        valid_combinations.append((short, long_w, stop_loss, trailing_stop, min_lookback))
    
    total_combinations = len(valid_combinations)
    print(f"テストする組み合わせ数: {total_combinations}")
    print(f"  損失確定パーセンテージ: {[f'{p*100:.0f}%' for p in stop_loss_percentages]}")
    print(f"  トレーリングストップロス: {[f'{p*100:.0f}%' for p in trailing_stop_percentages]}")
    print(f"  short_window範囲: {min(short_windows)} ~ {max(short_windows)}")
    print(f"  long_window範囲: {min(long_windows)} ~ {max(long_windows)}")
    print()
    
    results = []
    best_profit_pct = float('-inf')
    best_result = None
    
    for idx, (short, long_w, stop_loss, trailing_stop, lookback) in enumerate(valid_combinations, 1):
        agent_id = f"ma_trailing_s{short}_l{long_w}_sl{int(stop_loss*100)}pct_ts{int(trailing_stop*100)}pct"
        
        try:
            result = run_single_simulation(
                price_data=price_data,
                agent_id=agent_id,
                short_window=short,
                long_window=long_w,
                stop_loss_percentage=stop_loss,
                trailing_stop_percentage=trailing_stop,
                initial_balance=initial_balance,
                lookback_window=lookback
            )
            
            results.append(result)
            
            # 最良の結果を更新
            if result['profit_percentage'] > best_profit_pct:
                best_profit_pct = result['profit_percentage']
                best_result = result
            
            # 進捗表示（5%ごと）
            if idx % max(1, total_combinations // 20) == 0 or idx == total_combinations:
                progress = (idx / total_combinations) * 100
                print(f"進捗: {idx}/{total_combinations} ({progress:.1f}%) - "
                      f"現在の最良: {best_profit_pct:.2f}% "
                      f"(short={best_result['short_window']}, long={best_result['long_window']}, "
                      f"stop_loss={best_result['stop_loss_percentage']*100:.0f}%, "
                      f"trailing={best_result['trailing_stop_percentage']*100:.0f}%)")
        
        except Exception as e:
            print(f"エラー: short={short}, long={long_w}, stop_loss={stop_loss}, trailing={trailing_stop}: {e}")
            continue
    
    # 結果をソート（利益率で降順）
    results.sort(key=lambda x: x['profit_percentage'], reverse=True)
    
    # 結果を表示
    print("\n" + "=" * 120)
    print("探索結果サマリー")
    print("=" * 120)
    print(f"総テスト数: {len(results)}")
    print()
    
    # トップ20を表示
    print("トップ20の結果:")
    print("-" * 120)
    print(f"{'Rank':<5} {'Short':<6} {'Long':<6} {'Stop Loss':<10} {'Trailing':<9} {'Profit%':<12} {'Profit$':<12} {'Trades':<8} {'TS Trades':<10}")
    print("-" * 120)
    
    for rank, result in enumerate(results[:20], 1):
        stop_loss_str = f"{result['stop_loss_percentage']*100:.0f}%" if result['stop_loss_percentage'] is not None else "なし"
        trailing_str = f"{result['trailing_stop_percentage']*100:.0f}%" if result['trailing_stop_percentage'] is not None else "なし"
        print(f"{rank:<5} "
              f"{result['short_window']:<6} "
              f"{result['long_window']:<6} "
              f"{stop_loss_str:<10} "
              f"{trailing_str:<9} "
              f"{result['profit_percentage']:>10.2f}% "
              f"${result['total_profit']:>10,.2f} "
              f"{result['total_trades']:<8} "
              f"{result.get('trailing_stop_trades', 0):<10}")
    
    print()
    
    # 最良の結果の詳細
    if best_result:
        print("=" * 120)
        print("最良の結果（詳細）")
        print("=" * 120)
        print(f"短期移動平均: {best_result['short_window']}")
        print(f"長期移動平均: {best_result['long_window']}")
        stop_loss_str = f"{best_result['stop_loss_percentage']*100:.1f}%" if best_result['stop_loss_percentage'] is not None else "なし"
        trailing_str = f"{best_result['trailing_stop_percentage']*100:.1f}%" if best_result['trailing_stop_percentage'] is not None else "なし"
        print(f"損失確定: {stop_loss_str}")
        print(f"トレーリングストップロス: {trailing_str}")
        print(f"Lookbackウィンドウ: {best_result['lookback_window']}")
        print(f"利益率: {best_result['profit_percentage']:.2f}%")
        print(f"利益: ${best_result['total_profit']:,.2f}")
        print(f"最終価値: ${best_result['final_value']:,.2f}")
        print(f"総取引数: {best_result['total_trades']}")
        print(f"  買い注文: {best_result['buy_trades']}")
        print(f"  売り注文: {best_result['sell_trades']}")
        print(f"  損失確定取引: {best_result.get('stop_loss_trades', 0)}")
        print(f"  トレーリングストップロス取引: {best_result.get('trailing_stop_trades', 0)}")
        print()
        
        # 価格変動との比較
        initial_price = price_data[0].price
        final_price = price_data[-1].price
        price_change = ((final_price - initial_price) / initial_price) * 100
        print(f"期間中の価格変動: {price_change:.2f}%")
        print(f"相対パフォーマンス: {best_result['profit_percentage'] / price_change:.3f}")
        print()
    
    return results, best_result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="トレーリングストップロス機能付きエージェントのグリッドサーチ")
    parser.add_argument(
        "--csv",
        type=str,
        default="data/btc_prices_2021_2025.csv",
        help="価格データのCSVファイルパス"
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        nargs='+',
        default=[0.03, 0.05, 0.07, 0.10],
        help="テストする損失確定パーセンテージ（デフォルト: 0.03 0.05 0.07 0.10）"
    )
    parser.add_argument(
        "--trailing-stop",
        type=float,
        nargs='+',
        default=[0.03, 0.05, 0.07, 0.10],
        help="テストするトレーリングストップロスパーセンテージ（デフォルト: 0.03 0.05 0.07 0.10）"
    )
    parser.add_argument(
        "--short-window",
        type=int,
        nargs='+',
        default=[5, 10, 20, 100],
        help="テストする短期移動平均のウィンドウサイズ（デフォルト: 5 10 20 100）"
    )
    parser.add_argument(
        "--long-window",
        type=int,
        nargs='+',
        default=[200, 500, 1000, 5000],
        help="テストする長期移動平均のウィンドウサイズ（デフォルト: 200 500 1000 5000）"
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
    
    args = parser.parse_args()
    
    # CSVファイルのパスを確認
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(project_root, csv_path)
    
    if not os.path.exists(csv_path):
        print(f"エラー: CSVファイルが見つかりません: {csv_path}")
        sys.exit(1)
    
    # グリッドサーチ実行
    results, best_result = grid_search(
        csv_path=csv_path,
        stop_loss_percentages=args.stop_loss,
        trailing_stop_percentages=args.trailing_stop,
        short_windows=args.short_window,
        long_windows=args.long_window,
        initial_balance=args.initial_balance
    )
    
    # 結果をJSONファイルに保存（オプション）
    if args.output and results:
        output_path = args.output
        if not os.path.isabs(output_path):
            output_path = os.path.join(project_root, output_path)
        
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        output_data = {
            'all_results': results,
            'best_result': best_result,
            'summary': {
                'total_tests': len(results),
                'best_profit_percentage': best_result['profit_percentage'] if best_result else None,
                'best_short_window': best_result['short_window'] if best_result else None,
                'best_long_window': best_result['long_window'] if best_result else None,
                'best_stop_loss_percentage': best_result['stop_loss_percentage'] if best_result else None,
                'best_trailing_stop_percentage': best_result['trailing_stop_percentage'] if best_result else None,
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=json_serializer, ensure_ascii=False)
        
        print(f"結果を保存しました: {output_path}")

