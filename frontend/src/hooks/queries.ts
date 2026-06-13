import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
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
