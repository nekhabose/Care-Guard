import { cn } from "../../lib/cn";
import { titleCase } from "../../lib/format";
import type { RiskLevel, Severity, SessionStatus } from "../../lib/types";

function Pill({
  children,
  className,
  dot,
}: {
  children: React.ReactNode;
  className?: string;
  dot?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset",
        className,
      )}
    >
      {dot && <span className={cn("h-1.5 w-1.5 rounded-full", dot)} />}
      {children}
    </span>
  );
}

const RISK_STYLES: Record<RiskLevel, { cls: string; dot: string }> = {
  high: {
    cls: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30",
    dot: "bg-red-500",
  },
  medium: {
    cls: "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
    dot: "bg-amber-500",
  },
  low: {
    cls: "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30",
    dot: "bg-emerald-500",
  },
};

export function RiskBadge({ level }: { level: RiskLevel | null }) {
  if (!level)
    return (
      <Pill className="bg-slate-100 text-slate-500 ring-slate-300 dark:bg-slate-800 dark:text-slate-400 dark:ring-slate-700">
        Unscored
      </Pill>
    );
  const s = RISK_STYLES[level];
  return (
    <Pill className={s.cls} dot={s.dot}>
      {titleCase(level)} risk
    </Pill>
  );
}

const SEVERITY_STYLES: Record<Severity, { cls: string; dot: string }> = {
  urgent: {
    cls: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30",
    dot: "bg-red-500",
  },
  high: {
    cls: "bg-orange-50 text-orange-700 ring-orange-600/20 dark:bg-orange-500/10 dark:text-orange-300 dark:ring-orange-500/30",
    dot: "bg-orange-500",
  },
  medium: {
    cls: "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
    dot: "bg-amber-500",
  },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const s = SEVERITY_STYLES[severity];
  return (
    <Pill className={s.cls} dot={s.dot}>
      {titleCase(severity)}
    </Pill>
  );
}

const STATUS_STYLES: Record<string, string> = {
  completed:
    "bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30",
  in_progress:
    "bg-brand-50 text-brand-800 ring-brand-600/20 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/30",
  scheduled:
    "bg-slate-100 text-slate-600 ring-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700",
  no_answer:
    "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
  voicemail:
    "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
  failed:
    "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-500/10 dark:text-red-300 dark:ring-red-500/30",
};

export function StatusBadge({ status }: { status: SessionStatus }) {
  return (
    <Pill
      className={
        STATUS_STYLES[status] ??
        "bg-slate-100 text-slate-600 ring-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700"
      }
    >
      {titleCase(status)}
    </Pill>
  );
}

export function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
      {children}
    </span>
  );
}
