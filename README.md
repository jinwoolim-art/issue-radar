# issue-radar

AI 숏폼 채널용 **핫이슈 레이더**. 여러 출처를 주기적으로 훑어서 "지금 뜨는 AI 이슈"를 점수로 매기고, 요금 페이지가 바뀌면 잡아낸다.

- 트랙 1 (핫이슈): `python -m radar scan` → `out/latest.md` (사람용), `out/latest.json` (브리프·영상 공장용)
- 트랙 2 (요금 감시): `python -m radar pricing` → `data/pricing/<업체>/` 에 스냅샷, 바뀌면 바뀐 줄 출력
- 스캔 원본은 **7일 뒤 자동 삭제** (반응 속도 계산용으로만 잠깐 보관). 요금 스냅샷은 계속 보관.

## 실행

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
cp .env.example .env                           # 키 채우기 (없어도 A등급 출처는 동작)
.venv/bin/python -m radar all
```

## 출처 추가·수정

코드 수정 없이 `config/sources.yaml` (출처), `config/entities.yaml` (업체·제품 사전, 코너 키워드)만 고친다.

| 등급 | 출처 | 상태 |
|---|---|---|
| A 무료 | OpenAI·Google·Anthropic 공식, Hacker News, GeekNews, AI타임스, GitHub 트렌딩 | 동작 |
| B 키 필요(무료) | Reddit, YouTube | `.env` 에 키 넣으면 동작 |
| A (브라우저) | ChatGPT 요금, Product Hunt | 다음 단계 |
| C 유료 | X(트위터) | 검토 예정 |

## 키 발급

**YouTube Data API 키**
1. https://console.cloud.google.com → 프로젝트 선택(또는 새로 만들기)
2. "API 및 서비스 → 라이브러리" → `YouTube Data API v3` 사용 설정
3. "사용자 인증 정보 → 사용자 인증 정보 만들기 → API 키" → `.env` 의 `YOUTUBE_API_KEY`
4. 하루 무료 10,000유닛. 검색(1회 100유닛)은 3시간마다만 해서, 30분 주기로 돌려도 하루 약 3,000유닛

**Reddit API 앱**
1. 레딧 로그인 → https://www.reddit.com/prefs/apps → 맨 아래 "create another app"
2. 이름 `issue-radar`, 종류 **script**, redirect uri `http://localhost:8080`
3. 앱 이름 아래 짧은 문자열 = `REDDIT_CLIENT_ID`, `secret` = `REDDIT_CLIENT_SECRET`
4. `REDDIT_USER_AGENT` 에 `issue-radar/0.1 by <레딧아이디>`

## 다음 단계

- Claude 키로 이슈 묶기(한/영 같은 이슈 합치기) + **숏폼 브리프** 생성
- 30분 주기 자동 실행 (맥: launchd / Windows 워크스테이션: 작업 스케줄러)
- 점수 높은 이슈만 댓글 심화 수집 → 유료 출처 전환 규칙
