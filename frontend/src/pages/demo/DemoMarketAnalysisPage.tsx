import React, { useState } from 'react';
import { DemoDataBanner } from '../../components/layout/DemoDataBanner';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
  CartesianGrid
} from 'recharts';
import { Header } from '../../components/layout/Header';
import { MarketFilters, FilterState } from '../../components/market/MarketFilters';
import { useApp } from '../../context/AppContext';
import { DEMO_MARKET_DATA } from '../../services/demoData';

export const DemoMarketAnalysisPage: React.FC = () => {
  const { selectedEventId } = useApp();
  const [selectedAssetId, setSelectedAssetId] = useState<string>('ast_indigo');
  const [timeframe, setTimeframe] = useState<'1M' | '3M' | '6M' | 'Around event'>('Around event');
  const [filters, setFilters] = useState<FilterState>({
    regions: [],
    domains: [],
    timeframe: '',
  });

  const marketData = DEMO_MARKET_DATA;
  const currentAsset = marketData.assets.find((a) => a.assetId === selectedAssetId) || marketData.assets[0];
  const chartPoints = marketData.priceHistory[selectedAssetId] || [];
  const returnsList = marketData.returns[selectedAssetId] || [];

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB]">
      <Header
        title={marketData.eventHeadline}
        tag="EVENT › MARKET ANALYSIS"
        subtitle="Historical observations for assets linked to this event. These are past price movements, not predictions."
        showActions={true}
      />
      <DemoDataBanner reason="Demo mode is on (switch it off in Settings to see live backend data)." />

      {/* Advisory Banner matching reference */}
      <div className="bg-amber-50/70 border-b border-amber-200/80 px-6 py-2 text-xs text-amber-800 text-center font-medium">
        Layout inspiration only. Every value and date on this image is an illustrative observation; the real page renders backend market-data responses.
      </div>

      <div className="p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* Asset Selector Tabs & Filter Button */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-4">
          <div className="flex items-center space-x-2 overflow-x-auto text-xs">
            {marketData.assets.map((asset) => {
              const isSelected = asset.assetId === selectedAssetId;
              return (
                <button
                  key={asset.assetId}
                  onClick={() => setSelectedAssetId(asset.assetId)}
                  className={`px-3 py-1.5 rounded-lg border font-semibold flex items-center space-x-2 transition-all ${
                    isSelected
                      ? 'border-blue-600 bg-blue-50/60 text-blue-700 shadow-2xs'
                      : 'border-gray-200 bg-white hover:bg-gray-50 text-gray-700'
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      asset.availability === 'Available'
                        ? 'bg-blue-600'
                        : asset.availability === 'Partial'
                        ? 'bg-amber-500'
                        : 'bg-red-500'
                    }`}
                  />
                  <span>{asset.name.split(' ')[0]}</span>
                  <span className="text-[11px] text-gray-400 font-normal">
                    — {asset.availability}
                  </span>
                </button>
              );
            })}
          </div>

          <MarketFilters
            filters={filters}
            onChange={setFilters}
            onReset={() => setFilters({ regions: [], domains: [], timeframe: '' })}
          />
        </div>

        {/* SECTION A: ASSET SUMMARY */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs">
          <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
            A · ASSET SUMMARY
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs">
            {/* Column 1 */}
            <div className="space-y-3">
              <div>
                <span className="text-[11px] text-gray-400 block">Asset name</span>
                <span className="font-bold text-gray-900">{currentAsset.name}</span>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 block">Exchange / market</span>
                <span className="font-bold text-gray-900">{currentAsset.exchange}</span>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 block">Latest available observation</span>
                <span className="font-medium text-gray-900">{currentAsset.latestObservation}</span>
              </div>
            </div>

            {/* Column 2 */}
            <div className="space-y-3">
              <div>
                <span className="text-[11px] text-gray-400 block">Symbol</span>
                <span className="font-mono font-bold text-gray-900">{currentAsset.symbol}</span>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 block">Data provider</span>
                <span className="font-medium text-gray-900">{currentAsset.dataProvider}</span>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 block">Data freshness</span>
                <div className="flex items-center space-x-1.5">
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-50 text-amber-700 font-bold border border-amber-200">
                    Not live
                  </span>
                  <span className="text-gray-700 font-medium">last close, 2 days ago</span>
                </div>
              </div>
            </div>

            {/* Column 3 */}
            <div className="space-y-3">
              <div>
                <span className="text-[11px] text-gray-400 block">Asset type</span>
                <span className="font-bold text-gray-900">{currentAsset.assetType}</span>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 block">Currency</span>
                <span className="font-mono font-bold text-gray-900">{currentAsset.currency}</span>
              </div>
              <div>
                <span className="text-[11px] text-gray-400 block">Data availability</span>
                <div className="flex items-center space-x-1.5">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                      currentAsset.availability === 'Available'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : currentAsset.availability === 'Partial'
                        ? 'bg-amber-50 text-amber-700 border-amber-200'
                        : 'bg-red-50 text-red-700 border-red-200'
                    }`}
                  >
                    {currentAsset.availability}
                  </span>
                  <span className="text-gray-600 truncate">{currentAsset.availabilityNote}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* SECTION B: HISTORICAL PRICE CHART */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-gray-100 gap-2">
            <div>
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                B · HISTORICAL PRICE CHART
              </h3>
              <p className="text-[11px] text-gray-400 mt-0.5">
                Daily close, {currentAsset.currency} · Hover shows price and timestamp
              </p>
            </div>

            {/* Timeframe Toggles */}
            <div className="flex items-center space-x-1 bg-gray-100 p-1 rounded-lg text-xs font-medium">
              {(['1M', '3M', '6M', 'Around event'] as const).map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1 rounded-md transition-all ${
                    timeframe === tf
                      ? 'bg-white text-gray-950 font-bold shadow-2xs'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Chart Rendering or Honest Empty State */}
          {chartPoints.length > 0 ? (
            <div className="pt-4">
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartPoints} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                    <XAxis
                      dataKey="displayDate"
                      stroke="#94A3B8"
                      fontSize={11}
                      tickLine={false}
                    />
                    <YAxis
                      domain={['auto', 'auto']}
                      stroke="#94A3B8"
                      fontSize={11}
                      tickLine={false}
                      tickFormatter={(val) => val.toLocaleString()}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const data = payload[0].payload;
                          return (
                            <div className="bg-gray-900 text-white p-2.5 rounded-lg shadow-xl text-xs space-y-1">
                              <p className="text-gray-400 text-[10px] font-mono">{data.date}</p>
                              {data.close !== null ? (
                                <p className="font-bold text-sm">
                                  {currentAsset.currency} {data.close.toLocaleString()}
                                </p>
                              ) : (
                                <p className="text-amber-400 font-semibold">Missing observation</p>
                              )}
                              {data.isEventDate && (
                                <span className="inline-block px-1.5 py-0.5 rounded text-[9px] bg-blue-600 text-white font-bold">
                                  EVENT DATE
                                </span>
                              )}
                            </div>
                          );
                        }
                        return null;
                      }}
                    />

                    {/* Shaded 1-5d event window */}
                    <ReferenceArea
                      x1="14 Sep"
                      x2="21 Sep"
                      fill="#EFF6FF"
                      fillOpacity={0.7}
                      label={{
                        value: '1–5d window',
                        position: 'insideBottom',
                        fill: '#2563EB',
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    />

                    {/* Hatched area for missing observations */}
                    <ReferenceArea
                      x1="21 Sep"
                      x2="28 Sep"
                      fill="#F8FAFC"
                      fillOpacity={0.8}
                      label={{
                        value: 'No data · 3 days',
                        position: 'insideTop',
                        fill: '#B45309',
                        fontSize: 10,
                        fontWeight: 600,
                      }}
                    />

                    {/* Vertical Event Date Marker */}
                    <ReferenceLine
                      x="14 Sep"
                      stroke="#2563EB"
                      strokeDasharray="4 4"
                      label={{
                        value: 'Event · 14 Sep',
                        position: 'top',
                        fill: '#2563EB',
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    />

                    <Line
                      type="monotone"
                      dataKey="close"
                      stroke="#0F172A"
                      strokeWidth={2}
                      dot={{ r: 2, fill: '#0F172A' }}
                      activeDot={{ r: 5, fill: '#2563EB' }}
                      connectNulls={false} // Never interpolate missing data
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Chart Legend */}
              <div className="flex flex-wrap items-center justify-center gap-6 pt-4 text-[11px] text-gray-500 border-t border-gray-100">
                <div className="flex items-center space-x-1.5">
                  <span className="w-3 h-0.5 bg-gray-900"></span>
                  <span>Close</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-0.5 h-3 bg-blue-600 border-dashed"></span>
                  <span>Selected event date</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-3 h-3 bg-blue-100 border border-blue-300 rounded-xs"></span>
                  <span>Event window available</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-3 h-3 bg-gray-200 border border-gray-300 rounded-xs"></span>
                  <span>Missing observations (not interpolated)</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-14 text-center space-y-2">
              <div className="text-sm font-bold text-gray-800">
                No historical chart for {currentAsset.name}
              </div>
              <p className="text-xs text-gray-500 max-w-md mx-auto">
                The configured provider does not cover this index, so there is nothing to plot. No prices have been estimated or substituted.
              </p>
            </div>
          )}
        </div>

        {/* SECTION C & D: RETURNS & EVENT CONTEXT */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Section C: Returns (Backend-Calculated) */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
              C · RETURNS (BACKEND-CALCULATED)
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-100 text-[11px] font-bold text-gray-400 uppercase">
                    <th className="py-2">Window</th>
                    <th className="py-2">Return</th>
                    <th className="py-2 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {returnsList.length > 0 ? (
                    returnsList.map((ret, idx) => (
                      <tr key={idx} className="hover:bg-gray-50/50">
                        <td className="py-2.5 font-medium text-gray-800">{ret.window}</td>
                        <td className="py-2.5 font-bold font-mono">
                          <span
                            className={
                              ret.returnVal && ret.returnVal < 0
                                ? 'text-red-600'
                                : ret.returnVal && ret.returnVal > 0
                                ? 'text-emerald-600'
                                : 'text-gray-400'
                            }
                          >
                            {ret.returnPercentStr}
                          </span>
                        </td>
                        <td className="py-2.5 text-right">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${
                              ret.status === 'Complete'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                            }`}
                          >
                            {ret.statusNote || ret.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={3} className="py-6 text-center text-gray-400">
                        Returns unavailable for this asset.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <p className="text-[10px] text-gray-400 mt-4 leading-normal">
              Definition shown from the backend: close on trading day N after the event date, divided by the close on the event date, minus 1. If the backend uses other windows, those replace these rows.
            </p>
          </div>

          {/* Section D: Event Context & Limitations */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs space-y-4">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              D · EVENT CONTEXT
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-100 text-[11px] font-bold text-gray-400 uppercase">
                    <th className="py-2">Similar event</th>
                    <th className="py-2">Asset</th>
                    <th className="py-2 text-right">Observed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {marketData.similarEvents.map((sim, i) => (
                    <tr key={i} className="hover:bg-gray-50/50">
                      <td className="py-2.5">
                        <span className="font-bold text-gray-900 block">{sim.title}</span>
                        <span className="text-[10px] text-gray-400">{sim.sampleDate}</span>
                      </td>
                      <td className="py-2.5 font-medium text-gray-600">{sim.assetSymbol}</td>
                      <td className="py-2.5 text-right font-mono font-bold text-red-600">
                        {sim.observedReturn} <span className="text-gray-400 font-normal">{sim.windowLabel}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="p-3 bg-amber-50/60 border border-amber-100 rounded-lg text-[11px] text-amber-900 leading-relaxed">
              <strong className="font-bold">Limitations:</strong> {marketData.limitations}
            </div>
          </div>
        </div>

        {/* SECTION E: DATA AVAILABILITY */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs space-y-4">
          <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
            E · DATA AVAILABILITY
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            {marketData.dataAvailabilityCards.map((card) => (
              <div
                key={card.assetId}
                className="p-3.5 rounded-lg border border-gray-200 bg-gray-50/50 space-y-2"
              >
                <div className="flex items-center space-x-2">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                      card.status === 'Available'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : card.status === 'Partial'
                        ? 'bg-amber-50 text-amber-700 border-amber-200'
                        : 'bg-red-50 text-red-700 border-red-200'
                    }`}
                  >
                    {card.status}
                  </span>
                  <span className="font-bold text-gray-900">{card.assetName}</span>
                </div>
                <p className="text-[11px] text-gray-600 leading-snug">{card.details}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
