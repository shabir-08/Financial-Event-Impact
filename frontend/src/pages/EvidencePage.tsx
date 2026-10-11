import React, { useMemo } from 'react';
import { ExternalLink } from 'lucide-react';
import { Header } from '../components/layout/Header';
import { EmptyState, ErrorState, LiveEventGate, LoadingState, SimulatedBadge, StatusChip, human, useAsync } from '../components/live/LiveKit';
import { eventsApi } from '../services/eventsApi';
import { EventSummary } from '../types/live';

const Evidence: React.FC<{ event: EventSummary }> = ({ event }) => {
  const data = useAsync(() => eventsApi.evidence(event.id), event.id);
  const grouped = useMemo(() => {
    const m = new Map<string, NonNullable<typeof data.data>['relationship_evidence']>();
    (data.data?.relationship_evidence ?? []).forEach((r) => m.set(r.relationship_id, [...(m.get(r.relationship_id) ?? []), r]));
    return [...m.values()];
  }, [data.data]);
  if (data.status === 'loading') return <LoadingState />;
  if (data.status === 'error') return <ErrorState message={data.error!} onRetry={data.reload} />;
  const r = data.data!;
  const headline = new Map(r.articles.map((a) => [a.article_id, a]));
  return (
    <div className="space-y-5 text-xs">
      <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
        <p className="font-extrabold text-gray-950">Source articles ({r.articles.length})</p>
        {!r.articles.length && <EmptyState message="No articles are linked to this event." />}
        {r.articles.map((a) => (
          <div key={a.article_id} className="p-2 rounded border border-gray-100 space-y-1">
            <p className="font-semibold text-gray-900 flex flex-wrap items-center gap-2">
              {a.headline} <SimulatedBadge show={a.is_simulated} />
              {a.url && <a href={a.url} target="_blank" rel="noreferrer" className="text-blue-600 inline-flex items-center gap-0.5">source <ExternalLink size={11} /></a>}
            </p>
            <p className="text-gray-500">{a.source_name ?? 'unknown source'} · {a.published_at?.slice(0, 16).replace('T', ' ') ?? 'date unknown'} · {human(a.role)} · origin {human(a.input_origin)}</p>
            {(a.supporting_passages ?? []).map((s, i) => <p key={i} className="pl-2 border-l-2 border-blue-200 text-gray-700 italic">“{s}”</p>)}
          </div>
        ))}
      </div>
      <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
        <p className="font-extrabold text-gray-950">Claims extracted from the articles ({r.claims.length})</p>
        <p className="text-gray-500">A claim is only used as a REPORTED link if its passage was found verbatim in the article.</p>
        {r.claims.map((c) => (
          <div key={c.id} className="p-2 rounded border border-gray-100 space-y-1">
            <p className="font-semibold">{c.source_mention} → {c.target_mention} <span className="font-normal text-gray-500">({human(c.relationship_type)})</span></p>
            <p className="flex flex-wrap gap-2 items-center">
              <span className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${c.passage_verified ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'}`}>
                {c.passage_verified ? 'passage verified verbatim' : 'passage NOT verified'}
              </span>
              <span className="text-gray-500">{c.used_in_graph ? 'used in graph' : 'not used in graph'}</span>
            </p>
            {c.passage && <p className="pl-2 border-l-2 border-gray-200 italic text-gray-600">“{c.passage}”</p>}
          </div>
        ))}
      </div>
      <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
        <p className="font-extrabold text-gray-950">Evidence behind each graph relationship ({grouped.length})</p>
        {grouped.map((items) => (
          <div key={items[0].relationship_id} className="p-2 rounded border border-gray-100 space-y-1">
            <p className="font-semibold flex flex-wrap items-center gap-2">{items[0].source} → {items[0].target} <StatusChip status={items[0].status} /></p>
            {items.map((ev, i) => (
              <p key={i} className="text-gray-600">
                <span className="font-mono text-[10px] text-gray-400">{ev.evidence_type}</span>{' '}
                {ev.passage ? `“${ev.passage}”` : ev.reference}
                {ev.article_id && headline.get(ev.article_id) ? <span className="text-gray-400"> ({headline.get(ev.article_id)!.source_name ?? 'source'})</span> : null}
              </p>
            ))}
          </div>
        ))}
        <p className="text-[10px] text-gray-400">REPORTED = stated in a source article (passage verified); INFERRED = economic knowledge base, not the articles; UNVERIFIED = claimed but the passage could not be verified.</p>
      </div>
    </div>
  );
};

export const EvidencePage: React.FC = () => (
  <div className="flex-1 flex flex-col bg-[#F9FAFB] min-h-screen">
    <Header tag="EVIDENCE & SOURCES" subtitle="Articles, extracted claims and the evidence behind each relationship" showActions={true} />
    <div className="flex-1 p-6 max-w-7xl mx-auto w-full space-y-5">
      <LiveEventGate>{(event) => <Evidence key={event.id} event={event} />}</LiveEventGate>
    </div>
  </div>
);
