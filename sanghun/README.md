# Stablecoin Event Dashboard

스테이블코인 제도화·입법·신뢰 충격과 시장 가격의 움직임을 비교하는 정적 웹 대시보드입니다.

기존 `stablecoin_event_dashboard.html`을 GitHub에 업로드하고 수정하기 편하도록 HTML, CSS, JavaScript, 데이터로 분리했습니다. 기존 데이터와 분석 방식은 그대로 유지했습니다.

## 빠르게 실행하기

압축을 푼 뒤 `index.html`을 Chrome 또는 Edge로 열면 실행됩니다. `assets` 폴더는 `index.html`과 같은 위치에 두세요.

- Node.js, npm, 빌드 과정, API 키가 필요하지 않습니다.
- 데이터가 포함되어 있어 인터넷 없이도 차트와 CSV 다운로드를 사용할 수 있습니다.
- 이벤트 원문 링크를 열 때만 인터넷이 필요합니다.

개발 중 로컬 서버를 사용하고 싶다면 프로젝트 폴더에서 다음 명령을 실행합니다.

```bash
python -m http.server 8000
```

브라우저에서 `http://localhost:8000`으로 접속합니다.

## 파일 구성

| 파일 | 역할 |
| --- | --- |
| `index.html` | 대시보드 화면과 입력 컨트롤 |
| `assets/style.css` | 레이아웃, 색상, 반응형 화면 |
| `assets/app.js` | SVG 차트, 이벤트 선택, 수익률 표시, CSV 다운로드 |
| `assets/data.js` | 15개 시계열과 41개 이벤트를 담은 기존 데이터 스냅샷 |
| `.nojekyll` | GitHub Pages에서 정적 파일을 그대로 서비스하도록 설정 |
| `.gitignore` | 환경설정 및 임시 파일의 Git 추적 제외 |

## GitHub에 업로드하기

1. GitHub에서 새 저장소를 만듭니다. 예시 이름: `stablecoin-event-dashboard`.
2. ZIP 파일을 압축 해제합니다.
3. `index.html`, `assets` 폴더, `README.md` 등 **프로젝트 폴더 안의 파일**을 저장소 최상위에 업로드합니다. ZIP 자체를 올리면 웹사이트로 실행되지 않습니다.
4. 업로드한 변경사항을 커밋합니다.

Git 명령어를 사용하는 경우, 프로젝트 폴더에서 다음을 실행합니다. `<YOUR-USER>`를 자신의 GitHub 계정명으로 바꾸고 저장소 이름도 실제 이름과 맞추세요. 아래 명령은 비어 있는 새 원격 저장소를 기준으로 합니다.

```bash
git init
git add .
git commit -m "Add stablecoin event dashboard"
git branch -M main
git remote add origin https://github.com/<YOUR-USER>/stablecoin-event-dashboard.git
git push -u origin main
```

## GitHub Pages로 웹에서 보기

1. 저장소의 **Settings → Pages**로 이동합니다.
2. **Build and deployment → Source**에서 **Deploy from a branch**를 선택합니다.
3. 브랜치는 **main**, 폴더는 **/ (root)**를 선택하고 저장합니다.
4. 게시가 완료되면 Pages 설정에 표시되는 주소를 엽니다.

일반적인 프로젝트 사이트 주소는 다음 형태입니다.

```text
https://<YOUR-USER>.github.io/stablecoin-event-dashboard/
```

상대경로를 사용하므로 저장소 이름이 달라도 동작합니다. GitHub Pages 사용 가능 여부는 저장소 공개 범위와 계정 요금제에 따라 달라질 수 있습니다.

공식 안내:

- https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site

## 포함된 기능

- 2015년 1월 1일~2026년 9월 30일의 관측 가능한 일별 시계열
- BTC, ETH, SOL의 가격과 기준값 100 지수
- Circle(CRCL), Coinbase(COIN), PayPal(PYPL), Robinhood(HOOD), Visa(V), Mastercard(MA)
- USDT·USDC의 달러 가격과 페그 이탈
- SPY·BIL·IRX·TNX 비교 변수
- GENIUS·CLARITY 입법, 규제, 채택, 신뢰 충격 등 41개 이벤트
- 이벤트 당일 및 전후 구간 반응, 주식의 SPY 초과수익률
- 기간 선택, 종목 표시 전환, 이벤트 원문 링크
- 일별 가격·이벤트·이벤트 반응·일별 이벤트 더미 CSV 및 전체 JSON 다운로드

## 코드 수정하기

- 화면 문구·구성: `index.html`
- 색상·간격·모바일 화면: `assets/style.css`
- 차트·입력 처리·파일 다운로드: `assets/app.js`
- 가격과 이벤트 데이터: `assets/data.js`

`data.js`를 먼저 로드하고 `app.js`가 이어서 실행됩니다. 두 파일의 순서를 바꾸거나 `async` 속성을 추가하지 마세요.

`assets/app.js`의 주요 함수:

| 함수 | 역할 |
| --- | --- |
| `setup` | 화면 초기화 및 이벤트 핸들러 등록 |
| `lineChart` | SVG 차트 생성 및 툴팁 처리 |
| `renderMain` | 코인·주식·스테이블코인 시계열 표시 |
| `showEvent` | 선택 이벤트 변경 |
| `renderEventChart` | 이벤트 전후 경로 표시 |
| `renderHeatmap` | 이벤트별 수익률 표 표시 |
| `applyRange` | 표시 기간 변경 |
| `csvDownload` | CSV 파일 생성 및 다운로드 |

## 데이터 구조와 갱신

이 프로젝트는 기존 분석 결과를 표시하는 **정적 스냅샷**입니다. 실시간 데이터 수집기나 자동 갱신 기능은 포함하지 않습니다. 이번 코드 분리 작업에서 시세·입법 내용을 다시 수집하거나 재검증하지 않았습니다.

`assets/data.js`는 `window.STABLECOIN_DATA`에 다음 정보를 저장합니다.

- `dates`: 오름차순 날짜 배열
- `assets`: 자산별 종가(`p`), 수정종가(`a`), 관측 범위와 출처
- `events`: 이벤트 날짜·유형·원문·사전 계산된 자산별 반응
- `audit`: 자산별 관측 개수 등 데이터 범위

`p[i]`와 `a[i]`는 `dates[i]`에 대응합니다. 관측값이 없는 날은 `null`입니다. 이벤트의 `responses`에는 수익률 창과 전후 경로가 이미 계산되어 있습니다. **가격 배열만 바꾸면 이벤트 반응 값은 자동으로 다시 계산되지 않습니다.** 데이터를 갱신하려면 `responses`, 관측 범위, 건수 및 화면의 기준일 문구도 함께 갱신해야 합니다.

분석 기준과 출처는 대시보드의 ‘분석 기준과 데이터 범위’, ‘41개 이벤트의 원문 링크’에도 들어 있습니다. 가격 출처는 Yahoo Finance 및 초기 구간의 Coin Metrics입니다.

## 해석 기준

- 상장·출시 전 값과 휴장일은 채우지 않았습니다.
- 이벤트와 가격의 동시 움직임을 보여주며 인과효과를 확정하는 분석은 아닙니다.
- 코인의 UTC 일별 가격과 미국 주식의 거래일 종가는 동일한 시간 구간이 아닙니다.
- 초기 스테이블코인 집계가격의 극값과 공급자 변경 구간에 관한 설명을 기존 화면에 보존했습니다.
- 주식의 SPY 초과수익률은 단순 차감 값이며 시장모형 CAR가 아닙니다.

가격 데이터의 이용 조건은 원 제공자의 조건을 따릅니다.
