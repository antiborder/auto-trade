#!/usr/bin/env python3
"""
マルチタイムフレームエージェントのシミュレーション
15分足データからRSIとBBを計算、1時間足データからMACDを計算
"""
import sys
import os
import csv
import argparse
import time
import bisect
from datetime import datetime, timezone
from typing import List, Dict, Optional

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.agents.multi_timeframe_agent import MultiTimeframeAgent
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


def align_timeframes(
    data_15m: List[PriceData],
    data_1h: List[PriceData],
    progress_callback=None
) -> List[tuple]:
    """
    15分足データと1時間足データを時系列で整列（最適化版）
    各15分足データポイントに対して、対応する1時間足データの履歴を返す
    
    Args:
        data_15m: 15分足データ
        data_1h: 1時間足データ
        progress_callback: 進捗コールバック関数（オプション）
    
    Returns:
        List of tuples: (15m_price_data, 1h_index) where 1h_index is the index in sorted 1h data
    """
    aligned_data = []
    
    # 1時間足データを時系列でソート（一度だけ）
    data_1h_sorted = sorted(data_1h, key=lambda x: x.timestamp)
    timestamps_1h = [d.timestamp for d in data_1h_sorted]
    
    # 15分足データを時系列でソート
    data_15m_sorted = sorted(data_15m, key=lambda x: x.timestamp)
    
    total = len(data_15m_sorted)
    last_progress = 0
    
    for i, price_15m in enumerate(data_15m_sorted):
        # バイナリサーチで現在の15分足タイムスタンプ以前の1時間足データのインデックスを取得
        # bisect_rightは、指定された値以下の最大のインデックス+1を返す
        idx = bisect.bisect_right(timestamps_1h, price_15m.timestamp)
        
        if idx > 0:
            # インデックスを保存（後で効率的にアクセスするため）
            aligned_data.append((price_15m, idx))
        
        # 進捗表示（10%ごと）
        if progress_callback and i > 0 and (i * 100 // total) > last_progress:
            last_progress = i * 100 // total
            progress_callback(i, total, last_progress)
    
    return aligned_data, data_1h_sorted


def run_simulation(
    data_15m: List[PriceData],
    data_1h: List[PriceData],
    agent_id: str,
    # 15分足用パラメータ
    rsi_period: int = 10,
    rsi_oversold: float = 35.0,
    rsi_overbought: float = 80.0,
    bb_period: int = 22,
    bb_num_std_dev: float = 2.5,
    # 1時間足用パラメータ
    macd_fast: int = 12,
    macd_slow: int = 20,
    macd_signal: int = 11,
    initial_balance: float = 10000.0,
    lookback_window_15m: int = 100,
    lookback_window_1h: int = 50,
    log_path: Optional[str] = None
) -> Dict:
    """
    マルチタイムフレームシミュレーションを実行
    
    Returns:
        シミュレーション結果の辞書
    """
    # ログ出力関数
    def write_log(message: str):
        timestamp = datetime.now(timezone.utc).isoformat()
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        sys.stdout.flush()  # バッファリング問題を解決
        if log_path:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
    
    # 初期ログ
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        write_log("Multi-timeframe simulation started")
        write_log(f"15m data points: {len(data_15m)}")
        write_log(f"1h data points: {len(data_1h)}")
        write_log(f"Parameters: RSI({rsi_period}/{rsi_oversold}-{rsi_overbought}) [15m], BB({bb_period}/{bb_num_std_dev}) [15m], MACD({macd_fast}/{macd_slow}/{macd_signal}) [1h]")
        write_log("-" * 80)
    
    # エージェント作成
    agent = MultiTimeframeAgent(
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
    
    # データ整列（最適化版）
    start_time = time.time()
    write_log("Aligning timeframes...")
    
    def progress_callback(current, total, percent):
        if percent % 10 == 0:  # 10%ごと
            write_log(f"Alignment progress: {percent}% ({current}/{total})")
    
    aligned_data, data_1h_sorted = align_timeframes(data_15m, data_1h, progress_callback)
    
    alignment_time = time.time() - start_time
    write_log(f"Data alignment completed: {len(aligned_data)} aligned points in {alignment_time:.2f}s")
    
    if len(aligned_data) < lookback_window_15m:
        error_msg = f'Insufficient data: need at least {lookback_window_15m} aligned data points, got {len(aligned_data)}'
        write_log(f"Error: {error_msg}")
        return {'error': error_msg}
    
    # シミュレーター初期化
    simulator = FullPositionSimulator(initial_balance=initial_balance)
    simulator.reset()
    
    # シミュレーション実行
    total_iterations = len(aligned_data) - lookback_window_15m
    sim_start_time = time.time()
    last_log_time = sim_start_time
    log_interval = 300  # 5分 = 300秒
    
    write_log(f"Starting simulation: {total_iterations} iterations")
    
    for i in range(lookback_window_15m, len(aligned_data)):
        price_15m, idx_1h = aligned_data[i]
        
        # 15分足データの履歴を取得（効率的に）
        historical_15m = [d[0] for d in aligned_data[i-lookback_window_15m:i]]
        
        # 1時間足データの履歴を取得（インデックスを使用して効率的に）
        historical_1h = data_1h_sorted[:idx_1h]
        historical_1h_window = historical_1h[-lookback_window_1h:] if len(historical_1h) >= lookback_window_1h else historical_1h
        
        # エージェントに判断を求める
        decision = agent.decide(
            price_data=price_15m,
            historical_data=historical_15m,
            historical_data_1h=historical_1h_window
        )
        
        # 取引を実行
        simulator.execute_trade(decision, price_15m.price)
        
        # 進捗ログ（5分ごと、または完了時）
        current_time = time.time()
        iteration = i - lookback_window_15m + 1
        if current_time - last_log_time >= log_interval or iteration == total_iterations:
            elapsed = current_time - sim_start_time
            progress = (iteration / total_iterations) * 100
            estimated_total = (elapsed / iteration) * total_iterations if iteration > 0 else 0
            remaining = estimated_total - elapsed
            
            elapsed_h, elapsed_m = int(elapsed // 3600), int((elapsed % 3600) // 60)
            remaining_h, remaining_m = int(remaining // 3600), int((remaining % 3600) // 60)
            
            write_log(f"Progress: {iteration}/{total_iterations} ({progress:.1f}%) | "
                     f"Elapsed: {elapsed_h}h {elapsed_m}m | "
                     f"Estimated remaining: {remaining_h}h {remaining_m}m | "
                     f"Trades: {len(simulator.trades)}")
            last_log_time = current_time
    
    # 最終結果を計算
    final_price = aligned_data[-1][0].price
    final_value = simulator.balance + (simulator.btc_holdings * final_price)
    total_profit = final_value - initial_balance
    profit_percentage = (total_profit / initial_balance) * 100
    
    # 取引統計
    buy_trades = [t for t in simulator.trades if t.action == Action.BUY]
    sell_trades = [t for t in simulator.trades if t.action == Action.SELL]
    
    total_time = time.time() - start_time
    write_log(f"Simulation completed in {total_time:.2f}s")
    write_log(f"Final profit: {profit_percentage:.2f}% | Total trades: {len(simulator.trades)}")
    
    return {
        'initial_balance': initial_balance,
        'final_balance': simulator.balance,
        'final_btc_holdings': simulator.btc_holdings,
        'final_price': final_price,
        'final_value': final_value,
        'total_profit': total_profit,
        'profit_percentage': profit_percentage,
        'total_trades': len(simulator.trades),
        'buy_trades': len(buy_trades),
        'sell_trades': len(sell_trades),
        'trades': [
            {
                'action': t.action.value,
                'price': t.price,
                'amount': t.amount,
                'timestamp': t.timestamp.isoformat()
            }
            for t in simulator.trades
        ],
        'parameters': {
            'rsi_period': rsi_period,
            'rsi_oversold': rsi_oversold,
            'rsi_overbought': rsi_overbought,
            'bb_period': bb_period,
            'bb_num_std_dev': bb_num_std_dev,
            'macd_fast': macd_fast,
            'macd_slow': macd_slow,
            'macd_signal': macd_signal
        }
    }


def main():
    parser = argparse.ArgumentParser(description='Multi-timeframe agent simulation')
    parser.add_argument('--csv-15m', required=True, help='Path to 15-minute k-line CSV file')
    parser.add_argument('--csv-1h', required=True, help='Path to 1-hour k-line CSV file')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    
    # 15分足用パラメータ
    parser.add_argument('--rsi-period', type=int, default=10, help='RSI period (15m)')
    parser.add_argument('--rsi-oversold', type=float, default=35.0, help='RSI oversold threshold (15m)')
    parser.add_argument('--rsi-overbought', type=float, default=80.0, help='RSI overbought threshold (15m)')
    parser.add_argument('--bb-period', type=int, default=22, help='Bollinger Bands period (15m)')
    parser.add_argument('--bb-std-dev', type=float, default=2.5, help='Bollinger Bands std dev (15m)')
    
    # 1時間足用パラメータ
    parser.add_argument('--macd-fast', type=int, default=12, help='MACD fast period (1h)')
    parser.add_argument('--macd-slow', type=int, default=20, help='MACD slow period (1h)')
    parser.add_argument('--macd-signal', type=int, default=11, help='MACD signal period (1h)')
    
    parser.add_argument('--initial-balance', type=float, default=10000.0, help='Initial balance')
    parser.add_argument('--lookback-15m', type=int, default=100, help='Lookback window for 15m data')
    parser.add_argument('--lookback-1h', type=int, default=50, help='Lookback window for 1h data')
    parser.add_argument('--log', type=str, default=None, help='Log file path (optional)')
    
    args = parser.parse_args()
    
    print("Loading 15-minute data...")
    sys.stdout.flush()
    data_15m = load_price_data_from_csv(args.csv_15m)
    print(f"Loaded {len(data_15m)} 15-minute data points")
    sys.stdout.flush()
    
    print("Loading 1-hour data...")
    sys.stdout.flush()
    data_1h = load_price_data_from_csv(args.csv_1h)
    print(f"Loaded {len(data_1h)} 1-hour data points")
    sys.stdout.flush()
    
    # ログファイルパスの設定
    log_path = None
    if args.log:
        log_path = args.log if os.path.isabs(args.log) else os.path.join(project_root, args.log)
    
    print("Running simulation...")
    sys.stdout.flush()
    result = run_simulation(
        data_15m=data_15m,
        data_1h=data_1h,
        agent_id="multi_timeframe_agent",
        rsi_period=args.rsi_period,
        rsi_oversold=args.rsi_oversold,
        rsi_overbought=args.rsi_overbought,
        bb_period=args.bb_period,
        bb_num_std_dev=args.bb_std_dev,
        macd_fast=args.macd_fast,
        macd_slow=args.macd_slow,
        macd_signal=args.macd_signal,
        initial_balance=args.initial_balance,
        lookback_window_15m=args.lookback_15m,
        lookback_window_1h=args.lookback_1h,
        log_path=log_path
    )
    
    if 'error' in result:
        print(f"Error: {result['error']}")
        return 1
    
    # 結果を保存
    import json
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    # 結果を表示
    print("\n" + "=" * 80)
    print("Simulation Results")
    print("=" * 80)
    print(f"Initial Balance: ${result['initial_balance']:,.2f}")
    print(f"Final Value: ${result['final_value']:,.2f}")
    print(f"Total Profit: ${result['total_profit']:,.2f}")
    print(f"Profit Percentage: {result['profit_percentage']:.2f}%")
    print(f"Total Trades: {result['total_trades']} ({result['buy_trades']} buys, {result['sell_trades']} sells)")
    print("\nParameters:")
    params = result['parameters']
    print(f"  15m - RSI: Period={params['rsi_period']}, Oversold={params['rsi_oversold']}, Overbought={params['rsi_overbought']}")
    print(f"  15m - BB: Period={params['bb_period']}, Std Dev={params['bb_num_std_dev']}")
    print(f"  1h - MACD: Fast={params['macd_fast']}, Slow={params['macd_slow']}, Signal={params['macd_signal']}")
    print("=" * 80)
    print(f"\nResults saved to: {args.output}")
    if log_path:
        print(f"Log saved to: {log_path}")
    sys.stdout.flush()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

