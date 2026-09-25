# 입력 변환과 비교 준비

로컬 파일·엔진 프로젝트·Git 커밋·APK·IPA를 보존된 입력 스냅샷으로 준비합니다. 여기서 변환은 원본 복사 또는 패키지 추출과 출처·파일 해시·분석 가능 범위 기록입니다. 모든 입력을 Python으로 바꾸거나 APK/IPA에서 원래 소스를 완전히 되살리는 기능은 아닙니다.

## 실행 환경

Python 3.12 이상과 표준 라이브러리를 사용합니다. Git 입력에는 Git 실행 파일이 필요합니다. APK/IPA 추출은 Windows에서도 가능하며 Java·Xcode·macOS가 필요하지 않습니다. 선택적인 APK DEX 코드 복원은 별도로 설치한 JADX와 그 도구가 요구하는 Java 환경이 필요합니다. 분석 대상 프로젝트를 에디터에서 실행하거나 의존성을 설치하지 않습니다.

## 입력 종류별 사용

아래 입력 경로는 사용 예시입니다. `--output`은 **입력 밖의 새 폴더**로 지정하세요. 기존 결과를 덮어쓰지 않습니다.

로컬 프로젝트의 현재 파일을 보관:

```powershell
C:\codes\QA_train\streamlit\run_ast_analyzer.ps1 convert "C:\received\project" `
  --output "C:\QA_inputs\local_v2"
```

`auto`는 디렉터리의 현재 파일을 로컬 입력으로 읽습니다. Git 저장소여도 자동으로 HEAD를 선택하지 않습니다. 같은 저장소의 미커밋 파일과 커밋된 버전을 명확히 구분합니다.

로컬에 연결된 Git 저장소의 특정 버전:

```powershell
C:\codes\QA_train\streamlit\run_ast_analyzer.ps1 convert "C:\project_repo" `
  --kind git --ref "v1.0" --source-root "src" `
  --output "C:\QA_inputs\git_v1"
```

Git 입력은 지정 ref를 정확한 커밋 SHA로 고정하고 해당 트리의 파일을 추출합니다. 미커밋 변경과 untracked 파일은 포함하지 않습니다. checkout, pull, fetch 또는 원격 clone은 수행하지 않습니다. 원격 버전은 연결된 로컬 저장소에 먼저 확보해야 합니다. submodule·링크·제외 항목은 변환 기록을 확인하세요.

엔진 프로젝트:

```powershell
C:\codes\QA_train\streamlit\run_ast_analyzer.ps1 convert "C:\received\UnityProject" `
  --kind engine --output "C:\QA_inputs\engine_v2"
```

Unity·Unreal·Godot의 프로젝트 표식에서 엔진 종류를 식별합니다. 식별 가능한 버전 정보와 코드·에셋·설정을 보관하고 대표적인 엔진 캐시·빌드 폴더를 제외합니다. 에셋/씬을 추출했다고 컴포넌트 연결이나 기능 영향을 분석한 것은 아닙니다. APK 안의 엔진 흔적은 추정이며 원본 프로젝트 식별과 구분합니다.

APK:

```powershell
C:\codes\QA_train\streamlit\run_ast_analyzer.ps1 convert "C:\received\game.apk" `
  --output "C:\QA_inputs\apk_v2"
```

APK는 ZIP 구조를 검사해 파일을 추출하고 DEX·managed 코드·native 라이브러리·리소스 등의 구성을 기록합니다. APK 파일의 SHA256은 전달받은 파일의 식별자이며, 특정 Git 커밋에서 빌드됐다는 증거는 아닙니다. DEX 또는 native 흔적 확인은 코드 유효성·실행 가능성 검증이 아닙니다. binary AndroidManifest를 원본 XML로 자동 복원하는 기능은 포함하지 않습니다.

설치된 JADX로 DEX 복원 후보도 생성하려면:

```powershell
C:\codes\QA_train\streamlit\run_ast_analyzer.ps1 convert "C:\received\game.apk" `
  --jadx "C:\tools\jadx\lib\jadx-cli.jar" `
  --output "C:\QA_inputs\apk_v2_with_java"
```

위 jar 경로는 예시이며 실행 가능한 CLI JAR의 실제 위치를 지정합니다. Java는 PATH에 있어야 합니다. 배치 파일 `.bat`/`.cmd`는 지원하지 않습니다. 직접 실행 파일 또는 Java CLI JAR만 사용합니다. JADX 결과는 파생 코드 후보이며 원본 소스로 취급하지 않습니다. Native·Unity IL2CPP를 원래 C#으로 복원하는 기능은 없습니다. 복원 오류·미지원 범위를 기록하고 성공 여부는 capability와 경고에서 확인합니다. 매핑/심볼은 동일 빌드의 자료를 별도로 확보해야 합니다.

## IPA 입력

```powershell
C:\codes\QA_train\streamlit\run_ast_analyzer.ps1 convert "C:\received\game.ipa" `
  --output "C:\QA_inputs\ipa_v2"
```

확장자를 자동 감지하거나 `--kind ipa`를 지정합니다. 같은 ZIP 경로·충돌·링크·크기 검사를 거쳐 `Payload/<앱>.app/Info.plist`가 있는 패키지를 추출합니다. 모든 파일의 해시를 보관하고 top-level Payload 앱의 XML/binary plist에서 앱 ID, 표시 이름, 버전, 빌드 번호, 최소 OS 버전, 실행 파일 선언을 읽습니다. Info.plist는 1MiB까지 읽고 잘못된 메타데이터·누락된 실행 파일은 추출물을 유지하며 `partial`로 기록합니다.

실행 파일 이름은 번들 안의 파일명으로만 해석합니다. 실행 파일·프레임워크의 Mach-O/FAT magic은 바이너리 **후보** 표식이며 파일 유효성이나 복원 가능성을 증명하지 않습니다. 암호화·심볼 제거 상태는 `unknown`입니다. SwiftSupport·중첩 앱·앱 확장·프레임워크·리소스·서명/프로파일 파일은 전체 파일 목록에 보관하지만 메타데이터를 재귀적으로 해석하지 않습니다. 서명/프로파일 내용 검증, 앱 설치·실행, 복호화, Swift/Objective-C/네이티브 소스 복원은 지원하지 않습니다. JADX는 APK DEX 전용이며 IPA에서는 거부합니다.

IPA 역시 `package_payload`이고 `python_ast`, `original_source`, `restored_source`는 false입니다. Git 소스와 직접 AST 비교하는 대신 동일 빌드의 commit SHA·엔진/Xcode 설정·dSYM 같은 출처/심볼 자료를 함께 확보해 다음 분석 단계에서 사용해야 합니다. IPA 파일 해시와 plist 선언만으로 Git 커밋을 확정하지 않습니다.

관련 메타데이터와 번들 구조: [Apple Bundle Structures](https://developer.apple.com/library/archive/documentation/CoreFoundation/Conceptual/CFBundles/BundleTypes/BundleTypes.html), [CFBundleExecutable](https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundleexecutable).

## 공통 결과

```text
[스냅샷 폴더]/
  manifest.json       입력 출처·표현 종류·파일 목록·SHA256·capability·누락 범위
  conversion.md       사람이 검토할 변환 요약
  content/            복사한 원본 파일 또는 추출한 패키지 파일
  [복원 결과 폴더]/   선택적으로 실행한 JADX 결과
```

분석 가능 여부는 `manifest.json`의 `representation`과 `capabilities`로 판단합니다. `prepared`는 해당 변환 단계가 완료됐다는 뜻이며 제품 테스트 Pass나 APK/IPA와 Git 소스의 동일성을 의미하지 않습니다. `partial`이나 누락/경고가 있으면 범위를 먼저 확인하세요. APK/IPA는 추출이 성공해도 `package_payload`입니다.

입력 소스와 겹치는 출력, 기존 출력, 경로를 벗어나는 압축 항목, 파일 충돌과 설정 한도를 초과하는 압축은 거부합니다. 링크와 하위 저장소 등 제외 항목은 기록합니다. 결과는 수동 수정 없이 보관하세요. 비교할 때 content 파일 목록과 SHA256을 확인하며 변환 후 수정·추가·삭제된 스냅샷은 거부합니다. 이 검사는 파일 보존 확인이며 빌드 출처의 서명이나 신뢰 인증은 아닙니다.

## Python 비교기와 연결

Python 원본이 포함된 `prepared` 스냅샷 폴더 두 개를 현재 비교기에 바로 넣을 수 있습니다. 변환 manifest를 읽어 `content`를 분석하고 Git SHA 등 출처를 보고서에 남깁니다.

```powershell
C:\codes\QA_train\streamlit\run_ast_analyzer.ps1 compare `
  "C:\QA_inputs\git_v1" "C:\QA_inputs\local_v2" `
  --features "C:\QA_inputs\features.json"
```

단일 파일 스냅샷은 파일 입력으로 연결합니다. 서로 다른 원본 파일명도 기존 `compare before.py after.py`처럼 최신 파일명으로 맞춰 비교합니다. 기능 매핑은 최신 파일명 기준으로 작성하세요.

비교 루트는 import 경로의 기준과 같아야 합니다. `src/pkg/auth.py`를 `pkg.auth`로 import한다면 두 입력 모두 `--source-root src`로 준비하고 기능 매핑도 `pkg/auth.py`로 작성합니다. 현재 AST 비교는 Python만 지원합니다. 엔진 C#/C++·복원 Java·씬/프리팹은 목록과 보관까지이며 해당 분석기는 추후 추가합니다. APK/IPA 스냅샷을 현재 Python 비교기에 넣으면 지원 범위를 설명하는 오류를 반환합니다.

APK와 Git을 비교할 다음 단계는 Git 커밋을 같은 환경/설정으로 빌드해 패키지끼리 비교하거나, 동일 빌드의 매핑/심볼과 빌드 기록을 이용한 추적성 분석입니다. 컴파일러·난독화·압축·서명 등의 차이를 소스 기능 변경으로 단정하지 않습니다.

## 예제 입력 생성과 검증

```powershell
cd C:\codes\QA_train\streamlit
.\.venv\Scripts\python.exe -B .\examples\conversion\create_demo_inputs.py "C:\QA_inputs\fixture_inputs"
.\run_ast_analyzer.ps1 convert "C:\QA_inputs\fixture_inputs\unity_project" --output "C:\QA_inputs\fixture_engine"
.\run_ast_analyzer.ps1 convert "C:\QA_inputs\fixture_inputs\package_fixture.apk" --output "C:\QA_inputs\fixture_apk"
.\run_ast_analyzer.ps1 convert "C:\QA_inputs\fixture_inputs\ios_package_fixture.ipa" --output "C:\QA_inputs\fixture_ipa"
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

APK/IPA 예제는 파일 구성·추출 검증을 위한 **설치 불가능한 합성 ZIP fixture**입니다. 실제 Android/iOS 빌드·에디터 실행·JADX 복원·기능 테스트의 성공을 대신하지 않습니다.
