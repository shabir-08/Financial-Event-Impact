from app.domain import EntityType, NormalizationStatus
from app.schemas.llm import EntityExtraction, ExtractedEntity
from app.services.entities.extraction import normalize_extracted_entities
from app.services.entities.normalization import EntityNormalizer


def test_exact_alias_resolves(kb):
    n = EntityNormalizer(kb)
    r = n.normalize("Brent crude", EntityType.COMMODITY)
    assert r.status == NormalizationStatus.RESOLVED and r.entity_id == "commodity:crude_oil"
    assert n.normalize("Reserve Bank of India", "INSTITUTION").entity_id == "institution:rbi"


def test_canonical_id_passthrough(kb):
    r = EntityNormalizer(kb).normalize("asset:usdinr", EntityType.FINANCIAL_INSTRUMENT)
    assert r.entity_id == "asset:usdinr" and r.method == "canonical_id"


def test_similar_name_is_not_resolved(kb):
    r = EntityNormalizer(kb).normalize("IndiGo Partners Fund", EntityType.COMPANY)
    assert r.status == NormalizationStatus.UNRESOLVED and r.entity_id is None


def test_fuzzy_match_is_suggestion_only(kb):
    r = EntityNormalizer(kb).normalize("Interglobe Aviaton", EntityType.COMPANY)  # typo
    assert r.status == NormalizationStatus.UNRESOLVED
    assert r.entity_id is None
    assert "company:interglobe_aviation" in r.candidates


def test_type_mismatch_is_ambiguous(kb):
    r = EntityNormalizer(kb).normalize("India", EntityType.COMPANY)
    assert r.status == NormalizationStatus.AMBIGUOUS and r.entity_id is None
    assert r.candidates == ["country:india"]


def test_variable_typed_commodity_mention_maps_to_price_variable(kb):
    r = EntityNormalizer(kb).normalize("oil prices", EntityType.ECONOMIC_VARIABLE)
    assert r.entity_id == "variable:crude_oil_price"


def test_no_ticker_fabrication_for_unknown_company(kb):
    r = EntityNormalizer(kb).normalize("Acme Shipping Ltd", EntityType.COMPANY)
    assert r.entity_id is None
    assert not any(c.startswith("asset:") for c in r.candidates)


def test_find_mentions_respects_case_for_short_acronyms(kb):
    ms = EntityNormalizer(kb).find_mentions("Let us see whether US officials and the RBI act.")
    ids = [m.entity_id for m in ms]
    assert ids.count("country:us") == 1 and "institution:rbi" in ids


def test_extraction_records_passage_verification(kb):
    text = "OPEC+ cut output. The rupee fell."
    ext = EntityExtraction(entities=[
        ExtractedEntity(mention="OPEC+", entity_type=EntityType.INSTITUTION, passage="OPEC+ cut output.", confidence=0.9),
        ExtractedEntity(mention="rupee", entity_type=EntityType.CURRENCY, passage="The rupee rallied.", confidence=0.9),
        ExtractedEntity(mention="Zed Corp", entity_type=EntityType.COMPANY, passage="Zed Corp", confidence=0.5),
    ])
    out = {m.mention: m for m in normalize_extracted_entities(ext, EntityNormalizer(kb), text)}
    assert out["OPEC+"].passage_verified and out["OPEC+"].entity_id == "institution:opec_plus"
    assert not out["rupee"].passage_verified  # passage not in article
    assert out["Zed Corp"].status == NormalizationStatus.UNRESOLVED
