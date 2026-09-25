# AST 분석 엔진

Python AST 구조 분석, Git 변경 영향 분석, 입력 변환, Ver.A·Ver.B 비교와 값 흐름 해석을 담당하는 코어 프로젝트다. Streamlit 화면과 웹 세션 처리는 형제 폴더인 `../streamlit`에 분리되어 있다.

## 환경 준비

```powershell
cd C:\codes\QA_train\AST
uv sync
```

## 실행

```powershell
.\run_ast_analyzer.ps1 structure "C:\project\app.py"
.\run_ast_analyzer_Tree.ps1 "C:\project\app.py"
.\run_ast_analyzer.ps1 diff "C:\project\repository" --base HEAD~1 --target HEAD
.\run_ast_analyzer.ps1 convert "C:\received\project" --output "C:\QA_inputs\project_snapshot"
.\run_ast_analyzer.ps1 compare "C:\input\Ver.A" "C:\input\Ver.B"
```

- 기본 AST 사용법: [`USAGE_GUIDE.md`](USAGE_GUIDE.md)
- 입력 변환: [`CONVERSION_GUIDE.md`](CONVERSION_GUIDE.md)
- 코드 비교와 QA 영향 후보: [`COMPARISON_GUIDE.md`](COMPARISON_GUIDE.md)
- 웹 화면 사용법: [`../streamlit/WEB_GUIDE.md`](../streamlit/WEB_GUIDE.md)

분석 대상 코드는 import하거나 실행하지 않는다. 정적 연결과 영향 후보를 제공하며 제품 동작의 정상 여부나 테스트 통과를 확정하지 않는다.
