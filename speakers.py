"""Local diarization and timestamp-based speaker assignment."""
import os
from dataclasses import dataclass

MODEL_ID = "pyannote/speaker-diarization-community-1"


class DiarizationCancelled(Exception):
    pass


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


def diarize(path, token, speaker_count, status, cancelled):
    # Audio and usage metrics stay local. Only model downloads use the network.
    os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
    import torch
    from faster_whisper.audio import decode_audio
    from pyannote.audio import Pipeline

    def check_cancel():
        if cancelled():
            raise DiarizationCancelled()

    check_cancel()
    status("화자 구분 모델 준비 중 · 첫 실행은 다운로드가 필요합니다.")
    pipeline = Pipeline.from_pretrained(MODEL_ID, token=token or None)
    if pipeline is None:
        raise RuntimeError("Speaker model unavailable")
    check_cancel()
    # Use the same decoder/time origin as Whisper, including M4A support.
    waveform = torch.from_numpy(decode_audio(path, sampling_rate=16000)).unsqueeze(0)
    check_cancel()

    def hook(step_name, step_artifact, file=None, total=None, completed=None):
        check_cancel()
        labels = {"segmentation": "음성 구간 분석", "embeddings": "목소리 비교", "clustering": "화자 묶기"}
        label = labels.get(step_name, "화자 분석")
        suffix = f" · {completed}/{total}" if total and completed is not None else ""
        status("A/B 화자 구분 중 · " + label + suffix)

    options = {"num_speakers": speaker_count} if speaker_count else {}
    result = pipeline({"waveform": waveform, "sample_rate": 16000}, hook=hook, **options)
    check_cancel()
    turns = [SpeakerTurn(turn.start, turn.end, speaker)
             for turn, _, speaker in result.exclusive_speaker_diarization.itertracks(yield_label=True)]
    return sorted(turns, key=lambda t: (t.start, t.end))


def speaker_label(index):
    label = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


def format_speakers(segments, turns):
    """Split even a single Whisper segment when its words belong to different speakers.

    Unmatched words remain visible as [화자 미확인]; never invent an alternating speaker.
    """
    turns = sorted(turns, key=lambda t: (t.start, t.end))
    names = {}
    for turn in turns:
        if turn.speaker not in names:
            names[turn.speaker] = speaker_label(len(names))

    def match(start, end):
        scores = {}
        for turn in turns:
            if turn.start >= end:
                break
            overlap = max(0.0, min(end, turn.end) - max(start, turn.start))
            scores[turn.speaker] = scores.get(turn.speaker, 0.0) + overlap
        if not scores or max(scores.values()) <= 0:
            return "화자 미확인"
        return names[max(scores, key=scores.get)]

    lines = []
    for segment in segments:
        words = getattr(segment, "words", None)
        pieces = [(word.start, word.end, word.word) for word in words] if words else [
            (segment.start, segment.end, segment.text)]
        current, parts = None, []
        for start, end, text in pieces:
            if not text.strip():
                continue
            speaker = match(start, end)
            if current is not None and speaker != current:
                lines.append(f"{current}: {''.join(parts).strip()}")
                parts = []
            current = speaker
            parts.append(text)
        if parts:
            lines.append(f"{current}: {''.join(parts).strip()}")
    return "\n".join(lines)
