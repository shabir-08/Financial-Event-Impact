"""Idempotently mirror the JSON knowledge-base catalog (entities, assets, symbols, reference
historical events) into PostgreSQL so APIs and joins can use stable ids."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, AssetSymbol, Entity, HistoricalEvent
from app.services.relationships.knowledge_base import KnowledgeBase


def seed_catalog(session: Session, kb: KnowledgeBase) -> dict[str, int]:
    counts = {"entities": 0, "assets": 0, "symbols": 0, "historical_events": 0}
    existing_entities = {e.id: e for e in session.scalars(select(Entity)).all()}
    for e in kb.entities.values():
        row = existing_entities.get(e.id) or Entity(id=e.id)
        row.entity_type, row.display_name, row.canonical_name = e.type.value, e.name, e.name
        row.aliases, row.external_ids, row.country, row.effect_variable = e.aliases, e.external_ids, e.country, e.effect_variable
        row.source = "KNOWLEDGE_BASE"
        if e.id not in existing_entities:
            session.add(row)
            counts["entities"] += 1
    for a in kb.assets.values():
        ent = existing_entities.get(a.id) or Entity(id=a.id)
        ent.entity_type, ent.display_name, ent.canonical_name = a.entity_type.value, a.name, a.name
        ent.aliases, ent.country, ent.source = a.aliases, a.country, "KNOWLEDGE_BASE"
        ent.extra = {"asset_type": a.asset_type.value}
        if a.id not in existing_entities:
            session.add(ent)
            counts["entities"] += 1
    session.flush()

    existing_assets = {a.id: a for a in session.scalars(select(Asset)).all()}
    for a in kb.assets.values():
        row = existing_assets.get(a.id) or Asset(id=a.id)
        row.asset_type, row.name, row.currency, row.country = a.asset_type.value, a.name, a.currency, a.country
        row.exchange, row.exchange_timezone, row.quote_semantics = a.exchange, a.exchange_timezone, a.quote_semantics
        if a.id not in existing_assets:
            session.add(row)
            counts["assets"] += 1
    session.flush()

    existing_symbols = {(s.asset_id, s.provider): s for s in session.scalars(select(AssetSymbol)).all()}
    for a in kb.assets.values():
        for provider, symbol in a.symbols.items():
            row = existing_symbols.get((a.id, provider))
            if row is None:
                session.add(AssetSymbol(asset_id=a.id, provider=provider, symbol=symbol))
                counts["symbols"] += 1
            else:
                row.symbol = symbol

    existing_hist = set(session.scalars(select(HistoricalEvent.id)).all())
    for h in kb.historical_events:
        if h.id in existing_hist:
            continue
        session.add(HistoricalEvent(
            id=h.id, event_type=h.event_type.value, title=h.title, event_date=date.fromisoformat(h.event_date),
            entity_ids=h.entity_ids, primary_effects=h.primary_effects, source_type="CURATED_REFERENCE",
            verification_note="Hand-curated reference event; verify date and details before relying on it.",
        ))
        counts["historical_events"] += 1
    session.commit()
    return counts
