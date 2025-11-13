/**
 * DynamoDBアクセス用Server Actions
 */
'use server'

import { DynamoDBClient } from '@aws-sdk/client-dynamodb'
import { DynamoDBDocumentClient, ScanCommand, QueryCommand, GetItemCommand } from '@aws-sdk/lib-dynamodb'

const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'ap-northeast-1'
})

const docClient = DynamoDBDocumentClient.from(client)

const TABLES = {
  prices: process.env.PRICES_TABLE || 'btc-prices',
  decisions: process.env.DECISIONS_TABLE || 'trading-decisions',
  orders: process.env.ORDERS_TABLE || 'trading-orders',
  performance: process.env.PERFORMANCE_TABLE || 'agent-performance',
  simulations: process.env.SIMULATIONS_TABLE || 'simulations'
}

export async function getRecentPrices(limit: number = 100) {
  try {
    const command = new ScanCommand({
      TableName: TABLES.prices,
      Limit: limit
    })
    
    const response = await docClient.send(command)
    return response.Items || []
  } catch (error) {
    console.error('Error fetching prices:', error)
    return []
  }
}

export async function getAgentDecisions(agentId: string, limit: number = 100) {
  try {
    const command = new QueryCommand({
      TableName: TABLES.decisions,
      KeyConditionExpression: 'agent_id = :agentId',
      ExpressionAttributeValues: {
        ':agentId': agentId
      },
      Limit: limit,
      ScanIndexForward: false  // 新しい順
    })
    
    const response = await docClient.send(command)
    return response.Items || []
  } catch (error) {
    console.error('Error fetching decisions:', error)
    return []
  }
}

export async function getAgentOrders(agentId: string, limit: number = 100) {
  try {
    const command = new QueryCommand({
      TableName: TABLES.orders,
      IndexName: 'agent-timestamp-index',
      KeyConditionExpression: 'agent_id = :agentId',
      ExpressionAttributeValues: {
        ':agentId': agentId
      },
      Limit: limit,
      ScanIndexForward: false
    })
    
    const response = await docClient.send(command)
    return response.Items || []
  } catch (error) {
    console.error('Error fetching orders:', error)
    return []
  }
}

export async function getAgentPerformance(agentId: string) {
  try {
    const command = new GetItemCommand({
      TableName: TABLES.performance,
      Key: {
        agent_id: agentId
      }
    })
    
    const response = await docClient.send(command)
    return response.Item || null
  } catch (error) {
    console.error('Error fetching performance:', error)
    return null
  }
}

export async function getAllAgentsPerformance() {
  try {
    const command = new ScanCommand({
      TableName: TABLES.performance
    })
    
    const response = await docClient.send(command)
    return response.Items || []
  } catch (error) {
    console.error('Error fetching all performance:', error)
    return []
  }
}


