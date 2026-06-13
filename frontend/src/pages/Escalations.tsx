import { Check, CircleCheck, Siren } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useEscalations,
  usePatients,
  useResolveEscalation,
} from "../hooks/queries";
import { decodeClaims, getToken } from "../lib/auth";
import { cn } from "../lib/cn";
import { formatDateTime, fullName, initials, relativeTime } from "../lib/format";
import type { Severity } from "../lib/types";
import { Avatar } from "../components/ui/Avatar";
import { SeverityBadge, Tag } from "../components/ui/Badge";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, LoadingState, Spinner } from "../components/ui/States";

const SEVERITY_ORDER: Record<Severity, number> = { urgent: 0, high: 1, medium: 2 };

export function Escalations() {
  const [showResolved, setShowResolved] = useState(false);
  const { data, isLoading, isError, error, refetch } = useEscalations(!showResolved);
  const patients = usePatients();
  const resolve = useResolveEscalation();

  const claims = decodeClaims(getToken());
  const resolvedBy =
    (claims?.email as string) || (claims?.sub as string) || "coordinator";

  const patientFor = (pid: string) => (patients.data ?? []).find((p) => p.id === pid);

  const rows = (data ?? [])
    .slice()
    .sort((a, b) => {
      if (!!a.resolved_at !== !!b.resolved_at) return a.resolved_at ? 1 : -1;
      const s = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
      if (s !== 0) return s;
      return +new Date(b.created_at) - +new Date(a.created_at);
    });

  return (
    <div>
      <PageHeader
        title="Escalations"
        subtitle="Triage clinical concerns raised during patient check-ins."
        actions={
          <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
              checked={showResolved}
              onChange={(e) => setShowResolved(e.target.checked)}
            />
            Include resolved
          </label>
        }
      />

      {isError ? (
        <div className="card">
          <ErrorState error={error} onRetry={() => refetch()} />
        </div>
      ) : isLoading ? (
        <div className="card">
          <LoadingState label="Loading escalations…" />
        </div>
      ) : rows.length === 0 ? (
        <div className="card">
          <EmptyState
            title="Queue is clear"
            hint="No escalations match this view."
            icon={CircleCheck}
          />
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((e) => {
            const p = patientFor(e.patient_id);
            const isResolving =
              resolve.isPending && resolve.variables?.id === e.id;
            return (
              <div
                key={e.id}
                className={cn(
                  "card animate-fade-in p-5",
                  e.severity === "urgent" && !e.resolved_at &&
                    "ring-1 ring-red-200 dark:ring-red-500/30",
                )}
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 gap-4">
                    <Avatar
                      initials={p ? initials(p) : "··"}
                      seed={e.patient_id}
                    />
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        {p ? (
                          <Link
                            to={`/patients/${p.id}`}
                            className="font-semibold text-slate-800 hover:text-brand-700 dark:text-slate-100"
                          >
                            {fullName(p)}
                          </Link>
                        ) : (
                          <span className="font-semibold text-slate-500">
                            Unknown patient
                          </span>
                        )}
                        <SeverityBadge severity={e.severity} />
                        {e.resolved_at && (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                            <CircleCheck className="h-3.5 w-3.5" /> Resolved
                          </span>
                        )}
                      </div>
                      <p className="mt-1.5 text-sm text-slate-700 dark:text-slate-200">
                        {e.reason}
                      </p>
                      {e.symptoms_flagged.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {e.symptoms_flagged.map((s) => (
                            <Tag key={s}>{s.replace(/_/g, " ")}</Tag>
                          ))}
                        </div>
                      )}
                      <p className="mt-2 text-xs text-slate-400">
                        Raised {relativeTime(e.created_at)}
                        {e.notified_at &&
                          ` · Care team notified ${formatDateTime(e.notified_at)}`}
                        {e.resolved_at &&
                          ` · by ${e.resolved_by ?? "—"} ${formatDateTime(e.resolved_at)}`}
                      </p>
                    </div>
                  </div>

                  {!e.resolved_at && (
                    <button
                      className="btn-primary shrink-0"
                      disabled={isResolving}
                      onClick={() => resolve.mutate({ id: e.id, resolvedBy })}
                    >
                      {isResolving ? (
                        <Spinner className="h-4 w-4 text-white" />
                      ) : (
                        <Check className="h-4 w-4" />
                      )}
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {resolve.isError && (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-red-600">
          <Siren className="h-4 w-4" />
          {(resolve.error as Error).message}
        </p>
      )}
    </div>
  );
}
