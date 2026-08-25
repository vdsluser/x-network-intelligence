from xni.analysis.classification.associations import extract_associations


def _pairs(rows):
    return {(r.association_type, r.value) for r in rows}


def test_extracts_role_and_org_mention():
    rows = extract_associations("CEO @ExampleAI | AI builder")
    assert ("role", "CEO") in _pairs(rows)
    assert ("organization", "ExampleAI") in _pairs(rows)
    assert all(row.evidence for row in rows)


def test_declared_affiliation_requires_explicit_english_phrase():
    rows = extract_associations("Researcher | member of Example Association | AI")
    affiliations = [r for r in rows if r.association_type == "declared_affiliation"]
    assert len(affiliations) == 1
    assert affiliations[0].value == "Example Association"


def test_declared_affiliation_requires_explicit_korean_phrase():
    rows = extract_associations("연구자 | 소속: 미래기술연구소 | 인공지능")
    assert ("declared_affiliation", "미래기술연구소") in _pairs(rows)


def test_plain_topic_text_does_not_create_declared_affiliation():
    rows = extract_associations("politics society news Example Association")
    assert not any(r.association_type == "declared_affiliation" for r in rows)


def test_extracts_domains_from_raw_bio_urls_without_fetching():
    rows = extract_associations(
        "Researcher",
        raw_json={"bio_urls": [{"expanded_url": "https://www.example.org/about"}, "https://lab.example.ai/me"]},
    )
    domains = {r.value for r in rows if r.association_type == "domain"}
    assert domains == {"example.org", "lab.example.ai"}


def test_association_values_are_deduplicated_case_insensitively():
    rows = extract_associations("CEO @ExampleAI | working with @exampleai")
    orgs = [r for r in rows if r.association_type == "organization" and r.normalized_value == "exampleai"]
    assert len(orgs) == 1
