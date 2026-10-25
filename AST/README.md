# AST 분석 엔진

언어 중립 공통 그래프와 언어별 어댑터를 제공하는 정적 분석 코어 프로젝트다. 현재 의미 분석 구현은 Python이며, Git 변경 영향 분석, 입력 변환, Ver.A·Ver.B 비교와 값 흐름 해석을 지원한다. UI나 웹 프레임워크에는 의존하지 않는다. 기존 Streamlit 화면은 형제 폴더인 `../streamlit`에 호환 UI로 유지한다.

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

- 공통·언어별 엔진 구조: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- 기본 AST 사용법: [`USAGE_GUIDE.md`](USAGE_GUIDE.md)
- 입력 변환: [`CONVERSION_GUIDE.md`](CONVERSION_GUIDE.md)
- 코드 비교와 QA 영향 후보: [`COMPARISON_GUIDE.md`](COMPARISON_GUIDE.md)
- 웹 화면 사용법: [`../streamlit/WEB_GUIDE.md`](../streamlit/WEB_GUIDE.md)

## 입력 경계

`artifact_conversion.py`는 로컬 파일·폴더, Git ref, ZIP, 엔진 프로젝트, APK와 IPA 입력을 검증된 스냅샷으로 준비한다. 이 입력 형식은 언어별 분석 구조와 분리되어 유지된다. 스냅샷을 만든 뒤 사용자가 선택한 언어 어댑터만 실행한다.

언어 식별은 확장자와 일부 대표 파일명(`Dockerfile`, `Makefile`, `CMakeLists.txt`, `Jenkinsfile`)을 사용하고, 확장자가 없는 스크립트는 shebang을 보조 근거로 사용한다. 웹·모바일·백엔드·시스템·데이터·인프라 언어를 식별해 스냅샷에 기록하지만, 현재 의미 분석 어댑터는 `.py`와 `.ipynb`용 Python 구현만 제공한다.

분석 대상 코드는 import하거나 실행하지 않는다. 정적 연결과 영향 후보를 제공하며 제품 동작의 정상 여부나 테스트 통과를 확정하지 않는다.
