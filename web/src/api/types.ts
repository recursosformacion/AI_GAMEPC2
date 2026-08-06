// Public contract types of the OSAP REST API (V3.1). Independent of the domain model.

export interface SuccessEnvelope<T> {
  success: true;
  request_id: string;
  data: T;
}

export interface ErrorBody {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ErrorEnvelope {
  success: false;
  request_id: string;
  error: ErrorBody;
}

export type Envelope<T> = SuccessEnvelope<T> | ErrorEnvelope;

export interface SearchRequest {
  query: string;
  limit: number;
}

export interface WorkInfo {
  work_id: string;
  title: string;
  composer: string | null;
  catalogue: string | null;
}

export interface RepresentationInfo {
  provider: string;
  format: string;
  confidence: number;
}

export interface EvidenceInfo {
  source: string;
  code: string;
  score: number;
}

export interface SearchResultItem {
  work: WorkInfo;
  representation: RepresentationInfo;
  score: number;
  evidence: EvidenceInfo[];
}

export interface SearchResponse {
  search_id: string;
  results: SearchResultItem[];
}

export interface JobCreateRequest {
  type: string;
}

export interface JobResponse {
  job_id: string;
  type: string;
  state: string;
  progress: number;
  result: Record<string, unknown>;
}

export interface ProviderResponse {
  provider_id: string;
  name: string;
  available: boolean;
  formats: string[];
  last_sync: string | null;
}

export interface KnowledgeObservation {
  execution_id: string;
  source: string;
  field: string;
  value: string;
  provider: string | null;
}

export interface KnowledgeFact {
  fact_type: string;
  field: string;
  value: string;
  count: number;
}

export interface KnowledgeSuggestion {
  suggestion_type: string;
  field: string;
  source_value: string;
  target_value: string;
  reason: string;
}

export interface SystemHealth {
  status: string;
}

export interface SystemVersion {
  version: string;
}

export interface SystemStatistics {
  providers: number;
  searches: number;
  jobs: number;
  knowledge_observations: number;
  knowledge_facts: number;
  knowledge_suggestions: number;
}
