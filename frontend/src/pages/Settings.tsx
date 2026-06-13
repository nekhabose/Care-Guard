import { Check, Moon, Sun } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";
import {
  clearToken,
  decodeClaims,
  getApiBase,
  getToken,
  isDemoMode,
  setApiBase,
  setDemoMode,
  setToken,
} from "../lib/auth";
import { formatDateTime } from "../lib/format";
import { PageHeader } from "../components/ui/PageHeader";

export function Settings() {
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  const [base, setBase] = useState(getApiBase());
  const [token, setTokenValue] = useState(getToken() ?? "");
  const [saved, setSaved] = useState(false);
  const demo = isDemoMode();
  const claims = decodeClaims(getToken());

  const save = () => {
    setApiBase(base);
    if (token.trim()) setToken(token);
    else clearToken();
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  };

  const exitDemo = () => {
    setDemoMode(false);
    navigate("/login", { replace: true });
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
            Point the dashboard at your CareGuard API and provide a coordinator JWT.
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
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Access token (JWT)
              </label>
              <textarea
                className="input min-h-[80px] resize-y font-mono text-xs"
                placeholder="Paste a fresh Bearer token…"
                value={token}
                onChange={(e) => setTokenValue(e.target.value)}
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
          {demo ? (
            <div className="mt-3">
              <p className="text-sm text-slate-500 dark:text-slate-400">
                You are in <b>Demo Mode</b> with synthetic data.
              </p>
              <button className="btn-outline mt-3" onClick={exitDemo}>
                Exit demo mode
              </button>
            </div>
          ) : claims ? (
            <dl className="mt-3 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-slate-400">Subject</dt>
                <dd className="font-medium text-slate-700 dark:text-slate-200">
                  {(claims.sub as string) ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">Role</dt>
                <dd className="font-medium text-slate-700 dark:text-slate-200">
                  {(claims.role as string) ?? "—"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">Expires</dt>
                <dd className="font-medium text-slate-700 dark:text-slate-200">
                  {claims.exp
                    ? formatDateTime(new Date(claims.exp * 1000).toISOString())
                    : "—"}
                </dd>
              </div>
            </dl>
          ) : (
            <p className="mt-3 text-sm text-slate-400">
              No active token. Add one above to connect.
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
