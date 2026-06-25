import { getApiBase, getToken, isDemoMode } from "./auth";
import {
  mockEscalations,
  mockPatients,
  mockSessions,
  mockSummary,
  sessionsFor,
} from "./mock";
import type {
  AnalyticsSummary,
  Escalation,
  OutreachSession,
  Patient,
  RiskLevel,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiBase();
  const token = getToken();
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (res.status === 401) {
    throw new ApiError(401, "Session expired or token invalid. Please sign in again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body.message ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// Demo Mode short-circuits network calls with sample data. Small latency keeps
// loading states honest.
const wait = () => new Promise((r) => setTimeout(r, 220));

export const api = {
  async listPatients(riskLevel?: RiskLevel): Promise<Patient[]> {
    if (isDemoMode()) {
      await wait();
      return riskLevel
        ? mockPatients.filter((p) => p.risk_level === riskLevel)
        : mockPatients;
    }
    const qs = riskLevel ? `?risk_level=${riskLevel}` : "";
    return request<Patient[]>(`/dashboard/patients${qs}`);
  },

  async patientSessions(patientId: string): Promise<OutreachSession[]> {
    if (isDemoMode()) {
      await wait();
      return sessionsFor(patientId);
    }
    return request<OutreachSession[]>(`/dashboard/patients/${patientId}/sessions`);
  },

  async listEscalations(unresolvedOnly = true): Promise<Escalation[]> {
    if (isDemoMode()) {
      await wait();
      return unresolvedOnly
        ? mockEscalations.filter((e) => !e.resolved_at)
        : mockEscalations;
    }
    return request<Escalation[]>(
      `/dashboard/escalations?unresolved_only=${unresolvedOnly}`,
    );
  },

  async resolveEscalation(id: string, resolvedBy: string): Promise<Escalation> {
    if (isDemoMode()) {
      await wait();
      const e = mockEscalations.find((x) => x.id === id)!;
      e.resolved_at = new Date().toISOString();
      e.resolved_by = resolvedBy;
      return e;
    }
    return request<Escalation>(`/dashboard/escalations/${id}/resolve`, {
      method: "PATCH",
      body: JSON.stringify({ resolved_by: resolvedBy }),
    });
  },

  // Demo helper: synthesize a just-placed call so the UI updates without a
  // backend. Mutates mockSessions so the patient's timeline reflects it.
  _demoCall(patientId: string): OutreachSession {
    const existing = mockSessions[patientId] ?? [];
    const ts = new Date().toISOString();
    const sess: OutreachSession = {
      id: `s-manual-${existing.length + 1}-${patientId}`,
      patient_id: patientId,
      discharge_id: "d-demo",
      scheduled_at: ts,
      started_at: ts,
      completed_at: null,
      channel: "voice",
      status: "in_progress",
      outreach_number: existing.length + 1,
      twilio_call_sid: "CA-demo-manual",
      created_at: ts,
    };
    mockSessions[patientId] = [...existing, sess];
    return sess;
  },

  // Initiate an immediate AI voice check-in call to one patient.
  async callPatient(patientId: string): Promise<OutreachSession> {
    if (isDemoMode()) {
      await wait();
      return this._demoCall(patientId);
    }
    return request<OutreachSession>(`/dashboard/patients/${patientId}/call`, {
      method: "POST",
    });
  },

  // Call every high-risk patient now.
  async callHighRisk(): Promise<OutreachSession[]> {
    if (isDemoMode()) {
      await wait();
      return mockPatients
        .filter((p) => p.risk_level === "high")
        .map((p) => this._demoCall(p.id));
    }
    return request<OutreachSession[]>(`/dashboard/call-high-risk`, {
      method: "POST",
    });
  },

  // Seed the cohort from built-in mock FHIR data (no Epic webhook needed).
  async seedMockPatients(): Promise<Patient[]> {
    if (isDemoMode()) {
      await wait();
      return mockPatients;
    }
    return request<Patient[]>(`/dashboard/seed`, { method: "POST" });
  },

  async analyticsSummary(): Promise<AnalyticsSummary> {
    if (isDemoMode()) {
      await wait();
      return mockSummary();
    }
    return request<AnalyticsSummary>(`/dashboard/analytics/summary`);
  },
};
