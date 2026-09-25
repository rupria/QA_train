# QA Compare Streamlit UI

Ver.A와 Ver.B 입력, 비교 결과, AST 연결·해석을 한 화면에서 다루는 웹 프로젝트다. 분석·변환·비교 엔진은 형제 폴더인 `../AST`에 있으며 이 폴더에는 UI, 웹 세션 서비스와 실행 설정만 둔다.

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
