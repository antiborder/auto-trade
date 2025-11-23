"""
マルチタイムフレームシミュレーター
15分足データと1時間足データを使用したシミュレーション処理を提供
"""
import bisect
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Callable

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


def align_timeframes(
    data_15m: List[PriceData],
    data_1h: List[PriceData],
    progress_callback: Optional[Callable[[int, int, int], None]] = None
) -> Tuple[List[Tuple[PriceData, int]], List[PriceData]]:
    """
    15分足データと1時間足データを時系列で整列（最適化版）
    各15分足データポイントに対して、対応する1時間足データの履歴を返す
    
    Args:
        data_15m: 15分足データ
        data_1h: 1時間足データ
        progress_callback: 進捗コールバック関数（オプション）
            Callback signature: (current: int, total: int, percent: int) -> None
    
    Returns:
        Tuple of (aligned_data, data_1h_sorted) where:
        - aligned_data: List of tuples (15m_price_data, 1h_index)
        - data_1h_sorted: Sorted 1-hour data
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


class MultiTimeframeSimulator:
    """
    マルチタイムフレームシミュレーター
    15分足データからRSIとBBを計算、1時間足データからMACDを計算
    """
    
    def __init__(
        self,
        aligned_data: List[Tuple[PriceData, int]],
        data_1h_sorted: List[PriceData],
        initial_balance: float = 10000.0,
        lookback_window_15m: int = 100,
        lookback_window_1h: int = 50
    ):
        """
        初期化
        
        Args:
            aligned_data: 整列済みデータ（align_timeframesの結果）
            data_1h_sorted: ソート済み1時間足データ
            initial_balance: 初期残高
            lookback_window_15m: 15分足データのlookbackウィンドウサイズ
            lookback_window_1h: 1時間足データのlookbackウィンドウサイズ
        """
        self.aligned_data = aligned_data
        self.data_1h_sorted = data_1h_sorted
        self.initial_balance = initial_balance
        self.lookback_window_15m = lookback_window_15m
        self.lookback_window_1h = lookback_window_1h
        
        if len(aligned_data) < lookback_window_15m:
            raise ValueError(f'Insufficient data: need at least {lookback_window_15m} aligned data points, got {len(aligned_data)}')
    
    def run_simulation(
        self,
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
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict:
        """
        シミュレーションを実行
        
        Args:
            agent_id: エージェントID
            rsi_period: RSI期間（15分足用）
            rsi_oversold: RSIオーバーソールド閾値（15分足用）
            rsi_overbought: RSIオーバーボート閾値（15分足用）
            bb_period: ボリンジャーバンド期間（15分足用）
            bb_num_std_dev: ボリンジャーバンド標準偏差倍数（15分足用）
            macd_fast: MACD短期EMA期間（1時間足用）
            macd_slow: MACD長期EMA期間（1時間足用）
            macd_signal: MACDシグナルライン期間（1時間足用）
            progress_callback: 進捗コールバック関数（オプション）
                Callback signature: (iteration: int, total: int) -> None
        
        Returns:
            シミュレーション結果の辞書
        """
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
        
        # シミュレーター初期化
        simulator = FullPositionSimulator(initial_balance=self.initial_balance)
        simulator.reset()
        
        # シミュレーション実行
        total_iterations = len(self.aligned_data) - self.lookback_window_15m
        
        for i in range(self.lookback_window_15m, len(self.aligned_data)):
            price_15m, idx_1h = self.aligned_data[i]
            
            # 15分足データの履歴を取得（効率的に）
            historical_15m = [d[0] for d in self.aligned_data[i-self.lookback_window_15m:i]]
            
            # 1時間足データの履歴を取得（インデックスを使用して効率的に）
            historical_1h = self.data_1h_sorted[:idx_1h]
            historical_1h_window = historical_1h[-self.lookback_window_1h:] if len(historical_1h) >= self.lookback_window_1h else historical_1h
            
            # エージェントに判断を求める
            decision = agent.decide(
                price_data=price_15m,
                historical_data=historical_15m,
                historical_data_1h=historical_1h_window
            )
            
            # 取引を実行
            simulator.execute_trade(decision, price_15m.price)
            
            # 進捗コールバック
            if progress_callback:
                iteration = i - self.lookback_window_15m + 1
                progress_callback(iteration, total_iterations)
        
        # 最終結果を計算
        final_price = self.aligned_data[-1][0].price
        final_value = simulator.balance + (simulator.btc_holdings * final_price)
        total_profit = final_value - self.initial_balance
        profit_percentage = (total_profit / self.initial_balance) * 100
        
        # 取引統計
        buy_trades = [t for t in simulator.trades if t.action == Action.BUY]
        sell_trades = [t for t in simulator.trades if t.action == Action.SELL]
        
        return {
            'initial_balance': self.initial_balance,
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

