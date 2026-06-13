import { LogOut, Menu, Moon, Sun, TestTube2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../../hooks/useTheme";
import { decodeClaims, getToken, isDemoMode, logout } from "../../lib/auth";
import { Avatar } from "../ui/Avatar";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const demo = isDemoMode();
  const claims = decodeClaims(getToken());
  const name = (claims?.name as string) || (claims?.sub as string) || "Coordinator";
  const sub = (claims?.email as string) || (claims?.role as string) || "Care team";

  const onLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/80 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80 sm:px-6">
      <button
        className="btn-ghost -ml-2 p-2 lg:hidden"
        onClick={onMenu}
        aria-label="Open navigation"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="flex-1" />

      {demo && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300">
          <TestTube2 className="h-3.5 w-3.5" />
          Demo data
        </span>
      )}

      <button
        className="btn-ghost p-2"
        onClick={toggle}
        aria-label="Toggle theme"
        title={theme === "dark" ? "Switch to light" : "Switch to dark"}
      >
        {theme === "dark" ? (
          <Sun className="h-5 w-5" />
        ) : (
          <Moon className="h-5 w-5" />
        )}
      </button>

      <div className="hidden items-center gap-2.5 sm:flex">
        <Avatar initials={name.slice(0, 2).toUpperCase()} seed={name} size="sm" />
        <div className="leading-tight">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            {name}
          </p>
          <p className="text-[11px] text-slate-400">{sub}</p>
        </div>
      </div>

      <button className="btn-ghost p-2" onClick={onLogout} aria-label="Sign out" title="Sign out">
        <LogOut className="h-5 w-5" />
      </button>
    </header>
  );
}
