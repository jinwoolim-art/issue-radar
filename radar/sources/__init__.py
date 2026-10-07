from . import keyed, web
from .keyed import MissingKey

COLLECTORS = {
    "rss": web.rss,
    "gnews": web.gnews,
    "hackernews": web.hackernews,
    "anthropic_news": web.anthropic_news,
    "github_trending": web.github_trending,
    "reddit": keyed.reddit,
    "youtube": keyed.youtube,
    "naver": keyed.naver,
}

__all__ = ["COLLECTORS", "MissingKey"]
