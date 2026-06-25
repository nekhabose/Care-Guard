import { AlertCircle, Phone, UserPlus, X } from "lucide-react";
import { useState } from "react";
import { useOnboardPatient } from "../../hooks/queries";
import { ApiError, api, type OnboardInput } from "../../lib/api";

const CONDITIONS = [
  { value: "heart_failure", label: "Heart failure" },
  { value: "copd", label: "COPD" },
  { value: "pneumonia", label: "Pneumonia" },
  { value: "ami", label: "Heart attack (AMI)" },
  { value: "hip_knee", label: "Hip / knee replacement" },
  { value: "cabg", label: "Bypass surgery (CABG)" },
  { value: "general", label: "General / other" },
];

const PHONE_RE = /^\+[1-9]\d{7,14}$/;

export function OnboardPatientModal({ onClose }: { onClose: () => void }) {
  const onboard = useOnboardPatient();
  const [form, setForm] = useState<OnboardInput>({
    first_name: "",
    last_name: "",
    phone: "",
    condition: "heart_failure",
    lives_alone: false,
    has_followup_appointment: true,
  });
  const [age, setAge] = useState("");
  const [testCall, setTestCall] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (patch: Partial<OnboardInput>) => setForm((f) => ({ ...f, ...patch }));
  const phoneValid = PHONE_RE.test(form.phone.trim());
  const valid = form.first_name.trim() && form.last_name.trim() && phoneValid;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError(null);
    try {
      const patient = await onboard.mutateAsync({
        ...form,
        phone: form.phone.trim(),
        age: age ? Number(age) : null,
      });
      // Optionally verify outreach end to end by dialing the number now.
      if (testCall) await api.callPatient(patient.id);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Onboarding failed. Check the API connection.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-brand-50 p-1.5 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
              <UserPlus className="h-5 w-5" />
            </div>
            <h2 className="text-base font-bold text-slate-800 dark:text-white">Onboard patient</h2>
          </div>
          <button className="btn-ghost p-1.5" onClick={onClose} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4 px-6 py-5">
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">First name</label>
              <input className="input" value={form.first_name} onChange={(e) => set({ first_name: e.target.value })} />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">Last name</label>
              <input className="input" value={form.last_name} onChange={(e) => set({ last_name: e.target.value })} />
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Mobile number
            </label>
            <input
              className="input"
              placeholder="+14155550123"
              value={form.phone}
              onChange={(e) => set({ phone: e.target.value })}
            />
            <p className="mt-1 text-xs text-slate-400">
              E.164 format (with country code). Use your own mobile to test a real call.
            </p>
            {form.phone && !phoneValid && (
              <p className="mt-1 text-xs text-red-500">Enter a valid number like +14155550123.</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">Condition</label>
              <select
                className="input"
                value={form.condition}
                onChange={(e) => set({ condition: e.target.value })}
              >
                {CONDITIONS.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                Age <span className="font-normal text-slate-400">(optional)</span>
              </label>
              <input
                className="input"
                type="number"
                min={0}
                max={120}
                value={age}
                onChange={(e) => setAge(e.target.value)}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={form.lives_alone}
              onChange={(e) => set({ lives_alone: e.target.checked })}
            />
            Lives alone (raises readmission risk)
          </label>

          <label className="flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-amber-300"
              checked={testCall}
              onChange={(e) => setTestCall(e.target.checked)}
            />
            <Phone className="h-4 w-4" />
            Place a test call to this number right after onboarding
          </label>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn-outline" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={!valid || busy}>
              {busy ? "Onboarding…" : testCall ? "Onboard & call" : "Onboard patient"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
