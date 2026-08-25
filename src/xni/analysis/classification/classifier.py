from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .rules import ACCOUNT_TYPE_RULES, TOPIC_RULES, KeywordRule
from .taxonomy import MIN_RULE_CONFIDENCE


@dataclass(frozen=True)
class TopicMatch:
    topic: str
    confidence: float
    source: str
    evidence: str


@dataclass(frozen=True)
class AccountTypeMatch:
    account_type: str
    confidence: float
    source: str
    evidence: str


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    value = unicodedata.normalize("NFKC", text)
    return " ".join(value.split())


def _keyword_match(text: str, keyword: str) -> str | None:
    normalized_keyword = normalize_text(keyword)
    if not normalized_keyword:
        return None
    if normalized_keyword.isascii() and re.fullmatch(r"[A-Za-z0-9_+#.-]+", normalized_keyword):
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(normalized_keyword)}(?![A-Za-z0-9_])"
        match = re.search(pattern, text, flags=re.IGNORECASE)
    else:
        match = re.search(re.escape(normalized_keyword), text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _evaluate_rule(text: str, rule: KeywordRule) -> list[str] | None:
    if rule.confidence < MIN_RULE_CONFIDENCE:
        return None
    evidence: list[str] = []
    if rule.all_keywords:
        for keyword in rule.all_keywords:
            found = _keyword_match(text, keyword)
            if not found:
                return None
            evidence.append(found)
    if rule.any_keywords:
        found_any = None
        for keyword in rule.any_keywords:
            found = _keyword_match(text, keyword)
            if found:
                found_any = found
                break
        if not found_any:
            return None
        evidence.append(found_any)
    if not rule.any_keywords and not rule.all_keywords:
        return None
    return evidence


def classify_topics(text: str | None) -> list[TopicMatch]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    results: dict[str, TopicMatch] = {}
    for rule in TOPIC_RULES:
        evidence = _evaluate_rule(normalized, rule)
        if evidence is None:
            continue
        candidate = TopicMatch(
            topic=rule.output,
            confidence=rule.confidence,
            source=rule.source,
            evidence=" | ".join(dict.fromkeys(evidence)),
        )
        previous = results.get(rule.output)
        if previous is None or candidate.confidence > previous.confidence:
            results[rule.output] = candidate
    return sorted(results.values(), key=lambda item: item.topic)


def classify_account_type(text: str | None) -> AccountTypeMatch:
    normalized = normalize_text(text)
    if not normalized:
        return AccountTypeMatch("Unknown", 1.0, "default", "")
    for rule in ACCOUNT_TYPE_RULES:
        evidence = _evaluate_rule(normalized, rule)
        if evidence is not None:
            return AccountTypeMatch(
                account_type=rule.output,
                confidence=rule.confidence,
                source=rule.source,
                evidence=" | ".join(dict.fromkeys(evidence)),
            )
    return AccountTypeMatch("Unknown", 1.0, "default", "")
