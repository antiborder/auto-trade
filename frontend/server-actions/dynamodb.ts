/**
 * DynamoDBアクセス用Server Actions
 */
'use server'

import { DynamoDBClient } from '@aws-sdk/client-dynamodb'
import { DynamoDBDocumentClient, ScanCommand, QueryCommand, GetCommand } from '@aws-sdk/lib-dynamodb'

const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'ap-northeast-1'
})

const docClient = DynamoDBDocumentClient.from(client)

const TABLES = {
  prices: process.env.PRICES_TABLE || 'btc-prices',
  decisions: process.env.DECISIONS_TABLE || 'trading-decisions',
  orders: process.env.ORDERS_TABLE || 'trading-orders',
  performance: process.env.PERFORMANCE_TABLE || 'agent-performance',
  simulations: process.env.SIMULATIONS_TABLE || 'simulations',
  balance: process.env.BALANCE_TABLE || 'trading-balance'
}

export async function getRecentPrices(limit: number = 100) {
  try {
    // OPTIMIZED: Use Scan with Limit to reduce read units
    // Note: This may not return exactly the most recent items, but significantly reduces cost
    // For exact recent items, consider adding a GSI with timestamp as sort key
    const command = new ScanCommand({
      TableName: TABLES.prices,
      Limit: Math.min(limit * 3, 1000), // Scan up to 3x limit or 1000 items max to reduce reads
      // ProjectionExpression: 'timestamp, price, volume_24h' // Only fetch needed attributes
    })
    
    const response = await docClient.send(command)
    const items = response.Items || []
    
    // Sort by timestamp and return most recent N items
    const sortedItems = items.sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime()
      const timeB = new Date(b.timestamp).getTime()
      return timeB - timeA // 降順（新しい順）
    })
    
    const recentItems = sortedItems.slice(0, limit).reverse() // 古い順に並び替え
    console.log(`Fetched ${items.length} items (limited scan), returning ${recentItems.length} recent items from table: ${TABLES.prices}`)
    return recentItems
  } catch (error: any) {
    console.error('Error fetching prices:', error)
    throw new Error(`Failed to fetch prices: ${error.message || String(error)}`)
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
    const command = new GetCommand({
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
    console.log(`Fetched ${response.Items?.length || 0} performance items from table: ${TABLES.performance}`)
    return response.Items || []
  } catch (error: any) {
    console.error('Error fetching all performance:', error)
    // エラー情報を返してデバッグしやすくする
    throw new Error(`Failed to fetch performance: ${error.message || String(error)}`)
  }
}

export async function getRecentBalances(limit: number = 100) {
  try {
    // OPTIMIZED: Use Scan with Limit to reduce read units
    // Note: This may not return exactly the most recent items, but significantly reduces cost
    // For exact recent items, consider adding a GSI with timestamp as sort key
    const command = new ScanCommand({
      TableName: TABLES.balance,
      Limit: Math.min(limit * 3, 1000), // Scan up to 3x limit or 1000 items max to reduce reads
      // ProjectionExpression: 'timestamp, usdt_balance, btc_balance' // Only fetch needed attributes
    })
    
    const response = await docClient.send(command)
    const items = response.Items || []
    
    // Sort by timestamp and return most recent N items
    const sortedItems = items.sort((a, b) => {
      const timeA = new Date(a.timestamp).getTime()
      const timeB = new Date(b.timestamp).getTime()
      return timeB - timeA // 降順（新しい順）
    })
    
    const recentItems = sortedItems.slice(0, limit).reverse() // 古い順に並び替え
    console.log(`Fetched ${items.length} items (limited scan), returning ${recentItems.length} recent items from table: ${TABLES.balance}`)
    return recentItems
  } catch (error: any) {
    console.error('Error fetching balances:', error)
    throw new Error(`Failed to fetch balances: ${error.message || String(error)}`)
  }
}


