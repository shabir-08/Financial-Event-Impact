"""SQLAlchemy models. Importing this package registers every table on ``Base.metadata``."""

from app.models.analysis import (
    AnalysisRun,
    AssetImpact,
    ExtractedClaim,
    GraphNode,
    ImpactPath,
    MarketData,
    MarketObservation,
    Relationship,
    RelationshipEvidence,
)
from app.models.entities import Asset, AssetSymbol, Entity, EventEntity
from app.models.events import Event, EventArticle, HistoricalEvent
from app.models.news import Article, IngestionRun

__all__ = [
    "AnalysisRun",
    "Article",
    "Asset",
    "AssetImpact",
    "AssetSymbol",
    "Entity",
    "Event",
    "EventArticle",
    "EventEntity",
    "ExtractedClaim",
    "GraphNode",
    "HistoricalEvent",
    "ImpactPath",
    "IngestionRun",
    "MarketData",
    "MarketObservation",
    "Relationship",
    "RelationshipEvidence",
]
