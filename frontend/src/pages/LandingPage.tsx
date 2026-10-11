import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, ExternalLink, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useApp } from '../context/AppContext';
import { DEMO_EVENTS } from '../services/demoData';
import { eventsApi } from '../services/eventsApi';
import { errorMessage } from '../services/http';
import { useAsync } from '../components/live/LiveKit';
import { AuthModal } from '../components/auth/AuthModal';
import { UserMenu } from '../components/layout/UserMenu';
import { ArticleSummary, EventSummary } from '../types/live';

/** One card on the front page: an analysed event, or a fetched headline that has not been analysed yet. */
interface Story {
  key: string;
  kind: 'event' | 'headline' | 'demo';
  title: string;
  summary: string | null;
  label: string;
  source: string | null;
  publishedAt: string | null;
  imageUrl: string | null;
  url: string | null;
  eventId?: string;
  articleId?: string;
}

const human = (s: string) => s.replace(/_/g, ' ');

const ago = (iso: string | null): string => {
  if (!iso) return '';
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(mins)) return '';
  if (mins < 60) return `${Math.max(mins, 1)} min ago`;
  if (mins < 48 * 60) return `${Math.round(mins / 60)} h ago`;
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
};

const fromEvent = (e: EventSummary): Story => ({
  key: `e:${e.id}`, kind: 'event', title: e.title, summary: e.summary, label: human(e.event_type),
  source: e.lead_article?.source_name ?? null, publishedAt: e.lead_article?.published_at ?? e.first_reported_at,
  imageUrl: e.lead_article?.image_url ?? null, url: e.lead_article?.url ?? null, eventId: e.id,
});

const fromArticle = (a: ArticleSummary): Story => ({
  key: `a:${a.id}`, kind: 'headline', title: a.headline, summary: a.description, label: a.source_name ?? 'News',
  source: a.source_name, publishedAt: a.published_at, imageUrl: a.image_url, url: a.url, articleId: a.id,
});

const fromDemo = (d: (typeof DEMO_EVENTS)[number]): Story => ({
  key: `d:${d.id}`, kind: 'demo', title: d.headline, summary: d.summary, label: d.category, source: 'Demo',
  publishedAt: null, imageUrl: d.imageUrl ?? null, url: null, eventId: d.id,
});

/** Publisher image, or a neutral tile naming the publisher (never a stock photo standing in for real news). */
const StoryImage: React.FC<{ s: Story; aspect: string; eager?: boolean }> = ({ s, aspect, eager }) => {
  const [failed, setFailed] = useState(false);
  return (
    <div className={`relative overflow-hidden rounded-md bg-gray-100 border border-gray-200 ${aspect}`}>
      {s.imageUrl && !failed ? (
        <img src={s.imageUrl} alt="" loading={eager ? "eager" : "lazy"} referrerPolicy="no-referrer" onError={() => setFailed(true)}
             className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-xs font-semibold text-gray-400 tracking-wider uppercase p-4 text-center">
          {s.source ?? 'No image supplied'}
        </div>
      )}
    </div>
  );
};

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, openLoginModal } = useAuth();
  const { setSelectedEventId, demoMode, setDemoMode, reloadEvents } = useApp();
  const [busyArticle, setBusyArticle] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const live = useAsync(demoMode ? null : () => Promise.all([
    eventsApi.list(), eventsApi.articles('rss', 60).catch(() => [] as ArticleSummary[]),
  ]), demoMode ? 'demo' : 'live');

  const stories: Story[] = useMemo(() => {
    if (demoMode) return DEMO_EVENTS.map(fromDemo);
    if (!live.data) return [];
    const [events, articles] = live.data;
    const real = events.filter((e) => !e.is_simulated);
    const shownArticleIds = new Set(events.map((e) => e.lead_article?.article_id).filter(Boolean));
    const fresh = articles.filter((a) => a.processing_status === 'PENDING' && !shownArticleIds.has(a.id));
    const list = [...real.map(fromEvent), ...fresh.map(fromArticle)];
    // the large featured slot goes to the newest analysed event that has a publisher image, if any
    const lead = list.findIndex((s) => s.kind === 'event' && s.imageUrl);
    if (lead > 0) list.unshift(...list.splice(lead, 1));
    // practice (simulated) events only if there is no real news at all
    return list.length ? list : events.map(fromEvent);
  }, [demoMode, live.data]);

  const open = (s: Story) => {
    if (s.kind === 'headline') return;
    if (s.eventId) setSelectedEventId(s.eventId);
    if (!isAuthenticated) openLoginModal('/overview', s.eventId);
    else navigate('/workspace');
  };

  const analyse = async (s: Story) => {
    if (!s.articleId) return;
    if (!isAuthenticated) { openLoginModal('/overview'); return; }
    setBusyArticle(s.articleId);
    setActionError(null);
    try {
      const r = await eventsApi.processArticle(s.articleId);
      reloadEvents();
      if (r.event_id) {
        setSelectedEventId(r.event_id);
        navigate('/workspace');
      } else {
        setActionError(`"${s.title}" was not detected as a financial event (${r.reason ?? r.status}).`);
        live.reload();
      }
    } catch (e) {
      setActionError(errorMessage(e));
    } finally {
      setBusyArticle(null);
    }
  };

  const handleTopAction = () => (isAuthenticated ? navigate('/overview') : openLoginModal('/overview'));

  const Actions: React.FC<{ s: Story }> = ({ s }) => (
    <div className="flex flex-wrap items-center gap-4">
      {s.kind !== 'headline' && (
        <button onClick={() => open(s)} className="inline-flex items-center text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors w-fit group">
          <span>Learn more</span><ArrowRight size={13} className="ml-1 transition-transform group-hover:translate-x-1" />
        </button>
      )}
      {s.kind === 'headline' && (
        <button onClick={() => analyse(s)} disabled={busyArticle !== null}
                className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-800 disabled:opacity-50 w-fit">
          {busyArticle === s.articleId ? <><Loader2 size={12} className="animate-spin" /> Analysing…</> : <>Analyse <ArrowRight size={13} /></>}
        </button>
      )}
      {s.url && (
        <a href={s.url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-gray-800">
          Read at {s.source ?? 'source'} <ExternalLink size={11} />
        </a>
      )}
    </div>
  );

  const Meta: React.FC<{ s: Story }> = ({ s }) => (
    <span className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">
      {s.kind === 'headline' ? `${s.label} · not analysed yet` : s.label}
      {s.kind === 'event' && s.source ? ` · ${s.source}` : ''}
      {s.publishedAt ? <span className="text-gray-400 font-semibold normal-case tracking-normal"> · {ago(s.publishedAt)}</span> : null}
    </span>
  );

  const [featured, mid1, mid2, right1, right2, right3, ...more] = stories;
  const today = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).toUpperCase();

  return (
    <div className="min-h-screen bg-white text-gray-900 flex flex-col font-sans">
      {/* 1. Top Navbar */}
      <nav className="border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <span className="font-extrabold text-2xl tracking-tight text-gray-950 font-sans">XYZ</span>
          <span className="text-[10px] font-semibold text-gray-500 tracking-wider uppercase pt-1">FINANCIAL INTELLIGENCE</span>
        </div>
        <div className="flex items-center space-x-3">
          {isAuthenticated && <UserMenu />}
          <button onClick={handleTopAction} className="px-5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-md shadow-sm transition-all">
            {isAuthenticated ? 'Enter Workspace' : 'Login'}
          </button>
        </div>
      </nav>

      {/* 2. Subheader Banner */}
      <div className="border-b border-gray-200 px-6 py-3 flex flex-col md:flex-row md:items-center justify-between gap-2">
        <div className="flex items-baseline space-x-3">
          <h2 className="text-xl font-extrabold text-gray-950 tracking-tight">The global briefing</h2>
          <span className="text-xs text-gray-500 font-normal">Events that move markets. Connections that matter.</span>
        </div>
        <div className="text-[11px] font-semibold text-gray-400 tracking-wider uppercase text-right">
          {demoMode ? <>DEMO EDITION · FICTIONAL STORIES <button onClick={() => setDemoMode(false)} className="ml-2 px-2 py-0.5 rounded bg-blue-600 text-white normal-case tracking-normal font-bold">Switch to live news</button></> : `LIVE EDITION / ${today}`}
          {!demoMode && <span className="block normal-case tracking-normal font-normal">Publisher RSS feeds: Hindustan Times, Economic Times, Mint, BBC, Bloomberg</span>}
        </div>
      </div>

      {actionError && <p className="mx-6 mt-4 p-2.5 rounded-lg border border-amber-200 bg-amber-50 text-xs text-amber-900">{actionError}</p>}

      {!demoMode && live.status === 'loading' && (
        <p className="px-6 py-10 text-sm text-gray-500 flex items-center gap-2"><Loader2 size={16} className="animate-spin" /> Loading the latest news…</p>
      )}
      {!demoMode && live.status === 'error' && (
        <div className="m-6 p-4 rounded-lg border border-red-200 bg-red-50 text-sm text-red-900 space-y-2">
          <p className="font-bold">Could not load live news: {live.error}</p>
          <button onClick={live.reload} className="px-3 py-1 rounded border border-red-200 bg-white text-xs font-semibold">Retry</button>
        </div>
      )}
      {!demoMode && live.status === 'ok' && !stories.length && (
        <p className="px-6 py-10 text-sm text-gray-500">No news yet. Log in and use Overview → Add events → Fetch live news.</p>
      )}

      {featured && (
        <div className="flex-1 px-6 py-6 max-w-[1440px] mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Column 1: featured story */}
          <div className="lg:col-span-5 flex flex-col border-b lg:border-b-0 lg:border-r border-gray-200 lg:pr-8 pb-6 lg:pb-0">
            <StoryImage s={featured} aspect="aspect-[16/10]" eager />
            <p className="text-[11px] text-gray-400 mt-2 mb-4 italic">
              {featured.kind === 'demo' ? 'Illustrative imagery (demo).' : featured.imageUrl ? `Image: ${featured.source ?? 'publisher'}` : ''}
            </p>
            <Meta s={featured} />
            <h3 className="text-3xl font-extrabold text-gray-950 mt-1 mb-3 tracking-tight leading-tight">{featured.title}</h3>
            {featured.summary && <p className="text-sm text-gray-600 leading-relaxed mb-4">{featured.summary}</p>}
            <Actions s={featured} />
          </div>

          {/* Column 2: two image stories */}
          <div className="lg:col-span-4 flex flex-col space-y-6 border-b lg:border-b-0 lg:border-r border-gray-200 lg:pr-8 pb-6 lg:pb-0">
            {[mid1, mid2].filter(Boolean).map((s, i) => (
              <div key={s!.key} className={`flex flex-col ${i ? 'border-t border-gray-200 pt-6' : ''}`}>
                <div className="mb-3"><StoryImage s={s!} aspect="aspect-video" /></div>
                <Meta s={s!} />
                <h4 className="text-lg font-bold text-gray-950 mt-1 mb-1.5 leading-snug">{s!.title}</h4>
                {s!.summary && <p className="text-xs text-gray-600 leading-relaxed mb-3 line-clamp-4">{s!.summary}</p>}
                <Actions s={s!} />
              </div>
            ))}
          </div>

          {/* Column 3: one image story + text stories */}
          <div className="lg:col-span-3 flex flex-col space-y-6">
            {right1 && (
              <div className="flex flex-col">
                <div className="mb-3"><StoryImage s={right1} aspect="aspect-[16/10]" /></div>
                <Meta s={right1} />
                <h4 className="text-base font-bold text-gray-950 mt-1 mb-1.5 leading-snug">{right1.title}</h4>
                {right1.summary && <p className="text-xs text-gray-600 leading-relaxed mb-3 line-clamp-4">{right1.summary}</p>}
                <Actions s={right1} />
              </div>
            )}
            {[right2, right3].filter(Boolean).map((s) => (
              <div key={s!.key} className="border-t border-gray-200 pt-5">
                <Meta s={s!} />
                <h4 className="text-base font-bold text-gray-950 mt-1 mb-1.5 leading-snug">{s!.title}</h4>
                {s!.summary && <p className="text-xs text-gray-600 leading-relaxed mb-3 line-clamp-3">{s!.summary}</p>}
                <Actions s={s!} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. More headlines */}
      {more.length > 0 && (
        <div className="px-6 pb-10 max-w-[1440px] mx-auto w-full">
          <h3 className="text-sm font-extrabold text-gray-950 border-t border-gray-200 pt-5 mb-3">More headlines</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-5">
            {more.slice(0, 18).map((s) => (
              <div key={s.key} className="flex gap-3">
                {s.imageUrl && <div className="w-24 flex-shrink-0"><StoryImage s={s} aspect="aspect-[16/10]" /></div>}
                <div className="min-w-0 space-y-1">
                  <Meta s={s} />
                  <p className="text-sm font-bold text-gray-950 leading-snug">{s.title}</p>
                  <Actions s={s} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <AuthModal />
    </div>
  );
};
