import { Check } from "lucide-react";

const STYLES = {
  matched: "bg-good/10 text-good border-good/25",
  missing: "bg-surface-3 text-ink-faint border-line line-through decoration-ink-faint/60",
  neutral: "bg-surface-3 text-ink-muted border-line",
};

// Doubles as the FR-05 multi-select skill filter chip when `onClick` is
// passed -- one visual language for "skill" across the app (matched-skill
// pill on a card, missing-skill pill in the explainability drawer, and the
// clickable filter chip), instead of three different-looking components.
export default function SkillPill({ label, variant = "neutral", onClick, selected = false }) {
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-pressed={selected}
        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs border transition-colors ${
          selected ? "bg-accent/15 text-accent border-accent/50" : "bg-surface-3 text-ink-muted border-line hover:border-ink-faint hover:text-ink"
        }`}
      >
        {selected && <Check size={11} />}
        {label}
      </button>
    );
  }

  return <span className={`inline-block px-2.5 py-1 rounded-full text-xs border ${STYLES[variant]}`}>{label}</span>;
}
