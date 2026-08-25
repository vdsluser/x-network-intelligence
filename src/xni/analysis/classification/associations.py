from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .taxonomy import MIN_RULE_CONFIDENCE


@dataclass(frozen=True)
class AssociationMatch:
    association_type: str
    value: str
    normalized_value: str
    source: str
    evidence: str
    confidence: float


def normalize_association_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.strip().split())
    return normalized.casefold()


def _add(
    bucket: dict[tuple[str, str], AssociationMatch],
    association_type: str,
    value: str,
    *,
    source: str,
    evidence: str,
    confidence: float,
) -> None:
    value = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    value = value.strip(" @|,;:.-")
    if not value or confidence < MIN_RULE_CONFIDENCE:
        return
    normalized_value = normalize_association_value(value)
    key = (association_type, normalized_value)
    candidate = AssociationMatch(
        association_type=association_type,
        value=value,
        normalized_value=normalized_value,
        source=source,
        evidence=evidence.strip(),
        confidence=confidence,
    )
    previous = bucket.get(key)
    if previous is None or candidate.confidence > previous.confidence:
        bucket[key] = candidate


def _raw_urls(raw_json: dict[str, Any] | None) -> list[str]:
    if not raw_json:
        return []
    urls = raw_json.get("bio_urls")
    if not isinstance(urls, list):
        return []
    result: list[str] = []
    for item in urls:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            for key in ("expanded_url", "url", "display_url"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    result.append(value)
                    break
    return result


def extract_associations(
    description: str | None,
    *,
    raw_json: dict[str, Any] | None = None,
) -> list[AssociationMatch]:
    text = unicodedata.normalize("NFKC", description or "")
    bucket: dict[tuple[str, str], AssociationMatch] = {}

    for match in re.finditer(r"(?<![\w@])@([A-Za-z0-9_]{2,64})", text):
        _add(
            bucket,
            "organization",
            match.group(1),
            source="bio_mention",
            evidence=match.group(0),
            confidence=0.90,
        )

    role_patterns = (
        r"\b(CEO|CTO|CFO|COO|Founder|Co-Founder|Journalist|Reporter|Professor|Researcher)\b",
        r"(?<!\w)(대표|창업자|기자|교수|연구자|연구원)(?!\w)",
    )
    for pattern in role_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            _add(bucket, "role", match.group(1), source="bio_role", evidence=match.group(0), confidence=0.95)

    affiliation_patterns = (
        r"\bmember\s+of\s+([^|,;\n]{2,100})",
        r"\baffiliated\s+with\s+([^|,;\n]{2,100})",
        r"(?:^|[|,;\n])\s*소속\s*[:：]?\s*([^|,;\n]{2,100})",
    )
    for pattern in affiliation_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            evidence = match.group(0).strip(" |,;\n")
            value = match.group(1).strip()
            _add(
                bucket,
                "declared_affiliation",
                value,
                source="bio_explicit_affiliation",
                evidence=evidence,
                confidence=0.95,
            )

    technology_terms = (
        "Python", "JavaScript", "TypeScript", "React", "Node.js", "Rust", "LLM",
        "PyTorch", "TensorFlow", "CUDA", "Kubernetes",
    )
    for term in technology_terms:
        match = re.search(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", text, flags=re.IGNORECASE)
        if match:
            _add(
                bucket,
                "technology",
                match.group(0),
                source="bio_technology",
                evidence=match.group(0),
                confidence=0.90,
            )

    for raw_url in _raw_urls(raw_json):
        parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
        host = (parsed.hostname or "").strip().lower()
        if host.startswith("www."):
            host = host[4:]
        if host:
            _add(bucket, "domain", host, source="bio_url", evidence=raw_url, confidence=0.95)

    return sorted(bucket.values(), key=lambda row: (row.association_type, row.normalized_value))
