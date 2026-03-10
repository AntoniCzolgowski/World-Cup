export type LayerKey = "total" | "team_a" | "team_b" | "neutral" | "locals";
export type EntityType = "business" | "stadium" | "fanzone";
export type MetricFilterKey = "demand" | "capacity" | "revenue" | "audience" | "recommendations" | "competition" | "report_sections";

export interface MatchSummary {
  match_id: string;
  title: string;
  stage: string;
  home_team: { id: string; name: string; color: string };
  away_team: { id: string; name: string; color: string };
  kickoff_local: string;
  venue: string;
  venue_capacity: number;
}

export interface MatchesResponse {
  city_id: string;
  available_cities: Array<{ city_id: string; label: string; simulation_ready: boolean }>;
  matches: MatchSummary[];
  default_match_id: string;
}

export interface MatchMeta extends MatchSummary {
  city_id: string;
  city: string;
  day_offsets: number[];
  step_minutes: number;
  timeline: { start_hour: number; end_hour: number; steps: number };
  cultural_notes?: Record<string, string>;
}

export interface ZoneMeta {
  id: string;
  name: string;
  kind: string;
  node_id: string;
  center: [number, number];
  radius_m: number;
  focus_color: string;
  capacity: number;
  node: { id: string; label: string; lat: number; lng: number };
}

export interface EdgeMeta {
  id: string;
  source: string;
  target: string;
  road_name: string;
  capacity: number;
  base_travel_minutes: number;
  distance_km: number;
  kind: string;
  bidirectional: boolean;
  path: [number, number][];
}

export interface BusinessMeta {
  id: string;
  name: string;
  type: string;
  zone_id: string;
  node_id: string;
  lat: number;
  lng: number;
  rating: number;
  price_level: number;
  capacity_estimate: number;
  hours: string;
  source: string;
  signature_item: string;
}

export interface SpecialVenueMeta {
  id: string;
  name: string;
  entity_type: "stadium" | "fanzone";
  zone_id: string;
  lat: number;
  lng: number;
  comfort_capacity: number;
  kind: string;
}

export interface MetaResponse {
  app: { name: string; scenario_ids: string[]; city_id: string };
  match: MatchMeta;
  timeline: {
    step_minutes: number;
    steps_per_day: number;
    time_labels: string[];
    days: number[];
    match_markers: {
      kickoff_step: number;
      halftime_step: number;
      final_whistle_step: number;
      kickoff_label: string;
      halftime_label: string;
      final_whistle_label: string;
    };
  };
  zones: ZoneMeta[];
  edges: EdgeMeta[];
  businesses: BusinessMeta[];
  special_venues: SpecialVenueMeta[];
  pois: SpecialVenueMeta[];
  weather: Record<string, { temp_c: number; condition: string; walking_modifier: number }>;
  map_config?: {
    provider: "google_maps_js" | "none";
    google_maps_api_key: string | null;
    default_map_type: "roadmap" | "terrain" | "hybrid";
    available_map_types: Array<"roadmap" | "terrain" | "hybrid">;
    initial_center: [number, number];
    initial_zoom: number;
  };
  available_layers: LayerKey[];
  source_availability: Record<string, boolean>;
}

export interface ZoneSnapshot {
  zone_id: string;
  name: string;
  kind: string;
  center: [number, number];
  value: number;
  capacity: number;
  utilization: number;
  focus_color: string;
}

export interface EdgeSnapshot {
  edge_id: string;
  road_name: string;
  kind: string;
  load: number;
  capacity: number;
  congestion: number;
}

export interface BusinessOverlay {
  business_id: string;
  name: string;
  type: string;
  zone_id: string;
  value: number;
  rating: number;
  google_rating: number;
  capacity_estimate: number;
}

export interface SpecialOverlay {
  entity_id: string;
  entity_type: "stadium" | "fanzone";
  zone_id: string;
  name: string;
  value: number;
  comfort_capacity: number;
  crowd_pressure: number;
  lat: number;
  lng: number;
}

export interface SimulationSnapshotResponse {
  scenario_id: string;
  day: number;
  step: number;
  time_label: string;
  layer: LayerKey;
  zones: ZoneSnapshot[];
  edges: EdgeSnapshot[];
  business_overlay: BusinessOverlay[];
  special_overlay: SpecialOverlay[];
  summary: {
    city_total: number;
    active_travelers: number;
    busiest_zone: ZoneSnapshot;
    busiest_business: BusinessOverlay;
    busiest_special_venue: SpecialOverlay | null;
    most_congested_edge: EdgeSnapshot;
    weather: { temp_c: number; condition: string; walking_modifier: number };
    watch_items: Array<{ label: string; value: string; detail: string }>;
  };
}

export interface MetricExplanation {
  title: string;
  definition: string;
  formula: string;
  inputs: Record<string, number | string | boolean>;
  notes: string[];
}

export interface TimeSeriesPoint {
  step: number;
  label: string;
  value: number;
  marker?: string | null;
}

export interface BusinessMatchComparisonEntry {
  match_id: string;
  title: string;
  stage: string;
  home_team: { id: string; name: string; color: string };
  away_team: { id: string; name: string; color: string };
  kickoff_local: string;
  served_visits_today: number;
  peak_active_visitors: number;
  peak_label: string;
  revenue_estimate: number;
  dominant_nationality: string;
  dominant_share: number;
}

export interface BusinessMatchComparison {
  business_id: string;
  city_id: string;
  comparisons: BusinessMatchComparisonEntry[];
}

export interface BusinessDetailResponse {
  entity_type: "business";
  business: BusinessMeta;
  day: number;
  scenario_id: string;
  active_visitors_series_15m: TimeSeriesPoint[];
  peak: { step: number; label: string; active_visitors: number };
  peak_active_visitors: number;
  peak_capacity_pct_capped: number;
  served_visits_today: number;
  served_revenue: {
    total: number;
    avg_spend: number;
    service_capture_rate: number;
    served_visits_today: number;
  };
  google_rating: { value: number; source: string };
  nationality_mix: Record<string, number>;
  day_comparison: Array<{ day: number; label: string; served_visits_today: number; peak_active_visitors: number; peak_label: string }>;
  zone_context: {
    zone_id: string;
    zone_name: string;
    zone_kind: string;
    venues_in_zone: number;
    venue_rank: number;
    zone_total_served_visits: number;
    share_of_zone_demand: number;
  };
  audience_profile: {
    dominant_segment: string;
    dominant_label: string;
    dominant_share: number;
    spend_profile: string;
  };
  playbook: {
    pressure_level: string;
    tone: "danger" | "warning" | "accent" | "ok";
    peak_window: string;
    estimated_turns: number;
    dominant_segment: string;
    dominant_label: string;
    dominant_share: number;
    spend_profile: string;
    action_options: Array<{ title: string; detail: string; priority: string; timing: string }>;
    watchouts: string[];
  };
  peer_benchmark: Array<{ business_id: string; name: string; type: string; served_visits_today: number; peak_label: string; google_rating: number }>;
  insight_cards: Array<{ label: string; value: string; detail: string; tone: string; metric_key: string }>;
  metric_explanations: Record<string, MetricExplanation>;
  recommendation: { source: string; text: string; model: string | null };
  visible_sections: Record<MetricFilterKey, boolean>;
  provenance: {
    business_source: string;
    forecast_source: string;
    recommendation_source: string;
  };
  report_support: { can_generate_pdf: boolean };
}

export interface ZoneDetailResponse {
  entity_type: "stadium" | "fanzone";
  zone_id: string;
  venue: SpecialVenueMeta;
  day: number;
  scenario_id: string;
  active_people_series_15m: TimeSeriesPoint[];
  peak_active_people: number;
  peak: { step: number; label: string; active_people: number };
  arrivals_series_15m: TimeSeriesPoint[];
  departures_series_15m: TimeSeriesPoint[];
  cumulative_entries: number;
  cumulative_exits: number;
  audience_mix: Record<string, number>;
  wave_summary: { pre_match_peak: number; in_match_peak: number; post_match_peak: number };
  top_inbound_corridors: Array<{ edge_id: string; road_name: string; peak_load: number; peak_label: string }>;
  metric_explanations: Record<string, MetricExplanation>;
}

export interface ReportJobResponse {
  job_id: string;
  status: string;
  error?: string | null;
  download_url?: string | null;
}

export interface WhatIfResponse {
  scenario_id: string;
  blocked_edge_ids: string[];
  impact_summary: {
    blocked_edges: EdgeMeta[];
    top_spillovers: Array<{ edge_id: string; road_name: string; delta_congestion: number }>;
    busiest_zone_after_reroute: ZoneSnapshot;
    busiest_business_after_reroute: BusinessOverlay;
  };
}

export interface SignalPlanResponse {
  scenario_id: string;
  day: number;
  step: number;
  recommendations: Array<{
    intersection_id: string;
    label: string;
    lat: number;
    lng: number;
    score: number;
    focus_road: string;
    recommended_green_extension_sec: number;
    direction_bias: string;
  }>;
}

export interface OpportunityScoreBreakdown {
  revenue_index: number;
  demand_index: number;
  risk_index: number;
  capture_index: number;
  confidence_index: number;
}

export interface OpportunityMatch {
  match_id: string;
  title: string;
  stage: string;
  kickoff_local: string;
  home_team: { id: string; name: string; color: string };
  away_team: { id: string; name: string; color: string };
  revenue_estimate: number;
  served_visits: number;
  peak_capacity_pct: number;
  zone_share: number;
  dominant_segment: string;
  execution_pressure: number;
  stability_score: number;
  score_breakdown: OpportunityScoreBreakdown;
  opportunity_score: number;
  recommendation_tag: string;
  quick_recommendation: "Push" | "Hold" | "Avoid";
}

export interface PortfolioSummary {
  best_match_id: string;
  avg_opportunity_score: number;
  volatility_index: number;
  risk_exposure_pct: number;
  execution_pressure: number;
  stability_score: number;
  recommended_focus_match_ids: string[];
}

export interface OpportunityBoardResponse {
  business_id: string;
  city_id: string;
  portfolio_summary: PortfolioSummary;
  matches: OpportunityMatch[];
}

export interface ProvenanceResponse {
  generated_at: string;
  sources: Array<{ id: string; label: string; status: string; details: string }>;
  baseline_highlights: Record<string, unknown>;
  cohort_model: Record<string, unknown>;
}
