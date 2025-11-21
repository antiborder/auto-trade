#!/usr/bin/env python3
"""
RSI+MACD+ボリンジャーバンドエージェントのグリッドサーチ
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

from shared.agents.rsi_macd_bb_agent import RSIMACDBBAgent
from shared.agents.rsi_macd_bb_agent_with_stoploss import RSIMACDBBAgentWithStopLoss
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
    stop_loss_percentage: Optional[float],
    trailing_stop_percentage: Optional[float],
    initial_balance: float,
    lookback_window: int
) -> Dict:
    """
    単一のシミュレーションを実行
    
    Returns:
        シミュレーション結果の辞書
    """
    # エージェント作成
    if stop_loss_percentage is not None:
        # 損失確定機能付き
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
            trailing_stop_percentage=trailing_stop_percentage
        )
    else:
        # 損失確定なし
        agent = RSIMACDBBAgent(
            agent_id=agent_id,
            rsi_period=rsi_period,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            macd_fast=macd_fast,
            macd_slow=macd_slow,
            macd_signal=macd_signal,
            bb_period=bb_period,
            bb_num_std_dev=bb_num_std_dev
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
    result['rsi_period'] = rsi_period
    result['rsi_oversold'] = rsi_oversold
    result['rsi_overbought'] = rsi_overbought
    result['macd_fast'] = macd_fast
    result['macd_slow'] = macd_slow
    result['macd_signal'] = macd_signal
    result['bb_period'] = bb_period
    result['bb_num_std_dev'] = bb_num_std_dev
    result['stop_loss_percentage'] = stop_loss_percentage
    result['trailing_stop_percentage'] = trailing_stop_percentage
    result['lookback_window'] = lookback_window
    
    return result


def grid_search(
    csv_path: str,
    rsi_periods: List[int],
    rsi_oversold_levels: List[float],
    rsi_overbought_levels: List[float],
    macd_fast_periods: List[int],
    macd_slow_periods: List[int],
    macd_signal_periods: List[int],
    bb_periods: List[int],
    bb_num_std_devs: List[float],
    stop_loss_percentages: Optional[List[float]] = None,
    trailing_stop_percentages: Optional[List[float]] = None,
    initial_balance: float = 10000.0,
    min_lookback: int = 100
):
    """
    グリッドサーチを実行
    
    Args:
        csv_path: 価格データのCSVファイルパス
        rsi_periods: テストするRSI期間のリスト
        rsi_oversold_levels: テストするRSIオーバーソールド閾値のリスト
        rsi_overbought_levels: テストするRSIオーバーボート閾値のリスト
        macd_fast_periods: テストするMACD短期EMA期間のリスト
        macd_slow_periods: テストするMACD長期EMA期間のリスト
        macd_signal_periods: テストするMACDシグナルライン期間のリスト
        bb_periods: テストするボリンジャーバンド期間のリスト
        bb_num_std_devs: テストするボリンジャーバンド標準偏差倍数のリスト
        stop_loss_percentages: テストする損失確定パーセンテージのリスト（Noneの場合は損失確定なし）
        trailing_stop_percentages: テストするトレーリングストップロスパーセンテージのリスト（Noneの場合は無効）
        initial_balance: 初期残高
        min_lookback: 最小lookbackウィンドウサイズ
    """
    print(f"価格データを読み込んでいます: {csv_path}")
    price_data = load_price_data_from_csv(csv_path)
    
    if len(price_data) < min_lookback + 100:
        print(f"エラー: 価格データが不足しています")
        return None
    
    print(f"読み込んだ価格データ: {len(price_data)}件")
    print(f"期間: {price_data[0].timestamp} ～ {price_data[-1].timestamp}")
    print()
    
    # 有効な組み合わせを生成
    # 損失確定パラメータの処理
    if stop_loss_percentages is None:
        stop_loss_list = [None]
    else:
        stop_loss_list = stop_loss_percentages
    
    if trailing_stop_percentages is None:
        trailing_stop_list = [None]
    else:
        trailing_stop_list = trailing_stop_percentages
    
    # すべての組み合わせを生成
    valid_combinations = []
    for (rsi_p, rsi_os, rsi_ob, macd_f, macd_s, macd_sig, bb_p, bb_std, stop_loss, trailing) in itertools.product(
        rsi_periods,
        rsi_oversold_levels,
        rsi_overbought_levels,
        macd_fast_periods,
        macd_slow_periods,
        macd_signal_periods,
        bb_periods,
        bb_num_std_devs,
        stop_loss_list,
        trailing_stop_list
    ):
        # MACDの期間の妥当性チェック
        if macd_f >= macd_s:
            continue
        
        # lookback_windowは最大期間の合計以上が必要
        min_lookback_required = max(macd_s + macd_sig, rsi_p + 1, bb_p, min_lookback)
        if min_lookback_required + 100 < len(price_data):
            valid_combinations.append((rsi_p, rsi_os, rsi_ob, macd_f, macd_s, macd_sig, bb_p, bb_std, stop_loss, trailing, min_lookback_required))
    
    total_combinations = len(valid_combinations)
    print(f"テストする組み合わせ数: {total_combinations}")
    print(f"  RSI期間: {rsi_periods}")
    print(f"  RSIオーバーソールド: {rsi_oversold_levels}")
    print(f"  RSIオーバーボート: {rsi_overbought_levels}")
    print(f"  MACD Fast: {macd_fast_periods}")
    print(f"  MACD Slow: {macd_slow_periods}")
    print(f"  MACD Signal: {macd_signal_periods}")
    print(f"  ボリンジャーバンド期間: {bb_periods}")
    print(f"  ボリンジャーバンド標準偏差倍数: {bb_num_std_devs}")
    if stop_loss_percentages:
        print(f"  損失確定: {[f'{p*100:.0f}%' for p in stop_loss_percentages]}")
    if trailing_stop_percentages:
        print(f"  トレーリングストップロス: {[f'{p*100:.0f}%' for p in trailing_stop_percentages]}")
    print()
    
    results = []
    best_profit_pct = float('-inf')
    best_result = None
    
    for idx, (rsi_p, rsi_os, rsi_ob, macd_f, macd_s, macd_sig, bb_p, bb_std, stop_loss, trailing, lookback) in enumerate(valid_combinations, 1):
        stop_loss_str = f"sl{int(stop_loss*100)}pct" if stop_loss else "nosl"
        trailing_str = f"ts{int(trailing*100)}pct" if trailing else "nots"
        agent_id = f"rsi_macd_bb_r{rsi_p}_os{rsi_os:.0f}_ob{rsi_ob:.0f}_f{macd_f}_s{macd_s}_sig{macd_sig}_bbp{bb_p}_bbstd{bb_std}_{stop_loss_str}_{trailing_str}"
        
        try:
            result = run_single_simulation(
                price_data=price_data,
                agent_id=agent_id,
                rsi_period=rsi_p,
                rsi_oversold=rsi_os,
                rsi_overbought=rsi_ob,
                macd_fast=macd_f,
                macd_slow=macd_s,
                macd_signal=macd_sig,
                bb_period=bb_p,
                bb_num_std_dev=bb_std,
                stop_loss_percentage=stop_loss,
                trailing_stop_percentage=trailing,
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
                sl_str = f"{best_result['stop_loss_percentage']*100:.0f}%" if best_result.get('stop_loss_percentage') else "なし"
                print(f"進捗: {idx}/{total_combinations} ({progress:.1f}%) - "
                      f"現在の最良: {best_profit_pct:.2f}% "
                      f"(RSI={best_result['rsi_period']}, MACD={best_result['macd_fast']}/{best_result['macd_slow']}, "
                      f"BB={best_result['bb_period']}/{best_result['bb_num_std_dev']}, SL={sl_str})")
        
        except Exception as e:
            print(f"エラー: RSI={rsi_p}, MACD={macd_f}/{macd_s}/{macd_sig}, BB={bb_p}/{bb_std}: {e}")
            continue
    
    # 結果をソート（利益率で降順）
    results.sort(key=lambda x: x['profit_percentage'], reverse=True)
    
    # 結果を表示
    print("\n" + "=" * 160)
    print("探索結果サマリー")
    print("=" * 160)
    print(f"総テスト数: {len(results)}")
    print()
    
    # トップ20を表示
    print("トップ20の結果:")
    print("-" * 160)
    header = f"{'Rank':<5} {'RSI':<4} {'RSI OS':<7} {'RSI OB':<7} {'MACD F':<7} {'MACD S':<7} {'MACD Sig':<9} {'BB P':<6} {'BB Std':<7} {'SL':<6} {'Profit%':<12} {'Profit$':<12} {'Trades':<8}"
    print(header)
    print("-" * 160)
    
    for rank, result in enumerate(results[:20], 1):
        sl_str = f"{result['stop_loss_percentage']*100:.0f}%" if result.get('stop_loss_percentage') else "なし"
        print(f"{rank:<5} "
              f"{result['rsi_period']:<4} "
              f"{result['rsi_oversold']:<7.0f} "
              f"{result['rsi_overbought']:<7.0f} "
              f"{result['macd_fast']:<7} "
              f"{result['macd_slow']:<7} "
              f"{result['macd_signal']:<9} "
              f"{result['bb_period']:<6} "
              f"{result['bb_num_std_dev']:<7.1f} "
              f"{sl_str:<6} "
              f"{result['profit_percentage']:>10.2f}% "
              f"${result['total_profit']:>10,.2f} "
              f"{result['total_trades']:<8}")
    
    print()
    
    # 最良の結果の詳細
    if best_result:
        print("=" * 160)
        print("最良の結果（詳細）")
        print("=" * 160)
        print(f"RSI期間: {best_result['rsi_period']}")
        print(f"RSIオーバーソールド: {best_result['rsi_oversold']}")
        print(f"RSIオーバーボート: {best_result['rsi_overbought']}")
        print(f"MACD Fast: {best_result['macd_fast']}")
        print(f"MACD Slow: {best_result['macd_slow']}")
        print(f"MACD Signal: {best_result['macd_signal']}")
        print(f"ボリンジャーバンド期間: {best_result['bb_period']}")
        print(f"ボリンジャーバンド標準偏差倍数: {best_result['bb_num_std_dev']}")
        sl_str = f"{best_result['stop_loss_percentage']*100:.1f}%" if best_result.get('stop_loss_percentage') else "なし"
        ts_str = f"{best_result['trailing_stop_percentage']*100:.1f}%" if best_result.get('trailing_stop_percentage') else "なし"
        print(f"損失確定: {sl_str}")
        print(f"トレーリングストップロス: {ts_str}")
        print(f"Lookbackウィンドウ: {best_result['lookback_window']}")
        print()
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
    
    parser = argparse.ArgumentParser(description="RSI+MACD+ボリンジャーバンドエージェントのグリッドサーチ")
    parser.add_argument("--csv", type=str, default="data/btc_prices_2021_2025.csv")
    parser.add_argument("--rsi-period", type=int, nargs='+', default=[35], help="RSI期間")
    parser.add_argument("--rsi-oversold", type=float, nargs='+', default=[30], help="RSIオーバーソールド閾値")
    parser.add_argument("--rsi-overbought", type=float, nargs='+', default=[80], help="RSIオーバーボート閾値")
    parser.add_argument("--macd-fast", type=int, nargs='+', default=[12], help="MACD短期EMA期間")
    parser.add_argument("--macd-slow", type=int, nargs='+', default=[26], help="MACD長期EMA期間")
    parser.add_argument("--macd-signal", type=int, nargs='+', default=[11], help="MACDシグナルライン期間")
    parser.add_argument("--bb-period", type=int, nargs='+', default=[20], help="ボリンジャーバンド期間")
    parser.add_argument("--bb-std-dev", type=float, nargs='+', default=[2.0], help="ボリンジャーバンド標準偏差倍数")
    parser.add_argument("--stop-loss", type=float, nargs='+', help="損失確定パーセンテージ")
    parser.add_argument("--trailing-stop", type=float, nargs='+', help="トレーリングストップロスパーセンテージ")
    parser.add_argument("--initial-balance", type=float, default=10000.0)
    parser.add_argument("--output", type=str, help="結果をJSONファイルに保存するパス")
    
    args = parser.parse_args()
    
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        csv_path = os.path.join(project_root, csv_path)
    
    if not os.path.exists(csv_path):
        print(f"エラー: CSVファイルが見つかりません: {csv_path}")
        sys.exit(1)
    
    # グリッドサーチ実行
    results, best_result = grid_search(
        csv_path=csv_path,
        rsi_periods=args.rsi_period,
        rsi_oversold_levels=args.rsi_oversold,
        rsi_overbought_levels=args.rsi_overbought,
        macd_fast_periods=args.macd_fast,
        macd_slow_periods=args.macd_slow,
        macd_signal_periods=args.macd_signal,
        bb_periods=args.bb_period,
        bb_num_std_devs=args.bb_std_dev,
        stop_loss_percentages=args.stop_loss,
        trailing_stop_percentages=args.trailing_stop,
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
            'all_results': results,
            'best_result': best_result,
            'summary': {
                'total_tests': len(results),
                'best_profit_percentage': best_result['profit_percentage'] if best_result else None,
                'best_rsi_period': best_result['rsi_period'] if best_result else None,
                'best_macd_fast': best_result['macd_fast'] if best_result else None,
                'best_macd_slow': best_result['macd_slow'] if best_result else None,
                'best_bb_period': best_result['bb_period'] if best_result else None,
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, default=json_serializer, ensure_ascii=False)
        
        print(f"結果を保存しました: {output_path}")

