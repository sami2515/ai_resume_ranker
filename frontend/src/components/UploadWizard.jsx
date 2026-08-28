import { useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";

import {
  UploadCloud,
  FileText,
  CheckCircle2,
  XCircle,
  Copy,
  Loader2,
  Clock,
  Sparkles,
  Upload,
  Briefcase,
  Cpu,
  Layers,
  Check,
  Zap,
  ShieldAlert,
  ArrowRight,
  Sparkle,
} from "lucide-react";
import Button from "./ui/Button";
import { useToast } from "./ui/Toast";
import {
  uploadResumeBatch,
  uploadJobStatus,
  createJob,
  createJobWithFile,
  listJobs,
  rankJob,
  getAnalytics,
} from "../api";

const STATUS_LABEL = {
  uploading: "Uploading…",
  queued: "Queued…",
  processing: "Parsing…",
  created: "Parsed",
  duplicate: "Duplicate (already uploaded)",
  error: "Failed",
};

const STATUS_ICON = {
  uploading: Loader2,
  queued: Clock,
  processing: Loader2,
  created: CheckCircle2,
  duplicate: Copy,
  error: XCircle,
};

const STATUS_COLOR = {
  uploading: "text-ink-faint",
  queued: "text-warn",
  processing: "text-accent",
  created: "text-good",
  duplicate: "text-warn",
  error: "text-bad",
};

const PENDING_STATUSES = new Set(["queued", "processing"]);
const POLL_INTERVAL_MS = 1200;

const AI_STEPS = [
  {
    title: "Document Parsing & Entity Extraction",
    desc: "Extracting contact info, technical skills & experience years",
    icon: FileText,
  },
  {
    title: "SBERT Semantic Embeddings",
    desc: "Encoding 384-dimensional dense vectors (all-MiniLM-L6-v2)",
    icon: Cpu,
  },
  {
    title: "Hybrid Scoring & Overlap Weights",
    desc: "Calculating 40% Keyword TF-IDF/NER + 60% Semantic Cosine Match",
    icon: Layers,
  },
  {
    title: "Talent Ranking & Decision Confidence",
    desc: "Generating deterministic leaderboard & explainability report",
    icon: Sparkles,
  },
];

export default function UploadWizard({ onRanked }) {
  const toast = useToast();
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [totalCandidatesInDb, setTotalCandidatesInDb] = useState(0);

  // Job selection / creation states
  const [existingJobs, setExistingJobs] = useState([]);
  const [jdSource, setJdSource] = useState("new_text"); // 'new_text' | 'new_file' | 'existing'
  const [selectedExistingJobId, setSelectedExistingJobId] = useState("");
  const [jdTitle, setJdTitle] = useState("Senior Business Analyst");
  const [jdText, setJdText] = useState("");
  const [jdFile, setJdFile] = useState(null);
  const [jdDragOver, setJdDragOver] = useState(false);

  const handleJdDrop = (e) => {
    e.preventDefault();
    setJdDragOver(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      const ext = droppedFile.name.split(".").pop().toLowerCase();
      if (ext === "pdf" || ext === "docx") {
        setJdFile(droppedFile);
        setJdSource("new_file");
        const baseName = droppedFile.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
        if (!jdTitle || jdTitle === "Senior Business Analyst") {
          setJdTitle(baseName);
        }
        toast(`JD File "${droppedFile.name}" attached!`, "success");
      } else {
        toast("Please upload a valid .docx or .pdf file for Job Description.", "error");
      }
    }
  };

  // Ranking scope state: 'new_only' (only resumes in this session) vs 'all_pool' (entire database)
  const [rankingScope, setRankingScope] = useState("new_only");

  // AI Animation modal states
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [aiStep, setAiStep] = useState(0);
  const [aiProgress, setAiProgress] = useState(0);
  const [ranking, setRanking] = useState(false);
  const [rankError, setRankError] = useState(null);

  const inputRef = useRef(null);
  const jdFileInputRef = useRef(null);

  // Validation: track which fields user has interacted with
  const [touchedTitle, setTouchedTitle] = useState(false);
  const [touchedText, setTouchedText] = useState(false);

  const fetchMetadata = () => {
    listJobs()
      .then((res) => {
        const jobs = res.jobs || [];
        setExistingJobs(jobs);
        const activeJobs = jobs.filter((j) => j.status !== "paused");
        if (activeJobs.length > 0) {
          setSelectedExistingJobId(String(activeJobs[0].id));
        } else if (jobs.length > 0) {
          setSelectedExistingJobId(String(jobs[0].id));
        }
      })
      .catch(() => {});

    getAnalytics()
      .then((data) => {
        setTotalCandidatesInDb(data.total_candidates || 0);
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchMetadata();
  }, []);

  const addFiles = useCallback(
    async (fileList) => {
      const incoming = Array.from(fileList);
      const tempIds = incoming.map((file) => `${file.name}-${file.size}-${Math.random().toString(36).slice(2)}`);
      setFiles((prev) => [
        ...prev,
        ...incoming.map((file, i) => ({ id: tempIds[i], name: file.name, jobId: null, status: "uploading", error: null })),
      ]);

      // Automatically default to "new_only" when user drops files in
      setRankingScope("new_only");

      try {
        const results = await uploadResumeBatch(incoming);
        setFiles((prev) =>
          prev.map((f) => {
            const idx = tempIds.indexOf(f.id);
            if (idx === -1) return f;
            const r = results[idx];
            return { ...f, jobId: r.job_id, status: r.status, candidateId: r.candidate_id, error: r.error };
          })
        );
        fetchMetadata();
      } catch (err) {
        setFiles((prev) => prev.map((f) => (tempIds.includes(f.id) ? { ...f, status: "error", error: err.message } : f)));
        toast(`Batch upload failed: ${err.message}`, "error");
      }
    },
    [toast]
  );

  useEffect(() => {
    const pending = files.filter((f) => PENDING_STATUSES.has(f.status));
    if (pending.length === 0) return;

    const timer = setTimeout(async () => {
      const updates = await Promise.all(
        pending.map(async (f) => {
          try {
            const job = await uploadJobStatus(f.jobId);
            return { id: f.id, status: job.status, candidateId: job.candidate_id, error: job.error };
          } catch (err) {
            return { id: f.id, status: "error", error: err.message };
          }
        })
      );
      setFiles((prev) =>
        prev.map((f) => {
          const u = updates.find((x) => x.id === f.id);
          return u ? { ...f, ...u } : f;
        })
      );
      fetchMetadata();
    }, POLL_INTERVAL_MS);

    return () => clearTimeout(timer);
  }, [files]);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
  };

  const successFiles = files.filter((f) => f.status === "created" || f.status === "duplicate");
  const successCount = successFiles.length;
  const errorCount = files.filter((f) => f.status === "error").length;
  const pendingCount = files.filter((f) => f.status === "uploading" || PENDING_STATUSES.has(f.status)).length;

  // Deduplicated candidate IDs from newly uploaded files
  const uploadedCandidateIds = Array.from(
    new Set(files.filter((f) => f.candidateId).map((f) => f.candidateId))
  );
  const newBatchCount = uploadedCandidateIds.length > 0 ? uploadedCandidateIds.length : successFiles.length;

  const isJdReady =
    jdSource === "existing"
      ? Boolean(selectedExistingJobId)
      : jdSource === "new_file"
      ? Boolean(jdTitle.trim() && jdFile)
      : Boolean(jdTitle.trim() && jdText.trim());

  // Single Source of Truth for the active scope evaluation count
  const effectiveScope = files.length === 0 ? "all_pool" : rankingScope;
  const evaluatedCandidateCount =
    effectiveScope === "new_only"
      ? newBatchCount
      : Math.max(totalCandidatesInDb, newBatchCount);

  // Can rank if: no files currently in uploading/pending, JD is ready, AND (we have new files OR existing candidates in DB)
  const hasCandidates = evaluatedCandidateCount > 0;
  const canRank = pendingCount === 0 && isJdReady && hasCandidates;

  const currentJobTitle =
    jdSource === "existing"
      ? existingJobs.find((j) => String(j.id) === selectedExistingJobId)?.title || "Selected Position"
      : jdTitle || "Job Position";

  // Trigger AI Ranking with synchronized multi-step animation
  const handleRank = async () => {
    // Touch all fields to show validation errors
    if (jdSource !== "existing") {
      setTouchedTitle(true);
      setTouchedText(true);
    }
    if (!canRank) {
      if (!hasCandidates) toast("Please upload at least one resume before ranking.", "error");
      else if (!isJdReady) toast("Please complete the Job Description fields before ranking.", "error");
      return;
    }

    setRanking(true);
    setRankError(null);
    setAiModalOpen(true);
    setAiStep(0);
    setAiProgress(10);

    // Progressive step simulation — timed to feel premium (~5s)
    const stepTimer1 = setTimeout(() => { setAiStep(1); setAiProgress(28); }, 900);
    const stepTimer2 = setTimeout(() => { setAiStep(2); setAiProgress(55); }, 2000);
    const stepTimer3 = setTimeout(() => { setAiStep(3); setAiProgress(82); }, 3200);

    try {
      let targetJobId;
      if (jdSource === "existing") {
        targetJobId = Number(selectedExistingJobId);
      } else if (jdSource === "new_file") {
        const jd = await createJobWithFile({ title: jdTitle.trim(), file: jdFile });
        targetJobId = jd.id;
      } else {
        const jd = await createJob({ title: jdTitle.trim(), text: jdText.trim() });
        targetJobId = jd.id;
      }

      // If scope is 'new_only' and we have uploaded candidate IDs, pass them; else rank all
      const candidateIdsToPass =
        effectiveScope === "new_only" && uploadedCandidateIds.length > 0
          ? uploadedCandidateIds
          : null;

      await rankJob(targetJobId, candidateIdsToPass);

      // Ensure at least 4.5s total animation — premium feel + SRS <5s requirement
      await new Promise((r) => setTimeout(r, 4500));
      setAiProgress(100);

      await new Promise((r) => setTimeout(r, 400));
      setAiModalOpen(false);
      onRanked(targetJobId);
    } catch (err) {
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      clearTimeout(stepTimer3);
      setAiModalOpen(false);
      setRankError(err.message);
      toast(err.message || "Ranking failed", "error");
    } finally {
      setRanking(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-7">

      {/* 3-Step Progress Indicator */}
      <div className="bg-surface-2 border border-line rounded-2xl px-6 py-4">
        <div className="flex items-center justify-between relative">
          {/* Connector line behind */}
          <div className="absolute left-0 right-0 top-4 mx-12 h-px bg-line/60" style={{ zIndex: 0 }} />

          {[
            { n: 1, label: "Upload Resumes", done: successCount > 0 || totalCandidatesInDb > 0, active: true },
            { n: 2, label: "Set Job Description", done: isJdReady, active: successCount > 0 || totalCandidatesInDb > 0 },
            { n: 3, label: "Rank with AI", done: false, active: isJdReady && (successCount > 0 || totalCandidatesInDb > 0) },
          ].map((step, i) => (
            <div key={step.n} className="flex flex-col items-center gap-1.5 relative z-10" style={{ flex: 1 }}>
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all ${
                  step.done
                    ? "bg-good border-good text-white"
                    : step.active
                    ? "bg-accent border-accent text-white shadow-glow"
                    : "bg-surface-1 border-line text-ink-faint"
                }`}
              >
                {step.done ? <Check size={14} /> : step.n}
              </div>
              <span className={`text-[10px] font-semibold text-center leading-tight px-1 ${
                step.done ? "text-good" : step.active ? "text-white" : "text-ink-faint"
              }`}>
                {step.label}
              </span>
            </div>
          ))}
        </div>

        {/* Contextual tip */}
        <p className="text-center text-[11px] text-ink-muted mt-3 pt-3 border-t border-line/40">
          {!hasCandidates
            ? "⬆ Start by dragging resume files below, or drop a folder of CVs"
            : !isJdReady
            ? "✍ Now paste or upload a Job Description to match candidates against"
            : "🚀 Ready! Click \"Rank Candidates with AI\" to compute match scores instantly"}
        </p>
      </div>

      {/* Step 1: Upload Resumes */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-display font-semibold text-white flex items-center gap-2">
            <span className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${successCount > 0 || totalCandidatesInDb > 0 ? "bg-good text-white" : "bg-accent/15 text-accent"}`}>
              {successCount > 0 || totalCandidatesInDb > 0 ? <Check size={12} /> : "1"}
            </span>
            Upload Resumes
            <span className="text-xs font-normal text-ink-muted">(.pdf / .docx)</span>
          </h2>
          {totalCandidatesInDb > 0 && (
            <span className="text-xs text-ink-muted bg-surface-2 px-2.5 py-1 rounded-full border border-line">
              {files.length > 0 && effectiveScope === "new_only" ? (
                <>
                  <span className="text-accent font-semibold">{evaluatedCandidateCount}</span> selected for ranking ({totalCandidatesInDb} in pool)
                </>
              ) : (
                <>
                  <span className="text-white font-semibold">{totalCandidatesInDb}</span> in pool
                </>
              )}
            </span>
          )}
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Upload resumes: drag and drop or click to browse"
          className={`border-2 border-dashed rounded-2xl p-8 sm:p-10 text-center cursor-pointer transition-all duration-200 ${
            dragOver ? "border-accent bg-accent/5 scale-[1.005]" : "border-line hover:border-ink-faint bg-surface-2/50"
          }`}
        >
          <div className="w-12 h-12 rounded-2xl bg-accent/10 text-accent flex items-center justify-center mx-auto mb-3 shadow-glow">
            <UploadCloud size={24} />
          </div>
          <p className="text-white font-bold text-sm sm:text-base drop-shadow-sm" style={{ color: "#FFFFFF" }}>
            Drag &amp; drop resumes here, or <span className="text-blue-400 underline underline-offset-2 font-bold">click to browse</span>
          </p>
          <p className="text-slate-300 text-xs sm:text-sm mt-1.5 font-medium" style={{ color: "#CBD5E1" }}>
            Supports PDF and DOCX · Batch upload supported · Duplicates auto-detected
          </p>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".docx,.pdf"
            className="hidden"
            onChange={(e) => e.target.files?.length && addFiles(e.target.files)}
          />
        </div>

        {/* Uploaded Files Queue */}
        {files.length > 0 && (
          <ul className="mt-4 divide-y divide-line border border-line rounded-2xl overflow-hidden max-h-64 overflow-y-auto bg-surface-2" aria-live="polite">
            {files.map((f) => {
              const Icon = STATUS_ICON[f.status];
              const spinning = f.status === "uploading" || f.status === "processing";
              return (
                <li key={f.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                  <span className="flex items-center gap-2.5 min-w-0">
                    <FileText size={14} className="text-ink-faint shrink-0" />
                    <span className="text-white font-medium text-sm truncate">{f.name}</span>
                  </span>
                  <span className={`flex items-center gap-1.5 text-xs font-medium shrink-0 ${STATUS_COLOR[f.status]}`} title={f.error || ""}>
                    <Icon size={13} className={spinning ? "animate-spin" : ""} />
                    {STATUS_LABEL[f.status]}
                  </span>
                </li>
              );
            })}
          </ul>
        )}

        {/* Scope Selection Pills — synchronized labels */}
        {files.length > 0 ? (
          <div className="mt-3.5 bg-surface-2 border border-line/80 rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-good font-semibold">✓ {newBatchCount} of {files.length} resumes ready</span>
              {errorCount > 0 && <span className="text-bad">{errorCount} failed</span>}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-slate-300 text-xs shrink-0 font-medium">Who to rank:</span>
              <button
                type="button"
                onClick={() => setRankingScope("new_only")}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                  effectiveScope === "new_only"
                    ? "bg-accent text-white border-accent shadow-sm"
                    : "bg-surface-1 text-slate-300 border-line hover:text-white"
                }`}
                title="Only score the resumes you just uploaded"
              >
                🆕 Just uploaded ({newBatchCount})
              </button>
              <button
                type="button"
                onClick={() => setRankingScope("all_pool")}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                  effectiveScope === "all_pool"
                    ? "bg-accent text-white border-accent shadow-sm"
                    : "bg-surface-1 text-slate-300 border-line hover:text-white"
                }`}
                title="Re-rank all candidates in the database"
              >
                🌐 All in database ({Math.max(totalCandidatesInDb, newBatchCount)})
              </button>
            </div>
            <p className="text-[11px] text-slate-200 pt-1.5 border-t border-line/40 flex items-center gap-1.5" style={{ color: "#E2E8F0" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
              <span>
                {effectiveScope === "new_only"
                  ? `Ranking Scope: AI will evaluate only the ${newBatchCount} candidate(s) uploaded in this batch.`
                  : `Ranking Scope: AI will evaluate all ${Math.max(totalCandidatesInDb, newBatchCount)} candidate(s) in your database talent pool.`}
              </span>
            </p>
          </div>
        ) : totalCandidatesInDb > 0 ? (
          <div className="mt-3 bg-surface-2/80 border border-line/70 rounded-xl p-3 text-xs text-slate-200 flex items-center gap-2" style={{ color: "#E2E8F0" }}>
            <span className="w-2 h-2 rounded-full bg-blue-400 inline-block shrink-0" />
            <span>
              No new resumes added in this batch. Ranking will evaluate all <strong className="text-white font-bold" style={{ color: "#FFFFFF" }}>{totalCandidatesInDb} candidate(s)</strong> in your existing talent pool.
            </span>
          </div>
        ) : (
          <div className="mt-3 bg-warn/10 border border-warn/30 rounded-xl p-3 text-xs text-warn flex items-center gap-2">
            <ShieldAlert size={14} className="shrink-0" />
            <span>Your candidate database is currently empty. Please drop at least one resume above before ranking.</span>
          </div>
        )}
      </section>

      {/* Step 2: Job Description Setup */}
      <section>
        <h2 className="text-base font-display font-semibold text-white mb-3 flex items-center gap-2">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-accent/15 text-accent text-xs font-semibold">2</span>
          Job Description & Requirements
        </h2>

        <div className="space-y-4 bg-surface-2 border border-line rounded-2xl p-5 shadow-panel">
          {/* Option Selector */}
          <div className="flex rounded-xl bg-surface-1 border border-line p-1 gap-1">
            <button
              type="button"
              onClick={() => setJdSource("new_text")}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
                jdSource === "new_text" ? "bg-accent text-white shadow-glow" : "text-ink-muted hover:text-ink"
              }`}
            >
              <FileText size={13} /> Paste New JD Text
            </button>
            <button
              type="button"
              onClick={() => setJdSource("new_file")}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
                jdSource === "new_file" ? "bg-accent text-white shadow-glow" : "text-ink-muted hover:text-ink"
              }`}
            >
              <Upload size={13} /> Upload JD File (.docx / .pdf)
            </button>
            {existingJobs.length > 0 && (
              <button
                type="button"
                onClick={() => setJdSource("existing")}
                className={`flex-1 py-1.5 text-xs font-medium rounded-lg flex items-center justify-center gap-1.5 transition-colors ${
                  jdSource === "existing" ? "bg-accent text-white shadow-glow" : "text-ink-muted hover:text-ink"
                }`}
              >
                <Briefcase size={13} /> Select Saved Job ({existingJobs.length})
              </button>
            )}
          </div>

          {jdSource === "existing" ? (
            <div>
              <label htmlFor="select-existing-job" className="text-xs font-medium text-ink-muted block mb-1.5">
                Choose Existing Job Posting
              </label>
              <select
                id="select-existing-job"
                value={selectedExistingJobId}
                onChange={(e) => setSelectedExistingJobId(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-surface-1 border border-line text-white text-sm focus:outline-none focus:border-accent"
              >
                {existingJobs.map((j) => (
                  <option key={j.id} value={j.id} disabled={j.status === "paused"}>
                    {j.title} ({j.category || "General"}) {j.status === "paused" ? "— [PAUSED]" : ""}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label htmlFor="jd-title" className="text-xs font-medium text-ink-muted block mb-1.5">
                  Job title <span className="text-bad">*</span>
                </label>
                <input
                  id="jd-title"
                  type="text"
                  value={jdTitle}
                  onChange={(e) => { setJdTitle(e.target.value); setTouchedTitle(true); }}
                  onBlur={() => setTouchedTitle(true)}
                  placeholder="e.g. Senior Business Analyst"
                  className={`w-full px-3.5 py-2.5 rounded-xl bg-surface-1 border text-white placeholder-ink-faint focus:outline-none transition-colors text-sm ${
                    touchedTitle && !jdTitle.trim() ? "border-bad focus:border-bad" : "border-line focus:border-accent"
                  }`}
                />
                {touchedTitle && !jdTitle.trim() && (
                  <p className="text-bad text-[11px] mt-1 flex items-center gap-1">
                    <XCircle size={11} /> Job title is required
                  </p>
                )}
              </div>

              {jdSource === "new_text" ? (
                <div>
                  <label htmlFor="jd-text" className="text-xs font-medium text-ink-muted block mb-1.5">
                    Job description text <span className="text-bad">*</span>
                  </label>
                  <textarea
                    id="jd-text"
                    value={jdText}
                    onChange={(e) => { setJdText(e.target.value); setTouchedText(true); }}
                    onBlur={() => setTouchedText(true)}
                    placeholder="Paste the job description and requirements here. Include required skills, tools, and responsibilities for best AI matching..."
                    rows={5}
                    className={`w-full px-3.5 py-2.5 rounded-xl bg-surface-1 border text-white placeholder-ink-faint focus:outline-none transition-colors text-sm resize-y ${
                      touchedText && !jdText.trim() ? "border-bad focus:border-bad" : "border-line focus:border-accent"
                    }`}
                  />
                  {touchedText && !jdText.trim() && (
                    <p className="text-bad text-[11px] mt-1 flex items-center gap-1">
                      <XCircle size={11} /> Job description text is required
                    </p>
                  )}
                  {touchedText && jdText.trim() && jdText.trim().split(/\s+/).length < 10 && (
                    <p className="text-warn text-[11px] mt-1 flex items-center gap-1">
                      <ShieldAlert size={11} /> Too short — add more details for accurate AI matching
                    </p>
                  )}
                </div>
              ) : (
                <div>
                  <label className="text-xs font-medium text-ink-muted block mb-1.5">
                    Upload JD Document (.docx / .pdf) *
                  </label>
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setJdDragOver(true);
                    }}
                    onDragLeave={() => setJdDragOver(false)}
                    onDrop={handleJdDrop}
                    onClick={() => jdFileInputRef.current?.click()}
                    role="button"
                    tabIndex={0}
                    aria-label="Upload Job Description document: drag and drop or click to browse"
                    className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer bg-surface-1 transition-all duration-200 ${
                      jdDragOver ? "border-accent bg-accent/10 scale-[1.01]" : "border-line hover:border-accent"
                    }`}
                  >
                    <Upload size={20} className="text-accent mx-auto mb-1.5" />
                    {jdFile ? (
                      <div>
                        <p className="text-white text-sm font-bold flex items-center justify-center gap-1.5" style={{ color: "#FFFFFF" }}>
                          <CheckCircle2 size={16} className="text-good shrink-0" /> {jdFile.name}
                        </p>
                        <p className="text-[11px] text-slate-300 mt-1" style={{ color: "#CBD5E1" }}>
                          Click or drag &amp; drop another file to replace
                        </p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-white font-bold text-xs sm:text-sm drop-shadow-sm" style={{ color: "#FFFFFF" }}>
                          Drag &amp; drop JD file here, or <span className="text-blue-400 underline font-bold">click to browse</span>
                        </p>
                        <p className="text-slate-300 text-[11px] mt-1 font-medium" style={{ color: "#CBD5E1" }}>
                          Supports PDF and DOCX files
                        </p>
                      </div>
                    )}
                    <input
                      ref={jdFileInputRef}
                      type="file"
                      accept=".docx,.pdf"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files?.[0]) {
                          const f = e.target.files[0];
                          setJdFile(f);
                          setJdSource("new_file");
                          const baseName = f.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
                          if (!jdTitle || jdTitle === "Senior Business Analyst") {
                            setJdTitle(baseName);
                          }
                        }
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Step 3: Trigger Action */}
      <section className="space-y-3">
        {/* JD Quality Indicator — only shown when JD text is entered */}
        {jdSource === "new_text" && jdText.trim().length > 0 && (() => {
          const wordCount = jdText.trim().split(/\s+/).length;
          const hasSkillKeywords = /\b(python|javascript|java|sql|react|excel|powerpoint|word|css|html|node|django|flask|c\+\+|machine learning|data analysis|communication|leadership|management|accounting|design|photoshop|illustrator|figma|git|linux|networking|cisco|cloud|aws|azure)\b/i.test(jdText);
          const qualityScore = Math.min(100, Math.round(
            (Math.min(wordCount, 100) / 100) * 50 +
            (hasSkillKeywords ? 35 : 0) +
            (wordCount >= 30 ? 15 : wordCount >= 15 ? 8 : 0)
          ));
          const isGood = qualityScore >= 70;
          const isMid  = qualityScore >= 35;

          return (
            <div className={`rounded-xl p-3 border text-xs flex items-start gap-3 ${
              isGood ? "bg-good/10 border-good/30" : isMid ? "bg-warn/10 border-warn/30" : "bg-bad/10 border-bad/30"
            }`}>
              <div className={`w-9 h-9 rounded-lg flex flex-col items-center justify-center shrink-0 font-bold text-sm ${
                isGood ? "bg-good/20 text-good" : isMid ? "bg-warn/20 text-warn" : "bg-bad/20 text-bad"
              }`}>
                {qualityScore}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`font-semibold ${isGood ? "text-good" : isMid ? "text-warn" : "text-bad"}`}>
                    JD Quality: {isGood ? "Good ✓" : isMid ? "Fair — Improve for better results" : "Poor — AI match accuracy will be low"}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden mb-1.5">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${isGood ? "bg-good" : isMid ? "bg-warn" : "bg-bad"}`}
                    style={{ width: `${qualityScore}%` }}
                  />
                </div>
                {!isGood && (
                  <p className="text-ink-muted leading-relaxed">
                    {wordCount < 30
                      ? `Too short (${wordCount} words). Add role responsibilities, required skills, and tools. Aim for 50+ words.`
                      : !hasSkillKeywords
                      ? "No specific skills detected. Mention tools like Python, Excel, SQL, or role-specific technologies for better AI matching."
                      : "Add more specific requirements and skill keywords to improve candidate match accuracy."
                    }
                  </p>
                )}
              </div>
            </div>
          );
        })()}

        <Button
          variant="primary"
          size="lg"
          icon={ranking ? undefined : Sparkles}
          loading={ranking}
          disabled={!canRank}
          onClick={handleRank}
          className="w-full shadow-glow text-sm font-semibold"
        >
          {ranking ? "AI Semantic Matching in Progress..." : `Rank ${evaluatedCandidateCount} Candidates with AI`}
        </Button>
        {rankError && <p className="text-bad text-sm mt-2 text-center">{rankError}</p>}
      </section>

      {/* ── Premium AI Processing Modal — rendered in body via portal to avoid navbar z-index conflict ── */}
      {aiModalOpen && ReactDOM.createPortal(
      <div className="fixed inset-0 z-[200] flex items-center justify-center p-3" style={{ background: "rgba(9,13,22,0.92)", backdropFilter: "blur(16px)" }}>

        {/* Card — max-h to always fit in viewport */}
        <div
          className="relative w-full max-w-md overflow-hidden rounded-2xl shadow-2xl"
          style={{
            background: "linear-gradient(145deg,#0F172A 0%,#0D1526 60%,#0A1020 100%)",
            border: "1px solid rgba(37,99,235,0.35)",
            maxHeight: "calc(100vh - 24px)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Ambient glows */}
          <div className="pointer-events-none absolute -top-16 -right-16 w-48 h-48 rounded-full blur-3xl" style={{ background: "radial-gradient(circle,rgba(37,99,235,0.28) 0%,transparent 70%)" }} />
          <div className="pointer-events-none absolute -bottom-12 -left-12 w-40 h-40 rounded-full blur-3xl" style={{ background: "radial-gradient(circle,rgba(16,185,129,0.15) 0%,transparent 70%)" }} />

          {/* Top accent line */}
          <div className="h-[2px] w-full shrink-0" style={{ background: "linear-gradient(90deg, transparent, #2563EB, #10B981, transparent)" }} />

          {/* Scrollable body */}
          <div className="overflow-y-auto px-6 pt-5 pb-5 space-y-4" style={{ scrollbarWidth: "none" }}>

            {/* ── Header: Logo + Orb rings + badge + title ── */}
            <div className="flex flex-col items-center gap-3">

              {/* Orb with logo center */}
              <div className="relative w-20 h-20 flex items-center justify-center shrink-0">
                {/* Ping pulse ring */}
                <div className="absolute inset-0 rounded-full border border-blue-500/20 animate-ping" style={{ animationDuration: "2.2s" }} />
                {/* Outer spin */}
                <div className="absolute inset-0 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: "#2563EB", borderRightColor: "#3B82F6", animationDuration: "1.2s" }} />
                {/* Inner counter-spin */}
                <div className="absolute inset-3 rounded-full border border-transparent animate-spin" style={{ borderBottomColor: "#10B981", borderLeftColor: "#34D399", animationDuration: "1.8s", animationDirection: "reverse" }} />
                {/* Inner glow disc */}
                <div className="absolute inset-4 rounded-full" style={{ background: "radial-gradient(circle, rgba(37,99,235,0.30) 0%, rgba(37,99,235,0.04) 100%)" }} />
                {/* Logo center */}
                <img
                  src="/logo.png"
                  alt="AI ResumeRanker"
                  className="relative w-10 h-10 rounded-xl object-contain"
                  style={{ filter: "drop-shadow(0 0 10px rgba(37,99,235,0.7))", zIndex: 2 }}
                />
              </div>

              {/* Status badge */}
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border" style={{ background: "rgba(37,99,235,0.12)", borderColor: "rgba(37,99,235,0.35)" }}>
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                <span className="text-blue-400 text-[10px] font-mono font-semibold tracking-widest">AI NEURAL MATCHING ACTIVE</span>
              </div>

              {/* Title */}
              <div className="text-center">
                <h3 className="text-xl font-display font-bold text-white tracking-tight">
                  {aiProgress >= 100 ? "Ranking Complete ✓" : "Analyzing Candidates"}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Evaluating against <span className="text-white font-semibold">{currentJobTitle}</span>
                </p>
              </div>

              {/* Stat pills */}
              <div className="flex items-center gap-1.5 flex-wrap justify-center">
                <div className="px-2.5 py-0.5 rounded-lg border border-slate-700 bg-slate-800/60 text-[10px] text-slate-400">
                  <span className="text-white font-semibold">{evaluatedCandidateCount}</span> candidates
                </div>
                <div className="px-2.5 py-0.5 rounded-lg border border-slate-700 bg-slate-800/60 text-[10px] text-slate-400">
                  <span className="text-white font-semibold">SBERT</span> + TF-IDF
                </div>
                <div className="px-2.5 py-0.5 rounded-lg border border-slate-700 bg-slate-800/60 text-[10px] text-slate-400">
                  384-dim vectors
                </div>
              </div>
            </div>

            {/* ── Step Timeline ── */}
            <div className="rounded-xl overflow-hidden border border-slate-700/60" style={{ background: "rgba(15,23,42,0.8)" }}>
              {AI_STEPS.map((step, idx) => {
                const StepIcon = step.icon;
                const isComplete = aiStep > idx;
                const isCurrent  = aiStep === idx;
                return (
                  <div
                    key={step.title}
                    className="flex items-center gap-3 px-3 py-2.5 transition-all duration-500 border-b border-slate-800/80 last:border-0"
                    style={{ background: isCurrent ? "rgba(37,99,235,0.10)" : "transparent" }}
                  >
                    {/* Icon */}
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-all duration-500"
                      style={{
                        background: isComplete ? "rgba(16,185,129,0.20)" : isCurrent ? "linear-gradient(135deg,#1D4ED8,#2563EB)" : "rgba(30,41,59,0.8)",
                        border: isComplete ? "1px solid rgba(16,185,129,0.40)" : isCurrent ? "1px solid rgba(59,130,246,0.50)" : "1px solid rgba(51,65,85,0.6)",
                        boxShadow: isCurrent ? "0 0 12px rgba(37,99,235,0.40)" : "none",
                      }}
                    >
                      {isComplete
                        ? <Check size={13} className="text-emerald-400" />
                        : isCurrent
                        ? <Loader2 size={13} className="text-white animate-spin" />
                        : <StepIcon size={12} className="text-slate-500" />
                      }
                    </div>

                    {/* Text */}
                    <div className="flex-1 min-w-0">
                      <p className={`text-[11px] font-semibold transition-colors duration-300 ${isComplete ? "text-emerald-400" : isCurrent ? "text-white" : "text-slate-500"}`}>
                        {step.title}
                      </p>
                      <p className="text-[9px] text-slate-600 truncate mt-0.5">{step.desc}</p>
                    </div>

                    {/* Badge */}
                    <div className="shrink-0">
                      {isComplete && <span className="text-[9px] font-mono text-emerald-500 bg-emerald-500/10 border border-emerald-500/25 px-1.5 py-0.5 rounded-full">done</span>}
                      {isCurrent  && <span className="text-[9px] font-mono text-blue-400 bg-blue-500/10 border border-blue-500/25 px-1.5 py-0.5 rounded-full animate-pulse">running</span>}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* ── Progress bar ── */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400 font-medium">Matching Progress</span>
                <span className="font-mono font-bold text-blue-400">{Math.round(aiProgress)}%</span>
              </div>
              <div className="h-2.5 rounded-full overflow-hidden" style={{ background: "rgba(30,41,59,0.9)", border: "1px solid rgba(51,65,85,0.6)" }}>
                <div
                  className="h-full rounded-full relative overflow-hidden transition-all duration-700"
                  style={{
                    width: `${aiProgress}%`,
                    background: "linear-gradient(90deg, #1D4ED8, #2563EB, #3B82F6, #10B981)",
                    boxShadow: "0 0 10px rgba(37,99,235,0.6)",
                  }}
                >
                  <div
                    className="absolute inset-0 opacity-40"
                    style={{
                      background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)",
                      backgroundSize: "200% 100%",
                      animation: "shimmer 1.5s infinite linear",
                    }}
                  />
                </div>
              </div>
            </div>

          </div>

          {/* Bottom accent line */}
          <div className="h-[1px] w-full shrink-0" style={{ background: "linear-gradient(90deg, transparent, rgba(37,99,235,0.4), transparent)" }} />
        </div>
      </div>,
      document.body
      )}

    </div>
  );
}
