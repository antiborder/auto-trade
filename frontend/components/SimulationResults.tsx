'client'

interface SimulationResultsProps {
  results: any
}

export default function SimulationResults({ results }: SimulationResultsProps) {
  if (!results) return null

  return (
    <div className="border rounded p-6">
      <h2 className="text-xl font-semibold mb-4">Simulation Results</h2>
      
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-gray-600">Initial Balance:</span>
            <span className="ml-2 font-bold">${results.initial_balance?.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-gray-600">Final Value:</span>
            <span className={`ml-2 font-bold ${results.final_value >= results.initial_balance ? 'text-green-600' : 'text-red-600'}`}>
              ${results.final_value?.toFixed(2)}
            </span>
          </div>
          <div>
            <span className="text-gray-600">Total Profit:</span>
            <span className={`ml-2 font-bold ${results.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${results.total_profit?.toFixed(2)}
            </span>
          </div>
          <div>
            <span className="text-gray-600">Profit %:</span>
            <span className={`ml-2 font-bold ${results.profit_percentage >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {results.profit_percentage?.toFixed(2)}%
            </span>
          </div>
          <div>
            <span className="text-gray-600">Total Trades:</span>
            <span className="ml-2 font-bold">{results.total_trades}</span>
          </div>
          <div>
            <span className="text-gray-600">Buy Trades:</span>
            <span className="ml-2 font-bold">{results.buy_trades}</span>
          </div>
          <div>
            <span className="text-gray-600">Sell Trades:</span>
            <span className="ml-2 font-bold">{results.sell_trades}</span>
          </div>
        </div>

        {results.simulation_id && (
          <div className="mt-4 text-sm text-gray-500">
            Simulation ID: {results.simulation_id}
          </div>
        )}
      </div>
    </div>
  )
}

