import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { cn } from "../../lib/cn";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin", className)} />;
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-slate-400">
      <Spinner className="h-6 w-6 text-brand-600" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  icon: Icon = Inbox,
}: {
  title: string;
  hint?: string;
  icon?: typeof Inbox;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <div className="rounded-2xl bg-slate-100 p-3 text-slate-400 dark:bg-slate-800">
        <Icon className="h-6 w-6" />
      </div>
      <p className="font-semibold text-slate-700 dark:text-slate-200">{title}</p>
      {hint && <p className="max-w-sm text-sm text-slate-400">{hint}</p>}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const message =
    error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="rounded-2xl bg-red-50 p-3 text-red-500 dark:bg-red-500/10">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <p className="font-semibold text-slate-700 dark:text-slate-200">
        Couldn’t load data
      </p>
      <p className="max-w-md text-sm text-slate-400">{message}</p>
      {onRetry && (
        <button className="btn-outline mt-1" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
