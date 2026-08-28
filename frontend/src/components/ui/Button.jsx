import { forwardRef } from "react";
import { Loader2 } from "lucide-react";

// Design system (master doc Section 3.1): one accent color, used only for
// primary actions -- every other variant stays neutral so the accent keeps
// its meaning across the whole app.
const VARIANTS = {
  primary:
    "bg-accent text-white shadow-glow hover:bg-accent-hover active:scale-[0.98] disabled:shadow-none",
  secondary:
    "bg-surface-2 text-ink border border-line hover:border-ink-faint hover:bg-surface-3 active:scale-[0.98]",
  ghost: "text-ink-muted hover:text-ink hover:bg-surface-2 active:scale-[0.98]",
  danger:
    "bg-bad/10 text-bad border border-bad/30 hover:bg-bad/20 active:scale-[0.98]",
};

const SIZES = {
  sm: "text-xs px-2.5 py-1.5 gap-1.5 rounded-lg",
  md: "text-sm px-4 py-2 gap-2 rounded-xl",
  lg: "text-sm px-5 py-2.5 gap-2 rounded-xl",
};

const Button = forwardRef(function Button(
  { variant = "secondary", size = "md", icon: Icon, loading = false, disabled = false, className = "", children, ...props },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-medium transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 className="animate-spin" size={size === "sm" ? 14 : 16} /> : Icon ? <Icon size={size === "sm" ? 14 : 16} /> : null}
      {children}
    </button>
  );
});

export default Button;
