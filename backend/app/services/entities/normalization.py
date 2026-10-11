"""Entity normalisation: map extracted mentions to canonical ids only when identity is clear.

Policy (deliberately conservative):
* exact canonical id or exact alias match (case/whitespace-insensitive) -> RESOLVED
* several matching entities -> AMBIGUOUS (candidates kept, nothing chosen)
* alias match only on an entity of an incompatible type -> AMBIGUOUS
* no exact match -> UNRESOLVED; fuzzy matches are stored as *suggestions* only
No tickers are ever guessed: assets resolve only via catalog aliases/ids.
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.domain import EntityType, NormalizationStatus
from app.services.relationships.knowledge_base import KnowledgeBase
from app.services.text import normalize_alias

_TYPE_GROUPS: list[set[EntityType]] = [
    {EntityType.COMPANY},
    {EntityType.FINANCIAL_INSTRUMENT, EntityType.MARKET_INDEX},
    {EntityType.ECONOMIC_VARIABLE, EntityType.ECONOMIC_INDICATOR},
    {EntityType.COMMODITY},
    {EntityType.COUNTRY, EntityType.REGION},
    {EntityType.CURRENCY},
    {EntityType.INSTITUTION},
    {EntityType.SECTOR},
]


def _compatible(a: EntityType, b: EntityType) -> bool:
    if a == b:
        return True
    return any(a in g and b in g for g in _TYPE_GROUPS)


@dataclass
class NormalizationResult:
    status: NormalizationStatus
    entity_id: str | None = None
    method: str | None = None
    candidates: list[str] = field(default_factory=list)


@dataclass
class Mention:
    entity_id: str
    text: str
    start: int
    end: int


class EntityNormalizer:
    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb
        self._alias_index: dict[str, set[str]] = defaultdict(set)
        self._forms: dict[str, set[str]] = defaultdict(set)  # normalised alias -> surface forms
        self._types: dict[str, EntityType] = {}
        named: list[tuple[str, EntityType, list[str]]] = [
            (e.id, e.type, [e.name, *e.aliases]) for e in kb.entities.values()
        ] + [(a.id, a.entity_type, [a.name, *a.aliases]) for a in kb.assets.values()]
        for node_id, etype, names in named:
            self._types[node_id] = etype
            for a in names:
                key = normalize_alias(a)
                self._alias_index[key].add(node_id)
                self._forms[key].add(a.removeprefix("the "))
        self._aliases_sorted = sorted(self._alias_index, key=len, reverse=True)

    def entity_type_of(self, entity_id: str) -> EntityType | None:
        return self._types.get(entity_id)

    def normalize(self, mention: str, entity_type: EntityType | str) -> NormalizationResult:
        etype = EntityType(entity_type)
        raw = mention.strip()
        if raw in self._types:
            return NormalizationResult(NormalizationStatus.RESOLVED, raw, "canonical_id")

        hits = set(self._alias_index.get(normalize_alias(raw), set()))
        if hits:
            compatible = {h for h in hits if _compatible(self._types[h], etype)}
            # An LLM may type "oil prices" as a variable while the alias belongs to the commodity:
            # follow the commodity's declared effect variable rather than guessing.
            if not compatible and etype in (EntityType.ECONOMIC_VARIABLE, EntityType.ECONOMIC_INDICATOR):
                via = {self.kb.effect_variable(h) for h in hits} - {None}
                if len(via) == 1:
                    return NormalizationResult(NormalizationStatus.RESOLVED, via.pop(), "alias_effect_variable")
            if len(compatible) == 1:
                return NormalizationResult(NormalizationStatus.RESOLVED, compatible.pop(), "alias_exact")
            if len(compatible) > 1:
                collapsed = self._collapse_effect_pairs(compatible, etype)
                if collapsed:
                    return NormalizationResult(NormalizationStatus.RESOLVED, collapsed, "alias_exact_collapsed")
                return NormalizationResult(
                    NormalizationStatus.AMBIGUOUS, None, "alias_multiple", sorted(compatible)
                )
            return NormalizationResult(NormalizationStatus.AMBIGUOUS, None, "alias_type_mismatch", sorted(hits))

        suggestions = difflib.get_close_matches(normalize_alias(raw), self._alias_index.keys(), n=3, cutoff=0.86)
        cands = sorted({i for s in suggestions for i in self._alias_index[s]})
        return NormalizationResult(NormalizationStatus.UNRESOLVED, None, "no_exact_match" if not cands else "fuzzy_suggestion_only", cands)

    def _collapse_effect_pairs(self, ids: set[str], etype: EntityType) -> str | None:
        """{entity, entity.effect_variable} denote the same thing at different levels."""
        if len(ids) != 2:
            return None
        a, b = sorted(ids)
        for base, var in ((a, b), (b, a)):
            if self.kb.effect_variable(base) == var:
                return var if etype in (EntityType.ECONOMIC_VARIABLE, EntityType.ECONOMIC_INDICATOR) else base
        return None

    def find_mentions(self, text: str) -> list[Mention]:
        """Exact alias scan (longest match first, non-overlapping). Used by the mock provider."""
        lowered = text.lower()
        taken: list[tuple[int, int]] = []
        found: list[Mention] = []
        for alias in self._aliases_sorted:
            if len(alias) < 2:
                continue
            ids = self._alias_index[alias]
            if len(ids) != 1:
                continue
            # Short all-caps aliases (US, RBI, OPEC) must match case-sensitively to avoid "us" the pronoun.
            forms = sorted(self._forms[alias])
            case_sensitive = any(f.isupper() and len(f) <= 5 for f in forms)
            hay = text if case_sensitive else lowered
            pats = [re.escape(f) for f in forms] if case_sensitive else [re.escape(alias)]
            pats = [r"(?<![A-Za-z0-9])" + p + r"(?![A-Za-z0-9])" for p in pats]
            for pat in pats:
                for m in re.finditer(pat, hay):
                    s, e = m.span()
                    if any(s < te and e > ts for ts, te in taken):
                        continue
                    taken.append((s, e))
                    found.append(Mention(next(iter(ids)), text[s:e], s, e))
        return sorted(found, key=lambda m: m.start)
