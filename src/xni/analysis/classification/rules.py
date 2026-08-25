from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeywordRule:
    output: str
    any_keywords: tuple[str, ...] = ()
    all_keywords: tuple[str, ...] = ()
    confidence: float = 0.85
    source: str = "bio_rule"


TOPIC_RULES: tuple[KeywordRule, ...] = (
    KeywordRule("AI", ("artificial intelligence", "machine learning", "deep learning", "llm", "인공지능", "머신러닝", "딥러닝", "ai"), confidence=0.95),
    KeywordRule("Technology", ("software", "developer", "engineer", "python", "javascript", "technology", "tech", "개발자", "개발", "소프트웨어", "프로그래머"), confidence=0.85),
    KeywordRule("EconomyFinance", ("finance", "financial", "economy", "economics", "market analyst", "금융", "경제", "금융시장", "경제분석"), confidence=0.85),
    KeywordRule("Investment", ("investment", "investor", "asset management", "portfolio", "stocks", "stock market", "투자", "주식", "자산운용", "포트폴리오"), confidence=0.90),
    KeywordRule("Business", ("business", "startup", "entrepreneur", "founder", "ceo", "기업", "스타트업", "창업", "대표"), confidence=0.85),
    KeywordRule("MediaJournalism", ("journalist", "reporter", "newsroom", "editor", "news", "기자", "언론", "뉴스룸", "편집장"), confidence=0.90),
    KeywordRule("Crypto", ("crypto", "bitcoin", "ethereum", "blockchain", "web3", "암호화폐", "비트코인", "이더리움", "블록체인"), confidence=0.90),
    KeywordRule("Sports", ("sports", "football", "soccer", "baseball", "basketball", "table tennis", "스포츠", "축구", "야구", "농구", "탁구"), confidence=0.85),
    KeywordRule("Entertainment", ("entertainment", "actor", "actress", "singer", "music", "movie", "연예", "배우", "가수", "음악", "영화"), confidence=0.85),
    KeywordRule("Creator", ("creator", "youtube", "youtuber", "podcast", "streamer", "크리에이터", "유튜버", "팟캐스트", "스트리머"), confidence=0.90),
    KeywordRule("Organization", ("association", "foundation", "nonprofit", "ngo", "organization", "협회", "재단", "비영리", "기관"), confidence=0.90),
    KeywordRule("PoliticsSociety", ("politics", "political", "policy", "parliament", "politician", "정치", "정책", "국회", "의정"), confidence=0.85),
    KeywordRule("PublicAffairs", ("public affairs", "government relations", "civic", "공공정책", "대외협력", "공공", "시민사회"), confidence=0.85),
    KeywordRule("ScienceResearch", ("scientist", "researcher", "research lab", "science", "scientific", "연구원", "연구자", "과학", "연구소"), confidence=0.85),
    KeywordRule("Education", ("teacher", "professor", "educator", "university", "school", "교육", "교수", "교사", "대학교", "학교"), confidence=0.85),
    KeywordRule("CultureArts", ("artist", "art", "museum", "gallery", "culture", "예술", "작가", "미술", "문화", "갤러리"), confidence=0.85),
)

# Earlier entries win. Rules deliberately favor explicit institutional/account-role phrases.
ACCOUNT_TYPE_RULES: tuple[KeywordRule, ...] = (
    KeywordRule("Media", ("journalist", "reporter", "newsroom", "editor", "기자", "뉴스룸", "편집장", "언론사"), confidence=0.95),
    KeywordRule("Company", ("official account", "company", "corporation", "corp", " inc", "공식 계정", "주식회사", "기업 공식"), confidence=0.95),
    KeywordRule("Organization", ("association", "foundation", "nonprofit", "ngo", "organization", "협회", "재단", "비영리단체", "기관 공식"), confidence=0.95),
    KeywordRule("PublicFigure", ("member of parliament", "senator", "mayor", "minister", "국회의원", "의원", "시장", "장관"), confidence=0.95),
    KeywordRule("Creator", ("content creator", "creator", "youtuber", "streamer", "podcaster", "크리에이터", "유튜버", "스트리머", "팟캐스터"), confidence=0.90),
    KeywordRule("FanAccount", ("fan account", "fanpage", "fan page", "팬계정", "팬 계정", "팬페이지"), confidence=0.95),
    KeywordRule("Individual", ("researcher", "engineer", "developer", "investor", "analyst", "연구자", "연구원", "개발자", "엔지니어", "투자자", "분석가"), confidence=0.85),
)
