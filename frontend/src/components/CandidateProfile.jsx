import { useEffect, useState } from "react";
import ReactDOM from "react-dom";
import { X, Download, Mail, Phone, CalendarDays, GraduationCap, Award, CheckCircle2, XCircle, FileWarning, Tag } from "lucide-react";
import { getCandidateProfile, downloadResume } from "../api";
import ScoreGauge from "./ScoreGauge";
import SkillPill from "./SkillPill";
import Button from "./ui/Button";
import { getConfidenceMeta } from "../utils/confidence";

// Screen 4 -- Candidate Profile (master doc Section 3.6): the only screen
// where unmasked contact info appears, reached only via an explicit
// "View profile" action distinct from "View why" (Section 3.4 interaction
// rule) -- and where the hired/rejected decision (FR-10) lives.
export default function CandidateProfile({
  candidateId,
  jobId,
  onClose,
  feedbackState,
  onFeedback,
  isFeedbackSubmitting = false,
}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [downloadError, setDownloadError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    getCandidateProfile(candidateId, jobId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [candidateId, jobId]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleDownload = async () => {
    setDownloadError(null);
    try {
      await downloadResume(candidateId, data?.resume_filename);
    } catch (e) {
      setDownloadError(e.message);
    }
  };

  return ReactDOM.createPortal(
    <div className="fixed inset-0 z-[80] flex justify-end" role="dialog" aria-modal="true" aria-label="Candidate profile">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-fade-up" onClick={onClose} />
      <div className="relative w-full max-w-lg h-full bg-surface-1 border-l border-line overflow-y-auto animate-fade-up">
        <div className="sticky top-0 bg-surface-1/95 backdrop-blur border-b border-line px-6 py-4 flex items-center justify-between z-10">
          <span className="text-xs font-medium uppercase tracking-wider text-ink-faint">Candidate profile</span>
          <button onClick={onClose} className="text-ink-faint hover:text-ink p-1 rounded-lg hover:bg-surface-2" aria-label="Close profile">
            <X size={18} />
          </button>
        </div>

        {error && <div className="p-6 text-bad text-sm">{error}</div>}
        {!data && !error && (
          <div className="p-6 space-y-4">
            <div className="skeleton h-6 w-2/3 rounded" />
            <div className="skeleton h-4 w-1/2 rounded" />
            <div className="skeleton h-24 w-full rounded-xl" />
          </div>
        )}

        {data && (
          <div className="p-6 space-y-7">
            <div className="flex items-start gap-4">
              {data.composite_score != null && <ScoreGauge score={data.composite_score} confidence={data.confidence} size={56} />}
              <div className="min-w-0">
                <h2 className="text-lg font-semibold font-display text-ink truncate">
                  {data.full_name || data.resume_filename}
                </h2>
                {data.confidence && (
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getConfidenceMeta(data.confidence).colorClass}`}>
                      {getConfidenceMeta(data.confidence).shortLabel}
                    </span>
                    <span className="text-xs text-ink-muted">{data.confidence}</span>
                  </div>
                )}
                {data.predicted_category && (
                  <span
                    className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-surface-3 text-ink-muted border border-line mt-1.5"
                    title="Predicted by the offline-trained resume category classifier"
                  >
                    <Tag size={10} /> {data.predicted_category}
                  </span>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-line bg-surface-2 p-4 space-y-3">
              <div className="flex items-center gap-2.5 text-sm">
                <Mail size={15} className="text-ink-faint shrink-0" />
                <span className="text-ink">{data.email || "No email extracted"}</span>
              </div>
              <div className="flex items-center gap-2.5 text-sm">
                <Phone size={15} className="text-ink-faint shrink-0" />
                <span className="text-ink">{data.phone || "No phone extracted"}</span>
              </div>
              <div className="flex items-center gap-2.5 text-sm">
                <CalendarDays size={15} className="text-ink-faint shrink-0" />
                <span className="text-ink">
                  {data.experience_years != null ? `${data.experience_years} yrs experience (estimated)` : "Experience not detected"}
                </span>
              </div>
              <p className="text-[11px] text-ink-faint pt-1 border-t border-line/60">
                Full contact details are only shown here, after this explicit action — never in the ranked list, search, or export.
              </p>
            </div>

            {data.skills?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-ink mb-2">Extracted skills</h3>
                <div className="flex flex-wrap gap-1.5">
                  {data.skills.map((s) => (
                    <SkillPill key={s} label={s} variant="matched" />
                  ))}
                </div>
              </div>
            )}

            {data.education?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-ink mb-2 flex items-center gap-1.5">
                  <GraduationCap size={15} className="text-ink-faint" /> Education
                </h3>
                <ul className="text-sm text-ink-muted space-y-1 pl-1">
                  {data.education.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}

            {data.certifications?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-ink mb-2 flex items-center gap-1.5">
                  <Award size={15} className="text-ink-faint" /> Certifications
                </h3>
                <ul className="text-sm text-ink-muted space-y-1 pl-1">
                  {data.certifications.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="space-y-2">
              <Button variant="secondary" size="md" icon={Download} onClick={handleDownload} className="w-full">
                Download original resume
              </Button>
              {downloadError && (
                <p className="text-bad text-xs flex items-center gap-1.5">
                  <FileWarning size={13} /> {downloadError}
                </p>
              )}
            </div>

            {onFeedback && (
              <div className="rounded-2xl border border-line bg-surface-2 p-4">
                <h3 className="text-sm font-medium text-ink mb-3">Hiring decision</h3>
                <div className="flex gap-2">
                  <Button
                    variant={feedbackState === "hired" ? "primary" : "secondary"}
                    icon={CheckCircle2}
                    onClick={() => onFeedback("hired")}
                    disabled={isFeedbackSubmitting}
                    className="flex-1"
                    title={feedbackState === "hired" ? "Click to clear decision (currently Hired)" : "Mark as Hired"}
                  >
                    {isFeedbackSubmitting && feedbackState !== "rejected" ? "Saving..." : feedbackState === "hired" ? "Hired" : "Hire"}
                  </Button>
                  <Button
                    variant={feedbackState === "rejected" ? "danger" : "secondary"}
                    icon={XCircle}
                    onClick={() => onFeedback("rejected")}
                    disabled={isFeedbackSubmitting}
                    className="flex-1"
                    title={feedbackState === "rejected" ? "Click to clear decision (currently Rejected)" : "Mark as Rejected"}
                  >
                    {isFeedbackSubmitting && feedbackState === "rejected" ? "Saving..." : feedbackState === "rejected" ? "Rejected" : "Reject"}
                  </Button>
                </div>
                {feedbackState && (
                  <p className="text-xs text-ink-muted mt-3 flex items-center gap-1.5">
                    <CheckCircle2 size={13} className="text-good" />
                    Decision recorded — feeds the scheduled feedback-loop re-weighting step.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
