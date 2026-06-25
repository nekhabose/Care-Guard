import { Check, PhoneCall, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useCallHighRisk } from "../../hooks/queries";
import { ApiError } from "../../lib/api";
import { cn } from "../../lib/cn";
import { Spinner } from "./States";

/** Places an immediate call to every high-risk patient. */
export function CallHighRiskButton() {
  const call = useCallHighRisk();
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    if (count == null) return;
    const t = setTimeout(() => setCount(null), 3000);
    return () => clearTimeout(t);
  }, [count]);

  const errorMsg =
    call.isError &&
    (call.error instanceof ApiError || call.error instanceof Error)
      ? call.error.message
      : null;

  const onClick = () => {
    if (call.isPending) return;
    call.mutate(undefined, { onSuccess: (sessions) => setCount(sessions.length) });
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={call.isPending}
      title={errorMsg ? `Failed: ${errorMsg}` : "Call all high-risk patients now"}
      className={cn(
        "btn-primary !px-3 !py-1.5 !text-xs",
        count != null && "!bg-emerald-600 hover:!bg-emerald-600",
        errorMsg && "!bg-red-600 hover:!bg-red-600",
      )}
    >
      {call.isPending ? (
        <Spinner className="h-3.5 w-3.5" />
      ) : count != null ? (
        <Check className="h-3.5 w-3.5" />
      ) : errorMsg ? (
        <TriangleAlert className="h-3.5 w-3.5" />
      ) : (
        <PhoneCall className="h-3.5 w-3.5" />
      )}
      {call.isPending
        ? "Calling…"
        : count != null
          ? `Called ${count}`
          : errorMsg
            ? "Failed"
            : "Call all high-risk"}
    </button>
  );
}
