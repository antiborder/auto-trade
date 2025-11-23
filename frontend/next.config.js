/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    AWS_REGION: process.env.AWS_REGION || 'ap-northeast-1',
    PRICES_TABLE: process.env.PRICES_TABLE || 'btc-prices',
    DECISIONS_TABLE: process.env.DECISIONS_TABLE || 'trading-decisions',
    ORDERS_TABLE: process.env.ORDERS_TABLE || 'trading-orders',
    PERFORMANCE_TABLE: process.env.PERFORMANCE_TABLE || 'agent-performance',
    SIMULATIONS_TABLE: process.env.SIMULATIONS_TABLE || 'simulations',
    BALANCE_TABLE: process.env.BALANCE_TABLE || 'trading-balance',
  },
}

module.exports = nextConfig


