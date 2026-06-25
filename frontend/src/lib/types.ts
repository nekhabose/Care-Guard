// Mirrors backend/models/schemas/*.py — keep in sync with the FastAPI contract.

export type RiskLevel = "high" | "medium" | "low";
export type Severity = "urgent" | "high" | "medium";
export type SessionStatus =
  | "scheduled"
  | "in_progress"
  | "completed"
  | "no_answer"
  | "failed"
  | "voicemail";

export interface Patient {
  id: string;
  epic_patient_id: string;
  mrn: string | null;
  first_name: string;
  last_name: string;
  phone: string;
  date_of_birth: string | null; // ISO date
  risk_score: number | null;
  risk_level: RiskLevel | null;
  created_at: string; // ISO datetime
}

export interface Escalation {
  id: string;
  session_id: string;
  patient_id: string;
  severity: Severity;
  reason: string;
  symptoms_flagged: string[];
  notified_at: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
}

export interface OutreachSession {
  id: string;
  patient_id: string;
  discharge_id: string;
  scheduled_at: string;
  started_at: string | null;
  completed_at: string | null;
  channel: string; // "voice"
  status: SessionStatus;
  outreach_number: number;
  twilio_call_sid: string | null;
  created_at: string;
}

export interface AnalyticsSummary {
  total_patients: number;
  high_risk_patients: number;
  open_escalations: number;
  urgent_escalations: number;
  generated_at: string;
}
