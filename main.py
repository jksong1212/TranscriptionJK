import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from transcription import TranscriptionController


def main():
    app = QGuiApplication(sys.argv)
    app.setApplicationName("소리노트")
    app.setOrganizationName("SoundNote")
    QQuickStyle.setStyle("Basic")
    controller = TranscriptionController()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("transcriber", controller)
    engine.load(Path(__file__).parent / "qml" / "Main.qml")
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
