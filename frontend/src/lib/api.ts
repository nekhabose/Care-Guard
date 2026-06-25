import type { SessionUser } from "./auth";
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

// Pull a human message out of either error envelope the backend uses:
// domain errors -> {error:{code,message}}; FastAPI -> {detail}.
async function errorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body?.error?.message ?? body?.detail ?? body?.message ?? res.statusText;
  } catch {
    return res.statusText;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
  opts?: { auth?: boolean },
): Promise<T> {
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

  // On the login call a 401 means bad credentials — surface the server's
  // message. Elsewhere it means the session lapsed.
  if (res.status === 401 && !opts?.auth) {
    throw new ApiError(401, "Session expired or token invalid. Please sign in again.");
  }
  if (!res.ok) {
    throw new ApiError(res.status, await errorDetail(res));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: SessionUser;
}

export interface OnboardInput {
  first_name: string;
  last_name: string;
  phone: string;
  condition: string;
  age?: number | null;
  lives_alone?: boolean;
  prior_readmissions_90d?: number;
  has_followup_appointment?: boolean;
}

// Demo Mode short-circuits network calls with sample data. Small latency keeps
// loading states honest.
const wait = () => new Promise((r) => setTimeout(r, 220));

export const api = {
  // Exchange email + password for a bearer token. Returns the token + the
  // authenticated user; the caller persists them via auth.setSession.
  async login(email: string, password: string): Promise<TokenResponse> {
    return request<TokenResponse>(
      `/auth/login`,
      { method: "POST", body: JSON.stringify({ email, password }) },
      { auth: true },
    );
  },

  // Manually enrol a patient so they appear in the cohort and can be called.
  // Use a real mobile number to test an outreach call end to end.
  async onboardPatient(input: OnboardInput): Promise<Patient> {
    if (isDemoMode()) {
      await wait();
      const hrrp = input.condition !== "general";
      const p: Patient = {
        id: `manual-demo-${mockPatients.length + 1}`,
        epic_patient_id: `manual-${input.phone.replace(/\D/g, "").slice(-8)}`,
        mrn: null,
        first_name: input.first_name,
        last_name: input.last_name,
        phone: input.phone,
        date_of_birth: null,
        risk_score: hrrp ? 45 : 10,
        risk_level: hrrp ? "medium" : "low",
        created_at: new Date().toISOString(),
      };
      mockPatients.unshift(p);
      return p;
    }
    return request<Patient>(`/dashboard/patients/onboard`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

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
