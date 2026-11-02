# QA Train 업데이트 내역

[README로 돌아가기](README.md)

제품과 문서의 주요 변경을 최신순으로 기록합니다. 앱의 현재 버전은 루트 [`app_manifest.json`](app_manifest.json)을 기준으로 하며, 세부 코드 변경은 각 커밋에서 확인할 수 있습니다.

## 2026-11-02 · v0.1.0

기준 커밋: [`511bd6d`](https://github.com/rupria/QA_train/commit/511bd6d)

- Streamlit Cloud와 다운로드형 로컬 앱이 동일한 `streamlit/streamlit_app.py`와 `.streamlit/config.toml`을 사용하도록 통합했습니다.
- 루트 `app_manifest.json`을 제품 버전의 단일 기준으로 추가하고, `streamlit`, `local_runtime`, `learn`의 패키지 버전을 v0.1.0으로 맞췄습니다.
- 사이드바에서 `v0.1.0 · Streamlit Cloud` 또는 `v0.1.0 · 로컬 앱`으로 실행 형태를 확인할 수 있습니다.
- 로컬 실행기 `streamlit/run_qa_local.ps1`을 추가했습니다. 현재는 공통 Streamlit UI를 실행하는 단계이며 독립 설치 파일과 자동 업데이트는 이후 작업입니다.
- 원본 소스 비교를 `git diff --no-index` 기반으로 전환해 추가·삭제·수정·이름 변경과 실제 변경 줄을 표시합니다.
- 변경 파일을 선택하면 로컬에 포함한 Diff2Html로 GitHub 형태의 unified diff를 표시합니다. 사용자 코드를 외부 CDN으로 전송하지 않습니다.
- ZIP의 단일 최상위 래퍼 폴더를 자동 정규화하고 캐시·의존성·생성 폴더를 비교 전에 제외합니다.
- CRLF/LF 줄바꿈만 다른 파일은 코드 변경에서 제외합니다.
- 검증: 공통 버전 4개, Streamlit 89개, AST 80개 테스트 통과.

## 2026-10-27 · 분석기 경량화

기준 커밋: [`888148a`](https://github.com/rupria/QA_train/commit/888148a)

- `qa_ast` 지연 import, 파서 레지스트리 재사용, 확장자 인덱스 기반 언어 탐지를 적용했습니다.
- 로컬 1,000파일 벤치마크에서 언어 탐지 시간을 약 496ms에서 13ms로 줄였습니다.
- 기본 import peak 메모리를 약 4.4MB에서 2.45MB로 줄였습니다.

## 2026-10-25 · 다국어 분석 기반

기준 커밋: [`13a3617`](https://github.com/rupria/QA_train/commit/13a3617), [`f79db48`](https://github.com/rupria/QA_train/commit/f79db48), [`fded8e2`](https://github.com/rupria/QA_train/commit/fded8e2)

- 사용자가 사이드바에서 사용 언어를 직접 선택하도록 변경했습니다.
- Python 정밀 분석과 Tree-sitter 공통 어댑터를 언어 중립 그래프 구조로 연결했습니다.
- 등록 언어 56개 각각에 Ver.A·Ver.B 독립 fixture와 파서 검증을 추가했습니다.
- Python 이외 언어는 구문·심볼·import·호출 후보를 제공하며, 참조·값 흐름 정밀 분석은 Python에 우선 적용됩니다.

## 2026-10-23 · 영향 분석 및 규칙 학습 구조

기준 커밋: [`9477725`](https://github.com/rupria/QA_train/commit/9477725), [`7c59c52`](https://github.com/rupria/QA_train/commit/7c59c52)

- 공개 스타일 가이드를 수집·정규화해 식별자·컨벤션 규칙 데이터셋을 만드는 `learn` 파이프라인을 추가했습니다.
- 사용자 프로젝트 코드를 공통 학습 데이터에 누적하지 않는 로컬 분석 경계를 정했습니다.
- UI·API·DB·코드·TC 연결과 영향도 계산을 위한 단계별 구현 계획을 문서화했습니다.

## 기록 원칙

- 기능·구조·배포 방식·분석 결과에 영향을 주는 변경만 기록합니다.
- 날짜는 커밋 날짜를 기준으로 하고 가장 최근 기록을 위에 둡니다.
- 테스트 수치는 해당 업데이트에서 실제 실행한 결과만 적습니다.
- 계획 상태는 완료로 표현하지 않고 `README.md`의 현재 진행도와 함께 갱신합니다.
