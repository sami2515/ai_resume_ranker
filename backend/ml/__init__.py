"""
Model training & validation package (ML Training Master Plan Section 1).

Everything under nlp_pipeline/ runs online, per-request, inside the Flask
app. Everything under here runs offline, by a team member, on demand --
labeling, cross-validated training, calibration, and experiment logging.
Nothing in this package is imported by the live app except ml.classify,
which loads a frozen artifact this package's training script produces (and
returns None gracefully if that artifact doesn't exist yet).
"""
