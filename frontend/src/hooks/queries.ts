import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type OnboardInput } from "../lib/api";
import type { RiskLevel } from "../lib/types";

export function usePatients(riskLevel?: RiskLevel) {
  return useQuery({
    queryKey: ["patients", riskLevel ?? "all"],
    queryFn: () => api.listPatients(riskLevel),
  });
}

export function usePatientSessions(patientId: string | undefined) {
  return useQuery({
    queryKey: ["sessions", patientId],
    queryFn: () => api.patientSessions(patientId!),
    enabled: !!patientId,
  });
}

export function useEscalations(unresolvedOnly: boolean) {
  return useQuery({
    queryKey: ["escalations", unresolvedOnly],
    queryFn: () => api.listEscalations(unresolvedOnly),
  });
}

export function useAnalytics() {
  return useQuery({
    queryKey: ["analytics"],
    queryFn: () => api.analyticsSummary(),
    refetchInterval: 60_000,
  });
}

export function useCallPatient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patientId: string) => api.callPatient(patientId),
    onSuccess: (_data, patientId) => {
      qc.invalidateQueries({ queryKey: ["sessions", patientId] });
      qc.invalidateQueries({ queryKey: ["patients"] });
    },
  });
}

export function useCallHighRisk() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.callHighRisk(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      qc.invalidateQueries({ queryKey: ["patients"] });
    },
  });
}

export function useOnboardPatient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: OnboardInput) => api.onboardPatient(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useResolveEscalation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, resolvedBy }: { id: string; resolvedBy: string }) =>
      api.resolveEscalation(id, resolvedBy),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["escalations"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}
