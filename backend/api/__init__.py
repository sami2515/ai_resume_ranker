from .auth import auth_bp
from .resumes import resumes_bp
from .jobs import jobs_bp
from .candidates import candidates_bp
from .results import results_bp
from .feedback import feedback_bp
from .export import export_bp
from .analytics import analytics_bp

ALL_BLUEPRINTS = [auth_bp, resumes_bp, jobs_bp, candidates_bp, results_bp, feedback_bp, export_bp, analytics_bp]
