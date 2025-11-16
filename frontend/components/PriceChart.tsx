'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface PriceChartProps {
  data: any[]
}

export default function PriceChart({ data }: PriceChartProps) {
  // まず元のタイムスタンプでソートしてから、表示用に変換
  const chartData = data
    .map(item => ({
      timestamp: item.timestamp, // 元のタイムスタンプを保持
      timestampDisplay: new Date(item.timestamp).toLocaleString(), // 表示用
      price: parseFloat(item.price)
    }))
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map(item => ({
      timestamp: item.timestampDisplay, // ソート後に表示用に変換
      price: item.price
    }))

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="timestamp" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="price" stroke="#8884d8" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  )
}


