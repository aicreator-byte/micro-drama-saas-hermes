import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { AuthTokens, User, Project, SeriesBible, Character, Location, Episode, Scene, SceneCharacter, Dialogue, Prompt, PromptType, GoogleAccount, FlowTask, AssetType, Asset, PaginatedResponse, StoryGenerationRequest, StoryGenerationResponse, SceneBreakdownRequest, SceneBreakdownResponse, PromptGenerationRequest, PromptGenerationResponse, ProviderConfig, AppSettingsResponse, AppSettingsUpdate, GoogleAuthURLResponse, GoogleOAuthCallbackResponse, AutoGenerateCreate, AutoGenerateJob, BillingPlan, Subscription, VideoTimeline, TimelineClip, ConsistencyCheck, SubtitleJob, SubtitleSegment, CollabPresence } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private refreshPromise: Promise<string> | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: false,
    });

    // Load token from localStorage on initialization
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('auth_tokens');
      if (stored) {
        try {
          const tokens: AuthTokens = JSON.parse(stored);
          this.accessToken = tokens.access_token;
        } catch {
          localStorage.removeItem('auth_tokens');
        }
      }
    }

    // Request interceptor to add auth header
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        if (this.accessToken) {
          config.headers.Authorization = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          // Try to refresh token (in this case, we just logout)
          this.logout();
          if (typeof window !== 'undefined') {
            window.location.href = '/auth/login';
          }
        }

        return Promise.reject(error);
      }
    );
  }

  setToken(token: string | null) {
    this.accessToken = token;
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('auth_tokens', JSON.stringify({ access_token: token, token_type: 'bearer' }));
      } else {
        localStorage.removeItem('auth_tokens');
      }
    }
  }

  getToken(): string | null {
    return this.accessToken;
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  logout() {
    this.accessToken = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_tokens');
      localStorage.removeItem('user');
    }
  }

  // Auth endpoints
  async register(email: string, password: string, full_name?: string): Promise<User> {
    const response = await this.client.post<User>('/auth/register', { email, password, full_name });
    return response.data;
  }

  async login(email: string, password: string): Promise<AuthTokens> {
    const response = await this.client.post<AuthTokens>('/auth/login', { email, password });
    this.setToken(response.data.access_token);
    return response.data;
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<User>('/auth/me');
    return response.data;
  }

  // Project endpoints
  async createProject(data: Partial<Project>): Promise<Project> {
    const response = await this.client.post<Project>('/projects', data);
    return response.data;
  }

  async listProjects(page = 1, page_size = 20, status?: string): Promise<PaginatedResponse<Project>> {
    const params = new URLSearchParams({ page: page.toString(), page_size: page_size.toString() });
    if (status) params.append('status', status);
    const response = await this.client.get<PaginatedResponse<Project>>(`/projects?${params}`);
    return response.data;
  }

  async getProject(id: string): Promise<Project> {
    const response = await this.client.get<Project>(`/projects/${id}`);
    return response.data;
  }

  async updateProject(id: string, data: Partial<Project>): Promise<Project> {
    const response = await this.client.patch<Project>(`/projects/${id}`, data);
    return response.data;
  }

  async deleteProject(id: string): Promise<void> {
    await this.client.delete(`/projects/${id}`);
  }

  // Series Bible endpoints
  async createSeriesBible(projectId: string, data: Partial<SeriesBible>): Promise<SeriesBible> {
    const response = await this.client.post<SeriesBible>(`/series-bible/${projectId}`, data);
    return response.data;
  }

  async getSeriesBible(projectId: string): Promise<SeriesBible> {
    const response = await this.client.get<SeriesBible>(`/series-bible/${projectId}`);
    return response.data;
  }

  async updateSeriesBible(projectId: string, data: Partial<SeriesBible>): Promise<SeriesBible> {
    const response = await this.client.patch<SeriesBible>(`/series-bible/${projectId}`, data);
    return response.data;
  }

  async deleteSeriesBible(projectId: string): Promise<void> {
    await this.client.delete(`/series-bible/${projectId}`);
  }

  // Character endpoints
  async createCharacter(projectId: string, data: Partial<Character>): Promise<Character> {
    const response = await this.client.post<Character>(`/characters/${projectId}`, data);
    return response.data;
  }

  async listCharacters(projectId: string, page = 1, page_size = 20): Promise<PaginatedResponse<Character>> {
    const response = await this.client.get(`/characters/${projectId}?page=${page}&page_size=${page_size}`);
    return response.data;
  }

  async getCharacter(projectId: string, characterId: string): Promise<Character> {
    const response = await this.client.get<Character>(`/characters/${projectId}/${characterId}`);
    return response.data;
  }

  async updateCharacter(projectId: string, characterId: string, data: Partial<Character>): Promise<Character> {
    const response = await this.client.patch<Character>(`/characters/${projectId}/${characterId}`, data);
    return response.data;
  }

  async deleteCharacter(projectId: string, characterId: string): Promise<void> {
    await this.client.delete(`/characters/${projectId}/${characterId}`);
  }

  async reorderCharacters(projectId: string, characterIds: string[]): Promise<Character[]> {
    const response = await this.client.post<Character[]>(`/characters/${projectId}/reorder`, characterIds);
    return response.data;
  }

  // Location endpoints
  async createLocation(projectId: string, data: Partial<Location>): Promise<Location> {
    const response = await this.client.post<Location>(`/locations/${projectId}`, data);
    return response.data;
  }

  async listLocations(projectId: string, page = 1, page_size = 20): Promise<PaginatedResponse<Location>> {
    const response = await this.client.get(`/locations/${projectId}?page=${page}&page_size=${page_size}`);
    return response.data;
  }

  async getLocation(projectId: string, locationId: string): Promise<Location> {
    const response = await this.client.get<Location>(`/locations/${projectId}/${locationId}`);
    return response.data;
  }

  async updateLocation(projectId: string, locationId: string, data: Partial<Location>): Promise<Location> {
    const response = await this.client.patch<Location>(`/locations/${projectId}/${locationId}`, data);
    return response.data;
  }

  async deleteLocation(projectId: string, locationId: string): Promise<void> {
    await this.client.delete(`/locations/${projectId}/${locationId}`);
  }

  async reorderLocations(projectId: string, locationIds: string[]): Promise<Location[]> {
    const response = await this.client.post<Location[]>(`/locations/${projectId}/reorder`, locationIds);
    return response.data;
  }

  // Episode endpoints
  async createEpisode(projectId: string, data: Partial<Episode>): Promise<Episode> {
    const response = await this.client.post<Episode>(`/episodes/${projectId}`, data);
    return response.data;
  }

  async listEpisodes(projectId: string, page = 1, page_size = 20, status?: string): Promise<PaginatedResponse<Episode>> {
    const params = new URLSearchParams({ page: page.toString(), page_size: page_size.toString() });
    if (status) params.append('status', status);
    const response = await this.client.get(`/episodes/${projectId}?${params}`);
    return response.data;
  }

  async getEpisode(projectId: string, episodeId: string): Promise<Episode> {
    const response = await this.client.get<Episode>(`/episodes/${projectId}/${episodeId}`);
    return response.data;
  }

  async updateEpisode(projectId: string, episodeId: string, data: Partial<Episode>): Promise<Episode> {
    const response = await this.client.patch<Episode>(`/episodes/${projectId}/${episodeId}`, data);
    return response.data;
  }

  async deleteEpisode(projectId: string, episodeId: string): Promise<void> {
    await this.client.delete(`/episodes/${projectId}/${episodeId}`);
  }

  // Scene endpoints
  async createScene(projectId: string, episodeId: string, data: Partial<Scene> & { location_id?: string }): Promise<Scene> {
    const response = await this.client.post<Scene>(`/scenes/${projectId}/episodes/${episodeId}`, data);
    return response.data;
  }

  async listScenes(projectId: string, episodeId: string, page = 1, page_size = 20, status?: string): Promise<PaginatedResponse<Scene>> {
    const params = new URLSearchParams({ page: page.toString(), page_size: page_size.toString() });
    if (status) params.append('status', status);
    const response = await this.client.get(`/scenes/${projectId}/episodes/${episodeId}?${params}`);
    return response.data;
  }

  async getScene(projectId: string, episodeId: string, sceneId: string): Promise<Scene> {
    const response = await this.client.get<Scene>(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}`);
    return response.data;
  }

  async updateScene(projectId: string, episodeId: string, sceneId: string, data: Partial<Scene>): Promise<Scene> {
    const response = await this.client.patch<Scene>(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}`, data);
    return response.data;
  }

  async deleteScene(projectId: string, episodeId: string, sceneId: string): Promise<void> {
    await this.client.delete(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}`);
  }

  // Scene Characters
  async addCharacterToScene(projectId: string, episodeId: string, sceneId: string, characterId: string, data: Partial<SceneCharacter>): Promise<SceneCharacter> {
    const response = await this.client.post<SceneCharacter>(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}/characters`, { character_id: characterId, ...data });
    return response.data;
  }

  async listSceneCharacters(projectId: string, episodeId: string, sceneId: string): Promise<SceneCharacter[]> {
    const response = await this.client.get<SceneCharacter[]>(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}/characters`);
    return response.data;
  }

  async removeCharacterFromScene(projectId: string, episodeId: string, sceneId: string, characterId: string): Promise<void> {
    await this.client.delete(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}/characters/${characterId}`);
  }

  // Dialogues
  async createDialogue(projectId: string, episodeId: string, sceneId: string, data: Partial<Dialogue>): Promise<Dialogue> {
    const response = await this.client.post<Dialogue>(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}/dialogues`, data);
    return response.data;
  }

  async listDialogues(projectId: string, episodeId: string, sceneId: string): Promise<Dialogue[]> {
    const response = await this.client.get<Dialogue[]>(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}/dialogues`);
    return response.data;
  }

  async updateDialogue(projectId: string, episodeId: string, sceneId: string, dialogueId: string, data: Partial<Dialogue>): Promise<Dialogue> {
    const response = await this.client.patch<Dialogue>(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}/dialogues/${dialogueId}`, data);
    return response.data;
  }

  async deleteDialogue(projectId: string, episodeId: string, sceneId: string, dialogueId: string): Promise<void> {
    await this.client.delete(`/scenes/${projectId}/episodes/${episodeId}/${sceneId}/dialogues/${dialogueId}`);
  }

  // Prompt endpoints
  async createPrompt(projectId: string, data: Partial<Prompt>): Promise<Prompt> {
    const response = await this.client.post<Prompt>(`/prompts/${projectId}`, data);
    return response.data;
  }

  async listPrompts(projectId: string, params?: {
    page?: number;
    page_size?: number;
    prompt_type?: string;
    scene_id?: string;
    character_id?: string;
    location_id?: string;
    episode_id?: string;
  }): Promise<PaginatedResponse<Prompt>> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.append('page', params.page.toString());
    if (params?.page_size) searchParams.append('page_size', params.page_size.toString());
    if (params?.prompt_type) searchParams.append('prompt_type', params.prompt_type);
    if (params?.scene_id) searchParams.append('scene_id', params.scene_id);
    if (params?.character_id) searchParams.append('character_id', params.character_id);
    if (params?.location_id) searchParams.append('location_id', params.location_id);
    if (params?.episode_id) searchParams.append('episode_id', params.episode_id);
    const response = await this.client.get(`/prompts/${projectId}?${searchParams}`);
    return response.data;
  }

  async getPrompt(projectId: string, promptId: string): Promise<Prompt> {
    const response = await this.client.get<Prompt>(`/prompts/${projectId}/${promptId}`);
    return response.data;
  }

  async updatePrompt(projectId: string, promptId: string, data: Partial<Prompt>): Promise<Prompt> {
    const response = await this.client.patch<Prompt>(`/prompts/${projectId}/${promptId}`, data);
    return response.data;
  }

  async deletePrompt(projectId: string, promptId: string): Promise<void> {
    await this.client.delete(`/prompts/${projectId}/${promptId}`);
  }

  async generatePrompt(data: PromptGenerationRequest): Promise<PromptGenerationResponse> {
    const response = await this.client.post<PromptGenerationResponse>('/prompts/generate', data);
    return response.data;
  }

  async generateAllScenePrompts(projectId: string, episodeId: string, sceneId: string): Promise<Prompt[]> {
    const response = await this.client.post<Prompt[]>(`/prompts/${projectId}/episodes/${episodeId}/scenes/${sceneId}/generate-all`);
    return response.data;
  }

  // Google Account endpoints
  async createGoogleAccount(data: { email: string; display_name?: string }): Promise<GoogleAccount> {
    const response = await this.client.post<GoogleAccount>('/google-accounts', data);
    return response.data;
  }

  async listGoogleAccounts(): Promise<GoogleAccount[]> {
    const response = await this.client.get<GoogleAccount[]>('/google-accounts');
    return response.data;
  }

  async getGoogleAccount(accountId: string): Promise<GoogleAccount> {
    const response = await this.client.get<GoogleAccount>(`/google-accounts/${accountId}`);
    return response.data;
  }

  async updateGoogleAccount(accountId: string, data: Partial<GoogleAccount>): Promise<GoogleAccount> {
    const response = await this.client.patch<GoogleAccount>(`/google-accounts/${accountId}`, data);
    return response.data;
  }

  async deleteGoogleAccount(accountId: string): Promise<void> {
    await this.client.delete(`/google-accounts/${accountId}`);
  }

  async syncGoogleAccount(accountId: string): Promise<GoogleAccount> {
    const response = await this.client.post<GoogleAccount>(`/google-accounts/${accountId}/sync`);
    return response.data;
  }

  // Flow Bridge endpoints
  async createFlowTask(projectId: string, data: Partial<FlowTask>): Promise<FlowTask> {
    const response = await this.client.post<FlowTask>(`/flow/${projectId}/tasks`, data);
    return response.data;
  }

  async listFlowTasks(projectId: string, params?: {
    page?: number;
    page_size?: number;
    status?: string;
    task_type?: string;
    episode_id?: string;
    scene_id?: string;
  }): Promise<PaginatedResponse<FlowTask>> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.append('page', params.page.toString());
    if (params?.page_size) searchParams.append('page_size', params.page_size.toString());
    if (params?.status) searchParams.append('status', params.status);
    if (params?.task_type) searchParams.append('task_type', params.task_type);
    if (params?.episode_id) searchParams.append('episode_id', params.episode_id);
    if (params?.scene_id) searchParams.append('scene_id', params.scene_id);
    const response = await this.client.get(`/flow/${projectId}/tasks?${searchParams}`);
    return response.data;
  }

  async getFlowTask(projectId: string, taskId: string): Promise<FlowTask> {
    const response = await this.client.get<FlowTask>(`/flow/${projectId}/tasks/${taskId}`);
    return response.data;
  }

  async updateFlowTask(projectId: string, taskId: string, data: Partial<FlowTask>): Promise<FlowTask> {
    const response = await this.client.patch<FlowTask>(`/flow/${projectId}/tasks/${taskId}`, data);
    return response.data;
  }

  async deleteFlowTask(projectId: string, taskId: string): Promise<void> {
    await this.client.delete(`/flow/${projectId}/tasks/${taskId}`);
  }

  async exportPromptsForFlow(projectId: string, episodeId?: string, sceneIds?: string[]): Promise<unknown> {
    const params = new URLSearchParams();
    if (episodeId) params.append('episode_id', episodeId);
    if (sceneIds?.length) params.append('scene_ids', sceneIds.join(','));
    const response = await this.client.post(`/flow/${projectId}/export-prompts`, null, { params });
    return response.data;
  }

  async importFlowResults(projectId: string, taskId: string, outputFiles: string[]): Promise<unknown> {
    const response = await this.client.post(`/flow/${projectId}/import-results`, { output_files: outputFiles, task_id: taskId });
    return response.data;
  }

  // Asset endpoints
  async uploadAsset(projectId: string, file: File, assetType: AssetType, episodeId?: string, sceneId?: string, metadata?: Record<string, unknown>): Promise<Asset> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('asset_type', assetType);
    if (episodeId) formData.append('episode_id', episodeId);
    if (sceneId) formData.append('scene_id', sceneId);
    if (metadata) formData.append('metadata', JSON.stringify(metadata));

    const response = await this.client.post<Asset>(`/assets/${projectId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  async listAssets(projectId: string, params?: {
    page?: number;
    page_size?: number;
    asset_type?: string;
    episode_id?: string;
    scene_id?: string;
  }): Promise<PaginatedResponse<Asset>> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.append('page', params.page.toString());
    if (params?.page_size) searchParams.append('page_size', params.page_size.toString());
    if (params?.asset_type) searchParams.append('asset_type', params.asset_type);
    if (params?.episode_id) searchParams.append('episode_id', params.episode_id);
    if (params?.scene_id) searchParams.append('scene_id', params.scene_id);
    const response = await this.client.get(`/assets/${projectId}?${searchParams}`);
    return response.data;
  }

  async getAsset(projectId: string, assetId: string): Promise<Asset> {
    const response = await this.client.get<Asset>(`/assets/${projectId}/${assetId}`);
    return response.data;
  }

  async deleteAsset(projectId: string, assetId: string): Promise<void> {
    await this.client.delete(`/assets/${projectId}/${assetId}`);
  }

  async assembleEpisodeVideo(projectId: string, episodeId: string, sceneOrder: string[], outputFilename = 'episode_final.mp4', includeAudio = true, includeSubtitles = false): Promise<{ asset_id: string; file_path: string; file_size: number }> {
    const response = await this.client.post(`/assets/${projectId}/episodes/${episodeId}/assemble`, {
      scene_order: sceneOrder,
      output_filename: outputFilename,
      include_audio: includeAudio,
      include_subtitles: includeSubtitles,
    });
    return response.data;
  }

  async addSubtitlesToVideo(projectId: string, episodeId: string, videoAssetId: string, subtitleAssetId: string, outputFilename = 'episode_with_subs.mp4'): Promise<{ asset_id: string; file_path: string }> {
    const response = await this.client.post(`/assets/${projectId}/episodes/${episodeId}/add-subtitles`, {
      video_asset_id: videoAssetId,
      subtitle_asset_id: subtitleAssetId,
      output_filename: outputFilename,
    });
    return response.data;
  }

  // Story Engine endpoints
  async generateSeries(projectId: string, data: StoryGenerationRequest): Promise<StoryGenerationResponse> {
    const response = await this.client.post<StoryGenerationResponse>(`/story-engine/${projectId}/generate-series`, data);
    return response.data;
  }

  async breakdownEpisode(projectId: string, episodeId: string, data: SceneBreakdownRequest): Promise<SceneBreakdownResponse> {
    const response = await this.client.post<SceneBreakdownResponse>(`/story-engine/${projectId}/episodes/${episodeId}/breakdown`, data);
    return response.data;
  }

  async createEpisodesFromOutline(projectId: string, episodesData: Array<Record<string, unknown>>): Promise<{ created_episodes: number[]; count: number }> {
    const response = await this.client.post(`/story-engine/${projectId}/create-episodes`, episodesData);
    return response.data;
  }

  // Auto-Generate endpoints (Fase 1 backend)
  async createAutoGenerateJob(projectId: string, data: AutoGenerateCreate): Promise<AutoGenerateJob> {
    const response = await this.client.post<AutoGenerateJob>(`/projects/${projectId}/auto-generate`, data);
    return response.data;
  }

  async getAutoGenerateJob(projectId: string, jobId: string): Promise<AutoGenerateJob> {
    const response = await this.client.get<AutoGenerateJob>(`/projects/${projectId}/auto-generate/${jobId}`);
    return response.data;
  }

  async retryAutoGenerateStep(projectId: string, jobId: string, stepKey: string): Promise<AutoGenerateJob> {
    const response = await this.client.post<AutoGenerateJob>(`/projects/${projectId}/auto-generate/${jobId}/retry/${stepKey}`);
    return response.data;
  }

  // Settings endpoints
  async getSettings(): Promise<AppSettingsResponse> {
    const response = await this.client.get<AppSettingsResponse>('/settings');
    return response.data;
  }

  async updateSettings(data: AppSettingsUpdate): Promise<AppSettingsResponse> {
    const response = await this.client.patch<AppSettingsResponse>('/settings', data);
    return response.data;
  }

  // Google OAuth endpoints
  async getGoogleAuthUrl(accountId: string): Promise<GoogleAuthURLResponse> {
    const response = await this.client.get<GoogleAuthURLResponse>(`/google-accounts/${accountId}/auth-url`);
    return response.data;
  }

  async googleOAuthCallback(code: string, state: string, accountId: string): Promise<GoogleOAuthCallbackResponse> {
    const response = await this.client.post<GoogleOAuthCallbackResponse>(`/google-accounts/callback`, null, {
      params: { code, state, account_id: accountId }
    });
    return response.data;
  }

  async refreshGoogleToken(accountId: string): Promise<GoogleOAuthCallbackResponse> {
    const response = await this.client.post<GoogleOAuthCallbackResponse>(`/google-accounts/${accountId}/refresh`);
    return response.data;
  }

  async setGoogleAccountPassword(accountId: string, password: string): Promise<{ message: string }> {
    const response = await this.client.post(`/google-accounts/${accountId}/password`, { password });
    return response.data;
  }

  async checkGoogleAccountPassword(accountId: string): Promise<{ has_password: boolean }> {
    const response = await this.client.get(`/google-accounts/${accountId}/password/check`);
    return response.data;
  }

  async verifyGoogleAccountPassword(accountId: string, password: string): Promise<{ valid: boolean; message?: string }> {
    const response = await this.client.post(`/google-accounts/${accountId}/password/verify`, { password });
    return response.data;
  }

  // Billing endpoints (round 2 — TEST MODE, tanpa pembayaran nyata)
  async listBillingPlans(): Promise<BillingPlan[]> {
    const response = await this.client.get<BillingPlan[]>('/billing/plans');
    return response.data;
  }

  async getSubscription(): Promise<Subscription> {
    const response = await this.client.get<Subscription>('/billing/subscription');
    return response.data;
  }

  async createCheckout(plan: string): Promise<{ session_id: string; checkout_url: string; plan: BillingPlan; mode: string; note: string }> {
    const response = await this.client.post('/billing/checkout', { plan });
    return response.data;
  }

  async cancelSubscription(): Promise<Subscription> {
    const response = await this.client.post<Subscription>('/billing/cancel');
    return response.data;
  }

  // Timeline endpoints (round 2)
  async getTimeline(projectId: string, episodeId: string): Promise<VideoTimeline> {
    const response = await this.client.get<VideoTimeline>(`/projects/${projectId}/episodes/${episodeId}/timeline`);
    return response.data;
  }

  async createTimeline(projectId: string, episodeId: string, data: { name?: string; clips?: TimelineClip[]; fps?: number; resolution?: string }): Promise<VideoTimeline> {
    const response = await this.client.post<VideoTimeline>(`/projects/${projectId}/episodes/${episodeId}/timeline`, data);
    return response.data;
  }

  async updateTimeline(projectId: string, episodeId: string, data: { name?: string; clips?: TimelineClip[]; fps?: number; resolution?: string }): Promise<VideoTimeline> {
    const response = await this.client.patch<VideoTimeline>(`/projects/${projectId}/episodes/${episodeId}/timeline`, data);
    return response.data;
  }

  async deleteTimeline(projectId: string, episodeId: string): Promise<void> {
    await this.client.delete(`/projects/${projectId}/episodes/${episodeId}/timeline`);
  }

  async timelineFromPrompts(projectId: string, episodeId: string): Promise<VideoTimeline> {
    const response = await this.client.post<VideoTimeline>(`/projects/${projectId}/episodes/${episodeId}/timeline/from-prompts`);
    return response.data;
  }

  // Consistency check endpoints (round 2)
  async runConsistencyCheck(projectId: string): Promise<ConsistencyCheck> {
    const response = await this.client.post<ConsistencyCheck>(`/projects/${projectId}/consistency-check`);
    return response.data;
  }

  async listConsistencyChecks(projectId: string): Promise<ConsistencyCheck[]> {
    const response = await this.client.get<ConsistencyCheck[]>(`/projects/${projectId}/consistency-checks`);
    return response.data;
  }

  // Subtitle endpoints (round 2)
  async getSubtitleEngine(): Promise<{ engine: string | null; available: boolean; note: string | null }> {
    const response = await this.client.get('/projects/subtitles/engine');
    return response.data;
  }

  async listSubtitleJobs(projectId: string): Promise<SubtitleJob[]> {
    const response = await this.client.get<SubtitleJob[]>(`/projects/${projectId}/subtitles`);
    return response.data;
  }

  async createSubtitleFromSegments(projectId: string, data: { episode_id?: string; language?: string; segments: SubtitleSegment[] }): Promise<SubtitleJob> {
    const response = await this.client.post<SubtitleJob>(`/projects/${projectId}/subtitles/from-segments`, data);
    return response.data;
  }

  async uploadSubtitleAudio(projectId: string, file: File, episodeId?: string, language = 'id'): Promise<SubtitleJob> {
    const form = new FormData();
    form.append('file', file);
    const params: Record<string, string> = { language };
    if (episodeId) params.episode_id = episodeId;
    const response = await this.client.post<SubtitleJob>(`/projects/${projectId}/subtitles`, form, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  // Collaboration endpoints (round 2)
  async getCollabPresence(projectId: string): Promise<CollabPresence[]> {
    const response = await this.client.get<CollabPresence[]>(`/projects/${projectId}/collab/presence`);
    return response.data;
  }

  async postCollabEdit(projectId: string, op: { resource: string; resource_id: string; field: string; value: string }): Promise<{ ok: boolean; version: number }> {
    const response = await this.client.post(`/projects/${projectId}/collab/edit`, op);
    return response.data;
  }
}

export const api = new ApiClient();
export default api;