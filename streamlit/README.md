# QA Compare Streamlit UI

`비교`, `_AST`, `AST 연결·해석`, `스냅샷`을 제공하는 웹 프로젝트다. `_AST`는 입력 하나의 트리형·정리형 생성이며, 나머지 비교·흐름 해석과 입력 및 결과 상태를 분리한다. 분석·변환·비교 엔진은 형제 폴더인 `../AST`에 있고 이 폴더에는 UI, 웹 세션 서비스와 실행 설정을 둔다.

[Streamlit Cloud 접속](https://apptrain-akecrcbajuvarqhr2dgtcs.streamlit.app/). 실행 파일은 `streamlit/streamlit_app.py`, 브랜치는 `main`, Python 버전은 3.12다. Cloud에서는 `QA_WEB_ALLOW_LOCAL="0"`으로 파일 업로드·공개 GitHub 입력을 사용한다.

## 환경 준비와 실행

```powershell
cd C:\codes\QA_train\streamlit
uv sync
.\run_qa_web.ps1
```

브라우저에서 `http://127.0.0.1:8501`을 연다. 포트는 `.\run_qa_web.ps1 -Port 8502`처럼 바꿀 수 있다.

- 상세 웹 사용법: [`WEB_GUIDE.md`](WEB_GUIDE.md)
- AST 엔진 사용법: [`../AST/README.md`](../AST/README.md)

실행 중 업로드와 세션 스냅샷은 `streamlit/.web_runs/`에 저장되며 Git에 포함되지 않는다.

`_AST` 보고서는 `.web_runs/session-<ID>/ast_reports/<run-ID>/`에 `ast_tree.md`, `ast_structure.md`, `ast_structure.json`으로 자동 저장한다. 개별 파일과 ZIP을 내려받을 수 있다. Cloud의 세션 파일은 영구 저장을 보장하지 않는다.
