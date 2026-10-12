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
from app.models.lineage import EventImpact, EventLink, EventNode
from app.models.news import Article, IngestionRun
from app.models.report import AnalysisReport
from app.models.saved import SavedAnalysis
from app.models.simulation import SimulationRun

__all__ = [
    "AnalysisReport",
    "AnalysisRun",
    "Article",
    "Asset",
    "AssetImpact",
    "AssetSymbol",
    "Entity",
    "Event",
    "EventArticle",
    "EventEntity",
    "EventImpact",
    "EventLink",
    "EventNode",
    "ExtractedClaim",
    "GraphNode",
    "HistoricalEvent",
    "ImpactPath",
    "IngestionRun",
    "MarketData",
    "MarketObservation",
    "Relationship",
    "RelationshipEvidence",
    "SavedAnalysis",
    "SimulationRun",
]
