#!/usr/bin/env python3
"""
RSI+MACD+ボリンジャーバンドエージェントのL18直交配列表によるグリッドサーチ
"""
import sys
import os
import csv
from datetime import datetime
import json
from typing import List, Dict, Optional

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from shared.agents.rsi_macd_bb_agent_with_stoploss import RSIMACDBBAgentWithStopLoss
from shared.models.trading import PriceData, Action, TradingDecision, Order, OrderStatus
from simulation.engine.simulator import TradingSimulator


class FullPositionSimulator(TradingSimulator):
    """全額取引シミュレーター"""
    
    def execute_trade(self, decision: TradingDecision, current_price: float, fee_rate: float = 0.001) -> Optional[Order]:
        """取引をシミュレート（全額取引版）"""
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
    rsi_period: int,
    rsi_oversold: float,
    rsi_overbought: float,
    macd_fast: int,
    macd_slow: int,
    macd_signal: int,
    bb_period: int,
    bb_num_std_dev: float,
    stop_loss_percentage: float,
    initial_balance: float,
    lookback_window: int
) -> Dict:
    """単一のシミュレーションを実行"""
    agent = RSIMACDBBAgentWithStopLoss(
        agent_id=agent_id,
        rsi_period=rsi_period,
        rsi_oversold=rsi_oversold,
        rsi_overbought=rsi_overbought,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        bb_period=bb_period,
        bb_num_std_dev=bb_num_std_dev,
        stop_loss_percentage=stop_loss_percentage,
        trailing_stop_percentage=None
    )
    
    simulator = FullPositionSimulator(initial_balance=initial_balance)
    result = simulator.run_simulation(
        agent,
        price_data,
        lookback_window=lookback_window,
        stop_loss_percentage=stop_loss_percentage
    )
    
    trailing_stop_trades = len([d for d in result['decisions'] if 'Trailing Stop triggered' in d.get('reason', '')])
    result['trailing_stop_trades'] = trailing_stop_trades
    
    # パラメータを結果に追加
    result['rsi_period'] = rsi_period
    result['rsi_oversold'] = rsi_oversold
    result['rsi_overbought'] = rsi_overbought
    result['macd_fast'] = macd_fast
    result['macd_slow'] = macd_slow
    result['macd_signal'] = macd_signal
    result['bb_period'] = bb_period
    result['bb_num_std_dev'] = bb_num_std_dev
    result['stop_loss_percentage'] = stop_loss_percentage
    result['lookback_window'] = lookback_window
    
    return result


def run_l18_grid_search(csv_path: str, experiment_plan_file: str, initial_balance: float = 10000.0):
    """L18直交配列表に基づいてグリッドサーチを実行"""
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print()
    
    # 実験計画を読み込む
    with open(experiment_plan_file, 'r') as f:
        plan_data = json.load(f)
    
    experiments = plan_data['experiments']
    print(f"L18直交配列表による実験計画: {len(experiments)}件の実験")
    print()
    
    results = []
    best_profit_pct = float('-inf')
    best_result = None
    
    for idx, exp in enumerate(experiments, 1):
        exp_num = exp['experiment']
        
        # lookback_windowを計算
        min_lookback = max(exp['macd_slow'] + exp['macd_signal'], exp['rsi_period'] + 1, exp['bb_period'], 100)
        
        agent_id = f"l18_exp{exp_num}_r{exp['rsi_period']}_os{exp['rsi_oversold']}_ob{exp['rsi_overbought']}_f{exp['macd_fast']}_s{exp['macd_slow']}_sig{exp['macd_signal']}_bbp{exp['bb_period']}_bbstd{exp['bb_std_dev']:.1f}_sl{int(exp['stop_loss']*100)}"
        
        try:
            result = run_single_simulation(
                price_data=price_data,
                agent_id=agent_id,
                rsi_period=exp['rsi_period'],
                rsi_oversold=exp['rsi_oversold'],
                rsi_overbought=exp['rsi_overbought'],
                macd_fast=exp['macd_fast'],
                macd_slow=exp['macd_slow'],
                macd_signal=exp['macd_signal'],
                bb_period=exp['bb_period'],
                bb_num_std_dev=exp['bb_std_dev'],
                stop_loss_percentage=exp['stop_loss'],
                initial_balance=initial_balance,
                lookback_window=min_lookback
            )
            
            result['experiment_number'] = exp_num
            results.append(result)
            
            if result['profit_percentage'] > best_profit_pct:
                best_profit_pct = result['profit_percentage']
                best_result = result
            
            print(f"実験{exp_num:2d}/{len(experiments)}: 利益率={result['profit_percentage']:>8.2f}%, "
                  f"取引数={result['total_trades']:>3d}件 "
                  f"(RSI={exp['rsi_period']}, MACD={exp['macd_fast']}/{exp['macd_slow']}, BB={exp['bb_period']}/{exp['bb_std_dev']:.1f}, SL={exp['stop_loss']*100:.0f}%)")
        
        except Exception as e:
            print(f"実験{exp_num:2d}でエラー: {e}")
            continue
    
    # 結果をソート
    results.sort(key=lambda x: x['profit_percentage'], reverse=True)
    
    # 結果を表示
    print("\n" + "=" * 160)
    print("L18直交配列表による探索結果")
    print("=" * 160)
    print(f"総実験数: {len(results)}")
    print()
    
    print("トップ10の結果:")
    print("-" * 160)
    header = f"{'Rank':<5} {'Exp':<4} {'RSI':<4} {'RSI OS':<7} {'RSI OB':<7} {'MACD F':<7} {'MACD S':<7} {'MACD Sig':<9} {'BB P':<6} {'BB Std':<7} {'SL':<6} {'Profit%':<12} {'Trades':<8}"
    print(header)
    print("-" * 160)
    
    for rank, result in enumerate(results[:10], 1):
        print(f"{rank:<5} "
              f"{result['experiment_number']:<4} "
              f"{result['rsi_period']:<4} "
              f"{result['rsi_oversold']:<7.0f} "
              f"{result['rsi_overbought']:<7.0f} "
              f"{result['macd_fast']:<7} "
              f"{result['macd_slow']:<7} "
              f"{result['macd_signal']:<9} "
              f"{result['bb_period']:<6} "
              f"{result['bb_num_std_dev']:<7.1f} "
              f"{result['stop_loss_percentage']*100:.0f}%    "
              f"{result['profit_percentage']:>10.2f}% "
              f"{result['total_trades']:<8}")
    
    print()
    
    if best_result:
        print("=" * 160)
        print("最良の結果")
        print("=" * 160)
        print(f"実験番号: {best_result['experiment_number']}")
        print(f"利益率: {best_result['profit_percentage']:.2f}%")
        print(f"利益額: ${best_result['total_profit']:,.2f}")
        print(f"最終価値: ${best_result['final_value']:,.2f}")
        print()
        print(f"最適パラメータ:")
        print(f"  RSI期間: {best_result['rsi_period']}")
        print(f"  RSIオーバーソールド: {best_result['rsi_oversold']}")
        print(f"  RSIオーバーボート: {best_result['rsi_overbought']}")
        print(f"  MACD Fast: {best_result['macd_fast']}")
        print(f"  MACD Slow: {best_result['macd_slow']}")
        print(f"  MACD Signal: {best_result['macd_signal']}")
        print(f"  ボリンジャーバンド期間: {best_result['bb_period']}")
        print(f"  ボリンジャーバンド標準偏差: {best_result['bb_num_std_dev']}")
        print(f"  損失確定: {best_result['stop_loss_percentage']*100:.0f}%")
        print(f"  総取引数: {best_result['total_trades']}件")
        print()
    
    return results, best_result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RSI+MACD+ボリンジャーバンドエージェントのL18直交配列表によるグリッドサーチ")
    parser.add_argument("--csv", type=str, default="data/btc_prices_2021_2025.csv")
    parser.add_argument("--plan", type=str, default="results/l18_experiment_plan.json", help="L18実験計画ファイル")
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--output", type=str, help="結果をJSONファイルに保存するパス")
    
    args = parser.parse_args()
    
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(project_root, csv_path)
    
    plan_path = args.plan
    if not os.path.isabs(plan_path):
        plan_path = os.path.join(project_root, plan_path)
    
    if not os.path.exists(csv_path):
        print(f"エラー: CSVファイルが見つかりません: {csv_path}")
        sys.exit(1)
    
    if not os.path.exists(plan_path):
        print(f"エラー: 実験計画ファイルが見つかりません: {plan_path}")
        sys.exit(1)
    
    # グリッドサーチ実行
    results, best_result = run_l18_grid_search(
        csv_path=csv_path,
        experiment_plan_file=plan_path,
        initial_balance=args.initial_balance
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
            'method': 'L18_Orthogonal_Array',
            'all_results': results,
            'best_result': best_result,
            'summary': {
                'total_experiments': len(results),
                'best_profit_percentage': best_result['profit_percentage'] if best_result else None,
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=json_serializer, ensure_ascii=False)
        
        print(f"結果を保存しました: {output_path}")

