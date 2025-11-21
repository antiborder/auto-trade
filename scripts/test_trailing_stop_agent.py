#!/usr/bin/env python3
"""
トレーリングストップロス機能付きエージェントのテストスクリプト
"""
import sys
import os
import csv
from datetime import datetime
import json

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.agents.ma_agent_with_trailing_stop import MaAgentWithTrailingStop
from shared.models.trading import PriceData
from simulation.engine.simulator import TradingSimulator


class FullPositionSimulator(TradingSimulator):
    """全額取引シミュレーター"""
    
    def execute_trade(self, decision, current_price: float, fee_rate: float = 0.001):
        from shared.models.trading import Action, Order, OrderStatus
        from typing import Optional
        
        if decision.action == Action.HOLD:
            return None
        
        if decision.action == Action.BUY:
            if self.balance <= 0:
                return None
            order_amount_usd = self.balance / (1 + fee_rate)
            btc_amount = order_amount_usd / current_price
            fee = order_amount_usd * fee_rate
            self.balance = 0
            self.btc_holdings += btc_amount
            
            if self.entry_price is None:
                self.entry_price = current_price
            else:
                total_btc = self.btc_holdings
                old_btc = self.btc_holdings - btc_amount
                if total_btc > 0:
                    self.entry_price = (old_btc * self.entry_price + btc_amount * current_price) / total_btc
            
        elif decision.action == Action.SELL:
            if self.btc_holdings <= 0:
                return None
            btc_amount = self.btc_holdings
            order_amount_usd = btc_amount * current_price
            fee = order_amount_usd * fee_rate
            self.btc_holdings = 0
            self.balance += (order_amount_usd - fee)
            self.entry_price = None
        
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


def load_price_data_from_csv(csv_path: str):
    price_data = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                timestamp_str = row['timestamp'].strip()
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


def run_simulation(
    csv_path: str,
    short_window: int,
    long_window: int,
    stop_loss_percentage: float,
    trailing_stop_percentage: float,
    initial_balance: float = 10000.0,
    lookback_window: int = 1100
):
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    if len(price_data) < lookback_window + 10:
        print(f"エラー: 価格データが不足しています")
        return None
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print()
    
    # エージェント作成
    agent = MaAgentWithTrailingStop(
        agent_id="ma_trailing_stop_test",
        short_window=short_window,
        long_window=long_window,
        stop_loss_percentage=stop_loss_percentage,
        trailing_stop_percentage=trailing_stop_percentage
    )
    
    # シミュレーター作成
    simulator = FullPositionSimulator(initial_balance=initial_balance)
    
    # シミュレーション実行
    result = simulator.run_simulation(
        agent,
        price_data,
        lookback_window=lookback_window,
        stop_loss_percentage=stop_loss_percentage  # シミュレーター側の損失確定も有効化
    )
    
    # 結果を表示
    print("=" * 80)
    print("シミュレーション結果")
    print("=" * 80)
    print(f"利益率: {result['profit_percentage']:.2f}%")
    print(f"利益額: ${result['total_profit']:,.2f}")
    print(f"総取引数: {result['total_trades']}")
    print(f"  買い注文: {result['buy_trades']}")
    print(f"  売り注文: {result['sell_trades']}")
    print(f"  損失確定取引: {result.get('stop_loss_trades', 0)}")
    
    # トレーリングストップロス取引数をカウント
    trailing_stop_count = len([d for d in result['decisions'] if 'Trailing Stop triggered' in d.get('reason', '')])
    print(f"  トレーリングストップロス取引: {trailing_stop_count}")
    print()
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="トレーリングストップロス機能付きエージェントでシミュレーション")
    parser.add_argument("--csv", type=str, default="data/btc_prices_2021_2025.csv")
    parser.add_argument("--short-window", type=int, default=10)
    parser.add_argument("--long-window", type=int, default=1000)
    parser.add_argument("--stop-loss", type=float, default=0.07, help="損失確定パーセンテージ（デフォルト: 0.07 = 7%）")
    parser.add_argument("--trailing-stop", type=float, default=0.05, help="トレーリングストップロスパーセンテージ（デフォルト: 0.05 = 5%）")
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--lookback-window", type=int, default=1050)
    
    args = parser.parse_args()
    
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(project_root, csv_path)
    
    if not os.path.exists(csv_path):
        print(f"エラー: CSVファイルが見つかりません: {csv_path}")
        sys.exit(1)
    
    print(f"パラメータ:")
    print(f"  短期移動平均: {args.short_window}")
    print(f"  長期移動平均: {args.long_window}")
    print(f"  損失確定: {args.stop_loss*100:.1f}%")
    print(f"  トレーリングストップロス: {args.trailing_stop*100:.1f}%")
    print()
    
    result = run_simulation(
        csv_path=csv_path,
        short_window=args.short_window,
        long_window=args.long_window,
        stop_loss_percentage=args.stop_loss,
        trailing_stop_percentage=args.trailing_stop,
        initial_balance=args.initial_balance,
        lookback_window=args.lookback_window
    )

