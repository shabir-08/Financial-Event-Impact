import React, { useState, useMemo } from 'react';
import { DemoDataBanner } from '../../components/layout/DemoDataBanner';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronDown, Edit2, RotateCcw, AlertTriangle, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { Header } from '../../components/layout/Header';
import { useApp } from '../../context/AppContext';
import { DEMO_SAVED_ANALYSES } from '../../services/demoData';
import { SavedAnalysisRecord, AnalysisStatus } from '../../types/saved';

export const DemoSavedAnalysesPage: React.FC = () => {
  const navigate = useNavigate();
  const { setSelectedEventId } = useApp();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [selectedStatus, setSelectedStatus] = useState('All');
  const [sortOrder, setSortOrder] = useState('Newest first');

  const savedData = DEMO_SAVED_ANALYSES;

  const filteredRecords = useMemo(() => {
    return savedData.records.filter((rec) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = rec.originalEventTitle.toLowerCase().includes(q) ||
          (rec.userGivenName && rec.userGivenName.toLowerCase().includes(q));
        if (!matchesTitle) return false;
      }
      if (selectedCategory !== 'All' && rec.category !== selectedCategory) {
        return false;
      }
      if (selectedStatus !== 'All' && rec.status !== selectedStatus) {
        return false;
      }
      return true;
    });
  }, [searchQuery, selectedCategory, selectedStatus, savedData.records]);

  const handleReopen = (record: SavedAnalysisRecord) => {
    setSelectedEventId(record.eventId);
    navigate('/workspace');
  };

  const getStatusBadge = (status: AnalysisStatus) => {
    switch (status) {
      case 'Complete':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'Partial':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'Failed':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'Running':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      default:
        return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  const getEvidenceBadge = (status: string | null) => {
    if (!status) return <span className="text-gray-400 font-mono">—</span>;
    switch (status) {
      case 'Available':
        return <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">Available</span>;
      case 'Partial':
        return <span className="px-2 py-0.5 rounded text-[10px] bg-amber-50 text-amber-700 font-bold border border-amber-200">Partial</span>;
      case 'Unavailable':
        return <span className="px-2 py-0.5 rounded text-[10px] bg-gray-100 text-gray-500 font-bold border border-gray-200">Unavailable</span>;
      default:
        return <span className="text-gray-400 font-mono">—</span>;
    }
  };

  const categories = ['All', 'Commodity shock', 'Interest-rate decision', 'Regulatory change', 'Geopolitical', 'Macro data'];
  const statuses = ['All', 'Complete', 'Partial', 'Failed', 'Running'];

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB]">
      <Header
        title="Saved analyses"
        tag="HOME › SAVED ANALYSES"
        subtitle="Saved analyses (demo records: backend storage is not implemented yet)."
        showActions={false}
      />
      <DemoDataBanner reason="Demo mode is on (switch it off in Settings to see live backend data)." />

      {/* Advisory Banner matching reference */}
      <div className="bg-amber-50/70 border-b border-amber-200/80 px-6 py-2 text-xs text-amber-800 text-center font-medium">
        Layout inspiration only. Every title, date, count and status here is a placeholder; the real page lists records returned by the backend.
      </div>

      <div className="p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* Persistence Status Banner */}
        <div className="p-3.5 bg-emerald-50/70 border border-emerald-200 rounded-xl flex items-center space-x-2.5 text-xs text-emerald-900">
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gray-500 text-white shadow-2xs">
            Persistence not available
          </span>
          <span>
            These records are demo constants. No backend endpoint stores or lists saved analyses yet.
          </span>
        </div>

        {/* Filter & Metric Bar */}
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <div className="relative min-w-[220px]">
              <Search className="absolute left-3 top-2.5 text-gray-400" size={15} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by event title"
                className="w-full pl-9 pr-3 py-1.5 border border-gray-200 rounded-lg text-xs bg-gray-50/50 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>

            {/* Category Dropdown */}
            <div className="relative">
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="appearance-none pl-3 pr-8 py-1.5 border border-gray-200 bg-white rounded-lg text-xs font-semibold text-gray-700 outline-none hover:bg-gray-50 cursor-pointer"
              >
                {categories.map((c) => (
                  <option key={c} value={c}>Category: {c}</option>
                ))}
              </select>
              <ChevronDown size={13} className="absolute right-2.5 top-2.5 text-gray-400 pointer-events-none" />
            </div>

            {/* Status Dropdown */}
            <div className="relative">
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="appearance-none pl-3 pr-8 py-1.5 border border-gray-200 bg-white rounded-lg text-xs font-semibold text-gray-700 outline-none hover:bg-gray-50 cursor-pointer"
              >
                {statuses.map((s) => (
                  <option key={s} value={s}>Status: {s}</option>
                ))}
              </select>
              <ChevronDown size={13} className="absolute right-2.5 top-2.5 text-gray-400 pointer-events-none" />
            </div>

            {/* Sort Dropdown */}
            <div className="relative">
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
                className="appearance-none pl-3 pr-8 py-1.5 border border-gray-200 bg-white rounded-lg text-xs font-semibold text-gray-700 outline-none hover:bg-gray-50 cursor-pointer"
              >
                <option value="Newest first">Sort: Newest first</option>
                <option value="Oldest first">Sort: Oldest first</option>
              </select>
              <ChevronDown size={13} className="absolute right-2.5 top-2.5 text-gray-400 pointer-events-none" />
            </div>
          </div>

          {/* Counts metrics */}
          <div className="text-[11px] font-mono font-bold text-gray-500 uppercase tracking-wider flex items-center space-x-2">
            <span>{savedData.totalCount} ANALYSES</span>
            <span>·</span>
            <span className="text-emerald-600">{savedData.completeCount} COMPLETE</span>
            <span>·</span>
            <span className="text-amber-600">{savedData.partialCount} PARTIAL</span>
            <span>·</span>
            <span className="text-red-600">{savedData.failedCount} FAILED</span>
            <span>·</span>
            <span className="text-blue-600">{savedData.runningCount} RUNNING</span>
          </div>
        </div>

        {/* Saved Analyses Table */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-2xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/80 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                  <th className="py-3 px-5">EVENT</th>
                  <th className="py-3 px-4">CATEGORY</th>
                  <th className="py-3 px-4">ANALYSED</th>
                  <th className="py-3 px-4">STATUS</th>
                  <th className="py-3 px-3 text-center">NODES</th>
                  <th className="py-3 px-3 text-center">PATHS</th>
                  <th className="py-3 px-4 text-center">EVIDENCE</th>
                  <th className="py-3 px-4 text-center">HISTORICAL DATA</th>
                  <th className="py-3 px-5 text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredRecords.map((rec) => (
                  <tr key={rec.id} className="hover:bg-gray-50/60 transition-colors">
                    {/* EVENT */}
                    <td className="py-3.5 px-5">
                      <div className="flex items-center space-x-1.5 font-bold text-gray-900">
                        <span>{rec.userGivenName || rec.originalEventTitle}</span>
                        {rec.userGivenName && (
                          <Edit2 size={11} className="text-gray-400" />
                        )}
                      </div>
                      <div className="text-[11px] text-gray-400 mt-0.5">
                        Event: {rec.originalEventTitle}
                      </div>
                    </td>

                    {/* CATEGORY */}
                    <td className="py-3.5 px-4 font-medium text-gray-700">
                      {rec.category}
                    </td>

                    {/* ANALYSED */}
                    <td className="py-3.5 px-4 font-mono text-gray-500 whitespace-nowrap">
                      {rec.analysedAt}
                    </td>

                    {/* STATUS */}
                    <td className="py-3.5 px-4">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${getStatusBadge(
                          rec.status
                        )}`}
                      >
                        {rec.status}
                      </span>
                    </td>

                    {/* NODES */}
                    <td className="py-3.5 px-3 text-center font-mono font-bold text-gray-800">
                      {rec.nodesCount ?? '—'}
                    </td>

                    {/* PATHS */}
                    <td className="py-3.5 px-3 text-center font-mono font-bold text-gray-800">
                      {rec.pathsCount ?? '—'}
                    </td>

                    {/* EVIDENCE */}
                    <td className="py-3.5 px-4 text-center">
                      {getEvidenceBadge(rec.evidenceStatus)}
                    </td>

                    {/* HISTORICAL DATA */}
                    <td className="py-3.5 px-4 text-center">
                      {getEvidenceBadge(rec.historicalDataStatus)}
                    </td>

                    {/* ACTION */}
                    <td className="py-3.5 px-5 text-right">
                      {rec.status === 'Complete' || rec.status === 'Partial' ? (
                        <button
                          onClick={() => handleReopen(rec)}
                          className="px-3.5 py-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-md shadow-2xs transition-colors"
                        >
                          Reopen
                        </button>
                      ) : rec.status === 'Failed' ? (
                        <button className="px-3 py-1 border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-md">
                          Details
                        </button>
                      ) : (
                        <button className="px-3 py-1 border border-blue-200 text-blue-600 hover:bg-blue-50 rounded-md">
                          View
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-gray-100 bg-gray-50/50 text-[11px] text-gray-400">
            Dashes mean the backend returned no value, not zero. Rename, delete and saved preferences appear only if the backend supports them. The pencil marks a user-given name; the original event stays underneath.
          </div>
        </div>

        {/* OTHER STATES THIS PAGE MUST HANDLE (Section 15 & Reference 7) */}
        <div className="space-y-3 pt-2">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            OTHER STATES THIS PAGE MUST HANDLE
          </span>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            {/* No saved analyses yet */}
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs space-y-1.5">
              <span className="font-bold text-gray-900 block">No saved analyses yet</span>
              <p className="text-[11px] text-gray-500 leading-snug">
                The backend returned an empty list. Run an analysis from the landing page and it will appear here once the backend stores it.
              </p>
            </div>

            {/* Persistence not confirmed */}
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs space-y-1.5">
              <span className="px-2 py-0.5 rounded text-[10px] bg-amber-50 text-amber-700 font-bold border border-amber-200 inline-block">
                Persistence not confirmed
              </span>
              <p className="text-[11px] text-gray-500 leading-snug">
                The backend has not confirmed that records are kept. These analyses may disappear, and the page says so instead of calling them saved.
              </p>
            </div>

            {/* Could not load */}
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-2xs space-y-1.5">
              <span className="px-2 py-0.5 rounded text-[10px] bg-red-50 text-red-700 font-bold border border-red-200 inline-block">
                Could not load
              </span>
              <p className="text-[11px] text-gray-500 leading-snug">
                The request to the backend failed. Show the error and a retry button. Do not show a stale or empty list as if it were real.
              </p>
            </div>
          </div>

          <div className="p-3.5 bg-gray-50 border border-gray-200 rounded-xl text-[11px] text-gray-500">
            <strong className="font-bold text-gray-800">No accounts unless the backend has them.</strong> If the backend has no per-user access control, this page lists everything it stores and does not add a sign-in. A sign-in only appears if the backend actually supports one.
          </div>
        </div>
      </div>
    </div>
  );
};
