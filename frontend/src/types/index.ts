export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: 'user' | 'admin';
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

export interface Project {
  id: string;
  owner_id: string;
  title: string;
  description: string | null;
  genre: string | null;
  themes: string[] | null;
  status: 'draft' | 'in_production' | 'completed' | 'archived';
  settings: Record<string, unknown> | null;
  selected_google_account_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SeriesBible {
  id: string;
  project_id: string;
  premise: string | null;
  main_plot: string | null;
  subplots: Array<Record<string, unknown>> | null;
  character_relationships: Record<string, unknown> | null;
  world_settings: string | null;
  tone: string | null;
  visual_style: string | null;
  ending_direction: string | null;
  episode_structure: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  role: string | null;
  physical_appearance: string | null;
  personality: string | null;
  background: string | null;
  costume: string | null;
  consistency_instructions: string | null;
  reference_images: string[] | null;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface Location {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  environment: string | null;
  visual_references: string[] | null;
  lighting: string | null;
  atmosphere: string | null;
  consistency_instructions: string | null;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface Episode {
  id: string;
  project_id: string;
  episode_number: number;
  title: string | null;
  outline: string | null;
  status: 'planned' | 'writing' | 'scenes_ready' | 'prompts_ready' | 'generating' | 'post_production' | 'completed';
  production_notes: string | null;
  estimated_cost: number | null;
  actual_cost: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface Scene {
  id: string;
  episode_id: string;
  location_id: string | null;
  scene_number: number;
  title: string | null;
  description: string | null;
  shot_list: Array<Record<string, unknown>> | null;
  camera_directions: string | null;
  status: 'planned' | 'written' | 'prompts_ready' | 'generating' | 'completed';
  created_at: string;
  updated_at: string;
}

export interface SceneCharacter {
  id: string;
  scene_id: string;
  character_id: string;
  actions: string | null;
  emotional_state: string | null;
  position: string | null;
  character?: Character;
}

export interface Dialogue {
  id: string;
  scene_id: string;
  character_id: string;
  order_index: number;
  text: string;
  direction: string | null;
  audio_prompt: string | null;
  created_at: string;
  updated_at: string;
  character?: Character;
}

export type PromptType = 
  | 'character_image'
  | 'location_image'
  | 'scene_image'
  | 'video_generation'
  | 'camera_movement'
  | 'character_action'
  | 'dialogue_audio';

export interface Prompt {
  id: string;
  scene_id: string | null;
  character_id: string | null;
  location_id: string | null;
  episode_id: string | null;
  project_id: string;
  prompt_type: PromptType;
  title: string;
  prompt_text: string;
  negative_prompt: string | null;
  parameters: Record<string, unknown> | null;
  is_template: boolean;
  created_at: string;
  updated_at: string;
}

export interface GoogleAccount {
  id: string;
  user_id: string;
  email: string;
  display_name: string | null;
  status: 'connected' | 'disconnected' | 'expired' | 'error';
  session_data: Record<string, unknown> | null;
  last_sync: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface FlowTask {
  id: string;
  project_id: string;
  episode_id: string | null;
  scene_id: string | null;
  task_type: string;
  title: string;
  description: string | null;
  input_prompts: Array<Record<string, unknown>> | null;
  reference_assets: string[] | null;
  status: string;
  output_files: string[] | null;
  google_account_id: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export type AssetType = 'image' | 'video' | 'audio' | 'subtitle' | 'document';

export interface Asset {
  id: string;
  project_id: string;
  episode_id: string | null;
  scene_id: string | null;
  asset_type: AssetType;
  file_path: string;
  file_name: string;
  file_size: number | null;
  mime_type: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface StoryGenerationRequest {
  premise: string;
  genre?: string;
  themes?: string[];
  num_episodes: number;
  tone?: string;
}

export interface StoryGenerationResponse {
  episodes: Array<Record<string, unknown>>;
  series_bible: Record<string, unknown>;
}

export interface SceneBreakdownRequest {
  episode_outline: string;
  characters: Array<Record<string, unknown>>;
  locations: Array<Record<string, unknown>>;
}

export interface SceneBreakdownResponse {
  scenes: Array<Record<string, unknown>>;
}

export interface PromptGenerationRequest {
  prompt_type: PromptType;
  context: Record<string, unknown>;
  style_preferences?: Record<string, unknown>;
}

export interface PromptGenerationResponse {
  prompt_text: string;
  negative_prompt: string | null;
  parameters: Record<string, unknown> | null;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
}