import { Check, Phone, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useCallPatient } from "../../hooks/queries";
import { ApiError } from "../../lib/api";
import { cn } from "../../lib/cn";
import { Spinner } from "./States";

type Variant = "icon" | "button";

/**
 * Initiates an on-demand AI voice check-in call to a patient. Self-contained:
 * owns the mutation and shows pending / success / error feedback inline.
 */
export function CallButton({
  patientId,
  variant = "button",
  label = "Call now",
}: {
  patientId: string;
  variant?: Variant;
  label?: string;
}) {
  const call = useCallPatient();
  const [justCalled, setJustCalled] = useState(false);

  // Flash the success state briefly, then return to idle.
  useEffect(() => {
    if (!justCalled) return;
    const t = setTimeout(() => setJustCalled(false), 2500);
    return () => clearTimeout(t);
  }, [justCalled]);

  const onClick = (e: React.MouseEvent) => {
    // Rows wrap their content in a <Link>; don't navigate when calling.
    e.preventDefault();
    e.stopPropagation();
    if (call.isPending) return;
    call.mutate(patientId, { onSuccess: () => setJustCalled(true) });
  };

  const errorMsg =
    call.isError &&
    (call.error instanceof ApiError || call.error instanceof Error)
      ? call.error.message
      : null;

  const icon = call.isPending ? (
    <Spinner className="h-4 w-4" />
  ) : justCalled ? (
    <Check className="h-4 w-4" />
  ) : errorMsg ? (
    <TriangleAlert className="h-4 w-4" />
  ) : (
    <Phone className="h-4 w-4" />
  );

  const title = errorMsg
    ? `Call failed: ${errorMsg}`
    : justCalled
      ? "Call placed"
      : "Call this patient now";

  if (variant === "icon") {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={call.isPending}
        title={title}
        aria-label={`Call patient`}
        className={cn(
          "inline-flex h-8 w-8 items-center justify-center rounded-lg border transition active:scale-95 disabled:opacity-60",
          justCalled
            ? "border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-400"
            : errorMsg
              ? "border-red-200 bg-red-50 text-red-600 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400"
              : "border-slate-200 bg-white text-brand-700 hover:bg-brand-50 dark:border-slate-700 dark:bg-slate-900 dark:text-brand-300 dark:hover:bg-slate-800",
        )}
      >
        {icon}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={call.isPending}
      title={title}
      className={cn(
        "btn-primary",
        justCalled && "!bg-emerald-600 hover:!bg-emerald-600",
        errorMsg && "!bg-red-600 hover:!bg-red-600",
      )}
    >
      {icon}
      {call.isPending
        ? "Calling…"
        : justCalled
          ? "Call placed"
          : errorMsg
            ? "Call failed"
            : label}
    </button>
  );
}
