from xni.analysis.classification.classifier import classify_account_type, classify_topics


def test_ai_bio_matches_ai_and_technology_topics():
    matches = classify_topics("AI researcher | LLM | Python")
    assert {m.topic for m in matches} >= {"AI", "Technology"}
    assert all(m.confidence >= 0.70 for m in matches)
    assert all(m.evidence for m in matches)


def test_korean_bio_matches_finance_and_investment():
    matches = classify_topics("주식 투자와 자산운용, 금융시장 분석")
    assert {m.topic for m in matches} >= {"EconomyFinance", "Investment"}


def test_korean_media_role_wins_account_type():
    match = classify_account_type("경제 전문 기자 | 뉴스룸 | 콘텐츠 크리에이터")
    assert match.account_type == "Media"
    assert "기자" in match.evidence or "뉴스룸" in match.evidence


def test_company_rule_has_deterministic_priority_over_creator_word():
    match = classify_account_type("ExampleAI 공식 계정 | creator tools company")
    assert match.account_type == "Company"


def test_empty_bio_is_unknown():
    assert classify_topics("") == []
    match = classify_account_type("")
    assert match.account_type == "Unknown"
    assert match.confidence == 1.0
