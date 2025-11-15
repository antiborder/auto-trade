'use client'

import { useEffect, useState } from 'react'
import { getRecentPrices, getAllAgentsPerformance, getRecentBalances } from '../server-actions/dynamodb'
import PriceChart from '../components/PriceChart'
import AgentPerformance from '../components/AgentPerformance'
import BalanceChart from '../components/BalanceChart'

export default function Home() {
  const [prices, setPrices] = useState<any[]>([])
  const [performance, setPerformance] = useState<any[]>([])
  const [balances, setBalances] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      setError(null)
      try {
        const [priceData, perfData, balanceData] = await Promise.all([
          getRecentPrices(100),
          getAllAgentsPerformance(),
          getRecentBalances(100)
        ])
        setPrices(priceData)
        setPerformance(perfData)
        setBalances(balanceData)
        console.log('Fetched data:', { prices: priceData.length, performance: perfData.length, balances: balanceData.length })
      } catch (err: any) {
        console.error('Error fetching data:', err)
        setError(err.message || 'Failed to fetch data')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 60000) // 1分ごとに更新

    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return <div className="container mx-auto p-4">Loading...</div>
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">Bitcoin Auto Trading Dashboard</h1>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          <strong>Error:</strong> {error}
          <div className="mt-2 text-sm">
            <p>考えられる原因:</p>
            <ul className="list-disc list-inside">
              <li>AWS認証情報が設定されていない（AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY）</li>
              <li>DynamoDBテーブルが存在しない、またはアクセス権限がない</li>
              <li>テーブル名が正しくない</li>
            </ul>
          </div>
        </div>
      )}
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div>
          <h2 className="text-2xl font-semibold mb-4">Price History</h2>
          {prices.length === 0 && !error ? (
            <div className="text-gray-500">価格データがありません</div>
          ) : (
            <PriceChart data={prices} />
          )}
        </div>
        
        <div>
          <h2 className="text-2xl font-semibold mb-4">Agent Performance</h2>
          {performance.length === 0 && !error ? (
            <div className="text-gray-500">パフォーマンスデータがありません</div>
          ) : (
            <AgentPerformance data={performance} />
          )}
        </div>
      </div>
      
      <div className="mt-6">
        <h2 className="text-2xl font-semibold mb-4">Balance History</h2>
        {balances.length === 0 && !error ? (
          <div className="text-gray-500">残高データがありません</div>
        ) : (
          <BalanceChart data={balances} />
        )}
      </div>
    </div>
  )
}


