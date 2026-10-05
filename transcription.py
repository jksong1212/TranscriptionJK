from pathlib import Path

from speakers import DiarizationCancelled, diarize, format_speakers

from PySide6.QtCore import QObject, Property, QIODevice, QSaveFile, QThread, QUrl, Signal, Slot


class TranscriptionWorker(QThread):
    status = Signal(str)
    segment = Signal(str)
    progress = Signal(float)
    completed = Signal(bool)
    failed = Signal(str)
    warning = Signal(str)
    replacement = Signal(str)

    def __init__(self, path, model_name, language, parent=None, vad_filter=False,
                 speaker_enabled=False, token="", speaker_count=0):
        super().__init__(parent)
        self.path, self.model_name, self.language = path, model_name, language
        self.vad_filter = vad_filter
        self.speaker_enabled, self.token, self.speaker_count = speaker_enabled, token, speaker_count

    def run(self):
        try:
            from faster_whisper import WhisperModel

            self.status.emit("모델 준비 중 · 처음 실행하면 다운로드에 시간이 걸립니다.")
            model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            if self.isInterruptionRequested():
                self.completed.emit(True)
                return
            self.status.emit("음성을 분석하고 있습니다…")
            segments, info = model.transcribe(
                self.path, language=self.language, beam_size=5,
                vad_filter=self.vad_filter, condition_on_previous_text=False,
                word_timestamps=self.speaker_enabled,
            )
            collected = []
            self.status.emit(f"전사 중 · 전체 {info.duration:.1f}초 · 첫 구간 분석 중")
            for segment in segments:
                if self.isInterruptionRequested():
                    self.completed.emit(True)
                    return
                text = segment.text.strip()
                if text:
                    self.segment.emit(text)
                    if self.speaker_enabled:
                        collected.append(segment)
                scale = 0.8 if self.speaker_enabled else 1.0
                self.progress.emit(min(segment.end / max(info.duration, 0.001), 0.99) * scale)
                self.status.emit(f"전사 중 · {segment.end:.1f} / {info.duration:.1f}초 위치까지 인식")
            # Release Whisper before loading the second model to reduce peak memory.
            del segments, model
            if self.speaker_enabled and collected and not self.isInterruptionRequested():
                try:
                    turns = diarize(self.path, self.token, self.speaker_count,
                                    self.status.emit, self.isInterruptionRequested)
                    if not turns:
                        raise ValueError("No speaker turns")
                    self.replacement.emit(format_speakers(collected, turns))
                except DiarizationCancelled:
                    self.completed.emit(True)
                    return
                except Exception:
                    # Do not expose exception URLs/headers containing credentials.
                    self.warning.emit("전사는 완료됐지만 A/B 화자 구분에 실패했습니다. 일반 전사 결과는 보존했습니다.\n"
                                      "화자 모델 사용 동의, HF 토큰 권한, 인터넷 연결을 확인하세요. "
                                      "패키지 오류가 있으면 run.bat으로 다시 실행하세요.")
            self.completed.emit(self.isInterruptionRequested())
        except Exception as exc:
            self.failed.emit(f"전사하지 못했습니다. 파일과 인터넷 연결(첫 모델 다운로드)을 확인하세요.\n{exc}")
        finally:
            self.token = ""


class TranscriptionController(QObject):
    changed = Signal()
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._path = ""
        self._text = ""
        self._status = "녹음 파일을 불러와 시작하세요."
        self._busy = False
        self._progress = 0.0
        self._dirty = False
        self._worker = None
        self._speaker_warning = False

    @Property(str, notify=changed)
    def fileName(self):
        return Path(self._path).name if self._path else "선택한 파일이 없습니다"

    @Property(bool, notify=changed)
    def hasFile(self):
        return bool(self._path)

    @Property(str, notify=changed)
    def text(self):
        return self._text

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(bool, notify=changed)
    def dirty(self):
        return self._dirty

    @Property(float, notify=changed)
    def progress(self):
        return self._progress

    @Property(QUrl, notify=changed)
    def suggestedSaveUrl(self):
        return QUrl.fromLocalFile(str(Path(self._path).with_suffix(".txt"))) if self._path else QUrl()

    @Slot(QUrl)
    def selectFile(self, url):
        if self._busy:
            return
        path = Path(url.toLocalFile())
        if not url.isLocalFile() or not path.is_file():
            self.error.emit("읽을 수 있는 로컬 파일을 선택하세요.")
            return
        self._path = str(path)
        self._status = "준비되었습니다. 전사 시작을 눌러 주세요."
        self.changed.emit()

    @Slot(str)
    def editText(self, text):
        if not self._busy and text != self._text:
            self._text = text
            self._dirty = True
            self.changed.emit()

    @Slot(str, str)
    @Slot(str, str, bool)
    @Slot(str, str, bool, bool, str, int)
    def start(self, model_name, language, vad_filter=False, speaker_enabled=False, token="", speaker_count=0):
        if self._busy or not self._path:
            return
        if speaker_count not in range(0, 11):
            self.error.emit("화자 수는 자동 감지 또는 1~10명으로 선택하세요.")
            return
        if model_name not in {"tiny", "base", "small", "medium", "large-v3"} or language not in {"auto", "ko", "en", "ja"}:
            self.error.emit("지원하지 않는 모델 또는 언어입니다.")
            return
        self._busy, self._text, self._progress, self._dirty = True, "", 0.0, False
        self._status = "전사를 시작합니다…"
        self._speaker_warning = False
        worker = TranscriptionWorker(self._path, model_name, None if language == "auto" else language, self,
                                     vad_filter=vad_filter, speaker_enabled=speaker_enabled,
                                     token=token.strip(), speaker_count=speaker_count)
        self._worker = worker
        worker.status.connect(self._set_status)
        worker.segment.connect(self._append)
        worker.progress.connect(self._set_progress)
        worker.completed.connect(self._complete)
        worker.failed.connect(self._fail)
        worker.warning.connect(self._warn)
        worker.replacement.connect(self._replace)
        worker.finished.connect(self._finished)
        self.changed.emit()
        worker.start()

    @Slot()
    def cancel(self):
        if self._worker and self._busy:
            self._worker.requestInterruption()
            self._set_status("중지 요청됨 · 현재 모델 준비/음성 구간 처리가 끝나면 중지합니다.")

    @Slot(str)
    def _set_status(self, status):
        self._status = status
        self.changed.emit()

    @Slot(str)
    def _append(self, text):
        self._text += ("\n" if self._text else "") + text
        self._dirty = True
        self.changed.emit()

    @Slot(float)
    def _set_progress(self, progress):
        self._progress = progress
        self.changed.emit()

    @Slot(bool)
    def _complete(self, cancelled):
        self._status = "중지되었습니다. 지금까지의 결과를 저장할 수 있습니다." if cancelled else (
            "전사가 완료되었습니다." if self._text else "인식된 음성이 없습니다. 파일과 언어 설정을 확인하세요."
        )
        if not cancelled and self._speaker_warning:
            self._status = "전사 완료 · 화자 구분 실패 (일반 전사 결과를 저장할 수 있습니다.)"
        if not cancelled:
            self._progress = 1.0
        self.changed.emit()

    @Slot(str)
    def _replace(self, text):
        self._text = text
        self._dirty = True
        self.changed.emit()

    @Slot(str)
    def _warn(self, message):
        self._speaker_warning = True
        self.error.emit(message)

    @Slot(str)
    def _fail(self, message):
        self._set_status("전사 실패 · 설정을 확인한 후 다시 시도하세요.")
        self.error.emit(message)

    @Slot()
    def _finished(self):
        self._busy = False
        self._worker.deleteLater()
        self._worker = None
        self.changed.emit()

    @Slot(QUrl, result=bool)
    def save(self, url):
        if self._busy or not self._text.strip():
            return False
        if not url.isLocalFile():
            self.error.emit("저장할 로컬 경로를 선택하세요.")
            return False
        path = Path(url.toLocalFile())
        # The dialog supplies .txt by default; retain explicitly chosen filenames.
        output = QSaveFile(str(path))
        data = (self._text.rstrip() + "\n").encode("utf-8-sig")
        if not output.open(QIODevice.OpenModeFlag.WriteOnly):
            self.error.emit(f"저장하지 못했습니다: {output.errorString()}")
            return False
        if output.write(data) != len(data):
            output.cancelWriting()
            self.error.emit("파일 쓰기에 실패했습니다. 저장 공간을 확인하세요.")
            return False
        if not output.commit():
            self.error.emit(f"저장하지 못했습니다: {output.errorString()}")
            return False
        self._dirty = False
        self._set_status(f"저장 완료 · {path.name}")
        return True
