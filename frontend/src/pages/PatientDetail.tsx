import {
  ArrowLeft,
  CalendarClock,
  Hash,
  BadgeCheck,
  Phone,
  PhoneCall,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import {
  useEscalations,
  usePatients,
  usePatientSessions,
} from "../hooks/queries";
import {
  age,
  formatDate,
  formatDateTime,
  formatPhone,
  fullName,
  initials,
} from "../lib/format";
import { Avatar } from "../components/ui/Avatar";
import { RiskBadge, SeverityBadge, StatusBadge, Tag } from "../components/ui/Badge";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";

export function PatientDetail() {
  const { id } = useParams<{ id: string }>();
  const patients = usePatients();
  const sessions = usePatientSessions(id);
  const escalations = useEscalations(false);

  const patient = (patients.data ?? []).find((p) => p.id === id);
  const patientEscalations = (escalations.data ?? []).filter(
    (e) => e.patient_id === id,
  );

  if (patients.isLoading) return <LoadingState label="Loading patient…" />;
  if (patients.isError)
    return <ErrorState error={patients.error} onRetry={() => patients.refetch()} />;
  if (!patient)
    return (
      <EmptyState
        title="Patient not found"
        hint="This patient may not exist or you may not have access."
      />
    );

  const meta = [
    { icon: BadgeCheck, label: "MRN", value: patient.mrn ?? "—" },
    { icon: Hash, label: "Epic ID", value: patient.epic_patient_id },
    { icon: Phone, label: "Phone", value: formatPhone(patient.phone) },
    {
      icon: CalendarClock,
      label: "Age",
      value:
        age(patient.date_of_birth) != null
          ? `${age(patient.date_of_birth)} yrs`
          : "—",
    },
  ];

  const orderedSessions = (sessions.data ?? [])
    .slice()
    .sort((a, b) => +new Date(a.scheduled_at) - +new Date(b.scheduled_at));

  return (
    <div>
      <Link
        to="/patients"
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        Patients
      </Link>

      {/* Header card */}
      <div className="card p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <Avatar initials={initials(patient)} seed={patient.id} size="lg" />
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                {fullName(patient)}
              </h1>
              <p className="text-sm text-slate-400">
                Enrolled {formatDate(patient.created_at)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {patient.risk_score != null && (
              <div className="text-right">
                <p className="text-2xl font-bold text-slate-900 dark:text-white">
                  {patient.risk_score}
                </p>
                <p className="text-xs text-slate-400">Risk score</p>
              </div>
            )}
            <RiskBadge level={patient.risk_level} />
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-slate-100 pt-5 dark:border-slate-800 sm:grid-cols-4">
          {meta.map((m) => (
            <div key={m.label} className="flex items-start gap-2.5">
              <m.icon className="mt-0.5 h-4 w-4 text-slate-400" />
              <div>
                <p className="text-xs font-medium text-slate-400">{m.label}</p>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {m.value}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Outreach timeline */}
        <div className="card lg:col-span-3">
          <div className="border-b border-slate-100 px-5 py-4 dark:border-slate-800">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">
              Outreach timeline
            </h3>
            <p className="text-xs text-slate-400">
              Scheduled and completed AI voice check-ins
            </p>
          </div>
          {sessions.isLoading ? (
            <LoadingState />
          ) : sessions.isError ? (
            <ErrorState error={sessions.error} onRetry={() => sessions.refetch()} />
          ) : orderedSessions.length === 0 ? (
            <EmptyState
              title="No outreach yet"
              hint="Calls are scheduled automatically after discharge."
              icon={PhoneCall}
            />
          ) : (
            <ol className="relative px-5 py-4">
              <span className="absolute left-[34px] top-6 bottom-6 w-px bg-slate-200 dark:bg-slate-800" />
              {orderedSessions.map((sess) => (
                <li key={sess.id} className="relative flex gap-4 py-3">
                  <span className="z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-bold text-brand-700 ring-4 ring-white dark:bg-brand-500/15 dark:text-brand-300 dark:ring-slate-900">
                    {sess.outreach_number}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-slate-800 dark:text-slate-100">
                        Outreach call #{sess.outreach_number}
                      </p>
                      <StatusBadge status={sess.status} />
                    </div>
                    <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                      Scheduled {formatDateTime(sess.scheduled_at)}
                      {sess.completed_at &&
                        ` · Completed ${formatDateTime(sess.completed_at)}`}
                    </p>
                    {sess.twilio_call_sid && (
                      <p className="mt-1 font-mono text-[11px] text-slate-400">
                        {sess.twilio_call_sid}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>

        {/* Patient escalations */}
        <div className="card lg:col-span-2">
          <div className="border-b border-slate-100 px-5 py-4 dark:border-slate-800">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">
              Escalations
            </h3>
            <p className="text-xs text-slate-400">Clinical concerns flagged for this patient</p>
          </div>
          {escalations.isLoading ? (
            <LoadingState />
          ) : patientEscalations.length === 0 ? (
            <EmptyState title="No escalations" hint="No concerns raised so far." />
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {patientEscalations.map((e) => (
                <li key={e.id} className="px-5 py-4">
                  <div className="flex items-center justify-between gap-2">
                    <SeverityBadge severity={e.severity} />
                    <span className="text-xs text-slate-400">
                      {formatDateTime(e.created_at)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-slate-700 dark:text-slate-200">
                    {e.reason}
                  </p>
                  {e.symptoms_flagged.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {e.symptoms_flagged.map((s) => (
                        <Tag key={s}>{s.replace(/_/g, " ")}</Tag>
                      ))}
                    </div>
                  )}
                  <p className="mt-2 text-xs font-medium text-slate-400">
                    {e.resolved_at
                      ? `Resolved by ${e.resolved_by ?? "—"}`
                      : "Open"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
