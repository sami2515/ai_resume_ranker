"""
Scores agreement between two independent labeling passes (Section 2.2).

Usage (from repo root):
    python backend/scripts/check_labeling_agreement.py docs/labels_person_a.json docs/labels_person_b.json
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from ml.labeling import compute_agreement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels_a", help="First labeler's worksheet JSON.")
    parser.add_argument("labels_b", help="Second labeler's worksheet JSON (independent re-labeling of a subset).")
    args = parser.parse_args()

    result = compute_agreement(Path(args.labels_a), Path(args.labels_b))

    print(f"Compared {result['n_compared']} resume(s) labeled by both.")
    print(f"Percent agreement: {result['percent_agreement']:.1%}")
    if result["cohen_kappa"] is not None:
        print(f"Cohen's kappa:     {result['cohen_kappa']:.3f}")
    else:
        print("Cohen's kappa: not defined (only one distinct label used across both raters).")

    if result["disagreements"]:
        print(f"\n{len(result['disagreements'])} disagreement(s) -- discuss and resolve these together, "
              f"sharpening the Section 2.1 taxonomy rule if the disagreement reveals it was ambiguous:")
        for d in result["disagreements"]:
            print(f"  {d['filename']}: {d['labeler_a']!r} vs {d['labeler_b']!r}")
    else:
        print("\nNo disagreements on the compared subset.")


if __name__ == "__main__":
    main()
