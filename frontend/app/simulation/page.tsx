'use client'

import { useState } from 'react'
import SimulationForm from '../../components/SimulationForm'
import SimulationResults from '../../components/SimulationResults'

export default function SimulationPage() {
  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const handleSimulation = async (config: any) => {
    setLoading(true)
    try {
      // APIエンドポイントを呼び出し
      const response = await fetch('/api/simulation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(config),
      })
      
      const data = await response.json()
      setResults(data)
    } catch (error) {
      console.error('Simulation error:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-6">Trading Simulation</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <SimulationForm onSubmit={handleSimulation} loading={loading} />
        </div>
        
        <div>
          {results && <SimulationResults results={results} />}
        </div>
      </div>
    </div>
  )
}

