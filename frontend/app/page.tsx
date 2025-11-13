'use client'

import { useEffect, useState } from 'react'
import { getRecentPrices, getAllAgentsPerformance } from '../server-actions/dynamodb'
import PriceChart from '../components/PriceChart'
import AgentPerformance from '../components/AgentPerformance'

export default function Home() {
  const [prices, setPrices] = useState<any[]>([])
  const [performance, setPerformance] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      const [priceData, perfData] = await Promise.all([
        getRecentPrices(100),
        getAllAgentsPerformance()
      ])
      setPrices(priceData)
      setPerformance(perfData)
      setLoading(false)
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
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h2 className="text-2xl font-semibold mb-4">Price History</h2>
          <PriceChart data={prices} />
        </div>
        
        <div>
          <h2 className="text-2xl font-semibold mb-4">Agent Performance</h2>
          <AgentPerformance data={performance} />
        </div>
      </div>
    </div>
  )
}


