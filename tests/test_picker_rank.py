from engine.analysis import pick_backfill
from engine.highlight_quality import boilerplate_hits, disfluency


def seg(start, end, text, score=0.6):
    return {"start": start, "end": end, "norm_score": score, "norm_audio": 0.0, "text": text}


def test_shown_score_agrees_with_the_choice_order():
    # a window that opens with a mic check ranks lower, so its shown score is lower too (it used to show the raw signal score)
    good = seg(0.0, 40.0, "Why did nobody tell us this was possible? The answer changed how we build everything today.")
    bad = seg(100.0, 140.0, "Testing, one two three, can you hear me, uh um okay so yeah.")
    out = {o["start"]: o["final_score"] for o in pick_backfill([good, bad], [], 2)}
    assert out[0.0] > out[100.0]


def test_disfluency():
    stutter = "the, the, the, the pressure on the eyeball, of a, of a, of a fundamental thing"
    halting = "...an... ...entity scheme... ...for... ...epistol. So this... ...could be for songs... ...but... ...and..."
    clean = "The pressure inside the station is set close to sea level, because the crew needs to breathe normally."
    assert disfluency(stutter) > 0.4 and disfluency(halting) > 0.4 and disfluency(clean) == 0.0
    assert disfluency("the, the") == 0.0                       # too short to judge


def test_outro_and_retake_phrases_are_housekeeping():
    assert boilerplate_hits("So that is what I want to finish with. Thank you very much.") == 1
    assert boilerplate_hits("Feel free to contact me. Let me start that over.") == 2
    assert boilerplate_hits("Thank you very much, said the host, and then the real story began.") == 0     # only a closing thank-you counts
