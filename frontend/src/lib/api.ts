import { getApiBase, getToken, isDemoMode } from "./auth";
import {
  mockEscalations,
  mockPatients,
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

  async analyticsSummary(): Promise<AnalyticsSummary> {
    if (isDemoMode()) {
      await wait();
      return mockSummary();
    }
    return request<AnalyticsSummary>(`/dashboard/analytics/summary`);
  },
};
