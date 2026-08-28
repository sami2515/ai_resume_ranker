// Every non-happy-path screen state (master doc Section 3.2, Screen 8) gets
// real designed content -- an icon, an explanation, and where relevant an
// action -- never a blank panel or a raw error string.
export default function EmptyState({ icon: Icon, title, description, action, tone = "default" }) {
  const toneClass = {
    default: "text-ink-faint bg-surface-3",
    warn: "text-warn bg-warn/10",
    bad: "text-bad bg-bad/10",
  }[tone];

  return (
    <div className="flex flex-col items-center text-center py-14 px-6">
      {Icon && (
        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center mb-4 ${toneClass}`}>
          <Icon size={22} />
        </div>
      )}
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {description && <p className="text-sm text-ink-muted mt-1.5 max-w-sm leading-relaxed">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
