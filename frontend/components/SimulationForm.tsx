'use client'

import { useState, FormEvent } from 'react'

interface SimulationFormProps {
  onSubmit: (config: any) => void
  loading: boolean
}

export default function SimulationForm({ onSubmit, loading }: SimulationFormProps) {
  const [agentType, setAgentType] = useState('SimpleMA')
  const [agentId, setAgentId] = useState('')
  const [shortWindow, setShortWindow] = useState(5)
  const [longWindow, setLongWindow] = useState(20)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    
    const config: any = {
      agent_config: {
        id: agentId || `sim_${Date.now()}`,
        type: agentType,
      },
    }

    if (agentType === 'SimpleMA') {
      config.agent_config.short_window = shortWindow
      config.agent_config.long_window = longWindow
    }

    if (startDate) config.start_date = startDate
    if (endDate) config.end_date = endDate

    onSubmit(config)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 border rounded p-6">
      <h2 className="text-xl font-semibold mb-4">Simulation Configuration</h2>
      
      <div>
        <label className="block text-sm font-medium mb-2">Agent Type</label>
        <select
          value={agentType}
          onChange={(e) => setAgentType(e.target.value)}
          className="w-full border rounded p-2"
        >
          <option value="SimpleMA">Simple Moving Average</option>
          <option value="LSTM">LSTM Model</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Agent ID</label>
        <input
          type="text"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          placeholder="Optional"
          className="w-full border rounded p-2"
        />
      </div>

      {agentType === 'SimpleMA' && (
        <>
          <div>
            <label className="block text-sm font-medium mb-2">Short Window</label>
            <input
              type="number"
              value={shortWindow}
              onChange={(e) => setShortWindow(parseInt(e.target.value))}
              className="w-full border rounded p-2"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Long Window</label>
            <input
              type="number"
              value={longWindow}
              onChange={(e) => setLongWindow(parseInt(e.target.value))}
              className="w-full border rounded p-2"
            />
          </div>
        </>
      )}

      <div>
        <label className="block text-sm font-medium mb-2">Start Date (Optional)</label>
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="w-full border rounded p-2"
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">End Date (Optional)</label>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="w-full border rounded p-2"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-500 text-white rounded p-2 hover:bg-blue-600 disabled:bg-gray-400"
      >
        {loading ? 'Running Simulation...' : 'Run Simulation'}
      </button>
    </form>
  )
}

