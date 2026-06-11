// Mirrors backend/app/events.py + the pydantic models it serializes.

export interface SubjectProperty {
  community: string
  property_type: string
  beds: number
  baths: number
  sqft: number
  year_built: number
  lot_sqft: number | null
  garage_stalls: number
  notes: string
}

export interface Conflict {
  field: string
  values: Record<string, number | string>
  resolved_with: string
}

export interface PropertyRecord {
  address_key: string
  address: string
  community: string
  property_type: string
  beds: number | null
  beds_bsmt: number
  baths: number | null
  sqft: number | null
  lot_sqft: number | null
  year_built: number | null
  garage_stalls: number
  lat: number
  lon: number
  sold_price: number | null
  sold_date: string | null
  assessed_value: number | null
  sources: Record<string, string>
  conflicts: Conflict[]
}

export interface ScoredComp {
  comp: PropertyRecord
  score: number
  score_parts: Record<string, number>
}

export interface ReviewVerdict {
  address_key: string
  verdict: 'keep' | 'demote' | 'exclude'
  reason: string
  unreviewed: boolean
}

export interface AdjustedComp {
  address_key: string
  address: string
  sold_price: number
  sold_date: string
  score: number
  adjustments: Record<string, number>
  adjusted_price: number
}

export interface RiskFlag {
  code: string
  severity: 'info' | 'caution' | 'warning'
  message: string
  evidence: Record<string, unknown>
}

export interface ValuationPayload {
  estimate: number | null
  low?: number
  high?: number
  confidence?: 'A' | 'B' | 'C'
  adjustments?: AdjustedComp[]
  flags: RiskFlag[]
}

export interface SearchCriteria {
  radius_km: number
  days: number
  sqft_pct: number
  beds_delta: number
}

export interface SearchUpdate {
  round: number
  criteria: SearchCriteria
  found: number
  reason: string
}

export interface NodeEvent {
  node: string
  status: 'started' | 'done' | 'fallback'
  detail?: string
}

export interface CommunityInfo {
  community: string
  sales: number
  median_price: number
  types: string[]
}

export type AgentEvent =
  | { type: 'node'; data: NodeEvent }
  | { type: 'search_update'; data: SearchUpdate }
  | { type: 'comps'; data: { items: ScoredComp[] } }
  | { type: 'reviews'; data: { items: ReviewVerdict[] } }
  | { type: 'valuation'; data: ValuationPayload }
  | { type: 'narrative_delta'; data: { text: string } }
  | { type: 'done'; data: { run_id: string; timings: { total_s: number } } }
  | { type: 'error'; data: { message: string; recoverable: boolean } }
