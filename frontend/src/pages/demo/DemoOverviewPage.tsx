import React, { useState, useMemo } from 'react';
import { DemoDataBanner } from '../../components/layout/DemoDataBanner';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronLeft, ChevronRight, ArrowUpRight, Activity, Zap, CheckCircle2 } from 'lucide-react';
import { Header } from '../../components/layout/Header';
import { MarketFilters, FilterState } from '../../components/market/MarketFilters';
import { useApp } from '../../context/AppContext';
import { DEMO_EVENTS } from '../../services/demoData';
import { FinancialEvent } from '../../types/event';

export const DemoOverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const { setSelectedEventId } = useApp();

  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const [filters, setFilters] = useState<FilterState>({
    regions: [],
    domains: [],
    timeframe: '',
  });

  // Filter and search logic
  const filteredEvents = useMemo(() => {
    return DEMO_EVENTS.filter((event) => {
      // Search text
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesTitle = event.headline.toLowerCase().includes(query);
        const matchesDomain = event.domain.toLowerCase().includes(query);
        const matchesCategory = event.category.toLowerCase().includes(query);
        if (!matchesTitle && !matchesDomain && !matchesCategory) return false;
      }

      // Region filter
      if (filters.regions.length > 0 && !filters.regions.includes(event.region)) {
        return false;
      }

      // Domain filter
      if (filters.domains.length > 0 && !filters.domains.includes(event.domain)) {
        return false;
      }

      return true;
    });
  }, [searchQuery, filters]);

  // Pagination calculation
  const totalPages = Math.ceil(filteredEvents.length / itemsPerPage) || 1;
  const paginatedEvents = filteredEvents.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const handleSelectEvent = (event: FinancialEvent) => {
    setSelectedEventId(event.id);
    navigate('/workspace');
  };

  const getImpactBadge = (impact: string) => {
    switch (impact) {
      case 'High':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'Medium':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'Low':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      default:
        return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB]">
      <Header
        title="Intelligence Overview"
        tag="XYZ FINANCIAL INTELLIGENCE PLATFORM"
        subtitle="Recently detected market events and propagation candidates awaiting analysis"
        showActions={false}
      />
      <DemoDataBanner reason="Demo mode is on (switch it off in Settings to see live backend data)." />

      <div className="p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* Metric Triage Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
                Detected Events
              </span>
              <Activity size={16} className="text-blue-600" />
            </div>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className="text-2xl font-black text-gray-950 font-sans">{DEMO_EVENTS.length}</span>
              <span className="text-xs text-emerald-600 font-semibold">+2 today</span>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
                Completed Analyses
              </span>
              <CheckCircle2 size={16} className="text-emerald-600" />
            </div>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className="text-2xl font-black text-gray-950 font-sans">3</span>
              <span className="text-xs text-gray-400">stored in backend</span>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
                High Impact Shocks
              </span>
              <Zap size={16} className="text-red-500" />
            </div>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className="text-2xl font-black text-gray-950 font-sans">
                {DEMO_EVENTS.filter((e) => e.impact === 'High').length}
              </span>
              <span className="text-xs text-red-500 font-semibold">Priority review</span>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs">
            <div className="flex items-center justify-between text-gray-400">
              <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
                Network Status
              </span>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            <div className="mt-2 flex items-baseline space-x-2">
              <span className="text-base font-bold text-gray-950">Active Sync</span>
              <span className="text-xs text-gray-400">Graph engine ready</span>
            </div>
          </div>
        </div>

        {/* Search Bar & Hand-Drawn Filter Button Container */}
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3.5 top-2.5 text-gray-400" size={17} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search events, headlines, domains or categories..."
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-xs bg-gray-50/50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder:text-gray-400 font-medium"
            />
          </div>

          <div className="flex items-center space-x-3 w-full sm:w-auto justify-end">
            <MarketFilters
              filters={filters}
              onChange={setFilters}
              onReset={() => setFilters({ regions: [], domains: [], timeframe: '' })}
            />
          </div>
        </div>

        {/* Wireframe-Compliant Event List Table */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-2xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80 text-[11px] font-bold uppercase tracking-wider text-gray-500">
                  <th className="py-3 px-5">Event Title</th>
                  <th className="py-3 px-4">Domain</th>
                  <th className="py-3 px-4">Region</th>
                  <th className="py-3 px-4">Time</th>
                  <th className="py-3 px-4">Impact</th>
                  <th className="py-3 px-5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                {paginatedEvents.length > 0 ? (
                  paginatedEvents.map((evt) => (
                    <tr
                      key={evt.id}
                      onClick={() => handleSelectEvent(evt)}
                      className="hover:bg-blue-50/40 cursor-pointer transition-colors group"
                    >
                      <td className="py-4 px-5">
                        <div className="font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
                          {evt.headline}
                        </div>
                        <div className="text-[11px] text-gray-500 mt-0.5 truncate max-w-lg">
                          {evt.summary}
                        </div>
                      </td>

                      <td className="py-4 px-4 font-semibold text-gray-700">
                        {evt.domain}
                      </td>

                      <td className="py-4 px-4 font-medium text-gray-600">
                        {evt.region}
                      </td>

                      <td className="py-4 px-4 text-gray-500 font-mono">
                        {evt.timeAgo}
                      </td>

                      <td className="py-4 px-4">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold border ${getImpactBadge(
                            evt.impact
                          )}`}
                        >
                          {evt.impact}
                        </span>
                      </td>

                      <td className="py-4 px-5 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectEvent(evt);
                          }}
                          className="inline-flex items-center text-xs font-semibold text-blue-600 group-hover:text-blue-800 transition-colors"
                        >
                          <span>Analyze</span>
                          <ArrowUpRight size={14} className="ml-0.5" />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-gray-400">
                      No matching events found. Try adjusting your search query or filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls matching wireframe: Prev [ 1 | 2 | 3 ] Next */}
          <div className="px-5 py-3 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between text-xs text-gray-500">
            <span>
              Showing {filteredEvents.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0} to{' '}
              {Math.min(currentPage * itemsPerPage, filteredEvents.length)} of {filteredEvents.length} events
            </span>

            <div className="flex items-center space-x-1">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-2.5 py-1 rounded border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 text-gray-700 font-medium"
              >
                Prev
              </button>

              {Array.from({ length: totalPages }, (_, i) => i + 1).map((pageNum) => (
                <button
                  key={pageNum}
                  onClick={() => setCurrentPage(pageNum)}
                  className={`w-7 h-7 rounded text-xs font-bold transition-all ${
                    currentPage === pageNum
                      ? 'bg-blue-600 text-white shadow-2xs'
                      : 'border border-gray-200 bg-white hover:bg-gray-50 text-gray-700'
                  }`}
                >
                  {pageNum}
                </button>
              ))}

              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-2.5 py-1 rounded border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-40 text-gray-700 font-medium"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
