# QA Train Learn

공개 기준 문서에서 변수·식별자 생성 규칙과 코드 컨벤션을 구조화해, 이후 공개 코드 AST 학습에 사용할 근거 데이터셋을 만듭니다. 외부 LLM API를 사용하지 않으며 TC 추천 데이터나 프롬프트를 포함하지 않습니다.

학습 모델과 입력·손실·판정 규칙은 [`MODEL_POLICY.md`](MODEL_POLICY.md)에서 사람이 읽을 수 있고, [`model_policy.json`](model_policy.json)에서 프로그램이 읽을 수 있습니다. 기본 모델은 `Qwen/Qwen3-Embedding-0.6B`, 선택적 교사 모델은 `Qwen/Qwen3-Embedding-4B`입니다.

## 현재 범위

```text
공식 문서 다운로드
→ HTML 블록 추출
→ 명명·선언·서식·코드 품질·API 규칙 후보 분류
→ 출처와 원문 해시를 보존한 rules.jsonl
→ 한국어·영어 rule-retrieval 학습 예제
```

AST 자체가 확정할 수 있는 변수·함수·클래스 종류는 이후 AST 데이터셋에서 정답으로 사용합니다. 이 프로젝트의 규칙 데이터는 AST 심볼의 이름, 선언 방식, 의미 역할을 해석할 때 연결할 근거입니다.

## 자료 구분

| 구분 | 자료 | 사용 목적 |
|---|---|---|
| 언어·명명 규칙 | Google Style Guides, Microsoft C# 식별자 규칙, PEP 8 | 변수·함수·클래스 이름, 선언, 서식 |
| 코드 품질 | Frontend Fundamentals | 가독성, 예측 가능성, 응집도, 결합도 |
| API 계약 | Kakao REST API, NAVER Cloud Guide | endpoint, method, 요청·응답, 오류 용어 |
| 웹 표준 | W3C | HTML·CSS·DOM·웹 API 표준 용어 |

검토 가능한 출처 목록은 [`sources.json`](sources.json)에 있습니다. 자동으로 링크를 따라 전체 사이트를 수집하지 않고, 목록에 명시된 HTTPS 주소만 내려받습니다.

## 실행

Python 3.12와 `uv`가 필요합니다.

```powershell
cd C:\codes\QA_train\learn

# 자료 목록 확인
.\run_learn.ps1 catalog

# 선택 모델과 적용 규칙 확인
.\run_learn.ps1 policy

# 원문 캐시 다운로드
.\run_learn.ps1 fetch

# 캐시에서 규칙과 학습 예제 생성
.\run_learn.ps1 build

# 다운로드와 생성을 한 번에 실행
.\run_learn.ps1 all
```

특정 자료만 처리할 수 있습니다.

```powershell
.\run_learn.ps1 fetch -Source pep8,microsoft-csharp-identifiers
.\run_learn.ps1 build
```

다운로드 후에는 외부 연결 없이 `build`를 반복 실행할 수 있습니다. 원문이 변경됐는지 다시 확인하려면 `-Force`를 지정합니다.

## 출력

생성물은 Git에 커밋하지 않습니다.

```text
data/
├─ raw/                 # 다운로드한 HTML과 URL·시각·SHA-256 메타데이터
└─ processed/
   ├─ rules.jsonl       # 구조화된 규칙 근거
   ├─ training_examples.jsonl
   ├─ swift_embedding_candidates.jsonl # 검토 전 SWIFT 호환 후보
   └─ manifest.json     # 자료별·분류별 건수
```

`rules.jsonl`의 핵심 필드는 다음과 같습니다.

- `rule_id`: 안정적인 규칙 식별자
- `source_url`, `source_content_sha256`: 출처와 버전 근거
- `languages`, `category`, `targets`: 적용 언어·분류·식별자 종류
- `heading_path`, `statement`, `examples`: 문맥과 근거
- `extraction_method`, `confidence`: 생성 방식과 자동 분류 신뢰도

자동 추출 결과는 확정 규칙이 아니라 검토 대상입니다. 이후 공개 코드 AST와 연결할 때 높은 신뢰도 규칙부터 사용하고, 애매한 후보는 승인 상태를 추가해 관리합니다.

`swift_embedding_candidates.jsonl`은 형식 호환성을 확인하기 위한 후보 파일이며 각 행은 `training_eligible: false`입니다. 규칙 검토와 공개 코드 AST 연결이 끝나기 전에는 미세조정 입력으로 사용하지 않습니다.

## 테스트

```powershell
uv sync
.\.venv\Scripts\python.exe -X utf8 -B -m unittest discover -s tests -v
```

## 다음 연결 지점

다음 단계에서는 별도 AST 데이터셋 생성기가 다음 사실을 만듭니다.

- 심볼 원문과 분해 토큰
- AST가 확정한 변수·함수·클래스 종류
- 선언·호출·반환·값 쓰기 관계
- 이 규칙 데이터의 `rule_id`와 연결된 준수·위반 후보

개인 프로젝트는 공통 모델 학습 데이터에 섞지 않고, 학습된 공통 규칙·식별자 모델을 적용하는 프로젝트별 인덱스로 관리합니다.
