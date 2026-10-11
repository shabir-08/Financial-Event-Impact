import React, { useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine
} from 'recharts';
import { History, TrendingDown, Info } from 'lucide-react';
import { HistoricalObservationPoint } from '../../types/blackSwan';

interface MarketImpactChartProps {
  assetSymbol?: string;
  assetName: string;
  observations?: HistoricalObservationPoint[];
  windowName?: string;
}

export const MarketImpactChart: React.FC<MarketImpactChartProps> = ({
  assetSymbol,
  assetName,
  observations,
  windowName,
}) => {
  const [selectedWindow, setSelectedWindow] = useState<'around_event' | '1m' | '3m'>('around_event');

  if (!observations || observations.length === 0) {
    return (
      <div className="p-4 bg-gray-50/70 border border-gray-200 rounded-lg text-center space-y-1">
        <p className="text-xs font-semibold text-gray-700">
          Historical observations are unavailable for this asset.
        </p>
        <p className="text-[11px] text-gray-400">
          No historical benchmark shock observations found for {assetSymbol || assetName}.
        </p>
      </div>
    );
  }

  // Filter observations based on selected window
  const chartData = observations.map(pt => ({
    date: pt.date,
    price: pt.value,
    benchmark: pt.benchmarkValue,
    period: pt.eventPeriod,
  }));

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs space-y-3">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-gray-100">
        <div>
          <div className="flex items-center space-x-1.5 text-xs font-extrabold text-gray-950">
            <History size={14} className="text-blue-600" />
            <span>Historical Asset Behaviour</span>
          </div>
          <p className="text-[10px] text-gray-400 font-medium">
            {windowName || 'Empirical price action around benchmark energy shock'}
          </p>
        </div>

        {/* Window Selector */}
        <div className="flex items-center space-x-1 bg-gray-100 p-0.5 rounded text-[10px] font-bold">
          <button
            onClick={() => setSelectedWindow('around_event')}
            className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
              selectedWindow === 'around_event'
                ? 'bg-white text-blue-700 shadow-2xs'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            Event Window
          </button>
          <button
            onClick={() => setSelectedWindow('1m')}
            className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
              selectedWindow === '1m'
                ? 'bg-white text-blue-700 shadow-2xs'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            1M
          </button>
          <button
            onClick={() => setSelectedWindow('3m')}
            className={`px-2 py-0.5 rounded transition-all cursor-pointer ${
              selectedWindow === '3m'
                ? 'bg-white text-blue-700 shadow-2xs'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            3M
          </button>
        </div>
      </div>

      {/* Chart */}
      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#64748B' }}
              axisLine={{ stroke: '#E2E8F0' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#64748B' }}
              axisLine={{ stroke: '#E2E8F0' }}
              tickLine={false}
              domain={['auto', 'auto']}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  return (
                    <div className="bg-gray-900 text-white px-2.5 py-1.5 rounded shadow-lg text-[11px] font-mono border border-gray-700">
                      <div className="font-bold text-blue-300">{label}</div>
                      <div>Asset: ₹{payload[0].value}</div>
                      {payload[1] && <div className="text-gray-400">NIFTY: {payload[1].value}</div>}
                    </div>
                  );
                }
                return null;
              }}
            />
            <ReferenceLine x="Event" stroke="#EF4444" strokeDasharray="3 3" label={{ value: 'Shock Date', fill: '#EF4444', fontSize: 9 }} />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#2563EB"
              strokeWidth={2}
              dot={{ r: 3, fill: '#2563EB' }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-between text-[10px] text-gray-400 pt-1 border-t border-gray-100">
        <span className="flex items-center space-x-1">
          <span className="w-2 h-2 rounded-full bg-blue-600"></span>
          <span>{assetSymbol || assetName} (demo series)</span>
        </span>
        <span className="italic font-mono">Illustrative demo values, not market data</span>
      </div>
    </div>
  );
};
