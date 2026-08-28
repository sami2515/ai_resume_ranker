import { useState } from "react";
import { Mail, Lock, User, ArrowRight, Cpu, Sparkles, Shield, CheckCircle2 } from "lucide-react";
import Button from "./ui/Button";
import { login, register, clearToken } from "../api";

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [busy, setBusy] = useState(false);

  const handleNameChange = (e) => {
    const rawVal = e.target.value;
    const cleanVal = rawVal.replace(/[0-9]/g, "");
    if (rawVal !== cleanVal) {
      setError("Numbers are not allowed in the Full Name field.");
    } else if (error && error.includes("Numbers are not allowed")) {
      setError(null);
    }
    setFullName(cleanVal);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (mode === "register") {
      if (!fullName.trim()) {
        setError("Full name is required.");
        return;
      }
      if (/\d/.test(fullName)) {
        setError("Full name cannot contain numbers.");
        return;
      }
    }

    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Please enter a valid email address.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setBusy(true);
    try {
      if (mode === "login") {
        const recruiter = await login({ email, password });
        onAuthenticated(recruiter);
      } else {
        await register({ email, password, fullName });
        clearToken();
        setSuccess("Account created successfully! Please enter your password to log in.");
        setPassword("");
        setFullName("");
        setMode("login");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
      {/* ── Ambient Background Glows ───────────────────────────────────── */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Primary sapphire glow — top left */}
        <div
          className="absolute -top-40 -left-40 w-[500px] h-[500px] rounded-full opacity-20 blur-3xl"
          style={{ background: "radial-gradient(circle, #2563EB 0%, transparent 70%)" }}
        />
        {/* Emerald accent — bottom right */}
        <div
          className="absolute -bottom-32 -right-32 w-[420px] h-[420px] rounded-full opacity-12 blur-3xl"
          style={{ background: "radial-gradient(circle, #10B981 0%, transparent 70%)" }}
        />
        {/* Subtle center depth */}
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full opacity-8 blur-3xl"
          style={{ background: "radial-gradient(circle, #1E3A5F 0%, transparent 65%)" }}
        />
        {/* Faint grid pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.025]"
          style={{
            backgroundImage: "linear-gradient(#2563EB 1px, transparent 1px), linear-gradient(90deg, #2563EB 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
      </div>

      {/* ── Main Card ───────────────────────────────────────────────────── */}
      <div className="w-full max-w-sm relative z-10 animate-fade-up">
        {/* Logo & Brand */}
        <div className="flex flex-col items-center mb-7">
          <div className="relative mb-4">
            <img
              src="/logo.png"
              alt="AI Resume Ranker Logo"
              className="w-24 h-24 sm:w-28 sm:h-28 object-contain drop-shadow-2xl rounded-2xl"
            />
            {/* Glow under logo */}
            <div
              className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-16 h-4 blur-xl opacity-60 rounded-full"
              style={{ background: "#2563EB" }}
            />
          </div>

          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs font-mono font-bold tracking-wider uppercase px-2 py-0.5 rounded-md bg-accent/20 text-blue-400 border border-accent/40 shadow-sm">
              AI
            </span>
            <h1 className="text-2xl sm:text-3xl font-display font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-200 bg-clip-text text-transparent">
              Resume<span className="text-blue-400 font-black">Ranker</span>
            </h1>
          </div>
          <p className="text-ink-muted text-center text-xs sm:text-sm">
            Enterprise Talent Intelligence & Recruiter Suite
          </p>

          {/* Feature pills */}
          <div className="flex items-center gap-2 mt-3 flex-wrap justify-center">
            {[
              { icon: Cpu, label: "SBERT AI Engine" },
              { icon: Sparkles, label: "Hybrid Ranking" },
              { icon: Shield, label: "Secure & Private" },
            ].map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-surface-2 border border-line text-ink-muted"
              >
                <Icon size={9} className="text-blue-400" /> {label}
              </span>
            ))}
          </div>
        </div>

        {/* Mode Toggle */}
        <div className="flex mb-5 border border-line rounded-xl overflow-hidden p-1 bg-surface-2">
          {["login", "register"].map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(null); setSuccess(null); }}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors ${
                mode === m ? "bg-accent text-white shadow-glow" : "text-ink-muted hover:text-ink"
              }`}
            >
              {m === "login" ? "Log in" : "Register"}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3.5 bg-surface-2 border border-line rounded-2xl p-5 shadow-panel">
          {success && (
            <p className="text-emerald-400 text-xs bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-3 py-2 flex items-center gap-2" role="status">
              <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
              {success}
            </p>
          )}

          {mode === "register" && (
            <div>
              <label htmlFor="auth-name" className="text-xs font-medium text-ink-muted block mb-1.5">
                Full name
              </label>
              <div className="relative">
                <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
                <input
                  id="auth-name"
                  type="text"
                  value={fullName}
                  onChange={handleNameChange}
                  placeholder="e.g. Sarah Khan"
                  className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-surface-1 border border-line text-white placeholder-ink-faint focus:outline-none focus:border-accent transition-colors"
                />
              </div>
            </div>
          )}

          <div>
            <label htmlFor="auth-email" className="text-xs font-medium text-ink-muted block mb-1.5">Email</label>
            <div className="relative">
              <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
              <input
                id="auth-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-surface-1 border border-line text-white placeholder-ink-faint focus:outline-none focus:border-accent transition-colors"
              />
            </div>
          </div>

          <div>
            <label htmlFor="auth-password" className="text-xs font-medium text-ink-muted block mb-1.5">Password</label>
            <div className="relative">
              <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
              <input
                id="auth-password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
                className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-surface-1 border border-line text-white placeholder-ink-faint focus:outline-none focus:border-accent transition-colors"
              />
            </div>
          </div>

          {error && (
            <p className="text-bad text-sm bg-bad/10 border border-bad/30 rounded-xl px-3 py-2" role="alert">
              {error}
            </p>
          )}

          <Button type="submit" variant="primary" size="lg" loading={busy} icon={busy ? undefined : ArrowRight} className="w-full">
            {busy ? "Please wait..." : mode === "login" ? "Log in to Dashboard" : "Create Account"}
          </Button>
        </form>

        {/* Footer note */}
        <p className="text-center text-[11px] text-ink-faint mt-4">
          AI Resume Ranker · TechWiz Competition · Aptech Limited
        </p>
      </div>
    </div>
  );
}
