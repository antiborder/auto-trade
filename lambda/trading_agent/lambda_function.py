"""
取引エージェントLambda関数
複数のエージェントを並列実行し、取引判断と注文実行を行う
"""
import json
import os
import sys
from datetime import datetime
from typing import Optional

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

import boto3
from dynamodb.client import DynamoDBClient
from agents.base_agent import BaseAgent
from agents.simple_agent import SimpleAgent
from agents.lstm_agent import LSTMAgent
from models.trading import PriceData, TradingDecision, Action
from traders.bybit_trader import BybitTrader

# DynamoDBクライアント
db_client = DynamoDBClient()

def create_agents(config: dict) -> dict[str, BaseAgent]:
    """設定からエージェントを作成"""
    agents = {}
    agents_config = config.get('agents', [])
    
    for agent_config in agents_config:
        agent_type = agent_config.get('type')
        agent_id = agent_config.get('id')
        
        if agent_type == 'SimpleMA':
            agents[agent_id] = SimpleAgent(
                agent_id=agent_id,
                trader_id=agent_config.get('trader_id'),
                short_window=agent_config.get('short_window', 5),
                long_window=agent_config.get('long_window', 20)
            )
        elif agent_type == 'LSTM':
            model_path = agent_config.get('model_path')
            if model_path:
                # S3からモデルを読み込む（実装が必要な場合は追加）
                agents[agent_id] = LSTMAgent(
                    agent_id=agent_id,
                    trader_id=agent_config.get('trader_id'),
                    model_path=model_path
                )
    
    return agents

def lambda_handler(event, context):
    """
    Lambdaハンドラー
    
    1. 最新の価格データを取得
    2. 各エージェントで判断
    3. 必要に応じて注文を実行
    4. 結果をDynamoDBに保存
    """
    try:
        # 設定を取得（環境変数またはEventBridgeペイロードから）
        config_str = os.getenv('TRADING_CONFIG', '{}')
        if event.get('config'):
            config_str = json.dumps(event['config'])
        config = json.loads(config_str) if config_str else {}
        
        # デフォルト設定（設定がない場合）
        if not config.get('agents'):
            config = {
                'agents': [
                    {
                        'id': 'simple-agent-1',
                        'type': 'SimpleMA',
                        'short_window': 5,
                        'long_window': 20
                    }
                ]
            }
        
        # Bybitから価格データを取得
        bybit_api_key = os.getenv('BYBIT_API_KEY')
        bybit_api_secret = os.getenv('BYBIT_API_SECRET')
        bybit_testnet = os.getenv('BYBIT_TESTNET', 'false').lower() == 'true'
        
        # Bybit traderを作成
        bybit_trader = BybitTrader(
            trader_id='bybit-trader-1',
            api_key=bybit_api_key,
            api_secret=bybit_api_secret,
            testnet=bybit_testnet
        )
        
        # 現在の価格を取得
        current_price = bybit_trader.get_current_price(symbol='BTCUSDT')
        if not current_price:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Failed to fetch price from Bybit'})
            }
        
        # 過去のK線データを取得（5分足、100件）
        historical_data = bybit_trader.get_klines(symbol='BTCUSDT', interval='5', limit=100)
        
        if not historical_data:
            # K線データが取得できない場合は、現在の価格のみを使用
            historical_data = [current_price]
        
        # エージェントを作成
        agents = create_agents(config)
        
        results = []
        
        # 各エージェントで判断
        for agent_id, agent in agents.items():
            try:
                decision = agent.decide(current_price, historical_data)
                
                # 判断結果をDynamoDBに保存
                db_client.save_decision(decision)
                
                results.append({
                    'agent_id': agent_id,
                    'action': decision.action.value,
                    'confidence': decision.confidence,
                    'price': decision.price,
                    'reason': decision.reason
                })
            except Exception as e:
                print(f"Error in agent {agent_id}: {str(e)}")
                results.append({
                    'agent_id': agent_id,
                    'error': str(e)
                })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Trading decisions completed',
                'timestamp': datetime.utcnow().isoformat(),
                'results': results
            })
        }
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
