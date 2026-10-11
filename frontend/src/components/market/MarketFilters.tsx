import React, { useState } from 'react';
import { SlidersHorizontal, Plus, Minus, X, Check } from 'lucide-react';

export interface FilterState {
  regions: string[];
  domains: string[];
  timeframe: string;
}

interface MarketFiltersProps {
  filters: FilterState;
  onChange: (newFilters: FilterState) => void;
  onReset: () => void;
}

export const MarketFilters: React.FC<MarketFiltersProps> = ({
  filters,
  onChange,
  onReset,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [expandedSections, setExpandedSections] = useState<{
    region: boolean;
    domain: boolean;
    time: boolean;
  }>({
    region: true,
    domain: false,
    time: false,
  });

  const toggleSection = (section: 'region' | 'domain' | 'time') => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const handleRegionToggle = (region: string) => {
    const next = filters.regions.includes(region)
      ? filters.regions.filter((r) => r !== region)
      : [...filters.regions, region];
    onChange({ ...filters, regions: next });
  };

  const handleDomainToggle = (domain: string) => {
    const next = filters.domains.includes(domain)
      ? filters.domains.filter((d) => d !== domain)
      : [...filters.domains, domain];
    onChange({ ...filters, domains: next });
  };

  const handleTimeChange = (time: string) => {
    onChange({ ...filters, timeframe: filters.timeframe === time ? '' : time });
  };

  const totalActive =
    filters.regions.length +
    filters.domains.length +
    (filters.timeframe ? 1 : 0);

  const regionOptions = ['USA', 'EU', 'Asia', 'APAC', 'Global'];
  const domainOptions = ['Banking', 'Transport', 'Technology', 'Energy', 'Trade'];
  const timeOptions = ['Last 24 hours', 'Last 7 days', 'Last 30 days', '1-5d event window'];

  return (
    <div className="relative inline-block text-left">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center space-x-2 px-3 py-2 rounded-lg border text-xs font-semibold transition-all ${
          isOpen || totalActive > 0
            ? 'border-blue-600 bg-blue-50 text-blue-700'
            : 'border-gray-200 bg-white hover:bg-gray-50 text-gray-700 shadow-2xs'
        }`}
      >
        <SlidersHorizontal size={14} />
        <span>Filter</span>
        {totalActive > 0 && (
          <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-[10px] flex items-center justify-center font-bold">
            {totalActive}
          </span>
        )}
      </button>

      {/* Expandable Filter Dropdown / Drawer (matching hand-drawn sketches) */}
      {isOpen && (
        <div className="absolute right-0 sm:left-0 mt-2 w-72 bg-white border border-gray-200 rounded-xl shadow-xl z-40 p-4 transition-all">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                Filters
              </span>
              {totalActive > 0 && (
                <span className="text-[11px] text-blue-600 font-semibold">
                  ({totalActive} active)
                </span>
              )}
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-gray-700 p-1"
            >
              <X size={15} />
            </button>
          </div>

          <div className="py-2 space-y-2 text-xs">
            {/* Region Group */}
            <div className="border-b border-gray-100 pb-2">
              <button
                onClick={() => toggleSection('region')}
                className="w-full flex items-center justify-between py-1.5 text-xs font-bold text-gray-800 hover:text-gray-950"
              >
                <span>Region</span>
                <span className="text-gray-500 font-mono text-sm">
                  {expandedSections.region ? <Minus size={14} /> : <Plus size={14} />}
                </span>
              </button>

              {expandedSections.region && (
                <div className="pl-2 pt-1.5 space-y-1.5">
                  {regionOptions.map((reg) => {
                    const isChecked = filters.regions.includes(reg);
                    return (
                      <label
                        key={reg}
                        className="flex items-center space-x-2 cursor-pointer text-gray-700 hover:text-gray-950"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleRegionToggle(reg)}
                          className="w-3.5 h-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-xs">{reg}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Domain Group */}
            <div className="border-b border-gray-100 pb-2">
              <button
                onClick={() => toggleSection('domain')}
                className="w-full flex items-center justify-between py-1.5 text-xs font-bold text-gray-800 hover:text-gray-950"
              >
                <span>Domain</span>
                <span className="text-gray-500 font-mono text-sm">
                  {expandedSections.domain ? <Minus size={14} /> : <Plus size={14} />}
                </span>
              </button>

              {expandedSections.domain && (
                <div className="pl-2 pt-1.5 space-y-1.5">
                  {domainOptions.map((dom) => {
                    const isChecked = filters.domains.includes(dom);
                    return (
                      <label
                        key={dom}
                        className="flex items-center space-x-2 cursor-pointer text-gray-700 hover:text-gray-950"
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => handleDomainToggle(dom)}
                          className="w-3.5 h-3.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-xs">{dom}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Time Group */}
            <div className="pb-2">
              <button
                onClick={() => toggleSection('time')}
                className="w-full flex items-center justify-between py-1.5 text-xs font-bold text-gray-800 hover:text-gray-950"
              >
                <span>Time</span>
                <span className="text-gray-500 font-mono text-sm">
                  {expandedSections.time ? <Minus size={14} /> : <Plus size={14} />}
                </span>
              </button>

              {expandedSections.time && (
                <div className="pl-2 pt-1.5 space-y-1.5">
                  {timeOptions.map((t) => {
                    const isChecked = filters.timeframe === t;
                    return (
                      <label
                        key={t}
                        className="flex items-center space-x-2 cursor-pointer text-gray-700 hover:text-gray-950"
                      >
                        <input
                          type="radio"
                          name="timeframe"
                          checked={isChecked}
                          onChange={() => handleTimeChange(t)}
                          className="w-3.5 h-3.5 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-xs">{t}</span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
            <button
              onClick={onReset}
              className="text-xs text-gray-500 hover:text-gray-800 font-medium"
            >
              Reset
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-md shadow-2xs"
            >
              Apply filters
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
