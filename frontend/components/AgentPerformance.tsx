'use client'

interface AgentPerformanceProps {
  data: any[]
}

export default function AgentPerformance({ data }: AgentPerformanceProps) {
  return (
    <div className="space-y-4">
      {data.map((agent) => (
        <div key={agent.agent_id} className="border rounded p-4">
          <h3 className="font-semibold text-lg">{agent.agent_id}</h3>
          <div className="grid grid-cols-2 gap-2 mt-2">
            <div>
              <span className="text-gray-600">Total Profit:</span>
              <span className={`ml-2 font-bold ${agent.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${parseFloat(agent.total_profit).toFixed(2)}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Total Trades:</span>
              <span className="ml-2 font-bold">{agent.total_trades}</span>
            </div>
            <div>
              <span className="text-gray-600">Win Rate:</span>
              <span className="ml-2 font-bold">{(parseFloat(agent.win_rate) * 100).toFixed(2)}%</span>
            </div>
            <div>
              <span className="text-gray-600">Current Balance:</span>
              <span className="ml-2 font-bold">${parseFloat(agent.current_balance).toFixed(2)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}


