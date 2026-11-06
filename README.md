# MI3 — Global Freight & Trade Intelligence

**MI3**는 MI2(해운·항공 운송 크롤러)와 WorldMonitor(글로벌 병목·거시·국가 회복력)를 **하나의 대시보드**로 통합한 차세대 프로젝트입니다.

> MI2는 데이터 수집 계층, MI3는 통합·표현 계층입니다. MI3는 MI2의 `summary.json`과 SQLite 스냅샷을 읽고, WorldMonitor 공개 데이터를 병합해 1화면 SCM 인텔리전스를 제공합니다.

## 1. MI3 = MI2 + WorldMonitor

| 영역 | MI2 (데이터) | WorldMonitor (데이터) | MI3 (표현) |
|---|---|---|---|
| 해운 운임 | SCFI 18항로, BDI/BCI/BPI/BSI | Shipping rates (CCFI 등) | Freight 패널 |
| 선대/역량 | Linerlytica, Alphaliner Top100 | — | Freight 패널 |
| 포워더 | A&A Top 25 | — | Freight 패널 |
| 항공 운임 | TAC Index 3항로 | Airport delays | Freight 패널 |
| 유가 | Dubai/Brent/WTI, VLSFO 3항구 | Energy prices (EIA) | Energy 패널 |
| 원자재 | — | Commodity quotes | Energy 패널 (live) |
| 거시 | GSCPI, World GDP/CPI | Macro signals, World CPI, FRED | Macro 패널 |
| 병목 | — | 13개 해상 쵸크포인트 | Map + Bottleneck board |
| 국가 | — | 5-factor scorecard (196개국) | Resilience 패널 |
| 통합 | — | — | Composite + Transmission chain + Insights |

## 2. 데이터 소스 & 라이선스

| 소스 | 접근 | 라이선스 |
|---|---|---|
| MI2 `summary.json` + SQLite | 로컬 (`../MI2`) | © JamesJang-GU |
| WorldMonitor Chokepoint Status open data | `https://www.worldmonitor.app/data/v1/chokepoints/` | **CC-BY-4.0** |
| WorldMonitor Five-Factor Scorecard | `https://api.worldmonitor.app/api/scorecard/v1/list-five-factor-scorecards` | WorldMonitor |
| WorldMonitor API (선택) | `X-WorldMonitor-Key` | Pro/Enterprise key |

**Chokepoint attribution (필수):**
> WorldMonitor (https://www.worldmonitor.app). Scores and statuses are computed by WorldMonitor from IMF PortWatch, NGA Maritime Safety Information, and AIS data via aisstream.io.

전체 attribution/라이선스: `NOTICE.md`.

## 3. Quick start

```bash
# 1) 공개 데이터 갱신 (키 없이)
python3 fetch_worldmonitor.py --public-only

# 2) 대시보드 생성 (MI2 DB + WorldMonitor)
python3 make_map.py
python3 build.py

# 3) 단일 파일 생성 + 로컬 서버
python3 make_standalone.py
python3 -m http.server 8080
# → http://localhost:8080/
```

또는 `standalone.html`을 직접 열기 (단일 파일, 외부 의존성 없음).

### Live 모드 (선택)

```bash
export WORLDMONITOR_API_KEY=wm_xxx
python3 fetch_worldmonitor.py
python3 build.py
python3 make_standalone.py
```

Live 데이터: shipping rates, commodity quotes, energy prices, chokepoint history/bypass, country chokepoint exposure, macro signals, world CPI, FRED series. 헤더의 `MI3 LIVE` 칩 클릭 → 상세.

## 4. 화면 구성

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SYS 복합 스트레스 │ MAP 13개 쵸크포인트 │ ALERT signal feed                    │
├──────────────────────────────────────────────┬───────────────────────────────┤
│ CHOKE 병목 보드 (13행)                       │ FREIGHT & CAPACITY (7 cards)   │
├───────────────────┬───────────────────┬──────┴───────────────────────────────┤
│ ENERGY & BUNKER   │ GLOBAL ECONOMY    │ RESILIENCE (top/bottom 5 + 196)     │
├───────────────────┴───────────────────┴──────────────────────────────────────┤
│ TRANSMISSION CHAIN (chokepoint→freight→energy→macro→consumer) │ KEY INSIGHTS │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **복합 스트레스 지수**: 0–100, `0.40*chokepoint + 0.25*freight + 0.20*energy + 0.15*macro`
- **클릭**: 지도 노드, 병목 행, 지표 카드, 국가, 체인 노드, 인사이트, 알림 → 상세 drawer
- **상세 drawer**: 시계열 차트(hover), 통계, 관련 표(SCFI 항로/BDI 서브/선대 상태/Top 오퍼레이터/포워더/VLSFO 항구), 관련 지표 pill, 출처
- **국가 전체 196개**: `ALL 196 →` → 검색 가능한 전체 랭킹
- **반응형**: 1440×900 1화면, <1250px 2열, <760px 1열

## 5. 파일 구조

```
MI3/
├── index.html              # 대시보드 (data.js 참조)
├── standalone.html         # data.js 인라인 단일 파일
├── data.js                 # build.py 생성 (window.UNIFIED + window.WORLD_MAP)
├── build.py                # MI2 DB + WorldMonitor JSON → unified.json / data.js
├── fetch_worldmonitor.py   # 공개 데이터 + 선택적 live API 수집
├── make_map.py             # worldmonitor TopoJSON → SVG land path
├── make_standalone.py      # index.html + data.js → standalone.html
├── mi3.config.json         # 프로젝트 설정 (MI2/WorldMonitor 경로)
├── Makefile                # fetch / build / standalone / serve
├── data/
│   ├── unified.json        # 통합 데이터
│   ├── world-map.json      # SVG land path
│   ├── chokepoints-*.json  # WorldMonitor 일별 스냅샷
│   ├── chokepoints-latest.json
│   ├── scorecard.json
│   └── worldmonitor-live.json  # live 모드에서만 생성 (gitignore)
├── shot-main.png
├── shot-detail.png
└── NOTICE.md
```

## 6. 운영 아키텍처

```
MI2 GitHub Actions (매일 00:00 KST)
  └─ 7개 크롤러 → <module>.db
        └─ run_all.py --summary-only → summary.json
                    │
WorldMonitor open data (매일 06:23 UTC)                │
  └─ chokepoints/{date}.json + latest.json             │
  └─ scorecard (public)                                │
                    │                                  │
                    └──────────► MI3 build.py ◄────────┘
                                      │
                                      ├─ data/unified.json
                                      ├─ data.js
                                      └─ standalone.html
                                      │
                              GitHub Pages / 정적 호스팅
```

### 배포 옵션

1. **정적(현재)**: GitHub Pages에 `index.html` + `data.js` + `standalone.html` 업로드. 서버 비용 0.
2. **자동화**: GitHub Actions cron으로 `fetch_worldmonitor.py --public-only && make_map.py && build.py && make_standalone.py` 실행 후 커밋.
3. **Live**: `WORLDMONITOR_API_KEY`를 GitHub Secret으로 추가. API 한도/비용 모니터링.
4. **프론트 교체**: `data/unified.json` 스키마를 유지하면 React/Vue/Next.js로 이식 가능.

## 7. 복합 지수 계산식

```text
chokepoint = 0.5*weighted_avg + 0.3*max + 0.2*top3_avg + 10*flow_stress
             weights: hormuz .20, malacca .18, suez .15, bab_el_mandeb .13, panama .08, … (합 1.0)
freight    = 50 + 8*z(SCFI) + 8*z(BDI) + 5*z(TAC)
energy     = 50 + 6*z(Brent) + 6*z(VLSFO Singapore)
macro      = 50 + 20*(GSCPI-1) + 3*(CPI-2.5) - 2*(GDP-3)
composite  = 0.40*chokepoint + 0.25*freight + 0.20*energy + 0.15*macro
z(x)       = 1년 z-score; 50 = 1년 평균
```

- `flow_stress` = `mean(clamp(1 - flow_ratio, 0, 1))` (flow_ratio가 있는 쵸크포인트만)
- `top3_avg` = disruption score 상위 3개 평균
- **한계**: 가중치/체인은 휴리스틱. WorldMonitor/MI2 공식 지수 아님.

## 8. 현재 스냅샷 (2026-11-05)

- 복합 지수 **56.6 / elevated**
- Chokepoint 51.0 · Freight 63.4 · Energy 58.7 · Macro 57.4
- 최다 위험: **Strait of Hormuz 75 (war_zone)**, Kerch 70 (war_zone), Bab el-Mandeb 40 (critical)
- SCFI 3,687.35 · BDI 2,694 · TAC 5.21
- Brent 94.62 (-8.7%) · WTI 88.12 (-8.3%) · VLSFO Singapore 901.5 $/ton (-4.2%)
- GSCPI 1.28 · World CPI 3.04% · World GDP 2.92%


## 10. GitHub에 올리기 / 배포

### 1) GitHub에서 repo 생성
- https://github.com/new → 이름 `MI3` → Public → Create.
- 또는 CLI(gh)가 있으면:
  ```bash
  gh repo create JamesJang-GU/MI3 --public --source=. --push
  ```

### 2) Local MI3 push
```bash
cd /home/user/MI3
git remote add origin https://github.com/JamesJang-GU/MI3.git
git push -u origin main
```

### 3) GitHub Pages
- Settings → Pages → Build and deployment → Source: **Deploy from a branch**
- Branch: **main** → /(root) → Save
- URL: `https://jamesjang-gu.github.io/MI3/`

### 4) Daily build workflow (이미 포함됨)
`.github/workflows/mi3-daily.yml`
- 매일 **01:00 KST** (`cron: "0 16 * * *"`)
- MI2 repo clone → WorldMonitor 공개 데이터 fetch → `build.py` → `make_standalone.py` → commit/push
- MI2의 00:00 KST 크롤링이 끝난 뒤 실행되도록 01:00 KST로 설정
- `data/world-map.json`은 커밋되어 있으므로 CI에서는 `make_map.py`를 실행하지 않음 (지도 갱신 시에만 로컬에서 실행 후 커밋)

### 5) Live 모드 (선택)
- GitHub Settings → Secrets and variables → Actions → New repository secret
  - 이름: `WORLDMONITOR_API_KEY`
  - 값: `wm_xxx`
- `.github/workflows/mi3-daily.yml`의 fetch step을 `python3 fetch_worldmonitor.py --public-only` → `python3 fetch_worldmonitor.py`로 변경
- `data/worldmonitor-live.json`은 `.gitignore`에 포함되어 커밋되지 않지만, `build.py`가 읽어 `data.js`에 live 데이터를 포함함
- API 한도/비용 모니터링 필요

### 6) 확인
- `https://jamesjang-gu.github.io/MI3/` 열기
- 헤더 `MI3 CORE`, 10개 패널, 13개 지도 노드, 196개국 확인
- 쵸크포인트/지표/국가 클릭 → 상세 drawer
- Actions 탭에서 `mi3-daily` 실행 로그 확인

## 9. 한계 / 다음 단계

- **원자재**: MI2에는 유가만 있어 금/구리/리튬 등은 WorldMonitor `list-commodity-quotes` (key)로 보강.
- **뉴스/분쟁**: WorldMonitor news/conflict API는 key 필요. 현재는 수치형 지표 중심.
- **상관분석**: 체인 가중치는 정성적. 실제 시계열 상관/회귀로 보정 가능.
- **알림**: 임계치 초과 시 Slack/Teams/Telegram 웹훅 연동 가능.
- **라이선스**: 데이터 라이선스는 `NOTICE.md` 참조. 코드 라이선스는 별도 지정 필요.
