import {
  Activity,
  LayoutDashboard,
  Settings,
  ShieldPlus,
  Siren,
  Users,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "../../lib/cn";
import { useEscalations } from "../../hooks/queries";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/patients", label: "Patients", icon: Users, end: false },
  { to: "/escalations", label: "Escalations", icon: Siren, end: false },
  { to: "/settings", label: "Settings", icon: Settings, end: false },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { data: openEscalations } = useEscalations(true);
  const openCount = openEscalations?.length ?? 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="rounded-xl bg-brand-700 p-1.5 text-white shadow-soft">
          <ShieldPlus className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-extrabold tracking-tight text-slate-900 dark:text-white">
            CareGuard
          </p>
          <p className="text-[11px] font-medium text-slate-400">
            Care Coordination
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn("nav-link", isActive && "nav-link-active")
            }
          >
            <Icon className="h-[18px] w-[18px]" />
            <span className="flex-1">{label}</span>
            {label === "Escalations" && openCount > 0 && (
              <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
                {openCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="m-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900/50">
        <div className="flex items-center gap-2 text-xs font-semibold text-brand-700 dark:text-brand-300">
          <Activity className="h-4 w-4" />
          HIPAA-aware
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
          PHI is shown only to authorized coordinators. Access is audit-logged.
        </p>
      </div>
    </div>
  );
}
