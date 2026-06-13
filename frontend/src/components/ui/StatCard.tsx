import type { LucideIcon } from "lucide-react";
import { cn } from "../../lib/cn";

type Tone = "brand" | "red" | "amber" | "slate";

const TONES: Record<Tone, string> = {
  brand: "bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300",
  red: "bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  slate: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "slate",
  hint,
  loading,
}: {
  label: string;
  value: number | string;
  icon: LucideIcon;
  tone?: Tone;
  hint?: string;
  loading?: boolean;
}) {
  return (
    <div className="card animate-fade-in p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
            {label}
          </p>
          {loading ? (
            <div className="mt-2 h-8 w-16 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          ) : (
            <p className="mt-1 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
              {value}
            </p>
          )}
          {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
        </div>
        <div className={cn("rounded-xl p-2.5", TONES[tone])}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}
