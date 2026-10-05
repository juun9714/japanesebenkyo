"""유튜브 일본어 자막 학습기 - FastAPI 서버.

실행: .venv/bin/uvicorn app:app --reload  ->  http://127.0.0.1:8000
"""

import json
import os
import re
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable, YouTubeTranscriptApi

from japanese import analyze, grammar_meaning
from translate import has_claude_credentials, translate_lines, word_meaning

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"


def load_env(path: Path) -> None:
    """.env 파일의 KEY=VALUE 줄을 환경 변수로 읽는다 (이미 설정된 값은 유지)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env(ROOT / ".env")
CACHE.mkdir(exist_ok=True)

app = FastAPI()
yt = YouTubeTranscriptApi()

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
URL_RES = [
    re.compile(r"[?&]v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})"),
]


def parse_video_id(url: str) -> str | None:
    url = url.strip()
    if ID_RE.match(url):
        return url
    for r in URL_RES:
        m = r.search(url)
        if m:
            return m.group(1)
    return None


def fetch_japanese(video_id: str):
    """수동 일본어 자막 우선, 없으면 자동 생성 자막."""
    transcripts = yt.list(video_id)
    try:
        t = transcripts.find_manually_created_transcript(["ja"])
        kind = "manual"
    except NoTranscriptFound:
        t = transcripts.find_generated_transcript(["ja"])
        kind = "auto"
    return t.fetch(), kind


SENT_END = "。！？!?"
CLOSERS = "」』）)】"
MAX_SENT = 70  # 구두점 없이 이어지는 자동 자막을 자를 최대 글자 수
CACHE_VERSION = 2


def resegment(snippets) -> list[dict]:
    """자동 자막 조각을 이어 붙여 문장 단위로 다시 나눈다.
    조각 안의 각 글자 시각은 조각 길이에 비례해 배분한다."""
    chars: list[tuple[str, float, float]] = []  # (글자, 시작, 끝)
    for k, s in enumerate(snippets):
        text = s.text.replace("\n", " ").strip()
        end = s.start + s.duration
        if k + 1 < len(snippets):  # 자동 자막은 시간이 겹치므로 다음 조각 시작에서 자른다
            end = min(end, snippets[k + 1].start)
        end = max(end, s.start + 0.1)
        step = (end - s.start) / max(len(text), 1)
        for i, c in enumerate(text):
            chars.append((c, s.start + step * i, s.start + step * (i + 1)))
        chars.append(("", end, end))  # 조각 경계 표시

    sentences: list[dict] = []
    buf: list[tuple[str, float, float]] = []

    def flush():
        text = "".join(c for c, _, _ in buf).strip()
        if text:
            first = next(x for x in buf if x[0].strip())
            sentences.append({"start": first[1], "dur": buf[-1][2] - first[1], "ja": text})
        buf.clear()

    for i, ch in enumerate(chars):
        c = ch[0]
        if c == "":  # 조각 경계: 너무 길거나 다음 조각까지 공백이 길면 끊는다
            gap = chars[i + 1][1] - ch[2] if i + 1 < len(chars) else 0
            if len(buf) >= MAX_SENT or gap > 1.5:
                flush()
            continue
        buf.append(ch)
        nxt = chars[i + 1][0] if i + 1 < len(chars) else ""
        if c in SENT_END and (not nxt or nxt not in SENT_END + CLOSERS):
            flush()
        elif c in CLOSERS and buf[-2:-1] and buf[-2][0] in SENT_END:
            flush()
    flush()
    return sentences


def build(video_id: str) -> dict:
    try:
        fetched, kind = fetch_japanese(video_id)
    except VideoUnavailable:
        raise HTTPException(404, "영상을 찾을 수 없어요. 링크를 확인해 주세요.")
    except TranscriptsDisabled:
        raise HTTPException(404, "이 영상은 자막이 비활성화되어 있어요.")
    except NoTranscriptFound:
        raise HTTPException(404, "이 영상에는 일본어 자막(수동/자동)이 없어요.")

    snippets = [s for s in fetched.snippets if s.text.strip()]
    if kind == "auto":
        lines = resegment(snippets)
    else:  # 수동 자막은 보통 이미 문장/의미 단위로 나뉘어 있다
        lines = [{"start": s.start, "dur": s.duration, "ja": s.text.replace("\n", " ").strip()} for s in snippets]
    ko, translator = translate_lines([l["ja"] for l in lines])
    for l, k in zip(lines, ko):
        l["ko"] = k
        l["tokens"] = analyze(l["ja"])
    return {"version": CACHE_VERSION, "videoId": video_id, "kind": kind, "translator": translator, "lines": lines}


class ProcessReq(BaseModel):
    url: str
    refresh: bool = False


@app.post("/api/process")
async def process(req: ProcessReq):
    video_id = parse_video_id(req.url)
    if not video_id:
        raise HTTPException(400, "유튜브 링크 형식이 올바르지 않아요.")
    path = CACHE / f"{video_id}.json"
    if path.exists() and not req.refresh:
        cached = json.loads(path.read_text())
        if cached.get("version") == CACHE_VERSION:
            return cached
    data = await run_in_threadpool(build, video_id)
    path.write_text(json.dumps(data, ensure_ascii=False))
    return data


WORDS = CACHE / "words.json"
_words: dict = json.loads(WORDS.read_text()) if WORDS.exists() else {}
_words_lock = threading.Lock()


class WordReq(BaseModel):
    base: str
    surface: str
    pos: str
    sentence: str


def lookup_word(req: WordReq) -> dict:
    grammar = grammar_meaning(req.base, req.pos)
    claude = has_claude_credentials()
    if grammar and not claude:
        return {"meaning": grammar, "context": None, "source": "문법 설명", "hasClaude": False}
    # Claude는 문장 문맥까지 설명하므로 문장별로, Google은 단어별로 캐시
    key = f"{req.base}|{req.pos}"
    if claude:
        key += f"|{req.sentence}"
    if key not in _words:
        try:
            result = word_meaning(req.base, req.surface, req.pos, req.sentence, grammar)
        except Exception:
            raise HTTPException(502, "뜻을 가져오지 못했어요.")
        if claude and not result.get("context"):  # Claude 실패로 대체된 결과는 저장하지 않는다
            return {**result, "hasClaude": True}
        with _words_lock:
            _words[key] = result
            WORDS.write_text(json.dumps(_words, ensure_ascii=False))
    return {**_words[key], "hasClaude": claude}


@app.post("/api/word")
async def word(req: WordReq):
    return await run_in_threadpool(lookup_word, req)


@app.get("/api/history")
def history():
    items = []
    for p in sorted((p for p in CACHE.glob("*.json") if p != WORDS), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
        try:
            d = json.loads(p.read_text())
            first = next((l["ja"] for l in d["lines"] if l["ja"]), "")
            items.append({"videoId": d["videoId"], "preview": first[:40], "count": len(d["lines"])})
        except Exception:
            continue
    return items


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")
