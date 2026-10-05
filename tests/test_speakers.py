import unittest
from types import SimpleNamespace as NS

from speakers import SpeakerTurn, format_speakers, speaker_label


class SpeakerTests(unittest.TestCase):
    def test_splits_words_and_reuses_speaker_identity(self):
        segments = [NS(words=[NS(start=0, end=1, word="안녕하세요."),
                              NS(start=1, end=2, word=" 네."),
                              NS(start=2, end=3, word=" 반갑습니다.")])]
        turns = [SpeakerTurn(0, 1, "speaker9"), SpeakerTurn(1, 2, "speaker2"),
                 SpeakerTurn(2, 3, "speaker9")]
        self.assertEqual(format_speakers(segments, turns), "A: 안녕하세요.\nB: 네.\nA: 반갑습니다.")

    def test_largest_total_overlap_and_unknown(self):
        segments = [NS(start=0, end=2, text=" hello", words=None),
                    NS(start=10, end=11, text=" unmatched", words=None)]
        turns = [SpeakerTurn(0, .5, "one"), SpeakerTurn(.5, 2, "two")]
        self.assertEqual(format_speakers(segments, turns), "B: hello\n화자 미확인: unmatched")

    def test_alphabet_labels(self):
        self.assertEqual([speaker_label(i) for i in (0, 25, 26)], ["A", "Z", "AA"])
