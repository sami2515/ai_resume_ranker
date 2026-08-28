"""
Builds a labeling worksheet for one labeler (ML Training Master Plan Section 2.2).

Usage (from repo root):
    python backend/scripts/build_labeling_worksheet.py --out docs/labels_person_a.json
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from ml.labeling import build_labeling_worksheet, DEFAULT_RESUME_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Path to write the worksheet JSON to.")
    parser.add_argument("--resume-dir", default=str(DEFAULT_RESUME_DIR), help="Directory of resumes to label.")
    args = parser.parse_args()

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    n = build_labeling_worksheet(out_path, Path(args.resume_dir))
    print(f"Wrote {n} resume(s) to {out_path}.")
    print("Fill in 'category' for every entry (reading body_text_preview, never the filename), "
          "then set 'labeler' to your name.")


if __name__ == "__main__":
    main()
