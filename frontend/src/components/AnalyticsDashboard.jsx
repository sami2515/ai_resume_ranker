import { useEffect, useState } from "react";
import {
  Users,
  Briefcase,
  Target,
  BarChart3,
  ShieldAlert,
  LineChart,
  Cpu,
  Sparkles,
  RefreshCw,
  Sliders,
  History,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import Button from "./ui/Button";
import EmptyState from "./ui/EmptyState";
import { SkeletonStatCard } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";
import { getAnalytics, getActiveWeights, getWeightsHistory, triggerReweight } from "../api";

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="bg-surface-2 border border-line rounded-2xl p-4">
      <div className="flex items-center gap-2 text-ink-muted">
        <Icon size={14} />
        <p className="text-sm">{label}</p>
      </div>
      <p className="text-2xl font-display font-semibold text-ink mt-2 tabular-nums">{value}</p>
    </div>
  );
}

function BarRow({ label, value, max, colorClass = "bg-accent" }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-ink-muted w-40 truncate">{label}</span>
      <div className="flex-1 h-2.5 rounded-full bg-surface-3 overflow-hidden">
        <div className={`h-full rounded-full ${colorClass}`} style={{ width: `${pct}%`, transition: "width 0.6s cubic-bezier(0.16,1,0.3,1)" }} />
      </div>
      <span className="text-sm text-ink-muted w-8 text-right tabular-nums">{value}</span>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <section>
      <h2 className="text-base font-display font-semibold text-ink mb-3">{title}</h2>
      <div className="bg-surface-2 border border-line rounded-2xl p-4 space-y-2.5">{children}</div>
    </section>
  );
}

export default function AnalyticsDashboard() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // AI Re-weighting state
  const [activeWeights, setActiveWeights] = useState({});
  const [selectedCategory, setSelectedCategory] = useState("Business Analyst");
  const [weightHistory, setWeightHistory] = useState([]);
  const [reweighting, setReweighting] = useState(false);

  const fetchWeightsInfo = async () => {
    try {
      const w = await getActiveWeights();
      setActiveWeights(w.active_weights || {});
      const h = await getWeightsHistory();
      setWeightHistory(h.weights || []);
    } catch (err) {
      // weights info failure is non-fatal
    }
  };

  useEffect(() => {
    getAnalytics().then(setData).catch((e) => setError(e.message));
    fetchWeightsInfo();
  }, []);

  const handleTriggerReweight = async () => {
    setReweighting(true);
    try {
      const res = await triggerReweight(selectedCategory);
      if (res.status === "insufficient_feedback") {
        toast(
          res.reason || `Need at least 6 Hired/Rejected decisions for "${selectedCategory}" to re-weight. Keep reviewing candidates!`,
          "warn"
        );
      } else if (res.status === "promoted") {
        toast(`✓ Weights updated! Keyword: ${Math.round(res.keyword_weight * 100)}%, Semantic: ${Math.round(res.semantic_weight * 100)}%`, "success");
        fetchWeightsInfo();
      } else {
        toast(res.reason || "Re-weighting step completed.", "success");
        fetchWeightsInfo();
      }
    } catch (err) {
      toast(err.message || "Re-weighting failed. Please try again.", "error");
    } finally {
      setReweighting(false);
    }
  };

  if (error)
    return (
      <div className="max-w-3xl mx-auto">
        <EmptyState icon={ShieldAlert} tone="bad" title="Couldn't load analytics" description={error} />
      </div>
    );

  if (!data) {
    return (
      <div className="max-w-3xl mx-auto space-y-8" aria-live="polite" aria-busy="true">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <SkeletonStatCard key={i} />
          ))}
        </div>
        <div className="skeleton h-40 w-full rounded-2xl" />
      </div>
    );
  }

  if (data.total_candidates === 0) {
    return (
      <div className="max-w-3xl mx-auto">
        <EmptyState
          icon={LineChart}
          title="No data yet"
          description="Once you upload resumes and rank a job description, this dashboard will show volumes, score distribution, in-demand skills, and your hiring funnel at a glance."
        />
      </div>
    );
  }

  const maxSkillCount = Math.max(...data.top_skills.map((s) => s.count), 1);
  const funnel = data.hiring_funnel;
  const currentCategoryWeights = activeWeights[selectedCategory] || { keyword_weight: 0.4, semantic_weight: 0.6 };

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Top Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={Users} label="Resumes processed" value={data.total_candidates} />
        <StatCard icon={Briefcase} label="Jobs created" value={data.total_jobs} />
        <StatCard icon={Target} label="Matches computed" value={data.total_matches_computed} />
      </div>

      {/* Hiring Funnel & Score Distribution */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <Panel title="Hiring Funnel Decisions">
          <BarRow label="Evaluated" value={funnel.matches_computed} max={funnel.matches_computed} />
          <BarRow label="Reviewed" value={funnel.reviewed} max={funnel.matches_computed} colorClass="bg-sky-400" />
          <BarRow label="Hired" value={funnel.hired} max={funnel.matches_computed} colorClass="bg-good" />
          <BarRow label="Rejected" value={funnel.rejected} max={funnel.matches_computed} colorClass="bg-bad" />
          <BarRow label="Pending" value={funnel.pending} max={funnel.matches_computed} colorClass="bg-ink-faint" />
        </Panel>

        <Panel title="Score Distribution">
          <BarRow label="High confidence" value={data.score_distribution.high_confidence} max={data.total_matches_computed} colorClass="bg-good" />
          <BarRow label="Moderate" value={data.score_distribution.moderate} max={data.total_matches_computed} colorClass="bg-warn" />
          <BarRow label="Weak" value={data.score_distribution.weak} max={data.total_matches_computed} colorClass="bg-bad" />
        </Panel>
      </div>

      {/* Most In-Demand Skills */}
      <section>
        <h2 className="text-base font-display font-semibold text-ink mb-3 flex items-center gap-2">
          <BarChart3 size={16} className="text-ink-muted" /> Most In-Demand Skills in Candidate Pool
        </h2>
        <div className="bg-surface-2 border border-line rounded-2xl p-4 space-y-2.5">
          {data.top_skills.length === 0 && <p className="text-ink-faint text-sm">No candidates uploaded yet.</p>}
          {data.top_skills.map((s) => (
            <BarRow key={s.skill} label={s.skill} value={s.count} max={maxSkillCount} />
          ))}
        </div>
      </section>

      {/* AI Scoring Engine & Feedback Re-weighting Panel */}
      <section className="bg-surface-2 border border-accent/30 rounded-2xl p-5 sm:p-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-display font-bold text-ink flex items-center gap-2">
              <Cpu size={18} className="text-accent" /> AI Hybrid Scoring & Feedback Loop Optimization
            </h2>
            <p className="text-xs text-ink-muted mt-0.5">
              The matching engine combines Keyword Matching (NER/TF-IDF) and Semantic SBERT embeddings. Recruiter decisions adapt weights dynamically.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-surface-1 border border-line text-xs font-semibold text-ink focus:outline-none focus:border-accent"
            >
              <option value="Business Analyst">Business Analyst</option>
              <option value="Full Stack Developer">Full Stack Developer</option>
              <option value="Project Manager">Project Manager</option>
              <option value="Software Engineer">Software Engineer</option>
              <option value="General">General</option>
            </select>

            <Button
              variant="primary"
              size="sm"
              icon={RefreshCw}
              loading={reweighting}
              onClick={handleTriggerReweight}
            >
              Trigger Re-weight
            </Button>
          </div>
        </div>

        {/* Info note about feedback requirement */}
        <div className="flex items-start gap-2 text-xs text-ink-muted bg-surface-1 rounded-xl px-3 py-2.5 border border-line/60">
          <AlertCircle size={13} className="text-blue-400 shrink-0 mt-0.5" />
          <span>
            Re-weighting needs <strong className="text-white">at least 6 Hired / Rejected decisions</strong> for the selected category.
            Go to Rankings → mark candidates as <strong className="text-white">Hire</strong> or <strong className="text-white">Reject</strong>, then return here and re-run.
          </span>
        </div>

        {/* Current Active Formula Display */}
        <div className="bg-surface-1 border border-line rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-ink-muted font-medium">Active Formula for {selectedCategory}:</span>
            <span className="text-accent font-mono font-semibold">
              Score = ({Math.round(currentCategoryWeights.keyword_weight * 100)}% Keyword) + ({Math.round(currentCategoryWeights.semantic_weight * 100)}% Semantic)
            </span>
          </div>

          {/* Dual Progress Bar */}
          <div className="h-3 rounded-full bg-surface-3 flex overflow-hidden">
            <div
              className="bg-accent h-full transition-all duration-500"
              style={{ width: `${currentCategoryWeights.keyword_weight * 100}%` }}
              title={`Keyword Weight: ${Math.round(currentCategoryWeights.keyword_weight * 100)}%`}
            />
            <div
              className="bg-emerald-500 h-full transition-all duration-500"
              style={{ width: `${currentCategoryWeights.semantic_weight * 100}%` }}
              title={`Semantic Weight: ${Math.round(currentCategoryWeights.semantic_weight * 100)}%`}
            />
          </div>

          <div className="flex items-center justify-between text-[11px] text-ink-muted">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-accent inline-block" /> Keyword Overlap ({Math.round(currentCategoryWeights.keyword_weight * 100)}%)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" /> Semantic Vectors ({Math.round(currentCategoryWeights.semantic_weight * 100)}%)
            </span>
          </div>
        </div>

        {/* Weight History Audit Trail */}
        {weightHistory.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-line/60">
            <h3 className="text-xs font-semibold text-ink-muted flex items-center gap-1.5">
              <History size={13} /> Weight Audit Trail & Regression Checks
            </h3>
            <div className="max-h-44 overflow-y-auto divide-y divide-line/40 border border-line rounded-xl bg-surface-1">
              {weightHistory.slice(0, 5).map((w) => (
                <div key={w.id} className="p-2.5 text-xs flex items-center justify-between gap-3">
                  <div>
                    <span className="font-semibold text-ink">{w.category}</span>
                    <span className="text-ink-muted text-[11px] ml-2">
                      (KW: {w.keyword_weight}, Sem: {w.semantic_weight})
                    </span>
                    <p className="text-[11px] text-ink-faint mt-0.5">{w.reason || "Automated optimization proposal"}</p>
                  </div>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      w.status === "active"
                        ? "bg-good/15 text-good"
                        : w.status === "superseded"
                        ? "bg-surface-3 text-ink-muted"
                        : "bg-warn/15 text-warn"
                    }`}
                  >
                    {w.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

