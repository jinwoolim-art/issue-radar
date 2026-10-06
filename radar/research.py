"""유튜브 리서치: 주제 검색 → 영상 목록(조회수·댓글) → 자막 수집 → 읽기용 정리 파일.

꿀팁 추출·공식 문서 대조 같은 '판단'은 이 결과를 읽는 쪽(사람 또는 Claude)이 한다.
결과는 data/research/<날짜>_<주제>/ 에 남는다 (공개 저장소에는 안 올라감).
"""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

from . import http
from .sources.keyed import _env, _foreign

ROOT = Path(__file__).resolve().parent.parent
API = "https://www.googleapis.com/youtube/v3"


def _seconds(iso: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _slug(text: str) -> str:
    return re.sub(r"[^\w가-힣]+", "-", text).strip("-")[:40]


def youtube(topic: str, queries: list[str] | None = None, days: int = 180,
            max_videos: int = 12, min_seconds: int = 90) -> Path:
    key = _env("YOUTUBE_API_KEY")
    queries = queries or [topic]
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    ids = []
    for q in queries:   # 검색 1회 = 100유닛
        r = http.get(f"{API}/search", params={
            "part": "id", "q": q, "type": "video", "regionCode": "KR", "relevanceLanguage": "ko",
            "order": "relevance", "publishedAfter": after, "maxResults": 25, "key": key}).json()
        ids += [v["id"]["videoId"] for v in r.get("items", [])]
    ids = list(dict.fromkeys(ids))

    videos = []
    for i in range(0, len(ids), 50):
        r = http.get(f"{API}/videos", params={
            "part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i + 50]), "key": key}).json()
        for v in r.get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            videos.append({
                "id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}",
                "title": sn["title"], "channel": sn["channelTitle"], "date": sn["publishedAt"][:10],
                "views": int(st.get("viewCount", 0)), "comments": int(st.get("commentCount", 0)),
                "seconds": _seconds(v["contentDetails"]["duration"]),
            })
    # 쇼츠·외국어 제외 후 조회수순 상위 N개만 자막 수집
    picked = sorted((v for v in videos if v["seconds"] >= min_seconds and not _foreign(v["title"])),
                    key=lambda v: -v["views"])[:max_videos]

    fetch_transcripts(picked)

    out = ROOT / "data" / "research" / f"{datetime.now():%Y%m%d}_{_slug(topic)}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "videos.json").write_text(json.dumps(videos, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "meta.json").write_text(json.dumps({"topic": topic, "queries": queries, "days": days}, ensure_ascii=False), encoding="utf-8")
    (out / "transcripts.json").write_text(json.dumps(picked, ensure_ascii=False), encoding="utf-8")

    write_digest(out, topic, queries, days, videos, picked)
    return out


def fetch_transcripts(picked: list[dict]) -> int:
    """자막을 받아 picked 에 채운다. 유튜브가 IP를 막으면 즉시 멈춘다 (계속 두드리면 차단이 길어짐)."""
    api, got = YouTubeTranscriptApi(), 0
    for v in picked:
        if v.get("transcript"):
            continue
        try:
            v["transcript"] = " ".join(s.text for s in api.fetch(v["id"], languages=["ko", "en"]))
            v.pop("transcript_error", None)
            got += 1
        except Exception as e:
            v["transcript"], v["transcript_error"] = "", type(e).__name__
            if type(e).__name__ in ("IpBlocked", "RequestBlocked"):
                print("  ⛔ 유튜브가 자막 요청을 차단함 → 중단. 몇 시간 뒤 `python -m radar yt-retry` 로 이어 받기")
                break
        time.sleep(3)   # 차단 방지
    return got


def retry(folder: Path | None = None) -> Path:
    """못 받은 자막만 다시 받는다. 폴더를 안 주면 가장 최근 리서치."""
    folder = folder or sorted((ROOT / "data" / "research").glob("*/"))[-1]
    picked = json.loads((folder / "transcripts.json").read_text(encoding="utf-8"))
    got = fetch_transcripts(picked)
    (folder / "transcripts.json").write_text(json.dumps(picked, ensure_ascii=False), encoding="utf-8")
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8")) if (folder / "meta.json").exists() \
        else {"topic": folder.name, "queries": [folder.name], "days": 0}
    videos = json.loads((folder / "videos.json").read_text(encoding="utf-8"))
    write_digest(folder, meta["topic"], meta["queries"], meta["days"], videos, picked)
    print(f"  자막 {got}개 추가")
    return folder


def write_digest(out: Path, topic, queries, days, videos, picked):
    lines = [f"# 유튜브 리서치 — {topic}", f"_검색어: {', '.join(queries)} · 최근 {days}일 · "
             f"찾은 영상 {len(videos)}개 중 {len(picked)}개 자막 대상, "
             f"수집 완료 {sum(1 for v in picked if v.get('transcript'))}개_", "",
             "| 조회수 | 날짜 | 길이 | 채널 | 제목 | 자막 |", "|---|---|---|---|---|---|"]
    for v in picked:
        ok = f"{len(v['transcript']):,}자" if v.get("transcript") else f"없음({v.get('transcript_error', '대기')})"
        lines.append(f"| {v['views']:,} | {v['date']} | {v['seconds'] // 60}분 | {v['channel']} | "
                     f"[{v['title']}]({v['url']}) | {ok} |")
    for v in picked:
        if v.get("transcript"):
            lines += ["", f"## {v['channel']} — {v['title']}", f"{v['url']} · 조회수 {v['views']:,}", "",
                      v["transcript"]]
    (out / "digest.md").write_text("\n".join(lines), encoding="utf-8")
