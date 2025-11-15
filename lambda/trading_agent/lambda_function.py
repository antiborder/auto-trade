"""
取引エージェントLambda関数
複数のエージェントを並列実行し、取引判断と注文実行を行う
"""
import json
import os
import sys
from datetime import datetime
from typing import Optional

# 共通モジュールのパスを追加（Dockerコンテナ内ではshared/が同じディレクトリにコピーされる）
# sharedモジュールをインポートするために、親ディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

import boto3
from shared.dynamodb.client import DynamoDBClient
from shared.agents.base_agent import BaseAgent
from shared.agents.simple_agent import SimpleAgent
from shared.agents.lstm_agent import LSTMAgent
from shared.models.trading import PriceData, TradingDecision, Action, OrderStatus
from shared.traders.bybit_trader import BybitTrader

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
        
        # 残高を取得して保存（各エージェントの判断前に一度だけ実行）
        try:
            balance = bybit_trader.get_balance()
            print(f"Balance response from get_balance: {balance}")
            if "error" not in balance:
                try:
                    coin_list = balance.get("list", [])
                    print(f"Coin list from balance: {coin_list}")
                    if coin_list:
                        coins = coin_list[0].get("coin", [])
                        usdt_balance = 0.0
                        btc_balance = 0.0
                        
                        for coin in coins:
                            coin_type = coin.get("coin", "")
                            # UNIFIEDアカウントではavailableToWithdrawが空の場合があるので、
                            # walletBalanceまたはequityを使用
                            available_to_withdraw = coin.get("availableToWithdraw", "")
                            wallet_balance = coin.get("walletBalance", "")
                            equity = coin.get("equity", "")
                            
                            # 空文字列でない最初の値を使用
                            available_str = available_to_withdraw or wallet_balance or equity or "0"
                            available = float(available_str) if available_str else 0.0
                            
                            print(f"Coin: {coin_type}, availableToWithdraw: {available_to_withdraw}, walletBalance: {wallet_balance}, equity: {equity}, final: {available}")
                            
                            if coin_type == "USDT":
                                usdt_balance = available
                            elif coin_type == "BTC":
                                btc_balance = available
                        
                        # 残高をDynamoDBに保存
                        try:
                            db_client.put_balance(
                                timestamp=datetime.utcnow(),
                                usdt_balance=usdt_balance,
                                btc_balance=btc_balance
                            )
                            print(f"Balance saved: USDT={usdt_balance:.2f}, BTC={btc_balance:.6f}")
                        except Exception as e:
                            print(f"Failed to save balance to DynamoDB: {str(e)}")
                except Exception as e:
                    print(f"Error parsing balance: {str(e)}")
            else:
                print(f"Failed to get balance: {balance.get('error')}")
        except Exception as e:
            print(f"Error getting balance: {str(e)}")
        
        results = []
        
        # 各エージェントで判断
        for agent_id, agent in agents.items():
            try:
                decision = agent.decide(current_price, historical_data)
                
                # 判断結果をDynamoDBに保存
                decision_dict = {
                    'agent_id': decision.agent_id,
                    'timestamp': decision.timestamp,
                    'action': decision.action.value,  # Action enumを文字列に変換
                    'confidence': decision.confidence,
                    'price': decision.price,
                    'reason': decision.reason
                }
                if decision.model_prediction is not None:
                    decision_dict['model_prediction'] = decision.model_prediction
                db_client.put_decision(decision_dict)
                
                # 注文実行（HOLD以外で、信頼度が閾値以上の場合）
                order = None
                min_confidence = config.get('min_confidence', 0.5)  # デフォルト信頼度閾値
                order_amount_btc = config.get('order_amount_btc', 0.0001)  # デフォルト注文数量（BTC）
                
                if decision.action != Action.HOLD and decision.confidence >= min_confidence:
                    # 残高チェック（注文実行前に再取得）
                    balance = bybit_trader.get_balance()
                    can_trade = False
                    insufficient_funds_reason = None
                    
                    if "error" in balance:
                        print(f"Failed to get balance: {balance.get('error')}")
                        insufficient_funds_reason = f"Balance check failed: {balance.get('error')}"
                    else:
                        # Bybit APIの残高レスポンス構造を解析
                        # result.list[0].coin[] に各コインの残高が含まれる
                        try:
                            coin_list = balance.get("result", {}).get("list", [])
                            if coin_list:
                                coins = coin_list[0].get("coin", [])
                                usdt_balance = 0.0
                                btc_balance = 0.0
                                
                                for coin in coins:
                                    coin_type = coin.get("coin", "")
                                    available = float(coin.get("availableToWithdraw", "0") or "0")
                                    
                                    if coin_type == "USDT":
                                        usdt_balance = available
                                    elif coin_type == "BTC":
                                        btc_balance = available
                                
                                if decision.action == Action.BUY:
                                    # 買い注文: USDT残高を確認
                                    order_cost_usdt = order_amount_btc * current_price.price
                                    # 手数料を考慮（約0.1%）
                                    total_cost = order_cost_usdt * 1.001
                                    
                                    if usdt_balance >= total_cost:
                                        can_trade = True
                                    else:
                                        insufficient_funds_reason = f"Insufficient USDT balance: {usdt_balance:.2f} USDT < {total_cost:.2f} USDT required"
                                        
                                elif decision.action == Action.SELL:
                                    # 売り注文: BTC保有量を確認
                                    if btc_balance >= order_amount_btc:
                                        can_trade = True
                                    else:
                                        insufficient_funds_reason = f"Insufficient BTC balance: {btc_balance:.6f} BTC < {order_amount_btc:.6f} BTC required"
                            else:
                                insufficient_funds_reason = "No balance data available"
                        except Exception as e:
                            print(f"Error parsing balance: {str(e)}")
                            insufficient_funds_reason = f"Error parsing balance: {str(e)}"
                    
                    if not can_trade:
                        print(f"Skipping order due to insufficient funds: {insufficient_funds_reason}")
                        # 残高不足を記録（注文として記録しないが、ログに残す）
                        continue
                    
                    try:
                        # 注文を実行（成行注文）
                        order = bybit_trader.execute_order(
                            action=decision.action,
                            amount=order_amount_btc,
                            price=None  # Noneで成行注文
                        )
                        
                        # エージェントIDを設定（Orderはdataclassなので、新しいインスタンスを作成）
                        from dataclasses import replace
                        order = replace(order, agent_id=agent_id)
                        
                        # 注文結果をDynamoDBに保存
                        order_dict = {
                            'order_id': order.order_id,
                            'agent_id': order.agent_id,
                            'timestamp': order.timestamp,
                            'action': order.action.value,
                            'amount': order.amount,
                            'price': order.price,
                            'status': order.status.value,
                            'trader_id': order.trader_id
                        }
                        if order.execution_price is not None:
                            order_dict['execution_price'] = order.execution_price
                        if order.execution_timestamp is not None:
                            order_dict['execution_timestamp'] = order.execution_timestamp
                        if order.error_message is not None:
                            order_dict['error_message'] = order.error_message
                        
                        db_client.put_order(order_dict)
                        print(f"Order executed: {order.order_id}, Status: {order.status.value}")
                    except Exception as e:
                        print(f"Error executing order for agent {agent_id}: {str(e)}")
                        # 注文失敗も記録
                        failed_order = {
                            'order_id': f"{agent_id}_{datetime.utcnow().isoformat()}",
                            'agent_id': agent_id,
                            'timestamp': datetime.utcnow(),
                            'action': decision.action.value,
                            'amount': order_amount_btc,
                            'price': decision.price,
                            'status': OrderStatus.FAILED.value,
                            'trader_id': bybit_trader.trader_id,
                            'error_message': str(e)
                        }
                        db_client.put_order(failed_order)
                
                result_item = {
                    'agent_id': agent_id,
                    'action': decision.action.value,
                    'confidence': decision.confidence,
                    'price': decision.price,
                    'reason': decision.reason
                }
                if order:
                    result_item['order_id'] = order.order_id
                    result_item['order_status'] = order.status.value
                results.append(result_item)
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
