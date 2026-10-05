# 자막단어장

유튜브 영상의 일본어 자막을 가져와서 모든 단어에 발음(히라가나 / 한글 / 로마자)을 달고, 한국어 번역을 붙여 주는 일본어 학습용 웹 서비스.

## 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --reload
```

브라우저에서 http://127.0.0.1:8000 을 열고 유튜브 링크를 붙여 넣으면 됩니다.

## 번역 엔진

- `ANTHROPIC_API_KEY`가 설정돼 있으면 **Claude**(`claude-opus-5-5`)로 번역합니다. 앞뒤 문맥을 보고 번역해서 자동 생성 자막처럼 문장이 잘게 끊긴 경우에도 자연스럽습니다.
- 키가 없거나 Claude 호출이 실패하면 무료 **Google 번역**을 씁니다.

Claude 키 넣는 법:

1. https://console.anthropic.com/settings/keys 에서 키 발급 (결제 수단 등록 필요)
2. `.env.example`을 `.env`로 복사하고 `ANTHROPIC_API_KEY=` 뒤에 키를 붙여 넣기
3. 서버 재시작

```bash
cp .env.example .env
open -e .env      # 텍스트 편집기로 열어서 키 붙여 넣고 저장
.venv/bin/uvicorn app:app --reload
```

`.env`는 `.gitignore`에 들어 있어 git에 올라가지 않습니다. 키를 넣으면 단어 카드에 **이 문장에서의 뜻**(조사·조동사는 문법적 역할, 예: た가 과거인지 완료인지)도 나옵니다.

처리 결과는 `cache/<영상ID>.json`에 저장됩니다. 번역 엔진을 바꾼 뒤 다시 번역하려면 해당 파일을 지우세요.

## 기능

- 수동 일본어 자막이 있으면 그걸 쓰고, 없으면 자동 생성 자막을 씁니다
  - 자동 자막은 문장 중간에서 끊긴 조각이라, 이어 붙인 뒤 `。？！` 기준으로 문장 단위로 다시 나눠서 번역합니다 (`app.py`의 `resegment`)
- 단어마다 발음 표시: 히라가나(한자 위에만) / 한글 / 로마자 / 숨기기
- 단어를 누르면 **뜻**과 읽기, 한글 발음, 로마자, 기본형, 품사, 사전 링크(네이버, Jisho)가 나옵니다
  - 일반 단어: Claude 키가 있으면 사전적 뜻과 "이 문장에서의 뜻"을, 없으면 Google 번역으로 뜻을 보여줍니다 (`cache/words.json`에 저장)
  - 조사·조동사(は, が, て, ます, た 등): 기계 번역이 부정확해서 `japanese.py`의 `GRAMMAR_KO` 문법 설명표를 씁니다
- 재생 위치에 맞춰 현재 줄을 강조하고 자동으로 스크롤합니다. 줄을 누르면 그 위치로 이동합니다
- 번역 가리기(마우스를 올리면 보임): 먼저 듣고 해석해 본 뒤 확인하는 연습용
- 한 줄 반복, 재생 속도 0.5 / 0.75 / 1
- 단축키: `←` `→` 이전/다음 줄, `Space` 재생/정지, `R` 한 줄 반복

## 구성

| 파일 | 역할 |
|---|---|
| `app.py` | FastAPI 서버: 자막 가져오기, 캐시, API |
| `japanese.py` | 형태소 분석(fugashi + UniDic), 후리가나 정렬, 로마자/한글 변환 |
| `translate.py` | Claude / Google 번역 |
| `static/index.html` | 화면 (YouTube IFrame 플레이어 + 자막 목록) |
