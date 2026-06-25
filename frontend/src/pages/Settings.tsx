import { Check, LogOut, Moon, Sun, TestTube2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";
import {
  decodeClaims,
  getApiBase,
  getToken,
  isDemoMode,
  logout,
  setApiBase,
  setDemoMode,
} from "../lib/auth";
import { formatDateTime } from "../lib/format";
import { PageHeader } from "../components/ui/PageHeader";

export function Settings() {
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  const [base, setBase] = useState(getApiBase());
  const [saved, setSaved] = useState(false);
  const demo = isDemoMode();
  const claims = decodeClaims(getToken());

  const save = () => {
    setApiBase(base);
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  };

  const onLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const toggleDemo = (on: boolean) => {
    setDemoMode(on);
    // Re-fetch everything against the newly selected data source.
    navigate("/", { replace: true });
  };

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Connection, session, and appearance preferences."
      />

      <div className="space-y-6">
        {/* Connection */}
        <section className="card p-6">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">
            Backend connection
          </h3>
          <p className="mt-0.5 text-sm text-slate-400">
            Point the dashboard at your CareGuard API. You're signed in with your
            account — no token to paste.
          </p>
          <div className="mt-4 space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                API base URL
              </label>
              <input
                className="input"
                placeholder="https://api.careguard.health"
                value={base}
                onChange={(e) => setBase(e.target.value)}
              />
            </div>
            <button className="btn-primary" onClick={save}>
              {saved ? <Check className="h-4 w-4" /> : null}
              {saved ? "Saved" : "Save connection"}
            </button>
          </div>
        </section>

        {/* Session */}
        <section className="card p-6">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">
            Session
          </h3>
          <dl className="mt-3 grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-400">Signed in as</dt>
              <dd className="font-medium text-slate-700 dark:text-slate-200">
                {(claims?.name as string) || (claims?.email as string) || (claims?.sub as string) || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Role</dt>
              <dd className="font-medium text-slate-700 dark:text-slate-200">
                {(claims?.role as string) ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Session expires</dt>
              <dd className="font-medium text-slate-700 dark:text-slate-200">
                {claims?.exp
                  ? formatDateTime(new Date(claims.exp * 1000).toISOString())
                  : "—"}
              </dd>
            </div>
          </dl>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button className="btn-outline" onClick={onLogout}>
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
            {demo ? (
              <button className="btn-outline" onClick={() => toggleDemo(false)}>
                <TestTube2 className="h-4 w-4" />
                Exit demo data
              </button>
            ) : (
              <button className="btn-outline" onClick={() => toggleDemo(true)}>
                <TestTube2 className="h-4 w-4" />
                Explore demo data
              </button>
            )}
          </div>
          {demo && (
            <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
              Demo data is synthetic — calls are simulated and never dial a real number.
            </p>
          )}
        </section>

        {/* Appearance */}
        <section className="card p-6">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">
            Appearance
          </h3>
          <div className="mt-3 flex items-center justify-between">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Theme — currently {theme}
            </p>
            <button className="btn-outline" onClick={toggle}>
              {theme === "dark" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
              Switch to {theme === "dark" ? "light" : "dark"}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
