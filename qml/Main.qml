import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    width: 960
    height: 840
    minimumWidth: 720
    minimumHeight: 760
    visible: true
    title: "소리노트 · 음성 전사" + (transcriber.dirty ? " *" : "")
    color: "#f4f6fa"
    palette.window: "#f4f6fa"
    palette.windowText: "#263650"
    palette.text: "#263650"
    palette.base: "#ffffff"
    palette.button: "#e7edf7"
    palette.buttonText: "#263650"
    palette.highlight: "#3868c6"
    palette.highlightedText: "#ffffff"
    font.family: "Malgun Gothic"
    font.pixelSize: 14
    property bool allowClose: false

    function startTranscription() {
        transcriber.start(modelChoice.currentValue, languageChoice.currentValue, vadChoice.checked,
                          speakerChoice.checked, tokenField.text, speakerCount.value)
    }
    onClosing: function(event) {
        if (transcriber.busy) {
            event.accepted = false
            errorDialog.text = "전사 중입니다. 중지를 누른 후 처리가 끝나면 닫아 주세요."
            errorDialog.open()
        } else if (transcriber.dirty && !allowClose) {
            event.accepted = false
            closeDialog.open()
        }
    }

    FileDialog {
        id: audioDialog
        title: "녹음 파일 불러오기"
        nameFilters: ["오디오 파일 (*.wav *.mp3 *.m4a *.flac *.ogg *.aac *.wma *.mp4 *.webm)", "모든 파일 (*)"]
        onAccepted: transcriber.selectFile(selectedFile)
    }
    FileDialog {
        id: saveDialog
        title: "전사 결과 저장"
        fileMode: FileDialog.SaveFile
        nameFilters: ["텍스트 파일 (*.txt)"]
        defaultSuffix: "txt"
        onAccepted: transcriber.save(selectedFile)
    }
    MessageDialog { id: errorDialog; title: "안내"; buttons: MessageDialog.Ok }
    MessageDialog {
        id: replaceDialog
        title: "새 전사 시작"
        text: "저장하지 않은 결과가 있습니다. 현재 결과를 지우고 새로 전사할까요?"
        buttons: MessageDialog.Yes | MessageDialog.No
        onButtonClicked: function(button, role) { if (button === MessageDialog.Yes) window.startTranscription() }
    }
    MessageDialog {
        id: closeDialog
        title: "저장하지 않은 결과"
        text: "저장하지 않은 결과를 버리고 종료할까요?"
        buttons: MessageDialog.Yes | MessageDialog.No
        onButtonClicked: function(button, role) {
            if (button === MessageDialog.Yes) { window.allowClose = true; window.close() }
        }
    }
    Connections {
        target: transcriber
        function onError(message) { errorDialog.text = message; errorDialog.open() }
        function onChanged() {
            if (editor.text !== transcriber.text) editor.text = transcriber.text
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 20
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 5
                Label { text: "소리노트"; font.pixelSize: 30; font.bold: true; color: "#17243c" }
                Label { text: "녹음 속 이야기를 텍스트로 옮기세요."; color: "#68758b" }
            }
            Item { Layout.fillWidth: true }
            Label { text: "LOCAL TRANSCRIPTION"; color: "#64748b"; font.pixelSize: 11; font.letterSpacing: 1 }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: filePanel.implicitHeight + 36
            radius: 14
            color: "white"
            border.color: "#e2e7ef"
            ColumnLayout {
                id: filePanel
                anchors.fill: parent
                anchors.margins: 18
                spacing: 14
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: transcriber.fileName; Layout.fillWidth: true; elide: Text.ElideMiddle; font.bold: true; color: "#263650" }
                    Button { text: "녹음 파일 불러오기"; enabled: !transcriber.busy; onClicked: audioDialog.open() }
                }
                RowLayout {
                    spacing: 10
                    Label { text: "언어"; color: "#68758b" }
                    ComboBox {
                        id: languageChoice
                        textRole: "label"; valueRole: "code"
                        model: [{label: "자동 감지", code: "auto"}, {label: "한국어", code: "ko"}, {label: "영어", code: "en"}, {label: "일본어", code: "ja"}]
                        currentIndex: 1
                        enabled: !transcriber.busy
                        Layout.preferredWidth: 130
                    }
                    Label { text: "모델"; color: "#68758b" }
                    ComboBox {
                        id: modelChoice
                        textRole: "label"; valueRole: "code"
                        model: [{label: "빠르게 · Tiny", code: "tiny"}, {label: "균형 · Base", code: "base"}, {label: "정확하게 · Small", code: "small"}, {label: "고정확도 · Medium", code: "medium"}, {label: "고정확도 · Large v3", code: "large-v3"}]
                        currentIndex: 2
                        enabled: !transcriber.busy
                        Layout.preferredWidth: 175
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: transcriber.busy ? "중지" : "전사 시작"
                        enabled: transcriber.hasFile
                        highlighted: true
                        onClicked: {
                            if (transcriber.busy) transcriber.cancel()
                            else if (transcriber.dirty) replaceDialog.open()
                            else window.startTranscription()
                        }
                    }
                }
                CheckBox {
                    id: vadChoice
                    text: "무음 구간 건너뛰기 (작은 목소리가 빠지면 해제)"
                    checked: false
                    enabled: !transcriber.busy
                }
                RowLayout {
                    Layout.fillWidth: true
                    CheckBox {
                        id: speakerChoice
                        objectName: "speakerChoice"
                        text: "A/B 자동 화자 구분"
                        checked: true
                        enabled: !transcriber.busy
                    }
                    Item { Layout.fillWidth: true }
                    Label { text: "인원 (0 = 자동)"; color: "#68758b" }
                    SpinBox {
                        id: speakerCount
                        from: 0; to: 10; value: 0
                        enabled: speakerChoice.checked && !transcriber.busy
                    }
                    Button { text: "화자 설정"; onClicked: speakerSettings.open() }
                }
                Label {
                    visible: speakerChoice.checked
                    text: "전사 후 목소리를 비교해 A/B/C로 표시합니다. 처음에는 ‘화자 설정’이 필요합니다."
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    font.pixelSize: 12
                    color: "#68758b"
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "전사 결과"; font.bold: true; font.pixelSize: 17; color: "#263650" }
            Label { text: transcriber.dirty ? "• 저장 전" : ""; color: "#8a6470"; font.pixelSize: 12 }
            Item { Layout.fillWidth: true }
            Label { text: editor.length.toLocaleString() + "자"; color: "#68758b" }
            Button {
                text: "TXT로 저장"
                enabled: !transcriber.busy && transcriber.text.trim().length > 0
                onClicked: { saveDialog.selectedFile = transcriber.suggestedSaveUrl; saveDialog.open() }
            }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 120
            color: "white"
            radius: 12
            border.color: editor.activeFocus ? "#7d9eea" : "#e2e7ef"
            ScrollView {
                anchors.fill: parent
                anchors.margins: 4
                clip: true
                TextArea {
                    id: editor
                    objectName: "transcriptEditor"
                    placeholderText: "녹음 파일을 선택하고 전사를 시작하세요.\n완성된 텍스트는 여기에서 직접 수정할 수 있습니다."
                    placeholderTextColor: "#94a0b2"
                    color: "#25334a"
                    padding: 18
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    readOnly: transcriber.busy
                    background: null
                    onTextChanged: transcriber.editText(text)
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            ProgressBar {
                Layout.fillWidth: true
                visible: transcriber.busy
                value: transcriber.progress
                indeterminate: transcriber.busy && transcriber.progress === 0
            }
            Label { text: transcriber.status; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#52627a"; font.pixelSize: 12 }
            Label { text: "음성은 이 PC에서 처리됩니다. 첫 실행 시 모델 다운로드를 위해 인터넷이 필요합니다."; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#8a96a8"; font.pixelSize: 11 }
        }
    }

    Dialog {
        id: speakerSettings
        title: "자동 화자 구분 설정"
        anchors.centerIn: parent
        width: Math.min(window.width - 40, 620)
        modal: true
        standardButtons: Dialog.Close
        contentItem: ColumnLayout {
            spacing: 12
            Label {
                text: "무료 Community-1 모델을 PC에서 실행합니다. 처음 사용 시 아래 모델 페이지에서 사용 조건에 동의하고, 접근 권한이 있는 Hugging Face 토큰을 입력하세요."
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Button { text: "모델 사용 동의 페이지"; onClicked: Qt.openUrlExternally("https://huggingface.co/pyannote/speaker-diarization-community-1") }
                Button { text: "토큰 발급 페이지"; onClicked: Qt.openUrlExternally("https://huggingface.co/settings/tokens") }
            }
            TextField {
                id: tokenField
                objectName: "speakerToken"
                Layout.fillWidth: true
                placeholderText: "HF 토큰 (기존 HF 로그인 / HF_TOKEN 사용 시 비워 두세요)"
                echoMode: TextInput.Password
                enabled: !transcriber.busy
                selectByMouse: true
            }
            Label {
                text: "입력한 토큰은 앱 종료 시 사라지며 파일에 저장하지 않습니다. 화자 구분에 실패해도 일반 전사 결과는 유지됩니다. A/B는 이 녹음 안에서의 구분이며 실제 이름을 뜻하지 않습니다."
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                color: "#68758b"
            }
        }
    }
}

