import { useEffect, useMemo, useState } from "react";
import {
  Users,
  Search,
  Download,
  Trash2,
  UserRound,
  Tag,
  Briefcase,
  GraduationCap,
  Award,
  Calendar,
  X,
  ShieldAlert,
  UploadCloud,
} from "lucide-react";
import SkillPill from "./SkillPill";
import CandidateProfile from "./CandidateProfile";
import Button from "./ui/Button";
import ConfirmDialog from "./ui/ConfirmDialog";
import EmptyState from "./ui/EmptyState";
import { SkeletonCandidateCard } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";
import { searchCandidates, downloadResume, deleteCandidate } from "../api";

export default function CandidatePoolView({ onNavigateUpload }) {
  const toast = useToast();
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [selectedSkill, setSelectedSkill] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [minExp, setMinExp] = useState(0);
  const [profileCandidateId, setProfileCandidateId] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);

  const fetchCandidates = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (searchKeyword.trim()) params.keyword = searchKeyword.trim();
      if (selectedSkill) params.skill = selectedSkill;
      if (selectedCategory) params.category = selectedCategory;
      if (minExp > 0) params.min_experience = minExp;

      const res = await searchCandidates(params);
      setCandidates(res.candidates || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCandidates();
  }, [searchKeyword, selectedSkill, selectedCategory, minExp]);

  const allSkills = useMemo(() => {
    const set = new Set();
    candidates.forEach((c) => (c.skills || []).forEach((s) => set.add(s)));
    return Array.from(set).sort();
  }, [candidates]);

  const allCategories = useMemo(() => {
    const set = new Set();
    candidates.forEach((c) => {
      if (c.predicted_category) set.add(c.predicted_category);
    });
    return Array.from(set).sort();
  }, [candidates]);

  const handleDownload = async (candidateId, filename) => {
    try {
      await downloadResume(candidateId, filename);
    } catch (e) {
      toast(e.message, "error");
    }
  };

  const confirmDelete = async () => {
    const id = pendingDelete;
    setPendingDelete(null);
    try {
      await deleteCandidate(id);
      setCandidates((prev) => prev.filter((c) => c.id !== id));
      toast("Candidate data deleted successfully.", "success");
    } catch (e) {
      toast(e.message, "error");
    }
  };

  const hasActiveFilters = searchKeyword || selectedSkill || selectedCategory || minExp > 0;

  const clearFilters = () => {
    setSearchKeyword("");
    setSelectedSkill("");
    setSelectedCategory("");
    setMinExp(0);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-display font-bold text-ink">Candidate Pool & Talent Database</h2>
          <p className="text-sm text-ink-muted mt-1">
            Search and browse the entire parsed talent pool across all uploaded resumes.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-surface-2 border border-line text-xs font-semibold text-ink">
          <Users size={14} className="text-accent" />
          <span>{candidates.length} Profiles in Pool</span>
        </div>
      </div>

      {/* Search & Filters Bar */}
      <div className="bg-surface-2 border border-line rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap gap-4 items-end">
          {/* Keyword Search */}
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs font-medium text-ink-muted block mb-1.5">
              Search by candidate name, skill, or keyword
            </label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
              <input
                type="text"
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                placeholder="e.g. React, Python, Business Analyst..."
                className="w-full pl-9 pr-3 py-2 rounded-xl bg-surface-1 border border-line text-ink text-sm placeholder-ink-faint focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          {/* Category Filter */}
          <div className="min-w-[170px]">
            <label className="text-xs font-medium text-ink-muted block mb-1.5">Role Category</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-surface-1 border border-line text-ink text-sm focus:outline-none focus:border-accent"
            >
              <option value="">All Categories</option>
              {allCategories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* Experience Filter */}
          <div className="min-w-[150px]">
            <label className="text-xs font-medium text-ink-muted block mb-1.5">
              Min. Experience: <span className="text-ink font-semibold">{minExp} yrs</span>
            </label>
            <input
              type="range"
              min={0}
              max={15}
              value={minExp}
              onChange={(e) => setMinExp(Number(e.target.value))}
              className="w-full accent-accent"
            />
          </div>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="inline-flex items-center gap-1 text-xs text-ink-muted hover:text-ink pb-2 transition-colors"
            >
              <X size={13} /> Clear filters
            </button>
          )}
        </div>

        {/* Skill Tag Filters */}
        {allSkills.length > 0 && (
          <div className="pt-2 border-t border-line/60">
            <span className="text-xs font-medium text-ink-muted block mb-1.5">Popular Skills:</span>
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
              {allSkills.slice(0, 25).map((skill) => (
                <SkillPill
                  key={skill}
                  label={skill}
                  selected={selectedSkill === skill}
                  onClick={() => setSelectedSkill(selectedSkill === skill ? "" : skill)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Error state */}
      {error && (
        <EmptyState icon={ShieldAlert} tone="bad" title="Couldn't load candidates" description={error} />
      )}

      {/* Loading state */}
      {loading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <SkeletonCandidateCard key={i} />
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && candidates.length === 0 && (
        <EmptyState
          icon={Users}
          title={hasActiveFilters ? "No matches found" : "No candidates yet"}
          description={
            hasActiveFilters
              ? "Try broadening your search or removing filters."
              : "Upload resume documents (.pdf / .docx) in the Upload tab to build your talent pool."
          }
          action={
            hasActiveFilters ? (
              <Button variant="secondary" size="sm" onClick={clearFilters}>
                Clear Filters
              </Button>
            ) : (
              <Button variant="primary" size="sm" icon={UploadCloud} onClick={onNavigateUpload}>
                Upload Resumes
              </Button>
            )
          }
        />
      )}

      {/* Candidate Cards */}
      {!loading && !error && candidates.length > 0 && (
        <div className="space-y-3">
          {candidates.map((c) => (
            <div
              key={c.id}
              className="bg-surface-2 border border-line rounded-2xl p-5 flex flex-col sm:flex-row gap-4 sm:items-center justify-between transition-all hover:border-ink-faint/60 hover:shadow-panel"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => setProfileCandidateId(c.id)}
                    className="text-ink font-display font-bold text-base hover:text-accent transition-colors text-left"
                  >
                    {c.full_name || c.resume_filename}
                  </button>

                  {c.predicted_category && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-surface-3 text-ink-muted border border-line">
                      <Tag size={10} /> {c.predicted_category}
                    </span>
                  )}
                </div>

                {/* Candidate meta */}
                <div className="flex items-center gap-3 text-xs text-ink-muted mt-1.5 flex-wrap">
                  <span>
                    Experience: <strong className="text-ink">{c.experience_years || 0} yrs</strong>
                  </span>
                  <span>•</span>
                  <span className="truncate max-w-[200px]">{c.email || "Email Masked"}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Calendar size={11} className="text-ink-faint" />
                    {c.created_at ? new Date(c.created_at).toLocaleDateString() : "Uploaded"}
                  </span>
                </div>

                {/* Skills tags */}
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {(c.skills || []).slice(0, 8).map((skill) => (
                    <SkillPill key={skill} label={skill} variant="neutral" />
                  ))}
                  {(c.skills || []).length > 8 && (
                    <span className="text-xs text-ink-faint self-center">
                      +{(c.skills || []).length - 8} more
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 self-end sm:self-auto shrink-0 pt-2 sm:pt-0">
                <Button
                  size="sm"
                  variant="ghost"
                  icon={UserRound}
                  onClick={() => setProfileCandidateId(c.id)}
                >
                  Profile
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={Download}
                  onClick={() => handleDownload(c.id, c.resume_filename)}
                >
                  Resume
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={Trash2}
                  onClick={() => setPendingDelete(c.id)}
                  className="hover:text-bad hover:bg-bad/10"
                >
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Candidate Profile Modal */}
      {profileCandidateId && (
        <CandidateProfile candidateId={profileCandidateId} onClose={() => setProfileCandidateId(null)} />
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this candidate's data?"
        description="This removes their resume, extracted profile, and all ranking history from the system permanently. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
