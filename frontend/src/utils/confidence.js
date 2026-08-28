/**
 * Single source of truth for the 4-tier confidence system.
 * Directly maps backend nlp_pipeline.matching_engine.CONFIDENCE_BANDS exact labels
 * and provides robust fuzzy matching for legacy or short labels.
 */

export const CONFIDENCE_TIERS = {
  HIGH: {
    exactLabel: "High Confidence Match",
    shortLabel: "High Match",
    colorClass: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    strokeColor: "#10B981",
    glowColor: "#10B98155",
    textColor: "#10B981",
    gaugeLabel: "HIGH",
  },
  MODERATE: {
    exactLabel: "Moderate Match — Review Recommended",
    shortLabel: "Moderate Match",
    colorClass: "text-sky-400 bg-sky-500/10 border-sky-500/30",
    strokeColor: "#0EA5E9",
    glowColor: "#0EA5E944",
    textColor: "#0EA5E9",
    gaugeLabel: "MED",
  },
  PARTIAL: {
    exactLabel: "Partial / Weak Match — Secondary Pool",
    shortLabel: "Weak Match",
    colorClass: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    strokeColor: "#F59E0B",
    glowColor: "#F59E0B44",
    textColor: "#F59E0B",
    gaugeLabel: "WEAK",
  },
  NONE: {
    exactLabel: "No Match — Irrelevant",
    shortLabel: "No Match",
    colorClass: "text-rose-400 bg-rose-500/10 border-rose-500/30",
    strokeColor: "#F43F5E",
    glowColor: "#F43F5E44",
    textColor: "#F43F5E",
    gaugeLabel: "NONE",
  },
};

export function getConfidenceMeta(confidenceString) {
  if (!confidenceString) return CONFIDENCE_TIERS.NONE;

  const norm = String(confidenceString).trim().toLowerCase();

  if (norm.includes("high confidence") || norm.includes("high match")) {
    return CONFIDENCE_TIERS.HIGH;
  }
  if (norm.includes("moderate match") || norm.includes("moderate —") || norm.includes("moderate -") || norm.includes("moderate")) {
    return CONFIDENCE_TIERS.MODERATE;
  }
  if (norm.includes("partial") || norm.includes("secondary pool") || norm.includes("weak match") || norm.includes("weak")) {
    return CONFIDENCE_TIERS.PARTIAL;
  }
  if (norm.includes("no match") || norm.includes("irrelevant")) {
    return CONFIDENCE_TIERS.NONE;
  }

  return CONFIDENCE_TIERS.NONE;
}
