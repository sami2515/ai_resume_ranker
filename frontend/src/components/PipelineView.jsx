import { useEffect, useMemo, useState } from "react";
import {
  UserCheck,
  UserX,
  Star,
  Users,
  Briefcase,
  Search,
  Download,
  UserRound,
  ThumbsUp,
  ThumbsDown,
  Clock,
  ShieldAlert,
  Inbox,
  Filter,
} from "lucide-react";
import ScoreGauge from "./ScoreGauge";
import SkillPill from "./SkillPill";
import CandidateProfile from "./CandidateProfile";
import Button from "./ui/Button";
import EmptyState from "./ui/EmptyState";
import { SkeletonCandidateCard } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";
import { getPipeline, listJobs, submitFeedback, downloadResume } from "../api";
import { getConfidenceMeta } from "../utils/confidence";

export default function PipelineView({ onSelectJob }) {
  const toast = useToast();
  const [pipelineData, setPipelineData] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [activeTab, setActiveTab] = useState("all"); // 'all' | 'hired' | 'rejected' | 'shortlisted' | 'pending'
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [profileCandidateId, setProfileCandidateId] = useState(null);
  const [profileJobId, setProfileJobId] = useState(null);

  const fetchPipeline = async (jobId) => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (jobId) params.job_id = jobId;
      const res = await getPipeline(params);
      setPipelineData(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    listJobs()
      .then((res) => setJobs(res.jobs || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchPipeline(selectedJobId);
  }, [selectedJobId]);

  const handleFeedbackChange = async (matchResultId, decision) => {
    try {
      await submitFeedback(matchResultId, decision);
      toast(`Updated status to ${decision}.`, "success");
      fetchPipeline(selectedJobId);
    } catch (err) {
      toast(err.message, "error");
    }
  };

  const handleDownload = async (candidateId, filename) => {
    try {
      await downloadResume(candidateId, filename);
    } catch (err) {
      toast(err.message, "error");
    }
  };

  const filteredItems = useMemo(() => {
    if (!pipelineData?.items) return [];
    let items = pipelineData.items;

    if (activeTab === "hired") {
      items = items.filter((item) => item.decision === "hired");
    } else if (activeTab === "rejected") {
      items = items.filter((item) => item.decision === "rejected");
    } else if (activeTab === "shortlisted") {
      items = items.filter((item) => item.shortlisted && !item.decision);
    } else if (activeTab === "pending") {
      items = items.filter((item) => !item.decision);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      items = items.filter((item) => {
        const name = item.candidate?.full_name || item.candidate?.resume_filename || "";
        const job = item.job_title || "";
        const skills = (item.matched_skills || []).join(" ");
        return (
          name.toLowerCase().includes(q) ||
          job.toLowerCase().includes(q) ||
          skills.toLowerCase().includes(q)
        );
      });
    }

    return items;
  }, [pipelineData, activeTab, searchQuery]);

  const summary = pipelineData?.summary || {
    hired_count: 0,
    rejected_count: 0,
    shortlisted_count: 0,
    total_reviewed: 0,
    pending_count: 0,
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-display font-bold text-ink">Hiring Pipeline & Decisions</h2>
          <p className="text-sm text-ink-muted mt-1">
            Track and manage candidate decisions (Hired, Rejected, Shortlisted) across all positions.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label htmlFor="pipeline-job-filter" className="text-xs font-medium text-ink-muted flex items-center gap-1.5">
            <Filter size={13} /> Job:
          </label>
          <select
            id="pipeline-job-filter"
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-surface-2 border border-line text-ink text-sm focus:outline-none focus:border-accent"
          >
            <option value="">All Job Postings ({jobs.length})</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <button
          onClick={() => setActiveTab("hired")}
          className={`p-4 rounded-2xl border text-left transition-all ${
            activeTab === "hired"
              ? "bg-good/10 border-good/40 shadow-glow"
              : "bg-surface-2 border-line hover:border-good/30"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-muted">Hired</span>
            <div className="w-7 h-7 rounded-lg bg-good/15 text-good flex items-center justify-center">
              <UserCheck size={15} />
            </div>
          </div>
          <p className="text-2xl font-display font-bold text-good mt-2 tabular-nums">{summary.hired_count}</p>
        </button>

        <button
          onClick={() => setActiveTab("rejected")}
          className={`p-4 rounded-2xl border text-left transition-all ${
            activeTab === "rejected"
              ? "bg-bad/10 border-bad/40 shadow-glow"
              : "bg-surface-2 border-line hover:border-bad/30"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-muted">Rejected</span>
            <div className="w-7 h-7 rounded-lg bg-bad/15 text-bad flex items-center justify-center">
              <UserX size={15} />
            </div>
          </div>
          <p className="text-2xl font-display font-bold text-bad mt-2 tabular-nums">{summary.rejected_count}</p>
        </button>

        <button
          onClick={() => setActiveTab("shortlisted")}
          className={`p-4 rounded-2xl border text-left transition-all ${
            activeTab === "shortlisted"
              ? "bg-gold/10 border-gold/40 shadow-glow"
              : "bg-surface-2 border-line hover:border-gold/30"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-muted">Shortlisted (Unreviewed)</span>
            <div className="w-7 h-7 rounded-lg bg-gold/15 text-gold flex items-center justify-center">
              <Star size={15} />
            </div>
          </div>
          <p className="text-2xl font-display font-bold text-gold mt-2 tabular-nums">{summary.shortlisted_count}</p>
        </button>

        <button
          onClick={() => setActiveTab("all")}
          className={`p-4 rounded-2xl border text-left transition-all ${
            activeTab === "all"
              ? "bg-accent/10 border-accent/40 shadow-glow"
              : "bg-surface-2 border-line hover:border-accent/30"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-ink-muted">Total Reviewed</span>
            <div className="w-7 h-7 rounded-lg bg-accent/15 text-accent flex items-center justify-center">
              <Users size={15} />
            </div>
          </div>
          <p className="text-2xl font-display font-bold text-ink mt-2 tabular-nums">{summary.total_reviewed}</p>
        </button>
      </div>

      {/* Tabs & Search Bar */}
      <div className="bg-surface-2 border border-line rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex gap-1.5 flex-wrap">
          {[
            { id: "all", label: "All Candidates", count: pipelineData?.items?.length || 0 },
            { id: "hired", label: "Hired", count: summary.hired_count, color: "text-good" },
            { id: "rejected", label: "Rejected", count: summary.rejected_count, color: "text-bad" },
            { id: "shortlisted", label: "Shortlisted", count: summary.shortlisted_count, color: "text-gold" },
            { id: "pending", label: "Pending", count: summary.pending_count },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                activeTab === tab.id
                  ? "bg-accent text-white shadow-glow"
                  : "text-ink-muted hover:text-ink hover:bg-surface-3"
              }`}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>

        <div className="relative min-w-[220px] flex-1 sm:flex-none">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search candidate, job, skill..."
            className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-surface-1 border border-line text-ink text-xs placeholder-ink-faint focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      {/* Error state */}
      {error && (
        <EmptyState icon={ShieldAlert} tone="bad" title="Couldn't load pipeline" description={error} />
      )}

      {/* Loading state */}
      {loading && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <SkeletonCandidateCard key={i} />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && filteredItems.length === 0 && (
        <EmptyState
          icon={Inbox}
          title={
            activeTab === "hired"
              ? "No hired candidates yet"
              : activeTab === "rejected"
              ? "No rejected candidates yet"
              : activeTab === "shortlisted"
              ? "No unreviewed shortlisted candidates"
              : "No candidates found"
          }
          description={
            activeTab === "hired"
              ? "Mark candidates as 'Hire' on the Rankings page to populate your hired roster."
              : activeTab === "rejected"
              ? "Mark candidates as 'Reject' on the Rankings page to log recruiter decisions."
              : activeTab === "shortlisted"
              ? "Candidates scoring above 80% appear here automatically after ranking."
              : "Upload resumes and run AI ranking first, then mark candidates as Hired or Rejected here."
          }
          action={
            activeTab === "all" || activeTab === "pending" ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => window.dispatchEvent(new CustomEvent("navigate:tab", { detail: "upload" }))}
              >
                Go to Upload & Rank
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => window.dispatchEvent(new CustomEvent("navigate:tab", { detail: "results" }))}
              >
                View Rankings
              </Button>
            )
          }
        />
      )}

      {/* Items List */}
      {!loading && !error && filteredItems.length > 0 && (
        <div className="space-y-3">
          {filteredItems.map((item) => {
            const candidate = item.candidate || {};
            const isHired = item.decision === "hired";
            const isRejected = item.decision === "rejected";

            return (
              <div
                key={item.match_result_id}
                className={`bg-surface-2 border rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row gap-4 sm:items-center transition-all ${
                  isHired
                    ? "border-good/40 bg-good/[0.02]"
                    : isRejected
                    ? "border-bad/30 bg-bad/[0.01]"
                    : item.shortlisted
                    ? "border-gold/30"
                    : "border-line"
                }`}
              >
                <div className="flex items-center gap-3 shrink-0">
                  <ScoreGauge score={item.composite_score} confidence={item.confidence} />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      onClick={() => {
                        setProfileCandidateId(item.candidate_id);
                        setProfileJobId(item.job_id);
                      }}
                      className="text-ink font-display font-semibold text-[15px] hover:text-accent transition-colors text-left"
                    >
                      {candidate.full_name || candidate.resume_filename}
                    </button>

                    {/* Status Pill */}
                    {isHired && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-good/15 text-good border border-good/40">
                        <UserCheck size={11} /> Hired
                      </span>
                    )}
                    {isRejected && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-bad/15 text-bad border border-bad/40">
                        <UserX size={11} /> Rejected
                      </span>
                    )}
                    {!isHired && !isRejected && item.shortlisted && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-gold/15 text-gold border border-gold/40">
                        <Star size={11} /> Shortlisted
                      </span>
                    )}

                    {/* Job Link */}
                    <span className="inline-flex items-center gap-1 text-xs text-ink-muted bg-surface-3 px-2 py-0.5 rounded-lg border border-line">
                      <Briefcase size={11} /> {item.job_title}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-ink-muted mt-1">
                    <span>Exp: {candidate.experience_years || 0} yrs</span>
                    <span className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getConfidenceMeta(item.confidence).colorClass}`}>
                      {getConfidenceMeta(item.confidence).shortLabel}
                    </span>
                    {item.decision_date && (
                      <>
                        <span>•</span>
                        <span className="flex items-center gap-1 text-ink-faint">
                          <Clock size={11} /> {new Date(item.decision_date).toLocaleDateString()}
                        </span>
                      </>
                    )}
                  </div>

                  {/* Skills */}
                  <div className="flex flex-wrap gap-1.5 mt-2.5">
                    {(item.matched_skills || []).slice(0, 5).map((s) => (
                      <SkillPill key={s} label={s} variant="matched" />
                    ))}
                    {(item.matched_skills || []).length > 5 && (
                      <span className="text-xs text-ink-faint self-center">
                        +{item.matched_skills.length - 5} more
                      </span>
                    )}
                  </div>

                  {/* Actions Bar */}
                  <div className="flex flex-wrap items-center gap-2 mt-3.5 pt-2 border-t border-line/50">
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={UserRound}
                      onClick={() => {
                        setProfileCandidateId(item.candidate_id);
                        setProfileJobId(item.job_id);
                      }}
                    >
                      Full Profile
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={Download}
                      onClick={() => handleDownload(item.candidate_id, candidate.resume_filename)}
                    >
                      Resume
                    </Button>
                    {onSelectJob && (
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={Briefcase}
                        onClick={() => onSelectJob(item.job_id)}
                      >
                        View in Ranking
                      </Button>
                    )}

                    {/* Quick Decision Toggles */}
                    <div className="sm:ml-auto flex gap-1.5 w-full sm:w-auto pt-1 sm:pt-0">
                      <button
                        onClick={() => handleFeedbackChange(item.match_result_id, "hired")}
                        className={`flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors ${
                          isHired
                            ? "bg-good/20 text-good border-good/50 font-semibold"
                            : "border-line text-ink-muted hover:border-good/40 hover:text-good"
                        }`}
                      >
                        <ThumbsUp size={12} /> {isHired ? "Hired" : "Hire"}
                      </button>
                      <button
                        onClick={() => handleFeedbackChange(item.match_result_id, "rejected")}
                        className={`flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg border transition-colors ${
                          isRejected
                            ? "bg-bad/20 text-bad border-bad/50 font-semibold"
                            : "border-line text-ink-muted hover:border-bad/40 hover:text-bad"
                        }`}
                      >
                        <ThumbsDown size={12} /> {isRejected ? "Rejected" : "Reject"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Candidate Profile Modal */}
      {profileCandidateId && (
        <CandidateProfile
          candidateId={profileCandidateId}
          jobId={profileJobId}
          onClose={() => {
            setProfileCandidateId(null);
            setProfileJobId(null);
          }}
        />
      )}
    </div>
  );
}
