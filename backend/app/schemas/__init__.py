from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models import (
    UserRole, ProjectStatus, EpisodeStatus, SceneStatus,
    GoogleAccountStatus, AssetType, PromptType
)


# Base schemas
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# User schemas
class UserBase(BaseSchema):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseSchema):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class UserLogin(BaseSchema):
    email: EmailStr
    password: str


class Token(BaseSchema):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseSchema):
    user_id: Optional[UUID] = None


# Project schemas
class ProjectBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    genre: Optional[str] = None
    themes: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseSchema):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    genre: Optional[str] = None
    themes: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None
    status: Optional[ProjectStatus] = None
    selected_google_account_id: Optional[UUID] = None


class ProjectResponse(ProjectBase):
    id: UUID
    owner_id: UUID
    status: ProjectStatus
    selected_google_account_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseSchema):
    projects: List[ProjectResponse]
    total: int
    page: int
    page_size: int


# Series Bible schemas
class SeriesBibleBase(BaseSchema):
    premise: Optional[str] = None
    main_plot: Optional[str] = None
    subplots: Optional[List[Dict[str, Any]]] = None
    character_relationships: Optional[Dict[str, Any]] = None
    world_settings: Optional[str] = None
    tone: Optional[str] = None
    visual_style: Optional[str] = None
    ending_direction: Optional[str] = None
    episode_structure: Optional[Dict[str, Any]] = None


class SeriesBibleCreate(SeriesBibleBase):
    pass


class SeriesBibleUpdate(SeriesBibleBase):
    pass


class SeriesBibleResponse(SeriesBibleBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime


# Character schemas
class CharacterBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = None
    physical_appearance: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    costume: Optional[str] = None
    consistency_instructions: Optional[str] = None
    reference_images: Optional[List[str]] = None
    order_index: int = 0


class CharacterCreate(CharacterBase):
    pass


class CharacterUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = None
    physical_appearance: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    costume: Optional[str] = None
    consistency_instructions: Optional[str] = None
    reference_images: Optional[List[str]] = None
    order_index: Optional[int] = None


class CharacterResponse(CharacterBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime


# Location schemas
class LocationBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    environment: Optional[str] = None
    visual_references: Optional[List[str]] = None
    lighting: Optional[str] = None
    atmosphere: Optional[str] = None
    consistency_instructions: Optional[str] = None
    order_index: int = 0


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    environment: Optional[str] = None
    visual_references: Optional[List[str]] = None
    lighting: Optional[str] = None
    atmosphere: Optional[str] = None
    consistency_instructions: Optional[str] = None
    order_index: Optional[int] = None


class LocationResponse(LocationBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime


# Episode schemas
class EpisodeBase(BaseSchema):
    episode_number: int = Field(..., ge=1)
    title: Optional[str] = None
    outline: Optional[str] = None
    production_notes: Optional[str] = None
    estimated_cost: Optional[float] = None


class EpisodeCreate(EpisodeBase):
    pass


class EpisodeUpdate(BaseSchema):
    title: Optional[str] = None
    outline: Optional[str] = None
    status: Optional[EpisodeStatus] = None
    production_notes: Optional[str] = None
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None


class EpisodeResponse(EpisodeBase):
    id: UUID
    project_id: UUID
    status: EpisodeStatus
    actual_cost: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


# Scene schemas
class SceneBase(BaseSchema):
    scene_number: int = Field(..., ge=1)
    title: Optional[str] = None
    description: Optional[str] = None
    shot_list: Optional[List[Dict[str, Any]]] = None
    camera_directions: Optional[str] = None


class SceneCreate(SceneBase):
    location_id: Optional[UUID] = None


class SceneUpdate(BaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    shot_list: Optional[List[Dict[str, Any]]] = None
    camera_directions: Optional[str] = None
    location_id: Optional[UUID] = None
    status: Optional[SceneStatus] = None


class SceneResponse(SceneBase):
    id: UUID
    episode_id: UUID
    location_id: Optional[UUID] = None
    status: SceneStatus
    created_at: datetime
    updated_at: datetime


# SceneCharacter schemas
class SceneCharacterBase(BaseSchema):
    character_id: UUID
    actions: Optional[str] = None
    emotional_state: Optional[str] = None
    position: Optional[str] = None


class SceneCharacterCreate(SceneCharacterBase):
    pass


class SceneCharacterResponse(SceneCharacterBase):
    id: UUID
    scene_id: UUID


# Dialogue schemas
class DialogueBase(BaseSchema):
    character_id: UUID
    order_index: int
    text: str
    direction: Optional[str] = None
    audio_prompt: Optional[str] = None


class DialogueCreate(DialogueBase):
    pass


class DialogueUpdate(BaseSchema):
    text: Optional[str] = None
    direction: Optional[str] = None
    audio_prompt: Optional[str] = None


class DialogueResponse(DialogueBase):
    id: UUID
    scene_id: UUID
    created_at: datetime
    updated_at: datetime


# Prompt schemas
class PromptBase(BaseSchema):
    prompt_type: PromptType
    title: str = Field(..., min_length=1, max_length=255)
    prompt_text: str
    negative_prompt: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_template: bool = False


class PromptCreate(PromptBase):
    scene_id: Optional[UUID] = None
    character_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    episode_id: Optional[UUID] = None


class PromptUpdate(BaseSchema):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    prompt_text: Optional[str] = None
    negative_prompt: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class PromptResponse(PromptBase):
    id: UUID
    project_id: UUID
    scene_id: Optional[UUID] = None
    character_id: Optional[UUID] = None
    location_id: Optional[UUID] = None
    episode_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# Google Account schemas
class GoogleAccountBase(BaseSchema):
    email: EmailStr
    display_name: Optional[str] = None


class GoogleAccountCreate(GoogleAccountBase):
    pass


class GoogleAccountUpdate(BaseSchema):
    display_name: Optional[str] = None
    status: Optional[GoogleAccountStatus] = None
    session_data: Optional[Dict[str, Any]] = None


class GoogleAccountResponse(GoogleAccountBase):
    id: UUID
    user_id: UUID
    status: GoogleAccountStatus
    last_sync: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Flow Task schemas
class FlowTaskBase(BaseSchema):
    task_type: str
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    input_prompts: Optional[List[Dict[str, Any]]] = None
    reference_assets: Optional[List[str]] = None


class FlowTaskCreate(FlowTaskBase):
    episode_id: Optional[UUID] = None
    scene_id: Optional[UUID] = None
    google_account_id: Optional[UUID] = None


class FlowTaskUpdate(BaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    input_prompts: Optional[List[Dict[str, Any]]] = None
    reference_assets: Optional[List[str]] = None
    status: Optional[str] = None
    output_files: Optional[List[str]] = None


class FlowTaskResponse(FlowTaskBase):
    id: UUID
    project_id: UUID
    episode_id: Optional[UUID] = None
    scene_id: Optional[UUID] = None
    google_account_id: Optional[UUID] = None
    status: str
    output_files: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


# Asset schemas
class AssetBase(BaseSchema):
    asset_type: AssetType
    file_name: str
    mime_type: Optional[str] = None


class AssetCreate(AssetBase):
    file_path: str
    file_size: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class AssetResponse(AssetBase):
    id: UUID
    project_id: UUID
    episode_id: Optional[UUID] = None
    scene_id: Optional[UUID] = None
    file_path: str
    file_size: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


# Episode Revision schemas
class EpisodeRevisionBase(BaseSchema):
    revision_number: int
    outline: Optional[str] = None
    scenes_snapshot: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None


class EpisodeRevisionCreate(EpisodeRevisionBase):
    pass


class EpisodeRevisionResponse(EpisodeRevisionBase):
    id: UUID
    episode_id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime


# Audit Log schemas
class AuditLogResponse(BaseSchema):
    id: UUID
    user_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[UUID] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime


# Story Generation schemas
class StoryGenerationRequest(BaseSchema):
    premise: str
    genre: Optional[str] = None
    themes: Optional[List[str]] = None
    num_episodes: int = Field(default=20, ge=1, le=50)
    tone: Optional[str] = None


class StoryGenerationResponse(BaseSchema):
    episodes: List[Dict[str, Any]]
    series_bible: Dict[str, Any]


class SceneBreakdownRequest(BaseSchema):
    episode_outline: str
    characters: List[Dict[str, Any]]
    locations: List[Dict[str, Any]]


class SceneBreakdownResponse(BaseSchema):
    scenes: List[Dict[str, Any]]


# Prompt Generation schemas
class PromptGenerationRequest(BaseSchema):
    prompt_type: PromptType
    context: Dict[str, Any]
    style_preferences: Optional[Dict[str, Any]] = None


class PromptGenerationResponse(BaseSchema):
    prompt_text: str
    negative_prompt: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


# Pagination
class PaginationParams(BaseSchema):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseSchema):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int