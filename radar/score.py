"""같은 이슈 묶기 + 뜨는 점수 (v0: 규칙 기반, 무료).

Claude 키가 들어오면 묶기·요약은 AI로 교체하고, 이 규칙은 1차 거르기로 남긴다.
"""
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import Item, now_utc

CONFIG = Path(__file__).resolve().parent.parent / "config"
_ENT = yaml.safe_load((CONFIG / "entities.yaml").read_text(encoding="utf-8"))

STOPWORDS = {"the", "and", "for", "with", "from", "that", "this", "your", "you", "are", "how", "what",
             "new", "now", "its", "into", "show", "hn", "ask", "about", "has", "have", "will", "can",
             "is", "of", "to", "in", "on", "a", "an", "by", "at", "as", "it", "be", "or", "vs",
             "january", "february", "march", "april", "may", "june", "july", "august", "september",
             "october", "november", "december", "ai", "shorts"}
# 업체·제품 이름 자체는 묶기 유사도 계산에서 뺀다 ("Claude" 만 같다고 같은 이슈가 아니므로)
STOPWORDS |= {a.lower() for v in _ENT["companies"].values() for a in v if a.isascii() and " " not in a}
STOPWORDS |= {a.lower() for v in _ENT["products"].values() for a in v["aliases"] if a.isascii() and " " not in a}
_GENERAL = set(_ENT.get("general_companies", []))
AD_LINES = {"AI 광고 상품", "AI 검색 노출(GEO)", "AI 기업 홍보"}


def _matcher(alias: str):
    alias = alias.lower()
    if alias.isascii():
        rx = re.compile(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])")
        return lambda text: bool(rx.search(text))
    return lambda text: alias in text


_COMPANIES = {name: [_matcher(a) for a in aliases] for name, aliases in _ENT["companies"].items()}
_PRODUCTS = {name: (v["company"], [_matcher(a) for a in v["aliases"]]) for name, v in _ENT["products"].items()}
_AI_KW = [_matcher(k) for k in _ENT["ai_keywords"]]
_CORNERS = {name: [_matcher(k) for k in kws] for name, kws in _ENT["corners"].items()}


def tag(it: Item) -> tuple[set, set]:
    text = f"{it.title} {it.summary}".lower()
    products = {n for n, (_, ms) in _PRODUCTS.items() if any(m(text) for m in ms)}
    companies = {n for n, ms in _COMPANIES.items() if any(m(text) for m in ms)}
    companies |= {_PRODUCTS[p][0] for p in products if _PRODUCTS[p][0]}
    return products, companies


def is_ai(it: Item, title_only=False) -> bool:
    probe = Item(it.source, it.title, it.url, summary="" if title_only else it.summary)
    text = f"{probe.title} {probe.summary}".lower()
    p, c = tag(probe)
    return bool(p or (c - _GENERAL)) or any(m(text) for m in _AI_KW)


def _tokens(title: str) -> set:
    words = re.findall(r"[a-z0-9][a-z0-9.\-]*|[가-힣]{2,}", title.lower())
    words = (w.strip(".-") for w in words)
    return {w for w in words if len(w) >= 2 and w not in STOPWORDS and not re.fullmatch(r"(19|20)\d\d|\d{1,2}", w)}


def _versions(title: str) -> set:
    # 같은 제품을 언급할 때만 쓰이므로 "4" 같은 맨 숫자도 버전으로 본다 (Mistral Large 4)
    return set(re.findall(r"\d+(?:\.\d+)+|\d+[a-z]+\b|(?<![\d.])\d{1,3}(?![\d.])", title.lower()))


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def item_heat(it: Item, src: dict, prev: Item | None) -> float:
    h = float(src.get("base", 10))
    scale = {"points": 6, "stars today": 5, "upvotes": 5}
    if it.metric_label == "views":
        h += 4 * math.log1p(it.metric / 100)
    elif it.metric_label in scale:
        h += scale[it.metric_label] * math.log1p(it.metric)
    h += 3 * math.log1p(it.comments)
    if prev and prev.metric_label == it.metric_label:          # 반응 속도: 직전 스캔 대비 증가분
        h += 5 * math.log1p(max(0.0, it.metric - prev.metric))
    if it.published_at:
        age_h = (now_utc() - it.published_at).total_seconds() / 3600
        tau = it.extra.get("decay_hours", 36)   # 꾸준히 쌓이는 라인(GEO 등)은 키워드 감시에서 더 길게 지정
        h *= max(0.15, math.exp(-max(age_h, 0) / tau))
    else:
        h *= 0.5
    return h


@dataclass
class Cluster:
    items: list = field(default_factory=list)     # (Item, heat)
    products: set = field(default_factory=set)
    companies: set = field(default_factory=set)
    tokens: set = field(default_factory=set)
    versions: set = field(default_factory=set)
    heat: float = 0.0
    score: int = 0
    corner: str = "AI 소식"

    def accepts(self, it, p, c, toks, vers) -> bool:
        sim = _jaccard(toks, self.tokens)
        shared = len(toks & self.tokens)
        if self.products & p and shared >= 1 and (self.versions & vers or sim >= 0.2):
            return True
        if self.companies & c and sim >= 0.25 and shared >= 2:
            return True
        return sim >= 0.4 and shared >= 3

    def add(self, it, heat, p, c, toks, vers):
        self.items.append((it, heat))
        self.products |= p
        self.companies |= c
        self.tokens |= toks
        self.versions |= vers


def build_clusters(items: list[Item], sources: dict, prev: dict[str, Item]) -> list[Cluster]:
    scored = []
    for it in items:
        src = sources[it.source]
        ai_line = it.extra.get("ai_line")   # 로컬 AI 분류 결과가 있으면 그것이 우선
        if ai_line == "제외(AI 무관)":
            continue
        if not ai_line and src.get("ai_filter") and not is_ai(it, title_only=src.get("ai_filter_title_only", False)):
            continue
        scored.append((it, item_heat(it, src, prev.get(it.url))))
    scored.sort(key=lambda x: -x[1])

    clusters: list[Cluster] = []
    for it, heat in scored:
        p, c = tag(it)
        toks, vers = _tokens(it.title), _versions(it.title)
        target = next((cl for cl in clusters if cl.accepts(it, p, c, toks, vers)), None)
        if target is None:
            target = Cluster()
            clusters.append(target)
        target.add(it, heat, p, c, toks, vers)

    for cl in clusters:
        heats = sorted((h for _, h in cl.items), reverse=True)
        n_sources = len({it.source for it, _ in cl.items})
        official = any(sources[it.source].get("official") for it, _ in cl.items)
        cl.heat = sum(h * w for h, w in zip(heats, (1, 0.5, 0.3, 0.2, 0.1))) \
            + 12 * (n_sources - 1) + (8 if official else 0)
        # 영상 설명란은 해시태그·광고문구 도배라 제목만 본다
        text = " ".join(it.title if sources[it.source].get("ai_filter_title_only") else f"{it.title} {it.summary}"
                        for it, _ in cl.items).lower()
        hits = {name: sum(m(text) for m in ms) for name, ms in _CORNERS.items()}
        # 광고 3라인은 서로 단어가 겹치므로 우선순위로 가른다:
        # 광고 상품 단서 > 홍보(캠페인·광고 영상, AI 회사 등장 시) > GEO > 키워드 감시 라인 > 일반 코너
        lines = [it.extra.get("line") for it, _ in cl.items if it.extra.get("line")]
        general = {k: v for k, v in hits.items() if k not in AD_LINES}
        if hits.get("AI 광고 상품"):
            cl.corner = "AI 광고 상품"
        elif hits.get("AI 기업 홍보") and (cl.products or cl.companies - _GENERAL):
            cl.corner = "AI 기업 홍보"
        # GEO 단어(ai mode 등)는 구글 제품 소개글에도 나오므로 감시 키워드로 왔거나 단서가 2개 이상일 때만
        elif hits.get("AI 검색 노출(GEO)") and (lines or hits["AI 검색 노출(GEO)"] >= 2):
            cl.corner = "AI 검색 노출(GEO)"
        elif lines:
            cl.corner = max(set(lines), key=lines.count)
        elif general and max(general.values()) >= 1:
            cl.corner = max(general, key=general.get)
        # 로컬 AI 분류(정답지 기준 84%)가 있으면 묶음 안 다수결로 덮어쓴다 — 규칙 기반(53%)보다 정확
        ai_lines = [it.extra.get("ai_line") for it, _ in cl.items if it.extra.get("ai_line")]
        if ai_lines:
            cl.corner = max(set(ai_lines), key=ai_lines.count)

    clusters.sort(key=lambda c: -c.heat)
    top = clusters[0].heat if clusters else 1
    for cl in clusters:
        cl.score = round(100 * cl.heat / top)
    return clusters
