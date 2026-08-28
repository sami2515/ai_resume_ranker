import { createContext, useCallback, useContext, useRef, useState } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";

// Cross-screen UX rule (master doc Section 3.8): every action gets visible
// feedback, and error messages state what happened -- never a silent
// failure or a raw alert()/confirm(). One toast stack, one place errors and
// confirmations surface consistently across every screen.

const ToastContext = createContext(null);

const ICON = { success: CheckCircle2, error: XCircle, info: Info };
const COLOR = {
  success: "text-good border-good/30 bg-good/10",
  error: "text-bad border-bad/30 bg-bad/10",
  info: "text-accent border-accent/30 bg-accent/10",
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const counter = useRef(0);

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message, type = "info", timeout = 4500) => {
      const id = ++counter.current;
      setToasts((prev) => [...prev, { id, message, type }]);
      if (timeout) setTimeout(() => dismiss(id), timeout);
      return id;
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div
        className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 w-full max-w-sm"
        role="region"
        aria-live="polite"
        aria-label="Notifications"
      >
        {toasts.map((t) => {
          const Icon = ICON[t.type];
          return (
            <div
              key={t.id}
              className={`animate-fade-up flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm shadow-panel backdrop-blur bg-surface-2/95 ${COLOR[t.type]}`}
            >
              <Icon size={18} className="mt-0.5 shrink-0" />
              <p className="flex-1 text-ink">{t.message}</p>
              <button
                onClick={() => dismiss(t.id)}
                className="text-ink-faint hover:text-ink shrink-0"
                aria-label="Dismiss notification"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
