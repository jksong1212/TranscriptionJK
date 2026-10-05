import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QUrl, QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from transcription import TranscriptionController, TranscriptionWorker
from speakers import SpeakerTurn, DiarizationCancelled


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle("Basic")
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.controller = TranscriptionController()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.audio = Path(self.temp.name) / "녹음.wav"
        self.audio.write_bytes(b"test")
        self.controller.selectFile(QUrl.fromLocalFile(str(self.audio)))

    def wait_for_completion(self):
        deadline = time.monotonic() + 5
        while self.controller.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertFalse(self.controller.busy)

    def test_async_transcription_and_unicode_save(self):
        options = []
        class Model:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, path, **kwargs):
                options.append(kwargs)
                return iter([types.SimpleNamespace(text=" 안녕하세요. ", end=1),
                             types.SimpleNamespace(text="테스트입니다.", end=2)]), types.SimpleNamespace(duration=2)

        with patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=Model)}):
            self.controller.start("base", "ko")
            self.wait_for_completion()
        self.assertEqual(self.controller.text, "안녕하세요.\n테스트입니다.")
        self.assertEqual(self.controller.progress, 1)
        self.assertFalse(options[0]["vad_filter"])
        self.assertFalse(options[0]["condition_on_previous_text"])
        self.controller.editText(self.controller.text + "\n수정됨")
        target = Path(self.temp.name) / "결과.txt"
        target.write_text("previous", encoding="utf-8")
        self.assertTrue(self.controller.save(QUrl.fromLocalFile(str(target))))
        self.assertEqual(target.read_text(encoding="utf-8-sig"), self.controller.text + "\n")
        self.assertFalse(self.controller.dirty)

    def test_worker_error_releases_busy_state(self):
        def broken(*args, **kwargs):
            raise ValueError("invalid audio")

        errors = []
        self.controller.error.connect(errors.append)
        with patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=broken)}):
            self.controller.start("tiny", "auto")
            self.wait_for_completion()
        self.assertIn("invalid audio", errors[0])

    def test_cancellation_keeps_partial_result(self):
        worker = TranscriptionWorker(str(self.audio), "tiny", None)
        results, cancelled = [], []

        class Model:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, *args, **kwargs):
                def segments():
                    yield types.SimpleNamespace(text="partial", end=1)
                    worker.requestInterruption()
                    yield types.SimpleNamespace(text="unwanted", end=2)
                return segments(), types.SimpleNamespace(duration=2)

        worker.segment.connect(results.append)
        worker.completed.connect(cancelled.append)
        with patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=Model)}):
            worker.start()
            self.assertTrue(worker.wait(5000))
            self.app.processEvents()
        self.assertEqual(results, ["partial"])
        self.assertEqual(cancelled, [True])

    def test_invalid_file_and_save_failure(self):
        errors = []
        self.controller.error.connect(errors.append)
        self.controller.selectFile(QUrl("https://example.com/audio.mp3"))
        self.assertEqual(self.controller.fileName, "녹음.wav")
        self.controller.editText("keep me")
        self.assertFalse(self.controller.save(QUrl.fromLocalFile(str(Path(self.temp.name) / "missing" / "result.txt"))))
        self.assertTrue(self.controller.dirty)
        self.assertEqual(len(errors), 2)

    def run_speaker_job(self, side_effect=None):
        class Model:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, path, **kwargs):
                assert kwargs["word_timestamps"] is True
                return iter([types.SimpleNamespace(start=0, end=1, text="첫 말", words=None),
                             types.SimpleNamespace(start=1, end=2, text="답변", words=None)]), types.SimpleNamespace(duration=2)

        with patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=Model)}), \
             patch("transcription.diarize", side_effect=side_effect,
                   return_value=[SpeakerTurn(0, 1, "x"), SpeakerTurn(1, 2, "y")]) as mock:
            self.controller.start("base", "ko", False, True, "test-token", 2)
            self.wait_for_completion()
            self.assertEqual(mock.call_args.args[2], 2)

    def test_speaker_output_saved_with_labels(self):
        self.run_speaker_job()
        self.assertEqual(self.controller.text, "A: 첫 말\nB: 답변")
        target = Path(self.temp.name) / "speakers.txt"
        self.assertTrue(self.controller.save(QUrl.fromLocalFile(str(target))))
        self.assertIn("B: 답변", target.read_text(encoding="utf-8-sig"))

    def test_speaker_failure_keeps_text_and_hides_token(self):
        errors = []
        self.controller.error.connect(errors.append)
        self.run_speaker_job(RuntimeError("secret test-token"))
        self.assertEqual(self.controller.text, "첫 말\n답변")
        self.assertIn("화자 구분 실패", self.controller.status)
        self.assertEqual(len(errors), 1)
        self.assertNotIn("test-token", errors[0])

    def test_speaker_cancel_keeps_transcript(self):
        self.run_speaker_job(DiarizationCancelled())
        self.assertEqual(self.controller.text, "첫 말\n답변")
        self.assertIn("중지", self.controller.status)

    def test_qml_loads_and_shows_transcript(self):
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(lambda values: warnings.extend(str(v) for v in values))
        engine.rootContext().setContextProperty("transcriber", self.controller)
        engine.load(Path(__file__).resolve().parents[1] / "qml" / "Main.qml")
        self.assertTrue(engine.rootObjects(), warnings)
        root = engine.rootObjects()[0]
        self.app.processEvents()
        self.controller.editText("화면 테스트")
        self.app.processEvents()
        editor = root.findChild(QObject, "transcriptEditor")
        self.assertEqual(editor.property("text"), "화면 테스트")
        self.assertTrue(root.findChild(QObject, "speakerChoice").property("checked"))
        self.assertFalse(warnings, warnings)
        root.setProperty("allowClose", True)
        root.close()
        del engine


if __name__ == "__main__":
    unittest.main()
