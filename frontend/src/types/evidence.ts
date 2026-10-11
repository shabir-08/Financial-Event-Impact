export type EvidenceGroupBy = 'Event' | 'Entity' | 'Relationship' | 'Propagation path';

export type EvidenceOrigin = 'extracted' | 'knowledge_base' | 'unsupported';

export interface HighlightedEntity {
  text: string;
  isEntity: boolean;
}

export interface ExtractedArticle {
  id: string;
  sourceOutlet: string;
  publishedAt: string;
  headline: string;
  url: string;
  passage: string | null; // null if passage unavailable
  highlightedTokens?: HighlightedEntity[];
  eventTitle: string;
  relationshipLabel?: string;
  entityLabel?: string;
}

export interface KnowledgeBaseEntry {
  id: string;
  entryCode: string;
  title: string;
  relationshipType: string;
  rationale: string;
}

export interface RelationshipEvidenceItem {
  id: string;
  sourceLabel: string;
  targetLabel: string;
  relationString: string; // e.g. "Fuel costs → Airlines"
  extractedCount: number;
  knowledgeBaseCount: number;
  hasNoEvidence: boolean;
  propagationPathDescription?: string;
  pathTokens?: string[];
  extractedArticles: ExtractedArticle[];
  knowledgeBaseEntries: KnowledgeBaseEntry[];
  unsupportedMessage?: string;
}
