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
    
    def reset(self):
        """シミュレーションをリセット"""
        self.balance = self.initial_balance
        self.btc_holdings = self.initial_btc
        self.trades = []
        self.decisions = []
    
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
            
        elif decision.action == Action.SELL:
            # 売り: 保有BTCの10%を売却
            if self.btc_holdings <= 0:
                return None
            
            btc_amount = self.btc_holdings * 0.1
            order_amount_usd = btc_amount * current_price
            fee = order_amount_usd * fee_rate
            
            self.btc_holdings -= btc_amount
            self.balance += (order_amount_usd - fee)
        
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
    
    def run_simulation(self, agent: BaseAgent, price_history: List[PriceData], lookback_window: int = 60) -> dict:
        """
        シミュレーションを実行
        
        Args:
            agent: 取引エージェント
            price_history: 価格履歴
            lookback_window: エージェントが参照する過去データのウィンドウサイズ
            
        Returns:
            dict: シミュレーション結果
        """
        self.reset()
        
        for i in range(lookback_window, len(price_history)):
            current_price_data = price_history[i]
            historical_data = price_history[i-lookback_window:i]
            
            # エージェントで判断
            decision = agent.decide(current_price_data, historical_data)
            
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


