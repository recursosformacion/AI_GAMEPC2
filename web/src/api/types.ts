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
  page?: number;
  composer?: string | null;
  title?: string | null;
  catalogue?: string | null;
  instrumentation?: string | null;
  language?: string | null;
}

export interface WorkInfo {
  work_id: string;
  title: string;
  composer: string | null;
  catalogue: string | null;
  collection?: string | null;
}

export interface RepresentationInfo {
  id: string;
  provider: string;
  format: string;
  confidence: number;
  url?: string | null;
  title?: string | null;
}

export interface EvidenceInfo {
  source: string;
  code: string;
  score: number;
}

export interface WorkRelationships {
  aliases?: string[];
  related_catalogues?: string[];
  editions?: string[];
  parent_work?: string | null;
  movements?: string[];
}

export interface SearchResultItem {
  work: WorkInfo;
  representation: RepresentationInfo;
  representations?: RepresentationInfo[];
  score: number;
  evidence: EvidenceInfo[];
  relationships?: WorkRelationships | null;
}

export interface SearchResponse {
  search_id: string;
  results: SearchResultItem[];
  total?: number;
  page?: number;
  per_page?: number;
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

export interface RepositorySourceSummary {
  source_id: string;
  name: string;
  type: string;
  origin: string;
  trust: string;
  status: string;
  quality: number;
  quality_label: string;
  updated_at: string;
}

export interface SourceObservation {
  date: string;
  text: string;
}

export interface RepositorySource {
  source_id: string;
  name: string;
  type: string;
  origin: string;
  trust: string;
  status: string;
  quality: number;
  quality_label: string;
  updated_at: string;
  representations: number;
  works: number;
  composers: number;
  formats: string[];
  catalogues: string[];
  duplicate_percent: number;
  coverage: string[];
  capabilities: string[];
  description: string;
  license: string;
  website: string;
  contact: string;
  notes: string;
  observations: SourceObservation[];
  tags: string[];
  community_rating: number;
  reviews: number;
  searches: number;
  downloads: number;
  contributions: number;
  availability: number;
}

export interface SessionSource {
  source_id: string;
  name: string;
  type: string;
  location: string;
  status: string;
  analysis: Record<string, unknown>;
  created_at: string;
}

export interface SessionSourceCreate {
  name: string;
  type: string;
  location: string;
}

export interface DiscoverSource {
  source_id: string;
  name: string;
  type: string;
  origin: string;
  trust: string;
  quality: number;
  url: string;
}

export interface SearchModelCriteria {
  key: string;
  label: string;
}

export interface SearchModelBlock {
  id: string;
  label: string;
  kind: string;
  criteria: SearchModelCriteria[];
  options: string[];
}

export interface SearchModel {
  blocks: SearchModelBlock[];
}

export interface IntentResponse {
  type: string;
  label: string;
}

// --- compositores (consulta pública + fusión admin) -------------------------

export interface ComposerSummary {
  id: string;
  name: string;
  status: string;
  aliases_count: number;
  works_count: number;
  review_status: string | null;
}

export interface ComposerList {
  items: ComposerSummary[];
  total: number;
}

export interface ComposerCreationEvidence {
  composer_id: string;
  extracted_author: string | null;
  work_id: number | null;
  work_title: string | null;
  provider: string | null;
  resource_reference: string | null;
}

export interface ComposerDetail {
  id: string;
  name: string;
  status: string;
  aliases: string[];
  works_count: number;
  merged_into: string | null;
  merged_at: string | null;
  creation_evidence: ComposerCreationEvidence[];
  review_status: string | null;
  reviewed_at: string | null;
}

export interface ComposerWorkRef {
  work_id: number;
  title: string | null;
  composer_id: string | null;
  tags: string | null;
}export interface ComposerWorks {
  items: ComposerWorkRef[];
  total: number;
}

export interface MergeComposersResult {
  target_id: string;
  sources_merged: string[];
  aliases_transferred: number;
  works_moved: number;
  merge_operation_id: string | null;
}

// --- identidad (navegación de autenticación) --------------------------------

export interface FrontendUser {
  user_id: string;
  roles: string[];
  email_verified: boolean;
}

export interface AuthSession {
  access_token: string;
  refresh_token: string;
  user_id: string;
  roles: string[];
  email_verified: boolean;
}

export interface VoteResponse {
  work_id: string;
  vote: number;
  voted_at: string;
  vote_day: string;
}

export interface Statistics {
  rating: number | null;
  adjusted_rating: number | null;
  vote_count: number;
  work_count: number;
  confidence: number | null;
  calculated_at: string | null;
}

export interface WorkStatistics extends Statistics {
  work_id: string;
}

export interface ComposerStatistics extends Statistics {
  composer_id: string;
}

export interface VotesOverview {
  total_votes: number;
  top_works: Array<{ work_id: string; vote_count: number; rating: number | null; work_count: number }>;
  top_composers: Array<{ composer_id: string; vote_count: number; rating: number | null; work_count: number }>;
  last_execution: { kind: string; status: string; started_at: string; finished_at: string } | null;
}

export interface WorkResource {
  relative_path?: string | null;
  format?: string | null;
  file_id?: number | null;
  available?: boolean;
  url?: string | null;
}

export interface WorkDetailWork {
  id?: number | null;
  title?: string | null;
  composer?: string | null;
  composer_id?: string | null;
  artist?: string | null;
  tags?: string | null;
  catalogue?: string | null;
}

export interface WorkDetail {
  work: WorkDetailWork;
  resources: WorkResource[];
}

export interface SystemHealth {
  status: string;
  storage_target: string | null;
  read_only: boolean;
}

export interface SourcePreview {
  ok: boolean;
  fields: string[];
  error: string | null;
}

export interface SourceSuggestion {
  id: string;
  name: string;
  type: string;
  location: string;
  mapping: Record<string, unknown>;
  requested_by: string;
  status: string;
  admin_message: string | null;
  created_at: string;
}

export interface RegisterResult {
  user_id: string | null;
  verification_token: string | null;
  message: string;
}

export interface VerifyEmailResult {
  message: string;
}
