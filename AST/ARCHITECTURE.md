# AST 엔진 구조

분석 엔진은 **공통 계약**과 **언어별 구현**으로 나뉜다. 각 언어 파서는 고유한 AST/CST 객체를 내부에서만 사용하고, 나머지 비교·영향 분석 단계에는 동일한 `ProjectGraph`를 제공한다.

```text
AST/
├─ qa_ast/
│  ├─ common/
│  │  ├─ models.py          # 노드·엣지·근거·변경·영향 결과
│  │  ├─ capabilities.py    # 언어별 지원 기능 표시
│  │  ├─ adapter.py         # LanguageAdapter 계약
│  │  └─ registry.py        # 사용자가 선택한 어댑터 조회
│  ├─ languages/
│  │  └─ python/
│  │     ├─ analyzer.py     # Python 구조·Git diff CLI 구현
│  │     ├─ snapshot.py     # Python 심볼 스냅샷
│  │     ├─ relations.py    # 호출·참조 관계
│  │     ├─ comparison.py   # Ver.A·Ver.B 비교
│  │     ├─ flow.py         # Python 값 흐름
│  │     └─ adapter.py      # Python 결과 → 공통 그래프
│  └─ registry.py           # 현재 제공하는 언어 어댑터 목록
├─ artifact_conversion.py   # 언어 분석 전 공통 입력 스냅샷
├─ ipa_support.py           # 패키지 입력 보조
└─ ast_analyzer.py 등       # 기존 CLI/import 호환 진입점
```

## 의존 방향

```text
공통 모델·계약
      ↑
언어별 어댑터와 분석기
      ↑
CLI·웹 API·웹 프런트엔드
```

`common`은 Python `ast`, Tree-sitter, Roslyn 같은 파서 구현을 import하지 않는다. 언어별 디렉터리는 공통 계약을 사용해 노드, 연결, 근거와 분석 한계를 출력한다. 웹 API는 레지스트리에서 사용자가 선택한 어댑터만 실행하고, 브라우저 UI는 이 API의 JSON 계약만 사용한다. 현재 `streamlit/`은 새 웹 앱으로 교체하는 동안 유지하는 호환 UI다.

## 공통 그래프

- 노드: 프로젝트, 파일, 모듈, 클래스, 함수, UI, API, DB, 기능 등
- 연결: 포함, 선언, 호출, 참조, 읽기, 쓰기, 요청, 화면 전환, 영향 등
- 근거: 파일, 줄, 표현식, 파서와 적용 규칙
- 해석 상태: `exact`, `static`, `inferred`, `unresolved`
- 분석 한계: 파싱 오류, 동적 호출, 외부 의존성, 미지원 문법 등

공통 그래프에는 원본 파서 객체를 넣지 않는다. 언어 고유 정보가 필요하면 JSON으로 직렬화할 수 있는 값만 `language_data`에 넣는다.

## 새 언어 추가 순서

1. `qa_ast/languages/<language>/`에 `LanguageAdapter` 구현을 만든다.
2. 대상 파서로 심볼과 관계를 추출한다.
3. 결과를 `CommonNode`, `CommonEdge`, `Evidence`, `AnalysisBoundary`로 변환한다.
4. 실제 지원 수준을 `AnalysisCapabilities`에 표시한다.
5. `qa_ast/registry.py`에 어댑터를 등록한다.
6. 기존 언어와 섞인 프로젝트의 공통 그래프 연결 테스트를 추가한다.

자동 언어 감지는 웹 UI의 추천값으로만 사용한다. 최종 분석 언어는 사용자가 복수 선택하며, 선택하지 않았거나 지원하지 않는 파일은 분석 경계로 보고한다.

## 로컬 모델과 웹 앱 경계

웹 앱으로 전환할 때도 분석 엔진은 브라우저 서버에 사용자 코드를 보내지 않는다.

```text
learn/ 기본 규칙 데이터 ─────┐
                             ↓
사용자 코드 → 언어 어댑터 → 공통 그래프 → 로컬 모델 → 영향 설명
                 ↑                           ↓
                 └──── 로컬 API ← 웹 UI ────┘
```

- `learn/`: 공개 스타일 가이드로 만든 배포 가능한 기본 규칙 데이터와 버전 정보
- `AST/qa_ast/`: 코드를 실행하지 않고 공통 그래프로 변환하는 정적 분석 엔진
- `local_runtime/`: 고정된 모델 버전의 최초 다운로드·완료 검증·로컬 임베딩 실행
- 로컬 API: 분석 작업, 진행 상태와 결과를 웹 UI에 JSON으로 제공
- 웹 UI: 사용 언어 선택, Ver.A·Ver.B 입력, 결과 탐색과 다운로드

사용자의 원본 코드, 프로젝트별 임베딩, 벡터 인덱스와 분석 결과는 로컬 데이터 디렉터리에만 둔다. Git 저장소에는 기본 규칙 데이터와 모델 매니페스트만 포함한다. 모델 가중치는 최초 실행 시 내려받아 재사용하며, 프로젝트 데이터는 기본적으로 분석 세션 종료 시 삭제할 수 있게 한다.
