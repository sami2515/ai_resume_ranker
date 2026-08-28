import { Search, X } from "lucide-react";
import SkillPill from "./SkillPill";

// FR-05: keyword search + skill multi-select chips + experience/score
// sliders. Master doc Section 3.2 calls this out as its own inventoried
// screen element (#5), pinned above the ranked list.
export default function SearchFilterBar({ filters, onChange, maxExperience, availableSkills = [] }) {
  const { keyword, minExperience, minScore, skills } = filters;
  const hasActiveFilters = keyword || minExperience > 0 || minScore > 0 || skills.length > 0;

  const toggleSkill = (skill) => {
    const next = skills.includes(skill) ? skills.filter((s) => s !== skill) : [...skills, skill];
    onChange({ ...filters, skills: next });
  };

  return (
    <div className="bg-surface-2 border border-line rounded-2xl p-4 sm:p-5 space-y-4">
      <div className="flex flex-wrap gap-5 items-end">
        <div className="flex-1 min-w-[200px]">
          <label htmlFor="search-keyword" className="text-xs font-medium text-ink-muted block mb-1.5">
            Search (name, skill, filename)
          </label>
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input
              id="search-keyword"
              type="text"
              value={keyword}
              onChange={(e) => onChange({ ...filters, keyword: e.target.value })}
              placeholder="e.g. React, Candidate21..."
              className="w-full pl-9 pr-3 py-2 rounded-xl bg-surface-1 border border-line text-ink text-sm placeholder-ink-faint focus:outline-none focus:border-accent transition-colors"
            />
          </div>
        </div>

        <div className="min-w-[170px]">
          <label htmlFor="filter-experience" className="text-xs font-medium text-ink-muted block mb-1.5">
            Min. experience: <span className="text-ink tabular-nums">{minExperience} yrs</span>
          </label>
          <input
            id="filter-experience"
            type="range"
            min={0}
            max={Math.max(maxExperience, 1)}
            value={minExperience}
            onChange={(e) => onChange({ ...filters, minExperience: Number(e.target.value) })}
            className="w-full accent-accent"
          />
        </div>

        <div className="min-w-[170px]">
          <label htmlFor="filter-score" className="text-xs font-medium text-ink-muted block mb-1.5">
            Min. composite score: <span className="text-ink tabular-nums">{minScore}</span>
          </label>
          <input
            id="filter-score"
            type="range"
            min={0}
            max={100}
            value={minScore}
            onChange={(e) => onChange({ ...filters, minScore: Number(e.target.value) })}
            className="w-full accent-accent"
          />
        </div>

        {hasActiveFilters && (
          <button
            onClick={() => onChange({ keyword: "", minExperience: 0, minScore: 0, skills: [] })}
            className="inline-flex items-center gap-1 text-sm text-ink-muted hover:text-ink transition-colors"
          >
            <X size={13} /> Clear filters
          </button>
        )}
      </div>

      {availableSkills.length > 0 && (
        <div>
          <span className="text-xs font-medium text-ink-muted block mb-1.5">Filter by skill</span>
          <div className="flex flex-wrap gap-1.5">
            {availableSkills.map((skill) => (
              <SkillPill key={skill} label={skill} onClick={() => toggleSkill(skill)} selected={skills.includes(skill)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
