# 두 코드 버전 비교와 QA 영향 후보

로컬·엔진·Git·APK·IPA를 먼저 보관된 스냅샷으로 준비하려면 [CONVERSION_GUIDE.md](CONVERSION_GUIDE.md)를 참고하세요. 현재 비교기는 Python 원본 스냅샷만 지원하며 패키지 추출물은 직접 AST 비교하지 않습니다.

기준·최신 Python 코드의 AST를 비교해 변경된 함수·클래스·모듈 실행 내용을 찾습니다. 변경 심볼을 사용하는 호출·참조 관계를 이전과 최신 코드에서 각각 역추적합니다. 기능 진입점과 TC ID를 지정하면 실제 연결 경로를 근거로 QA 확인 항목을 제시합니다.

분석 대상 코드를 실행하거나 import하지 않습니다. 코드 변경과 영향 후보를 만드는 도구이며 제품 사양의 올바름이나 실제 테스트 Pass를 판정하지 않습니다.

## 1. 예제 실행

PowerShell에서:

```powershell
cd C:\codes\QA_train\AST
.\run_ast_analyzer.ps1 compare `
  .\examples\code_compare\base `
  .\examples\code_compare\target `
  --features .\examples\code_compare\features.json
```

기본 출력은 실행마다 별도 폴더에 저장됩니다.

```text
reports\compare\[실행ID]\comparison.md
reports\compare\[실행ID]\comparison.json
```

이번 예제는 토큰 유효성 조건을 `age < MAX_TOKEN_AGE`에서 `age <= MAX_TOKEN_AGE`로 변경합니다. 예제 수치와 TC ID는 실제 제품 정책이 아닌 도구 검증용입니다.

예상 분석 결과:

- 변경: `services/auth.py::valid_token` 1건.
- 로그인 후보: `screens.py::login` → `services/auth.py::LoginPolicy.allowed` → `services/auth.py::valid_token`.
- 자동 로그인 후보: `screens.py::automatic_login` → `services/auth.py::valid_token`.
- 관련 TC: `LOGIN-001`, `LOGIN-BOUNDARY-001`, `AUTO-LOGIN-001`.
- `screens.py::open_inventory`의 주석·줄바꿈 변경은 AST 변경과 영향 기능에서 제외.
- 제품 테스트 결과: 미실행. 예를 들어 나이 29·30·31에서 기대 정책을 별도 명세로 확인해야 합니다.

## 2. 실제 파일 또는 폴더 비교

파일 두 개:

```powershell
.\run_ast_analyzer.ps1 compare "C:\input\before.py" "C:\input\after.py"
```

서로 다른 파일명도 같은 논리 파일로 비교합니다. 보고서와 기능 매핑의 `file`은 최신 파일명인 `after.py`를 사용합니다. 두 파일의 실제 절대 경로는 보고서 상단에 각각 보존합니다.

프로젝트 폴더 두 개:

```powershell
.\run_ast_analyzer.ps1 compare "C:\input\base" "C:\input\target" `
  --features "C:\input\features.json" `
  --output "C:\output\comparison.md"
```

폴더 비교는 동일 상대 경로의 파일과 동일 qualified name의 심볼을 연결합니다. Git 저장소나 커밋 해시가 없어도 가능합니다. 임의의 대상 프로젝트를 자동 선택하지 않습니다.

`--format markdown`, `--format json` 또는 기본 `--format both`를 사용합니다. `both`에 `--output comparison.md`를 지정하면 `comparison.md`와 `comparison.json`을 함께 만듭니다. 출력 경로에 기존 보고서가 있으면 갱신하므로 보존하려면 다른 이름을 지정하세요. 원본 `.py`·`.ipynb` 및 기능 매핑을 출력 경로로 지정할 수 없습니다.

## 3. 변경 단위

- 함수·비동기 함수·클래스·메서드·중첩 함수와 `<module>` 실행 범위별로 비교합니다.
- AST 위치 속성은 비교에서 제외해 주석·공백·단순 줄 이동을 변경으로 잡지 않습니다.
- 중첩 정의는 부모의 본문 대신 이름·종류·정의 순서로 표현합니다. 메서드 본문 수정이 클래스와 모듈 변경으로 중복 표시되지 않습니다.
- 함수 이름, 인자, 기본값, 데코레이터, 조건식, 반환값 등 AST의 구조 변경은 표시합니다. docstring도 AST에 포함됩니다.
- 정의의 추가·삭제는 해당 심볼 변경과 부모의 이름 바인딩 변경을 함께 만들 수 있습니다.
- 모듈 상수·import·최상위 실행 내용은 `<module>`, 클래스 필드는 클래스 범위로 표시합니다.
- 이름 변경·파일 이동은 삭제와 추가로 표시합니다. 자동 rename 추정은 하지 않습니다.
- 원본 코드 diff와 AST diff, 이전·최신 줄 번호를 모두 보존합니다.

## 4. 호출·참조에서 기능과 TC 연결

자동으로 추적하는 근거:

- 같은 모듈 함수와 중첩 함수의 직접 호출.
- 명시적 import, 별칭 import, 상대 import 및 확인 가능한 패키지 재노출.
- 클래스 직접 호출, 확인 가능한 생성자 `__init__`, `Class.method`, 현재 클래스의 `self.method`·`cls.method`.
- 상수·클래스 필드 및 함수 객체에 대한 정적 참조.
- 변경된 심볼을 사용하는 상위 호출·참조 경로. 기본 깊이는 10이며 `--max-depth`로 조정합니다. 순환 관계는 방문 기록으로 종료하며 깊이 제한은 경고로 표시합니다.

모듈 이름은 비교 루트 기준 상대 경로에서 도출합니다. import 경로와 일치하도록 프로젝트 루트를 지정하세요. 외부 패키지는 실행하거나 분석 범위 밖에서 찾아오지 않습니다.

기능 매핑이 없어도 변경 심볼과 상위 호출·참조 후보를 볼 수 있습니다. 사용자에게 보이는 기능명과 기존 TC ID를 연결하려면 다음 JSON을 지정합니다.

```json
{
  "schema_version": 1,
  "features": [
    {
      "id": "LOGIN",
      "name": "로그인",
      "entry_points": [{"file": "screens.py", "symbol": "login"}],
      "tc_ids": ["LOGIN-001", "LOGIN-BOUNDARY-001"]
    }
  ]
}
```

`file`은 비교 루트 기준 상대 경로이며 `symbol`은 `LoginPolicy.allowed` 같은 qualified name입니다. 모듈 실행 전체를 진입점으로 지정할 때는 `<module>`을 사용합니다. 기존 또는 최신 코드에 진입점이 없으면 미확인 경고를 남깁니다. 삭제된 함수의 과거 영향도 이전 코드의 경로와 매핑으로 보존합니다.

현재 제품 기능명·TC ID는 매핑에 근거합니다. 함수 이름만 보고 제품 기능을 임의 확정하거나, TC를 새로 생성하지 않습니다. 보고서의 관련 TC는 회귀 실행 후보이며 결과는 미실행입니다.

## 5. 오류·미해결 관계·한계

- 코드 파싱·인코딩·파일 읽기 오류가 있으면 해당 파일 양쪽의 변경 판정을 건너뜁니다. 오류를 함수 삭제로 오인하지 않습니다.
- 중복 qualified name은 안전한 대응이 불가능해 해당 파일을 건너뜁니다. 조건부 재정의 및 property getter/setter처럼 같은 이름을 여러 번 선언하는 경우도 포함합니다.
- 보고서에 오류·건너뛴 파일·미해결 호출·외부 호출·깊이 제한을 기록합니다. 파싱 오류가 있으면 `status=incomplete`와 종료 코드 2를 반환합니다.
- 종료 코드 0은 파싱 완료이지 정확도 100%나 제품 테스트 Pass가 아닙니다. 잘못된 경로·인자·매핑·출력 오류는 종료 코드 1입니다.
- 인스턴스 변수, 대입한 함수 별칭, 매개변수 콜백, 상속, 동적 import/속성/리플렉션, star import 및 런타임 DI는 해석하지 않습니다. 조건부 바인딩·컴프리헨션·데코레이터의 영향은 일부 누락하거나 넓게 잡힐 수 있습니다.
- import 모듈 참조는 모듈 전체 의존 후보가 될 수 있습니다. 각 기능의 실제 영향은 실행과 명세로 확인합니다.
- `.ipynb`는 원본 코드 셀 번호 기준으로 비교합니다. 셀 삽입·재정렬은 추가·삭제로 보일 수 있고 셀 간 이름 해석은 지원하지 않습니다.
- 기존 노트북 전처리를 사용합니다. `%`, `!`, `%%` 명령에서 제외한 내용은 AST 비교 범위 밖이며 전처리 사실을 기록합니다. `%%writefile`은 지시문을 제외한 Python 본문만 분석합니다.
- Python 전용입니다. APK·IPA, Java·Kotlin·C#·네이티브 코드는 이 기능의 입력이 아닙니다.

## 웹에서 값 전달 해석

Streamlit의 **비교** 탭에서 Ver.A·Ver.B의 코드 영향 비교를 마친 뒤 **AST 연결·해석** 탭을 사용합니다. 변경 심볼을 선택하고 **흐름 해석**을 누르면 두 버전의 명시 반환값 → 호출 결과 → 변수 → 인자 → 매개변수 → 반환 또는 상태 쓰기 후보를 분석합니다. 기존 호출·참조 관계는 값 전달과 구분하며 토글로 함께 표시할 수 있습니다.

연결마다 파일·줄·심볼과 Python 표현식, 규칙에 따른 해석이 있습니다. 기능 매핑의 진입점까지 값 의존 근거가 있는지도 구분합니다. 기능명은 기존 매핑으로만 연결하며, 코드 범위에 도달했다는 사실이 실제 기능의 실행·정상 동작을 뜻하지 않습니다. Ver.A·Ver.B별 그래프, 연결 차이, 미해결 경계와 JSON·Markdown 다운로드를 제공합니다.

직선 문장, 재대입에 따른 흐름 차단, 명시 인자 바인딩을 우선 지원합니다. 분기·루프·예외·context 본문, 동적 호출·heap 별칭·읽기·전역/nonlocal, 상속·decorator·async/generator와 확장·가변 인자는 추적 경계로 남깁니다. 단순 지역 생성자·메서드 연결은 제한된 후보로 처리합니다. 웹 추적 깊이는 1~30, 노드는 버전별 최대 160개이며 순환·깊이/노드 제한을 표시합니다. 연결 ID는 문장 순서에도 의존하므로 줄 삽입·삭제 후의 연결 차이가 실제 연결 변경과 일대일로 대응하지 않을 수 있습니다. 현재 CLI `compare` 출력은 그대로이며 흐름 해석은 웹의 별도 동작입니다. LLM·RAG는 사용하지 않습니다.

상위 호출자의 발견은 기존 호출그래프가 확인한 범위에 한정됩니다. 단순 지역 생성자 추정은 이미 도달한 scope 안의 후속 전달에서만 사용하며 receiver 별칭·인자 전달 이후의 메서드 추적은 중단합니다. 미표시 연결은 실제 연결이 없다는 증거가 아닙니다.

자세한 조작 방법은 [Streamlit 웹 가이드](../streamlit/WEB_GUIDE.md)를 참고하세요.

## 6. 도구 검증

AST 도구 폴더에서:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

회귀 테스트는 변경 탐지와 기능 연결뿐 아니라 주석·서식 제외, 삭제 전 경로, import 별칭·상대 import, 이름 가림·재정의·`global`·`del`, 메서드·생성자, 상수 의존, 순환·깊이 제한, 파싱 오류, 노트북 전처리, 원본 실행·덮어쓰기 방지 및 기존 tree/structure 명령을 확인합니다.
