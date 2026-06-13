import { Search, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { usePatients } from "../hooks/queries";
import { age, formatDate, formatPhone, fullName, initials } from "../lib/format";
import { cn } from "../lib/cn";
import type { RiskLevel } from "../lib/types";
import { Avatar } from "../components/ui/Avatar";
import { RiskBadge } from "../components/ui/Badge";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";

const FILTERS: { label: string; value: RiskLevel | "all" }[] = [
  { label: "All", value: "all" },
  { label: "High", value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low", value: "low" },
];

export function Patients() {
  const [filter, setFilter] = useState<RiskLevel | "all">("all");
  const [query, setQuery] = useState("");
  const { data, isLoading, isError, error, refetch } = usePatients(
    filter === "all" ? undefined : filter,
  );

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return data ?? [];
    return (data ?? []).filter((p) =>
      [fullName(p), p.mrn, p.epic_patient_id, p.phone]
        .filter(Boolean)
        .some((v) => v!.toLowerCase().includes(q)),
    );
  }, [data, query]);

  return (
    <div>
      <PageHeader
        title="Patients"
        subtitle="Post-discharge cohort under active monitoring."
        actions={
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className="input w-full pl-9 sm:w-72"
              placeholder="Search name, MRN, phone…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        }
      />

      <div className="mb-4 inline-flex rounded-xl border border-slate-200 bg-white p-1 dark:border-slate-800 dark:bg-slate-900">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={cn(
              "rounded-lg px-3.5 py-1.5 text-sm font-medium transition",
              filter === f.value
                ? "bg-brand-700 text-white shadow-sm"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        {isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : isLoading ? (
          <LoadingState label="Loading patients…" />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No patients found"
            hint={query ? "Try a different search." : "No patients match this filter."}
            icon={Users}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-800">
                <tr>
                  <th className="px-5 py-3 font-semibold">Patient</th>
                  <th className="px-5 py-3 font-semibold">MRN</th>
                  <th className="px-5 py-3 font-semibold">Phone</th>
                  <th className="px-5 py-3 font-semibold">Age</th>
                  <th className="px-5 py-3 font-semibold">Risk</th>
                  <th className="px-5 py-3 text-right font-semibold">Enrolled</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {rows.map((p) => (
                  <tr
                    key={p.id}
                    className="group transition hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <td className="px-5 py-3">
                      <Link to={`/patients/${p.id}`} className="flex items-center gap-3">
                        <Avatar initials={initials(p)} seed={p.id} size="sm" />
                        <div>
                          <p className="font-semibold text-slate-800 group-hover:text-brand-700 dark:text-slate-100">
                            {fullName(p)}
                          </p>
                          <p className="text-xs text-slate-400">{p.epic_patient_id}</p>
                        </div>
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-slate-500 dark:text-slate-400">
                      {p.mrn ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-slate-500 dark:text-slate-400">
                      {formatPhone(p.phone)}
                    </td>
                    <td className="px-5 py-3 text-slate-500 dark:text-slate-400">
                      {age(p.date_of_birth) ?? "—"}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <RiskBadge level={p.risk_level} />
                        {p.risk_score != null && (
                          <span className="text-xs font-semibold text-slate-400">
                            {p.risk_score}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-right text-slate-500 dark:text-slate-400">
                      {formatDate(p.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {!isLoading && rows.length > 0 && (
        <p className="mt-3 text-xs text-slate-400">
          Showing {rows.length} patient{rows.length === 1 ? "" : "s"}.
        </p>
      )}
    </div>
  );
}
