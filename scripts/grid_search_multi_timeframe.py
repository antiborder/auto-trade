#!/usr/bin/env python3
"""
マルチタイムフレームエージェントのグリッドサーチ
15分足データからRSIとBBを計算、1時間足データからMACDを計算
"""
import sys
import os
import csv
import time
import json
import itertools
from datetime import datetime, timezone
from typing import List, Dict, Optional

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.models.trading import PriceData, Action
from simulation.engine.multi_timeframe_simulator import (
    align_timeframes,
    MultiTimeframeSimulator
)


def load_price_data_from_csv(csv_path: str) -> List[PriceData]:
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
    simulator: MultiTimeframeSimulator,
    agent_id: str,
    # 15分足用パラメータ
    rsi_period: int,
    rsi_oversold: float,
    rsi_overbought: float,
    bb_period: int,
    bb_num_std_dev: float,
    # 1時間足用パラメータ
    macd_fast: int,
    macd_slow: int,
    macd_signal: int
) -> Dict:
    """
    単一のシミュレーションを実行
    
    Args:
        simulator: MultiTimeframeSimulatorインスタンス（整列済みデータを含む）
        agent_id: エージェントID
        その他のパラメータ: エージェントのパラメータ
    
    Returns:
        シミュレーション結果の辞書
    """
    result = simulator.run_simulation(
        agent_id=agent_id,
        rsi_period=rsi_period,
        rsi_oversold=rsi_oversold,
        rsi_overbought=rsi_overbought,
        bb_period=bb_period,
        bb_num_std_dev=bb_num_std_dev,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal
    )
    
    # グリッドサーチ用に追加のフィールドを追加
    result['rsi_period'] = rsi_period
    result['rsi_oversold'] = rsi_oversold
    result['rsi_overbought'] = rsi_overbought
    result['bb_period'] = bb_period
    result['bb_num_std_dev'] = bb_num_std_dev
    result['macd_fast'] = macd_fast
    result['macd_slow'] = macd_slow
    result['macd_signal'] = macd_signal
    
    return result


def grid_search(
    csv_15m_path: str,
    csv_1h_path: str,
    rsi_periods: List[int],
    rsi_oversold_levels: List[float],
    rsi_overbought_levels: List[float],
    bb_periods: List[int],
    bb_num_std_devs: List[float],
    macd_fast_periods: List[int],
    macd_slow_periods: List[int],
    macd_signal_periods: List[int],
    initial_balance: float = 10000.0,
    lookback_window_15m: int = 100,
    lookback_window_1h: int = 50,
    log_file: Optional[str] = None,
    output_file: Optional[str] = None
):
    """
    グリッドサーチを実行
    
    Args:
        csv_15m_path: 15分足データのCSVファイルパス
        csv_1h_path: 1時間足データのCSVファイルパス
        rsi_periods: テストするRSI期間のリスト（15分足用）
        rsi_oversold_levels: テストするRSIオーバーソールド閾値のリスト（15分足用）
        rsi_overbought_levels: テストするRSIオーバーボート閾値のリスト（15分足用）
        bb_periods: テストするボリンジャーバンド期間のリスト（15分足用）
        bb_num_std_devs: テストするボリンジャーバンド標準偏差倍数のリスト（15分足用）
        macd_fast_periods: テストするMACD短期EMA期間のリスト（1時間足用）
        macd_slow_periods: テストするMACD長期EMA期間のリスト（1時間足用）
        macd_signal_periods: テストするMACDシグナルライン期間のリスト（1時間足用）
        initial_balance: 初期残高
        lookback_window_15m: 15分足データのlookbackウィンドウサイズ
        lookback_window_1h: 1時間足データのlookbackウィンドウサイズ
        log_file: ログファイルのパス
        output_file: 出力JSONファイルのパス
    """
    print(f"Loading 15-minute data: {csv_15m_path}")
    data_15m = load_price_data_from_csv(csv_15m_path)
    print(f"Loaded {len(data_15m)} 15-minute data points")
    
    print(f"Loading 1-hour data: {csv_1h_path}")
    data_1h = load_price_data_from_csv(csv_1h_path)
    print(f"Loaded {len(data_1h)} 1-hour data points")
    
    # データ整列（一度だけ実行）
    print("Aligning timeframes...")
    start_align = time.time()
    aligned_data, data_1h_sorted = align_timeframes(data_15m, data_1h)
    align_time = time.time() - start_align
    print(f"Data alignment completed: {len(aligned_data)} aligned points in {align_time:.2f}s")
    
    if len(aligned_data) < lookback_window_15m + 100:
        print(f"Error: Insufficient aligned data")
        return None
    
    # シミュレーターインスタンスを作成（一度だけ、全パターンで再利用）
    try:
        simulator = MultiTimeframeSimulator(
            aligned_data=aligned_data,
            data_1h_sorted=data_1h_sorted,
            initial_balance=initial_balance,
            lookback_window_15m=lookback_window_15m,
            lookback_window_1h=lookback_window_1h
        )
    except ValueError as e:
        print(f"Error creating simulator: {e}")
        return None
    
    # 有効な組み合わせを生成
    valid_combinations = []
    for (rsi_p, rsi_os, rsi_ob, bb_p, bb_std, macd_f, macd_s, macd_sig) in itertools.product(
        rsi_periods,
        rsi_oversold_levels,
        rsi_overbought_levels,
        bb_periods,
        bb_num_std_devs,
        macd_fast_periods,
        macd_slow_periods,
        macd_signal_periods
    ):
        # MACDの期間の妥当性チェック
        if macd_f >= macd_s:
            continue
        
        # lookback_windowは最大期間の合計以上が必要
        min_lookback_required_15m = max(rsi_p + 1, bb_p, lookback_window_15m)
        min_lookback_required_1h = max(macd_s + macd_sig, lookback_window_1h)
        
        if min_lookback_required_15m + 100 < len(aligned_data):
            valid_combinations.append((rsi_p, rsi_os, rsi_ob, bb_p, bb_std, macd_f, macd_s, macd_sig))
    
    total_combinations = len(valid_combinations)
    print(f"\nTotal combinations to test: {total_combinations}")
    print(f"  15m - RSI periods: {rsi_periods}")
    print(f"  15m - RSI oversold: {rsi_oversold_levels}")
    print(f"  15m - RSI overbought: {rsi_overbought_levels}")
    print(f"  15m - BB periods: {bb_periods}")
    print(f"  15m - BB std devs: {bb_num_std_devs}")
    print(f"  1h - MACD fast: {macd_fast_periods}")
    print(f"  1h - MACD slow: {macd_slow_periods}")
    print(f"  1h - MACD signal: {macd_signal_periods}")
    print()
    
    # ログファイルの設定
    log_path = None
    if log_file:
        log_path = log_file if os.path.isabs(log_file) else os.path.join(project_root, log_file)
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    # 開始時間を記録
    start_time = time.time()
    
    def write_log(message: str):
        """ログをファイルとコンソールに書き込む"""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        sys.stdout.flush()
        if log_path:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
    
    # 初期ログ
    if log_path:
        write_log("Multi-timeframe grid search started")
        write_log(f"15-minute data: {csv_15m_path} ({len(data_15m)} records)")
        write_log(f"1-hour data: {csv_1h_path} ({len(data_1h)} records)")
        write_log(f"Data alignment completed in {align_time:.2f}s")
        write_log(f"Total combinations: {total_combinations}")
        write_log("-" * 80)
    
    results = []
    best_profit_pct = float('-inf')
    best_result = None
    
    for idx, (rsi_p, rsi_os, rsi_ob, bb_p, bb_std, macd_f, macd_s, macd_sig) in enumerate(valid_combinations, 1):
        agent_id = f"multi_tf_{rsi_p}_{rsi_os}_{rsi_ob}_{bb_p}_{bb_std}_{macd_f}_{macd_s}_{macd_sig}"
        
        try:
            result = run_single_simulation(
                simulator=simulator,
                agent_id=agent_id,
                rsi_period=rsi_p,
                rsi_oversold=rsi_os,
                rsi_overbought=rsi_ob,
                bb_period=bb_p,
                bb_num_std_dev=bb_std,
                macd_fast=macd_f,
                macd_slow=macd_s,
                macd_signal=macd_sig
            )
            
            if 'error' in result:
                continue
            
            results.append(result)
            
            # 最良の結果を更新
            if result['profit_percentage'] > best_profit_pct:
                best_profit_pct = result['profit_percentage']
                best_result = result
            
            # 各シミュレーション後にログ出力
            progress = (idx / total_combinations) * 100
            elapsed_time = time.time() - start_time
            estimated_total_time = (elapsed_time / idx) * total_combinations if idx > 0 else 0
            remaining_time = estimated_total_time - elapsed_time
            
            elapsed_h, elapsed_m, elapsed_s = int(elapsed_time // 3600), int((elapsed_time % 3600) // 60), int(elapsed_time % 60)
            remaining_h, remaining_m, remaining_s = int(remaining_time // 3600), int((remaining_time % 3600) // 60), int(remaining_time % 60)
            
            best_params_str = ""
            if best_result:
                best_params_str = (f"RSI({best_result['rsi_period']}/{best_result['rsi_oversold']:.0f}-{best_result['rsi_overbought']:.0f}) "
                                 f"BB({best_result['bb_period']}/{best_result['bb_num_std_dev']}) "
                                 f"MACD({best_result['macd_fast']}/{best_result['macd_slow']}/{best_result['macd_signal']})")
            
            log_message = (f"Progress: {idx}/{total_combinations} ({progress:.1f}%) | "
                          f"Elapsed: {elapsed_h}h {elapsed_m}m {elapsed_s}s | "
                          f"Estimated remaining: {remaining_h}h {remaining_m}m | "
                          f"Current profit: {result['profit_percentage']:.2f}% | "
                          f"Best profit: {best_profit_pct:.2f}% | "
                          f"Best params: {best_params_str}")
            write_log(log_message)
        
        except Exception as e:
            print(f"Error with RSI({rsi_p}/{rsi_os}-{rsi_ob}) BB({bb_p}/{bb_std}) MACD({macd_f}/{macd_s}/{macd_sig}): {e}")
            continue
    
    # 結果をソート（利益率で降順）
    results.sort(key=lambda x: x['profit_percentage'], reverse=True)
    
    # 結果を表示
    print("\n" + "=" * 80)
    print("Grid Search Results Summary")
    print("=" * 80)
    print(f"Total combinations tested: {len(results)}")
    print()
    
    if best_result:
        print("Best Result:")
        print(f"  Profit: {best_result['profit_percentage']:.2f}%")
        print(f"  Total Profit: ${best_result['total_profit']:,.2f}")
        print(f"  Final Value: ${best_result['final_value']:,.2f}")
        print(f"  Total Trades: {best_result['total_trades']} ({best_result['buy_trades']} buys, {best_result['sell_trades']} sells)")
        print()
        print("  Best Parameters:")
        print(f"    15m - RSI: Period={best_result['rsi_period']}, Oversold={best_result['rsi_oversold']}, Overbought={best_result['rsi_overbought']}")
        print(f"    15m - BB: Period={best_result['bb_period']}, Std Dev={best_result['bb_num_std_dev']}")
        print(f"    1h - MACD: Fast={best_result['macd_fast']}, Slow={best_result['macd_slow']}, Signal={best_result['macd_signal']}")
    
    print("=" * 80)
    
    # 結果をJSONファイルに保存
    if output_file:
        output_path = output_file if os.path.isabs(output_file) else os.path.join(project_root, output_file)
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        output_data = {
            'total_combinations': total_combinations,
            'best_result': best_result,
            'top_10_results': results[:10],
            'all_results': results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {output_path}")
    
    total_time = time.time() - start_time
    write_log(f"Grid search completed in {total_time:.2f}s")
    write_log(f"Total combinations tested: {len(results)}")
    if best_result:
        write_log(f"Best profit: {best_result['profit_percentage']:.2f}%")
        write_log(f"Best parameters: RSI({best_result['rsi_period']}/{best_result['rsi_oversold']:.0f}-{best_result['rsi_overbought']:.0f}) "
                 f"BB({best_result['bb_period']}/{best_result['bb_num_std_dev']}) "
                 f"MACD({best_result['macd_fast']}/{best_result['macd_slow']}/{best_result['macd_signal']})")
    
    return {
        'total_combinations': total_combinations,
        'best_result': best_result,
        'results': results
    }


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-timeframe agent grid search')
    parser.add_argument('--csv-15m', required=True, help='Path to 15-minute k-line CSV file')
    parser.add_argument('--csv-1h', required=True, help='Path to 1-hour k-line CSV file')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--log', type=str, default=None, help='Log file path (optional)')
    
    # 15分足用パラメータ
    parser.add_argument('--rsi-period', type=int, nargs='+', required=True, help='RSI periods (15m)')
    parser.add_argument('--rsi-oversold', type=float, nargs='+', required=True, help='RSI oversold levels (15m)')
    parser.add_argument('--rsi-overbought', type=float, nargs='+', required=True, help='RSI overbought levels (15m)')
    parser.add_argument('--bb-period', type=int, nargs='+', required=True, help='Bollinger Bands periods (15m)')
    parser.add_argument('--bb-std-dev', type=float, nargs='+', required=True, help='Bollinger Bands std devs (15m)')
    
    # 1時間足用パラメータ
    parser.add_argument('--macd-fast', type=int, nargs='+', required=True, help='MACD fast periods (1h)')
    parser.add_argument('--macd-slow', type=int, nargs='+', required=True, help='MACD slow periods (1h)')
    parser.add_argument('--macd-signal', type=int, nargs='+', required=True, help='MACD signal periods (1h)')
    
    parser.add_argument('--initial-balance', type=float, default=10000.0, help='Initial balance')
    parser.add_argument('--lookback-15m', type=int, default=100, help='Lookback window for 15m data')
    parser.add_argument('--lookback-1h', type=int, default=50, help='Lookback window for 1h data')
    
    args = parser.parse_args()
    
    grid_search(
        csv_15m_path=args.csv_15m,
        csv_1h_path=args.csv_1h,
        rsi_periods=args.rsi_period,
        rsi_oversold_levels=args.rsi_oversold,
        rsi_overbought_levels=args.rsi_overbought,
        bb_periods=args.bb_period,
        bb_num_std_devs=args.bb_std_dev,
        macd_fast_periods=args.macd_fast,
        macd_slow_periods=args.macd_slow,
        macd_signal_periods=args.macd_signal,
        initial_balance=args.initial_balance,
        lookback_window_15m=args.lookback_15m,
        lookback_window_1h=args.lookback_1h,
        log_file=args.log,
        output_file=args.output
    )
