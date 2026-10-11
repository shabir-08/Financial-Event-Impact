import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Download, FileText } from 'lucide-react';
import { Header } from '../components/layout/Header';
import { ReportSectionView } from '../components/report/ReportSectionView';
import { EmptyState, ErrorState, LoadingState, SimulatedBadge, useAsync } from '../components/live/LiveKit';
import { reportsApi } from '../services/reportsApi';
import { downloadReportPdf } from '../services/reportPdf';
import { errorMessage } from '../services/http';
import { Report } from '../types/report';

export const ReportView: React.FC<{ report: Report }> = ({ report }) => (
  <div className="space-y-4">
    <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-extrabold text-gray-950">{report.title}</h1>
        {report.is_hypothetical && (
          <span className="px-1.5 py-0.5 rounded border border-purple-300 bg-purple-50 text-purple-800 text-[10px] font-mono font-bold">HYPOTHETICAL SCENARIO</span>
        )}
        <SimulatedBadge show={report.is_simulated_data} />
      </div>
      <p className="text-gray-500 font-mono">
        {report.report_id} · {report.kind} source {report.source_id} · created {report.created_at.slice(0, 16).replace('T', ' ')}
        {report.cached ? ' · stored report reused' : ''}
      </p>
      <div className="flex flex-wrap gap-1.5 pt-1">
        {report.sections.map((s, i) => (
          <a key={s.key} href={`#${s.key}`} className="px-2 py-0.5 rounded border border-gray-200 text-[10px] text-gray-600 hover:bg-gray-50">
            {i + 1}. {s.title} <span className="text-gray-400">({s.status})</span>
          </a>
        ))}
      </div>
    </div>
    {report.sections.map((s, i) => <div id={s.key} key={s.key}><ReportSectionView section={s} index={i + 1} /></div>)}
  </div>
);

/** /reports/:reportId shows a stored report; /reports/new?kind=&source= creates one, then redirects. */
export const ReportPage: React.FC = () => {
  const { reportId } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [createError, setCreateError] = useState<string | null>(null);
  const creating = reportId === 'new';
  const requested = useRef<string | null>(null); // StrictMode runs effects twice: create the report only once

  useEffect(() => {
    if (!creating) return;
    const kind = params.get('kind') as 'event' | 'simulation' | null;
    const source = params.get('source');
    if (!kind || !source) { setCreateError('Missing report source (kind and source are required).'); return; }
    if (requested.current === `${kind}:${source}`) return;
    requested.current = `${kind}:${source}`;
    reportsApi.create(kind, source)
      .then((r) => navigate(`/reports/${r.report_id}`, { replace: true }))
      .catch((e) => setCreateError(errorMessage(e)));
  }, [creating, params, navigate]);

  const data = useAsync(!creating && reportId ? () => reportsApi.get(reportId) : null, reportId ?? '');
  const report = data.data;
  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
      <Header title={report?.title ?? 'Analysis report'} tag="ANALYSIS REPORT" subtitle="12-section report assembled by the backend from stored results" showActions={false} />
      <div className="flex-1 p-6 max-w-5xl mx-auto w-full space-y-4">
        {creating && !createError && <LoadingState label="Assembling the report on the backend…" />}
        {createError && <ErrorState message={createError} />}
        {!creating && data.status === 'loading' && <LoadingState />}
        {!creating && data.status === 'error' && <ErrorState message={data.error!} onRetry={data.reload} />}
        {report && (
          <>
            <div className="flex justify-end">
              <button onClick={() => downloadReportPdf(report)}
                      className="flex items-center gap-1.5 px-3.5 py-1.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-800 text-xs font-semibold rounded-lg cursor-pointer">
                <Download size={14} /> Export PDF
              </button>
            </div>
            <ReportView report={report} />
          </>
        )}
      </div>
    </div>
  );
};

/** /reports: list of stored reports. */
export const ReportsListPage: React.FC = () => {
  const navigate = useNavigate();
  const data = useAsync(() => reportsApi.list(), 'list');
  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
      <Header title="Reports" tag="ANALYSIS REPORTS" subtitle="Reports stored by the backend; generate new ones from an event page or a simulation" showActions={false} />
      <div className="flex-1 p-6 max-w-5xl mx-auto w-full space-y-4 text-xs">
        {data.status === 'loading' && <LoadingState />}
        {data.status === 'error' && <ErrorState message={data.error!} onRetry={data.reload} />}
        {data.status === 'ok' && !data.data!.length && <EmptyState message="No reports yet. Use “Generate report” on an event page or after running a simulation." />}
        {data.status === 'ok' && data.data!.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl divide-y divide-gray-100">
            {data.data!.map((r) => (
              <button key={r.report_id} onClick={() => navigate(`/reports/${r.report_id}`)}
                      className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-center gap-2 cursor-pointer">
                <FileText size={14} className="text-gray-400" />
                <span className="font-semibold text-gray-900">{r.title}</span>
                <span className="text-gray-400 font-mono ml-auto">{r.kind} · {r.created_at.slice(0, 16).replace('T', ' ')}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
