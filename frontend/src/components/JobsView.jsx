import { useEffect, useState, useRef } from "react";
import ReactDOM from "react-dom";
import {
  Briefcase,
  Plus,
  Users,
  Trophy,
  UserCheck,
  UserX,
  Play,
  Pause,
  Trash2,
  FileText,
  Upload,
  Calendar,
  Layers,
  ArrowRight,
  ShieldAlert,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import Button from "./ui/Button";
import SkillPill from "./SkillPill";
import EmptyState from "./ui/EmptyState";
import { useToast } from "./ui/Toast";
import { listJobs, createJob, createJobWithFile, rankJob, updateJobStatus, deleteJob } from "../api";

export default function JobsView({ onSelectJob, onNavigateUpload }) {
  const toast = useToast();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [rankingJobId, setRankingJobId] = useState(null);

  // Modal form state
  const [title, setTitle] = useState("");
  const [mode, setMode] = useState("text"); // 'text' | 'file'
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [touchedTitle, setTouchedTitle] = useState(false);
  const [touchedText, setTouchedText] = useState(false);
  const fileInputRef = useRef(null);

  const fetchJobs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listJobs();
      setJobs(res.jobs || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleCreateJob = async (e) => {
    e.preventDefault();
    setTouchedTitle(true);
    setTouchedText(true);
    if (!title.trim()) {
      return;
    }

    setCreating(true);
    try {
      let created;
      if (mode === "file") {
        if (!file) {
          toast("Please select a .docx or .pdf JD file", "error");
          setCreating(false);
          return;
        }
        created = await createJobWithFile({ title: title.trim(), file });
      } else {
        if (!text.trim()) {
          toast("Job description text is required", "error");
          setCreating(false);
          return;
        }
        created = await createJob({ title: title.trim(), text: text.trim() });
      }

      toast(`Job "${created.title}" created successfully!`, "success");
      setShowModal(false);
      setTitle("");
      setText("");
      setFile(null);
      setTouchedTitle(false);
      setTouchedText(false);
      fetchJobs();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setCreating(false);
    }
  };

  const handleReRank = async (jobId, jobTitle) => {
    setRankingJobId(jobId);
    try {
      const res = await rankJob(jobId);
      toast(`Re-ranked ${res.ranked} candidates against "${jobTitle}".`, "success");
      fetchJobs();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setRankingJobId(null);
    }
  };

  const handleToggleStatus = async (jobId, currentStatus, title) => {
    const nextStatus = currentStatus === "paused" ? "active" : "paused";
    try {
      await updateJobStatus(jobId, nextStatus);
      toast(
        `Position "${title}" is now ${nextStatus === "paused" ? "Paused (hiring on hold)" : "Active"}.`,
        "success"
      );
      fetchJobs();
    } catch (err) {
      toast(err.message, "error");
    }
  };

  const handleDeleteJob = async (jobId, title) => {
    if (!window.confirm(`Are you sure you want to delete "${title}"? This will remove its ranking results.`)) {
      return;
    }
    try {
      await deleteJob(jobId);
      toast(`Job "${title}" deleted successfully.`, "success");
      fetchJobs();
    } catch (err) {
      toast(err.message, "error");
    }
  };

  const totalCandidatesRanked = jobs.reduce((sum, j) => sum + (j.stats?.total_candidates || 0), 0);
  const totalHired = jobs.reduce((sum, j) => sum + (j.stats?.hired_count || 0), 0);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-display font-bold text-ink">Job Postings & Requirements</h2>
          <p className="text-sm text-ink-muted mt-1">
            Manage your positions, track candidate volumes, and launch resume match rankings.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="primary" icon={Plus} onClick={() => setShowModal(true)}>
            Post New Job
          </Button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-surface-2 border border-line rounded-2xl p-4">
          <div className="flex items-center gap-2 text-ink-muted text-xs">
            <Briefcase size={14} className="text-accent" /> Active Jobs
          </div>
          <p className="text-2xl font-display font-bold text-ink mt-2 tabular-nums">{jobs.length}</p>
        </div>

        <div className="bg-surface-2 border border-line rounded-2xl p-4">
          <div className="flex items-center gap-2 text-ink-muted text-xs">
            <Users size={14} className="text-sky-400" /> Matches Evaluated
          </div>
          <p className="text-2xl font-display font-bold text-ink mt-2 tabular-nums">{totalCandidatesRanked}</p>
        </div>

        <div className="bg-surface-2 border border-line rounded-2xl p-4">
          <div className="flex items-center gap-2 text-ink-muted text-xs">
            <UserCheck size={14} className="text-good" /> Hired Placements
          </div>
          <p className="text-2xl font-display font-bold text-good mt-2 tabular-nums">{totalHired}</p>
        </div>

        <div className="bg-surface-2 border border-line rounded-2xl p-4">
          <div className="flex items-center gap-2 text-ink-muted text-xs">
            <Layers size={14} className="text-gold" /> Categories Covered
          </div>
          <p className="text-2xl font-display font-bold text-ink mt-2 tabular-nums">
            {new Set(jobs.map((j) => j.category)).size}
          </p>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <EmptyState icon={ShieldAlert} tone="bad" title="Couldn't load jobs" description={error} />
      )}

      {/* Loading state */}
      {loading && (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton h-36 w-full rounded-2xl" />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && jobs.length === 0 && (
        <EmptyState
          icon={Briefcase}
          title="No job descriptions created yet"
          description="Create your first job posting by typing requirements or uploading a JD document to rank candidates."
          action={
            <Button variant="primary" icon={Plus} onClick={() => setShowModal(true)}>
              Create Your First Job
            </Button>
          }
        />
      )}

      {/* Jobs Grid */}
      {!loading && !error && jobs.length > 0 && (
        <div className="space-y-4">
          {jobs.map((job) => {
            const stats = job.stats || {
              total_candidates: 0,
              top_score: 0,
              shortlisted_count: 0,
              hired_count: 0,
              rejected_count: 0,
            };
            const isRanking = rankingJobId === job.id;

            return (
              <div
                key={job.id}
                className="bg-surface-2 border border-line rounded-2xl p-5 sm:p-6 transition-all hover:border-ink-faint/60 hover:shadow-panel"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className={`text-base font-display font-bold truncate ${job.status === "paused" ? "text-ink-muted line-through" : "text-ink"}`}>{job.title}</h3>
                      <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/30">
                        {job.category || "General"}
                      </span>
                      {job.status === "paused" ? (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1">
                          ⏸️ Paused
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                          🟢 Active
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 text-xs text-ink-muted mt-1.5 flex-wrap">
                      <span className="flex items-center gap-1">
                        <Calendar size={12} className="text-ink-faint" />
                        {new Date(job.created_at).toLocaleDateString()}
                      </span>
                      {job.min_experience > 0 && <span>• Min Exp: {job.min_experience} yrs</span>}
                    </div>

                    {/* Extracted Required Skills */}
                    {(job.required_skills || []).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-3">
                        {job.required_skills.slice(0, 7).map((skill) => (
                          <SkillPill key={skill} label={skill} variant="matched" />
                        ))}
                        {job.required_skills.length > 7 && (
                          <span className="text-xs text-ink-faint self-center">
                            +{job.required_skills.length - 7} more
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Top Score Badge */}
                  {stats.total_candidates > 0 && (
                    <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-1 border border-line shrink-0">
                      <Trophy size={14} className="text-gold" />
                      <div>
                        <span className="text-[10px] text-ink-muted uppercase block">Top Match</span>
                        <span className="text-sm font-bold text-ink tabular-nums">{stats.top_score}%</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Metrics Bar & Action Buttons */}
                <div className="mt-5 pt-4 border-t border-line/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-4 text-xs text-ink-muted flex-wrap">
                    <span className="flex items-center gap-1.5">
                      <Users size={13} className="text-ink-faint" />
                      <strong className="text-ink font-semibold">{stats.total_candidates}</strong> Ranked
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Sparkles size={13} className="text-gold" />
                      <strong className="text-gold font-semibold">{stats.shortlisted_count}</strong> Shortlisted
                    </span>
                    <span className="flex items-center gap-1.5">
                      <UserCheck size={13} className="text-good" />
                      <strong className="text-good font-semibold">{stats.hired_count}</strong> Hired
                    </span>
                    <span className="flex items-center gap-1.5">
                      <UserX size={13} className="text-bad" />
                      <strong className="text-bad font-semibold">{stats.rejected_count}</strong> Rejected
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 self-end sm:self-auto flex-wrap">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={job.status === "paused" ? Play : Pause}
                      onClick={() => handleToggleStatus(job.id, job.status, job.title)}
                      className={job.status === "paused" ? "text-emerald-400 hover:bg-emerald-500/10" : "text-amber-400 hover:bg-amber-500/10"}
                      title={job.status === "paused" ? "Resume Job (Allow new applicants)" : "Pause Job (Temporarily hold hiring)"}
                    >
                      {job.status === "paused" ? "Resume" : "Pause"}
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      icon={Trash2}
                      onClick={() => handleDeleteJob(job.id, job.title)}
                      className="text-bad/80 hover:bg-bad/10 hover:text-bad"
                      title="Delete Job and its ranking results"
                    >
                      Delete
                    </Button>

                    <Button
                      variant="secondary"
                      size="sm"
                      icon={Play}
                      loading={isRanking}
                      onClick={() => handleReRank(job.id, job.title)}
                    >
                      Re-Rank
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      icon={ArrowRight}
                      onClick={() => onSelectJob(job.id)}
                    >
                      View Rankings
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Job Modal */}
      {showModal &&
        ReactDOM.createPortal(
          <div
            className="fixed inset-0 z-[200] flex items-center justify-center p-4"
            style={{ background: "rgba(9,13,22,0.92)", backdropFilter: "blur(16px)" }}
          >
            <div className="bg-surface-2 border border-line rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-display font-bold text-ink flex items-center gap-2">
                  <Briefcase size={18} className="text-accent" /> Post New Job Description
                </h3>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-ink-muted hover:text-ink text-sm p-1 rounded-lg hover:bg-surface-3"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleCreateJob} className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-ink-muted block mb-1.5">Job Title *</label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    onBlur={() => setTouchedTitle(true)}
                    placeholder="e.g. Senior Business Analyst / Full Stack Developer"
                    className={`w-full px-3.5 py-2.5 rounded-xl bg-surface-1 border text-ink placeholder-ink-faint focus:outline-none text-sm transition-colors ${
                      touchedTitle && !title.trim()
                        ? "border-bad focus:border-bad"
                        : "border-line focus:border-accent"
                    }`}
                  />
                  {touchedTitle && !title.trim() && (
                    <p className="text-bad text-xs mt-1">Job title is required</p>
                  )}
                </div>

                {/* Mode Switcher */}
                <div className="flex rounded-xl bg-surface-1 border border-line p-1 gap-1">
                  <button
                    type="button"
                    onClick={() => setMode("text")}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
                      mode === "text" ? "bg-accent text-white shadow-glow" : "text-ink-muted hover:text-ink"
                    }`}
                  >
                    <FileText size={13} /> Paste Text
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("file")}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
                      mode === "file" ? "bg-accent text-white shadow-glow" : "text-ink-muted hover:text-ink"
                    }`}
                  >
                    <Upload size={13} /> Upload File (.docx / .pdf)
                  </button>
                </div>

                {mode === "text" ? (
                  <div>
                    <label className="text-xs font-semibold text-ink-muted block mb-1.5">
                      Job Description & Responsibilities *
                    </label>
                    <textarea
                      rows={6}
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      onBlur={() => setTouchedText(true)}
                      placeholder="Paste the full job requirements, required skills, and qualifications here..."
                      className={`w-full px-3.5 py-2.5 rounded-xl bg-surface-1 border text-ink placeholder-ink-faint focus:outline-none text-sm resize-y transition-colors ${
                        touchedText && !text.trim()
                          ? "border-bad focus:border-bad"
                          : "border-line focus:border-accent"
                      }`}
                    />
                    {touchedText && !text.trim() && (
                      <p className="text-bad text-xs mt-1">Job description text is required</p>
                    )}
                    {text.trim() && text.trim().split(/\s+/).length < 10 && (
                      <p className="text-warn text-xs mt-1">⚠ Too short — add more details for accurate AI matching</p>
                    )}
                  </div>
                ) : (
                  <div>
                    <label className="text-xs font-semibold text-ink-muted block mb-1.5">
                      Select JD Document (.docx or .pdf) *
                    </label>
                    <div
                      onClick={() => fileInputRef.current?.click()}
                      className="border-2 border-dashed border-line hover:border-accent rounded-xl p-6 text-center cursor-pointer bg-surface-1 transition-colors"
                    >
                      <Upload size={24} className="mx-auto text-accent mb-2" />
                      {file ? (
                        <p className="text-xs text-good font-semibold flex items-center justify-center gap-1">
                          <CheckCircle2 size={13} /> {file.name} ({(file.size / 1024).toFixed(1)} KB)
                        </p>
                      ) : (
                        <>
                          <p className="text-xs text-ink font-medium">Click to select JD file</p>
                          <p className="text-[11px] text-ink-muted mt-0.5">Supports .docx and .pdf up to 10MB</p>
                        </>
                      )}
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".docx,.pdf"
                        className="hidden"
                        onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
                      />
                    </div>
                  </div>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="secondary" onClick={() => { setShowModal(false); setTouchedTitle(false); setTouchedText(false); }}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" loading={creating}>
                    Create Job Posting
                  </Button>
                </div>
              </form>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
