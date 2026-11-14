"""The barge-in rule, checked without a microphone.

Run it directly: python tests/test_barge_in.py

This is the one piece of the voice path with real branching, and when it is
wrong it is wrong in a way that is hard to hear: either Kaia talks over
people, or she cuts herself off every time she speaks through a speaker.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routes.voice import should_barge_in, BARGE_IN_GRACE_S


def test():
    asked = "what is the weather in dublin tomorrow"

    # A real interruption, well after she started.
    assert should_barge_in("actually hold on", 2.0, asked)

    # Too short to be speech: a cough, a "mm", a stray syllable.
    assert not should_barge_in("hmm", 2.0, asked)
    assert not should_barge_in("", 2.0, asked)

    # Inside the grace window. Deepgram is still revising the question that
    # started this answer, so anything here is the question, not a new one.
    assert not should_barge_in("actually hold on", BARGE_IN_GRACE_S - 0.1, asked)

    # A late revision of the same question, after the grace window. The
    # prefix check is what stops this one — without it Kaia is cut off by
    # the echo of the very question she is answering.
    assert not should_barge_in("what is the weather in dub", 3.0, asked)

    # Same opening words but a genuinely different question still counts,
    # because the first few characters are all that are compared and these
    # differ inside them.
    assert should_barge_in("no, in Cork instead", 3.0, asked)

    # Nothing asked yet: no echo to confuse it with.
    assert should_barge_in("are you there", 1.0, "")

    print("barge-in rule: ok")


if __name__ == "__main__":
    test()
