import { Crown, Download, Eye, Trash2, ThumbsUp, ThumbsDown, UserRound, Tag, Loader2 } from "lucide-react";
import { useState } from "react";
import ScoreGauge from "./ScoreGauge";
import SkillPill from "./SkillPill";
import Button from "./ui/Button";
import { useToast } from "./ui/Toast";
import { downloadResume } from "../api";
import { getConfidenceMeta } from "../utils/confidence";

export default function CandidateCard({
  result,
  onExplain,
  onProfile,
  onFeedback,
  onDeleteRequest,
  feedbackState,
  isFeedbackSubmitting = false,
}) {
  const { candidate, rank_position, composite_score, confidence, matched_skills, shortlisted } = result;
  const toast = useToast();
  const isTopRank = rank_position === 1;
  const [showActions, setShowActions] = useState(false);

  const handleDownload = async () => {
    try {
      await downloadResume(candidate.id, candidate.resume_filename);
    } catch (e) {
      toast(e.message, "error");
    }
  };

  const confMeta = getConfidenceMeta(confidence);

  return (
    <div
      className={`group relative bg-surface-2 border rounded-2xl p-4 sm:p-5 transition-all duration-200 hover:shadow-panel hover:border-accent/30 ${
        isTopRank
          ? "border-gold/50 shadow-glow-gold ring-1 ring-gold/20"
          : feedbackState === "hired"
          ? "border-good/40"
          : feedbackState === "rejected"
          ? "border-bad/30 opacity-80"
          : "border-line"
      }`}
    >
      {/* ── Top Row: Rank + Gauge + Name + Actions ── */}
      <div className="flex items-start gap-3 sm:gap-4">
        {/* Rank + Score Gauge */}
        <div className="flex flex-col items-center gap-1 shrink-0">
          {isTopRank && (
            <Crown size={14} className="text-gold drop-shadow-sm" aria-hidden="true" />
          )}
          <span className="text-ink-faint font-mono text-[11px]">#{rank_position}</span>
          <ScoreGauge score={composite_score} confidence={confidence} size={60} />
        </div>

        {/* Name + Confidence + Skills */}
        <div className="flex-1 min-w-0">
          {/* Name row */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap min-w-0">
              <button
                onClick={onExplain}
                className="text-white font-display font-semibold text-[15px] truncate hover:text-blue-400 transition-colors text-left max-w-[180px] sm:max-w-none"
              >
                {candidate.full_name || candidate.resume_filename}
              </button>

              {/* Status badges */}
              {shortlisted && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-accent/15 text-blue-400 border border-accent/30 shrink-0">
                  ⭐ Shortlisted
                </span>
              )}
              {feedbackState === "hired" && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-good/15 text-good border border-good/30 shrink-0">
                  ✓ Hired
                </span>
              )}
              {feedbackState === "rejected" && (
                <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-bad/15 text-bad border border-bad/30 shrink-0">
                  ✕ Rejected
                </span>
              )}
            </div>

            {/* Delete — safely separated in top-right corner */}
            <button
              onClick={onDeleteRequest}
              className="shrink-0 p-1.5 rounded-lg text-ink-faint hover:text-bad hover:bg-bad/10 transition-colors opacity-0 group-hover:opacity-100"
              title="Delete candidate"
              aria-label="Delete candidate"
            >
              <Trash2 size={13} />
            </button>
          </div>

          {/* Confidence badge */}
          <div className="mt-1.5 flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full border ${confMeta.colorClass}`}>
              {confMeta.shortLabel}
            </span>
            {candidate.experience_years > 0 && (
              <span className="text-[10px] text-ink-muted">
                {candidate.experience_years.toFixed(1)} yrs exp
              </span>
            )}
            {candidate.predicted_category && (
              <span
                className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-surface-3 text-ink-muted border border-line"
                title="Predicted role category"
              >
                <Tag size={9} /> {candidate.predicted_category}
              </span>
            )}
          </div>

          {/* Matched Skills */}
          <div className="flex flex-wrap gap-1.5 mt-2.5">
            {matched_skills.slice(0, 5).map((s) => (
              <SkillPill key={s} label={s} variant="matched" />
            ))}
            {matched_skills.length > 5 && (
              <span className="text-[11px] text-ink-faint self-center">+{matched_skills.length - 5} more</span>
            )}
            {matched_skills.length === 0 && (
              <span className="text-[11px] text-ink-faint italic">No matched skills detected</span>
            )}
          </div>
        </div>
      </div>

      {/* ── Bottom Action Bar ───────────────────────────────────────────── */}
      <div className="mt-4 flex items-center justify-between gap-2 pt-3 border-t border-line/60">
        {/* Left: View actions */}
        <div className="flex items-center gap-1.5">
          <Button size="sm" variant="ghost" icon={Eye} onClick={onExplain} title="See how AI computed this match score">
            AI Explanation
          </Button>
          <Button size="sm" variant="ghost" icon={UserRound} onClick={onProfile} title="View full candidate profile & contact info">
            Profile
          </Button>
          <Button size="sm" variant="ghost" icon={Download} onClick={handleDownload} title="Download original resume file">
            Resume
          </Button>
        </div>

        {/* Right: Hire / Reject decisions */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => onFeedback("hired")}
            disabled={isFeedbackSubmitting}
            aria-pressed={feedbackState === "hired"}
            title={feedbackState === "hired" ? "Click to clear decision (currently Hired)" : "Mark candidate as Hired"}
            className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl border transition-all ${
              isFeedbackSubmitting
                ? "opacity-50 cursor-not-allowed border-line text-ink-faint"
                : feedbackState === "hired"
                ? "bg-good/20 text-good border-good/50 shadow-sm hover:bg-good/30"
                : "border-line text-ink-muted hover:border-good/40 hover:text-good hover:bg-good/5"
            }`}
          >
            {isFeedbackSubmitting && feedbackState !== "rejected" ? (
              <Loader2 size={12} className="animate-spin text-good" />
            ) : (
              <ThumbsUp size={12} />
            )}
            {feedbackState === "hired" ? "Hired" : "Hire"}
          </button>

          <button
            onClick={() => onFeedback("rejected")}
            disabled={isFeedbackSubmitting}
            aria-pressed={feedbackState === "rejected"}
            title={feedbackState === "rejected" ? "Click to clear decision (currently Rejected)" : "Mark candidate as Rejected"}
            className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl border transition-all ${
              isFeedbackSubmitting
                ? "opacity-50 cursor-not-allowed border-line text-ink-faint"
                : feedbackState === "rejected"
                ? "bg-bad/20 text-bad border-bad/50 shadow-sm hover:bg-bad/30"
                : "border-line text-ink-muted hover:border-bad/40 hover:text-bad hover:bg-bad/5"
            }`}
          >
            {isFeedbackSubmitting && feedbackState === "rejected" ? (
              <Loader2 size={12} className="animate-spin text-bad" />
            ) : (
              <ThumbsDown size={12} />
            )}
            {feedbackState === "rejected" ? "Rejected" : "Reject"}
          </button>
        </div>
      </div>
    </div>
  );
}
