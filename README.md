# QA Train

하나의 소스에서 AST를 생성하거나, Ver.A와 Ver.B의 로컬 코드·Git 버전·엔진 프로젝트·APK·IPA를 비교해 변경 지점과 QA 영향 후보를 찾는 정적 분석 프로젝트입니다.

현재는 **1차 MVP와 Streamlit Cloud 기능 확인 환경이 완료된 상태**입니다. Cloud 앱은 기존 비교·AST 기능을 빠르게 확인하는 용도로 유지하고, 로컬 앱은 공개 기본 규칙 팩을 검증·설치해 로컬 분석에 사용하는 구조를 준비하고 있습니다. 외부 LLM API는 사용하지 않습니다.

> 기준일: 2026-10-24
>
> 운영 형태: 로컬 실행 / [Streamlit Cloud](https://apptrain-akecrcbajuvarqhr2dgtcs.streamlit.app/)

## 프로젝트 목표

```text
Ver.A / Ver.B 입력
→ 비교 가능한 스냅샷으로 변환
→ 파일 및 코드 변경 탐지
→ 변경 심볼의 호출·참조·값 흐름 추적
→ 제품 기능과 기존 TC 연결
→ QA 영향 설명 및 회귀 테스트 후보 제시
```

분석 대상 코드는 실행하거나 import하지 않습니다. 결과는 변경 영향과 회귀 테스트의 **후보 및 근거**이며, 실제 제품의 Pass/Fail 판정은 아닙니다.

## 현재 진행도

| 영역 | 상태 | 현재 구현 |
|---|---|---|
| 입력 변환 | ✅ 완료 | 로컬 파일·폴더, Git ref, Unity·Unreal·Godot 프로젝트, APK, IPA를 스냅샷으로 준비 |
| 기본 파일 비교 | ✅ 완료 | 상대 경로·파일 크기·SHA-256 기준으로 추가·삭제·수정 탐지 |
| Git 버전 선택 | ✅ 완료 | 저장소의 브랜치를 목록에서 고른 뒤 최근 커밋 선택, 서로 다른 저장소도 Ver.A·Ver.B에서 독립 조회 |
| Python AST 분석 | ✅ 완료 | 함수·클래스·import·호출·변수 대입·제어 흐름 추출 |
| 언어 중립 분석 구조 | ✅ 1차 완료 | 공통 그래프·근거·분석 한계·어댑터 레지스트리, Python 정밀 어댑터와 Tree-sitter 공통 어댑터 |
| 단일 입력 AST 화면 | ✅ 완료 | 맨 오른쪽 `_AST` 탭에서 단일 소스 분석, 데이터·설정 파일을 포함한 프로젝트 트리와 AST 보고서 다운로드 |
| 코드 영향 분석 | ✅ 완료 | 변경 심볼과 상위 호출·참조 관계 탐색 |
| 기능·TC 수동 매핑 | 🟡 1차 완료 | 사용자가 제공한 기능 매핑 JSON으로 코드 진입점과 기존 TC 후보 연결 |
| UI·API·DB 매핑 | ⬜ 계획 | 화면·컴포넌트·API·백엔드 심볼·데이터 키·TC를 승인 상태와 함께 연결 |
| 값 흐름 해석 | 🟡 1차 완료 | 반환값 → 변수 → 인자 → 매개변수 → 반환·상태 쓰기 후보 추적 |
| 기존 Streamlit UI | ✅ 확장 | Ver.A·Ver.B 준비, 분석 언어 직접 선택, 비교, 흐름 해석, 결과 다운로드 |
| 로컬 웹 앱 전환 | 🟡 규칙 팩 기반 구현 | 버전 규칙 팩 생성·SHA-256 검증·원자적 로컬 설치 완료, 브라우저 UI와 자동 업데이트는 다음 단계 |
| AST/UI 역할 분리 | ✅ 완료 | `AST`는 분석 엔진, `streamlit`은 UI·웹 세션으로 독립 구성 |
| APK·IPA 분석 | 🟡 일부 지원 | 동일 형식끼리 파일 구성 비교, IPA `Info.plist` 메타데이터 확인 |
| 기본 규칙 검색 | 🟡 구조 완료 | 기본 규칙만 임베딩하며 사용자 프로젝트 코드는 임베딩 저장하지 않음 |
| 로컬 LLM 해석 | ⬜ 계획 | 검색 근거와 AST를 로컬 코드 모델에 전달해 기능 영향과 QA 확인 항목을 설명 |
| 다국어 코드 분석 | 🟡 1차 완료 | Tree-sitter 기반 구문·심볼·import·호출 후보 비교. Python만 참조·값 흐름 정밀 분석 |
| Streamlit Cloud 배포 | ✅ 완료 | `main`의 `streamlit/streamlit_app.py`, Python 3.12, 서버 로컬 입력 비활성화 |
| 공개 서비스 운영 강화 | ⬜ 계획 | 인증, 작업 시간 제한과 임시 세션 보관 정책 |
| 공개 규칙 학습 데이터 | 🟡 팩 구조 완료 | 733개 후보는 모두 `pending`; `metadata_only` 초안 팩 생성 완료, 검수와 규칙 임베딩은 대기 |
| 로컬 모델 배포 | 🟡 다운로드 기반 구현 | 고정된 임베딩 모델을 최초 실행 시 내려받는 경계 구현, 코드 분석용 로컬 LLM은 미선정 |
| 로컬 프로젝트 분석 | ⬜ 계획 | 프로젝트 코드는 AST·관계 그래프·통계로 분석하고 공통 규칙이나 프로젝트 벡터 DB에 누적하지 않음 |
| 영향도·신뢰도 계산 | ⬜ 계획 | 변경 노드의 직접·간접·데이터·조건부 영향과 근거 경로 계산 |

**현재 위치:** Cloud 앱은 기존 비교·AST 기능 확인용으로 유지한다. 로컬 앱은 공개 기본 규칙 팩만 웹에서 받고, 임베딩 모델과 향후 코드 분석 모델은 사용자 PC에 내려받아 실행한다. 사용자 코드·AST·DB 스키마·분석 결과는 외부로 보내지 않으며 프로젝트 코드는 임베딩 저장하지 않는다. 현재는 규칙 팩 생성·검증·로컬 설치 경계까지 구현했다. 상세 체크리스트는 [`IMPACT_ANALYSIS_PLAN.md`](IMPACT_ANALYSIS_PLAN.md)에 있다.

검증 기준:

- 2026-10-25 다중 언어 파서·선택 UI 회귀: AST 엔진 80개 + Streamlit 87개 = 167개 통과
- 규칙 팩 별도 검증 기록: `learn` 7개 + `local_runtime` 10개 = 17개 통과
- TypeScript 실비교에서 변경 함수와 1단계 상위 호출자 후보 확인

전체 회귀 기록과 이번 변경 범위 테스트를 구분한다. 일반 업데이트에서는 변경한 기능과 직접 연결된 테스트만 실행하며, 전체 회귀 테스트는 별도로 실행했을 때 수치를 갱신한다.

반복 비교용 파일은 [`Test/ast_compare_fixture.py`](Test/ast_compare_fixture.py) 하나를 Git에서 계속 추적한다. 비교 기능을 확인할 때 `git log --oneline -- Test/ast_compare_fixture.py`에서 기준·대상 커밋을 고르고 비교 루트를 `Test`로 지정한다. 새 fixture를 매번 만들고 삭제하지 않으며, 비교 시나리오를 바꿀 필요가 있을 때만 이 파일의 `FIXTURE_REVISION`과 통제된 코드 구간을 갱신한다.

## 지금 할 수 있는 것

### 소스 하나에서 AST 생성

맨 오른쪽 `_AST` 탭에서 `.py`, `.ipynb`, 프로젝트 ZIP, Git 커밋 하나 또는 준비한 Python 소스를 선택하고 **AST 생성**을 누릅니다. 로컬 실행에서는 서버 PC의 소스 경로도 사용할 수 있습니다.

- 트리형: Python 표준 `ast.dump(tree, indent=2)`를 `text` 코드 블록에 보존한 Markdown
- 정리형: 함수·클래스·import·호출·변수 대입·제어 흐름을 원본 순서로 정리한 Markdown·JSON
- 프로젝트 파일 트리: 데이터·설정·리소스까지 폴더 계층으로 표시하고 파일별 상대 경로·종류·크기·SHA-256 확인
- 파일 선택 시 해당 Python 파일·노트북 셀의 AST 표시. 정리형 JSON의 `files[].ast_paths`로 파일과 AST 위치 연결
- 파일·코드 셀별 파싱 오류를 같은 보고서에 보존
- `file_tree.md`를 포함한 보고서 4개를 묶은 ZIP 다운로드
- 비교 결과와 독립적인 입력·분석 상태. 탭 이동이나 결과 형식 변경으로 재분석하지 않음
- 분석 완료 후 사이드바의 **세션 데이터 정리**로 현재 세션의 입력 복사본·스냅샷·보고서 삭제

### 한 화면에서 Ver.A와 Ver.B 비교

각 버전은 서로 다른 방식으로 준비할 수 있습니다.

- 업로드한 파일·ZIP·APK·IPA
- Streamlit 서버 PC의 로컬 파일·폴더
- 공개 GitHub 저장소 또는 로컬 Git 저장소의 ref·커밋
- 현재 브라우저 세션에서 이미 준비한 스냅샷

Git 입력에서는 저장소 주소를 넣고 브랜치 목록을 불러온 뒤, 선택한 브랜치의 날짜·메시지·SHA를 보고 각 버전을 고릅니다. 같은 저장소는 `비교`와 `_AST`에서 브랜치·커밋 조회 결과를 공유하고, 서로 다른 저장소는 각각 독립된 목록을 유지합니다. 같은 이력을 사용하면 Ver.A는 직전 커밋, Ver.B는 최신 커밋을 기본값으로 사용합니다.

### 선택 언어 코드 영향 분석

비교 화면에서 분석할 언어를 직접 선택합니다. 선택하지 않으면 파서를 실행하지 않고 파일 구성만 비교합니다. JavaScript/TypeScript, Vue/Svelte/Astro, JVM, .NET, 네이티브, 데이터·스크립트, 인프라 언어는 Tree-sitter 공통 어댑터로 구문·심볼·import·호출 후보를 비교합니다. Python은 아래 정밀 분석 범위를 추가로 제공합니다.

- AST 구조가 바뀐 함수·메서드·클래스·모듈 범위 탐지
- 주석·공백·단순 줄 이동을 코드 변경에서 제외
- 이전 및 최신 버전의 호출·참조 관계 역추적
- 원본 diff, AST diff, 파일·줄·심볼 근거 보존
- 기능 진입점과 기존 TC ID를 매핑해 회귀 확인 후보 표시
- Markdown·JSON 보고서 다운로드

### AST 연결·값 흐름 해석

변경 심볼을 선택하면 Ver.A와 Ver.B에서 값이 어디로 전달되는지 정적으로 추적합니다.

- 명시적인 반환값과 함수 호출 결과
- 변수 대입·재대입
- 호출 인자와 함수 매개변수
- 조건식에서 사용되는 값
- 반환 또는 속성·첨자 쓰기 후보
- 두 버전 사이에 추가·삭제된 연결

각 연결에는 파일, 줄, 심볼, Python 표현식과 적용된 해석 규칙이 붙습니다. 이 단계에는 LLM이나 RAG가 사용되지 않습니다.

## 입력별 지원 범위

| 비교 입력 | 현재 결과 |
|---|---|
| Python 원본 ↔ Python 원본 | AST 변경, 호출·참조 관계, 값 흐름, 기능·TC 후보 |
| Git Python ↔ 로컬 Python | 동일한 Python 코드 영향 분석 |
| 같은 선택 언어의 원본 ↔ 원본 | Tree-sitter AST 지문, 심볼·import·호출 영향 후보 |
| 일반 프로젝트 ↔ 일반 프로젝트 | 상대 경로·크기·SHA-256·텍스트 차이 |
| APK ↔ APK | 패키지 내부 파일 구성 차이 |
| IPA ↔ IPA | 패키지 구성 차이와 각 입력의 `Info.plist` 선언 메타데이터 |
| APK/IPA ↔ Git 원본 | 직접 비교하지 않음. 같은 빌드 조건의 양쪽 패키지 또는 양쪽 원본 필요 |
| APK ↔ IPA | 직접 비교하지 않음 |

APK·IPA 분석은 설치·실행 검증이나 원본 코드 복원을 의미하지 않습니다. 현재 패키지 단계에서는 파일 구성과 제한된 선언 메타데이터를 비교합니다.

## 구성

```text
QA_train/
├─ IMPACT_ANALYSIS_PLAN.md # 사용자 영향도 분석 구현 체크리스트
├─ AST/                    # 분석·변환·비교·값 흐름 엔진과 CLI
│  ├─ qa_ast/
│  │  ├─ common/           # 언어 중립 노드·연결·근거·어댑터 계약
│  │  └─ languages/
│  │     ├─ tree_sitter/   # 다중 언어 카탈로그와 공통 Tree-sitter 어댑터
│  │     └─ python/        # Python 파서·스냅샷·관계·비교·값 흐름
│  ├─ ast_analyzer.py      # 기존 CLI 호환 진입점
│  ├─ artifact_conversion.py # Git·ZIP·로컬·엔진·APK·IPA 공통 입력
│  ├─ code_*.py            # 기존 import 호환 진입점
│  ├─ ipa_support.py
│  ├─ ARCHITECTURE.md
│  ├─ tests/
│  └─ reports/
├─ streamlit/              # 웹 UI·세션 서비스·실행 설정
│  ├─ streamlit_app.py
│  ├─ qa_web_service.py
│  ├─ qa_ast_service.py    # 세션 스냅샷 하나의 AST 보고서 생성
│  ├─ ast_ui.py            # _AST 입력·결과·다운로드 화면
│  ├─ qa_flow_service.py
│  ├─ flow_ui.py
│  ├─ ast_runtime.py       # 형제 AST 프로젝트를 불러오는 경계
│  └─ tests/
├─ learn/                  # 공개 규칙 수집·검토·규칙 팩 생성
├─ local_runtime/          # 규칙 팩 설치·검증과 로컬 모델 다운로드·실행
└─ pj_request_learn/       # 로컬 프로젝트 프로필 예정, 코드 임베딩 제외
```

의존 방향은 `웹 UI/로컬 API 및 기존 streamlit → AST·local_runtime`입니다. AST 엔진은 특정 웹 프레임워크 없이 CLI나 로컬 API에서 독립 실행할 수 있습니다. `artifact_conversion.py`의 Git·ZIP·로컬·엔진·APK·IPA 입력은 그대로 유지됩니다.

```mermaid
flowchart LR
    A[Ver.A] --> S[입력 스냅샷]
    B[Ver.B] --> S
    S --> F[파일 비교]
    F --> L[선택한 언어 어댑터]
    L --> D[공통 그래프 변경]
    D --> R[호출·참조 영향]
    R --> V[값 흐름 해석]
    V --> M[기능·기존 TC 매핑]
    M --> O[Markdown / JSON 보고서]
    K[향후 Hybrid RAG] -. 문서 근거 .-> M
    L[향후 LLM] -. 사용자 설명 .-> O
```

## 실행 방법

Python 3.12와 [uv](https://docs.astral.sh/uv/)가 필요합니다.

### 로컬 규칙 팩 준비

Cloud 앱은 이 팩을 사용하지 않는다. 로컬 앱용 규칙 팩은 검토 상태와 임베딩 준비 상태를 manifest에 기록하고, SHA-256을 검증한 뒤 `%LOCALAPPDATA%\QA Train\rules\`에 설치한다.

```powershell
cd QA_train\learn

# 현재 pending 규칙의 구조 확인용 초안
.\run_learn.ps1 pack -PackVersion 0.1.0-draft -ReviewStatus pending

cd ..\local_runtime
uv run qa-rules install ..\learn\data\packs\base-rules-0.1.0-draft.zip
uv run qa-rules status
```

현재 초안은 733개 `pending` 규칙을 담은 `metadata_only` 팩이며 `release_eligible: false`, `semantic_ready: false`다. 검토 완료 규칙만 선별하고 기본 규칙 임베딩을 추가한 뒤 정식 배포 팩으로 승격한다.

### 로컬 모델 최초 준비

설치 앱은 이 과정을 자동으로 실행할 예정이다. 개발 환경에서는 상태를 먼저 확인하고, 모델이 없을 때만 다운로드한다.

```powershell
cd QA_train\local_runtime
uv sync --extra inference
.\run_model_setup.ps1 status
.\run_model_setup.ps1 download
```

모델 버전은 매니페스트의 커밋 SHA로 고정된다. 다운로드에 사용자 코드나 공통 그래프를 포함하지 않으며, 완료된 모델은 사용자 로컬 데이터 폴더에서 재사용한다.

### 기존 Streamlit 웹 앱

[Cloud 앱 열기](https://apptrain-akecrcbajuvarqhr2dgtcs.streamlit.app/). Cloud는 기존 비교·AST 기능을 빠르게 확인하는 환경으로 유지합니다. 파일 업로드와 공개 GitHub 입력을 사용하며 로컬 규칙 팩·로컬 모델 분석은 실행하지 않습니다. Cloud의 세션 파일은 영구 보관을 보장하지 않으므로 필요한 결과는 다운로드합니다.

```powershell
git clone https://github.com/rupria/QA_train.git
cd QA_train\streamlit
uv sync
.\run_qa_web.ps1
```

브라우저에서 <http://127.0.0.1:8501>을 엽니다. 다른 포트는 다음처럼 지정합니다.

```powershell
.\run_qa_web.ps1 -Port 8502
```

### AST CLI

```powershell
cd QA_train\AST
uv sync

# 구조 보고서
.\run_ast_analyzer.ps1 structure "C:\project\app.py"

# 원본 AST 트리
.\run_ast_analyzer_Tree.ps1 "C:\project\app.py"

# Git 변경 분석
.\run_ast_analyzer.ps1 diff "C:\project\repository" --base HEAD~1 --target HEAD

# 입력 스냅샷 생성
.\run_ast_analyzer.ps1 convert "C:\received\project" --output "C:\QA_inputs\project_snapshot"

# Ver.A / Ver.B 코드 비교
.\run_ast_analyzer.ps1 compare "C:\input\Ver.A" "C:\input\Ver.B"
```

자세한 사용법:

- [AST 분석 엔진](AST/README.md)
- [AST 기본 사용법](AST/USAGE_GUIDE.md)
- [입력 변환](AST/CONVERSION_GUIDE.md)
- [코드 비교와 QA 영향 후보](AST/COMPARISON_GUIDE.md)
- [Streamlit 웹 UI](streamlit/README.md)
- [웹 화면 사용 가이드](streamlit/WEB_GUIDE.md)

## 검증

두 프로젝트의 환경과 테스트는 분리되어 있습니다. 아래 전체 회귀 명령은 사용자 요청이 있을 때 실행합니다. 평소에는 변경 파일과 기능에 대응하는 개별 테스트 또는 테스트 모듈만 실행합니다.

```powershell
cd QA_train\AST
uv sync
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v

cd ..\streamlit
uv sync
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
```

테스트용 APK·IPA fixture는 설치 가능한 앱이 아닌 합성 ZIP입니다.

Git diff·AST 비교의 기본 확인에는 `Test/ast_compare_fixture.py`의 두 이력을 사용합니다. 이 파일은 재사용 자산이므로 작업 후 삭제하지 않습니다.

## 단계별 진행 기록

### 1. Python AST 분석기 시작 — 2026-09-16

단일 Python 파일과 Jupyter Notebook을 실행하지 않고 읽는 구조 분석기에서 시작했습니다.

- 함수·클래스·import·호출 관계 추출
- Markdown·JSON 출력
- 사람이 읽는 구조 보고서와 원본 AST 트리 보고서 분리
- 분석 대상 코드를 실행하거나 수정하지 않는 원칙 확립

관련 커밋:

- `6591f88` — AST 분석기 최초 구현
- `6d73e63` — 비교용 Notebook 추가
- `fd1c1ff` — 중복 보고서 정리
- `fe9ccaa` — 구조 보고서와 AST 트리 출력 분리

### 2. 파일 diff에서 QA 영향 분석으로 확장

최신 커밋 해시나 파일 변경 목록만으로는 어떤 기능을 다시 확인해야 하는지 알기 어려웠습니다. 비교 단위를 파일에서 코드 심볼과 관계로 확장했습니다.

- 함수·클래스·메서드의 추가·삭제·수정 분류
- 원본 diff와 AST 구조 차이 연결
- 변경 심볼을 사용하는 상위 호출·참조 후보 탐색
- 기능 진입점과 기존 TC를 매핑 파일로 연결
- 결과를 테스트 판정이 아닌 회귀 확인 후보로 정의

### 3. 여러 입력을 공통 스냅샷으로 변환

실제 QA 입력은 Git 코드, 로컬 프로젝트, 엔진 프로젝트, APK, IPA 등으로 올 수 있습니다. 비교 전에 각 입력을 안전한 스냅샷으로 바꾸는 변환 계층을 만들었습니다.

- 원본 출처와 선택한 Git SHA 기록
- 원본을 수정하지 않는 별도 스냅샷 생성
- 파일별 SHA-256과 manifest 저장
- 엔진 캐시·빌드 폴더 제외
- APK·IPA의 안전한 패키지 추출
- IPA `Info.plist` 선언 메타데이터 수집

패키지와 Git 원본을 직접 대응하거나 패키지에서 원래 소스를 완전히 복원하는 기능은 현재 범위에 포함되지 않습니다.

### 4. Streamlit 기반 Ver.A·Ver.B 통합 화면

`이전 버전`과 `최신 버전`이라는 고정 의미 대신 사용자가 고른 두 입력을 나타내는 `Ver.A`와 `Ver.B`로 이름을 정했습니다. 입력 준비와 비교를 별도 화면에서 반복하지 않고 같은 페이지에서 처리하도록 구성했습니다.

- Git ↔ Git
- Git ↔ 로컬 소스
- 로컬 ↔ 로컬
- APK ↔ APK
- IPA ↔ IPA
- 준비된 스냅샷 재사용

Git 입력은 최신 해시 하나만 보여주는 방식에서 브랜치와 커밋 기록을 차례로 선택하는 방식으로 바뀌었습니다. 같은 저장소의 직전 커밋과 최신 커밋을 바로 비교할 수 있고, Ver.A와 Ver.B에 서로 다른 저장소 주소도 지정할 수 있습니다.

### 5. 호출 관계에서 값 흐름 해석으로 확장

함수가 서로 연결됐다는 사실만으로는 변경된 값이 어디까지 가는지 설명하기 어렵습니다. LLM 없이 재현할 수 있는 정적 규칙으로 값 전달 근거를 먼저 만들었습니다.

- 반환값, 호출 결과, 변수, 인자, 매개변수 연결
- 재대입에 따른 이전 흐름 차단
- 조건 사용, 반환, 상태 쓰기 후보 표시
- Ver.A·Ver.B의 연결 차이 비교
- 파일·줄·심볼·표현식 근거 제공

동적 호출, 런타임 DI, 복잡한 별칭, 상속, 비동기·generator 흐름 등은 추적 경계로 남깁니다.

### 6. AST 엔진과 Streamlit UI 분리 — 2026-09-25

분석 기능과 웹 기능이 한 폴더에 섞이지 않도록 두 프로젝트를 다시 분리했습니다.

- `AST`: 정적 분석, 입력 변환, 비교, 값 흐름, CLI
- `streamlit`: 화면, 브라우저 세션, 업로드·Git 입력 처리, 결과 표시
- `streamlit/ast_runtime.py`: UI가 AST 엔진을 호출하는 명시적 경계

관련 커밋:

- `7a167dd` — 입력 변환, 비교, 값 흐름과 Streamlit 앱 추가
- `d409628` — AST 엔진과 Streamlit UI를 별도 프로젝트로 재분리

### 7. 단일 AST 화면과 Cloud 배포 — 2026-09-29

- 기존 Cloud 주소를 `streamlit/streamlit_app.py`의 새 배포에 연결
- Python 3.12와 `streamlit/uv.lock` 사용, `QA_WEB_ALLOW_LOCAL="0"` 설정
- `_AST` 탭에 단일 입력 분석과 트리형·정리형·ZIP 다운로드 추가
- 입력 변경 시 이전 결과와 다운로드를 숨기고, 두 버전 비교와 상태를 분리
- 다른 PC에서는 저장소 `main`을 받아 같은 기능을 로컬에서 실행 가능

### 8. Hybrid RAG와 LLM 역할 정의 — 다음 단계

확정한 순서는 **AST 근거 생성 → Hybrid RAG 검색 → LLM 해석 → QA 추천**입니다. LLM이 코드 관계를 추측하게 하기 전에 AST가 재현 가능한 파일·줄·심볼 근거를 만듭니다.

Hybrid RAG에서 함께 찾을 자료:

- 프로젝트 기능 명세와 화면·API 문서
- 기존 수동·자동화 TC
- 장애·버그 이력
- 코드의 심볼·파일·호출·값 흐름
- 언어별 명명 규칙과 코딩 스타일
- 공개 코드의 구조 패턴과 평가 예제

검색은 심볼·경로·키워드 기반 검색과 의미 기반 벡터 검색을 결합하는 방향입니다. 언어별 스타일 가이드는 이름과 역할을 해석하는 보조 근거로 사용하며 제품 동작의 정답으로 사용하지 않습니다.

LLM은 검색 결과와 AST 근거를 이용해 다음을 설명하는 계층으로 계획합니다.

- 변경이 연결되는 사용자 기능
- 가능한 영향 시나리오와 확인할 경계값
- 우선 실행할 기존 TC와 누락된 확인 항목
- 근거가 부족하거나 정적 분석이 멈춘 지점

운영 비용은 사용자가 입력한 API 키로 추론하는 BYOK 방식을 검토합니다. API 키를 저장소나 분석 보고서에 기록하지 않고 실행 세션에서만 사용하도록 설계해야 합니다.

## Hybrid RAG·다국어 계획

### 1. 공통 근거 스키마 확정

AST 결과, 값 흐름, 기능 매핑, TC, 문서 조각이 같은 ID 체계로 연결되도록 JSON 스키마를 확정합니다.

### 2. 검색 인덱스 분리

- 코드 인덱스: 파일, 심볼, import, 호출, 값 흐름
- 제품 인덱스: 기능 명세, 화면, API, 데이터 모델
- QA 인덱스: TC, 버그, 회귀 이력
- 규칙 인덱스: 언어·프레임워크별 명명 및 코딩 규칙

### 3. Hybrid 검색과 근거 평가

키워드·심볼 검색과 벡터 검색을 결합하고, 각 결과에 출처·버전·점수·연결 경로를 남깁니다. 공개 GitHub 코드는 모델을 바로 재학습하기보다 허용된 범위에서 검색 자료와 평가 데이터로 사용하는 방향을 우선 검토합니다.

### 4. 사용자 API 키 기반 LLM 해석

검색된 근거만 전달하고 구조화된 결과를 받습니다. 기능 영향, TC 추천, 불확실성을 함께 표시하고 근거가 없는 설명은 확정하지 않습니다.

### 5. 언어별 분석 어댑터

언어마다 파서와 프레임워크 규칙이 다르므로 `사용 언어` 하나만 받는 설정으로 끝내지 않습니다. 최소한 다음 환경 정보가 필요합니다.

- 언어와 버전
- 프레임워크·엔진과 버전
- 소스 루트·빌드 방식
- 패키지 관리자와 lock 파일
- 테스트 프레임워크
- 기능 명세·TC·API 문서 위치

분석 결과는 언어별 어댑터가 공통 스키마로 변환하도록 계획합니다.

## 다음 작업 우선순위

1. 733개 규칙 후보 검토와 `accepted` 상태 확정
2. 고정된 Qwen3 Embedding revision으로 기본 규칙을 한 번 임베딩
3. `semantic_ready` 규칙 팩과 SHA-256 생성
4. GitHub Releases에 정식 규칙 팩 업로드
5. 로컬 앱의 규칙 팩 버전 확인·다운로드 진행 상태 연결
6. AST 결과와 기본 규칙 검색 결과를 결합하는 로컬 분석 입력 확정
7. 코드 분석용 로컬 LLM 후보 선정과 하드웨어 등급별 실행 정책
8. 공통 영향 결과 JSON과 신뢰도 계산
9. JavaScript/TypeScript, Java/Kotlin, C# 분석 어댑터
10. 브라우저 UI와 설치 파일 구성

## 현재 한계

- 의미 단위 코드 분석은 현재 Python 중심입니다.
- 정적 분석만으로 실제 실행 순서, 외부 API 응답, DB 저장 결과를 확정할 수 없습니다.
- 동적 import·reflection·callback·DI·복잡한 별칭과 상속은 일부 누락될 수 있습니다.
- 실제 제품 기능명과 TC는 사용자가 제공한 매핑이나 문서가 필요합니다.
- APK·IPA에서 원본 코드를 완전히 복원하지 않습니다.
- APK·IPA의 설치, 서명, 실행, 기기 호환성은 검증하지 않습니다.
- Cloud 배포는 공개 앱이며 서버 로컬 경로 입력을 차단합니다. 인증, 작업 시간 제한과 데이터 보관 정책은 추가 운영 과제입니다.
- 현재 규칙 팩은 733개 후보가 모두 `pending`인 구조 확인용 초안이며 임베딩과 정식 배포는 완료되지 않았습니다.
- 코드 분석용 로컬 LLM은 아직 선정·연결하지 않았습니다. 외부 LLM API와 사용자 API 토큰은 사용하지 않는 방향입니다.

## 참고할 RAG 자료 후보

- [Google Style Guides](https://google.github.io/styleguide/)
- [Kakao REST API Reference](https://developers.kakao.com/docs/ko/rest-api/reference)
- [Microsoft C# 식별자 명명 규칙](https://learn.microsoft.com/ko-kr/dotnet/csharp/fundamentals/coding-style/identifier-names)
- [PEP 8](https://peps.python.org/pep-0008/)
- [W3C Standards](https://www.w3.org/)
- [NAVER Cloud Platform Guide](https://guide.ncloud-docs.com/docs/home)
- [Frontend Fundamentals Code Quality](https://frontend-fundamentals.com/code-quality/code/)

이 문서들은 언어와 플랫폼의 용어·명명·구조를 해석하는 참고 자료입니다. 프로젝트의 실제 요구사항과 기능 명세는 별도로 연결해야 합니다.
