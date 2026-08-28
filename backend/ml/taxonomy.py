"""
Resume category label taxonomy (ML Training Master Plan Section 2.1).

Fixed before any labeling happens, and not changed mid-project -- a
shifting taxonomy invalidates whatever labeling was already done. This is
a *separate* concept from services.CATEGORY_KEYWORDS, which infers a job
category from a JD title for the Section 5.4 feedback-loop re-weighting
groups and already existed before this document. This taxonomy is for
classifying a *resume's* content -- the "Classification of Resumes and Job
Post" step in the architecture diagram that Section 2 says doesn't exist
yet as a trained model.
"""

from __future__ import annotations

# name -> the one-line rule two independent labelers should be able to
# apply identically. If a rule can't be written this precisely, per
# Section 2.1, the taxonomy isn't ready -- so these are deliberately
# specific rather than vague.
CATEGORY_RULES: dict[str, str] = {
    "Business Analyst": (
        "Primary focus is requirements gathering, stakeholder communication, "
        "process/gap analysis, or reporting -- without resume-wide systems-"
        "design or technical-elicitation language dominating the summary."
    ),
    "Business Systems Analyst": (
        "BA duties (above) PLUS explicit systems/requirements-elicitation "
        "language: functional specs, systems design, UAT test-case authoring, "
        "or bridging business requirements to a specific software system."
    ),
    "Project Manager": (
        "Primary focus is planning, budget/timeline ownership, team/vendor "
        "coordination, or Agile ceremony facilitation (Scrum Master counts "
        "here) -- the resume is about running the project, not building it."
    ),
    "Java Developer": (
        "Primary focus is hands-on software implementation where Java is the "
        "dominant or sole language named across the experience section."
    ),
    "Full Stack Developer": (
        "Primary focus is hands-on software implementation spanning both "
        "frontend and backend work, or naming multiple languages/frameworks "
        "across the stack rather than one dominant language."
    ),
    "Other / General": (
        "Required catch-all. Use this whenever a resume genuinely doesn't fit "
        "one of the above -- never force-fit a resume into a category it "
        "doesn't belong in just to avoid using this bucket."
    ),
}

CATEGORIES: list[str] = list(CATEGORY_RULES.keys())
OTHER_GENERAL = "Other / General"

# Section 2.4: below this many labeled examples, a category can't train a
# reliable per-class behavior in isolation and gets folded into
# OTHER_GENERAL for classifier purposes (the label itself is preserved in
# the raw label file -- only the classifier's training set is affected).
MIN_CATEGORY_COUNT_FOR_TRAINING = 10


def validate_category(name: str) -> None:
    if name not in CATEGORY_RULES:
        raise ValueError(
            f"'{name}' is not in the fixed taxonomy {CATEGORIES}. "
            f"Per Section 2.1, the taxonomy is fixed before labeling -- "
            f"if a resume genuinely doesn't fit, label it '{OTHER_GENERAL}', "
            f"don't invent a new category."
        )
