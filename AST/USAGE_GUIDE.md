# AST 코드 분석기 사용 가이드

## 1. 도구 위치와 역할

AST 분석기는 분석 대상 프로젝트와 분리되어 있다.

```text
C:\codes\QA_train\AST
├─ .venv\                  AST 전용 Python 실행 환경
├─ ast_analyzer.py         분석기 본체
├─ run_ast_analyzer.ps1    가공형/ diff PowerShell 실행 파일
├─ run_ast_analyzer_Tree.ps1  트리형 PowerShell 실행 파일
├─ reports\structure\      가공형 보고서
├─ reports\tree\           트리형 보고서
├─ README.md               도구 개요
└─ USAGE_GUIDE.md          이 사용 가이드
```

분석기는 지정한 Python 소스 코드를 실행하지 않고 `ast.parse()`로 문법 구조만 읽는다. 분석 대상 파일을 수정하지 않는다.

## 2. 현재 기본 운영 방식

1. 사용자가 분석할 Python `.py` 또는 Jupyter `.ipynb` 파일을 지정한다.
2. 분석기는 `.py` 파일 또는 노트북의 Python 코드 셀을 AST로 읽는다.
3. 함수·클래스·import·호출 관계를 추출한다.
4. 결과를 Markdown으로 자동 저장한다.
5. 같은 파일을 다시 분석하면 같은 보고서가 최신 결과로 갱신된다.

GitHub 연결, 브랜치, 커밋 해시는 단일 파일 AST 분석에 사용하지 않는다.

## 3. 가장 간단한 실행 방법

PowerShell에서 다음 명령을 실행한다.

```powershell
C:\codes\QA_train\AST\run_ast_analyzer.ps1 structure "분석할 .py 또는 .ipynb 파일의 전체 경로"
```

예시:

```powershell
C:\codes\QA_train\AST\run_ast_analyzer.ps1 structure "C:\sk-encoa\gitproject\app.py"
```

Jupyter Notebook 예시:

```powershell
C:\codes\QA_train\AST\run_ast_analyzer.ps1 structure "C:\sk-encoa\gitproject\py08-streamlit.ipynb"
```

실행 결과:

```text
작성 완료: C:\codes\QA_train\AST\reports\structure\app_ast_structure.md
```

## 4. 자동 저장 규칙

`--output`을 생략하면 다음 규칙으로 저장한다.

```text
C:\codes\QA_train\AST\reports\structure\[원본 파일명]_ast_structure.md
```

예시:

| 분석 파일 | 자동 저장 파일 |
|---|---|
| `app.py` | `reports\structure\app_ast_structure.md` |
| `payment_service.py` | `reports\structure\payment_service_ast_structure.md` |
| `user.py` | `reports\structure\user_ast_structure.md` |
| `py08-streamlit.ipynb` | `reports\structure\py08-streamlit_ast_structure.md` |

서로 다른 폴더에 같은 파일명이 있으면 보고서명이 겹칠 수 있다. 이 경우 `--output`으로 저장 경로를 직접 지정한다.

```powershell
C:\codes\QA_train\AST\run_ast_analyzer.ps1 structure `
  "C:\project-a\service\user.py" `
  --output "C:\codes\QA_train\AST\reports\structure\project-a_user_ast.md"
```

## 5. 출력 형식 선택

### Markdown

기본 형식이다. 사람이 읽고 검토하거나 QA 문서에 연결하기 좋다.

```powershell
C:\codes\QA_train\AST\run_ast_analyzer.ps1 structure "C:\project\sample.py"
```

### JSON

자동화 프로그램에서 읽거나 기능·TC 매핑에 사용할 때 선택한다.

```powershell
C:\codes\QA_train\AST\run_ast_analyzer.ps1 structure `
  "C:\project\sample.py" `
  --format json
```

자동 저장 위치:

```text
C:\codes\QA_train\AST\reports\structure\sample_ast_structure.json
```

### AST 트리형

트리형은 전용 `_Tree` 실행 파일을 사용한다.

```powershell
C:\codes\QA_train\AST\run_ast_analyzer_Tree.ps1 `
  "C:\sk-encoa\gitproject\py08-streamlit.ipynb"
```

자동 저장 위치:

```text
C:\codes\QA_train\AST\reports\tree\py08-streamlit_ast_tree.md
```

가공형과 트리형은 각각 독립적으로 실행하며, 서로의 결과 파일을 덩어쓰지 않는다.

## 6. 분석 결과에서 확인할 수 있는 정보

| 항목 | 의미 |
|---|---|
| 분석 경로 | 입력한 Python 파일의 전체 경로 |
| 모듈 | 파일을 Python 모듈명으로 표현한 값 |
| imports | 코드가 불러오는 라이브러리와 모듈 |
| class | 선언된 클래스 |
| function | 선언된 함수 |
| async_function | 선언된 비동기 함수 |
| 줄 | 함수나 클래스의 시작·종료 줄 |
| 호출 대상 | 함수 또는 클래스 내부에서 호출하는 함수명 |
| 변수 대입 | 셀 또는 모듈 최상위에서 값을 저장하는 코드 |
| 호출 | `input`, `print`, `st.title`처럼 실행되는 호출문 |
| 제어 흐름 | `if`, `for`, `while`, `try` 등의 분기·반복 구조 |

`셀·모듈 실행 내용`은 원본 코드의 위에서 아래 순서를 유지한다. `원본 줄`은 `.py` 파일 또는 노트북 코드 셀 안의 줄 번호이며, `↳` 표시는 `with`, `if`, 반복문 등 내부 단계임을 뜻한다.
| 파싱 오류 | Python 문법 오류나 읽기 실패 내용 |

예시:

```text
| 종류 | 심볼 | 줄 | 호출 대상 |
| function | calculate_discount | 10-14 | round |
| function | approve_payment | 17-30 | calculate_discount, repository.save |
```

## 7. 결과 해석 방법

### 심볼

함수와 클래스처럼 코드에서 이름을 가진 구조다.

```python
def calculate_discount(price):
    return round(price * 0.9)
```

위 코드에서는 다음 정보가 나온다.

```text
심볼: calculate_discount
종류: function
호출 대상: round
```

### 호출 대상

함수 안에서 호출한 이름을 보여준다. 이름 기반 결과이므로 실제 실행 순서나 런타임 성공 여부까지 증명하지는 않는다.

### import

파일이 직접 불러오는 모듈을 보여준다. 동적 import나 문자열을 이용한 로딩은 나타나지 않을 수 있다.

## 8. 지원 범위

- Python `.py` 파일
- Jupyter `.ipynb`의 Python 코드 셀
- 함수와 비동기 함수
- 클래스
- 데코레이터
- import
- 함수 호출명
- 시작·종료 줄
- Python 문법 오류 표시
- Markdown 및 JSON 저장

## 9. 현재 범위에서 확인할 수 없는 것

- 코드가 실제 실행될 때의 호출 순서
- API 요청·응답 결과
- DB 쿼리와 저장 결과
- 이벤트 발행·구독의 실제 동작
- 문자열 기반 동적 호출
- 외부 서비스 연결 결과
- 노트북의 Markdown 셀과 Python 이외의 셀 매직 내용
- JavaScript, Java, C# 등 Python 이외의 언어
- 해당 코드가 정상 동작하는지에 대한 테스트 판정

AST 결과는 코드 구조 정보다. 기능 동작과 사이드 이펙트를 확정하려면 실행 테스트, 로그, API·DB 확인이 추가로 필요하다.

## 10. 오류 해결

### 파일을 찾을 수 없음

원본 코드가 실제로 있는 전체 경로와 `.py` 또는 `.ipynb` 확장자를 지정하고 큰따옴표로 감싼다. `C:\codes\QA_train\AST`는 분석 도구 위치이며, 원본 코드 위치가 아니다.

```powershell
C:\codes\QA_train\AST\run_ast_analyzer.ps1 structure "C:\경로에 공백\sample.py"
```

### `SyntaxError`가 표시됨

분석 파일의 Python 문법이 완성되지 않았거나 현재 Python 버전에서 해석할 수 없는 문법인지 확인한다.

### AST 환경을 찾을 수 없음

다음 명령으로 전용 환경을 복구한다.

```powershell
cd C:\codes\QA_train\AST
uv sync
```

### 보고서가 갱신되지 않음

명령에 입력한 파일과 보고서 파일명이 같은지 확인한다. `--output`을 사용했다면 지정한 경로를 확인한다.

## 11. 사용자 지정 원칙

- 분석할 코드 파일은 사용자가 지정한다.
- 분석기는 임의의 프로젝트나 파일을 선택하지 않는다.
- 단일 파일 AST 분석에서는 Git 해시를 요구하지 않는다.
- 다른 파일을 분석하려면 실행 명령의 파일 경로만 변경한다.
