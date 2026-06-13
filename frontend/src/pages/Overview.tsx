import { HeartPulse, Siren, TriangleAlert, Users } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";
import { useAnalytics, useEscalations, usePatients } from "../hooks/queries";
import { fullName, initials, relativeTime } from "../lib/format";
import type { RiskLevel } from "../lib/types";
import { Avatar } from "../components/ui/Avatar";
import { RiskBadge, SeverityBadge } from "../components/ui/Badge";
import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { StatCard } from "../components/ui/StatCard";

const RISK_COLORS: Record<RiskLevel, string> = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#10b981",
};

export function Overview() {
  const analytics = useAnalytics();
  const patients = usePatients();
  const escalations = useEscalations(true);

  const riskData = useMemo(() => {
    const counts: Record<RiskLevel, number> = { high: 0, medium: 0, low: 0 };
    for (const p of patients.data ?? []) {
      if (p.risk_level) counts[p.risk_level]++;
    }
    return (Object.keys(counts) as RiskLevel[]).map((k) => ({
      name: k[0].toUpperCase() + k.slice(1),
      key: k,
      value: counts[k],
    }));
  }, [patients.data]);

  const severityData = useMemo(() => {
    const counts = { urgent: 0, high: 0, medium: 0 };
    for (const e of escalations.data ?? []) counts[e.severity]++;
    return [
      { name: "Urgent", value: counts.urgent, fill: "#ef4444" },
      { name: "High", value: counts.high, fill: "#f97316" },
      { name: "Medium", value: counts.medium, fill: "#f59e0b" },
    ];
  }, [escalations.data]);

  const recentOpen = (escalations.data ?? [])
    .slice()
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
    .slice(0, 5);

  const patientName = (id: string) => {
    const p = (patients.data ?? []).find((x) => x.id === id);
    return p ? fullName(p) : "Unknown patient";
  };

  const s = analytics.data;

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Real-time view of your post-discharge population and open clinical escalations."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Patients monitored"
          value={s?.total_patients ?? 0}
          icon={Users}
          tone="brand"
          loading={analytics.isLoading}
          hint="Active post-discharge cohort"
        />
        <StatCard
          label="High-risk patients"
          value={s?.high_risk_patients ?? 0}
          icon={HeartPulse}
          tone="red"
          loading={analytics.isLoading}
          hint="Prioritized for outreach"
        />
        <StatCard
          label="Open escalations"
          value={s?.open_escalations ?? 0}
          icon={Siren}
          tone="amber"
          loading={analytics.isLoading}
          hint="Awaiting coordinator action"
        />
        <StatCard
          label="Urgent escalations"
          value={s?.urgent_escalations ?? 0}
          icon={TriangleAlert}
          tone="red"
          loading={analytics.isLoading}
          hint="Immediate attention"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Risk distribution */}
        <div className="card p-5 lg:col-span-1">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">
            Risk distribution
          </h3>
          <p className="text-xs text-slate-400">Across monitored patients</p>
          <div className="mt-2 h-56">
            {patients.isLoading ? (
              <LoadingState />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={riskData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={52}
                    outerRadius={80}
                    paddingAngle={3}
                    stroke="none"
                  >
                    {riskData.map((d) => (
                      <Cell key={d.key} fill={RISK_COLORS[d.key]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      borderRadius: 12,
                      border: "none",
                      boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="mt-2 flex justify-center gap-4">
            {riskData.map((d) => (
              <div key={d.key} className="flex items-center gap-1.5 text-xs">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ background: RISK_COLORS[d.key] }}
                />
                <span className="text-slate-500 dark:text-slate-400">
                  {d.name} · <b className="text-slate-700 dark:text-slate-200">{d.value}</b>
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Escalations by severity */}
        <div className="card p-5 lg:col-span-2">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">
            Open escalations by severity
          </h3>
          <p className="text-xs text-slate-400">Triage workload snapshot</p>
          <div className="mt-2 h-56">
            {escalations.isLoading ? (
              <LoadingState />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={severityData} barSize={48}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} />
                  <Tooltip
                    cursor={{ fill: "rgba(148,163,184,0.12)" }}
                    contentStyle={{
                      borderRadius: 12,
                      border: "none",
                      boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
                    }}
                  />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                    {severityData.map((d) => (
                      <Cell key={d.name} fill={d.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Recent escalations */}
      <div className="mt-6 card">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-800">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">
            Recent escalations
          </h3>
          <Link to="/escalations" className="text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300">
            View all →
          </Link>
        </div>
        {escalations.isError ? (
          <ErrorState error={escalations.error} onRetry={() => escalations.refetch()} />
        ) : escalations.isLoading ? (
          <LoadingState />
        ) : recentOpen.length === 0 ? (
          <EmptyState title="No open escalations" hint="Your queue is clear — nice work." icon={Siren} />
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {recentOpen.map((e) => (
              <li key={e.id} className="flex items-center gap-4 px-5 py-3.5">
                <Avatar
                  initials={initials({
                    first_name: patientName(e.patient_id).split(" ")[0] ?? "",
                    last_name: patientName(e.patient_id).split(" ")[1] ?? "",
                  })}
                  seed={e.patient_id}
                  size="sm"
                />
                <div className="min-w-0 flex-1">
                  <Link
                    to={`/patients/${e.patient_id}`}
                    className="font-medium text-slate-800 hover:text-brand-700 dark:text-slate-100"
                  >
                    {patientName(e.patient_id)}
                  </Link>
                  <p className="truncate text-sm text-slate-500 dark:text-slate-400">
                    {e.reason}
                  </p>
                </div>
                <div className="hidden text-right text-xs text-slate-400 sm:block">
                  {relativeTime(e.created_at)}
                </div>
                <SeverityBadge severity={e.severity} />
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* High-risk patients */}
      <div className="mt-6 card">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-800">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">
            High-risk patients
          </h3>
          <Link to="/patients" className="text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300">
            All patients →
          </Link>
        </div>
        {patients.isLoading ? (
          <LoadingState />
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {(patients.data ?? [])
              .filter((p) => p.risk_level === "high")
              .slice(0, 5)
              .map((p) => (
                <li key={p.id} className="flex items-center gap-4 px-5 py-3.5">
                  <Avatar initials={initials(p)} seed={p.id} size="sm" />
                  <Link
                    to={`/patients/${p.id}`}
                    className="min-w-0 flex-1 font-medium text-slate-800 hover:text-brand-700 dark:text-slate-100"
                  >
                    {fullName(p)}
                    <span className="ml-2 text-xs font-normal text-slate-400">
                      MRN {p.mrn ?? "—"}
                    </span>
                  </Link>
                  {p.risk_score != null && (
                    <span className="hidden text-sm font-semibold text-slate-600 dark:text-slate-300 sm:block">
                      {p.risk_score}
                    </span>
                  )}
                  <RiskBadge level={p.risk_level} />
                </li>
              ))}
          </ul>
        )}
      </div>
    </div>
  );
}
