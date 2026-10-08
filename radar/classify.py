"""AI 분류기 — 로컬 AI(Ollama)로 수집 글의 콘텐츠 라인을 정한다. 규칙 기반(score.py)보다 정확하게.

- 무료: 이 컴퓨터의 Ollama + qwen3:8b. 나중에 Windows 3060에서도 그대로.
- 한 번에 여러 제목을 묶어 보내고(속도), 결과는 url 기준으로 캐시(30분마다 같은 글을 다시 묻지 않게).
"""
import hashlib
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "classify_cache.json"
OLLAMA = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
BATCH = 12

LINES = ["AI 소식", "사용 스킬", "요금·프로모션", "업체 소개",
         "AI 광고 상품", "AI 검색 노출(GEO)", "AI 기업 홍보", "제외(AI 무관)"]

GUIDE = """너는 한국 AI 숏폼 채널의 자료 분류 담당이다. 각 글 제목(과 짧은 요약)을 보고 아래 라인 중 정확히 하나를 고른다.

- AI 소식: AI 업계 일반 뉴스. 대형 AI 회사(OpenAI·구글·앤트로픽·메타·MS 등)의 새 모델·기능 발표, 기업 협력·실적, 정책·규제, 연구 결과, 사건사고.
- 사용 스킬: 일반 사용자가 따라 할 수 있는 AI 사용법·꿀팁·튜토리얼·서비스 비교·활용 가이드.
- 요금·프로모션: AI 서비스의 요금제·가격 변경·할인·무료 혜택·구독 조건.
- 업체 소개: 새롭거나 덜 알려진 AI 스타트업·도구·오픈소스 프로젝트 소개, 투자 유치, 신생 제품 출시. (대형 AI 회사의 발표는 'AI 소식')
- AI 광고 상품: AI 회사가 광고주에게 파는 광고 상품·광고 플랫폼 사업(예: ChatGPT 광고, 광고 형식·측정·광고 매출). 광고주·마케터 대상 이야기.
- AI 검색 노출(GEO): AI 검색·AI 답변에서 브랜드·상품·매장이 노출·추천되는 문제. GEO·AEO·AI 검색 최적화, 소상공인·쇼핑몰의 AI 노출, 네이버 AI 브리핑·AI탭 노출.
- AI 기업 홍보: AI 회사가 자기 브랜드를 알리는 광고 캠페인·홍보 영상·광고 모델 기용(광고 '상품' 판매가 아님).
- 제외(AI 무관): AI와 관련 없는 글(지역 축제, 일반 산업·금융·스포츠 등), 또는 검색 노출을 노린 엉터리·스팸 글.

규칙:
- 각 글 앞의 [출처]를 참고한다. AI 회사 공식 블로그·AI 전문 커뮤니티 글은 대부분 AI 관련이다.
- [GitHub 트렌딩]의 '사용자명/저장소명' 형태 제목은 새 AI 도구·프로젝트 → '업체 소개'.
- 회사·기관이 새 제품·서비스·플랫폼을 '출시·공개·론칭·선봬'하는데 그 회사가 대형 AI 회사가 아니면 '업체 소개'.
- 제목에 'AI'가 들어가도 실제 주제가 AI가 아니면 '제외(AI 무관)'. 제목이 짧은 영어라 애매하면 출처를 보고 AI 관련으로 본다.
- 애매하면 시청자가 이 글로 무엇을 얻는지 기준으로 고른다."""

SCHEMA = {"type": "object", "properties": {"results": {"type": "array", "items": {
    "type": "object", "properties": {"n": {"type": "integer"}, "line": {"type": "string", "enum": LINES}},
    "required": ["n", "line"]}}}, "required": ["results"]}


def _key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def _ask(batch: list[dict]) -> dict[int, str]:
    lines = "\n".join(f"{i + 1}. [{b.get('source', '')}] {b['title']}" + (f" — {b['summary'][:120]}" if b.get("summary") else "")
                      for i, b in enumerate(batch))
    r = httpx.post(OLLAMA, timeout=300, json={
        "model": MODEL, "stream": False, "think": False, "format": SCHEMA,
        "options": {"temperature": 0, "num_ctx": 8192},
        "messages": [{"role": "system", "content": GUIDE},
                     {"role": "user", "content": f"다음 {len(batch)}개 글을 분류해. 번호(n)와 라인(line)만.\n\n{lines}"}]})
    r.raise_for_status()
    out = json.loads(r.json()["message"]["content"]).get("results", [])
    return {o["n"]: o["line"] for o in out if o.get("line") in LINES}


def classify(items: list[dict]) -> dict[str, str]:
    """items: [{url, title, summary}] → {url: line}. 캐시에 있는 글은 다시 묻지 않는다."""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = [it for it in items if _key(it["url"]) not in cache]
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        try:
            got = _ask(batch)
        except Exception as e:   # 로컬 AI가 꺼져 있으면 규칙 기반 결과를 그대로 쓰게 둔다
            print(f"  AI 분류 실패({type(e).__name__}) — 규칙 기반 유지")
            break
        for j, it in enumerate(batch, 1):
            if j in got:
                cache[_key(it["url"])] = got[j]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return {it["url"]: _guard(it, cache[_key(it["url"])]) for it in items if _key(it["url"]) in cache}


def _guard(it: dict, line: str) -> str:
    """작은 AI가 AI 회사·제품 이름이 든 글을 'AI 무관'으로 버리는 실수 방지 → 'AI 소식'으로 되살림."""
    if line != "제외(AI 무관)":
        return line
    from .models import Item
    from .score import _GENERAL, tag
    p, c = tag(Item(source="", title=it["title"], url=it["url"], summary=it.get("summary", "")))
    return "AI 소식" if (p or (c - _GENERAL)) else line
