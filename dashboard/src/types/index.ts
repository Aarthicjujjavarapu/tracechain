// TypeScript types — mirrors Pydantic backend schemas
// Fully populated in Step 7

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
