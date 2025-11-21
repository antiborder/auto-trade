"""
シミュレーションエンジン
過去の価格データを使用して取引戦略をシミュレート
"""
from datetime import datetime
from typing import List, Optional
from shared.models.trading import PriceData, Action, TradingDecision, Order, OrderStatus
from shared.agents.base_agent import BaseAgent


class TradingSimulator:
    """取引シミュレーター"""
    
    def __init__(self, initial_balance: float = 10000.0, initial_btc: float = 0.0):
        self.initial_balance = initial_balance
        self.initial_btc = initial_btc
        self.balance = initial_balance
        self.btc_holdings = initial_btc
        self.trades: List[Order] = []
        self.decisions: List[TradingDecision] = []
        
        # エントリー価格追跡（損失確定用）
        self.entry_price: Optional[float] = None
    
    def reset(self):
        """シミュレーションをリセット"""
        self.balance = self.initial_balance
        self.btc_holdings = self.initial_btc
        self.trades = []
        self.decisions = []
        self.entry_price = None
    
    def execute_trade(self, decision: TradingDecision, current_price: float, fee_rate: float = 0.001) -> Optional[Order]:
        """
        取引をシミュレート
        
        Args:
            decision: 取引判断
            current_price: 現在の価格
            fee_rate: 手数料率（デフォルト0.1%）
            
        Returns:
            Order: 実行された注文、またはNone
        """
        if decision.action == Action.HOLD:
            return None
        
        # 注文数量を計算（簡易版: 残高の一定割合）
        if decision.action == Action.BUY:
            # 買い: 残高の10%を使用
            order_amount_usd = self.balance * 0.1
            btc_amount = order_amount_usd / current_price
            fee = order_amount_usd * fee_rate
            
            if order_amount_usd + fee > self.balance:
                return None  # 残高不足
            
            self.balance -= (order_amount_usd + fee)
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
            # 売り: 保有BTCの10%を売却
            if self.btc_holdings <= 0:
                return None
            
            btc_amount = self.btc_holdings * 0.1
            order_amount_usd = btc_amount * current_price
            fee = order_amount_usd * fee_rate
            
            self.btc_holdings -= btc_amount
            self.balance += (order_amount_usd - fee)
            
            # ポジションがなくなったらエントリー価格をリセット
            if self.btc_holdings <= 0:
                self.entry_price = None
        
        order = Order(
            order_id=f"sim_{datetime.utcnow().isoformat()}",
            agent_id=decision.agent_id,
            action=decision.action,
            amount=btc_amount if decision.action == Action.BUY else btc_amount,
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
    
    def run_simulation(
        self,
        agent: BaseAgent,
        price_history: List[PriceData],
        lookback_window: int = 60,
        stop_loss_percentage: Optional[float] = None
    ) -> dict:
        """
        シミュレーションを実行
        
        Args:
            agent: 取引エージェント
            price_history: 価格履歴
            lookback_window: エージェントが参照する過去データのウィンドウサイズ
            stop_loss_percentage: 損失確定パーセンテージ（Noneの場合は損失確定なし）
            
        Returns:
            dict: シミュレーション結果
        """
        self.reset()
        
        # 損失確定チェック用のフラグ
        use_stop_loss = stop_loss_percentage is not None
        
        for i in range(lookback_window, len(price_history)):
            current_price_data = price_history[i]
            historical_data = price_history[i-lookback_window:i]
            
            # 損失確定チェック（優先度が最も高い）
            if use_stop_loss and self.entry_price is not None and self.btc_holdings > 0:
                loss_percentage = (current_price_data.price - self.entry_price) / self.entry_price
                
                if loss_percentage <= -stop_loss_percentage:
                    # 損失確定トリガー
                    stop_loss_decision = TradingDecision(
                        agent_id=agent.agent_id,
                        timestamp=datetime.utcnow(),
                        action=Action.SELL,
                        confidence=1.0,
                        price=current_price_data.price,
                        reason=f"Stop Loss triggered: {loss_percentage*100:.2f}% loss (entry: ${self.entry_price:.2f}, current: ${current_price_data.price:.2f})"
                    )
                    
                    # 損失確定取引を実行（全額売却）
                    btc_amount = self.btc_holdings
                    order_amount_usd = btc_amount * current_price_data.price
                    fee = order_amount_usd * 0.001
                    
                    self.btc_holdings = 0
                    self.balance += (order_amount_usd - fee)
                    self.entry_price = None
                    
                    order = Order(
                        order_id=f"sim_stoploss_{datetime.utcnow().isoformat()}",
                        agent_id=agent.agent_id,
                        action=Action.SELL,
                        amount=btc_amount,
                        price=current_price_data.price,
                        timestamp=stop_loss_decision.timestamp,
                        status=OrderStatus.EXECUTED,
                        trader_id="simulator",
                        execution_price=current_price_data.price,
                        execution_timestamp=stop_loss_decision.timestamp
                    )
                    
                    self.trades.append(order)
                    self.decisions.append(stop_loss_decision)
                    continue  # 損失確定後は通常の判断をスキップ
            
            # エージェントで判断
            decision = agent.decide(current_price_data, historical_data)
            
            # エージェントが損失確定やトレーリングストップロス機能を持つ場合、ポジション情報を更新
            if hasattr(agent, 'update_position'):
                # update_positionのシグネチャを確認
                import inspect
                sig = inspect.signature(agent.update_position)
                params = list(sig.parameters.keys())
                
                if len(params) >= 3 and 'current_price' in params:
                    # トレーリングストップロス対応版（current_priceを渡す）
                    agent.update_position(self.entry_price, self.btc_holdings, current_price_data.price)
                else:
                    # 通常版
                    agent.update_position(self.entry_price, self.btc_holdings)
            
            # 取引実行
            order = self.execute_trade(decision, current_price_data.price)
        
        # 最終評価
        final_price = price_history[-1].price
        final_value = self.balance + (self.btc_holdings * final_price)
        total_profit = final_value - self.initial_balance
        
        return {
            'initial_balance': self.initial_balance,
            'initial_btc': self.initial_btc,
            'final_balance': self.balance,
            'final_btc': self.btc_holdings,
            'final_value': final_value,
            'total_profit': total_profit,
            'profit_percentage': (total_profit / self.initial_balance) * 100,
            'total_trades': len(self.trades),
            'buy_trades': len([t for t in self.trades if t.action == Action.BUY]),
            'sell_trades': len([t for t in self.trades if t.action == Action.SELL]),
            'stop_loss_trades': len([d for d in self.decisions if 'Stop Loss triggered' in d.reason]),
            'trades': [self._order_to_dict(o) for o in self.trades],
            'decisions': [self._decision_to_dict(d) for d in self.decisions]
        }
    
    def _order_to_dict(self, order: Order) -> dict:
        """Orderを辞書に変換"""
        return {
            'order_id': order.order_id,
            'agent_id': order.agent_id,
            'action': order.action.value,
            'amount': order.amount,
            'price': order.price,
            'timestamp': order.timestamp.isoformat() if isinstance(order.timestamp, datetime) else order.timestamp,
            'status': order.status.value,
            'execution_price': order.execution_price
        }
    
    def _decision_to_dict(self, decision: TradingDecision) -> dict:
        """TradingDecisionを辞書に変換"""
        return {
            'agent_id': decision.agent_id,
            'timestamp': decision.timestamp.isoformat() if isinstance(decision.timestamp, datetime) else decision.timestamp,
            'action': decision.action.value,
            'confidence': decision.confidence,
            'price': decision.price,
            'reason': decision.reason
        }
