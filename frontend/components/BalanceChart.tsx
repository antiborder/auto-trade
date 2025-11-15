'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

interface BalanceChartProps {
  data: any[]
}

export default function BalanceChart({ data }: BalanceChartProps) {
  if (!data || data.length === 0) {
    return <div className="text-gray-500">残高データがありません</div>
  }

  const chartData = data
    .map(item => ({
      timestamp: new Date(item.timestamp).toLocaleString(),
      usdt: parseFloat(item.usdt_balance || 0),
      btc: parseFloat(item.btc_balance || 0)
    }))
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

  // 最新の残高を取得
  const latest = chartData[chartData.length - 1]

  return (
    <div>
      {latest && (
        <div className="mb-4 grid grid-cols-2 gap-4">
          <div className="bg-blue-50 p-4 rounded-lg">
            <div className="text-sm text-gray-600">USDT Balance</div>
            <div className="text-2xl font-bold text-blue-600">
              ${latest.usdt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </div>
          <div className="bg-orange-50 p-4 rounded-lg">
            <div className="text-sm text-gray-600">BTC Balance</div>
            <div className="text-2xl font-bold text-orange-600">
              {latest.btc.toFixed(6)} BTC
            </div>
          </div>
        </div>
      )}
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" />
          <YAxis yAxisId="left" />
          <YAxis yAxisId="right" orientation="right" />
          <Tooltip />
          <Legend />
          <Line 
            yAxisId="left"
            type="monotone" 
            dataKey="usdt" 
            stroke="#3b82f6" 
            strokeWidth={2}
            name="USDT Balance"
            dot={false}
          />
          <Line 
            yAxisId="right"
            type="monotone" 
            dataKey="btc" 
            stroke="#f97316" 
            strokeWidth={2}
            name="BTC Balance"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

