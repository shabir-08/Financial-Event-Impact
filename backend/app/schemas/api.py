"""Request/response schemas for the REST API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.market import DataGap, Freshness, Limitation, PriceBar

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorBody


# --------------------------------------------------------------------- health
class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    app_env: str
    database: Literal["ok", "unavailable"]
    database_error: str | None = None


class IntegrationStatus(BaseModel):
    provider: str
    configured: bool
    credentials_present: bool | None = None
    simulated: bool = False
    model: str | None = None
    notes: list[str] = []
    #: For LLM_PROVIDER=fallback: each chain member in order with its configuration state.
    chain: list[dict[str, Any]] = []


class IntegrationsResponse(BaseModel):
    llm: IntegrationStatus
    news: IntegrationStatus
    market_data: IntegrationStatus
    database: IntegrationStatus
    knowledge_base: dict[str, Any]


# ------------------------------------------------------------------- articles
class ArticleOut(ORM):
    id: str
    provider: str
    provider_article_id: str | None
    headline: str
    description: str | None
    content: str | None
    source_name: str | None
    source_domain: str | None
    url: str | None
    published_at: datetime | None
    retrieved_at: datetime
    language: str | None
    processing_status: str
    filter_reason: str | None
    is_simulated: bool
    input_origin: str
    error: dict[str, Any] | None = None
    image_url: str | None = None


class IngestRequest(BaseModel):
    provider: Literal["gdelt", "finnhub", "fixture", "rss"] | None = Field(
        None, description="Override NEWS_PROVIDER for this call. 'fixture' loads SIMULATED demo articles.")
    query: str | None = Field(None, max_length=500)
    limit: int = Field(25, ge=1, le=100)
    feeds: list[str] | None = Field(None, max_length=50, description="provider=rss only: feed keys to read (GET /api/articles/news-sources); default all")
    process: bool = Field(False, description="Run event detection on newly inserted articles (background).")
    analyze: bool = Field(True, description="When processing, also run full impact analysis for detected events.")


class IngestResponse(BaseModel):
    ingestion_run_id: str
    provider: str
    fetched: int
    inserted: int
    duplicates: int
    invalid: int
    article_ids: list[str]
    processing: Literal["not_requested", "scheduled"]
    notes: list[str] = []


class ProcessArticleResponse(BaseModel):
    article_id: str
    status: str
    event_id: str | None
    merged_into_existing: bool
    reason: str | None
    analysis_id: str | None


# --------------------------------------------------------------------- events
class LeadArticle(BaseModel):
    article_id: str
    headline: str
    source_name: str | None
    url: str | None
    published_at: datetime | None
    image_url: str | None
    provider: str
    is_simulated: bool


class EventSummary(ORM):
    id: str
    event_type: str
    title: str
    summary: str | None
    event_date: date | None
    first_reported_at: datetime | None
    countries: list[str]
    financial_relevance: float | None
    verification_status: str
    is_simulated: bool
    latest_analysis_id: str | None
    created_at: datetime
    lead_article: LeadArticle | None = None


class EventArticleOut(BaseModel):
    article: ArticleOut
    role: str
    supporting_passages: list[str]
    association_reason: str | None


class EventDetail(EventSummary):
    reported_figures: list[dict[str, Any]]
    primary_effects: list[dict[str, Any]]
    relevance_rationale: str | None
    extraction_version: str
    llm_provider: str
    llm_model: str | None
    processing_history: list[dict[str, Any]]
    articles: list[EventArticleOut] = []


class ManualEventRequest(BaseModel):
    """Controlled input for analysing explicitly supplied text (NOT the automated ingestion flow)."""

    headline: str = Field(min_length=10, max_length=1000)
    body: str = Field("", max_length=50_000)
    source_name: str | None = Field(None, max_length=255)
    url: HttpUrl | None = None
    published_at: datetime | None = None
    simulated: bool = Field(False, description="Mark the input as a simulated/test scenario.")
    skip_prefilter: bool = Field(True, description="Bypass the keyword pre-filter for supplied text.")
    wait: bool = Field(True, description="Run synchronously and return the finished analysis.")


class AnalyzeRequest(BaseModel):
    wait: bool = Field(False, description="Run synchronously instead of as a background job.")


class AnalysisAccepted(BaseModel):
    analysis_id: str | None
    event_id: str | None
    article_id: str | None = None
    status: str
    detail: str | None = None


class EntityMentionOut(ORM):
    id: str
    entity_id: str | None
    mention_text: str
    entity_type: str
    origin: str
    normalization_status: str
    normalization_method: str | None
    candidate_ids: list[str]
    evidence_passage: str | None
    passage_verified: bool
    extraction_confidence: float | None
    article_id: str | None


class EntitiesResponse(BaseModel):
    event_id: str
    analysis_id: str | None
    article_entities: list[EntityMentionOut]
    inferred_entities: list[EntityMentionOut]
    counts: dict[str, int]


class PathOut(BaseModel):
    id: str
    rank: int
    target_asset_id: str
    target_asset_name: str
    node_ids: list[str]
    node_labels: list[str]
    relationships: list[dict[str, Any]]
    path_score: float
    score_breakdown: dict[str, Any]
    impact_direction: str
    explanation: str
    uncertainties: list[str]


class AssetImpactOut(BaseModel):
    asset_id: str
    asset_name: str
    asset_type: str | None
    impact_direction: str
    best_path_score: float
    path_ids: list[str]
    mechanism: str
    uncertainty: list[str]
    market_data_status: str
    historical_comparison: dict[str, Any] | None
    observations: list[dict[str, Any]] = []


class PathsResponse(BaseModel):
    event_id: str
    analysis_id: str
    mode: str
    score_semantics: str = "Heuristic ranking scores in [0,1]; NOT probabilities of price movements."
    paths: list[PathOut]
    assets: list[AssetImpactOut]
    explanation: dict[str, Any] | None


class EvidenceResponse(BaseModel):
    event_id: str
    analysis_id: str | None
    articles: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    relationship_evidence: list[dict[str, Any]]


class AnalysisOut(BaseModel):
    id: str
    event_id: str | None
    article_id: str | None
    status: str
    mode: str
    trigger: str
    analysis_version: str
    knowledge_base_version: str | None
    llm_provider: str
    llm_model: str | None
    market_data_provider: str | None
    config: dict[str, Any]
    steps: list[dict[str, Any]]
    warnings: list[str]
    error: dict[str, Any] | None
    started_at: datetime | None
    finished_at: datetime | None
    graph_generated_at: datetime | None
    graph_stats: dict[str, Any] | None
    explanation_status: str | None
    explanation: dict[str, Any] | None
    top_assets: list[dict[str, Any]] = []


class AssetOut(BaseModel):
    id: str
    name: str
    asset_type: str
    currency: str | None
    country: str | None
    exchange: str | None
    exchange_timezone: str
    quote_semantics: str | None
    symbols: dict[str, str]


class AssetHistoryResponse(BaseModel):
    asset: AssetOut
    provider: str | None
    symbol: str | None
    status: Literal["AVAILABLE", "PARTIALLY_AVAILABLE", "UNAVAILABLE"]
    reason: str | None
    limitation: Limitation | None
    start: date
    end: date
    price_field: str | None
    simulated: bool
    retrieved_from_cache: bool
    latest_observation: PriceBar | None
    freshness: Freshness
    gaps: list[DataGap]
    calculation: dict[str, Any]
    bars: list[PriceBar]
