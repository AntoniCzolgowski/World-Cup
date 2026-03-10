import type {
  BusinessDetailResponse,
  BusinessMatchComparison,
  LayerKey,
  MatchesResponse,
  MetaResponse,
  OpportunityBoardResponse,
  ProvenanceResponse,
  ReportJobResponse,
  SignalPlanResponse,
  SimulationSnapshotResponse,
  WhatIfResponse,
  ZoneDetailResponse,
} from "./types";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export function fetchMatches(cityId?: string): Promise<MatchesResponse> {
  const query = new URLSearchParams();
  if (cityId) query.set("city_id", cityId);
  const qs = query.toString();
  return requestJson<MatchesResponse>(`/api/matches${qs ? `?${qs}` : ""}`);
}

export function fetchMeta(params?: { cityId?: string; matchId?: string }): Promise<MetaResponse> {
  const query = new URLSearchParams();
  if (params?.cityId) query.set("city_id", params.cityId);
  if (params?.matchId) query.set("match_id", params.matchId);
  const qs = query.toString();
  return requestJson<MetaResponse>(`/api/meta${qs ? `?${qs}` : ""}`);
}

export function fetchSimulation(params: {
  day: number;
  step: number;
  scenario: string;
  layer: LayerKey;
  cityId?: string;
  matchId?: string;
}): Promise<SimulationSnapshotResponse> {
  const query = new URLSearchParams({
    day: String(params.day),
    step: String(params.step),
    scenario: params.scenario,
    layer: params.layer,
  });
  if (params.cityId) query.set("city_id", params.cityId);
  if (params.matchId) query.set("match_id", params.matchId);
  return requestJson<SimulationSnapshotResponse>(`/api/simulation?${query.toString()}`);
}

export function fetchBusiness(params: {
  businessId: string;
  day: number;
  scenario: string;
  cityId?: string;
  matchId?: string;
}): Promise<BusinessDetailResponse> {
  const query = new URLSearchParams({
    day: String(params.day),
    scenario: params.scenario,
  });
  if (params.cityId) query.set("city_id", params.cityId);
  if (params.matchId) query.set("match_id", params.matchId);
  return requestJson<BusinessDetailResponse>(`/api/business/${params.businessId}?${query.toString()}`);
}

export function fetchBusinessComparison(params: { businessId: string; cityId?: string }): Promise<BusinessMatchComparison> {
  const query = new URLSearchParams();
  if (params.cityId) query.set("city_id", params.cityId);
  const qs = query.toString();
  return requestJson<BusinessMatchComparison>(`/api/business/${params.businessId}/compare${qs ? `?${qs}` : ""}`);
}

export function fetchZone(params: {
  zoneId: string;
  day: number;
  scenario: string;
  cityId?: string;
  matchId?: string;
}): Promise<ZoneDetailResponse> {
  const query = new URLSearchParams({
    day: String(params.day),
    scenario: params.scenario,
  });
  if (params.cityId) query.set("city_id", params.cityId);
  if (params.matchId) query.set("match_id", params.matchId);
  return requestJson<ZoneDetailResponse>(`/api/zone/${params.zoneId}?${query.toString()}`);
}

export function createBusinessReport(params: {
  businessId: string;
  day: number;
  scenario: string;
  visibleSections: Record<string, boolean>;
  cityId?: string;
  matchId?: string;
}): Promise<ReportJobResponse> {
  const query = new URLSearchParams();
  if (params.cityId) query.set("city_id", params.cityId);
  if (params.matchId) query.set("match_id", params.matchId);
  const qs = query.toString();
  return requestJson<ReportJobResponse>(`/api/business/${params.businessId}/report${qs ? `?${qs}` : ""}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      day: params.day,
      scenario: params.scenario,
      visible_sections: params.visibleSections,
    }),
  });
}

export function fetchReportJob(jobId: string): Promise<ReportJobResponse> {
  return requestJson<ReportJobResponse>(`/api/reports/${jobId}`);
}

export function fetchSignals(params: {
  day: number;
  step: number;
  scenario: string;
  cityId?: string;
  matchId?: string;
}): Promise<SignalPlanResponse> {
  const query = new URLSearchParams({
    day: String(params.day),
    step: String(params.step),
    scenario: params.scenario,
  });
  if (params.cityId) query.set("city_id", params.cityId);
  if (params.matchId) query.set("match_id", params.matchId);
  return requestJson<SignalPlanResponse>(`/api/optimize-signals?${query.toString()}`);
}

export function fetchOpportunityBoard(params: { businessId: string; cityId?: string }): Promise<OpportunityBoardResponse> {
  const query = new URLSearchParams();
  if (params.cityId) query.set("city_id", params.cityId);
  const qs = query.toString();
  return requestJson<OpportunityBoardResponse>(`/api/business/${params.businessId}/opportunity-board${qs ? `?${qs}` : ""}`);
}

export function fetchProvenance(): Promise<ProvenanceResponse> {
  return requestJson<ProvenanceResponse>("/api/provenance");
}

export function runWhatIf(params: {
  day: number;
  step: number;
  blockedEdgeIds: string[];
  durationSteps?: number;
  cityId?: string;
  matchId?: string;
}): Promise<WhatIfResponse> {
  const query = new URLSearchParams();
  if (params.cityId) query.set("city_id", params.cityId);
  if (params.matchId) query.set("match_id", params.matchId);
  const qs = query.toString();
  return requestJson<WhatIfResponse>(`/api/what-if${qs ? `?${qs}` : ""}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      day: params.day,
      timestep: params.step,
      blocked_edges: params.blockedEdgeIds,
      duration_steps: params.durationSteps,
    }),
  });
}
