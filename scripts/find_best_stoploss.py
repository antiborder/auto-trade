#!/usr/bin/env python3
"""
損失確定パラメータの最適値を探索するスクリプト
様々な損失確定パーセンテージをテストしてパフォーマンスを比較
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
from shared.models.trading import PriceData, Action, TradingDecision, Order, OrderStatus
from simulation.engine.simulator import TradingSimulator
from typing import Optional
from datetime import datetime


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


def run_simulation_comparison(
    csv_path: str,
    short_window: int,
    long_window: int,
    stop_loss_percentages: List[float],
    initial_balance: float = 10000.0,
    lookback_window: int = 1100,
    include_no_stoploss: bool = True,
    use_full_position: bool = True
) -> Dict:
    """
    様々な損失確定パラメータでシミュレーションを実行して比較
    
    Args:
        csv_path: 価格データのCSVファイルパス
        short_window: 短期移動平均のウィンドウサイズ
        long_window: 長期移動平均のウィンドウサイズ
        stop_loss_percentages: テストする損失確定パーセンテージのリスト（例: [0.05, 0.07, 0.10]）
        initial_balance: 初期残高
        lookback_window: Lookbackウィンドウサイズ
        include_no_stoploss: Trueの場合、損失確定なしの結果も含める
    
    Returns:
        結果の辞書（各損失確定パラメータごとの結果を含む）
    """
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    if len(price_data) < lookback_window + 10:
        print(f"エラー: 価格データが不足しています")
        return None
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print(f"初期価格: ${price_data[0].price:,.2f}")
    print(f"最終価格: ${price_data[-1].price:,.2f}")
    print()
    
    results = []
    
    # 損失確定なしの場合
    if include_no_stoploss:
        print("=" * 80)
        print("損失確定なしでシミュレーション実行中...")
        print("=" * 80)
        
        agent = MaAgent(
            agent_id="ma_agent_no_stoploss",
            short_window=short_window,
            long_window=long_window
        )
        
        if use_full_position:
            simulator = FullPositionSimulator(initial_balance=initial_balance)
        else:
            simulator = TradingSimulator(initial_balance=initial_balance)
        result = simulator.run_simulation(
            agent,
            price_data,
            lookback_window=lookback_window,
            stop_loss_percentage=None
        )
        
        result['stop_loss_percentage'] = None
        result['short_window'] = short_window
        result['long_window'] = long_window
        results.append(result)
        
        print(f"利益率: {result['profit_percentage']:.2f}%")
        print(f"利益額: ${result['total_profit']:,.2f}")
        print(f"総取引数: {result['total_trades']}")
        print()
    
    # 各損失確定パーセンテージでテスト
    for stop_loss_pct in stop_loss_percentages:
        print("=" * 80)
        print(f"損失確定 {stop_loss_pct*100:.1f}% でシミュレーション実行中...")
        print("=" * 80)
        
        agent_id = f"ma_agent_stoploss_{int(stop_loss_pct*100)}pct"
        agent = MaAgentWithStopLoss(
            agent_id=agent_id,
            short_window=short_window,
            long_window=long_window,
            stop_loss_percentage=stop_loss_pct
        )
        
        if use_full_position:
            simulator = FullPositionSimulator(initial_balance=initial_balance)
        else:
            simulator = TradingSimulator(initial_balance=initial_balance)
        result = simulator.run_simulation(
            agent,
            price_data,
            lookback_window=lookback_window,
            stop_loss_percentage=stop_loss_pct
        )
        
        result['stop_loss_percentage'] = stop_loss_pct
        result['short_window'] = short_window
        result['long_window'] = long_window
        results.append(result)
        
        print(f"利益率: {result['profit_percentage']:.2f}%")
        print(f"利益額: ${result['total_profit']:,.2f}")
        print(f"総取引数: {result['total_trades']}")
        print(f"損失確定取引数: {result.get('stop_loss_trades', 0)}")
        print()
    
    # 結果をソート（利益率で降順）
    results.sort(key=lambda x: x['profit_percentage'], reverse=True)
    
    # 結果を表示
    print("=" * 80)
    print("比較結果サマリー")
    print("=" * 80)
    print(f"{'Rank':<5} {'Stop Loss':<12} {'Profit%':<12} {'Profit$':<12} {'Trades':<10} {'Stop Loss Trades':<15}")
    print("-" * 80)
    
    for rank, result in enumerate(results, 1):
        stop_loss_str = f"{result['stop_loss_percentage']*100:.1f}%" if result['stop_loss_percentage'] is not None else "なし"
        print(f"{rank:<5} "
              f"{stop_loss_str:<12} "
              f"{result['profit_percentage']:>10.2f}% "
              f"${result['total_profit']:>10,.2f} "
              f"{result['total_trades']:<10} "
              f"{result.get('stop_loss_trades', 0):<15}")
    
    print()
    
    # 最良の結果の詳細
    best_result = results[0]
    print("=" * 80)
    print("最良の結果（詳細）")
    print("=" * 80)
    if best_result['stop_loss_percentage'] is None:
        print(f"損失確定: なし")
    else:
        print(f"損失確定: {best_result['stop_loss_percentage']*100:.1f}%")
    print(f"利益率: {best_result['profit_percentage']:.2f}%")
    print(f"利益額: ${best_result['total_profit']:,.2f}")
    print(f"最終価値: ${best_result['final_value']:,.2f}")
    print(f"総取引数: {best_result['total_trades']}")
    print(f"  買い注文: {best_result['buy_trades']}")
    print(f"  売り注文: {best_result['sell_trades']}")
    print(f"  損失確定取引: {best_result.get('stop_loss_trades', 0)}")
    print()
    
    # 価格変動との比較
    initial_price = price_data[0].price
    final_price = price_data[-1].price
    price_change = ((final_price - initial_price) / initial_price) * 100
    print(f"期間中の価格変動: {price_change:.2f}%")
    print(f"相対パフォーマンス: {best_result['profit_percentage'] / price_change:.3f}")
    print()
    
    return {
        'all_results': results,
        'best_result': best_result,
        'price_data_summary': {
            'initial_price': initial_price,
            'final_price': final_price,
            'price_change_percentage': price_change,
            'data_count': len(price_data)
        }
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="損失確定パラメータの最適値を探索")
    parser.add_argument(
        "--csv",
        type=str,
        default="data/btc_prices_2021_2025.csv",
        help="価格データのCSVファイルパス"
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
        "--stop-loss-range",
        type=float,
        nargs=3,
        metavar=('MIN', 'MAX', 'STEP'),
        default=[0.03, 0.15, 0.01],
        help="損失確定パーセンテージの範囲（最小、最大、ステップ、デフォルト: 3% ～ 15%、0.01%ステップ）"
    )
    parser.add_argument(
        "--stop-loss-list",
        type=float,
        nargs='+',
        help="テストする損失確定パーセンテージのリスト（例: 0.05 0.07 0.10）"
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
        "--no-baseline",
        action="store_true",
        help="損失確定なしのベースラインを含めない"
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
    
    # テストする損失確定パーセンテージのリストを作成
    if args.stop_loss_list:
        stop_loss_percentages = args.stop_loss_list
    else:
        min_pct, max_pct, step = args.stop_loss_range
        stop_loss_percentages = []
        current = min_pct
        while current <= max_pct:
            stop_loss_percentages.append(round(current, 4))
            current += step
    
    print(f"テストする損失確定パーセンテージ: {[f'{p*100:.1f}%' for p in stop_loss_percentages]}")
    if not args.no_baseline:
        print("損失確定なしのベースラインも含まれます")
    print()
    
    # シミュレーション実行
    print(f"取引戦略: {'全額取引（100%）' if args.full_position else '部分取引（10%）'}")
    print()
    
    results = run_simulation_comparison(
        csv_path=csv_path,
        short_window=args.short_window,
        long_window=args.long_window,
        stop_loss_percentages=stop_loss_percentages,
        initial_balance=args.initial_balance,
        lookback_window=args.lookback_window,
        include_no_stoploss=not args.no_baseline,
        use_full_position=args.full_position
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
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=json_serializer, ensure_ascii=False)
        
        print(f"結果を保存しました: {output_path}")

