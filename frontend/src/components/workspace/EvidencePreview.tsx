import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, BookOpen, ExternalLink, ShieldCheck } from 'lucide-react';

interface EvidencePreviewItem {
  id: number;
  title: string;
  sourceOutlet: string;
  publishedAt: string;
  url: string;
  tag: string;
  passageSnippet: string;
}

export const EvidencePreview: React.FC = () => {
  const navigate = useNavigate();

  // Top three evidence items with source titles, URLs, and metadata
  const evidenceItems: EvidencePreviewItem[] = [
    {
      id: 1,
      title: 'Carriers brace for higher fuel bills after crude surge',
      sourceOutlet: 'EXAMPLE NEWSWIRE',
      publishedAt: '14 Sep 2026, 08:42 IST',
      url: 'https://news.example.com/markets/2026/09/14/carriers-fuel-bills',
      tag: 'ARTICLE EXTRACT',
      passageSnippet: 'Jet fuel costs rose sharply as Brent jumped 12%, with carriers warning of margin compression...',
    },
    {
      id: 2,
      title: 'Containerships divert around Cape of Good Hope as strait closure enters Day 4',
      sourceOutlet: 'MARITIME INTELLIGENCE WEEKLY',
      publishedAt: '15 Sep 2026, 09:15 UTC',
      url: 'https://shipping.example.com/analysis/2026/09/cape-rerouting',
      tag: 'LOGISTICS BRIEF',
      passageSnippet: 'Liners vectoring ultra-large vessels around southern Africa add 3,500 nautical miles and 10-14 sea days...',
    },
    {
      id: 3,
      title: 'Spot container benchmark jumps 18% as extended sea voyages absorb capacity',
      sourceOutlet: 'GLOBAL LOGISTICS MONITOR',
      publishedAt: '15 Sep 2026, 14:30 UTC',
      url: 'https://logistics.example.org/freight/spot-index-surge',
      tag: 'BENCHMARK DATA',
      passageSnippet: 'World Container Index rose 18% as longer voyages absorbed ~9% of active global TEU capacity...',
    },
  ];

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-gray-100">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-blue-50 text-blue-600">
            <BookOpen size={16} />
          </div>
          <div>
            <h3 className="text-xs font-extrabold text-gray-900 tracking-tight">
              Top Evidence & Sources
            </h3>
            <p className="text-[11px] text-gray-500 font-medium">
              Source passages supporting active graph causal relationships
            </p>
          </div>
        </div>
        <button
          onClick={() => navigate('/evidence')}
          className="group text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors inline-flex items-center cursor-pointer"
        >
          <span>View All Sources</span>
          <ArrowRight size={13} className="ml-1 transition-transform group-hover:translate-x-1" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        {evidenceItems.map((item) => (
          <div
            key={item.id}
            onClick={() => navigate('/evidence')}
            className="p-3.5 rounded-lg border border-gray-200/80 bg-gray-50/50 hover:bg-white hover:border-blue-300 hover:shadow-2xs transition-all flex flex-col justify-between space-y-2.5 cursor-pointer"
          >
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-[10px]">
                <span className="font-mono font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                  Item #{item.id}
                </span>
                <span className="font-mono text-gray-400 font-medium">
                  {item.sourceOutlet}
                </span>
              </div>

              <h4 className="font-bold text-gray-950 leading-snug line-clamp-2">
                {item.title}
              </h4>

              <p className="text-[11px] text-gray-600 leading-relaxed italic line-clamp-2">
                &ldquo;{item.passageSnippet}&rdquo;
              </p>
            </div>

            <div className="pt-2 border-t border-gray-200/60 flex items-center justify-between text-[10px] text-gray-400">
              <span className="font-mono">{item.publishedAt}</span>
              <span className="text-blue-600 font-bold flex items-center space-x-0.5">
                <span>View</span>
                <ExternalLink size={10} />
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
