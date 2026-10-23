# 학습 모델과 적용 규칙

## 선택 모델

현재 단계의 기본 모델은 **`Qwen/Qwen3-Embedding-0.6B`**입니다.

- 로컬에서 실행할 수 있는 공개 가중치 모델
- Apache 2.0 라이선스
- 한국어·영어·프로그래밍 언어를 포함한 100개 이상 언어 지원
- 최대 32K 입력과 1024차원 embedding
- 검색 작업에 맞춘 사용자 지시문 지원

**`Qwen/Qwen3-Embedding-4B`**는 선택적 교사 모델입니다. 데이터 생성에 반드시 필요하지 않으며, GPU 환경이 준비됐을 때 0.6B 결과와 비교하거나 어려운 positive·negative 후보를 채점하는 데만 사용합니다.

`Qwen/Qwen3-Reranker-0.6B`는 현재 비활성화합니다. 검토된 hard negative와 검색 평가셋이 생긴 뒤에만 연결합니다. 현재 자료만으로 reranker까지 학습하면 문서 표현을 암기하고 실제 AST 검색을 개선하지 못할 가능성이 높습니다.

기계가 읽는 동일 설정은 [`model_policy.json`](model_policy.json)에 있습니다.

## 모델 입력 규칙

Qwen3 Embedding 공식 사용법에 따라 질의에만 영어 지시문을 붙이고 근거 문서에는 붙이지 않습니다.

```text
Instruct: Given a software convention query in Korean or English, retrieve direct evidence about identifiers, naming, declarations, code quality, API contracts, and web standards.
Query: Python 함수 이름 규칙
```

문서 입력:

```text
Function names should be lowercase, with words separated by underscores as necessary to improve readability.
```

고정 처리 규칙:

1. tokenizer는 left padding을 사용합니다.
2. 마지막 토큰의 hidden state를 embedding으로 사용합니다.
3. embedding은 L2 정규화합니다.
4. 유사도는 cosine을 사용합니다.
5. 모델은 32K까지 지원하지만 현재 규칙 청크는 8K 이하로 제한합니다.
6. 기본 출력은 1024차원입니다.

공식 모델 카드는 지시문을 사용하면 대부분의 검색 작업에서 1~5% 향상될 수 있고, 다국어 환경에서도 지시문은 영어로 작성할 것을 권장합니다.

## 학습 규칙

초기 학습은 ModelScope SWIFT의 embedding task와 LoRA를 사용합니다. 손실 함수는 Qwen 공식 학습 문서가 권장하는 InfoNCE입니다.

```text
anchor   = 규칙을 찾는 한국어 또는 영어 질의
positive = 해당 규칙의 직접 근거
negative = 단어는 비슷하지만 해당 심볼에 적용되지 않는 규칙
```

고정 정책:

- InfoNCE temperature: `0.01`
- batch의 다른 positive를 negative 후보로 사용하는 in-batch negative 활성화
- positive보다 더 유사한 negative는 false negative일 가능성이 있으므로 마스킹
- 같은 심볼에 동시에 적용 가능한 규칙은 negative로 사용하지 않음
- 문서 인접 청크를 train과 evaluation에 무작위로 나누지 않음
- 규칙 원문 버전과 공개 코드 저장소·커밋 단위로 분리

SWIFT 호환 후보 데이터는 다음 형태로 생성합니다. 모든 자동 추출 후보는 `review_status: pending`, `training_eligible: false`로 시작합니다.

```json
{
  "messages": [{"role": "user", "content": "Instruct: ...\nQuery: Python 함수 이름 규칙"}],
  "positive_messages": [[{"role": "user", "content": "Naming conventions\nFunction names should ..."}]]
}
```

공개 코드 AST 단계에서는 검증된 오답 후보를 `negative_messages`에 추가합니다. 현재 규칙 문서만으로는 실제 코드 기준의 negative가 없으므로 자동으로 가짜 negative를 만들지 않습니다.

## 판정 경계

| 판정 | 담당 |
|---|---|
| 변수·함수·클래스 종류 | AST parser |
| 선언·호출·반환·값 쓰기 관계 | AST parser |
| 식별자 토큰과 자연어 의미 연결 | Embedding 모델 |
| 심볼에 적용할 컨벤션 근거 검색 | Embedding 모델 |
| 규칙 준수·위반 최종 확정 | 규칙 검사기와 검토 상태 |
| 개인 프로젝트 고유 용어 | 프로젝트별 인덱스 |

모델 검색 결과가 AST 사실을 덮어쓸 수 없습니다. 모델이 찾은 규칙에는 항상 `rule_id`, 출처 URL, 원문 SHA-256이 붙어야 합니다.

## 학습 시작 조건

문서를 내려받았다는 이유만으로 모델을 즉시 미세조정하지 않습니다. 다음 조건이 갖춰진 뒤 시작합니다.

1. 자동 추출 규칙에 검토 상태가 추가됨
2. 공개 코드 AST 심볼과 적용 가능한 `rule_id`가 연결됨
3. 같은 이름이지만 적용되지 않는 hard negative가 준비됨
4. 공개 저장소·버전이 겹치지 않는 평가셋이 준비됨

조건을 충족하기 전에는 0.6B 기본 모델을 그대로 사용해 기준 성능을 측정합니다.

## 제외 범위

이 단계에서 다음 정보는 모델 입력과 출력에 넣지 않습니다.

- TC ID와 TC 추천
- 테스트 우선순위
- 결함 가능성 점수
- 테스트 시나리오 생성
- 개인 프로젝트 내용을 공통 모델 가중치에 저장하는 작업

## 공식 자료

- [Qwen3-Embedding-0.6B 모델 카드](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [Qwen3 Embedding SWIFT 학습 문서](https://github.com/QwenLM/Qwen3-Embedding/blob/main/docs/training/SWIFT.md)
