"""
取引エージェントLambda関数
価格データを取得し、複数のエージェントで判断を行い、必要に応じて注文を実行
"""
import json
import os
import sys
from datetime import datetime
from typing import List

# 共通モジュールのパスを追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))
from dynamodb.client import DynamoDBClient
from agents.base_agent import BaseAgent
from agents.simple_agent import SimpleAgent
from agents.lstm_agent import LSTMAgent
from traders.base_trader import BaseTrader
from traders.rest_trader import RESTTrader
from models.trading import PriceData, Action


def create_agents(config: dict) -> List[BaseAgent]:
    """設定に基づいてエージェントを作成"""
    agents = []
    
    for agent_config in config.get('agents', []):
        agent_type = agent_config.get('type')
        agent_id = agent_config.get('id')
        trader_id = agent_config.get('trader_id')
        
        if agent_type == 'SimpleMA':
            agent = SimpleAgent(
                agent_id=agent_id,
                trader_id=trader_id,
                short_window=agent_config.get('short_window', 5),
                long_window=agent_config.get('long_window', 20)
            )
        elif agent_type == 'LSTM':
            agent = LSTMAgent(
                agent_id=agent_id,
                trader_id=trader_id,
                model_path=agent_config.get('model_path')
            )
        else:
            continue
        
        agents.append(agent)
    
    return agents


def create_traders(config: dict) -> dict[str, BaseTrader]:
    """設定に基づいてトレーダーを作成"""
    traders = {}
    
    for trader_config in config.get('traders', []):
        trader_id = trader_config.get('id')
        trader_type = trader_config.get('type')
        
        if trader_type == 'REST':
            trader = RESTTrader(
                trader_id=trader_id,
                api_endpoint=trader_config.get('api_endpoint'),
                api_key=trader_config.get('api_key'),
                api_secret=trader_config.get('api_secret')
            )
            traders[trader_id] = trader
    
    return traders


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
        config = json.loads(config_str)
        
        # DynamoDBクライアント
        db_client = DynamoDBClient()
        
        # 最新の価格データを取得
        recent_prices = db_client.get_recent_prices(limit=100)
        if not recent_prices:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No price data available'})
            }
        
        # 最新価格
        latest_price_data = recent_prices[-1]
        current_price = PriceData(
            timestamp=datetime.fromisoformat(latest_price_data['timestamp']) if isinstance(latest_price_data['timestamp'], str) else latest_price_data['timestamp'],
            price=float(latest_price_data['price']),
            volume=latest_price_data.get('volume_24h'),
            high=latest_price_data.get('high'),
            low=latest_price_data.get('low')
        )
        
        # 過去データをPriceDataオブジェクトに変換
        historical_data = []
        for p in recent_prices:
            historical_data.append(PriceData(
                timestamp=datetime.fromisoformat(p['timestamp']) if isinstance(p['timestamp'], str) else p['timestamp'],
                price=float(p['price']),
                volume=p.get('volume_24h'),
                high=p.get('high'),
                low=p.get('low')
            ))
        
        # エージェントとトレーダーを作成
        agents = create_agents(config)
        traders = create_traders(config)
        
        results = []
        
        # 各エージェントで判断
        for agent in agents:
            try:
                # 判断実行
                decision = agent.decide(current_price, historical_data)
                
                # 判断をDynamoDBに保存
                decision_dict = {
                    'agent_id': decision.agent_id,
                    'timestamp': decision.timestamp,
                    'action': decision.action.value,
                    'confidence': decision.confidence,
                    'price': decision.price,
                    'reason': decision.reason,
                    'model_prediction': decision.model_prediction
                }
                db_client.put_decision(decision_dict)
                
                # 買い/売りの場合、注文を実行
                if decision.action != Action.HOLD and agent.trader_id:
                    trader = traders.get(agent.trader_id)
                    if trader:
                        # 注文数量を計算（簡易版: 固定金額またはパーセンテージ）
                        order_amount = config.get('default_order_amount', 0.001)  # デフォルト0.001 BTC
                        
                        order = trader.execute_order(
                            action=decision.action,
                            amount=order_amount,
                            price=decision.price
                        )
                        
                        # agent_idを設定
                        order.agent_id = decision.agent_id
                        
                        # 注文をDynamoDBに保存
                        order_dict = {
                            'order_id': order.order_id,
                            'agent_id': order.agent_id,
                            'action': order.action.value,
                            'amount': order.amount,
                            'price': order.price,
                            'timestamp': order.timestamp,
                            'status': order.status.value,
                            'trader_id': order.trader_id,
                            'execution_price': order.execution_price,
                            'execution_timestamp': order.execution_timestamp,
                            'error_message': order.error_message
                        }
                        db_client.put_order(order_dict)
                        
                        results.append({
                            'agent_id': agent.agent_id,
                            'decision': decision_dict,
                            'order': order_dict
                        })
                    else:
                        results.append({
                            'agent_id': agent.agent_id,
                            'decision': decision_dict,
                            'order': None,
                            'error': f'Trader {agent.trader_id} not found'
                        })
                else:
                    results.append({
                        'agent_id': agent.agent_id,
                        'decision': decision_dict,
                        'order': None
                    })
            except Exception as e:
                print(f"Error processing agent {agent.agent_id}: {e}")
                results.append({
                    'agent_id': agent.agent_id,
                    'error': str(e)
                })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Trading agents processed',
                'timestamp': datetime.utcnow().isoformat(),
                'results': results
            })
        }
    except Exception as e:
        print(f"Error in trading_agent: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


