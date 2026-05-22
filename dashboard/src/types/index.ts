// TypeScript types — mirrors Pydantic backend schemas

export type RunStatus = "pending" | "running" | "success" | "failed";
export type StepType = "step" | "llm_step";
export type LLMStatus = "success" | "failed";

export interface WorkflowRun {
  id: string;
  workflow_name: string;
  status: RunStatus;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  total_cost: number | null;
  total_tokens: number | null;
  original_run_id: string | null;
  is_replay: boolean;
  metadata: Record<string, unknown> | null;
  reliability_score: number | null;
  reliability_reasons: string[] | null;
}

// ── Failure Classification ─────────────────────────────────────────────────────

export type FailureSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface FailureClassification {
  id:             string;
  run_id:         string;
  step_id:        string | null;
  category:       string;
  severity:       FailureSeverity;
  evidence:       Record<string, unknown> | null;
  recommendation: string | null;
  created_at:     string;
}

// ── Incidents ─────────────────────────────────────────────────────────────────

export type IncidentStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";

export interface Incident {
  id:                 string;
  title:              string;
  category:           string;
  severity:           FailureSeverity;
  status:             IncidentStatus;
  workflow_name:      string | null;
  occurrence_count:   number;
  first_seen_at:      string;
  last_seen_at:       string;
  evidence:           Record<string, unknown> | null;
  recommended_action: string | null;
  resolved_at:        string | null;
  created_at:         string;
}

export interface TraceStep {
  id: string;
  run_id: string;
  step_name: string;
  step_type: StepType;
  status: RunStatus;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  retry_count: number;
  metadata: Record<string, unknown> | null;
}

export interface LLMCall {
  id: string;
  run_id: string;
  step_id: string | null;
  provider: string;
  model: string;
  prompt: string;
  response: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  estimated_cost: number | null;
  latency_ms: number | null;
  time_to_first_token_ms: number | null;
  is_stream: boolean;
  temperature: number | null;
  status: LLMStatus;
  error_message: string | null;
  prompt_version: string | null;
  created_at: string;
}

export interface PromptVersion {
  id: string;
  prompt_name: string;
  version: string;
  prompt_text: string;
  is_active: boolean;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface EvaluationResult {
  id: string;
  run_id: string;
  relevance_score: number;
  groundedness_score: number;
  hallucination_risk: number;
  quality_score: number;
  failure_reason: string | null;
  created_at: string;
}

export interface HumanFeedback {
  id: string;
  run_id: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface OverviewMetrics {
  total_runs: number;
  success_rate: number;
  avg_latency_ms: number;
  total_cost: number;
  total_tokens: number;
  failure_count: number;
}

export interface WorkflowHealth {
  workflow_name:         string;
  run_count:             number;
  avg_reliability_score: number | null;
  success_rate:          number;
  open_incidents:        number;
  top_failure_category:  string | null;
  trend:                 "improving" | "degrading" | "stable" | "insufficient_data";
  trend_delta:           number | null;
}

// ── Agent graph ───────────────────────────────────────────────────────────────

export type NodeStatus = "running" | "ok" | "error" | "retrying";
export type NodeKind   = "workflow" | "step" | "llm" | "tool" | "retriever" | "reranker" | "memory" | "validator" | "agent" | "embedding";

export interface GraphNodeData {
  label:         string;
  status:        NodeStatus;
  kind:          NodeKind;
  duration_ms:   number | null;
  input_tokens:  number | null;
  output_tokens: number | null;
  cost_usd:      number | null;
  retry_count:   number;
  attributes:    Record<string, unknown>;
}

export interface GraphNode {
  id:       string;
  type:     NodeKind;
  position: { x: number; y: number };
  data:     GraphNodeData;
}

export interface GraphEdge {
  id:     string;
  source: string;
  target: string;
  type:   string;
}

export interface RunGraph {
  run_id:   string;
  trace_id: string;
  nodes:    GraphNode[];
  edges:    GraphEdge[];
}

// ── Diagnostics ───────────────────────────────────────────────────────────────

export interface RetryAttempt {
  attempt:       number;
  delay_ms:      number;
  error_type:    string;
  error_message: string;
  timestamp_ns:  number;
}

export interface RetryChain {
  span_id:        string;
  span_name:      string;
  max_attempts:   number;
  attempt_count:  number;
  exhausted:      boolean;
  final_status:   string;
  total_delay_ms: number;
  unique_errors:  string[];
  attempts:       RetryAttempt[];
}

export interface BottleneckSpan {
  span_id:          string;
  name:             string;
  kind:             string;
  duration_ms:      number;
  pct_of_run:       number;
  is_critical_path: boolean;
  parent_id:        string | null;
  depth:            number;
}

export interface LatencyReport {
  total_run_ms:      number;
  p50_ms:            number;
  p95_ms:            number;
  p99_ms:            number;
  slow_threshold_ms: number;
  slow_spans:        string[];
  critical_path:     string[];
  bottlenecks:       BottleneckSpan[];
}

export interface ModelUsage {
  model:         string;
  provider:      string;
  call_count:    number;
  input_tokens:  number;
  output_tokens: number;
  total_tokens:  number;
  cost_usd:      number;
}

export interface TokenReport {
  total_input_tokens:  number;
  total_output_tokens: number;
  total_tokens:        number;
  total_cost_usd:      number;
  by_model:            ModelUsage[];
  anomalies:           string[];
}

export interface ContextWarning {
  span_id:   string;
  span_name: string;
  model:     string;
  kind:      string;
  message:   string;
  severity:  "warning" | "critical";
}

export interface RunDiagnostics {
  run_id:        string;
  retry_chains:  RetryChain[];
  retry_summary: { total_chains: number; total_attempts: number; exhausted: number; total_delay_ms: number };
  latency:       LatencyReport;
  tokens:        TokenReport;
  context_window:{ warning_count: number; critical_count: number; warnings: ContextWarning[] };
}

// ── Alert Rules ───────────────────────────────────────────────────────────────

export type AlertMetric   = "success_rate" | "avg_latency_ms" | "avg_cost" | "open_incidents" | "reliability_score";
export type AlertOperator = "lt" | "lte" | "gt" | "gte";

export interface AlertRule {
  id:             string;
  name:           string;
  metric:         AlertMetric;
  operator:       AlertOperator;
  threshold:      number;
  window_minutes: number;
  severity:       FailureSeverity;
  workflow_name:  string | null;
  enabled:        boolean;
  created_at:     string;
}

export interface AlertFiring {
  id:           string;
  rule_id:      string;
  metric_value: number;
  fired_at:     string;
  resolved_at:  string | null;
  is_active:    boolean;
}

export interface AlertSummary {
  total_rules:   number;
  enabled_rules: number;
  firing_now:    number;
}
