// ApiClient: the ONLY HTTP access point of the web client.
//
// Responsibilities:
//  - calls /api/v1/... endpoints
//  - serializes/deserializes DTOs
//  - interprets the uniform envelope (success / request_id / data / error)
//  - transforms REST errors into ApiError (code/message/details)
//
// Pages never call fetch/axios directly. Everything goes through this class.

import type {
  AmigosArticle,
  AmigosArticleCreateInput,
  AmigosArticleList,
  AmigosArticleUpdateInput,
  AmigosCoralDetails,
  AmigosCoralDetailsInput,
  AmigosEvent,
  AmigosEventInput,
  AmigosEventList,
  AmigosAuthorization,
  AmigosAuthorizationScope,
  AmigosGroup,
  AmigosGroupLink,
  AmigosMember,
  AmigosMemberList,
  AmigosMyGroup,
  AmigosMyPermissions,
  Catalogue,
  Collaborator,
  Ensemble,
  Epoch,
  Genre,
  Instrument,
  InstrumentCategory,
  ComposerDetail,
  CorrectionRequestRead,
  ComposerList,
  ComposerStatistics,
  ComposerSummary,
  ComposerWorks,
  AdminOverview,
  Alias,
  Envelope,
  MergeComposersResult,
  MoveAliasResult,
  OpProvider,
  PromoteAliasResult,
  ResolutionSession,
  ResolutionSessionCreateRequest,
  RepresentationInput,
  RepresentationSelection,
  SetAttributionResult,
  SourcePreview,
  SourceSuggestion,
  RegisterResult,
  VerifyEmailResult,
  VotesOverview,
  ActivityMe,
  AnalyticsMe,
  FunnelMetrics,
  WorkDetail,
  WorkStatistics,
  WorkAiProposal,
  WorkAiProposalPage,
  WorkAiProposalResult,
  WorkAiProposalStatus,
  WorkAiReviewAction,
  RecentWorkList,
  PopularWorkList,
  PublicWork,
  RepresentationSheet,
  RepresentationProbe,
  NotificationList,
} from "./types";
import { ApiError } from "./errors";

export const API_PREFIX = "/api/v1";

export interface AuthHandler {
  getToken: () => string | null;
  refresh: () => Promise<boolean>;
  logout: () => void;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch | undefined;
  private token: string | null = null;
  private auth: AuthHandler = {
    getToken: () => null,
    refresh: async () => false,
    logout: () => undefined,
  };

  constructor(baseUrl: string = API_PREFIX, fetcher?: typeof fetch) {
    this.baseUrl = baseUrl;
    // If no fetcher is provided, `globalThis.fetch` is resolved at call time. This keeps
    // the client testable (tests can stub `globalThis.fetch`) and works in the browser.
    this.fetcher = fetcher;
  }

  setToken(token: string | null): void {
    this.token = token;
  }

  getToken(): string | null {
    return this.token;
  }

  setAuthHandler(auth: AuthHandler): void {
    this.auth = auth;
  }

  /** Descarga el fichero de una representación para visualizarlo (devuelve la respuesta). */
  async fetchRepresentationFile(representationId: string): Promise<Response> {
    const doFetch = this.fetcher ?? globalThis.fetch.bind(globalThis);
    const headers: Record<string, string> = {};
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    return doFetch(
      `${this.baseUrl}/representations/${encodeURIComponent(representationId)}/download?view=1`,
      { headers }
    );
  }

  /** Sube una imagen de «Los amigos» (logo/portada/foto/anuncio) y devuelve su URL pública. */
  async uploadAmigosImage(
    file: File,
    opts: { groupId?: string; scope?: "group" | "events" | "blog" } = {},
  ): Promise<{ id: number; url: string }> {
    const doFetch = this.fetcher ?? globalThis.fetch.bind(globalThis);
    const params = new URLSearchParams({
      name: file.name,
      mime_type: file.type,
      scope: opts.scope ?? "group",
    });
    if (opts.groupId) params.set("group_id", opts.groupId);
    const headers: Record<string, string> = { "Content-Type": "application/octet-stream" };
    const token = this.auth.getToken() ?? this.token;
    if (token !== null) headers["Authorization"] = `Bearer ${token}`;
    const response = await doFetch(`${this.baseUrl}/amigos/uploads?${params.toString()}`, {
      method: "POST",
      headers,
      body: file,
    });
    let parsed: Envelope<{ id: number; url: string }> | null = null;
    try {
      parsed = (await response.json()) as Envelope<{ id: number; url: string }>;
    } catch {
      parsed = null;
    }
    if (parsed !== null && parsed.success === true) return parsed.data;
    if (parsed !== null && "error" in parsed && parsed.error) {
      throw new ApiError(parsed.error.code, parsed.error.message, parsed.error.details);
    }
    throw new ApiError("INVALID_RESPONSE", `Upload failed (HTTP ${response.status})`);
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  async patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("PATCH", path, body);
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>("DELETE", path);
  }

  async put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>("PUT", path, body);
  }

  async getComposers(
    q: string,
    limit: number,
    offset: number,
    review?: string,
    visible?: string,
  ): Promise<ComposerList> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (q) {
      params.set("q", q);
    }
    if (review) {
      params.set("review", review);
    }
    if (visible) {
      params.set("visible", visible);
    }
    return this.get<ComposerList>(`/composers?${params.toString()}`);
  }

  async getComposer(personId: string): Promise<ComposerDetail> {
    return this.get<ComposerDetail>(`/composers/${encodeURIComponent(personId)}`);
  }

  async getComposerBiography(personId: string): Promise<ComposerDetail> {
    return this.get<ComposerDetail>(`/composers/${encodeURIComponent(personId)}/biography`);
  }

  async getWork(workId: string): Promise<WorkDetail> {
    return this.get<WorkDetail>(`/works/${encodeURIComponent(workId)}`);
  }

  /** Obras incorporadas/actualizadas recientemente (alimenta la portada). */
  async getRecentWorks(limit = 8): Promise<RecentWorkList> {
    return this.get<RecentWorkList>(`/works/recent?limit=${limit}`);
  }

  /** Obras más consultadas de los últimos días (portada). */
  async getPopularWorks(limit = 5, days = 30): Promise<PopularWorkList> {
    return this.get<PopularWorkList>(`/works/popular?limit=${limit}&days=${days}`);
  }

  /** Ficha pública del índice (obras que no están en el store de compositores). */
  async getPublicWork(workId: string): Promise<PublicWork> {
    return this.get<PublicWork>(`/works/public/${encodeURIComponent(workId)}`);
  }

  /** Campana: mis notificaciones (y globales si soy admin). */
  async getNotifications(): Promise<NotificationList> {
    return this.get<NotificationList>("/notifications");
  }

  async markNotificationRead(id: number): Promise<{ ok: boolean }> {
    return this.post<{ ok: boolean }>(`/notifications/${id}/read`, {});
  }

  async markAllNotificationsRead(): Promise<{ ok: boolean }> {
    return this.post<{ ok: boolean }>("/notifications/read-all", {});
  }

  /** Ficha de una representación (obra, proveedor, formato y acciones). */
  async getRepresentation(representationId: string): Promise<RepresentationSheet> {
    return this.get<RepresentationSheet>(
      `/representations/${encodeURIComponent(representationId)}`,
    );
  }

  /** ¿Se puede servir el fichero externo en el visor? (retos anti-bot ⇒ false). */
  async probeRepresentation(representationId: string): Promise<RepresentationProbe> {
    return this.get<RepresentationProbe>(
      `/representations/${encodeURIComponent(representationId)}/probe`,
    );
  }

  /** Colaboradores públicos de un proyecto (fachada osap-api → support + auth). */
  async getCollaborators(project = "omr"): Promise<Collaborator[]> {
    return this.get<Collaborator[]>(`/public/collaborators?project=${encodeURIComponent(project)}`);
  }

  // --- «Los amigos» ---------------------------------------------------------

  /** Grupos públicos (o todos, incluidos inactivos, si se indica y hay permiso). */
  async getAmigosGroups(includeInactive = false, kind?: string): Promise<AmigosGroup[]> {
    const params = new URLSearchParams();
    if (includeInactive) params.set("include_inactive", "true");
    if (kind !== undefined && kind !== "") params.set("kind", kind);
    const qs = params.toString();
    return this.get<AmigosGroup[]>(`/amigos/groups${qs === "" ? "" : `?${qs}`}`);
  }

  async getAmigosGroupArticles(
    groupId: string,
    limit = 100,
    offset = 0,
  ): Promise<AmigosArticleList> {
    return this.get<AmigosArticleList>(
      `/amigos/groups/${encodeURIComponent(groupId)}/articles?limit=${limit}&offset=${offset}`,
    );
  }

  async getAmigosArticle(articleId: string): Promise<AmigosArticle> {
    return this.get<AmigosArticle>(`/amigos/articles/${encodeURIComponent(articleId)}`);
  }

  /** Grupos en los que puedo colaborar (con mi rol). Requiere sesión. */
  async getAmigosMyGroups(): Promise<AmigosMyGroup[]> {
    return this.get<AmigosMyGroup[]>("/amigos/my/groups");
  }

  /** Permisos del usuario en «Los amigos» (grupos, eventos, blog). */
  async getAmigosMyPermissions(): Promise<AmigosMyPermissions> {
    return this.get<AmigosMyPermissions>("/amigos/my/permissions");
  }

  /** Mis anuncios (o todos, si soy autorizador/admin). */
  async getAmigosMyEvents(): Promise<AmigosEventList> {
    return this.get<AmigosEventList>("/amigos/my/events");
  }

  /** Mis artículos del blog (o todos, si soy autorizador/admin). */
  async getAmigosMyBlog(limit = 200, offset = 0): Promise<AmigosArticleList> {
    return this.get<AmigosArticleList>(`/amigos/my/blog?limit=${limit}&offset=${offset}`);
  }

  async getAmigosMyArticles(limit = 100, offset = 0): Promise<AmigosArticleList> {
    return this.get<AmigosArticleList>(`/amigos/my?limit=${limit}&offset=${offset}`);
  }

  async createAmigosArticle(
    groupId: string,
    input: AmigosArticleCreateInput,
  ): Promise<AmigosArticle> {
    return this.post<AmigosArticle>(
      `/amigos/groups/${encodeURIComponent(groupId)}/articles`,
      input,
    );
  }

  async updateAmigosArticle(
    articleId: string,
    input: AmigosArticleUpdateInput,
  ): Promise<AmigosArticle> {
    return this.patch<AmigosArticle>(`/amigos/articles/${encodeURIComponent(articleId)}`, input);
  }

  async submitAmigosArticle(articleId: string): Promise<AmigosArticle> {
    return this.post<AmigosArticle>(`/amigos/articles/${encodeURIComponent(articleId)}/submit`);
  }

  async publishAmigosArticle(articleId: string): Promise<AmigosArticle> {
    return this.post<AmigosArticle>(`/amigos/articles/${encodeURIComponent(articleId)}/publish`);
  }

  async withdrawAmigosArticle(articleId: string): Promise<AmigosArticle> {
    return this.post<AmigosArticle>(`/amigos/articles/${encodeURIComponent(articleId)}/withdraw`);
  }

  // --- «Los amigos» (administración de grupos y moderación) -----------------

  async createAmigosGroup(input: {
    name: string;
    kind?: string;
    slug?: string | null;
    description?: string | null;
    image_url?: string | null;
    editorial_mode?: string;
    website?: string | null;
    email?: string | null;
    logo_url?: string | null;
    links?: AmigosGroupLink[];
  }): Promise<AmigosGroup> {
    return this.post<AmigosGroup>("/admin/amigos/groups", input);
  }

  async updateAmigosGroup(
    groupId: string,
    input: {
      name?: string;
      description?: string | null;
      image_url?: string | null;
      editorial_mode?: string;
      status?: string;
      website?: string | null;
      email?: string | null;
      logo_url?: string | null;
      links?: AmigosGroupLink[];
    },
  ): Promise<AmigosGroup> {
    return this.patch<AmigosGroup>(`/admin/amigos/groups/${encodeURIComponent(groupId)}`, input);
  }

  async getAmigosMembers(groupId: string): Promise<AmigosMemberList> {
    return this.get<AmigosMemberList>(
      `/admin/amigos/groups/${encodeURIComponent(groupId)}/members`,
    );
  }

  async grantAmigosMember(
    groupId: string,
    userId: string,
    role: "admin" | "collaborator" = "collaborator",
  ): Promise<AmigosMember> {
    return this.post<AmigosMember>(`/admin/amigos/groups/${encodeURIComponent(groupId)}/members`, {
      user_id: userId,
      role,
    });
  }

  async revokeAmigosMember(groupId: string, userId: string): Promise<AmigosMember> {
    return this.delete<AmigosMember>(
      `/admin/amigos/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(userId)}`,
    );
  }

  /** Ficha estructurada de un coral (datos propios del tipo de grupo). */
  async getAmigosCoralDetails(groupId: string): Promise<AmigosCoralDetails> {
    return this.get<AmigosCoralDetails>(
      `/amigos/groups/${encodeURIComponent(groupId)}/coral`,
    );
  }

  async updateAmigosCoralDetails(
    groupId: string,
    input: AmigosCoralDetailsInput,
  ): Promise<AmigosCoralDetails> {
    return this.put<AmigosCoralDetails>(
      `/admin/amigos/groups/${encodeURIComponent(groupId)}/coral`,
      input,
    );
  }

  // --- Agenda: actuaciones y eventos ---------------------------------------

  async getAmigosEvents(
    params: { kind?: string; locality?: string; group_id?: string; from_date?: string } = {},
  ): Promise<AmigosEventList> {
    const q = new URLSearchParams();
    if (params.kind) q.set("kind", params.kind);
    if (params.locality) q.set("locality", params.locality);
    if (params.group_id) q.set("group_id", params.group_id);
    if (params.from_date) q.set("from_date", params.from_date);
    const qs = q.toString();
    return this.get<AmigosEventList>(`/amigos/events${qs === "" ? "" : `?${qs}`}`);
  }

  async getAmigosEvent(eventId: string): Promise<AmigosEvent> {
    return this.get<AmigosEvent>(`/amigos/events/${encodeURIComponent(eventId)}`);
  }

  async createAmigosEvent(input: AmigosEventInput): Promise<AmigosEvent> {
    return this.post<AmigosEvent>("/admin/amigos/events", input);
  }

  async updateAmigosEvent(eventId: string, input: Partial<AmigosEventInput>): Promise<AmigosEvent> {
    return this.patch<AmigosEvent>(`/admin/amigos/events/${encodeURIComponent(eventId)}`, input);
  }

  async setAmigosEventStatus(eventId: string, editorialStatus: string): Promise<AmigosEvent> {
    return this.post<AmigosEvent>(
      `/admin/amigos/events/${encodeURIComponent(eventId)}/status`,
      { editorial_status: editorialStatus },
    );
  }

  /** Contador de anuncio (best-effort): 'view' | 'expand' | 'buy'. */
  recordAmigosEvent(eventId: string, kind: "view" | "expand" | "buy"): void {
    void this
      .post<unknown>(`/amigos/events/${encodeURIComponent(eventId)}/stat?kind=${kind}`)
      .catch(() => undefined);
  }

  // --- Blog general «Artículos» --------------------------------------------

  async getAmigosBlog(limit = 100, offset = 0): Promise<AmigosArticleList> {
    return this.get<AmigosArticleList>(`/amigos/blog?limit=${limit}&offset=${offset}`);
  }

  async createAmigosBlogArticle(input: AmigosArticleCreateInput): Promise<AmigosArticle> {
    return this.post<AmigosArticle>("/admin/amigos/blog", input);
  }

  async approveAmigosBlogArticle(articleId: string): Promise<AmigosArticle> {
    return this.post<AmigosArticle>(`/admin/amigos/blog/${encodeURIComponent(articleId)}/approve`);
  }

  // --- Autorizaciones editoriales (blog/events) ----------------------------

  async getAmigosAuthorizations(scope: AmigosAuthorizationScope): Promise<{ items: AmigosAuthorization[]; total: number }> {
    return this.get(`/admin/amigos/authorizations?scope=${scope}`);
  }

  async grantAmigosAuthorization(
    userId: string,
    scope: AmigosAuthorizationScope,
    directPublish = false,
  ): Promise<AmigosAuthorization> {
    return this.post<AmigosAuthorization>("/admin/amigos/authorizations", {
      user_id: userId,
      scope,
      direct_publish: directPublish,
    });
  }

  async revokeAmigosAuthorization(userId: string, scope: AmigosAuthorizationScope): Promise<unknown> {
    return this.delete(
      `/admin/amigos/authorizations/${encodeURIComponent(userId)}?scope=${scope}`,
    );
  }

  async getAmigosGroupArticlesAdmin(
    groupId: string,
    limit = 200,
    offset = 0,
  ): Promise<AmigosArticleList> {
    return this.get<AmigosArticleList>(
      `/admin/amigos/groups/${encodeURIComponent(groupId)}/articles?limit=${limit}&offset=${offset}`,
    );
  }

  async getAmigosPending(groupId?: string): Promise<AmigosArticleList> {
    const qs = groupId ? `?group_id=${encodeURIComponent(groupId)}` : "";
    return this.get<AmigosArticleList>(`/admin/amigos/pending${qs}`);
  }

  async approveAmigosArticle(articleId: string): Promise<AmigosArticle> {
    return this.post<AmigosArticle>(
      `/admin/amigos/articles/${encodeURIComponent(articleId)}/approve`,
    );
  }

  async returnAmigosArticle(articleId: string, note = ""): Promise<AmigosArticle> {
    return this.post<AmigosArticle>(
      `/admin/amigos/articles/${encodeURIComponent(articleId)}/return?note=${encodeURIComponent(note)}`,
    );
  }

  /** Épocas históricas (catálogo público; backend osap-storage). */
  async getEpochs(): Promise<Epoch[]> {
    return this.get<Epoch[]>("/epochs");
  }

  /** Géneros musicales (clasificación pública). */
  async getGenres(): Promise<Genre[]> {
    return this.get<Genre[]>("/genres");
  }

  /** Catálogos temáticos (Köchel, BWV…). Distinto de `/catalog` (Fuentes). */
  async getCatalogues(): Promise<Catalogue[]> {
    return this.get<Catalogue[]>("/catalogues");
  }

  /** Instrumentos y voces (la categoría se usa solo para agrupar en la UI). */
  async getInstruments(): Promise<Instrument[]> {
    return this.get<Instrument[]>("/instruments");
  }

  /** Categorías de instrumentos: uso interno de la UI para agrupar; no es una sección pública. */
  async getInstrumentCategories(): Promise<InstrumentCategory[]> {
    return this.get<InstrumentCategory[]>("/instrument-categories");
  }

  /** Ensembles y formaciones. */
  async getEnsembles(): Promise<Ensemble[]> {
    return this.get<Ensemble[]>("/ensembles");
  }

  async getComposerWorks(personId: string, limit: number, offset: number): Promise<ComposerWorks> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    return this.get<ComposerWorks>(`/composers/${encodeURIComponent(personId)}/works?${params.toString()}`);
  }

  async createResolutionSession(req: ResolutionSessionCreateRequest): Promise<ResolutionSession> {
    return this.post<ResolutionSession>("/works/resolve", req);
  }

  async getResolutionSession(sessionId: string): Promise<ResolutionSession> {
    return this.get<ResolutionSession>(`/sessions/${encodeURIComponent(sessionId)}`);
  }

  async selectBestRepresentation(workId: string, representations: RepresentationInput[]): Promise<RepresentationSelection> {
    return this.post<RepresentationSelection>(
      `/works/${encodeURIComponent(workId)}/representations/select-best`,
      { representations },
    );
  }

  async getWorkRepresentationSelection(workId: string): Promise<RepresentationSelection> {
    return this.get<RepresentationSelection>(
      `/works/${encodeURIComponent(workId)}/representations/selection`,
    );
  }

  async mergeComposers(targetId: string, sources: string[]): Promise<MergeComposersResult> {
    return this.post<MergeComposersResult>("/admin/composers/merge", { target_id: targetId, sources });
  }

  async createComposer(name: string): Promise<ComposerSummary> {
    return this.post<ComposerSummary>("/admin/composers", { name });
  }

  async reviewComposer(personId: string, reviewStatus: string): Promise<ComposerDetail> {
    return this.post<ComposerDetail>(`/admin/composers/${encodeURIComponent(personId)}/review`, {
      review_status: reviewStatus,
    });
  }

  async addAlias(personId: string, alias: string): Promise<Alias> {
    return this.post<Alias>(`/admin/composers/${encodeURIComponent(personId)}/aliases`, { alias });
  }

  async listAliases(personId: string): Promise<Alias[]> {
    return this.get<Alias[]>(`/admin/composers/${encodeURIComponent(personId)}/aliases`);
  }

  async moveAlias(personId: string, aliasId: number, targetComposerId: string): Promise<MoveAliasResult> {
    return this.post<MoveAliasResult>(
      `/admin/composers/${encodeURIComponent(personId)}/aliases/${aliasId}/move`,
      { from_person_id: personId, target_person_id: targetComposerId },
    );
  }

  async promoteAlias(personId: string, aliasId: number): Promise<PromoteAliasResult> {
    return this.post<PromoteAliasResult>(
      `/admin/composers/${encodeURIComponent(personId)}/aliases/${aliasId}/promote`,
      {},
    );
  }

  async setAttribution(personIds: string[], attributionType: string): Promise<SetAttributionResult> {
    return this.post<SetAttributionResult>("/admin/composers/set-attribution", {
      person_ids: personIds,
      attribution_type: attributionType,
    });
  }

  async previewSource(url: string): Promise<SourcePreview> {
    return this.post<SourcePreview>("/sources/preview", { url });
  }

  async suggestSource(payload: {
    name: string;
    type: string;
    location: string;
    mapping: Record<string, unknown>;
  }): Promise<SourceSuggestion> {
    return this.post<SourceSuggestion>("/sources/suggest", payload);
  }

  async submitContact(message: string, contactEmail?: string): Promise<CorrectionRequestRead> {
    return this.post<CorrectionRequestRead>("/contact", {
      kind: "contact",
      message,
      contact_email: contactEmail || null,
    });
  }

  async submitCorrection(payload: {
    kind: "source" | "composer" | "work" | "representation";
    entity_id: string;
    entity_provider?: string;
    field?: string;
    current_value?: string;
    proposed_value?: string;
    message: string;
  }): Promise<CorrectionRequestRead> {
    return this.post<CorrectionRequestRead>("/corrections", payload);
  }

  async listCorrections(): Promise<CorrectionRequestRead[]> {
    return this.get<CorrectionRequestRead[]>("/admin/corrections");
  }

  async resolveCorrection(id: string, action: "review" | "close", message: string): Promise<CorrectionRequestRead> {
    return this.post<CorrectionRequestRead>(`/admin/corrections/${encodeURIComponent(id)}/resolve`, {
      action,
      message,
    });
  }

  async listSourceSuggestions(): Promise<SourceSuggestion[]> {
    return this.get<SourceSuggestion[]>("/admin/source-suggestions");
  }

  async resolveSourceSuggestion(suggestionId: string, action: string, message: string): Promise<SourceSuggestion> {
    return this.post<SourceSuggestion>(`/admin/source-suggestions/${encodeURIComponent(suggestionId)}/resolve`, {
      action,
      message,
    });
  }

  async getAdminOverview(): Promise<AdminOverview> {
    return this.get<AdminOverview>("/admin/overview");
  }

  async getStorageWebUrl(section?: string): Promise<{ url: string }> {
    const qs = section ? `?section=${encodeURIComponent(section)}` : "";
    return this.get<{ url: string }>(`/admin/storage-web${qs}`);
  }

  async getSupportWebUrl(section?: string): Promise<{ url: string }> {
    const qs = section ? `?section=${encodeURIComponent(section)}` : "";
    return this.get<{ url: string }>(`/admin/support-web${qs}`);
  }

  // --- cuotas de descarga OMR (admin) ---------------------------------------
  async getQuotaPlans(): Promise<QuotaPlan[]> {
    return this.get<QuotaPlan[]>("/admin/quota/plans");
  }

  async setQuotaPlan(name: string, payload: QuotaPlanUpdate): Promise<{ name: string; downloads_per_day: number }> {
    return this.put(`/admin/quota/plans/${encodeURIComponent(name)}`, payload);
  }

  async getQuotaOverrides(): Promise<QuotaOverride[]> {
    return this.get<QuotaOverride[]>("/admin/quota/overrides");
  }

  async setQuotaOverride(userId: string, payload: QuotaOverrideUpdate): Promise<{ user_id: string }> {
    return this.put(`/admin/quota/overrides/${encodeURIComponent(userId)}`, payload);
  }

  async deleteQuotaOverride(userId: string): Promise<{ user_id: string }> {
    return this.delete(`/admin/quota/overrides/${encodeURIComponent(userId)}`);
  }

  async getQuotaUsage(from: string, to: string): Promise<QuotaUsage> {
    return this.get<QuotaUsage>(
      `/admin/quota/usage?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    );
  }

  async listOpProviders(): Promise<OpProvider[]> {
    return this.get<OpProvider[]>("/admin/op/providers");
  }

  async upsertOpProvider(payload: {
    provider_id: string;
    name: string;
    base_url?: string | null;
    wired?: boolean;
    config?: Record<string, unknown>;
    description?: Record<string, string> | string | null;
    endpoints?: Record<string, unknown>;
    mapping?: Record<string, unknown>;
    resources?: Record<string, unknown>;
    transforms?: Record<string, unknown>;
  }): Promise<OpProvider> {
    return this.post<OpProvider>("/admin/op/providers", payload);
  }

  async deleteOpProvider(providerId: string): Promise<{ deleted: boolean; provider_id: string }> {
    return this.delete<{ deleted: boolean; provider_id: string }>(
      `/admin/op/providers/${encodeURIComponent(providerId)}`,
    );
  }

  async setOpProviderWired(providerId: string, wired: boolean): Promise<OpProvider> {
    return this.post<OpProvider>(`/admin/op/providers/${encodeURIComponent(providerId)}/wire`, { wired });
  }

  async devSession(): Promise<{ access_token: string; refresh_token: string }> {
    return this.post<{ access_token: string; refresh_token: string }>("/auth/dev-session", {});
  }

  async getWorkStatistics(workId: string): Promise<WorkStatistics> {
    return this.get<WorkStatistics>(`/works/${encodeURIComponent(workId)}/statistics`);
  }

  async getComposerStatistics(personId: string): Promise<ComposerStatistics> {
    return this.get<ComposerStatistics>(`/composers/${encodeURIComponent(personId)}/statistics`);
  }

  async getVotesOverview(): Promise<VotesOverview> {
    return this.get<VotesOverview>("/admin/votes");
  }

  /** Estadísticas del propio usuario (la identidad va en el token, no en parámetros). */
  async getAnalyticsMe(from?: string, to?: string): Promise<AnalyticsMe> {
    const params = new URLSearchParams();
    if (from) params.set("from_day", from);
    if (to) params.set("to_day", to);
    const qs = params.toString();
    return this.get<AnalyticsMe>(`/analytics/me${qs ? `?${qs}` : ""}`);
  }

  /** Mi Actividad: panel personal (aportaciones, descargas, impacto). */
  async getActivityMe(from?: string, to?: string): Promise<ActivityMe> {
    const params = new URLSearchParams();
    if (from) params.set("from_day", from);
    if (to) params.set("to_day", to);
    const qs = params.toString();
    return this.get<ActivityMe>(`/activity/me${qs ? `?${qs}` : ""}`);
  }

  /** Métricas del funnel S0–S4 (solo admin). */
  async getFunnelMetrics(from?: string, to?: string): Promise<FunnelMetrics> {
    const params = new URLSearchParams();
    if (from) params.set("from_day", from);
    if (to) params.set("to_day", to);
    const qs = params.toString();
    return this.get<FunnelMetrics>(`/admin/analytics/funnel${qs ? `?${qs}` : ""}`);
  }

  // --- atribución asistida por IA (solo admin) -------------------------------
  //
  // La SPA no habla con Gemini: solo consume las propuestas de osap-api (que delega en
  // osap-storage). Aceptar es lo único que asigna la persona.

  async listWorkAttributionProposals(
    status: WorkAiProposalStatus,
    limit: number,
    offset: number,
  ): Promise<WorkAiProposalPage> {
    const params = new URLSearchParams({ status, limit: String(limit), offset: String(offset) });
    return this.get<WorkAiProposalPage>(`/admin/work-person-ai?${params.toString()}`);
  }

  async getWorkAttributionProposal(proposalId: number): Promise<WorkAiProposal> {
    return this.get<WorkAiProposal>(`/admin/work-person-ai/${proposalId}`);
  }

  async proposeWorkAttribution(
    workId: number,
    options?: { batchId?: string; force?: boolean },
  ): Promise<WorkAiProposalResult> {
    const params = new URLSearchParams();
    if (options?.batchId) params.set("batch_id", options.batchId);
    if (options?.force) params.set("force", "true");
    const qs = params.toString();
    return this.post<WorkAiProposalResult>(`/admin/work-person-ai/propose/${workId}${qs ? `?${qs}` : ""}`);
  }

  async reviewWorkAttributionProposal(
    proposalId: number,
    action: WorkAiReviewAction,
    note?: string,
  ): Promise<{ id: number; status: WorkAiProposalStatus }> {
    // `reviewed_by` no se envía: el servidor lo deriva del usuario autenticado.
    return this.post<{ id: number; status: WorkAiProposalStatus }>(
      `/admin/work-person-ai/${proposalId}/review`,
      { action, note },
    );
  }

  async register(email: string, password: string, name?: string): Promise<RegisterResult> {    return this.post<RegisterResult>("/auth/register", { email, password, name });
  }

  async verifyEmail(token: string): Promise<VerifyEmailResult> {
    return this.post<VerifyEmailResult>("/auth/verify-email", { token });
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const fetchImpl = this.fetcher ?? globalThis.fetch;
    let retried = false;
    // eslint-disable-next-line no-constant-condition
    for (;;) {
      const headers: Record<string, string> = {};
      if (body !== undefined) {
        headers["Content-Type"] = "application/json";
      }
      const token = this.auth.getToken() ?? this.token;
      if (token !== null) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      let response: Response;
      try {
        // `fetch` must be invoked with `this` bound to globalThis/window, otherwise it
        // throws "Illegal invocation". Pages never touch this detail.
        response = await fetchImpl.call(globalThis, `${this.baseUrl}${path}`, {
          method,
          headers,
          body: body !== undefined ? JSON.stringify(body) : undefined,
        });
      } catch (cause) {
        throw new ApiError("NETWORK", "Network error", { cause: String(cause) });
      }

      // 401 → refresh (una vez) → retry único. Si vuelve a 401 → logout.
      if (response.status === 401 && !retried) {
        retried = true;
        const refreshed = await this.auth.refresh();
        if (refreshed) {
          continue;
        }
        throw new ApiError("UNAUTHORIZED", "Session expired");
      }
      if (response.status === 401 && retried) {
        this.auth.logout();
      }

      let parsed: Envelope<T> | null = null;
      try {
        parsed = (await response.json()) as Envelope<T>;
      } catch {
        parsed = null;
      }

      if (parsed === null || typeof parsed !== "object") {
        throw new ApiError("INVALID_RESPONSE", `Invalid response (HTTP ${response.status})`);
      }

      if (parsed.success === true) {
        return parsed.data;
      }

      if ("error" in parsed && parsed.error !== undefined && parsed.error !== null) {
        throw new ApiError(parsed.error.code, parsed.error.message, parsed.error.details);
      }

      throw new ApiError("INVALID_RESPONSE", `Unexpected response (HTTP ${response.status})`);
    }
  }
}

export const apiClient = new ApiClient();

// --- cuotas de descarga OMR (admin) -----------------------------------------

export interface QuotaPlan {
  name: string;
  downloads_per_day: number;
  valid_from?: string | null;
  valid_until?: string | null;
}

export interface QuotaPlanUpdate {
  downloads_per_day: number;
  valid_from?: string | null;
  valid_until?: string | null;
}

export interface QuotaOverride {
  user_id: string;
  downloads_per_day: number;
  valid_from?: string | null;
  valid_until?: string | null;
  note?: string | null;
}

export interface QuotaOverrideUpdate {
  downloads_per_day: number;
  valid_from?: string | null;
  valid_until?: string | null;
  note?: string | null;
}

export interface QuotaUsage {
  from: string;
  to: string;
  total: number;
  registered: number;
  anonymous: number;
  distinct_users: number;
  distinct_ips: number;
  by_day: { day: string; total: number }[];
  by_provider: { provider: string; total: number }[];
  top_works: { work_id: string; total: number }[];
}
