import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Newspaper, FileText, Loader2 } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { eventsApi } from '../../services/eventsApi';
import { errorMessage } from '../../services/http';
import { IngestResponse, NewsProviderId, NewsSources } from '../../types/live';

const REFRESH_EVERY_MS = 10_000;
const REFRESH_FOR_MS = 4 * 60_000;

/**
 * Creates events on the live backend:
 *  - fetch news from a provider (GDELT) and process it in the background (event detection + LLM analysis);
 *  - analyse article text supplied by the user (labelled USER_SUPPLIED by the backend).
 */
export const AddEventsPanel: React.FC = () => {
  const navigate = useNavigate();
  const { reloadEvents, setSelectedEventId, events } = useApp();
  const [tab, setTab] = useState<'news' | 'text'>('news');
  const [query, setQuery] = useState(''); // RSS: optional keyword filter; GDELT: empty = default query
  const [sources, setSources] = useState<NewsSources | null>(null);
  const [provider, setProvider] = useState<NewsProviderId>('rss');
  const [feeds, setFeeds] = useState<string[]>([]);
  const [limit, setLimit] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ingest, setIngest] = useState<IngestResponse | null>(null);
  const [refreshUntil, setRefreshUntil] = useState<number | null>(null);
  const [headline, setHeadline] = useState('');
  const [body, setBody] = useState('');
  const [source, setSource] = useState('');
  const [url, setUrl] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const startCount = useRef(0);

  useEffect(() => {
    eventsApi.newsSources().then((s) => {
      setSources(s);
      setFeeds((s.providers.find((p) => p.id === 'rss')?.feeds ?? []).map((f) => f.key));
    }).catch((e) => setError(`Could not load news sources: ${errorMessage(e)}`));
  }, []);
  const rss = sources?.providers.find((p) => p.id === 'rss');
  const current = sources?.providers.find((p) => p.id === provider);

  // While background processing runs, refresh the event list so new events appear.
  useEffect(() => {
    if (!refreshUntil) return;
    const t = setInterval(() => {
      if (Date.now() > refreshUntil) { setRefreshUntil(null); return; }
      reloadEvents();
    }, REFRESH_EVERY_MS);
    return () => clearInterval(t);
  }, [refreshUntil, reloadEvents]);

  const fetchNews = async () => {
    setBusy(true); setError(null); setIngest(null); setNote(null);
    startCount.current = events.length;
    try {
      const r = await eventsApi.ingest(provider, query.trim() || null, limit, provider === 'rss' ? feeds : undefined);
      setIngest(r);
      if (r.processing === 'scheduled' && r.inserted > 0) setRefreshUntil(Date.now() + REFRESH_FOR_MS);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const analyseText = async () => {
    setBusy(true); setError(null); setNote(null);
    try {
      const r = await eventsApi.analyzeText({ headline: headline.trim(), body: body.trim(), source_name: source.trim(), url: url.trim(), simulated: false });
      reloadEvents();
      if (r.event_id) {
        setSelectedEventId(r.event_id);
        navigate('/workspace');
      } else {
        setNote(`No financial event was detected (${r.status}${r.detail ? `: ${r.detail}` : ''}).`);
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const newEvents = Math.max(0, events.length - startCount.current);
  const input = 'w-full px-2.5 py-1.5 border border-gray-200 rounded-lg text-xs outline-none focus:ring-2 focus:ring-blue-500';
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-extrabold text-gray-950">Add events</span>
        <div className="flex gap-1">
          <button onClick={() => setTab('news')} className={`px-2.5 py-1 rounded-lg border flex items-center gap-1 cursor-pointer ${tab === 'news' ? 'bg-blue-50 border-blue-200 text-blue-800' : 'border-gray-200 text-gray-600'}`}>
            <Newspaper size={12} /> Fetch live news
          </button>
          <button onClick={() => setTab('text')} className={`px-2.5 py-1 rounded-lg border flex items-center gap-1 cursor-pointer ${tab === 'text' ? 'bg-blue-50 border-blue-200 text-blue-800' : 'border-gray-200 text-gray-600'}`}>
            <FileText size={12} /> Analyse an article
          </button>
        </div>
      </div>

      {tab === 'news' ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-gray-500">Source</span>
            {(sources?.providers ?? []).filter((p) => p.id !== 'fixture').map((p) => (
              <button key={p.id} onClick={() => setProvider(p.id)} disabled={!p.configured} title={p.note}
                      className={`px-2.5 py-1 rounded-lg border cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${provider === p.id ? 'bg-blue-50 border-blue-200 text-blue-800 font-semibold' : 'border-gray-200 text-gray-600'}`}>
                {p.name}{!p.configured ? ' (needs key)' : ''}
              </button>
            ))}
          </div>
          {current && <p className="text-gray-400">{current.note}</p>}
          {provider === 'rss' && rss?.feeds && (
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              {rss.feeds.map((f) => (
                <label key={f.key} className="inline-flex items-center gap-1 text-gray-700 cursor-pointer">
                  <input type="checkbox" checked={feeds.includes(f.key)}
                         onChange={(e) => setFeeds((cur) => e.target.checked ? [...cur, f.key] : cur.filter((k) => k !== f.key))} />
                  {f.name}
                </label>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-2 items-end">
            <label className="flex-1 min-w-[220px] space-y-1"><span className="text-gray-500">{provider === 'rss' ? 'Keyword filter (optional, any word matches)' : 'Search query (last 24 h; empty = default financial-news query)'}</span>
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. OPEC oil supply" className={input} maxLength={500} /></label>
            <label className="w-24 space-y-1"><span className="text-gray-500">Articles</span>
              <input type="number" min={1} max={50} value={limit} onChange={(e) => { const v = parseInt(e.target.value, 10); if (Number.isFinite(v)) setLimit(Math.min(50, Math.max(1, v))); }} className={input} /></label>
            <button onClick={fetchNews} disabled={busy || (provider === 'rss' && !feeds.length)} className="px-3 py-1.5 rounded-lg bg-blue-600 text-white font-bold disabled:opacity-50 flex items-center gap-1 cursor-pointer">
              {busy && <Loader2 size={12} className="animate-spin" />} Fetch and analyse
            </button>
          </div>
          <p className="text-gray-400">Articles are deduplicated, pre-filtered for financial relevance and analysed in the background by the configured LLM (calls count against your provider quota).</p>
          {ingest?.notes && ingest.notes.length > 0 && (
            <p className="text-amber-800">Some sources failed: {ingest.notes.join('; ')}</p>
          )}
          {ingest && (
            <p className="text-gray-700">
              Fetched {ingest.fetched} · new {ingest.inserted} · duplicates {ingest.duplicates} · invalid {ingest.invalid}.{' '}
              {ingest.inserted === 0 ? (ingest.fetched === 0 ? 'No articles matched; try a broader query or more sources.' : 'Nothing new to analyse (already fetched earlier).') : refreshUntil
                ? <span className="inline-flex items-center gap-1"><Loader2 size={11} className="animate-spin" /> Processing in the background; the list refreshes every 10 s ({newEvents} new event(s) so far).</span>
                : `Processing finished or stopped refreshing (${newEvents} new event(s)). Reload to check again.`}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="Headline (required, at least 10 characters)" className={input} maxLength={1000} />
          <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Article text (optional but recommended)" className={`${input} h-28`} maxLength={50000} />
          <div className="flex flex-wrap gap-2">
            <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source name (optional)" className={`${input} flex-1 min-w-[160px]`} />
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://source-url (optional)" className={`${input} flex-1 min-w-[200px]`} />
            <button onClick={analyseText} disabled={busy || headline.trim().length < 10}
                    className="px-3 py-1.5 rounded-lg bg-blue-600 text-white font-bold disabled:opacity-50 flex items-center gap-1 cursor-pointer">
              {busy && <Loader2 size={12} className="animate-spin" />} {busy ? 'Analysing (up to a few minutes)…' : 'Analyse'}
            </button>
          </div>
          <p className="text-gray-400">The text is treated as untrusted input and labelled as user-supplied in the analysis.</p>
          {note && <p className="text-gray-700">{note}</p>}
        </div>
      )}
      {error && (
        <p className="p-2 rounded border border-red-200 bg-red-50 text-red-900">
          Request failed: {error}
          {/rate limit/i.test(error) && ' GDELT allows one request every few seconds per IP and sometimes throttles for longer; try again in a minute, or use "Analyse an article".'}
        </p>
      )}
    </div>
  );
};
