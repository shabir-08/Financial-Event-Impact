import React, { useState } from 'react';
import { DemoDataBanner } from '../../components/layout/DemoDataBanner';
import { useNavigate } from 'react-router-dom';
import { ArrowUpRight, ExternalLink, BookOpen, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Header } from '../../components/layout/Header';
import { useApp } from '../../context/AppContext';
import { DEMO_EVIDENCE_RELATIONSHIPS, DEMO_EVENTS } from '../../services/demoData';
import { RelationshipEvidenceItem } from '../../types/evidence';

export const DemoEvidencePage: React.FC = () => {
  const navigate = useNavigate();
  const { selectedEventId, setSelectedNodeId } = useApp();

  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string>('rel_fuel_airlines');
  const [showAllRelationships, setShowAllRelationships] = useState<boolean>(false);

  const currentEvent = DEMO_EVENTS.find((e) => e.id === selectedEventId) || DEMO_EVENTS[0];
  const activeRelationship =
    DEMO_EVIDENCE_RELATIONSHIPS.find((r) => r.id === selectedRelationshipId) ||
    DEMO_EVIDENCE_RELATIONSHIPS[1];

  const displayedRelationships = showAllRelationships
    ? DEMO_EVIDENCE_RELATIONSHIPS
    : DEMO_EVIDENCE_RELATIONSHIPS.slice(0, 5);

  const handleViewInGraph = () => {
    setSelectedNodeId('node_freight');
    navigate('/workspace');
  };

  return (
    <div className="flex-1 flex flex-col bg-[#F9FAFB]">
      <Header
        title={currentEvent.headline}
        tag="EVENT › EVIDENCE AND SOURCES"
        subtitle="Every link in the graph, with the text that supports it and where that text came from."
        showActions={true}
      />
      <DemoDataBanner reason="Demo mode is on (switch it off in Settings to see live backend data)." />

      {/* Advisory Banner matching reference */}
      <div className="bg-amber-50/70 border-b border-amber-200/80 px-6 py-2 text-xs text-amber-800 text-center font-medium">
        Layout inspiration only. Every headline, source, URL, passage and date here is illustrative; the real page renders backend responses only.
      </div>

      <div className="p-6 max-w-7xl mx-auto w-full space-y-6">
        {/* Legend Bar (Group By removed per reference) */}
        <div className="flex items-center justify-end border-b border-gray-200 pb-4">
          <div className="flex items-center space-x-4 text-[11px] text-gray-500">
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded-xs bg-blue-600"></span>
              <span>Extracted from an article</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded-xs bg-amber-500"></span>
              <span>Added from the knowledge base</span>
            </div>
          </div>
        </div>

        {/* Master-Detail Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Relationships List */}
          <div className="lg:col-span-4 bg-white border border-gray-200 rounded-xl overflow-hidden shadow-2xs">
            <div className="p-4 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between">
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block">
                RELATIONSHIPS IN THIS EVENT
              </span>
              <span className="text-[10px] font-semibold text-gray-400">
                {displayedRelationships.length} of {DEMO_EVIDENCE_RELATIONSHIPS.length}
              </span>
            </div>

            <div className="divide-y divide-gray-100 text-xs max-h-[700px] overflow-y-auto">
              {displayedRelationships.map((rel) => {
                const isSelected = rel.id === selectedRelationshipId;
                return (
                  <button
                    key={rel.id}
                    onClick={() => setSelectedRelationshipId(rel.id)}
                    className={`w-full p-4 text-left transition-all flex flex-col space-y-2 cursor-pointer ${
                      isSelected
                        ? 'bg-blue-50/50 border-l-4 border-blue-600'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <span className="font-bold text-gray-900">{rel.relationString}</span>

                    <div className="flex flex-wrap gap-1.5">
                      {rel.extractedCount > 0 && (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-blue-100 text-blue-700 font-semibold">
                          {rel.extractedCount} extracted
                        </span>
                      )}
                      {rel.knowledgeBaseCount > 0 && (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-amber-100 text-amber-800 font-semibold">
                          {rel.extractedCount > 0
                            ? `${rel.knowledgeBaseCount} knowledge base`
                            : 'Knowledge base only'}
                        </span>
                      )}
                      {rel.hasNoEvidence && (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-red-100 text-red-700 font-semibold">
                          No evidence
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              onClick={() => setShowAllRelationships((prev) => !prev)}
              className="w-full p-3 text-center border-t border-gray-100 text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50/50 font-semibold transition-colors flex items-center justify-center space-x-1 cursor-pointer"
            >
              <span>
                {showAllRelationships
                  ? 'Show top 5 relationships'
                  : `Show all ${DEMO_EVIDENCE_RELATIONSHIPS.length} relationships`}
              </span>
            </button>
          </div>

          {/* Right Column: Detailed Evidence Citations */}
          <div className="lg:col-span-8 space-y-6">
            {/* Relationship Header Card */}
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs">
              <div className="flex items-center justify-between pb-3 border-b border-gray-100">
                <div>
                  <h3 className="text-xl font-extrabold text-gray-950">
                    {activeRelationship.relationString}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1">
                    {activeRelationship.propagationPathDescription ||
                      `${activeRelationship.extractedCount} extracted, ${activeRelationship.knowledgeBaseCount} knowledge base`}
                  </p>
                </div>

                <button
                  onClick={handleViewInGraph}
                  className="flex items-center space-x-1.5 px-3 py-1.5 border border-blue-600 text-blue-600 hover:bg-blue-50 text-xs font-semibold rounded-lg transition-colors"
                >
                  <span>View in graph</span>
                  <ArrowUpRight size={14} />
                </button>
              </div>

              {/* Path Breadcrumbs */}
              {activeRelationship.pathTokens && (
                <div className="mt-3 flex items-center space-x-1.5 text-xs text-gray-600 font-medium">
                  <span className="text-gray-400">Path:</span>
                  {activeRelationship.pathTokens.map((token, i) => (
                    <React.Fragment key={i}>
                      <span className="px-2 py-0.5 bg-gray-100 rounded text-gray-800 font-mono text-[11px]">
                        {token}
                      </span>
                      {i < activeRelationship.pathTokens!.length - 1 && (
                        <span className="text-gray-400">&rarr;</span>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              )}
            </div>

            {/* EXTRACTED FROM ARTICLES SECTION */}
            {activeRelationship.extractedArticles.length > 0 && (
              <div className="space-y-4">
                <div>
                  <span className="text-[10px] font-bold text-blue-600 uppercase tracking-wider block">
                    EXTRACTED FROM ARTICLES
                  </span>
                  <p className="text-xs text-gray-500">Passages taken directly from the source text.</p>
                </div>

                {activeRelationship.extractedArticles.map((art) => (
                  <div
                    key={art.id}
                    className="bg-white border border-gray-200 rounded-xl p-5 shadow-2xs space-y-3.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-gray-800 uppercase tracking-wide">
                          {art.sourceOutlet}
                        </span>
                        <span className="text-gray-400">·</span>
                        <span className="text-gray-400 font-mono">{art.publishedAt}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700 font-bold border border-blue-200">
                          Extracted
                        </span>
                      </div>

                      <a
                        href={art.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center space-x-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-md shadow-2xs transition-colors"
                      >
                        <span>Open original</span>
                        <ExternalLink size={12} />
                      </a>
                    </div>

                    <h4 className="text-base font-bold text-gray-950">
                      {art.headline}
                    </h4>

                    <span className="text-[11px] font-mono text-gray-400 block truncate">
                      {art.url}
                    </span>

                    {/* Passage quote with entity highlighting */}
                    {art.passage ? (
                      <div className="p-3.5 bg-gray-50 border-l-4 border-blue-600 rounded-r-lg text-xs leading-relaxed text-gray-800 italic">
                        &ldquo;
                        {art.highlightedTokens
                          ? art.highlightedTokens.map((token, idx) =>
                              token.isEntity ? (
                                <mark
                                  key={idx}
                                  className="bg-blue-100 text-blue-900 font-semibold px-1 py-0.5 rounded not-italic"
                                >
                                  {token.text}
                                </mark>
                              ) : (
                                <span key={idx}>{token.text}</span>
                              )
                            )
                          : art.passage}
                        &rdquo;
                      </div>
                    ) : (
                      <div className="p-3 bg-amber-50/80 border border-amber-200 rounded-lg text-xs text-amber-900 leading-relaxed">
                        <strong className="font-bold block mb-0.5">Passage unavailable.</strong>
                        The backend did not return a supporting passage for this article, so none is shown. The article is listed because it was linked to this relationship; open the original to read it.
                      </div>
                    )}

                    <div className="pt-2 flex flex-wrap gap-2 text-[10px]">
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded">
                        Event: {art.eventTitle}
                      </span>
                      {art.relationshipLabel && (
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded font-semibold">
                          Relationship: {art.relationshipLabel}
                        </span>
                      )}
                      {art.entityLabel && (
                        <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded font-semibold">
                          Entity: {art.entityLabel}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* FROM ECONOMIC KNOWLEDGE BASE SECTION */}
            {activeRelationship.knowledgeBaseEntries.length > 0 && (
              <div className="space-y-4">
                <div>
                  <span className="text-[10px] font-bold text-amber-600 uppercase tracking-wider block">
                    FROM THE ECONOMIC KNOWLEDGE BASE
                  </span>
                  <p className="text-xs text-gray-500">
                    Background relationship added by the system. No article states this.
                  </p>
                </div>

                {activeRelationship.knowledgeBaseEntries.map((kb) => (
                  <div
                    key={kb.id}
                    className="bg-white border-2 border-dashed border-amber-200 rounded-xl p-5 shadow-2xs space-y-3"
                  >
                    <div className="flex items-center space-x-2 text-xs">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-amber-100 text-amber-800 font-bold">
                        Knowledge base
                      </span>
                      <span className="text-gray-400 font-mono text-[11px]">{kb.entryCode}</span>
                    </div>

                    <h4 className="text-base font-bold text-gray-900">{kb.title}</h4>

                    <p className="text-xs text-gray-600 leading-relaxed">{kb.rationale}</p>
                  </div>
                ))}
              </div>
            )}

            {/* A RELATIONSHIP WITH NO EVIDENCE SECTION */}
            {activeRelationship.hasNoEvidence && (
              <div className="space-y-4">
                <div>
                  <span className="text-[10px] font-bold text-red-600 uppercase tracking-wider block">
                    A RELATIONSHIP WITH NO EVIDENCE
                  </span>
                </div>

                <div className="bg-white border-2 border-dashed border-red-200 rounded-xl p-5 shadow-2xs space-y-3">
                  <div className="flex items-center space-x-2 text-xs">
                    <span className="font-bold text-gray-900 text-base">
                      {activeRelationship.relationString}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-red-50 text-red-700 font-bold border border-red-200">
                      No evidence
                    </span>
                  </div>

                  <p className="text-xs text-gray-600 leading-relaxed">
                    {activeRelationship.unsupportedMessage ||
                      'No article passages and no knowledge-base entries were returned for this relationship. Treat it as unsupported. Nothing has been written in to fill the gap.'}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Disclaimer footer */}
        <div className="pt-6 border-t border-gray-200 text-center text-[11px] text-gray-400">
          External links open in a new tab with rel=&quot;noopener noreferrer&quot;. Source passages are shown as extracted and never rewritten.
        </div>
      </div>
    </div>
  );
};
