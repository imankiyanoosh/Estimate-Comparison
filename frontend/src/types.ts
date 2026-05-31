export interface LineItem {
  id: string
  room_name: string
  category_code: string
  category_name: string
  selector_code: string
  activity_code: string
  description_raw: string
  qty: number
  unit: string
  unit_price: number
  tax: number
  rcv: number
  depreciation: number
  acv: number
  source_page: number
  is_misc: boolean
  is_code_upgrade: boolean
  extraction_confidence: number
}

export interface LineMatch {
  id: string
  match_type: string
  match_state: string
  confidence: number
  score_breakdown: Record<string, number>
  qty_delta: number
  unit_price_delta: number
  rcv_delta: number
  human_reviewed: boolean
  carrier_item: LineItem | null
  pa_item: LineItem | null
}

export interface EstimateSummary {
  id: string
  source: string
  price_list_code: string | null
  estimator_name: string | null
  insured_name: string | null
  claim_number: string | null
  date_entered: string | null
  total_rcv: number
  total_acv: number
  overhead_pct: number
  profit_pct: number
  extraction_confidence: number
  qa_passed: boolean
  qa_issues: string[]
}

export interface ExecutiveSummary {
  pa_total: number
  carrier_total: number
  total_delta: number
  matched_count: number
  missing_count: number
  only_in_carrier_count: number
  qty_diff_count: number
  price_diff_count: number
  unresolved_count: number
  exact_match_count: number
  price_list_warning: boolean
}

export interface RoomBreakdown {
  room_name: string
  carrier_rcv: number
  pa_rcv: number
  rcv_delta: number
  line_count_carrier: number
  line_count_pa: number
  missing_count: number
}

export interface CategoryBreakdown {
  category_code: string
  category_name: string
  carrier_rcv: number
  pa_rcv: number
  rcv_delta: number
  pct_variance: number
  missing_count: number
}

export interface FinancialDelta {
  kind: string
  carrier_value: number
  pa_value: number
  delta: number
  rationale: string
}

export interface ReportData {
  job: { id: string; status: string; carrier_filename: string; pa_filename: string; created_at: string }
  carrier_estimate: EstimateSummary | null
  pa_estimate: EstimateSummary | null
  executive_summary: ExecutiveSummary
  room_breakdown: RoomBreakdown[]
  category_breakdown: CategoryBreakdown[]
  line_matches: LineMatch[]
  financial_deltas: FinancialDelta[]
}

export interface JobStatus {
  job_id: string
  status: string
  carrier_filename: string
  pa_filename: string
  created_at: string
  error_message: string | null
  carrier_estimate: EstimateSummary | null
  pa_estimate: EstimateSummary | null
}
