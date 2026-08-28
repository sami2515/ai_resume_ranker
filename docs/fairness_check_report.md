# Fairness Check Appendix (project documentation Section 12.5)

## Methodology

For each of 10 real resumes from the organizer dataset, we produced an
otherwise-identical copy with only the candidate's name changed to one
independently associated with a different gender or racial/ethnic group,
scored both against the same job description, and checked the composite
score shift against a ±2.0 point tolerance.

The race/ethnicity name pairs are drawn from Bertrand & Mullainathan,
["Are Emily and Greg More Employable Than Lakisha and Jamal? A Field
Experiment on Labor Market
Discrimination"](https://www.nber.org/papers/w9873) (*American Economic
Review*, 2004) — the names were independently validated via Massachusetts
birth records and perception surveys as strongly associated with a given
race, which is why they're used here rather than an internally-guessed
name list. That paper measured a ~50% gap in human-recruiter callback
rates for otherwise-identical resumes under these names; this appendix
asks the same question of this project's automated scoring instead.
Gender pairs use matched first names with a shared surname, isolating
gender as the single changed variable.

Full methodology and code: [`backend/nlp_pipeline/fairness.py`](../backend/nlp_pipeline/fairness.py).
Reproduce with `python backend/scripts/fairness_test.py`.

## Results

JD: **Senior Business Analyst** (`datasets/test_jds/business_analyst.txt`) · Tolerance: ±2.0 points

| Resume | Category | Name A | Name B | Score A | Score B | Delta | Result |
|---|---|---|---|---|---|---|---|
| Adelina_Erimia_PMP1.docx | gender | James Whitfield | Jennifer Whitfield | 56.6 | 56.6 | 0.0 | PASS |
| BA - Candidate_28.docx | gender | Michael Donovan | Michelle Donovan | 63.9 | 63.9 | 0.0 | PASS |
| BA - Candidate_29.docx | gender | Robert Chen | Roberta Chen | 62.7 | 62.7 | 0.0 | PASS |
| BA Candidate_27.docx | gender | David Okafor | Diana Okafor | 64.9 | 64.9 | 0.0 | PASS |
| BA_Candidate44.docx | race/ethnicity | Brad Baker | Jamal Baker | 64.0 | 64.0 | 0.0 | PASS |
| Business Analyst_GHyma.docx | race/ethnicity | Emily Walsh | Lakisha Walsh | 62.5 | 62.5 | 0.0 | PASS |
| Candidate 114 Full Stack Java Developer.docx | race/ethnicity | Greg Sullivan | Darnell Sullivan | 52.0 | 52.0 | 0.0 | PASS |
| Candidate 158 Java.docx | race/ethnicity | Allison Meyer | Ebony Meyer | 51.2 | 51.2 | 0.0 | PASS |
| Candidate 168-NJ - Mar 2018-V3.0.docx | race/ethnicity | Todd Pearson | Tremayne Pearson | 59.5 | 59.5 | 0.0 | PASS |
| Candidate 174 BA.docx | race/ethnicity | Kristen Schaefer | Latoya Schaefer | 62.9 | 62.9 | 0.0 | PASS |

**10/10 pairs passed**, all with a measured delta of 0.0 points (at the
1-decimal precision the scoring engine reports).

## Why the delta is exactly zero — and why that's not the whole story

This isn't a rounding artifact hiding a real gap that we're not showing
you; it follows directly from how this specific pipeline is built, and is
worth explaining rather than just citing the number:

- **Skill matching** (`extractor.py`'s gazetteer) never looks at personal
  names at all — it pattern-matches technical/soft-skill terms, so a name
  change literally cannot move `matched_skills`/`missing_skills`.
- **The semantic score**, in the active backend for this evaluation
  (spaCy word-vector average, `en_core_web_md` — see the README's
  "Semantic matching backend" section), filters out any token without a
  static word vector before building the document embedding. Most person
  names are out-of-vocabulary for a general-purpose word-vector model, so
  they're dropped before scoring, not merely down-weighted.
- **The keyword score** (TF-IDF cosine similarity) is close to
  mathematically insensitive to a single rare token — like a name —
  appearing in one document but not the other; its contribution to the
  cosine-similarity numerator is zero (the other document has weight 0 in
  that dimension), and its effect on the vector norm is negligible for a
  low-frequency term.

**What this does and doesn't prove:** this result shows the current
architecture doesn't leak the specific, literal failure mode this check
targets — a name token directly moving the score. It does **not** prove
the system is unbiased in general. A model can pass this exact check and
still encode bias in subtler ways (e.g., through which schools,
neighborhoods, or phrasing patterns correlate with which demographic
groups) that this check isn't designed to catch.

**Re-run this before trusting the result long-term.** The production
design target (Section 3.4) is real Sentence-BERT embeddings, not the
current spaCy fallback. A transformer sentence encoder processes the
*entire* token sequence — including names — differently from a filtered
word-vector average, and could show a different (though not necessarily
larger) result. If/when `sentence-transformers` is active
(`python -m nlp_pipeline.matching_engine --selftest` shows which backend
is running), re-run `python backend/scripts/fairness_test.py` and update
this appendix rather than assuming the 0.0 result carries over.

Raw data: [`docs/fairness_check_report.json`](fairness_check_report.json).
