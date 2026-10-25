# 로컬 모델 런타임

QA Train 설치 파일에는 규칙 팩·모델을 검증하고 설치하는 코드와 [`model_manifest.json`](model_manifest.json)을 포함한다. 공개 규칙 팩과 모델 가중치는 사용자 PC로 내려받아 검증한 뒤 로컬에서 재사용한다.

기본 모델은 `Qwen/Qwen3-Embedding-0.6B`이며 매니페스트에 Hugging Face 커밋 SHA를 고정한다. 앱 업데이트가 새 SHA를 제공하기 전에는 임의로 최신 모델로 바꾸지 않는다.

## 데이터 위치

Windows 기본값:

```text
%LOCALAPPDATA%\QA Train\models\
%LOCALAPPDATA%\QA Train\rules\
```

`QA_TRAIN_DATA_DIR` 환경 변수 또는 CLI의 `--data-dir`로 다른 로컬 디스크를 지정할 수 있다. 모델 가중치, 사용자 프로젝트 임베딩과 분석 결과는 Git 저장소에 저장하지 않는다.

## 개발 환경

```powershell
cd C:\codes\QA_train\local_runtime
uv sync --extra inference
```

상태 확인:

```powershell
.\run_model_setup.ps1 status
```

최초 다운로드:

```powershell
.\run_model_setup.ps1 download
```

웹 API는 먼저 `ModelStore.status()`를 확인한다. 상태가 `missing`이면 다운로드 용량과 저장 위치를 보여준 뒤 `ModelStore.ensure()`를 백그라운드 작업으로 실행한다. 완료 마커와 필수 파일 검증이 끝난 모델만 `ready`가 된다.

## 상태

- `missing`: 아직 모델이 없음
- `downloading`: 다른 프로세스가 다운로드 중
- `ready`: 고정된 모델 버전을 로컬에서 사용할 수 있음
- `invalid`: 불완전하거나 매니페스트와 다른 모델 디렉터리

다운로드 실패 시 `.partial-*` 임시 폴더를 제거하고 완료 마커를 만들지 않는다. 사용자 코드와 공통 그래프는 다운로드 요청에 포함하지 않는다.
## 규칙 팩 설치 경계

현재 단계는 네트워크 자동 업데이트를 연결하지 않고, 버전 ZIP의 로컬 설치·검증까지만 제공한다.

```powershell
uv run qa-rules status
uv run qa-rules install C:\path\base-rules-1.0.0.zip
uv run qa-rules path
```

설치 과정은 다음을 보장한다.

- ZIP 경로 이탈과 중복 파일 차단
- manifest 파일 목록과 ZIP 내용 일치 확인
- 파일 크기와 SHA-256 검증
- 임시 폴더 설치 후 원자적 전환
- 현재 사용 중인 팩 버전을 `current.json`으로 기록

Cloud Streamlit 앱은 기존 비교·AST 기능 확인용으로 유지하며 이 로컬 규칙 팩을 사용하지 않는다.