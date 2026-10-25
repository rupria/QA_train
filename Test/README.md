# 언어별 분석 테스트

이 폴더의 언어 샘플은 실행용 프로그램이 아니라 파서와 비교기를 검증하는 최소 소스입니다. QA Train은 샘플 코드를 실행하거나 import하지 않고 텍스트로만 읽습니다.

## 빠른 실행

저장소 루트에서 실행합니다.

```powershell
# 지원 언어와 계열 확인
.\Test\run_language_tests.ps1 -List

# 언어 하나: 파싱 + Ver.A/Ver.B 변경 비교
.\Test\run_language_tests.ps1 -Language typescript

# 여러 언어
.\Test\run_language_tests.ps1 -Language python,javascript,csharp

# 언어 계열
.\Test\run_language_tests.ps1 -Group web -Check parse

# 전체 지원 언어
.\Test\run_language_tests.ps1 -All -Check all

# 자동화에서 사용할 JSON 결과
.\Test\run_language_tests.ps1 -Language rust -Json
```

`-Check` 값은 `parse`, `compare`, `all` 중 하나입니다.

- `parse`: 선택한 어댑터가 파일을 인식하고 오류 없이 공통 그래프를 만드는지 확인
- `compare`: 숫자 리터럴만 다른 Ver.A와 Ver.B에서 변경을 찾는지 확인
- `all`: 두 검증 모두 실행

## 구성

- `language_cases.py`: 모든 등록 언어의 결정적 최소 샘플
- `run_language_parser_tests.py`: 언어·계열별 테스트 러너
- `run_language_tests.ps1`: Windows 실행 래퍼
- `test_language_case_catalog.py`: 등록 언어와 샘플 누락 방지 테스트
- `ast_compare_fixture.py`: 기존 Git 이력·Python AST 비교용 고정 fixture

언어를 새로 등록하면 `language_cases.py`에도 샘플을 추가해야 카탈로그 테스트가 통과합니다. 샘플은 외부 네트워크·파일·프로세스에 접근하지 않아야 하며 `__QA_VALUE__` 표시는 정확히 한 번 포함해야 합니다.
