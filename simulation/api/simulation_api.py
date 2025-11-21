"""
シミュレーションAPI
Lambda関数またはAPI Gateway経由で呼び出し可能
"""
import json
import os
import sys
from datetime import datetime
from typing import Optional

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../simulation/engine'))

from dynamodb.client import DynamoDBClient
from simulator import TradingSimulator
from agents.base_agent import BaseAgent
from agents.ma_agent import MaAgent
from agents.lstm_agent import LSTMAgent
from models.trading import PriceData


def create_agent_from_config(agent_config: dict) -> Optional[BaseAgent]:
    """設定からエージェントを作成"""
    agent_type = agent_config.get('type')
    agent_id = agent_config.get('id')
    
    if agent_type == 'SimpleMA' or agent_type == 'MA':
        return MaAgent(
            agent_id=agent_id,
            short_window=agent_config.get('short_window', 5),
            long_window=agent_config.get('long_window', 20)
        )
    elif agent_type == 'LSTM':
        return LSTMAgent(
            agent_id=agent_id,
            model_path=agent_config.get('model_path')
        )
    return None


def run_simulation(agent_config: dict, start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """
    シミュレーションを実行
    
    Args:
        agent_config: エージェント設定
        start_date: 開始日（ISO形式）
        end_date: 終了日（ISO形式）
        
    Returns:
        dict: シミュレーション結果
    """
    # エージェント作成
    agent = create_agent_from_config(agent_config)
    if not agent:
        return {'error': 'Failed to create agent'}
    
    # 価格データ取得
    db_client = DynamoDBClient()
    all_prices = db_client.get_recent_prices(limit=1000)
    
    if not all_prices:
        return {'error': 'No price data available'}
    
    # 日付フィルタリング
    price_data = []
    for p in all_prices:
        timestamp = p.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        if start_date and timestamp < datetime.fromisoformat(start_date):
            continue
        if end_date and timestamp > datetime.fromisoformat(end_date):
            continue
        
        price_data.append(PriceData(
            timestamp=timestamp,
            price=float(p['price']),
            volume=p.get('volume_24h'),
            high=p.get('high'),
            low=p.get('low')
        ))
    
    if len(price_data) < 60:
        return {'error': 'Insufficient price data for simulation'}
    
    # シミュレーション実行
    simulator = TradingSimulator(initial_balance=10000.0)
    result = simulator.run_simulation(agent, price_data, lookback_window=60)
    
    # 結果をDynamoDBに保存
    simulation_id = f"sim_{datetime.utcnow().isoformat()}"
    db_client.dynamodb.Table(db_client.table_names['simulations']).put_item(
        Item={
            'simulation_id': simulation_id,
            'agent_id': agent_config.get('id'),
            'timestamp': datetime.utcnow().isoformat(),
            'result': json.dumps(result)
        }
    )
    
    result['simulation_id'] = simulation_id
    return result


def lambda_handler(event, context):
    """
    Lambdaハンドラー（API Gateway経由で呼び出し可能）
    """
    try:
        # リクエストボディを取得
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        agent_config = body.get('agent_config')
        start_date = body.get('start_date')
        end_date = body.get('end_date')
        
        if not agent_config:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'agent_config is required'})
            }
        
        result = run_simulation(agent_config, start_date, end_date)
        
        if 'error' in result:
            return {
                'statusCode': 400,
                'body': json.dumps(result)
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

