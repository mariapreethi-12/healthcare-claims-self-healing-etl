export type Run = {
  id: string; filename: string; status: string; mapping_source: string | null;
  total_records: number; accepted_records: number; rejected_records: number;
  created_at: string; completed_at: string | null;
};
export type Event = {
  id: string; run_id: string; source_column: string; target_column: string | null;
  event_type: string; confidence: number | null; resolution: string; created_at: string;
};
export type RunDetail = Run & {
  detected_columns: string[]; suggested_mapping: Record<string, string>;
  approved_mapping: Record<string, string> | null; error_message: string | null; events: Event[];
};
export type Claim = {
  id: string; run_id: string; claim_id: string; patient_id: string; provider_id: string;
  diagnosis_code: string; procedure_code: string; claim_amount: string; claim_date: string; claim_status: string;
};
export type Metrics = {
  total_runs: number; completed_runs: number; pending_approval_runs: number; total_claims: number;
  rejected_claims: number; acceptance_rate: number; total_claim_amount: number; schema_events: number;
  status_breakdown: Record<string, number>; recent_runs: Run[];
};
