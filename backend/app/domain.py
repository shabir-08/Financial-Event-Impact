"""Domain vocabulary shared by models, schemas and services."""

from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    MONETARY_POLICY = "MONETARY_POLICY"
    INTEREST_RATE_CHANGE = "INTEREST_RATE_CHANGE"
    INFLATION = "INFLATION"
    GDP_GROWTH = "GDP_GROWTH"
    EMPLOYMENT = "EMPLOYMENT"
    COMMODITY_PRICE_CHANGE = "COMMODITY_PRICE_CHANGE"
    ENERGY_SUPPLY = "ENERGY_SUPPLY"
    GEOPOLITICAL = "GEOPOLITICAL"
    WAR_CONFLICT = "WAR_CONFLICT"
    SANCTIONS = "SANCTIONS"
    TARIFF_TRADE = "TARIFF_TRADE"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"
    CORPORATE_EARNINGS = "CORPORATE_EARNINGS"
    MERGER_ACQUISITION = "MERGER_ACQUISITION"
    CORPORATE_ANNOUNCEMENT = "CORPORATE_ANNOUNCEMENT"
    BANKING_CREDIT = "BANKING_CREDIT"
    GOVERNMENT_POLICY = "GOVERNMENT_POLICY"
    FINANCIAL_REGULATION = "FINANCIAL_REGULATION"
    SOVEREIGN_DEBT = "SOVEREIGN_DEBT"
    CURRENCY_MARKET = "CURRENCY_MARKET"
    MARKET_DISRUPTION = "MARKET_DISRUPTION"
    OTHER = "OTHER"


class EntityType(StrEnum):
    EVENT = "EVENT"
    COMPANY = "COMPANY"
    COMMODITY = "COMMODITY"
    SECTOR = "SECTOR"
    ECONOMIC_INDICATOR = "ECONOMIC_INDICATOR"
    ECONOMIC_VARIABLE = "ECONOMIC_VARIABLE"
    FINANCIAL_INSTRUMENT = "FINANCIAL_INSTRUMENT"
    MARKET_INDEX = "MARKET_INDEX"
    INSTITUTION = "INSTITUTION"
    COUNTRY = "COUNTRY"
    REGION = "REGION"
    CURRENCY = "CURRENCY"


class AssetType(StrEnum):
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    ETF = "ETF"
    COMMODITY = "COMMODITY"
    CURRENCY_PAIR = "CURRENCY_PAIR"
    GOVERNMENT_BOND = "GOVERNMENT_BOND"
    BOND = "BOND"
    FUTURE = "FUTURE"


class RelationshipType(StrEnum):
    INCREASES = "INCREASES"
    REDUCES = "REDUCES"
    MAY_INCREASE = "MAY_INCREASE"
    MAY_REDUCE = "MAY_REDUCE"
    INFLUENCES = "INFLUENCES"
    MAY_INFLUENCE = "MAY_INFLUENCE"
    EXPOSES_TO = "EXPOSES_TO"
    AFFECTS_PROFITABILITY_OF = "AFFECTS_PROFITABILITY_OF"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    OBSERVED_TO_MOVE_WITH = "OBSERVED_TO_MOVE_WITH"


# Default sign implied by a relationship type when no explicit sign is given.
RELATIONSHIP_DEFAULT_SIGN: dict[RelationshipType, int] = {
    RelationshipType.INCREASES: 1,
    RelationshipType.MAY_INCREASE: 1,
    RelationshipType.REDUCES: -1,
    RelationshipType.MAY_REDUCE: -1,
}


class EdgeDirection(StrEnum):
    """Sign of the effect along an edge: source up -> target up (POSITIVE) etc."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"

    @classmethod
    def from_sign(cls, sign: int) -> "EdgeDirection":
        return {1: cls.POSITIVE, -1: cls.NEGATIVE}.get(sign, cls.CONTEXT_DEPENDENT)

    @property
    def sign(self) -> int:
        return {EdgeDirection.POSITIVE: 1, EdgeDirection.NEGATIVE: -1}.get(self, 0)


class EdgeStatus(StrEnum):
    REPORTED = "REPORTED"  # stated in a source article, passage verified
    OBSERVED = "OBSERVED"  # measured in market data
    INFERRED = "INFERRED"  # derived from the economic knowledge base
    UNVERIFIED = "UNVERIFIED"  # claimed by extraction but evidence could not be verified


class RelationshipOrigin(StrEnum):
    ARTICLE = "ARTICLE"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"
    EVENT_TRIGGER = "EVENT_TRIGGER"
    MARKET_DATA = "MARKET_DATA"


class MoveDirection(StrEnum):
    UP = "UP"
    DOWN = "DOWN"
    UNCHANGED = "UNCHANGED"
    UNCLEAR = "UNCLEAR"

    @property
    def sign(self) -> int:
        return {MoveDirection.UP: 1, MoveDirection.DOWN: -1}.get(self, 0)


class ImpactDirection(StrEnum):
    POTENTIAL_UPWARD_PRESSURE = "POTENTIAL_UPWARD_PRESSURE"
    POTENTIAL_DOWNWARD_PRESSURE = "POTENTIAL_DOWNWARD_PRESSURE"
    DIRECTION_UNCERTAIN = "DIRECTION_UNCERTAIN"
    MIXED_SIGNALS = "MIXED_SIGNALS"

    @classmethod
    def from_sign(cls, sign: int) -> "ImpactDirection":
        return {1: cls.POTENTIAL_UPWARD_PRESSURE, -1: cls.POTENTIAL_DOWNWARD_PRESSURE}.get(
            sign, cls.DIRECTION_UNCERTAIN
        )


class NormalizationStatus(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class EntityOrigin(StrEnum):
    ARTICLE = "ARTICLE"  # explicitly mentioned in a source article
    INFERRED = "INFERRED"  # introduced by economic inference


class ArticleStatus(StrEnum):
    PENDING = "PENDING"
    FILTERED_OUT = "FILTERED_OUT"
    NOT_EVENT = "NOT_EVENT"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class VerificationStatus(StrEnum):
    SINGLE_SOURCE = "SINGLE_SOURCE"
    CORROBORATED = "CORROBORATED"  # >= 2 distinct source domains
    USER_SUPPLIED = "USER_SUPPLIED"
    SIMULATED = "SIMULATED"


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class RunMode(StrEnum):
    LIVE = "LIVE"  # real LLM provider
    SIMULATED = "SIMULATED"  # mock LLM provider and/or fixture data


class DataAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIALLY_AVAILABLE = "PARTIALLY_AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
