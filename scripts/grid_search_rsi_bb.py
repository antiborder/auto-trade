#!/usr/bin/env python3
"""
RSI+ボリンジャーバンドエージェントのグリッドサーチ
全額取引シミュレーターを使用
"""
import sys
import os
import csv
from datetime import datetime, timezone
import json
from typing import List, Dict, Tuple, Optional
import itertools
import time

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.agents.rsi_bb_agent import RSIBBAgent
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
            
            order_amount_usd = self.balance / (1 + fee_rate)
            btc_amount = order_amount_usd / current_price
            fee = order_amount_usd * fee_rate
            
            self.balance = 0
            self.btc_holdings += btc_amount
            
            # エントリー価格を更新（損失確定用）
            if self.entry_price is None:
                self.entry_price = current_price
            else:
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
            
            self.btc_holdings = 0
            self.balance += (order_amount_usd - fee)
            self.entry_price = None
        else:
            return None
        
        order = Order(
            order_id=f"sim_{datetime.now(timezone.utc).isoformat()}",
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
    rsi_period: int,
    rsi_oversold: float,
    rsi_overbought: float,
    bb_period: int,
    bb_num_std_dev: float,
    initial_balance: float,
    lookback_window: int
) -> Dict:
    """
    単一のシミュレーションを実行
    
    Returns:
        シミュレーション結果の辞書
    """
    # エージェント作成
    agent = RSIBBAgent(
        agent_id=agent_id,
        rsi_period=rsi_period,
        rsi_oversold=rsi_oversold,
        rsi_overbought=rsi_overbought,
        bb_period=bb_period,
        bb_num_std_dev=bb_num_std_dev
    )
    
    # 全額取引シミュレーター作成
    simulator = FullPositionSimulator(initial_balance=initial_balance)
    
    # シミュレーション実行
    result = simulator.run_simulation(
        agent,
        price_data,
        lookback_window=lookback_window
    )
    
    # パラメータを結果に追加
    result['rsi_period'] = rsi_period
    result['rsi_oversold'] = rsi_oversold
    result['rsi_overbought'] = rsi_overbought
    result['bb_period'] = bb_period
    result['bb_num_std_dev'] = bb_num_std_dev
    result['lookback_window'] = lookback_window
    
    return result


def grid_search(
    csv_path: str,
    rsi_periods: List[int],
    rsi_oversold_levels: List[float],
    rsi_overbought_levels: List[float],
    bb_periods: List[int],
    bb_num_std_devs: List[float],
    initial_balance: float = 10000.0,
    min_lookback: int = 100,
    log_file: Optional[str] = None
):
    """
    グリッドサーチを実行
    
    Args:
        csv_path: 価格データのCSVファイルパス
        rsi_periods: テストするRSI期間のリスト
        rsi_oversold_levels: テストするRSIオーバーソールド閾値のリスト
        rsi_overbought_levels: テストするRSIオーバーボート閾値のリスト
        bb_periods: テストするボリンジャーバンド期間のリスト
        bb_num_std_devs: テストするボリンジャーバンド標準偏差倍数のリスト
        initial_balance: 初期残高
        min_lookback: 最小lookbackウィンドウサイズ
        log_file: ログファイルのパス
    """
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    if len(price_data) < min_lookback + 100:
        print(f"エラー: 価格データが不足しています")
        return None
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print()
    
    # すべての組み合わせを生成
    valid_combinations = []
    for (rsi_p, rsi_os, rsi_ob, bb_p, bb_std) in itertools.product(
        rsi_periods,
        rsi_oversold_levels,
        rsi_overbought_levels,
        bb_periods,
        bb_num_std_devs
    ):
        # lookback_windowは最大期間の合計以上が必要
        min_lookback_required = max(rsi_p + 1, bb_p, min_lookback)
        if min_lookback_required + 100 < len(price_data):
            valid_combinations.append((rsi_p, rsi_os, rsi_ob, bb_p, bb_std, min_lookback_required))
    
    total_combinations = len(valid_combinations)
    print(f"テストする組み合わせ数: {total_combinations}")
    print(f"  RSI期間: {rsi_periods}")
    print(f"  RSIオーバーソールド: {rsi_oversold_levels}")
    print(f"  RSIオーバーボート: {rsi_overbought_levels}")
    print(f"  ボリンジャーバンド期間: {bb_periods}")
    print(f"  ボリンジャーバンド標準偏差倍数: {bb_num_std_devs}")
    print()
    
    results = []
    best_profit_pct = float('-inf')
    best_result = None
    
    # ログファイルの設定
    log_path = None
    if log_file:
        log_path = log_file if os.path.isabs(log_file) else os.path.join(project_root, log_file)
        # ログファイルのディレクトリを作成
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    # 開始時間と最後のログ時間を記録
    start_time = time.time()
    last_log_time = start_time
    log_interval = 300  # 5分 = 300秒
    
    def write_log(message: str):
        """ログをファイルとコンソールに書き込む"""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        if log_path:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
    
    # 初期ログ
    if log_path:
        write_log(f"Grid search started")
        write_log(f"Total combinations to test: {total_combinations}")
        write_log(f"RSI periods: {rsi_periods}")
        write_log(f"RSI oversold levels: {rsi_oversold_levels}")
        write_log(f"RSI overbought levels: {rsi_overbought_levels}")
        write_log(f"BB Periods: {bb_periods}")
        write_log(f"BB Std Devs: {bb_num_std_devs}")
        write_log(f"Data points: {len(price_data)}")
        write_log(f"Log file: {log_path}")
        write_log("-" * 80)
    
    for idx, (rsi_p, rsi_os, rsi_ob, bb_p, bb_std, lookback) in enumerate(valid_combinations, 1):
        agent_id = f"rsi_bb_r{rsi_p}_os{rsi_os:.0f}_ob{rsi_ob:.0f}_bbp{bb_p}_bbstd{bb_std}"
        
        try:
            result = run_single_simulation(
                price_data=price_data,
                agent_id=agent_id,
                rsi_period=rsi_p,
                rsi_oversold=rsi_os,
                rsi_overbought=rsi_ob,
                bb_period=bb_p,
                bb_num_std_dev=bb_std,
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
                if best_result:
                    print(f"進捗: {idx}/{total_combinations} ({progress:.1f}%) - "
                          f"現在の最良: {best_profit_pct:.2f}% "
                          f"(RSI={best_result['rsi_period']}/{best_result['rsi_oversold']:.0f}-{best_result['rsi_overbought']:.0f}, "
                          f"BB={best_result['bb_period']}/{best_result['bb_num_std_dev']})")
                else:
                    print(f"進捗: {idx}/{total_combinations} ({progress:.1f}%) - まだ結果なし")
            
            # 5分ごとのログ出力
            current_time = time.time()
            if current_time - last_log_time >= log_interval:
                elapsed_time = current_time - start_time
                progress_pct = (idx / total_combinations) * 100
                
                # 残り時間の推定
                if idx > 0:
                    avg_time_per_combination = elapsed_time / idx
                    remaining_combinations = total_combinations - idx
                    estimated_remaining = avg_time_per_combination * remaining_combinations
                    estimated_remaining_str = f"{int(estimated_remaining // 3600)}h {int((estimated_remaining % 3600) // 60)}m"
                else:
                    estimated_remaining_str = "N/A"
                
                elapsed_str = f"{int(elapsed_time // 3600)}h {int((elapsed_time % 3600) // 60)}m {int(elapsed_time % 60)}s"
                
                # 最良の結果の情報を構築
                if best_result:
                    best_params_str = (
                        f"RSI({best_result['rsi_period']}/{best_result['rsi_oversold']:.0f}-{best_result['rsi_overbought']:.0f}), "
                        f"BB({best_result['bb_period']}/{best_result['bb_num_std_dev']})"
                    )
                else:
                    best_params_str = "None yet"
                
                log_msg = (
                    f"Progress: {idx}/{total_combinations} ({progress_pct:.2f}%) | "
                    f"Elapsed: {elapsed_str} | "
                    f"Estimated remaining: {estimated_remaining_str} | "
                    f"Best profit: {best_profit_pct:.2f}% | "
                    f"Best params: {best_params_str} | "
                    f"Completed: {len(results)} simulations"
                )
                write_log(log_msg)
                last_log_time = current_time
        
        except Exception as e:
            error_msg = f"エラー: RSI={rsi_p}/{rsi_os}-{rsi_ob}, BB={bb_p}/{bb_std}: {e}"
            print(error_msg)
            if log_path:
                write_log(error_msg)
            continue
    
    # 結果をソート（利益率で降順）
    results.sort(key=lambda x: x['profit_percentage'], reverse=True)
    
    # 結果を表示
    print("\n" + "=" * 140)
    print("探索結果サマリー")
    print("=" * 140)
    print(f"総テスト数: {len(results)}")
    print()
    
    # トップ20を表示
    print("トップ20の結果:")
    print("-" * 140)
    header = f"{'Rank':<5} {'RSI':<8} {'RSI OS':<7} {'RSI OB':<7} {'BB P':<6} {'BB Std':<7} {'Profit%':<12} {'Profit$':<12} {'Trades':<8}"
    print(header)
    print("-" * 140)
    
    for rank, result in enumerate(results[:20], 1):
        print(f"{rank:<5} "
              f"{result['rsi_period']:<8} "
              f"{result['rsi_oversold']:<7.0f} "
              f"{result['rsi_overbought']:<7.0f} "
              f"{result['bb_period']:<6} "
              f"{result['bb_num_std_dev']:<7.1f} "
              f"{result['profit_percentage']:>10.2f}% "
              f"${result['total_profit']:>10,.2f} "
              f"{result['total_trades']:<8}")
    
    print()
    
    # 最良の結果の詳細
    if best_result:
        print("=" * 140)
        print("最良の結果（詳細）")
        print("=" * 140)
        print(f"RSI期間: {best_result['rsi_period']}")
        print(f"RSIオーバーソールド: {best_result['rsi_oversold']}")
        print(f"RSIオーバーボート: {best_result['rsi_overbought']}")
        print(f"ボリンジャーバンド期間: {best_result['bb_period']}")
        print(f"ボリンジャーバンド標準偏差倍数: {best_result['bb_num_std_dev']}")
        print(f"Lookbackウィンドウ: {best_result['lookback_window']}")
        print()
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
        if price_change != 0:
            print(f"相対パフォーマンス: {best_result['profit_percentage'] / price_change:.3f}")
        print()
    
    # 完了ログ
    if log_path:
        total_elapsed = time.time() - start_time
        elapsed_str = f"{int(total_elapsed // 3600)}h {int((total_elapsed % 3600) // 60)}m {int(total_elapsed % 60)}s"
        write_log("-" * 80)
        write_log(f"Grid search completed in {elapsed_str}")
        write_log(f"Total combinations tested: {len(results)}")
        if best_result:
            write_log(f"Best profit: {best_result['profit_percentage']:.2f}%")
            write_log(f"Best parameters: RSI({best_result['rsi_period']}/{best_result['rsi_oversold']:.0f}-{best_result['rsi_overbought']:.0f}), BB({best_result['bb_period']}/{best_result['bb_num_std_dev']})")
    
    return results, best_result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RSI+ボリンジャーバンドエージェントのグリッドサーチ")
    parser.add_argument("--csv", type=str, default="data/btc_prices_2021_2025.csv")
    parser.add_argument("--rsi-period", type=int, nargs='+', default=[10, 14, 18, 22, 26], help="RSI期間")
    parser.add_argument("--rsi-oversold", type=float, nargs='+', default=[20, 25, 30, 35, 40], help="RSIオーバーソールド閾値")
    parser.add_argument("--rsi-overbought", type=float, nargs='+', default=[60, 65, 70, 75, 80], help="RSIオーバーボート閾値")
    parser.add_argument("--bb-period", type=int, nargs='+', default=[15, 18, 20, 22, 25], help="ボリンジャーバンド期間")
    parser.add_argument("--bb-std-dev", type=float, nargs='+', default=[1.5, 2.0, 2.5, 3.0], help="ボリンジャーバンド標準偏差倍数")
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--output", type=str, help="結果をJSONファイルに保存するパス")
    parser.add_argument("--log", type=str, help="進捗ログを保存するファイルパス（5分ごとに更新）")
    
    args = parser.parse_args()
    
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(project_root, csv_path)
    
    if not os.path.exists(csv_path):
        print(f"エラー: CSVファイルが見つかりません: {csv_path}")
        sys.exit(1)
    
    # ログファイルパスの設定
    log_file = args.log
    if log_file and not os.path.isabs(log_file):
        log_file = os.path.join(project_root, log_file)
    
    # グリッドサーチ実行
    results, best_result = grid_search(
        csv_path=csv_path,
        rsi_periods=args.rsi_period,
        rsi_oversold_levels=args.rsi_oversold,
        rsi_overbought_levels=args.rsi_overbought,
        bb_periods=args.bb_period,
        bb_num_std_devs=args.bb_std_dev,
        initial_balance=args.initial_balance,
        log_file=log_file
    )
    
    # 結果をJSONファイルに保存
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
                'best_rsi_period': best_result['rsi_period'] if best_result else None,
                'best_rsi_oversold': best_result['rsi_oversold'] if best_result else None,
                'best_rsi_overbought': best_result['rsi_overbought'] if best_result else None,
                'best_bb_period': best_result['bb_period'] if best_result else None,
                'best_bb_num_std_dev': best_result['bb_num_std_dev'] if best_result else None,
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=json_serializer, ensure_ascii=False)
        
        print(f"結果を保存しました: {output_path}")

