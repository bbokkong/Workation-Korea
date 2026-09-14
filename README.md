# Workation Korea - GitHub Pages 전용

이 저장소 하나만으로 **정적 웹사이트 공개 + GitHub Actions 자동 데이터 갱신**을 할 수 있게 만든 버전입니다.
별도 Render/Python 서버/SQLite 서버는 필요하지 않습니다.

## 1. 가장 쉬운 배포 순서

1. GitHub에서 새 저장소를 만들고 이름을 예: `workation-korea`로 정합니다.
2. 이 ZIP을 풀고 **안의 파일/폴더 전체**를 저장소의 최상위에 업로드합니다.
   - `.github` 폴더도 반드시 포함해야 합니다.
   - GitHub 웹 업로드에서 숨김 폴더 업로드가 번거로우면 GitHub Desktop을 쓰는 것이 가장 쉽습니다.
3. 기본 브랜치가 `main`인지 확인합니다.
4. 저장소에서 **Settings -> Pages**로 이동합니다.
5. **Build and deployment -> Source**를 **GitHub Actions**로 선택합니다.
6. 상단 **Actions** 탭에서 `Update workation data and deploy Pages`가 실행되는지 확인합니다.
7. 첫 배포가 끝나면 `Settings -> Pages`에 공개 주소가 표시됩니다.
   - 보통 `https://사용자명.github.io/workation-korea/` 형태입니다.

## 2. 자동 업데이트

`.github/workflows/pages.yml`이 6시간마다 실행됩니다.

- 공식 프로그램 URL 방문
- `모집중 / 모집예정 / 마감 / 확인필요` 판정
- 공개된 경우 신청 마감일 추출
- 공개된 경우 잔여 인원/좌석 추출
- `site/data/programs.json` 업데이트
- 변경된 데이터를 GitHub 저장소에 자동 커밋
- GitHub Pages 재배포

GitHub Actions의 예약 실행은 GitHub 상황에 따라 정확히 정각에 시작되지 않고 지연될 수 있습니다.

## 3. 처음 즉시 데이터 확인하기

자동 6시간 주기를 기다릴 필요가 없습니다.

1. GitHub 저장소 -> **Actions**
2. `Update workation data and deploy Pages` 클릭
3. **Run workflow**
4. 테스트하려면 `5`, 전체 확인이면 `0`
5. **Run workflow** 클릭

전체 93개 프로그램을 순서대로 확인하므로 몇 분 걸릴 수 있습니다.

## 4. GitHub Actions 권한이 막힐 때

`Settings -> Actions -> General -> Workflow permissions`에서
**Read and write permissions**를 선택하고 저장하세요.

이 권한이 있어야 Actions가 갱신된 `programs.json`을 저장소에 자동 커밋할 수 있습니다.

## 5. 파일 구조

```text
.
├── .github/
│   └── workflows/
│       └── pages.yml
├── scripts/
│   ├── update_programs.py
│   ├── scrapers.py
│   └── requirements.txt
├── site/
│   ├── index.html
│   ├── .nojekyll
│   └── data/
│       ├── programs.json
│       └── sync_status.json
└── README.md
```

## 6. 지도

웹앱은 Leaflet + OpenStreetMap을 사용하고 실제 대한민국 시·도/시·군·구 GeoJSON을 불러와 클릭 필터를 제공합니다.
지도 타일과 행정경계 데이터는 브라우저에서 외부 공개 서비스에 접속하므로 사용자의 인터넷 연결이 필요합니다.

## 7. 자동 판정의 한계

공식 사이트의 HTML에 모집상태/마감일/잔여좌석이 텍스트로 공개되어 있을 때 가장 잘 작동합니다.
JavaScript로만 렌더링되는 사이트, 로그인/캡차가 필요한 사이트, 잔여 객실을 공개하지 않는 사이트는 `확인필요` 또는 `공식 미공개`로 남을 수 있습니다.

특히 **남은 자리 숫자는 추정하지 않습니다.** 공식 페이지에 숫자가 확인되는 경우에만 표시합니다.

## 8. 사이트 내용 수정

`site/index.html`을 수정하고 `main` 브랜치에 저장하면 GitHub Actions가 다시 배포합니다.
`site/data/programs.json`은 자동화가 수정하므로 직접 수정할 경우 다음 자동 실행에서 값이 달라질 수 있습니다.
