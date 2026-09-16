# AST 코드 분석 도구

`C:\sk-encoa\AST\.venv`의 분리된 Python 환경에서 실행한다. Python `.py` 파일과 Jupyter `.ipynb` 코드 셀을 지원하며 분석 대상 코드는 수정하지 않는다.

자세한 단일 파일 분석 방법은 [`USAGE_GUIDE.md`](USAGE_GUIDE.md)를 참고한다.

## 코드 구조 분석

```powershell
C:\sk-encoa\AST\run_ast_analyzer.ps1 structure C:\sk-encoa\gitproject\app.py
```

노트북 분석:

```powershell
C:\sk-encoa\AST\run_ast_analyzer.ps1 structure C:\sk-encoa\gitproject\py08-streamlit.ipynb
```

`--output`을 생략하면 `C:\sk-encoa\AST\reports\app_ast_structure.md`에 자동 저장한다. 같은 파일을 다시 분석하면 최신 결과로 갱신한다.

저장 위치를 직접 지정할 수도 있다.

```powershell
C:\sk-encoa\AST\run_ast_analyzer.ps1 structure C:\sk-encoa\gitproject\app.py --output C:\보고서\app.md
```

JSON이 필요하면 다음과 같이 실행한다.

```powershell
C:\sk-encoa\AST\run_ast_analyzer.ps1 structure C:\sk-encoa\gitproject\app.py --format json
```

JSON도 `C:\sk-encoa\AST\reports\app_ast_structure.json`에 자동 저장된다.

## 커밋되지 않은 Python 변경 분석

```powershell
C:\sk-encoa\AST\run_ast_analyzer.ps1 diff C:\sk-encoa\gitproject --base HEAD --output ast-diff-report.md
```

## 브랜치 또는 커밋 비교

```powershell
C:\sk-encoa\AST\run_ast_analyzer.ps1 diff C:\sk-encoa\gitproject --base origin/main --target HEAD --output ast-diff-report.md
```

보고서는 두 순서로 구성된다.

1. 변경 파일 → 변경 심볼 → 연관 모듈
2. 기능 그룹 → 모듈 → 이전 값과 변경 값

`기능 그룹`은 우선 파일 경로를 기준으로 자동 분류한다. 실제 사용자 기능명과 TC를 연결하려면 프로젝트의 기능 매핑 파일을 추가로 관리해야 한다.

## 지원 범위

- Python `.py` 파일
- Jupyter `.ipynb`의 Python 코드 셀
- 함수, 비동기 함수, 클래스, import, 함수 호출
- Git diff에 포함된 변경 전후 코드
- import 및 호출명 기반 연관 모듈 후보

동적 import, 문자열 기반 호출, 런타임 이벤트, DB 연결은 AST만으로 확정할 수 없으므로 별도 실행 추적이나 프로젝트 매핑이 필요하다.
