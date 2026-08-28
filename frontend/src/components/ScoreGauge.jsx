// Circular score gauge — upgraded with gradient stroke + confidence glow
import { getConfidenceMeta } from "../utils/confidence";

export default function ScoreGauge({ score, confidence, size = 64 }) {
  const radius = (size - 10) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedScore = Math.min(Math.max(score, 0), 100);
  const offset = circumference * (1 - clampedScore / 100);

  const meta = getConfidenceMeta(confidence);
  const band = {
    stroke: meta.strokeColor,
    glow: meta.glowColor,
    textColor: meta.textColor,
  };
  const gradId = `sg-grad-${Math.round(score)}-${(confidence || "").charAt(0)}`;

  return (
    <div
      className="relative shrink-0 flex items-center justify-center cursor-help"
      style={{ width: size, height: size }}
      title={`AI Match Score: ${Math.round(clampedScore)}/100 — ${confidence || "No confidence data"}`}
      aria-label={`Score ${Math.round(score)}, ${confidence}`}
    >
      {/* Outer glow ring */}
      <div
        className="absolute inset-0 rounded-full blur-sm opacity-60"
        style={{ boxShadow: `0 0 ${size * 0.28}px ${band.glow}` }}
      />

      <svg width={size} height={size} className="-rotate-90" style={{ position: "relative", zIndex: 1 }}>
        {/* Gradient definition */}
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={band.stroke} stopOpacity="0.6" />
            <stop offset="100%" stopColor={band.stroke} stopOpacity="1" />
          </linearGradient>
        </defs>

        {/* Track ring */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke="#1E293B"
          strokeWidth="7"
        />

        {/* Score arc with gradient */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none"
          stroke={`url(#${gradId})`}
          strokeWidth="7"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.7s cubic-bezier(0.16,1,0.3,1), stroke 0.4s" }}
        />
      </svg>

      {/* Center score number */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center leading-none"
        style={{ zIndex: 2 }}
      >
        <span
          className="font-display font-bold tabular-nums"
          style={{ fontSize: size * 0.275, color: band.textColor, lineHeight: 1 }}
        >
          {Math.round(clampedScore)}
        </span>
      </div>
    </div>
  );
}
