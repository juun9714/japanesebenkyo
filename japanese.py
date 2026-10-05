"""일본어 형태소 분석 + 읽기(후리가나) / 로마자 / 한글 발음 변환."""

import re

import fugashi

_tagger = fugashi.Tagger()

POS_KO = {
    "名詞": "명사",
    "代名詞": "대명사",
    "動詞": "동사",
    "形容詞": "형용사",
    "形状詞": "な형용사",
    "副詞": "부사",
    "連体詞": "연체사",
    "接続詞": "접속사",
    "感動詞": "감동사",
    "助詞": "조사",
    "助動詞": "조동사",
    "接頭辞": "접두사",
    "接尾辞": "접미사",
    "補助記号": "기호",
    "記号": "기호",
    "空白": "공백",
}

KANJI_RE = re.compile(r"[㐀-鿿豈-﫿々〆ヶ]")
KANA_RE = re.compile(r"^[぀-ヿー]+$")


def kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _furigana_parts(surface: str, reading: str) -> list[dict]:
    """한자가 섞인 단어에서 오쿠리가나를 분리해 한자 부분에만 루비를 단다.
    예: 行き / いき -> [{t:'行', r:'い'}, {t:'き'}]"""
    if not KANJI_RE.search(surface) or not reading:
        return [{"t": surface}]
    s_h = kata_to_hira(surface)
    # 앞쪽 공통 가나
    pre = 0
    while pre < len(s_h) and pre < len(reading) and s_h[pre] == reading[pre] and not KANJI_RE.match(surface[pre]):
        pre += 1
    # 뒤쪽 공통 가나
    suf = 0
    while (
        suf < len(s_h) - pre
        and suf < len(reading) - pre
        and s_h[-1 - suf] == reading[-1 - suf]
        and not KANJI_RE.match(surface[-1 - suf])
    ):
        suf += 1
    core = surface[pre : len(surface) - suf]
    core_r = reading[pre : len(reading) - suf]
    parts = []
    if pre:
        parts.append({"t": surface[:pre]})
    parts.append({"t": core, "r": core_r} if core_r else {"t": core})
    if suf:
        parts.append({"t": surface[len(surface) - suf :]})
    return parts


# ---- 로마자 / 한글 변환 -------------------------------------------------

_ROMA = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "ゐ": "i", "ゑ": "e", "を": "o", "ん": "n", "ゔ": "vu",
    "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o",
    "ゃ": "ya", "ゅ": "yu", "ょ": "yo", "ゎ": "wa",
}
_YOON = {"ゃ": "a", "ゅ": "u", "ょ": "o"}
_SMALL_V = {"ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o"}

# 한글: (초성, 중성) 조합 테이블
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

_CONS_KO = {
    "": "ㅇ", "k": "ㅋ", "g": "ㄱ", "s": "ㅅ", "sh": "ㅅ", "z": "ㅈ", "j": "ㅈ",
    "t": "ㅌ", "ch": "ㅊ", "ts": "ㅆ", "d": "ㄷ", "n": "ㄴ", "h": "ㅎ", "f": "ㅎ",
    "b": "ㅂ", "p": "ㅍ", "m": "ㅁ", "y": "ㅇ", "r": "ㄹ", "w": "ㅇ", "v": "ㅂ",
}
_VOW_KO = {
    ("", "a"): "ㅏ", ("", "i"): "ㅣ", ("", "u"): "ㅜ", ("", "e"): "ㅔ", ("", "o"): "ㅗ",
    ("y", "a"): "ㅑ", ("y", "u"): "ㅠ", ("y", "o"): "ㅛ", ("y", "e"): "ㅖ",
    ("w", "a"): "ㅘ", ("w", "i"): "ㅟ", ("w", "e"): "ㅞ", ("w", "o"): "ㅝ",
}


def _split_roma(r: str) -> tuple[str, str, str]:
    """로마자 음절을 (자음, 반모음, 모음)으로 분해."""
    v = r[-1]
    head = r[:-1]
    for cons in ("sh", "ch", "ts"):
        if head.startswith(cons):
            rest = head[len(cons):]
            # shi/chi 계열(sha, sho...)은 이미 구개음 -> y 반모음 취급
            return cons, "y" if cons in ("sh", "ch") and v in "auo" else rest, v
    if head == "j":
        return "j", "y" if v in "auo" else "", v
    if head in ("y", "w"):
        return "", head, v
    if len(head) == 2 and head[1] == "y":
        return head[0], "y", v
    return head, "", v


def _syllables(hira: str) -> list[str]:
    """히라가나 문자열을 로마자 음절 리스트로. 'っ'=Q, 'ん'=N, 장음=- 으로 표시."""
    out: list[str] = []
    i = 0
    while i < len(hira):
        c = hira[i]
        nxt = hira[i + 1] if i + 1 < len(hira) else ""
        if c == "っ":
            out.append("Q")
        elif c == "ん":
            out.append("N")
        elif c == "ー":
            out.append("-")
        elif c in _ROMA:
            base = _ROMA[c]
            if nxt in _YOON and c not in _YOON and base.endswith("i") and len(base) > 1:
                stem = base[:-1]
                if stem in ("sh", "ch", "j"):
                    base = stem + _YOON[nxt]
                else:
                    base = stem + "y" + _YOON[nxt]
                i += 1
            elif nxt in _SMALL_V and c not in _SMALL_V:
                # ファ, ティ, ウィ 같은 외래어 표기
                stem = {"ふ": "f", "て": "t", "で": "d", "う": "w", "ゔ": "v", "し": "sh", "ち": "ch", "じ": "j", "つ": "ts"}.get(c)
                if stem:
                    base = stem + _SMALL_V[nxt]
                    i += 1
            out.append(base)
        else:
            out.append(c)
        i += 1
    return out


def to_romaji(hira: str) -> str:
    syl = _syllables(hira)
    res = []
    for idx, s in enumerate(syl):
        if s == "Q":
            nxt = syl[idx + 1] if idx + 1 < len(syl) else ""
            res.append("t" if nxt.startswith("ch") else (nxt[:1] if nxt and nxt[0].isalpha() and nxt not in ("N",) else ""))
        elif s == "N":
            res.append("n")
        elif s == "-":
            res.append(res[-1][-1] if res and res[-1] and res[-1][-1] in "aiueo" else "-")
        else:
            res.append(s)
    return "".join(res)


def _compose(cho: str, jung: str, jong: str = " ") -> str:
    return chr(0xAC00 + (_CHO.index(cho) * 21 + _JUNG.index(jung)) * 28 + _JONG.index(jong))


def to_hangul(hira: str) -> str:
    syl = _syllables(hira)
    out: list = []
    for s in syl:
        if s in ("Q", "N"):
            if out and isinstance(out[-1], list):
                out[-1][2] = "ㅅ" if s == "Q" else "ㄴ"
            elif s == "N":
                out.append("ㄴ")
            continue
        if s == "-":
            out.append("-")
            continue
        if not s or not s[-1] in "aiueo":
            out.append(s)
            continue
        cons, glide, v = _split_roma(s)
        cho = _CONS_KO.get(cons, "ㅇ")
        jung = _VOW_KO.get((glide, v)) or _VOW_KO[("", v)]
        if v == "u" and cons in ("s", "z", "ts") and not glide:
            jung = "ㅡ"  # す→스, ず→즈, つ→쓰
        elif cons == "f" and v != "u":
            jung = _VOW_KO[("w", v)]  # ファ→화, フィ→휘
        out.append([cho, jung, " "])
    res = []
    for b in out:
        res.append(_compose(*b) if isinstance(b, list) else b)
    return "".join(res).replace("-", "ー")


# ---- 공개 함수 ----------------------------------------------------------

def _clean(v) -> str:
    return "" if v in (None, "*") else str(v)


def analyze(text: str) -> list[dict]:
    tokens = []
    for w in _tagger(text):
        f = w.feature
        surface = w.surface
        pos1 = _clean(f.pos1)
        kana = _clean(f.kana)
        if not kana and KANA_RE.match(surface):
            kana = surface
        reading = kata_to_hira(kana)
        has_kanji = bool(KANJI_RE.search(surface))
        is_symbol = pos1 in ("補助記号", "記号", "空白") or not reading
        base = _clean(f.orthBase) or surface
        base_reading = kata_to_hira(_clean(f.kanaBase))
        tok = {
            "s": surface,
            "pre": w.white_space,
            "sym": is_symbol,
        }
        if not is_symbol:
            tok.update(
                {
                    "r": reading,
                    "rm": to_romaji(reading),
                    "ko": to_hangul(reading),
                    "parts": _furigana_parts(surface, reading) if has_kanji else [{"t": surface}],
                    "base": base,
                    "baseR": base_reading,
                    "pos": POS_KO.get(pos1, pos1),
                    "pos2": _clean(f.pos2),
                }
            )
        tokens.append(tok)
    return tokens


# 조사·조동사 등 문법 요소는 기계 번역이 부정확하므로 직접 설명한다 (기본형 기준)
GRAMMAR_KO = {
    "は": "~은/는 (주제)", "が": "~이/가 (주어) · ~지만 (역접)", "を": "~을/를 (목적어)",
    "に": "~에, ~에게 (장소·시간·대상)", "へ": "~(으)로, ~에 (방향)", "で": "~에서 (장소) · ~(으)로 (수단)",
    "と": "~와/과 · ~(이)라고 (인용) · ~하면", "も": "~도", "の": "~의 · ~것 (명사화)",
    "から": "~부터, ~에서 · ~니까 (이유)", "まで": "~까지", "より": "~보다 · ~부터",
    "や": "~(이)랑, ~나 (나열)", "か": "~까? (의문) · ~(이)나", "ね": "~네, ~죠 (동의·확인)",
    "よ": "~요, ~야 (알림·강조)", "な": "~하지 마 (금지) · ~네 (감탄)", "ぞ": "~다고! (강조)",
    "て": "~하고, ~해서 (연결)", "ば": "~하면 (가정)",
    "けど": "~지만, ~는데", "けれど": "~지만, ~는데", "けれども": "~지만, ~는데",
    "し": "~하고 (이유 나열)", "ながら": "~하면서", "たり": "~하거나 (예시 나열)",
    "だけ": "~만, ~뿐", "しか": "~밖에 (부정과 함께)", "ばかり": "~만, ~뿐 · 막 ~함",
    "など": "~등", "って": "~(이)라고 · ~(이)란", "ので": "~때문에, ~해서", "のに": "~는데도 · ~하기 위해",
    "でも": "~라도", "ほど": "~만큼, ~정도", "くらい": "~정도", "ぐらい": "~정도", "ずつ": "~씩",
    "ます": "~ㅂ니다 (정중)", "です": "~입니다 (정중)", "だ": "~이다 (단정)", "た": "~했다 (과거·완료)",
    "ない": "~하지 않다 (부정)", "ぬ": "~하지 않다 (부정, 문어)", "ん": "~하지 않다 (부정, 구어)",
    "たい": "~하고 싶다", "たがる": "(남이) ~하고 싶어하다",
    "れる": "~되다 (수동) · ~할 수 있다 (가능) · 존경", "られる": "~되다 (수동) · ~할 수 있다 (가능) · 존경",
    "せる": "~하게 하다 (사역)", "させる": "~하게 하다 (사역)", "う": "~하자 · ~하겠지 (의지·추측)",
    "よう": "~하자 · ~하겠지 (의지·추측) · ~같다", "まい": "~하지 않겠다 · ~하지 않겠지",
    "らしい": "~인 것 같다 (추측) · ~답다", "そう": "~할 것 같다 · ~라고 한다 (전문)",
    "みたい": "~인 것 같다", "ちゃう": "~해 버리다 (구어)", "じゃう": "~해 버리다 (구어)",
    "べし": "~해야 한다", "ござる": "있다 (정중)", "やす": "~ㅂ니다 (방언)",
    # 품사에 따라 뜻이 갈리는 것: "기본형|품사"
    "ん|조사": "~인 것 (=の, 설명·강조)", "の|조사": "~의 · ~것 (명사화) · ~니? (의문)",
}

GRAMMAR_POS = {"조사", "조동사"}


def grammar_meaning(base: str, pos: str) -> str | None:
    if pos not in GRAMMAR_POS:
        return None
    return GRAMMAR_KO.get(f"{base}|{pos}") or GRAMMAR_KO.get(base)
