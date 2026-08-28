import { useEffect, useState, useRef } from "react";
import {
  UploadCloud,
  ListOrdered,
  BarChart3,
  LogOut,
  CircleDot,
  Briefcase,
  UserCheck,
  Users,
  Menu,
  X,
  ChevronRight,
  ChevronDown,
  User,
  ShieldCheck,
  Loader2,
} from "lucide-react";
import AuthScreen from "./components/AuthScreen";
import UploadWizard from "./components/UploadWizard";
import ResultsView from "./components/ResultsView";
import JobsView from "./components/JobsView";
import PipelineView from "./components/PipelineView";
import CandidatePoolView from "./components/CandidatePoolView";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import { getHealth, getCurrentRecruiter, listJobs, getToken, logout } from "./api";

const TABS = [
  {
    id: "upload",
    label: "Upload",
    fullLabel: "Upload & Match",
    desc: "Bulk resume parsing & instant AI ranking",
    icon: UploadCloud,
  },
  {
    id: "jobs",
    label: "Jobs",
    fullLabel: "Job Postings",
    desc: "Manage positions & track applicant counts",
    icon: Briefcase,
  },
  {
    id: "results",
    label: "Rankings",
    fullLabel: "Ranked Results",
    desc: "Match scores, explainability & actions",
    icon: ListOrdered,
  },
  {
    id: "pipeline",
    label: "Pipeline",
    fullLabel: "Hiring Pipeline",
    desc: "Track Hired & Rejected applicants",
    icon: UserCheck,
  },
  {
    id: "candidates",
    label: "Talent Pool",
    fullLabel: "Candidate Pool",
    desc: "Global searchable resume database",
    icon: Users,
  },
  {
    id: "analytics",
    label: "Analytics",
    fullLabel: "Analytics & AI",
    desc: "Funnel stats & model re-weighting",
    icon: BarChart3,
  },
];

export default function App() {
  const [recruiter, setRecruiter] = useState(undefined);
  const [tab, setTab] = useState("upload");
  const [jobId, setJobId] = useState(null);
  const [health, setHealth] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const profileMenuRef = useRef(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "unreachable" }));
  }, []);

  useEffect(() => {
    if (!getToken()) {
      setRecruiter(null);
      return;
    }

    // Safety fallback timer — prevent infinite blank/loading screen if API hangs or is unreachable
    const safetyTimer = setTimeout(() => {
      setRecruiter((prev) => (prev === undefined ? null : prev));
    }, 2500);

    getCurrentRecruiter()
      .then((rec) => {
        clearTimeout(safetyTimer);
        setRecruiter(rec);
        listJobs()
          .then((res) => {
            if (res.jobs && res.jobs.length > 0) {
              setJobId(res.jobs[0].id);
            }
          })
          .catch(() => {});
      })
      .catch(() => {
        clearTimeout(safetyTimer);
        setRecruiter(null);
      });

    return () => clearTimeout(safetyTimer);
  }, []);

  useEffect(() => {
    const onUnauthorized = () => setRecruiter(null);
    window.addEventListener("auth:unauthorized", onUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", onUnauthorized);
  }, []);

  // Cross-component navigation via custom events
  useEffect(() => {
    const onNavigateTab = (e) => handleTabChange(e.detail);
    window.addEventListener("navigate:tab", onNavigateTab);
    return () => window.removeEventListener("navigate:tab", onNavigateTab);
  }, []);

  // Always scroll to top whenever switching tabs or selecting a new job
  useEffect(() => {
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [tab, jobId]);

  // Click outside to close profile dropdown
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target)) {
        setProfileDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleRanked = (newJobId) => {
    setJobId(newJobId);
    setTab("results");
    setMobileMenuOpen(false);
  };

  const handleSelectJob = (selectedJobId) => {
    setJobId(selectedJobId);
    setTab("results");
    setMobileMenuOpen(false);
  };

  const handleTabChange = (tabId) => {
    setTab(tabId);
    setMobileMenuOpen(false);
  };

  const handleLogout = () => {
    logout();
    setRecruiter(null);
    setJobId(null);
    setTab("upload");
    setMobileMenuOpen(false);
    setProfileDropdownOpen(false);
  };

  if (recruiter === undefined) {
    return (
      <div className="min-h-screen bg-base flex flex-col items-center justify-center p-4">
        <div className="flex items-center gap-2 mb-3">
          <img src="/logo.png" alt="AI Resume Ranker" className="w-14 h-14 object-contain" />
        </div>
        <div className="flex items-center gap-2 text-ink-muted text-sm font-medium">
          <Loader2 size={16} className="animate-spin text-accent" />
          <span>Loading AI Resume Ranker...</span>
        </div>
      </div>
    );
  }
  if (recruiter === null) {
    return <AuthScreen onAuthenticated={setRecruiter} />;
  }

  const activeTabObj = TABS.find((t) => t.id === tab) || TABS[0];
  const userInitials = (recruiter.full_name || recruiter.email || "U").charAt(0).toUpperCase();

  return (
    <div className="min-h-screen bg-base text-ink flex flex-col">
      {/* Sticky Top Header */}
      <header className="border-b border-line/70 sticky top-0 z-30 bg-base/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-2.5 flex items-center justify-between gap-2 sm:gap-4">
          {/* Logo & Brand Info */}
          <div className="flex items-center gap-3 shrink-0">
            <img
              src="/logo.png"
              alt="Logo"
              className="w-10 h-10 sm:w-11 sm:h-11 object-contain shrink-0 rounded-xl drop-shadow-md"
            />
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5 leading-none">
                <span className="text-[10px] sm:text-[11px] font-mono font-bold tracking-wider uppercase px-1.5 py-0.5 rounded bg-accent/20 text-blue-400 border border-accent/40 shadow-sm">
                  AI
                </span>
                <span className="text-base sm:text-lg font-display font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-200 bg-clip-text text-transparent whitespace-nowrap">
                  Resume<span className="text-blue-400 font-black">Ranker</span>
                </span>
              </div>
              <span className="text-[10px] text-ink-faint tracking-wider uppercase font-medium mt-1 hidden sm:block">
                Talent Intelligence Suite
              </span>
            </div>
          </div>

          {/* Desktop Navigation Links (Compact & Centered) */}
          <nav className="hidden md:flex items-center gap-1 bg-surface-2 border border-line rounded-xl p-1">
            {TABS.map((t) => {
              const Icon = t.icon;
              const disabled = t.id === "results" && jobId === null;
              const isActive = tab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => handleTabChange(t.id)}
                  disabled={disabled}
                  title={disabled ? "Run AI Ranking first — go to Upload & Match to rank candidates" : t.desc}
                  className={`inline-flex items-center gap-1.5 px-2.5 lg:px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                    isActive
                      ? "bg-accent text-white shadow-glow"
                      : "text-ink-muted hover:text-ink hover:bg-surface-3 disabled:text-ink-faint/30 disabled:cursor-not-allowed disabled:hover:bg-transparent"
                  }`}
                >
                  <Icon size={14} className="shrink-0" />
                  <span>{t.label}</span>
                  {disabled && <span className="text-[9px] opacity-50 ml-0.5">🔒</span>}
                </button>
              );
            })}
          </nav>

          {/* Right Area: Profile Capsule & Actions */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Desktop User Profile & Sign Out */}
            <div className="hidden md:flex items-center gap-2 pl-2 sm:pl-3 border-l border-line/70 relative" ref={profileMenuRef}>
              {/* Profile Capsule Trigger */}
              <button
                type="button"
                onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                className={`group flex items-center gap-2.5 p-1 pl-1.5 pr-2.5 rounded-xl border transition-all ${
                  profileDropdownOpen
                    ? "bg-surface-3 border-accent/60 shadow-glow"
                    : "bg-surface-2 hover:bg-surface-3 border-line hover:border-accent/40"
                }`}
                title="Account Options"
              >
                {/* Gradient Avatar */}
                <div className="relative shrink-0">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 border border-blue-400/40 flex items-center justify-center text-xs font-bold text-white shadow-sm">
                    {userInitials}
                  </div>
                  <span className="absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full bg-good border-2 border-base" />
                </div>

                {/* Recruiter Details */}
                <div className="text-left min-w-0">
                  <p className="text-xs font-semibold text-white group-hover:text-blue-300 transition-colors truncate max-w-[90px] lg:max-w-[120px] leading-tight">
                    {recruiter.full_name || recruiter.email.split("@")[0]}
                  </p>
                  <p className="text-[10px] text-ink-muted leading-tight truncate">
                    Recruiter
                  </p>
                </div>

                <ChevronDown
                  size={13}
                  className={`text-ink-muted transition-transform duration-200 ${
                    profileDropdownOpen ? "rotate-180 text-blue-400" : "group-hover:text-ink"
                  }`}
                />
              </button>

              {/* Quick Sign Out Button */}
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-xs font-medium text-ink-muted hover:text-bad bg-surface-2 hover:bg-bad/10 border border-line hover:border-bad/30 px-2.5 py-1.5 rounded-xl transition-all shadow-sm"
                aria-label="Log out"
                title="Sign out of account"
              >
                <LogOut size={13} />
                <span className="hidden xl:inline">Sign Out</span>
              </button>

              {/* Glassmorphic Profile Dropdown Menu */}
              {profileDropdownOpen && (
                <div className="absolute right-0 top-full mt-2 w-64 rounded-2xl bg-surface-2/95 backdrop-blur-xl border border-line shadow-2xl p-3.5 space-y-3 z-50 animate-in fade-in zoom-in-95 duration-150">
                  {/* User Identity Header */}
                  <div className="flex items-center gap-3 pb-3 border-b border-line/70">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 border border-blue-400/40 flex items-center justify-center text-sm font-bold text-white shadow-md shrink-0">
                      {userInitials}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <p className="text-xs font-bold text-white truncate">{recruiter.full_name || "Recruiter"}</p>
                        <span className="text-[9px] font-semibold px-1.5 py-0.2 rounded bg-accent/20 text-blue-400 border border-accent/40">
                          HR
                        </span>
                      </div>
                      <p className="text-[11px] text-ink-muted truncate mt-0.5">{recruiter.email}</p>
                    </div>
                  </div>

                  {/* System & Engine Status */}
                  <div className="bg-surface-1/80 border border-line/60 rounded-xl p-2.5 space-y-1.5 text-[11px]">
                    <div className="flex items-center justify-between text-ink-muted">
                      <span>Account Role</span>
                      <span className="text-white font-medium">Enterprise Recruiter</span>
                    </div>
                    <div className="flex items-center justify-between text-ink-muted">
                      <span>AI Model Engine</span>
                      <span className="text-good font-semibold flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-good inline-block" /> SBERT Active
                      </span>
                    </div>
                  </div>

                  {/* Dropdown Logout Button */}
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-bad/10 hover:bg-bad/20 text-bad border border-bad/30 text-xs font-semibold transition-colors"
                  >
                    <LogOut size={14} /> Log Out of Account
                  </button>
                </div>
              )}
            </div>

            {/* Mobile / Tablet Menu Button (< 768px) */}
            <div className="flex items-center gap-1.5 md:hidden">
              <span className="text-[11px] font-semibold px-2 py-1 rounded-lg bg-surface-2 border border-line text-accent flex items-center gap-1">
                <activeTabObj.icon size={12} /> {activeTabObj.label}
              </span>

              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-1.5 rounded-xl bg-surface-2 border border-line text-ink hover:bg-surface-3 transition-colors"
                aria-label="Toggle navigation menu"
              >
                {mobileMenuOpen ? <X size={18} className="text-accent" /> : <Menu size={18} />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile & Tablet Dropdown Drawer (< 768px) */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-line bg-surface-2/95 backdrop-blur-xl px-4 py-4 space-y-3 animate-in slide-in-from-top-2 duration-150 shadow-2xl">
            <p className="text-[11px] font-bold text-ink-muted uppercase tracking-wider px-1">
              Select Workspace View
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {TABS.map((t) => {
                const Icon = t.icon;
                const disabled = t.id === "results" && jobId === null;
                const isActive = tab === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => handleTabChange(t.id)}
                    disabled={disabled}
                    className={`flex items-start gap-3 p-3 rounded-xl text-left transition-all ${
                      isActive
                        ? "bg-accent text-white shadow-glow"
                        : "bg-surface-1/80 border border-line/70 text-ink hover:border-accent/40 disabled:opacity-40 disabled:cursor-not-allowed"
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                        isActive ? "bg-white/20 text-white" : "bg-surface-3 text-accent"
                      }`}
                    >
                      <Icon size={16} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className={`text-xs font-semibold ${isActive ? "text-white" : "text-ink"}`}>
                        {t.fullLabel}
                      </p>
                      <p
                        className={`text-[11px] leading-tight truncate mt-0.5 ${
                          isActive ? "text-white/80" : "text-ink-muted"
                        }`}
                      >
                        {t.desc}
                      </p>
                    </div>
                    <ChevronRight size={14} className={isActive ? "text-white/80" : "text-ink-faint"} />
                  </button>
                );
              })}
            </div>

            {/* Recruiter Profile in Mobile Drawer */}
            <div className="pt-3 border-t border-line flex items-center justify-between px-1">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-8 h-8 rounded-full bg-surface-3 border border-line flex items-center justify-center text-xs font-bold text-accent shrink-0">
                  {(recruiter.full_name || recruiter.email || "U").charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-ink truncate">{recruiter.full_name || "Recruiter"}</p>
                  <p className="text-[10px] text-ink-muted truncate">{recruiter.email}</p>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="inline-flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg bg-bad/10 text-bad border border-bad/30 hover:bg-bad/20 transition-colors shrink-0 ml-2"
              >
                <LogOut size={13} /> Sign Out
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Page Context Header — shows what page you're on and what to do */}
      <div className="border-b border-line/40 bg-base/60">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/25 flex items-center justify-center shrink-0">
              <activeTabObj.icon size={15} className="text-accent" />
            </div>
            <div className="min-w-0">
              <h1 className="text-sm font-display font-bold text-white leading-tight">{activeTabObj.fullLabel}</h1>
              <p className="text-[11px] text-ink-muted leading-tight hidden sm:block">{activeTabObj.desc}</p>
            </div>
          </div>
          {/* Context-aware right badge */}
          {tab === "results" && jobId && (
            <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-accent/15 border border-accent/30 text-blue-300 shrink-0 hidden sm:inline-flex items-center gap-1.5">
              <CircleDot size={10} className="text-blue-400" /> Active Job #{jobId}
            </span>
          )}
          {tab === "upload" && (
            <span className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-good/10 border border-good/25 text-emerald-400 shrink-0 hidden sm:inline-flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> 3-Step Workflow
            </span>
          )}
          {tab === "candidates" && (
            <button
              onClick={() => handleTabChange("upload")}
              className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-accent/15 border border-accent/30 text-blue-300 shrink-0 hidden sm:inline-flex items-center gap-1 hover:bg-accent/25 transition-colors"
            >
              <UploadCloud size={11} /> Upload More
            </button>
          )}
          {tab === "analytics" && (
            <button
              onClick={() => handleTabChange("results")}
              className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-surface-2 border border-line text-ink-muted shrink-0 hidden sm:inline-flex items-center gap-1 hover:text-ink transition-colors"
            >
              <ListOrdered size={11} /> View Rankings
            </button>
          )}
          {tab === "pipeline" && (
            <button
              onClick={() => handleTabChange("upload")}
              className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-surface-2 border border-line text-ink-muted shrink-0 hidden sm:inline-flex items-center gap-1 hover:text-ink transition-colors"
            >
              <UploadCloud size={11} /> New Batch
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 flex-1 w-full">
        {tab === "upload" && <UploadWizard onRanked={handleRanked} />}
        {tab === "jobs" && (
          <JobsView onSelectJob={handleSelectJob} onNavigateUpload={() => setTab("upload")} />
        )}
        {tab === "results" && jobId !== null && (
          <ResultsView jobId={jobId} onSwitchJob={setJobId} />
        )}
        {tab === "pipeline" && <PipelineView onSelectJob={handleSelectJob} />}
        {tab === "candidates" && <CandidatePoolView onNavigateUpload={() => handleTabChange("upload")} />}
        {tab === "analytics" && <AnalyticsDashboard />}
      </main>
      {/* Footer */}
      <footer className="border-t border-line/40 bg-base/60 mt-auto">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="" className="w-5 h-5 object-contain opacity-60" />
            <span className="text-[11px] text-ink-faint font-medium">
              AI ResumeRanker · Powered by SBERT + TF-IDF · TechWiz 2026
            </span>
          </div>
          <span className="text-[11px] text-ink-faint">Aptech Limited · All Rights Reserved</span>
        </div>
      </footer>
    </div>
  );
}

