"""Decide whether a knowledge-base rule or event trigger applies to the current event."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.relationships.knowledge_base import EventTrigger, KBRule

#: Applicability when a rule's soft context entities are all absent from the event.
SOFT_CONTEXT_MISSING_FACTOR = 0.7


@dataclass
class EventContext:
    event_type: str
    #: Resolved node ids explicitly mentioned in the event's articles (plus their effect variables).
    entity_ids: set[str]
    #: node_id -> sign (+1/-1/0) for primary effects reported by the articles.
    primary_effects: dict[str, int] = field(default_factory=dict)


@dataclass
class Applicability:
    applicable: bool
    factor: float
    reasons: list[str]


def evaluate_rule(rule: KBRule, ctx: EventContext) -> Applicability:
    c = rule.conditions
    if c.event_types and ctx.event_type not in {t.value for t in c.event_types}:
        return Applicability(False, 0.0, [f"event type {ctx.event_type} not in {[t.value for t in c.event_types]}"])
    if c.requires_entities_any and not (set(c.requires_entities_any) & ctx.entity_ids):
        return Applicability(False, 0.0, [f"requires one of {c.requires_entities_any}; none mentioned"])
    missing = [e for e in c.requires_entities_all if e not in ctx.entity_ids]
    if missing:
        return Applicability(False, 0.0, [f"requires all of {c.requires_entities_all}; missing {missing}"])
    reasons: list[str] = []
    factor = 1.0
    if c.context_entities_any:
        if set(c.context_entities_any) & ctx.entity_ids:
            reasons.append("context entities present in event")
        else:
            factor = SOFT_CONTEXT_MISSING_FACTOR
            reasons.append(f"none of the context entities {c.context_entities_any} mentioned; applicability reduced")
    if c.note:
        reasons.append(f"condition: {c.note}")
    return Applicability(True, factor, reasons)


@dataclass
class TriggerDecision:
    applicable: bool
    sign: int
    reasons: list[str]


def evaluate_trigger(trigger: EventTrigger, ctx: EventContext) -> TriggerDecision:
    if ctx.event_type not in {t.value for t in trigger.event_types}:
        return TriggerDecision(False, 0, ["event type does not match"])
    if trigger.requires_entities_any and not (set(trigger.requires_entities_any) & ctx.entity_ids):
        return TriggerDecision(False, 0, [f"requires one of {trigger.requires_entities_any}"])
    missing = [e for e in trigger.requires_entities_all if e not in ctx.entity_ids]
    if missing:
        return TriggerDecision(False, 0, [f"missing required entities {missing}"])
    if trigger.sign_source == "FIXED":
        return TriggerDecision(True, trigger.effect_sign, [trigger.note] if trigger.note else [])
    sign = ctx.primary_effects.get(trigger.primary_effect_variable or "", 0)
    reason = ("direction taken from the article's reported primary effect" if sign
              else "articles did not report a direction for this variable; treated as context-dependent")
    return TriggerDecision(True, sign, [reason])
