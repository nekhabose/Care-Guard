import { ArrowRight, ShieldPlus, TestTube2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  getApiBase,
  setApiBase,
  setDemoMode,
  setToken,
} from "../lib/auth";

export function Login() {
  const navigate = useNavigate();
  const [token, setTokenInput] = useState("");
  const [base, setBase] = useState(getApiBase());

  const signIn = (e: React.FormEvent) => {
    e.preventDefault();
    if (!token.trim()) return;
    setApiBase(base);
    setToken(token);
    setDemoMode(false);
    navigate("/", { replace: true });
  };

  const startDemo = () => {
    setDemoMode(true);
    navigate("/", { replace: true });
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-slate-50 px-4 py-12 dark:bg-slate-950">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-soft dark:border-slate-800 dark:bg-slate-900 md:grid-cols-2">
        {/* Brand panel */}
        <div className="relative hidden flex-col justify-between bg-gradient-to-br from-brand-700 via-brand-800 to-brand-950 p-10 text-white md:flex">
          <div className="flex items-center gap-2.5">
            <div className="rounded-xl bg-white/15 p-2">
              <ShieldPlus className="h-6 w-6" />
            </div>
            <span className="text-lg font-extrabold tracking-tight">CareGuard</span>
          </div>
          <div>
            <h2 className="text-2xl font-bold leading-snug">
              Catch readmissions before they happen.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-brand-100/90">
              Monitor post-discharge outreach, triage clinical escalations, and
              keep your highest-risk patients safe at home.
            </p>
          </div>
          <div className="flex gap-6 text-sm text-brand-100/80">
            <div>
              <p className="text-2xl font-bold text-white">−38%</p>
              <p>30-day readmits</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-white">24/7</p>
              <p>AI voice check-ins</p>
            </div>
          </div>
        </div>

        {/* Form panel */}
        <div className="p-8 sm:p-10">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
            Sign in
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Coordinator access to the CareGuard dashboard.
          </p>

          <form onSubmit={signIn} className="mt-6 space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                API base URL
                <span className="ml-1 font-normal text-slate-400">(optional)</span>
              </label>
              <input
                className="input"
                placeholder="https://api.careguard.health"
                value={base}
                onChange={(e) => setBase(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Access token (JWT)
              </label>
              <textarea
                className="input min-h-[88px] resize-y font-mono text-xs"
                placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…"
                value={token}
                onChange={(e) => setTokenInput(e.target.value)}
              />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={!token.trim()}>
              Sign in
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          <div className="my-6 flex items-center gap-3 text-xs text-slate-400">
            <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
            or
            <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
          </div>

          <button onClick={startDemo} className="btn-outline w-full">
            <TestTube2 className="h-4 w-4" />
            Explore with demo data
          </button>
          <p className="mt-3 text-center text-xs text-slate-400">
            Demo mode uses synthetic patients — no PHI, no backend required.
          </p>
        </div>
      </div>
    </div>
  );
}
