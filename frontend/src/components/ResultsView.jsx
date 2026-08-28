import { useEffect, useMemo, useState } from "react";
import {
  FileSpreadsheet,
  FileText,
  SearchX,
  ShieldAlert,
  TriangleAlert,
  Briefcase,
  UserCheck,
  UserX,
  Star,
} from "lucide-react";
import CandidateCard from "./CandidateCard";
import ExplainabilityDrawer from "./ExplainabilityDrawer";
import CandidateProfile from "./CandidateProfile";
import SearchFilterBar from "./SearchFilterBar";
import Button from "./ui/Button";
import ConfirmDialog from "./ui/ConfirmDialog";
import EmptyState from "./ui/EmptyState";
import { SkeletonCandidateCard } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";
import { getJobResults, listJobs, submitFeedback, exportJob, deleteCandidate } from "../api";

export default function ResultsView({ jobId, onSwitchJob }) {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [allJobs, setAllJobs] = useState([]);
  const [error, setError] = useState(null);
  const [explainCandidateId, setExplainCandidateId] = useState(null);
  const [profileCandidateId, setProfileCandidateId] = useState(null);
  const [feedback, setFeedback] = useState({}); // matchResultId -> "hired" | "rejected"
  const [statusFilter, setStatusFilter] = useState("all"); // 'all' | 'shortlisted' | 'hired' | 'rejected' | 'pending'
  const [filters, setFilters] = useState({ keyword: "", minExperience: 0, minScore: 0, skills: [] });
  const [pendingDelete, setPendingDelete] = useState(null);
  const [exporting, setExporting] = useState(null);

  useEffect(() => {
    listJobs()
      .then((res) => setAllJobs(res.jobs || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setData(null);
    setError(null);
    getJobResults(jobId)
      .then((res) => {
        setData(res);
        const initialFeedback = {};
        (res.results || []).forEach((r) => {
          if (r.decision) {
            initialFeedback[r.id] = r.decision;
          }
        });
        setFeedback(initialFeedback);
      })
      .catch((e) => setError(e.message));
  }, [jobId]);

  const maxExperience = useMemo(() => {
    if (!data) return 10;
    return Math.max(...data.results.map((r) => r.candidate.experience_years || 0), 1);
  }, [data]);

  const availableSkills = useMemo(() => {
    if (!data) return [];
    const set = new Set();
    data.results.forEach((r) => r.matched_skills.forEach((s) => set.add(s)));
    return Array.from(set).sort();
  }, [data]);

  const filteredResults = useMemo(() => {
    if (!data) return [];
    const kw = filters.keyword.trim().toLowerCase();
    return data.results.filter((r) => {
      // Status filter
      const currentDecision = feedback[r.id];
      if (statusFilter === "hired" && currentDecision !== "hired") return false;
      if (statusFilter === "rejected" && currentDecision !== "rejected") return false;
      if (statusFilter === "shortlisted" && !r.shortlisted) return false;
      if (statusFilter === "pending" && currentDecision) return false;

      // Score and Experience filters
      if (r.composite_score < filters.minScore) return false;
      if ((r.candidate.experience_years || 0) < filters.minExperience) return false;
      if (filters.skills.length > 0 && !filters.skills.every((s) => r.matched_skills.includes(s))) return false;
      if (kw) {
        const haystack = [r.candidate.full_name, r.candidate.resume_filename, ...(r.candidate.skills || [])]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(kw)) return false;
      }
      return true;
    });
  }, [data, filters, statusFilter, feedback]);

  const [submittingFeedbackIds, setSubmittingFeedbackIds] = useState(new Set());

  const handleFeedback = async (matchResultId, targetDecision) => {
    // Validation: prevent rapid double-clicks while request is in-flight
    if (submittingFeedbackIds.has(matchResultId)) return;

    const currentDecision = feedback[matchResultId];
    // Toggle logic: clicking the active decision again un-marks it back to 'unreviewed'
    const newDecision = currentDecision === targetDecision ? "unreviewed" : targetDecision;

    setSubmittingFeedbackIds((prev) => new Set(prev).add(matchResultId));
    setFeedback((prev) => ({
      ...prev,
      [matchResultId]: newDecision === "unreviewed" ? undefined : newDecision,
    }));

    try {
      await submitFeedback(matchResultId, newDecision);
      if (newDecision === "unreviewed") {
        toast("Decision cleared. Candidate returned to unreviewed pool.", "info");
      } else {
        toast(
          `Marked candidate as ${newDecision.toUpperCase()}. Decision logged to feedback loop.`,
          "success"
        );
      }
    } catch (e) {
      // Revert on error
      setFeedback((prev) => ({ ...prev, [matchResultId]: currentDecision }));
      toast(`Failed to save decision: ${e.message}`, "error");
    } finally {
      setSubmittingFeedbackIds((prev) => {
        const next = new Set(prev);
        next.delete(matchResultId);
        return next;
      });
    }
  };

  const handleExport = async (format) => {
    setExporting(format);
    try {
      await exportJob(jobId, format);
      toast(`Exported ${filteredResults.length} candidate${filteredResults.length === 1 ? "" : "s"} to ${format.toUpperCase()}.`, "success");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setExporting(null);
    }
  };

  const confirmDelete = async () => {
    const candidateId = pendingDelete;
    setPendingDelete(null);
    try {
      await deleteCandidate(candidateId);
      setData((prev) => {
        const remaining = prev.results
          .filter((r) => r.candidate_id !== candidateId)
          .map((r, i) => ({ ...r, rank_position: i + 1 }));
        return { ...prev, results: remaining, total: remaining.length };
      });
      toast("Candidate data deleted.", "success");
    } catch (e) {
      toast(e.message, "error");
    }
  };

  if (error)
    return (
      <div className="max-w-3xl mx-auto">
        <EmptyState icon={ShieldAlert} tone="bad" title="Couldn't load results" description={error} />
      </div>
    );

  if (!data) {
    return (
      <div className="max-w-3xl mx-auto space-y-4" aria-live="polite" aria-busy="true">
        <div className="skeleton h-9 w-2/3 rounded-lg" />
        <div className="skeleton h-24 w-full rounded-2xl" />
        {[...Array(4)].map((_, i) => (
          <SkeletonCandidateCard key={i} />
        ))}
      </div>
    );
  }

  const sparseRequirements = (data.jd.required_skills || []).length === 0;
  const hiredCount = Object.values(feedback).filter((d) => d === "hired").length;
  const rejectedCount = Object.values(feedback).filter((d) => d === "rejected").length;
  const shortlistedCount = data.results.filter((r) => r.shortlisted).length;

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Top Header with Job Selector & Export Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-surface-2 border border-line rounded-2xl p-5">
        <div className="flex-1 min-w-[240px]">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-ink-muted uppercase tracking-wider font-semibold">Active Ranking:</span>
            {allJobs.length > 1 && onSwitchJob && (
              <select
                value={jobId}
                onChange={(e) => onSwitchJob(Number(e.target.value))}
                className="text-xs px-2 py-0.5 rounded-lg bg-surface-1 border border-line text-accent font-semibold focus:outline-none"
              >
                {allJobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    Switch: {j.title}
                  </option>
                ))}
              </select>
            )}
          </div>
          <h2 className="text-lg font-display font-bold text-ink">{data.jd.title}</h2>
          <p className="text-xs text-ink-muted mt-0.5">
            {data.total} candidate{data.total === 1 ? "" : "s"} evaluated • Category: {data.jd.category || "General"}
          </p>
        </div>

        <div className="flex gap-2">
          <Button variant="secondary" size="sm" icon={FileSpreadsheet} loading={exporting === "excel"} onClick={() => handleExport("excel")} title={`Export ${filteredResults.length} candidates to Excel`}>
            Excel ({filteredResults.length})
          </Button>
          <Button variant="secondary" size="sm" icon={FileText} loading={exporting === "pdf"} onClick={() => handleExport("pdf")} title={`Export ${filteredResults.length} candidates to PDF`}>
            PDF ({filteredResults.length})
          </Button>
        </div>
      </div>

      {sparseRequirements && (
        <div className="flex items-start gap-3 p-4 rounded-2xl bg-warn/10 border border-warn/30 text-sm text-warn">
          <TriangleAlert size={17} className="shrink-0 mt-0.5" />
          <p>
            Few requirements detected in this job description — review extraction. Ranking still ran on whatever text similarity is available, but scores may be less reliable than usual.
          </p>
        </div>
      )}

      {/* Quick Status Filter Tabs */}
      <div className="flex gap-1.5 flex-wrap">
        {[
          { id: "all", label: "All Candidates", count: data.total },
          { id: "shortlisted", label: "Shortlisted", count: shortlistedCount, icon: Star, color: "text-gold" },
          { id: "hired", label: "Hired", count: hiredCount, icon: UserCheck, color: "text-good" },
          { id: "rejected", label: "Rejected", count: rejectedCount, icon: UserX, color: "text-bad" },
          { id: "pending", label: "Unreviewed", count: Math.max(data.total - hiredCount - rejectedCount, 0) },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setStatusFilter(tab.id)}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
              statusFilter === tab.id
                ? "bg-accent text-white shadow-glow"
                : "bg-surface-2 border border-line text-ink-muted hover:text-ink"
            }`}
          >
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      <SearchFilterBar filters={filters} onChange={setFilters} maxExperience={maxExperience} availableSkills={availableSkills} />

      {data.no_strong_matches && (
        <div className="bg-surface-2 border border-warn/40 rounded-2xl p-5 space-y-4">
          {/* Header */}
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-warn/15 border border-warn/30 flex items-center justify-center shrink-0">
              <TriangleAlert size={18} className="text-warn" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">No Strong Matches Found</h3>
              <p className="text-xs text-ink-muted mt-0.5">
                All candidates scored below the shortlist threshold for <strong className="text-white">{data.jd.title}</strong>.
                Rankings are still shown below — here's how to improve results:
              </p>
            </div>
          </div>

          {/* Tips Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {[
              {
                icon: "📝",
                title: "Enrich Job Description",
                desc: "Add specific skills like Python, SQL, Excel, or role-specific tools to your JD text for better semantic matching.",
              },
              {
                icon: "📄",
                title: "Check Resume Quality",
                desc: "Resumes with minimal text or image-based CVs may not parse correctly. Use text-based .docx or .pdf files.",
              },
              {
                icon: "🔄",
                title: "Re-rank with Broader JD",
                desc: "Go back to Upload tab and try a more detailed JD with at least 50+ words describing the role requirements.",
              },
            ].map((tip) => (
              <div key={tip.title} className="bg-surface-1/80 border border-line/60 rounded-xl p-3 text-xs space-y-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-base">{tip.icon}</span>
                  <span className="font-semibold text-white">{tip.title}</span>
                </div>
                <p className="text-ink-muted leading-relaxed">{tip.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!data.no_strong_matches && filteredResults.length === 0 && (
        <EmptyState
          icon={SearchX}
          title="No results for this filter"
          description="Nothing in the ranked list matches the current filters."
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setStatusFilter("all");
                setFilters({ keyword: "", minExperience: 0, minScore: 0, skills: [] });
              }}
            >
              Clear filters
            </Button>
          }
        />
      )}

      <div className="space-y-3">
        {filteredResults.map((r) => (
          <CandidateCard
            key={r.id}
            result={r}
            feedbackState={feedback[r.id]}
            isFeedbackSubmitting={submittingFeedbackIds.has(r.id)}
            onExplain={() => setExplainCandidateId(r.candidate_id)}
            onProfile={() => setProfileCandidateId(r.candidate_id)}
            onFeedback={(decision) => handleFeedback(r.id, decision)}
            onDeleteRequest={() => setPendingDelete(r.candidate_id)}
          />
        ))}
      </div>

      {explainCandidateId && (
        <ExplainabilityDrawer
          candidateId={explainCandidateId}
          jobId={jobId}
          onClose={() => setExplainCandidateId(null)}
          onOpenProfile={() => {
            setProfileCandidateId(explainCandidateId);
            setExplainCandidateId(null);
          }}
        />
      )}

      {profileCandidateId &&
        (() => {
          const match = data.results.find((r) => r.candidate_id === profileCandidateId);
          return (
            <CandidateProfile
              candidateId={profileCandidateId}
              jobId={jobId}
              onClose={() => setProfileCandidateId(null)}
              feedbackState={match ? feedback[match.id] : undefined}
              isFeedbackSubmitting={match ? submittingFeedbackIds.has(match.id) : false}
              onFeedback={match ? (decision) => handleFeedback(match.id, decision) : undefined}
            />
          );
        })()}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this candidate's data?"
        description="This removes their resume, extracted profile, and all ranking history. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />

      {/* Bottom CTA — prevent dead-end after reviewing all candidates */}
      {filteredResults.length > 0 && (
        <div className="mt-2 flex items-center justify-center gap-3 py-5 border-t border-line/40 text-center">
          <span className="text-xs text-ink-faint">Want to add more candidates?</span>
          <button
            onClick={() => {
              // Dispatch a custom event to navigate back to upload tab
              window.dispatchEvent(new CustomEvent("navigate:tab", { detail: "upload" }));
            }}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 underline underline-offset-2 transition-colors flex items-center gap-1"
          >
            ← Upload more resumes & re-rank
          </button>
        </div>
      )}
    </div>
  );
}
