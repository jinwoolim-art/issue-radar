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
             "is", "of", "to", "in", "on", "a", "an", "by", "at", "as", "it", "be", "or", "vs"}


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


def is_ai(it: Item) -> bool:
    text = f"{it.title} {it.summary}".lower()
    p, c = tag(it)
    return bool(p or c) or any(m(text) for m in _AI_KW)


def _tokens(title: str) -> set:
    words = re.findall(r"[a-z0-9][a-z0-9.\-]*|[가-힣]{2,}", title.lower())
    return {w.strip(".-") for w in words if len(w) >= 2 and w not in STOPWORDS}


def _versions(title: str) -> set:
    return set(re.findall(r"\d+(?:\.\d+)+|\d+[a-z]+\b", title.lower()))


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
        h *= max(0.15, math.exp(-max(age_h, 0) / 36))
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
        if self.products & p and (self.versions & vers or sim >= 0.2):
            return True
        if self.companies & c and sim >= 0.25:
            return True
        return sim >= 0.4

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
        if src.get("ai_filter") and not is_ai(it):
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
        text = " ".join(f"{it.title} {it.summary}" for it, _ in cl.items).lower()
        hits = {name: sum(m(text) for m in ms) for name, ms in _CORNERS.items()}
        best = max(hits, key=hits.get)
        if hits[best] >= 1:
            cl.corner = best

    clusters.sort(key=lambda c: -c.heat)
    top = clusters[0].heat if clusters else 1
    for cl in clusters:
        cl.score = round(100 * cl.heat / top)
    return clusters
