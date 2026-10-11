"""Stage 2 of event detection plus extraction: article -> structured event, entities and claims.

Responsibilities:
* LLM-assisted classification of a pre-filtered article
* entity extraction + normalisation, relationship/claim extraction with passage verification
* associating the article with an existing event (same underlying event) or creating one
* persisting everything with extraction-version metadata so events can be reprocessed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.database.base import utcnow
from app.domain import ArticleStatus, EntityOrigin, VerificationStatus
from app.models import Article, Event, EventArticle, EventEntity, ExtractedClaim
from app.schemas.llm import EXTRACTION_VERSION, ArticleForLLM, EventClassification, LLMResult
from app.services.entities.extraction import NormalizedMention, normalize_extracted_entities
from app.services.entities.normalization import EntityNormalizer
from app.services.events.prefilter import prefilter_article
from app.services.llm.base import LLMProvider
from app.services.relationships.claims import EVENT, ClaimBuilder, ClaimDraft
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.text import jaccard, token_set, verify_passage

log = logging.getLogger(__name__)

MIN_FINANCIAL_RELEVANCE = 0.3
ASSOCIATION_HOURS = 48
ASSOCIATION_WINDOW = timedelta(hours=ASSOCIATION_HOURS)


@dataclass
class ProcessResult:
    article_id: str
    status: ArticleStatus
    event_id: str | None = None
    merged_into_existing: bool = False
    reason: str | None = None


def article_for_llm(article: Article) -> ArticleForLLM:
    body = "\n\n".join(p for p in (article.description, article.content) if p)
    return ArticleForLLM(
        article_id=article.id,
        headline=article.headline,
        text=body or "(no article body available from provider; analyse the headline only)",
        source_name=article.source_name,
        published_at=article.published_at.isoformat() if article.published_at else None,
    )


class EventProcessor:
    def __init__(self, session: Session, llm: LLMProvider, kb: KnowledgeBase) -> None:
        self.session = session
        self.llm = llm
        self.kb = kb
        self.normalizer = EntityNormalizer(kb)
        self.claims = ClaimBuilder(kb, self.normalizer)

    async def process_article(self, article_id: str, *, skip_prefilter: bool = False) -> ProcessResult:
        article = self.session.get(Article, article_id)
        if article is None:
            raise AppError(f"article {article_id} not found")
        existing_link = self.session.scalar(select(EventArticle).where(EventArticle.article_id == article.id))
        if existing_link is not None:
            return ProcessResult(article.id, ArticleStatus.PROCESSED, existing_link.event_id, reason="already processed")

        if not skip_prefilter:
            pf = prefilter_article(article, self.kb)
            article.prefilter_score = pf.score
            if not pf.passed:
                article.processing_status, article.filter_reason = ArticleStatus.FILTERED_OUT, pf.reason
                self.session.commit()
                return ProcessResult(article.id, ArticleStatus.FILTERED_OUT, reason=pf.reason)

        try:
            return await self._extract_and_store(article)
        except AppError as exc:
            self.session.rollback()
            article = self.session.get(Article, article_id)
            article.processing_status = ArticleStatus.FAILED
            article.error = exc.to_dict()
            self.session.commit()
            log.warning("Article %s failed: %s", article_id, exc.message)
            return ProcessResult(article_id, ArticleStatus.FAILED, reason=exc.message)

    async def _extract_and_store(self, article: Article) -> ProcessResult:
        payload = article_for_llm(article)
        source_text = f"{payload.headline}\n\n{payload.text}"
        cls_result = await self.llm.classify_event(payload)
        cls = cls_result.output
        if not cls.is_financial_event or cls.financial_relevance < MIN_FINANCIAL_RELEVANCE:
            article.processing_status = ArticleStatus.NOT_EVENT
            article.filter_reason = f"LLM: not a financial event (relevance {cls.financial_relevance:.2f})"
            article.extra = {**article.extra, "classification": cls.model_dump(mode="json"),
                             "classification_simulated": cls_result.simulated}
            self.session.commit()
            return ProcessResult(article.id, ArticleStatus.NOT_EVENT, reason=article.filter_reason)

        ent_result = await self.llm.extract_entities(payload, cls)
        mentions = normalize_extracted_entities(ent_result.output, self.normalizer, source_text)
        rel_result = await self.llm.extract_relationships(payload, cls, ent_result.output)
        drafts = self.claims.build(cls, rel_result.output, mentions, source_text)

        simulated = article.is_simulated or self.llm.simulated
        event, merged, reason = self._associate(article, cls, mentions, drafts, simulated, cls_result)
        history_entry = {
            "at": utcnow().isoformat(),
            "action": "merged_article" if merged else "created",
            "article_id": article.id,
            "extraction_version": EXTRACTION_VERSION,
            "llm_provider": self.llm.name,
            "llm_model": self.llm.model,
            "llm_simulated": self.llm.simulated,
            "article_simulated": article.is_simulated,
            "llm_attempts": [cls_result.attempts, ent_result.attempts, rel_result.attempts],
            "llm_served_by": {step: {"provider": r.provider, "model": r.model, "fallback_trail": r.fallback_trail}
                              for step, r in (("classification", cls_result), ("entities", ent_result),
                                              ("relationships", rel_result))},
            "association_reason": reason,
        }
        event.processing_history = [*event.processing_history, history_entry]

        passages = [p for p in cls.supporting_passages if verify_passage(p, source_text)]
        self.session.add(EventArticle(event_id=event.id, article_id=article.id,
                                      role="SUPPORTING" if merged else "PRIMARY",
                                      supporting_passages=passages, association_reason=reason))
        self._store_mentions(event, article, mentions)
        self._store_claims(event, article, drafts)
        self._refresh_verification(event)
        article.processing_status = ArticleStatus.PROCESSED
        article.error = None
        self.session.commit()
        return ProcessResult(article.id, ArticleStatus.PROCESSED, event.id, merged, reason)

    # ------------------------------------------------------------- association
    def _associate(
        self, article: Article, cls: EventClassification, mentions: list[NormalizedMention],
        drafts: list[ClaimDraft], simulated: bool, cls_result: LLMResult,
    ) -> tuple[Event, bool, str]:
        when = article.published_at or utcnow()
        effect_targets = {d.target_entity_id for d in drafts if d.source_entity_id == EVENT and d.target_entity_id}
        entity_ids = {m.entity_id for m in mentions if m.entity_id}
        candidates = self.session.scalars(
            select(Event).where(Event.event_type == cls.event_type.value, Event.is_simulated == simulated)
        ).all()
        for ev in candidates:
            ref = ev.first_reported_at
            if ref is not None and ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            if ref is not None and abs((_aware(when) - ref)) > ASSOCIATION_WINDOW:
                continue
            ev_targets = {e.get("node_id") for e in ev.primary_effects if e.get("node_id")}
            ev_entities = set(self.session.scalars(
                select(EventEntity.entity_id).where(EventEntity.event_id == ev.id, EventEntity.entity_id.is_not(None),
                                                   EventEntity.origin == EntityOrigin.ARTICLE)))
            effect_overlap = jaccard(effect_targets, ev_targets)
            entity_overlap = jaccard(entity_ids, ev_entities)
            title_overlap = jaccard(token_set(cls.title), token_set(ev.title))
            # Same type + time window are necessary; shared entities alone are NOT sufficient.
            if (effect_overlap >= 0.5 and entity_overlap >= 0.2) or title_overlap >= 0.6:
                self._merge_into(ev, article, cls, drafts)
                return ev, True, (f"same event_type and within {ASSOCIATION_HOURS}h; primary-effect overlap "
                                  f"{effect_overlap:.2f}, entity overlap {entity_overlap:.2f}, title overlap {title_overlap:.2f}")
        ev = Event(
            event_type=cls.event_type.value,
            title=cls.title[:1000],
            summary=cls.summary,
            event_date=_parse_date(cls.event_date) or (article.published_at.date() if article.published_at else None),
            first_reported_at=article.published_at,
            countries=sorted(set(cls.countries)),
            reported_figures=[f.model_dump() | {"passage_verified": verify_passage(f.passage, article.text_for_analysis),
                                                "article_id": article.id} for f in cls.reported_figures],
            primary_effects=self._effects_json(cls, drafts, article.id),
            financial_relevance=cls.financial_relevance,
            relevance_rationale=cls.relevance_rationale,
            is_simulated=simulated,
            extraction_version=EXTRACTION_VERSION,
            # The provider that actually produced the classification (matters for fallback chains).
            llm_provider=cls_result.provider,
            llm_model=cls_result.model,
            verification_status=VerificationStatus.SINGLE_SOURCE,
        )
        self.session.add(ev)
        self.session.flush()
        return ev, False, "no matching existing event; created new event"

    def _merge_into(self, ev: Event, article: Article, cls: EventClassification, drafts: list[ClaimDraft]) -> None:
        ev.countries = sorted(set(ev.countries) | set(cls.countries))
        known = {(e.get("node_id"), e.get("direction")) for e in ev.primary_effects}
        ev.primary_effects = ev.primary_effects + [
            e for e in self._effects_json(cls, drafts, article.id) if (e.get("node_id"), e.get("direction")) not in known
        ]
        if article.published_at and (ev.first_reported_at is None or _aware(article.published_at) < _aware(ev.first_reported_at)):
            ev.first_reported_at = article.published_at

    def _effects_json(self, cls: EventClassification, drafts: list[ClaimDraft], article_id: str) -> list[dict]:
        out = []
        for d in drafts:
            if d.source_entity_id == EVENT and d.is_primary_effect:
                out.append({"mention": d.target_mention, "node_id": d.target_entity_id,
                            "direction": {1: "UP", -1: "DOWN"}.get(d.effect_sign, "UNCLEAR"),
                            "passage": d.passage, "passage_verified": d.passage_verified, "article_id": article_id})
        return out

    # ------------------------------------------------------------- persistence
    def _store_mentions(self, event: Event, article: Article, mentions: list[NormalizedMention]) -> None:
        for m in mentions:
            self.session.add(EventEntity(
                event_id=event.id, article_id=article.id, entity_id=m.entity_id, mention_text=m.mention,
                entity_type=m.entity_type, origin=EntityOrigin.ARTICLE, normalization_status=m.status,
                normalization_method=m.method, candidate_ids=m.candidates, evidence_passage=m.passage,
                passage_verified=m.passage_verified, extraction_confidence=m.confidence,
                extraction_version=EXTRACTION_VERSION,
            ))

    def _store_claims(self, event: Event, article: Article, drafts: list[ClaimDraft]) -> None:
        for d in drafts:
            self.session.add(ExtractedClaim(
                event_id=event.id, article_id=article.id, source_mention=d.source_mention[:500],
                target_mention=d.target_mention[:500], source_entity_id=d.source_entity_id,
                target_entity_id=d.target_entity_id, relationship_type=d.relationship_type.value,
                effect_sign=d.effect_sign, mechanism=d.mechanism, passage=d.passage,
                passage_verified=d.passage_verified, extraction_confidence=d.confidence,
                is_primary_effect=d.is_primary_effect, extraction_version=EXTRACTION_VERSION,
            ))

    def _refresh_verification(self, event: Event) -> None:
        self.session.flush()
        arts = self.session.scalars(
            select(Article).join(EventArticle, EventArticle.article_id == Article.id).where(EventArticle.event_id == event.id)
        ).all()
        if any(a.is_simulated for a in arts):
            event.verification_status = VerificationStatus.SIMULATED
        elif any(a.input_origin == "USER_SUPPLIED" for a in arts):
            event.verification_status = VerificationStatus.USER_SUPPLIED
        else:
            domains = {a.source_domain for a in arts if a.source_domain}
            event.verification_status = (
                VerificationStatus.CORROBORATED if len(domains) >= 2 else VerificationStatus.SINGLE_SOURCE
            )


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
