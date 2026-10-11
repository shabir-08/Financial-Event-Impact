import json
import shutil

import pytest

from app.services.relationships.knowledge_base import load_knowledge_base
from app.services.text import canonical_url, verify_passage
from app.core.config import DATA_DIR


class TestPassageVerification:
    text = "Brent crude jumped 8% to $97 a barrel on Monday.  Analysts said the cut tightens supply."

    def test_verbatim_passage_verifies(self):
        assert verify_passage("Brent crude jumped 8% to $97 a barrel on Monday.", self.text)

    def test_whitespace_case_and_quotes_normalised(self):
        assert verify_passage("brent  crude JUMPED 8% to $97 a barrel", self.text)
        assert verify_passage("analysts said the cut tightens supply", self.text.replace("'", "’"))

    def test_paraphrase_rejected(self):
        assert not verify_passage("Brent oil rose 8 percent on Monday", self.text)

    def test_ellipsis_fragments_must_appear_in_order(self):
        assert verify_passage("Brent crude jumped 8% ... the cut tightens supply", self.text)
        assert not verify_passage("the cut tightens supply ... Brent crude jumped 8%", self.text)

    def test_empty_or_tiny_passages_rejected(self):
        assert not verify_passage("", self.text)
        assert not verify_passage("8%", self.text)


def test_canonical_url_strips_tracking_and_www():
    a = canonical_url("https://www.Example.com/news/a/?utm_source=x&id=5#frag")
    b = canonical_url("https://example.com/news/a?id=5")
    assert a == b


class TestKnowledgeBase:
    def test_loads_and_validates(self, kb):
        assert kb.version and len(kb.rules) > 50 and len(kb.assets) > 30
        # asset exposures are converted into ordinary rules targeting asset nodes
        assert any(r.kind == "ASSET_EXPOSURE" and r.target == "asset:usdinr" for r in kb.rules.values())

    def test_outgoing_is_data_driven(self, kb):
        targets = {r.target for r in kb.outgoing("variable:crude_oil_price")}
        assert {"variable:jet_fuel_cost", "variable:india_oil_import_bill", "asset:brent_futures"} <= targets

    def test_unknown_reference_fails_validation(self, tmp_path):
        kb_dir = tmp_path / "kb"
        shutil.copytree(DATA_DIR / "knowledge_base", kb_dir)
        f = kb_dir / "relationships" / "energy.json"
        data = json.loads(f.read_text(encoding="utf-8"))
        data["rules"][0]["target"] = "variable:does_not_exist"
        f.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="unknown node"):
            load_knowledge_base(kb_dir)

    def test_adding_rule_requires_no_code_change(self, tmp_path):
        kb_dir = tmp_path / "kb"
        shutil.copytree(DATA_DIR / "knowledge_base", kb_dir)
        extra = {"domain": "test", "rules": [{
            "id": "kb.test.gold_to_gld", "source": "variable:gold_price", "target": "asset:gld",
            "relationship_type": "INFLUENCES", "effect_sign": 0, "mechanism": "test", "reliability": 0.5,
            "economic_relevance": 0.5}]}
        (kb_dir / "relationships" / "zz_test.json").write_text(json.dumps(extra), encoding="utf-8")
        kb2 = load_knowledge_base(kb_dir)
        assert "kb.test.gold_to_gld" in kb2.rules

    def test_source_quality_unknown_domain_is_neutral_not_zero(self, kb):
        q, assessed = kb.source_quality_for("unknown-blog.example")
        assert q == pytest.approx(0.6) and assessed is False
        q2, assessed2 = kb.source_quality_for("www.reuters.com")
        assert q2 > q and assessed2
