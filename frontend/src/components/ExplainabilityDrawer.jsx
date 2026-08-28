import { useEffect, useState } from "react";
import ReactDOM from "react-dom";
import { X, UserRound, ChevronRight } from "lucide-react";
import SkillPill from "./SkillPill";
import Button from "./ui/Button";
import { explainCandidate } from "../api";
import { getConfidenceMeta } from "../utils/confidence";

// Explainability Drawer: Shows candidate profile details, skill-level matched/missing
// evidence, and composite score computation breakdown.

function ScoreBar({ label, value, colorClass }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-ink-muted mb-1.5">
        <span>{label}</span>
        <span className="font-mono tabular-nums">{value.toFixed(1)}</span>
      </div>
      <div className="h-2 rounded-full bg-surface-3 overflow-hidden">
        <div
          className={`h-full rounded-full ${colorClass}`}
          style={{ width: `${Math.min(value, 100)}%`, transition: "width 0.6s cubic-bezier(0.16,1,0.3,1)" }}
        />
      </div>
    </div>
  );
}

export default function ExplainabilityDrawer({ candidateId, jobId, onClose, onOpenProfile }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    explainCandidate(candidateId, jobId)
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

  return ReactDOM.createPortal(
    <div className="fixed inset-0 z-[70] flex justify-end" role="dialog" aria-modal="true" aria-label="Explainability breakdown">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-fade-up" onClick={onClose} />
      <div className="relative w-full max-w-md h-full bg-surface-1 border-l border-line overflow-y-auto animate-fade-up">
        <div className="sticky top-0 bg-surface-1/95 backdrop-blur border-b border-line px-6 py-4 flex items-center justify-between z-10">
          <span className="text-xs font-medium uppercase tracking-wider text-ink-faint">Why this score</span>
          <button onClick={onClose} className="text-ink-faint hover:text-ink p-1 rounded-lg hover:bg-surface-2" aria-label="Close explanation">
            <X size={18} />
          </button>
        </div>

        {error && <p className="text-bad p-6">{error}</p>}
        {!data && !error && (
          <div className="p-6 space-y-4">
            <div className="skeleton h-6 w-1/2 rounded" />
            <div className="skeleton h-28 w-full rounded-xl" />
            <div className="skeleton h-4 w-1/3 rounded" />
          </div>
        )}

        {data && (
          <div className="p-6 space-y-6">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-display font-semibold text-ink truncate">
                {data.candidate.full_name || data.candidate.resume_filename}
              </h2>
              <Button size="sm" variant="secondary" icon={UserRound} onClick={onOpenProfile} className="shrink-0">
                Profile <ChevronRight size={13} />
              </Button>
            </div>

            <div className="p-4 rounded-2xl bg-surface-2 border border-line space-y-3.5">
              <div className="flex items-baseline justify-between">
                <span className="text-ink-muted text-sm">Composite score</span>
                <span className="text-2xl font-display font-semibold text-ink tabular-nums">{data.composite_score}</span>
              </div>
              <div className="flex items-center gap-2 -mt-2">
                <span className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getConfidenceMeta(data.confidence).colorClass}`}>
                  {getConfidenceMeta(data.confidence).shortLabel}
                </span>
                <span className="text-xs text-ink-muted">{data.confidence}</span>
              </div>
              <ScoreBar label="Keyword score (TF-IDF)" value={data.keyword_score} colorClass="bg-sky-400" />
              <ScoreBar label="Semantic score (meaning match)" value={data.semantic_score} colorClass="bg-accent" />
              <p className="text-xs text-ink-faint font-mono pt-1 border-t border-line/60">{data.formula}</p>
            </div>

            <div>
              <h3 className="text-sm font-medium text-ink mb-2">
                Matched requirements ({data.matched_skills.length})
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {data.matched_skills.length > 0 ? (
                  data.matched_skills.map((s) => <SkillPill key={s} label={s} variant="matched" />)
                ) : (
                  <p className="text-sm text-ink-faint">No direct skill matches found.</p>
                )}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-medium text-ink mb-2">
                Missing requirements ({data.missing_skills.length})
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {data.missing_skills.length > 0 ? (
                  data.missing_skills.map((s) => <SkillPill key={s} label={s} variant="missing" />)
                ) : (
                  <p className="text-sm text-ink-faint">No missing requirements — full skill coverage.</p>
                )}
              </div>
            </div>

            <p className="text-xs text-ink-faint border-t border-line pt-4 leading-relaxed">
              Matched/missing requirements are skill-level (gazetteer-based), not
              phrase-by-phrase evidence linking. The semantic score reflects
              overall document-level meaning similarity between the resume and
              the job description. Contact details and education/certifications
              are on this candidate's profile.
            </p>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
