import { useEffect, useRef } from "react";
import { AlertTriangle } from "lucide-react";
import Button from "./Button";

// Cross-screen UX rule (master doc Section 3.8): every destructive or
// hard-to-reverse action requires a confirmation step -- a real dialog with
// a designed state, not the browser's own window.confirm().
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = true,
  onConfirm,
  onCancel,
}) {
  const cancelRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
    const onKey = (e) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-fade-up" onClick={onCancel} />
      <div className="relative w-full max-w-sm rounded-2xl border border-line bg-surface-2 p-6 shadow-panel animate-fade-up">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${danger ? "bg-bad/10 text-bad" : "bg-accent/10 text-accent"}`}>
          <AlertTriangle size={20} />
        </div>
        <h2 id="confirm-title" className="text-base font-semibold text-ink">
          {title}
        </h2>
        <p className="text-sm text-ink-muted mt-1.5 leading-relaxed">{description}</p>
        <div className="flex justify-end gap-2 mt-6">
          <Button ref={cancelRef} variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
