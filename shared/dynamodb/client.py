"""
DynamoDBクライアント
"""
import os
import boto3
from typing import Optional
from decimal import Decimal
from datetime import datetime
import json


class DynamoDBClient:
    """DynamoDBアクセス用クライアント"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'ap-northeast-1'))
        self.table_names = {
            'prices': os.getenv('PRICES_TABLE', 'btc-prices'),
            'decisions': os.getenv('DECISIONS_TABLE', 'trading-decisions'),
            'orders': os.getenv('ORDERS_TABLE', 'trading-orders'),
            'performance': os.getenv('PERFORMANCE_TABLE', 'agent-performance'),
            'simulations': os.getenv('SIMULATIONS_TABLE', 'simulations'),
            'balance': os.getenv('BALANCE_TABLE', 'trading-balance')
        }
    
    def _serialize_value(self, value):
        """値をDynamoDB用にシリアライズ"""
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, float):
            return Decimal(str(value))
        elif isinstance(value, dict):
            return json.dumps(value)
        return value
    
    def _deserialize_value(self, value):
        """DynamoDBの値をデシリアライズ"""
        if isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, str):
            try:
                # JSON文字列の可能性
                return json.loads(value)
            except:
                # ISO形式の日時の可能性
                try:
                    return datetime.fromisoformat(value)
                except:
                    return value
        return value
    
    def put_price(self, timestamp: datetime, price: float, **kwargs):
        """価格データを保存"""
        table = self.dynamodb.Table(self.table_names['prices'])
        item = {
            'timestamp': timestamp.isoformat(),
            'price': Decimal(str(price)),
            **{k: self._serialize_value(v) for k, v in kwargs.items()}
        }
        table.put_item(Item=item)
    
    def get_recent_prices(self, limit: int = 100) -> list:
        """最近の価格データを取得"""
        table = self.dynamodb.Table(self.table_names['prices'])
        response = table.scan(
            Limit=limit,
            ScanFilter={
                'timestamp': {
                    'AttributeValueList': [],
                    'ComparisonOperator': 'NOT_NULL'
                }
            }
        )
        items = response.get('Items', [])
        # タイムスタンプでソート
        items.sort(key=lambda x: x.get('timestamp', ''))
        return [self._deserialize_value(item) for item in items]
    
    def put_decision(self, decision: dict):
        """取引判断を保存"""
        table = self.dynamodb.Table(self.table_names['decisions'])
        item = {
            'agent_id': decision['agent_id'],
            'timestamp': decision['timestamp'].isoformat() if isinstance(decision['timestamp'], datetime) else decision['timestamp'],
            'action': decision['action'],
            'confidence': Decimal(str(decision['confidence'])),
            'price': Decimal(str(decision['price'])),
            'reason': decision.get('reason', ''),
            **{k: self._serialize_value(v) for k, v in decision.items() if k not in ['agent_id', 'timestamp', 'action', 'confidence', 'price', 'reason']}
        }
        table.put_item(Item=item)
    
    def put_order(self, order: dict):
        """注文を保存"""
        table = self.dynamodb.Table(self.table_names['orders'])
        item = {
            'order_id': order['order_id'],
            'agent_id': order['agent_id'],
            'timestamp': order['timestamp'].isoformat() if isinstance(order['timestamp'], datetime) else order['timestamp'],
            'action': order['action'],
            'amount': Decimal(str(order['amount'])),
            'price': Decimal(str(order['price'])),
            'status': order['status'],
            'trader_id': order['trader_id'],
            **{k: self._serialize_value(v) for k, v in order.items() if k not in ['order_id', 'agent_id', 'timestamp', 'action', 'amount', 'price', 'status', 'trader_id']}
        }
        table.put_item(Item=item)
    
    def update_performance(self, agent_id: str, performance: dict):
        """エージェントパフォーマンスを更新"""
        table = self.dynamodb.Table(self.table_names['performance'])
        item = {
            'agent_id': agent_id,
            'last_updated': datetime.utcnow().isoformat(),
            'total_profit': Decimal(str(performance.get('total_profit', 0))),
            'total_trades': performance.get('total_trades', 0),
            'win_rate': Decimal(str(performance.get('win_rate', 0))),
            'current_balance': Decimal(str(performance.get('current_balance', 0))),
            'current_position': Decimal(str(performance.get('current_position', 0)))
        }
        table.put_item(Item=item)
    
    def get_performance(self, agent_id: str) -> Optional[dict]:
        """エージェントパフォーマンスを取得"""
        table = self.dynamodb.Table(self.table_names['performance'])
        response = table.get_item(Key={'agent_id': agent_id})
        if 'Item' in response:
            item = response['Item']
            return {k: self._deserialize_value(v) for k, v in item.items()}
        return None
    
    def put_balance(self, timestamp: datetime, usdt_balance: float, btc_balance: float, **kwargs):
        """残高を保存"""
        table = self.dynamodb.Table(self.table_names['balance'])
        item = {
            'timestamp': timestamp.isoformat(),
            'usdt_balance': Decimal(str(usdt_balance)),
            'btc_balance': Decimal(str(btc_balance)),
            **{k: self._serialize_value(v) for k, v in kwargs.items()}
        }
        table.put_item(Item=item)
    
    def get_recent_balances(self, limit: int = 100) -> list:
        """最近の残高データを取得"""
        table = self.dynamodb.Table(self.table_names['balance'])
        response = table.scan(
            Limit=limit
        )
        items = response.get('Items', [])
        # タイムスタンプでソート
        items.sort(key=lambda x: x.get('timestamp', ''))
        return [{k: self._deserialize_value(v) for k, v in item.items()} for item in items]


