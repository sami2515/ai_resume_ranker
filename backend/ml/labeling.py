"""
Labeling tooling (ML Training Master Plan Section 2.2).

This module builds the worksheet a human labeler fills in, and scores
agreement between two independent labeling passes. It never assigns a
category itself -- doing that would defeat the entire point of an
independent second-pass agreement check, and would mean the "trained"
classifier was actually trained on this tool's own guesses.
"""

from __future__ import annotations
import json
from pathlib import Path

from .taxonomy import CATEGORIES

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RESUME_DIR = REPO_ROOT / "datasets" / "resumes"


def build_labeling_worksheet(out_path: Path, resume_dir: Path = DEFAULT_RESUME_DIR, preview_chars: int = 400) -> int:
    """Writes a JSON worksheet: one entry per resume, with a body-text
    preview (never the filename -- Section 2.2 / ML Engineering Plan
    Finding 2) so a labeler can work from this file without reopening
    every resume, and a blank 'category' field for them to fill in.
    Returns the number of resumes written."""
    from nlp_pipeline.parser import parse_resume, ResumeParseError

    entries = {}
    for f in sorted(resume_dir.glob("*.docx")):
        try:
            parsed = parse_resume(f)
        except ResumeParseError:
            continue
        preview = " ".join(parsed.raw_text.split())[:preview_chars]
        entries[f.name] = {"body_text_preview": preview, "category": None}

    out_path.write_text(
        json.dumps(
            {
                "instructions": (
                    "Read body_text_preview (or the full resume if the preview isn't enough -- "
                    "never the filename) and set 'category' to one of: " + ", ".join(CATEGORIES) + ". "
                    "Leave nothing null when you're done."
                ),
                "labeler": "REPLACE WITH YOUR NAME",
                "entries": entries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return len(entries)


def _load_labels(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries", data)  # accept either the worksheet shape or a flat {filename: category}
    labels = {}
    for filename, value in entries.items():
        category = value["category"] if isinstance(value, dict) else value
        if category:
            labels[filename] = category
    return labels


def compute_agreement(labels_a_path: Path, labels_b_path: Path) -> dict:
    """Percent agreement + Cohen's kappa (Section 2.2) between two
    independent labeling passes, over whichever filenames both labelers
    actually labeled. Cohen's kappa needs at least two distinct labels
    across BOTH raters combined to be defined -- sklearn raises on a
    degenerate single-label case, so that's surfaced as a clear message
    rather than a stack trace."""
    from sklearn.metrics import cohen_kappa_score

    labels_a = _load_labels(labels_a_path)
    labels_b = _load_labels(labels_b_path)
    shared = sorted(set(labels_a) & set(labels_b))
    if not shared:
        raise ValueError("No overlapping filenames between the two label files -- nothing to compare.")

    a_seq = [labels_a[f] for f in shared]
    b_seq = [labels_b[f] for f in shared]
    agree_count = sum(1 for a, b in zip(a_seq, b_seq) if a == b)
    percent_agreement = agree_count / len(shared)

    kappa = None
    if len(set(a_seq) | set(b_seq)) > 1:
        kappa = cohen_kappa_score(a_seq, b_seq)

    disagreements = [
        {"filename": f, "labeler_a": labels_a[f], "labeler_b": labels_b[f]}
        for f in shared
        if labels_a[f] != labels_b[f]
    ]

    return {
        "n_compared": len(shared),
        "percent_agreement": round(percent_agreement, 4),
        "cohen_kappa": round(kappa, 4) if kappa is not None else None,
        "disagreements": disagreements,
    }
