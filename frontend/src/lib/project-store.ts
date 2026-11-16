import { create } from 'zustand';
import type { Project, Character, Location as LocationType, Episode, Scene, Prompt, PromptType, GoogleAccount, FlowTask, Asset, SeriesBible, SceneCharacter, Dialogue } from '@/types';
import { api } from '@/lib/api';

interface ProjectState {
  currentProject: Project | null;
  seriesBible: SeriesBible | null;
  characters: Character[];
  locations: LocationType[];
  episodes: Episode[];
  scenes: Record<string, Scene[]>;
  sceneCharacters: Record<string, SceneCharacter[]>;
  dialogues: Record<string, Dialogue[]>;
  prompts: Prompt[];
  googleAccounts: GoogleAccount[];
  flowTasks: FlowTask[];
  assets: Asset[];
  projects: Project[];
  isLoading: boolean;
  error: string | null;
  selectedScene: string | null;
  setSelectedScene: (sceneId: string | null) => void;

  // Project actions
  setCurrentProject: (project: Project | null) => void;
  fetchProject: (projectId: string) => Promise<void>;
  fetchProjects: () => Promise<void>;
  createProject: (data: Partial<Project>) => Promise<Project>;
  updateProject: (projectId: string, data: Partial<Project>) => Promise<Project>;
  deleteProject: (projectId: string) => Promise<void>;

  // Series Bible actions
  fetchSeriesBible: (projectId: string) => Promise<void>;
  createSeriesBible: (projectId: string, data: Partial<SeriesBible>) => Promise<SeriesBible>;
  updateSeriesBible: (projectId: string, data: Partial<SeriesBible>) => Promise<SeriesBible>;

  // Character actions
  fetchCharacters: (projectId: string) => Promise<void>;
  createCharacter: (projectId: string, data: Partial<Character>) => Promise<Character>;
  updateCharacter: (projectId: string, characterId: string, data: Partial<Character>) => Promise<Character>;
  deleteCharacter: (projectId: string, characterId: string) => Promise<void>;
  reorderCharacters: (projectId: string, characterIds: string[]) => Promise<void>;

  // Location actions
  fetchLocations: (projectId: string) => Promise<void>;
  createLocation: (projectId: string, data: Partial<LocationType>) => Promise<LocationType>;
  updateLocation: (projectId: string, locationId: string, data: Partial<LocationType>) => Promise<LocationType>;
  deleteLocation: (projectId: string, locationId: string) => Promise<void>;
  reorderLocations: (projectId: string, locationIds: string[]) => Promise<void>;

  // Episode actions
  fetchEpisodes: (projectId: string) => Promise<void>;
  createEpisode: (projectId: string, data: Partial<Episode>) => Promise<Episode>;
  updateEpisode: (projectId: string, episodeId: string, data: Partial<Episode>) => Promise<Episode>;
  deleteEpisode: (projectId: string, episodeId: string) => Promise<void>;

  // Scene actions
  fetchScenes: (projectId: string, episodeId: string) => Promise<void>;
  createScene: (projectId: string, episodeId: string, data: Partial<Scene> & { location_id?: string }) => Promise<Scene>;
  updateScene: (projectId: string, episodeId: string, sceneId: string, data: Partial<Scene>) => Promise<Scene>;
  deleteScene: (projectId: string, episodeId: string, sceneId: string) => Promise<void>;

  // Scene Character actions
  fetchSceneCharacters: (projectId: string, episodeId: string, sceneId: string) => Promise<void>;
  addCharacterToScene: (projectId: string, episodeId: string, sceneId: string, characterId: string, data: Partial<SceneCharacter>) => Promise<SceneCharacter>;
  removeCharacterFromScene: (projectId: string, episodeId: string, sceneId: string, characterId: string) => Promise<void>;

  // Dialogue actions
  fetchDialogues: (projectId: string, episodeId: string, sceneId: string) => Promise<void>;
  createDialogue: (projectId: string, episodeId: string, sceneId: string, data: Partial<Dialogue>) => Promise<Dialogue>;
  updateDialogue: (projectId: string, episodeId: string, sceneId: string, dialogueId: string, data: Partial<Dialogue>) => Promise<Dialogue>;
  deleteDialogue: (projectId: string, episodeId: string, sceneId: string, dialogueId: string) => Promise<void>;

  // Prompt actions
  fetchPrompts: (projectId: string, params?: { prompt_type?: string; scene_id?: string; character_id?: string; location_id?: string; episode_id?: string }) => Promise<void>;
  createPrompt: (projectId: string, data: Partial<Prompt>) => Promise<Prompt>;
  updatePrompt: (projectId: string, promptId: string, data: Partial<Prompt>) => Promise<Prompt>;
  deletePrompt: (projectId: string, promptId: string) => Promise<void>;
  generatePrompt: (data: { prompt_type: PromptType; context: Record<string, unknown>; style_preferences?: Record<string, unknown> }) => Promise<{ prompt_text: string; negative_prompt: string | null; parameters: Record<string, unknown> | null }>;
  generateAllScenePrompts: (projectId: string, episodeId: string, sceneId: string) => Promise<Prompt[]>;

  // Google Account actions
  fetchGoogleAccounts: () => Promise<void>;
  createGoogleAccount: (data: { email: string; display_name?: string }) => Promise<GoogleAccount>;
  updateGoogleAccount: (accountId: string, data: Partial<GoogleAccount>) => Promise<GoogleAccount>;
  deleteGoogleAccount: (accountId: string) => Promise<void>;
  syncGoogleAccount: (accountId: string) => Promise<GoogleAccount>;

  // Flow Bridge actions
  fetchFlowTasks: (projectId: string, params?: { status?: string; task_type?: string; episode_id?: string; scene_id?: string }) => Promise<void>;
  createFlowTask: (projectId: string, data: Partial<FlowTask>) => Promise<FlowTask>;
  updateFlowTask: (projectId: string, taskId: string, data: Partial<FlowTask>) => Promise<FlowTask>;
  deleteFlowTask: (projectId: string, taskId: string) => Promise<void>;
  exportPromptsForFlow: (projectId: string, episodeId?: string, sceneIds?: string[]) => Promise<unknown>;
  importFlowResults: (projectId: string, taskId: string, outputFiles: string[]) => Promise<unknown>;

  // Asset actions
  fetchAssets: (projectId: string, params?: { asset_type?: string; episode_id?: string; scene_id?: string }) => Promise<void>;
  uploadAsset: (projectId: string, file: File, assetType: string, episodeId?: string, sceneId?: string, metadata?: Record<string, unknown>) => Promise<Asset>;
  deleteAsset: (projectId: string, assetId: string) => Promise<void>;
  assembleEpisodeVideo: (projectId: string, episodeId: string, sceneOrder: string[], outputFilename?: string, includeAudio?: boolean, includeSubtitles?: boolean) => Promise<{ asset_id: string; file_path: string; file_size: number }>;
  addSubtitlesToVideo: (projectId: string, episodeId: string, videoAssetId: string, subtitleAssetId: string, outputFilename?: string) => Promise<{ asset_id: string; file_path: string }>;

  // Story Engine actions
  generateSeries: (projectId: string, data: { premise: string; genre?: string; themes?: string[]; num_episodes: number; tone?: string }) => Promise<{ episodes: Record<string, unknown>[]; series_bible: Record<string, unknown> }>;
  breakdownEpisode: (projectId: string, episodeId: string, data: { episode_outline: string; characters: Record<string, unknown>[]; locations: Record<string, unknown>[] }) => Promise<{ scenes: Record<string, unknown>[] }>;
  createEpisodesFromOutline: (projectId: string, episodesData: Record<string, unknown>[]) => Promise<{ created_episodes: number[]; count: number }>;

  // Utility
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearProject: () => void;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  currentProject: null,
  seriesBible: null,
  characters: [],
  locations: [],
  episodes: [],
  scenes: {},
  sceneCharacters: {},
  dialogues: {},
  prompts: [],
  googleAccounts: [],
  flowTasks: [],
  assets: [],
  projects: [],
  isLoading: false,
  error: null,
  selectedScene: null,
  setSelectedScene: (sceneId) => set({ selectedScene: sceneId }),

  setCurrentProject: (project) => set({ currentProject: project }),

  fetchProject: async (projectId) => {
    set({ isLoading: true, error: null });
    try {
      const project = await api.getProject(projectId);
      set({ currentProject: project, isLoading: false });
    } catch (error) {
      set({ error: 'Failed to fetch project', isLoading: false });
      throw error;
    }
  },

  fetchProjects: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.listProjects();
      set({ projects: response.items, isLoading: false });
    } catch (error) {
      set({ error: 'Failed to fetch projects', isLoading: false });
      throw error;
    }
  },

  createProject: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const project = await api.createProject(data);
      set({ isLoading: false });
      return project;
    } catch (error) {
      set({ error: 'Failed to create project', isLoading: false });
      throw error;
    }
  },

  updateProject: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const project = await api.updateProject(projectId, data);
      set({ currentProject: project, isLoading: false });
      return project;
    } catch (error) {
      set({ error: 'Failed to update project', isLoading: false });
      throw error;
    }
  },

  deleteProject: async (projectId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteProject(projectId);
      set({ currentProject: null, isLoading: false });
    } catch (error) {
      set({ error: 'Failed to delete project', isLoading: false });
      throw error;
    }
  },

  // Series Bible
  fetchSeriesBible: async (projectId) => {
    try {
      const bible = await api.getSeriesBible(projectId);
      set({ seriesBible: bible });
    } catch {
      set({ seriesBible: null });
    }
  },

  createSeriesBible: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const bible = await api.createSeriesBible(projectId, data);
      set({ seriesBible: bible, isLoading: false });
      return bible;
    } catch (error) {
      set({ error: 'Failed to create series bible', isLoading: false });
      throw error;
    }
  },

  updateSeriesBible: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const bible = await api.updateSeriesBible(projectId, data);
      set({ seriesBible: bible, isLoading: false });
      return bible;
    } catch (error) {
      set({ error: 'Failed to update series bible', isLoading: false });
      throw error;
    }
  },

  // Characters
  fetchCharacters: async (projectId) => {
    try {
      const response = await api.listCharacters(projectId);
      set({ characters: response.items });
    } catch {
      set({ characters: [] });
    }
  },

  createCharacter: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const character = await api.createCharacter(projectId, data);
      set((state) => ({ characters: [...state.characters, character], isLoading: false }));
      return character;
    } catch (error) {
      set({ error: 'Failed to create character', isLoading: false });
      throw error;
    }
  },

  updateCharacter: async (projectId, characterId, data) => {
    set({ isLoading: true, error: null });
    try {
      const character = await api.updateCharacter(projectId, characterId, data);
      set((state) => ({
        characters: state.characters.map((c) => (c.id === characterId ? character : c)),
        isLoading: false,
      }));
      return character;
    } catch (error) {
      set({ error: 'Failed to update character', isLoading: false });
      throw error;
    }
  },

  deleteCharacter: async (projectId, characterId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteCharacter(projectId, characterId);
      set((state) => ({
        characters: state.characters.filter((c) => c.id !== characterId),
        isLoading: false,
      }));
    } catch (error) {
      set({ error: 'Failed to delete character', isLoading: false });
      throw error;
    }
  },

  reorderCharacters: async (projectId, characterIds) => {
    try {
      const characters = await api.reorderCharacters(projectId, characterIds);
      set({ characters });
    } catch (error) {
      set({ error: 'Failed to reorder characters' });
      throw error;
    }
  },

  // Locations
  fetchLocations: async (projectId) => {
    try {
      const response = await api.listLocations(projectId);
      set({ locations: response.items });
    } catch {
      set({ locations: [] });
    }
  },

  createLocation: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const location = await api.createLocation(projectId, data);
      set((state) => ({ locations: [...state.locations, location], isLoading: false }));
      return location;
    } catch (error) {
      set({ error: 'Failed to create location', isLoading: false });
      throw error;
    }
  },

  updateLocation: async (projectId, locationId, data) => {
    set({ isLoading: true, error: null });
    try {
      const location = await api.updateLocation(projectId, locationId, data);
      set((state) => ({
        locations: state.locations.map((l) => (l.id === locationId ? location : l)),
        isLoading: false,
      }));
      return location;
    } catch (error) {
      set({ error: 'Failed to update location', isLoading: false });
      throw error;
    }
  },

  deleteLocation: async (projectId, locationId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteLocation(projectId, locationId);
      set((state) => ({
        locations: state.locations.filter((l) => l.id !== locationId),
        isLoading: false,
      }));
    } catch (error) {
      set({ error: 'Failed to delete location', isLoading: false });
      throw error;
    }
  },

  reorderLocations: async (projectId, locationIds) => {
    try {
      const locations = await api.reorderLocations(projectId, locationIds);
      set({ locations });
    } catch (error) {
      set({ error: 'Failed to reorder locations' });
      throw error;
    }
  },

  // Episodes
  fetchEpisodes: async (projectId) => {
    try {
      const response = await api.listEpisodes(projectId);
      set({ episodes: response.items });
    } catch {
      set({ episodes: [] });
    }
  },

  createEpisode: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const episode = await api.createEpisode(projectId, data);
      set((state) => ({ episodes: [...state.episodes, episode].sort((a, b) => a.episode_number - b.episode_number), isLoading: false }));
      return episode;
    } catch (error) {
      set({ error: 'Failed to create episode', isLoading: false });
      throw error;
    }
  },

  updateEpisode: async (projectId, episodeId, data) => {
    set({ isLoading: true, error: null });
    try {
      const episode = await api.updateEpisode(projectId, episodeId, data);
      set((state) => ({
        episodes: state.episodes.map((e) => (e.id === episodeId ? episode : e)),
        isLoading: false,
      }));
      return episode;
    } catch (error) {
      set({ error: 'Failed to update episode', isLoading: false });
      throw error;
    }
  },

  deleteEpisode: async (projectId, episodeId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteEpisode(projectId, episodeId);
      set((state) => ({
        episodes: state.episodes.filter((e) => e.id !== episodeId),
        scenes: Object.fromEntries(Object.entries(state.scenes).filter(([key]) => !key.startsWith(episodeId))),
        isLoading: false,
      }));
    } catch (error) {
      set({ error: 'Failed to delete episode', isLoading: false });
      throw error;
    }
  },

  // Scenes
  fetchScenes: async (projectId, episodeId) => {
    try {
      const response = await api.listScenes(projectId, episodeId);
      set((state) => ({ scenes: { ...state.scenes, [episodeId]: response.items } }));
    } catch {
      set((state) => ({ scenes: { ...state.scenes, [episodeId]: [] } }));
    }
  },

  createScene: async (projectId, episodeId, data) => {
    set({ isLoading: true, error: null });
    try {
      const scene = await api.createScene(projectId, episodeId, data);
      set((state) => ({
        scenes: {
          ...state.scenes,
          [episodeId]: [...(state.scenes[episodeId] || []), scene].sort((a, b) => a.scene_number - b.scene_number),
        },
        isLoading: false,
      }));
      return scene;
    } catch (error) {
      set({ error: 'Failed to create scene', isLoading: false });
      throw error;
    }
  },

  updateScene: async (projectId, episodeId, sceneId, data) => {
    set({ isLoading: true, error: null });
    try {
      const scene = await api.updateScene(projectId, episodeId, sceneId, data);
      set((state) => ({
        scenes: {
          ...state.scenes,
          [episodeId]: state.scenes[episodeId]?.map((s) => (s.id === sceneId ? scene : s)) || [],
        },
        isLoading: false,
      }));
      return scene;
    } catch (error) {
      set({ error: 'Failed to update scene', isLoading: false });
      throw error;
    }
  },

  deleteScene: async (projectId, episodeId, sceneId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteScene(projectId, episodeId, sceneId);
      set((state) => ({
        scenes: {
          ...state.scenes,
          [episodeId]: state.scenes[episodeId]?.filter((s) => s.id !== sceneId) || [],
        },
        sceneCharacters: Object.fromEntries(
          Object.entries(state.sceneCharacters).filter(([key]) => !key.startsWith(sceneId))
        ),
        dialogues: Object.fromEntries(
          Object.entries(state.dialogues).filter(([key]) => !key.startsWith(sceneId))
        ),
        isLoading: false,
      }));
    } catch (error) {
      set({ error: 'Failed to delete scene', isLoading: false });
      throw error;
    }
  },

  // Scene Characters
  fetchSceneCharacters: async (projectId, episodeId, sceneId) => {
    try {
      const characters = await api.listSceneCharacters(projectId, episodeId, sceneId);
      set((state) => ({ sceneCharacters: { ...state.sceneCharacters, [sceneId]: characters } }));
    } catch {
      set((state) => ({ sceneCharacters: { ...state.sceneCharacters, [sceneId]: [] } }));
    }
  },

  addCharacterToScene: async (projectId, episodeId, sceneId, characterId, data) => {
    set({ isLoading: true, error: null });
    try {
      const sceneChar = await api.addCharacterToScene(projectId, episodeId, sceneId, characterId, data);
      set((state) => ({
        sceneCharacters: {
          ...state.sceneCharacters,
          [sceneId]: [...(state.sceneCharacters[sceneId] || []), sceneChar],
        },
        isLoading: false,
      }));
      return sceneChar;
    } catch (error) {
      set({ error: 'Failed to add character to scene', isLoading: false });
      throw error;
    }
  },

  removeCharacterFromScene: async (projectId, episodeId, sceneId, characterId) => {
    set({ isLoading: true, error: null });
    try {
      await api.removeCharacterFromScene(projectId, episodeId, sceneId, characterId);
      set((state) => ({
        sceneCharacters: {
          ...state.sceneCharacters,
          [sceneId]: state.sceneCharacters[sceneId]?.filter((c) => c.character_id !== characterId) || [],
        },
        isLoading: false,
      }));
    } catch (error) {
      set({ error: 'Failed to remove character from scene', isLoading: false });
      throw error;
    }
  },

  // Dialogues
  fetchDialogues: async (projectId, episodeId, sceneId) => {
    try {
      const dialogues = await api.listDialogues(projectId, episodeId, sceneId);
      set((state) => ({ dialogues: { ...state.dialogues, [sceneId]: dialogues } }));
    } catch {
      set((state) => ({ dialogues: { ...state.dialogues, [sceneId]: [] } }));
    }
  },

  createDialogue: async (projectId, episodeId, sceneId, data) => {
    set({ isLoading: true, error: null });
    try {
      const dialogue = await api.createDialogue(projectId, episodeId, sceneId, data);
      set((state) => ({
        dialogues: {
          ...state.dialogues,
          [sceneId]: [...(state.dialogues[sceneId] || []), dialogue].sort((a, b) => a.order_index - b.order_index),
        },
        isLoading: false,
      }));
      return dialogue;
    } catch (error) {
      set({ error: 'Failed to create dialogue', isLoading: false });
      throw error;
    }
  },

  updateDialogue: async (projectId, episodeId, sceneId, dialogueId, data) => {
    set({ isLoading: true, error: null });
    try {
      const dialogue = await api.updateDialogue(projectId, episodeId, sceneId, dialogueId, data);
      set((state) => ({
        dialogues: {
          ...state.dialogues,
          [sceneId]: state.dialogues[sceneId]?.map((d) => (d.id === dialogueId ? dialogue : d)) || [],
        },
        isLoading: false,
      }));
      return dialogue;
    } catch (error) {
      set({ error: 'Failed to update dialogue', isLoading: false });
      throw error;
    }
  },

  deleteDialogue: async (projectId, episodeId, sceneId, dialogueId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteDialogue(projectId, episodeId, sceneId, dialogueId);
      set((state) => ({
        dialogues: {
          ...state.dialogues,
          [sceneId]: state.dialogues[sceneId]?.filter((d) => d.id !== dialogueId) || [],
        },
        isLoading: false,
      }));
    } catch (error) {
      set({ error: 'Failed to delete dialogue', isLoading: false });
      throw error;
    }
  },

  // Prompts
  fetchPrompts: async (projectId, params) => {
    try {
      const response = await api.listPrompts(projectId, params);
      set({ prompts: response.items });
    } catch {
      set({ prompts: [] });
    }
  },

  createPrompt: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const prompt = await api.createPrompt(projectId, data);
      set((state) => ({ prompts: [...state.prompts, prompt], isLoading: false }));
      return prompt;
    } catch (error) {
      set({ error: 'Failed to create prompt', isLoading: false });
      throw error;
    }
  },

  updatePrompt: async (projectId, promptId, data) => {
    set({ isLoading: true, error: null });
    try {
      const prompt = await api.updatePrompt(projectId, promptId, data);
      set((state) => ({
        prompts: state.prompts.map((p) => (p.id === promptId ? prompt : p)),
        isLoading: false,
      }));
      return prompt;
    } catch (error) {
      set({ error: 'Failed to update prompt', isLoading: false });
      throw error;
    }
  },

  deletePrompt: async (projectId, promptId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deletePrompt(projectId, promptId);
      set((state) => ({ prompts: state.prompts.filter((p) => p.id !== promptId), isLoading: false }));
    } catch (error) {
      set({ error: 'Failed to delete prompt', isLoading: false });
      throw error;
    }
  },

  generatePrompt: async (data) => {
    return api.generatePrompt(data);
  },

  generateAllScenePrompts: async (projectId, episodeId, sceneId) => {
    set({ isLoading: true, error: null });
    try {
      const prompts = await api.generateAllScenePrompts(projectId, episodeId, sceneId);
      set((state) => ({ prompts: [...state.prompts, ...prompts], isLoading: false }));
      return prompts;
    } catch (error) {
      set({ error: 'Failed to generate scene prompts', isLoading: false });
      throw error;
    }
  },

  // Google Accounts
  fetchGoogleAccounts: async () => {
    try {
      const accounts = await api.listGoogleAccounts();
      set({ googleAccounts: accounts });
    } catch {
      set({ googleAccounts: [] });
    }
  },

  createGoogleAccount: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const account = await api.createGoogleAccount(data);
      set((state) => ({ googleAccounts: [...state.googleAccounts, account], isLoading: false }));
      return account;
    } catch (error) {
      set({ error: 'Failed to create Google account', isLoading: false });
      throw error;
    }
  },

  updateGoogleAccount: async (accountId, data) => {
    set({ isLoading: true, error: null });
    try {
      const account = await api.updateGoogleAccount(accountId, data);
      set((state) => ({
        googleAccounts: state.googleAccounts.map((a) => (a.id === accountId ? account : a)),
        isLoading: false,
      }));
      return account;
    } catch (error) {
      set({ error: 'Failed to update Google account', isLoading: false });
      throw error;
    }
  },

  deleteGoogleAccount: async (accountId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteGoogleAccount(accountId);
      set((state) => ({ googleAccounts: state.googleAccounts.filter((a) => a.id !== accountId), isLoading: false }));
    } catch (error) {
      set({ error: 'Failed to delete Google account', isLoading: false });
      throw error;
    }
  },

  syncGoogleAccount: async (accountId) => {
    try {
      const account = await api.syncGoogleAccount(accountId);
      set((state) => ({
        googleAccounts: state.googleAccounts.map((a) => (a.id === accountId ? account : a)),
      }));
      return account;
    } catch (error) {
      set({ error: 'Failed to sync Google account' });
      throw error;
    }
  },

  // Flow Bridge
  fetchFlowTasks: async (projectId, params) => {
    try {
      const response = await api.listFlowTasks(projectId, params);
      set({ flowTasks: response.items });
    } catch {
      set({ flowTasks: [] });
    }
  },

  createFlowTask: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const task = await api.createFlowTask(projectId, data);
      set((state) => ({ flowTasks: [...state.flowTasks, task], isLoading: false }));
      return task;
    } catch (error) {
      set({ error: 'Failed to create flow task', isLoading: false });
      throw error;
    }
  },

  updateFlowTask: async (projectId, taskId, data) => {
    set({ isLoading: true, error: null });
    try {
      const task = await api.updateFlowTask(projectId, taskId, data);
      set((state) => ({
        flowTasks: state.flowTasks.map((t) => (t.id === taskId ? task : t)),
        isLoading: false,
      }));
      return task;
    } catch (error) {
      set({ error: 'Failed to update flow task', isLoading: false });
      throw error;
    }
  },

  deleteFlowTask: async (projectId, taskId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteFlowTask(projectId, taskId);
      set((state) => ({ flowTasks: state.flowTasks.filter((t) => t.id !== taskId), isLoading: false }));
    } catch (error) {
      set({ error: 'Failed to delete flow task', isLoading: false });
      throw error;
    }
  },

  exportPromptsForFlow: async (projectId, episodeId, sceneIds) => {
    return api.exportPromptsForFlow(projectId, episodeId, sceneIds);
  },

  importFlowResults: async (projectId, taskId, outputFiles) => {
    return api.importFlowResults(projectId, taskId, outputFiles);
  },

  // Assets
  fetchAssets: async (projectId, params) => {
    try {
      const response = await api.listAssets(projectId, params);
      set({ assets: response.items });
    } catch {
      set({ assets: [] });
    }
  },

  uploadAsset: async (projectId, file, assetType, episodeId, sceneId, metadata) => {
    set({ isLoading: true, error: null });
    try {
      const asset = await api.uploadAsset(projectId, file, assetType as any, episodeId, sceneId, metadata);
      set((state) => ({ assets: [...state.assets, asset], isLoading: false }));
      return asset;
    } catch (error) {
      set({ error: 'Failed to upload asset', isLoading: false });
      throw error;
    }
  },

  deleteAsset: async (projectId, assetId) => {
    set({ isLoading: true, error: null });
    try {
      await api.deleteAsset(projectId, assetId);
      set((state) => ({ assets: state.assets.filter((a) => a.id !== assetId), isLoading: false }));
    } catch (error) {
      set({ error: 'Failed to delete asset', isLoading: false });
      throw error;
    }
  },

  assembleEpisodeVideo: async (projectId, episodeId, sceneOrder, outputFilename, includeAudio, includeSubtitles) => {
    set({ isLoading: true, error: null });
    try {
      const result = await api.assembleEpisodeVideo(projectId, episodeId, sceneOrder, outputFilename, includeAudio, includeSubtitles);
      set({ isLoading: false });
      return result;
    } catch (error) {
      set({ error: 'Failed to assemble episode video', isLoading: false });
      throw error;
    }
  },

  addSubtitlesToVideo: async (projectId, episodeId, videoAssetId, subtitleAssetId, outputFilename) => {
    set({ isLoading: true, error: null });
    try {
      const result = await api.addSubtitlesToVideo(projectId, episodeId, videoAssetId, subtitleAssetId, outputFilename);
      set({ isLoading: false });
      return result;
    } catch (error) {
      set({ error: 'Failed to add subtitles', isLoading: false });
      throw error;
    }
  },

  // Story Engine
  generateSeries: async (projectId, data) => {
    set({ isLoading: true, error: null });
    try {
      const result = await api.generateSeries(projectId, data);
      // Create episodes from generated data
      if (result.episodes.length > 0) {
        await get().createEpisodesFromOutline(projectId, result.episodes);
        // Refresh episodes
        await get().fetchEpisodes(projectId);
      }
      // Refresh series bible
      await get().fetchSeriesBible(projectId);
      set({ isLoading: false });
      return result;
    } catch (error) {
      set({ error: 'Failed to generate series', isLoading: false });
      throw error;
    }
  },

  breakdownEpisode: async (projectId, episodeId, data) => {
    set({ isLoading: true, error: null });
    try {
      const result = await api.breakdownEpisode(projectId, episodeId, data);
      // Refresh scenes for this episode
      await get().fetchScenes(projectId, episodeId);
      // Update episode status
      await get().updateEpisode(projectId, episodeId, { status: 'scenes_ready' });
      set({ isLoading: false });
      return result;
    } catch (error) {
      set({ error: 'Failed to breakdown episode', isLoading: false });
      throw error;
    }
  },

  createEpisodesFromOutline: async (projectId, episodesData) => {
    return api.createEpisodesFromOutline(projectId, episodesData);
  },

  // Utility
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  clearProject: () => set({
    currentProject: null,
    seriesBible: null,
    characters: [],
    locations: [],
    episodes: [],
    scenes: {},
    sceneCharacters: {},
    dialogues: {},
    prompts: [],
    flowTasks: [],
    assets: [],
    projects: [],
    selectedScene: null,
    error: null,
  }),
}));