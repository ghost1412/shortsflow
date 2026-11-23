"""Score what the case explainer decides on a fixed set of topics (script step only: no narration, no render). See engine/case_scorecard.py.

    python scripts/case_scorecard.py                          # every topic
    python scripts/case_scorecard.py --topics rainbow,fridge --length short
    python scripts/case_scorecard.py --llm local              # the model on this PC only (nothing leaves it)
    python scripts/case_scorecard.py --json scorecard.json    # also keep the numbers
"""
import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import case_scorecard  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topics", default=",".join(case_scorecard.TOPICS), help="comma separated: " + ", ".join(case_scorecard.TOPICS))
    p.add_argument("--length", default="standard", choices=("short", "standard", "long"))
    p.add_argument("--llm", default="auto", choices=("auto", "local", "cloud"))
    p.add_argument("--out", default=None, help="where the script folders go (default: a temporary folder)")
    p.add_argument("--json", default=None, help="also write the numbers to this file")
    args = p.parse_args(argv)
    topics = [t.strip() for t in args.topics.split(",") if t.strip()]
    unknown = [t for t in topics if t not in case_scorecard.TOPICS]
    if unknown:
        print(f"[Error] Unknown topic(s): {', '.join(unknown)}. Choose from: {', '.join(case_scorecard.TOPICS)}.")
        return 2
    out = args.out or tempfile.mkdtemp(prefix="sf_scorecard_")
    results = case_scorecard.run(topics, out, args.length, args.llm)
    print()
    print(case_scorecard.table(results))
    print(f"\nScripts are in {out}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
