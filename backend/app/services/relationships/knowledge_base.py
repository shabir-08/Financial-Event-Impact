"""Reusable economic relationship knowledge base, loaded from JSON seed files.

The knowledge base is data-driven: adding a relationship, entity or asset means editing
``data/knowledge_base``; graph algorithms never hardcode economic relationships.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.config import DATA_DIR
from app.domain import AssetType, EntityType, EventType, RelationshipType

EvidenceBasis = Literal["ESTABLISHED_MECHANISM", "EMPIRICAL_ASSOCIATION", "CONTESTED", "INSTRUMENT_DEFINITION"]


class KBConditions(BaseModel):
    event_types: list[EventType] | None = None
    # Hard conditions: the rule is NOT applied unless satisfied.
    requires_entities_any: list[str] = []
    requires_entities_all: list[str] = []
    # Soft condition: rule applies, but with reduced applicability if none are present.
    context_entities_any: list[str] = []
    note: str = ""


class KBRule(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: RelationshipType
    effect_sign: Literal[-1, 0, 1]
    mechanism: str
    conditions: KBConditions = KBConditions()
    time_horizon: str | None = None
    rationale: str = ""
    reliability: float = Field(ge=0, le=1)
    economic_relevance: float = Field(ge=0, le=1)
    evidence_basis: EvidenceBasis = "ESTABLISHED_MECHANISM"
    kind: Literal["RELATIONSHIP", "ASSET_EXPOSURE"] = "RELATIONSHIP"


class EventTrigger(BaseModel):
    id: str
    event_types: list[EventType]
    requires_entities_any: list[str] = []
    requires_entities_all: list[str] = []
    target: str
    relationship_type: RelationshipType
    sign_source: Literal["FIXED", "PRIMARY_EFFECT"]
    effect_sign: Literal[-1, 0, 1] = 0
    primary_effect_variable: str | None = None
    mechanism: str
    reliability: float = Field(ge=0, le=1)
    economic_relevance: float = Field(ge=0, le=1)
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> "EventTrigger":
        if self.sign_source == "PRIMARY_EFFECT" and not self.primary_effect_variable:
            raise ValueError(f"trigger {self.id}: PRIMARY_EFFECT requires primary_effect_variable")
        return self


class CatalogEntity(BaseModel):
    id: str
    type: EntityType
    name: str
    aliases: list[str] = []
    external_ids: dict[str, str] = {}
    effect_variable: str | None = None
    country: str | None = None


class AssetExposure(BaseModel):
    source: str
    relationship_type: RelationshipType
    effect_sign: Literal[-1, 0, 1]
    mechanism: str
    reliability: float = Field(ge=0, le=1)
    economic_relevance: float = Field(ge=0, le=1)


class AssetSpec(BaseModel):
    id: str
    name: str
    asset_type: AssetType
    currency: str | None = None
    country: str | None = None
    exchange: str | None = None
    exchange_timezone: str = "UTC"
    aliases: list[str] = []
    quote_semantics: str | None = None
    symbols: dict[str, str] = {}
    exposures: list[AssetExposure] = []

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MARKET_INDEX if self.asset_type == AssetType.INDEX else EntityType.FINANCIAL_INSTRUMENT


class HistoricalEventSpec(BaseModel):
    id: str
    event_type: EventType
    event_date: str
    title: str
    entity_ids: list[str] = []
    primary_effects: list[dict[str, str]] = []


class KnowledgeBase:
    def __init__(
        self,
        rules: list[KBRule],
        triggers: list[EventTrigger],
        entities: list[CatalogEntity],
        assets: list[AssetSpec],
        historical_events: list[HistoricalEventSpec],
        categories: dict,
        source_quality: dict,
        version: str,
    ) -> None:
        self.entities = {e.id: e for e in entities}
        self.assets = {a.id: a for a in assets}
        self.triggers = triggers
        self.historical_events = historical_events
        self.categories = categories
        self.source_quality = source_quality
        self.version = version

        exposure_rules = []
        for asset in assets:
            for i, exp in enumerate(asset.exposures):
                exposure_rules.append(
                    KBRule(
                        id=f"kb.exposure.{asset.id.split(':', 1)[1]}.{i}",
                        source=exp.source,
                        target=asset.id,
                        relationship_type=exp.relationship_type,
                        effect_sign=exp.effect_sign,
                        mechanism=exp.mechanism,
                        rationale=f"Asset exposure declared in the asset catalog for {asset.name}.",
                        reliability=exp.reliability,
                        economic_relevance=exp.economic_relevance,
                        evidence_basis="INSTRUMENT_DEFINITION"
                        if exp.relationship_type == RelationshipType.ASSOCIATED_WITH
                        else "EMPIRICAL_ASSOCIATION",
                        kind="ASSET_EXPOSURE",
                    )
                )
        self.rules = {r.id: r for r in [*rules, *exposure_rules]}
        self._by_source: dict[str, list[KBRule]] = defaultdict(list)
        for r in self.rules.values():
            self._by_source[r.source].append(r)
        self._validate_references()

    # ------------------------------------------------------------------ queries
    def node_exists(self, node_id: str) -> bool:
        return node_id in self.entities or node_id in self.assets

    def outgoing(self, node_id: str) -> list[KBRule]:
        return list(self._by_source.get(node_id, []))

    def is_asset(self, node_id: str) -> bool:
        return node_id in self.assets

    def node_label(self, node_id: str) -> str:
        if node_id in self.entities:
            return self.entities[node_id].name
        if node_id in self.assets:
            return self.assets[node_id].name
        return node_id

    def node_type(self, node_id: str) -> str:
        if node_id in self.entities:
            return self.entities[node_id].type.value
        if node_id in self.assets:
            return self.assets[node_id].entity_type.value
        return "UNKNOWN"

    def effect_variable(self, node_id: str) -> str | None:
        e = self.entities.get(node_id)
        return e.effect_variable if e else None

    def source_quality_for(self, domain: str | None) -> tuple[float, bool]:
        """Return (quality, assessed). Unknown domains get the neutral default, flagged unassessed."""
        default = float(self.source_quality.get("default_unassessed", 0.6))
        if not domain:
            return default, False
        tiers: dict[str, float] = self.source_quality.get("tiers", {})
        d = domain.lower().removeprefix("www.")
        for known, q in tiers.items():
            if d == known or d.endswith("." + known):
                return float(q), True
        return default, False

    # --------------------------------------------------------------- validation
    def _validate_references(self) -> None:
        problems = []
        for r in self.rules.values():
            for end in (r.source, r.target):
                if not self.node_exists(end):
                    problems.append(f"rule {r.id} references unknown node {end}")
            for ref in [*r.conditions.requires_entities_any, *r.conditions.requires_entities_all,
                        *r.conditions.context_entities_any]:
                if not self.node_exists(ref):
                    problems.append(f"rule {r.id} condition references unknown node {ref}")
        for t in self.triggers:
            for ref in [t.target, *t.requires_entities_any, *t.requires_entities_all]:
                if not self.node_exists(ref):
                    problems.append(f"trigger {t.id} references unknown node {ref}")
        for e in self.entities.values():
            if e.effect_variable and e.effect_variable not in self.entities:
                problems.append(f"entity {e.id} effect_variable {e.effect_variable} unknown")
        for h in self.historical_events:
            for ref in [*h.entity_ids, *(p["variable"] for p in h.primary_effects)]:
                if not self.node_exists(ref):
                    problems.append(f"historical event {h.id} references unknown node {ref}")
        if problems:
            raise ValueError("Knowledge base validation failed:\n" + "\n".join(problems))


def load_knowledge_base(directory: Path | None = None) -> KnowledgeBase:
    kb_dir = directory or DATA_DIR / "knowledge_base"
    files = sorted(kb_dir.rglob("*.json"))
    digest = hashlib.sha256()
    for f in files:
        digest.update(f.name.encode())
        digest.update(f.read_bytes())

    def read(name: str) -> dict:
        return json.loads((kb_dir / name).read_text(encoding="utf-8"))

    rules: list[KBRule] = []
    for f in sorted((kb_dir / "relationships").glob("*.json")):
        rules.extend(KBRule.model_validate(r) for r in json.loads(f.read_text(encoding="utf-8"))["rules"])
    ids = [r.id for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate knowledge-base rule ids")

    return KnowledgeBase(
        rules=rules,
        triggers=[EventTrigger.model_validate(t) for t in read("event_triggers.json")["triggers"]],
        entities=[CatalogEntity.model_validate(e) for e in read("entities.json")["entities"]],
        assets=[AssetSpec.model_validate(a) for a in read("assets.json")["assets"]],
        historical_events=[HistoricalEventSpec.model_validate(h) for h in read("historical_events.json")["events"]],
        categories=read("event_categories.json"),
        source_quality=read("source_quality.json"),
        version=digest.hexdigest()[:16],
    )


@lru_cache
def get_knowledge_base() -> KnowledgeBase:
    return load_knowledge_base()
