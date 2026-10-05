# 소리노트

Python + PySide6/QML 기반의 간단한 로컬 음성 전사 앱입니다.

## 실행 (Windows, uv 사용)

[uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치한 뒤 `run.bat`을 더블 클릭하세요.
uv가 Python 3.12와 필요한 패키지를 준비하고 앱을 실행합니다. 최초 설치에는 인터넷이 필요합니다.
터미널에서도 실행할 수 있습니다.

```powershell
.\run.bat
```

`run.bat`은 `UV_PROJECT_ENVIRONMENT=C:\uv_envs\Transcription_py`를 설정하고
`uv run .\main.py %*`로 실행합니다. 가상 환경은 해당 경로에 자동 생성되며,
다른 폴더에서 실행해도 정상적으로 앱을 엽니다.

다른 PC에 배포할 때는 `.venv`, `.python`, `.uv-cache`, `__pycache__`를 제외하고 복사하세요.
`pyproject.toml`, `uv.lock`, `.python-version`, Python 소스, `qml` 폴더와 `run.bat`은 포함해야 합니다.
받는 PC에도 uv가 설치되어 있어야 하며, 실행하면 해당 PC용 환경을 새로 만듭니다.

`녹음 파일 불러오기` → 언어/모델 선택 → `전사 시작` → 결과 편집 → `TXT로 저장` 순서로 사용합니다.
MP3, WAV, M4A, FLAC 등 FFmpeg/PyAV가 지원하는 오디오를 처리합니다.
TXT는 Windows에서도 한글을 읽기 쉬운 UTF-8 BOM 형식으로 원자적으로 저장합니다.
저장하지 않은 결과를 새 전사로 지우거나 앱을 닫을 때 확인합니다.

## 전사 모델

- Tiny: 빠른 초안용
- Base: 속도와 정확도의 균형
- Small: 기본값, 더 높은 정확도, 더 많은 메모리와 처리 시간
- Medium / Large v3: 정확도를 우선할 때 선택, CPU에서는 처리가 오래 걸릴 수 있습니다.

기본 언어는 한국어입니다. 다른 언어는 직접 선택하거나 자동 감지를 사용하세요.
작은 목소리가 음성 감지 필터에서 제외되지 않도록 `무음 구간 건너뛰기`는 기본적으로 꺼져 있습니다.
무음이 긴 녹음에서는 이 옵션을 켜면 도움이 될 수 있습니다. 필터를 끄더라도 음성 인식 모델 자체의
누락이나 무음 구간의 잘못된 인식이 없어지는 것은 아닙니다. 처리 중에는 인식 위치와 전체 길이를 표시합니다.

CPU/int8 방식이므로 별도의 GPU나 API 키가 필요하지 않습니다.
선택한 모델은 첫 사용 때 Hugging Face에서 다운로드되어 사용자 캐시에 보관됩니다.
이후 캐시가 있으면 오프라인에서도 사용할 수 있습니다. 녹음 파일은 서버로 업로드하지 않습니다.
긴 녹음은 CPU 성능에 따라 시간이 걸립니다. 잡음, 음악, 겹치는 목소리는 정확도에 영향을 줍니다.
진행률은 처리한 음성 구간 위치 기준이며 남은 시간 추정치는 아닙니다.
중지 요청은 모델 준비/현재 음성 구간 처리 후 적용됩니다. 중지 후에는 부분 결과를 저장할 수 있습니다.

## A/B 자동 화자 구분

`A/B 자동 화자 구분`은 기본으로 켜져 있습니다. 전사를 마친 후
`pyannote/speaker-diarization-community-1` 모델이 같은 목소리를 묶고,
단어별 시간과 비교하여 `A: ...`, `B: ...` 형식으로 표시합니다. TXT에도 그대로 저장됩니다.
첫 등장 순서로 A/B/C를 부여하며, 녹음마다 독립적인 표시입니다. 실제 이름을 식별하지 않습니다.
겹쳐 말하기와 짧은 응답에서는 구분이 틀릴 수 있고, 대응하는 화자가 없으면 `화자 미확인`으로 남깁니다.

최초 설정:

1. 앱의 `화자 설정` → `모델 사용 동의 페이지`에서 Hugging Face 계정으로 조건에 동의합니다.
2. `토큰 발급 페이지`에서 해당 모델을 읽을 수 있는 토큰을 발급하고 앱의 비밀번호 입력란에 넣습니다.
3. 필요하면 인원을 지정합니다. 두 사람 대화는 `2`, 인원을 모르면 `0`(자동)을 사용합니다.
4. 전사를 시작합니다. 처음에는 모델 다운로드 시간이 추가됩니다.

앱 입력 토큰은 파일에 저장하지 않습니다. 이미 Hugging Face에 로그인했거나 `HF_TOKEN` 환경 변수를
설정했다면 입력란은 비워도 됩니다. 토큰은 채팅이나 소스 코드에 넣지 마세요.
음성은 로컬에서 처리하고 pyannote 사용량 수집은 비활성화합니다.
모델 권한/다운로드 오류가 나면 일반 전사는 남기고 화자 구분 실패를 안내합니다.
화자 분석 중 중지는 현재 분석 단계가 끝나거나 진행 알림이 발생할 때 적용됩니다.
`run.bat`은 기존대로 `C:\uv_envs\Transcription_py`에 화자 구분 패키지도 자동 설치합니다.

모델 출처: [pyannote Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1),
CC BY 4.0, pyannote. 이 앱은 전사와 화자 시간 정보를 결합하며 모델 가중치를 수정하지 않습니다.

## 검증

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'C:\uv_envs\Transcription_py'
uv run python -m unittest discover -s tests -v
```

테스트는 가짜 전사 엔진으로 비동기 처리와 오류, 취소, 저장 및 QML 로딩을 확인합니다.
실제 음성 인식 품질 확인에는 녹음 파일과 다운로드된 모델이 필요합니다.

## 참고

- [Qt for Python QML](https://doc.qt.io/qtforpython-6/tutorials/qmlapp/qmlapplication.html)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
