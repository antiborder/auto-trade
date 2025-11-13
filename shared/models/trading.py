"""
取引関連のデータモデル
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Action(Enum):
    """取引アクション"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderStatus(Enum):
    """注文ステータス"""
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class PriceData:
    """価格データ"""
    timestamp: datetime
    price: float
    volume: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    close: Optional[float] = None


@dataclass
class TradingDecision:
    """取引判断"""
    agent_id: str
    timestamp: datetime
    action: Action
    confidence: float
    price: float
    reason: str
    model_prediction: Optional[float] = None


@dataclass
class Order:
    """注文情報"""
    order_id: str
    agent_id: str
    action: Action
    amount: float
    price: float
    timestamp: datetime
    status: OrderStatus
    trader_id: str
    execution_price: Optional[float] = None
    execution_timestamp: Optional[datetime] = None
    error_message: Optional[str] = None


@dataclass
class AgentPerformance:
    """エージェントパフォーマンス"""
    agent_id: str
    total_profit: float
    total_trades: int
    win_rate: float
    last_updated: datetime
    current_balance: float
    current_position: float  # BTC保有量


