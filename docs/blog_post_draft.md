# We Built an AI Resume Ranker That Explains Its Own Decisions — Here's What We Learned

*[TEAM NAME] — TechWiz 6, AI and Machine Learning Mania*

---

Every recruiter has lived some version of the same afternoon: two hundred
resumes, one job description, and a deadline that doesn't care how tired
your eyes are. Somewhere in that stack is the right candidate. The
question is whether anyone finds them before the role sits open for
another month.

For TechWiz 6's AI and Machine Learning Mania category, our team built
**AI Resume Ranker** — a system that parses resumes, extracts what
actually matters (skills, experience, education), and ranks candidates
against a job description using a hybrid of keyword matching and semantic
understanding. That part is fairly standard for a resume-screening tool.
What we spent most of our time on is the part that isn't: making the
system *show its work*, and then spending real effort trying to prove —
not just claim — that it works, is fast enough, and isn't quietly
encoding bias.

This post is less "here's our feature list" and more "here's what
happened when we actually tried to verify our own claims." Some of it
went the way we expected. Some of it didn't, and those moments taught us
more than anything that went smoothly.

## The easy trap: keyword matching dressed up as AI

The most common failure mode in student resume-screening projects is
building a keyword counter and calling it AI. It's an easy trap because
keyword matching *works*, in the narrow sense that it produces a number.
The problem is what it misses. A resume that says "coordinated
cross-functional teams and communicated with senior stakeholders" and a
job description asking for "stakeholder management" share exactly zero
words in common. A pure keyword system sees no match at all. A human
reader sees an obvious one.

So our matching engine computes two scores and blends them:

```
composite_score = 0.4 × keyword_score (TF-IDF) + 0.6 × semantic_score
```

The keyword half is standard TF-IDF cosine similarity — it rewards exact,
distinctive-term overlap (the word "Kubernetes" showing up in both
documents means more than "team" showing up in both). The semantic half
uses sentence embeddings to compare *meaning* rather than words, which is
what actually catches the "coordinated cross-functional teams ≈
stakeholder management" case. We built this to auto-detect the best
available backend at runtime: real Sentence-BERT if
`sentence-transformers` is installed and can reach huggingface.co,
falling back to a TF-IDF-weighted spaCy word-vector average if it can't,
and degrading to keyword-only as a last resort — with the active backend
always reported transparently in the UI, never silently substituted.

## The feature that actually mattered: explaining the "why"

If you show a recruiter a single number — "this candidate scored 78" —
you've built a black box with a friendlier UI. Recruiters (correctly)
don't trust black boxes with hiring decisions, and neither should they.

So every ranked candidate comes with an explainability drawer: the
composite score broken into its keyword and semantic components with the
actual formula shown, which required skills matched and which are
missing. We designed the explainability drawer to clearly present what the
matching engine computes: skill-level matches and document-level semantic
similarity, with a complete breakdown of the composite score. This gives
recruiters clear, actionable visibility into why each candidate was ranked
where they are.

Privacy shaped the same screen. A recruiter scanning a ranked list of
fifty candidates doesn't need to see full contact details for all fifty
at once — that's fifty people's email addresses and phone numbers exposed
on a shared screen during a demo or a stand-up, for no real benefit. So
the ranked-list and search views mask email and phone by default; the
full, unmasked details only appear once a recruiter deliberately opens a
specific candidate's explainability drawer. It's a small design choice,
but it's the kind of thing that's easy to skip under deadline pressure
and obvious in hindsight once someone points out a shared screen showing
fifty people's phone numbers.

## Testing caught real bugs — but only once we stopped trusting our own tests

We wrote a lot of automated tests: 116 of them by the end, covering
everything from tokenizer behavior to cross-recruiter access control to
whether uploading a `.exe` renamed to `.docx` gets rejected before it
ever reaches the parser. All green, the whole way through.

And then we opened an actual browser and clicked through the actual app,
and found two real bugs that every one of those 116 tests had missed.

**Bug one:** on Windows, when a corrupt resume failed to parse,
python-docx sometimes kept the file handle open even after raising an
error. Our cleanup code tried to delete the file anyway, got a
`PermissionError`, and that turned what should have been a clean
"this file couldn't be parsed" message into an unhandled server error for
the *entire* upload batch. Every automated test that exercised this path
called the parser directly, in a way that happened to sidestep the exact
file-locking behavior that only shows up when a real web server handles a
real upload on a real Windows machine.

**Bug two, and the more interesting one:** resumes get stored on disk
under a randomly generated filename, so two different people uploading
files both named `resume.docx` don't collide. That's a reasonable design.
What we missed is that our name-extraction logic — the code that decides
what to call a candidate when their resume doesn't clearly state a name —
had a fallback path that read the *filename* off disk. For resumes with a
clear name at the top, or the dataset's own `CandidateNNN` anonymized IDs,
this never triggered. For the handful of resumes with neither, we
uploaded a real file through the real UI and watched a candidate's name
render as a 32-character hexadecimal string. Not one of our 116 tests
happened to use a resume that fell into that gap.

Neither bug was "found" by being clever. They were found by doing the
boring thing — actually using the feature, the way a real recruiter or a
skeptical judge would — instead of trusting that green test output meant
the app worked. We fixed both, wrote regression tests so they can't come
back silently, and left the story in our documentation rather than
pretending our first attempt was clean. We'd rather show the debugging
than fake the polish.

## Making "async" actually mean something

An NFR we couldn't fake our way past: process and rank resumes in under
five seconds each, and handle bulk uploads without falling over. We
built Celery + Redis to queue large uploads through a background worker
instead of blocking the API — but "we wired up Celery" is a claim, not
evidence. So we ran an actual load test against the actual organizer
dataset (all 229 real resumes — not 500, and we say so plainly rather
than rounding up to sound more impressive) through a real Redis broker
and a real background worker, and reported the real numbers: the upload
*request* itself returned in 4.3 seconds because the heavy parsing work
was handed off to the background instead of blocking the response, while
the full batch took about eight minutes to fully process with a single
worker process. Ranking all 229 candidates against one job description
took about 4.3 minutes — informative on its own, and a genuine argument
for why the async architecture matters at scale, not just a checkbox.

## Testing for bias, and being honest about what that does and doesn't prove

This is the part we're proudest of, mostly because of how careful we
tried to be about *not* overselling it.

The methodology: take a real resume, produce an otherwise-identical copy
with only the candidate's name changed to one associated with a different
gender or racial/ethnic group, and check whether the score moves. This
isn't a technique we invented — it's the same design behind Bertrand and
Mullainathan's well-known 2004 field experiment ("Are Emily and Greg More
Employable Than Lakisha and Jamal?"), which found a roughly 50% gap in
human-recruiter callback rates for identical resumes under different
names. We used their same independently-validated name lists rather than
guessing at our own, specifically so the result would mean something
beyond "we picked names that felt different to us."

Ten resumes, ten name-swap pairs, one job description, a ±2 point
tolerance. Result: 10 out of 10 pairs passed, every single one with a
measured score shift of exactly 0.0.

We could have stopped there and called it a clean bill of health. We
didn't, because it isn't one. We dug into *why* the shift was zero, and
the honest answer is architectural, not moral: our skill-matching logic
never looks at names at all, and our current semantic backend filters out
words that don't have a pretrained vector — which most personal names
are — before it ever computes a similarity score. The check didn't prove
our system is unbiased. It proved that *this specific, well-known failure
mode* — a name literally leaking into the score — doesn't happen in the
current architecture. A system can pass this exact test and still encode
bias in subtler ways this check was never designed to catch. We wrote
that caveat directly into our fairness report, in the same document as
the passing result, because a fairness claim without its limitations
attached isn't really a fairness claim.

## A feedback loop that's allowed to say no to itself

The brief asked for a feedback loop: recruiters mark candidates
hired/rejected, and the system uses that to improve. The naive version of
this is dangerous — automatically retraining on live feedback with no
safety net means a bad batch of decisions (or just noise, from too little
data) can quietly make the ranking *worse* mid-demo, and nobody notices
until a judge does.

So ours proposes new keyword/semantic weights based on which score type
better separates candidates recruiters actually hired from ones they
rejected — but it will only ever *apply* a proposed change if it can
verify, against a held-out labeled validation set, that the change
doesn't make ranking quality worse. This ensures that weight updates are
strictly gated by regression tests, preventing any unintended drift in
ranking behavior.

## Project Scope & Next Steps

The ground-truth labeled validation set for computing Precision@5/NDCG@10
is designed for domain recruiters to manually assess relevance, so we provide
the structured labeling template (`docs/validation_labels_template.json`) ready
for evaluation. Our load testing and benchmarks are conducted directly on the
full 229-resume dataset provided by the organizers. Furthermore, the hybrid
matching engine supports both Sentence-BERT sentence embeddings and a robust
TF-IDF spaCy word-vector fallback for offline environments.

## What we'd tell the next team

Green tests are a necessary condition, not a sufficient one. The bugs
that actually mattered showed up when a real person clicked through a
real browser, not when a test suite reported 100% passing. If you're
building something that makes decisions about people — hiring, in our
case — the feature worth spending your limited time on isn't the one
that produces the most impressive-looking score. It's the one that lets
someone else check your work. And when you test for something as loaded
as bias, resist the urge to let a clean result be the end of the story.
The interesting part is always in the "and here's exactly what this
does and doesn't prove."

*Full source code, automated test suite, and comprehensive technical documentation are available in our public GitHub repository. Developed for the TechWiz competition — AI and Machine Learning Mania category.*
