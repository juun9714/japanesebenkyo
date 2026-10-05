"""일본어 자막 줄 -> 한국어 번역.

ANTHROPIC_API_KEY 등 Claude 자격 증명이 있으면 Claude로 번역(문맥 반영, 학습용 품질),
없으면 무료 Google 번역 엔드포인트로 대체한다.
"""

import json
import logging
import os
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-opus-5-5"
CHUNK = 120  # Claude 요청 1회당 자막 줄 수
GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"

SYSTEM = (
    "당신은 일본어 학습자를 위한 자막 번역가입니다. 일본어 유튜브 자막을 줄 단위로 "
    "자연스러운 한국어로 번역합니다. 앞뒤 줄의 문맥을 참고하되, 각 줄의 번역은 그 줄의 "
    "내용만 담아 원문과 1:1로 대응시키세요(학습자가 원문과 비교하며 공부합니다). "
    "문장이 여러 줄로 나뉘어 있으면 각 조각에 해당하는 부분만 번역하세요. "
    "고유명사는 한국에서 통용되는 표기를 쓰세요."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"i": {"type": "integer"}, "ko": {"type": "string"}},
                "required": ["i", "ko"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["translations"],
    "additionalProperties": False,
}


def has_claude_credentials() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _translate_claude(lines: list[str]) -> list[str]:
    import anthropic

    client = anthropic.Anthropic()
    result = [""] * len(lines)
    for start in range(0, len(lines), CHUNK):
        chunk = lines[start : start + CHUNK]
        numbered = "\n".join(f"{start + k}\t{t}" for k, t in enumerate(chunk))
        response = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            system=SYSTEM,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[
                {
                    "role": "user",
                    "content": "다음 자막을 번역하세요. 각 줄은 `번호<TAB>원문` 형식이며, "
                    "모든 번호에 대해 번역을 반환하세요.\n\n" + numbered,
                }
            ],
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            raise RuntimeError(f"Claude 번역 중단: stop_reason={response.stop_reason}")
        text = next(b.text for b in response.content if b.type == "text")
        for item in json.loads(text)["translations"]:
            if 0 <= item["i"] < len(lines):
                result[item["i"]] = item["ko"]
    return result


def _google(text: str) -> str:
    data = urllib.parse.urlencode({"client": "gtx", "sl": "ja", "tl": "ko", "dt": "t", "q": text}).encode()
    req = urllib.request.Request(GOOGLE_URL, data=data, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    return "".join(seg[0] for seg in body[0] if seg[0])


def _translate_google(lines: list[str]) -> list[str]:
    result: list[str] = []
    # 여러 줄을 개행으로 묶어 요청 횟수를 줄인다
    batch: list[str] = []

    def flush():
        if not batch:
            return
        out = _google("\n".join(batch)).split("\n")
        if len(out) != len(batch):  # 줄 수가 어긋나면 줄 단위로 재시도
            out = [_google(t) for t in batch]
        result.extend(o.strip() for o in out)
        batch.clear()

    for t in lines:
        if sum(len(b) + 1 for b in batch) + len(t) > 3000:
            flush()
        batch.append(t.replace("\n", " "))
    flush()
    return result


def translate_lines(lines: list[str]) -> tuple[list[str], str]:
    """(번역 리스트, 사용한 번역기 이름)을 반환."""
    if has_claude_credentials():
        try:
            return _translate_claude(lines), "Claude"
        except Exception:
            log.exception("Claude 번역 실패, Google 번역으로 대체")
    return _translate_google(lines), "Google 번역"


WORD_SYSTEM = (
    "당신은 한국인 일본어 학습자를 돕는 일본어 사전입니다. 주어진 단어의 한국어 뜻을 "
    "사전처럼 짧게 알려주고, 주어진 문장에서 그 단어가 어떤 뜻·용법으로 쓰였는지 설명하세요. "
    "조사·조동사처럼 문법 요소라면 이 문장에서의 문법적 역할을 구체적으로 설명하세요 "
    "(예: た가 과거인지 완료인지, に가 장소인지 대상인지, て가 순서인지 이유인지). "
    "필요하면 비슷한 형태와 비교해 한두 문장으로 설명해도 됩니다. "
    "자막은 음성 인식 오류가 있을 수 있으니, 문장이 이상하면 원래 의도를 짐작해 설명하세요."
)

WORD_SCHEMA = {
    "type": "object",
    "properties": {
        "meaning": {"type": "string", "description": "사전적 뜻. 여러 뜻이면 '; '로 구분, 30자 이내"},
        "context": {"type": "string", "description": "이 문장에서의 뜻·용법·문법적 역할, 1~2문장"},
    },
    "required": ["meaning", "context"],
    "additionalProperties": False,
}


def _word_claude(base: str, surface: str, pos: str, sentence: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=WORD_SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": WORD_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[
            {
                "role": "user",
                "content": f"단어: {surface} (기본형: {base}, 품사: {pos})\n문장: {sentence}",
            }
        ],
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"Claude 단어 뜻 조회 중단: stop_reason={response.stop_reason}")
    text = next(b.text for b in response.content if b.type == "text")
    return {**json.loads(text), "source": "Claude"}


def word_meaning(base: str, surface: str, pos: str, sentence: str, grammar: str | None = None) -> dict:
    """{'meaning', 'context'(없으면 None), 'source'}를 반환.
    grammar: 조사·조동사의 문법 설명표 뜻. 있으면 그걸 뜻으로 쓰고 Claude에게는 문맥 설명만 받는다."""
    if has_claude_credentials():
        try:
            result = _word_claude(base, surface, pos, sentence)
            if grammar:
                result["meaning"] = grammar
            return result
        except Exception:
            log.exception("Claude 단어 뜻 조회 실패")
    if grammar:
        return {"meaning": grammar, "context": None, "source": "문법 설명"}
    return {"meaning": _google(base).strip(), "context": None, "source": "Google 번역"}
