"""Text utilities shared by extraction, evidence verification and the mock provider."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
_WS = re.compile(r"\s+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    return _WS.sub(" ", text).strip().lower()


def normalize_alias(text: str) -> str:
    t = normalize_text(text)
    t = t.removeprefix("the ")
    return t.strip(" .,;:")


def verify_passage(passage: str | None, source_text: str) -> bool:
    """True if ``passage`` occurs (after whitespace/quote/case normalisation) in ``source_text``.

    LLM-provided evidence passages are only trusted when this check passes.
    Ellipses are treated as separators: every fragment must appear, in order.
    """
    if not passage or not passage.strip():
        return False
    hay = normalize_text(source_text)
    fragments = [normalize_text(f) for f in re.split(r"\.\.\.|…", passage) if f.strip()]
    if not fragments or any(len(f) < 8 for f in fragments):
        return False
    pos = 0
    for frag in fragments:
        idx = hay.find(frag, pos)
        if idx < 0:
            return False
        pos = idx + len(frag)
    return True


def split_sentences(text: str) -> list[str]:
    out = []
    for block in text.split("\n"):
        out.extend(s.strip() for s in _SENTENCE.split(block) if s.strip())
    return out


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    netloc = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    # Drop tracking query params but keep others (some sites route on query strings).
    query = "&".join(
        q for q in parts.query.split("&") if q and not q.lower().startswith(("utm_", "fbclid", "gclid"))
    )
    return urlunsplit((parts.scheme.lower() or "https", netloc, path, query, ""))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    netloc = urlsplit(url).netloc.lower()
    return netloc.removeprefix("www.") or None


def token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", normalize_text(text)) if len(t) > 2}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)
