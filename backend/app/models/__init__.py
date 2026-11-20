from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Enum, Integer, Boolean,
    JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


class UserRole(PyEnum):
    USER = "user"
    ADMIN = "admin"


class ProjectStatus(PyEnum):
    DRAFT = "draft"
    IN_PRODUCTION = "in_production"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class EpisodeStatus(PyEnum):
    PLANNED = "planned"
    WRITING = "writing"
    SCENES_READY = "scenes_ready"
    PROMPTS_READY = "prompts_ready"
    GENERATING = "generating"
    POST_PRODUCTION = "post_production"
    COMPLETED = "completed"


class SceneStatus(PyEnum):
    PLANNED = "planned"
    WRITTEN = "written"
    PROMPTS_READY = "prompts_ready"
    GENERATING = "generating"
    COMPLETED = "completed"


class GoogleAccountStatus(PyEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"
    ERROR = "error"


class AssetType(PyEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    DOCUMENT = "document"


class PromptType(PyEnum):
    CHARACTER_IMAGE = "character_image"
    LOCATION_IMAGE = "location_image"
    SCENE_IMAGE = "scene_image"
    VIDEO_GENERATION = "video_generation"
    CAMERA_MOVEMENT = "camera_movement"
    CHARACTER_ACTION = "character_action"
    DIALOGUE_AUDIO = "dialogue_audio"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    projects = relationship("Project", back_populates="owner", lazy="selectin")
    google_accounts = relationship("GoogleAccount", back_populates="user", lazy="selectin", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", lazy="selectin")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    genre: Mapped[str] = mapped_column(String(100), nullable=True)
    themes: Mapped[List[str]] = mapped_column(JSON, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, nullable=True)
    selected_google_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("google_accounts.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="projects", lazy="selectin")
    series_bible = relationship("SeriesBible", back_populates="project", lazy="selectin", uselist=False, cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="project", lazy="selectin", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="project", lazy="selectin", cascade="all, delete-orphan")
    episodes = relationship("Episode", back_populates="project", lazy="selectin", cascade="all, delete-orphan")
    google_account = relationship("GoogleAccount", foreign_keys=[selected_google_account_id], lazy="selectin")
    assets = relationship("Asset", back_populates="project", lazy="selectin", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="project", lazy="selectin")


class SeriesBible(Base):
    __tablename__ = "series_bibles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    premise: Mapped[str] = mapped_column(Text, nullable=True)
    main_plot: Mapped[str] = mapped_column(Text, nullable=True)
    subplots: Mapped[List[dict]] = mapped_column(JSON, nullable=True)
    character_relationships: Mapped[dict] = mapped_column(JSON, nullable=True)
    world_settings: Mapped[str] = mapped_column(Text, nullable=True)
    tone: Mapped[str] = mapped_column(String(255), nullable=True)
    visual_style: Mapped[str] = mapped_column(String(255), nullable=True)
    ending_direction: Mapped[str] = mapped_column(Text, nullable=True)
    episode_structure: Mapped[dict] = mapped_column(JSON, nullable=True)
    # Asal bible: 'manual' (dibuat/diubah lewat API bible manual) atau
    # 'auto' (ditulis auto-generate). Langkah 1 auto-generate TIDAK
    # menimpa bible 'manual' yang berisi main_plot (lihat auto_generate).
    # Default 'manual' agar bible lama (pra-migrasi) ikut terlindungi.
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="series_bible", lazy="selectin")


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=True)
    physical_appearance: Mapped[str] = mapped_column(Text, nullable=True)
    personality: Mapped[str] = mapped_column(Text, nullable=True)
    background: Mapped[str] = mapped_column(Text, nullable=True)
    costume: Mapped[str] = mapped_column(Text, nullable=True)
    consistency_instructions: Mapped[str] = mapped_column(Text, nullable=True)
    reference_images: Mapped[List[str]] = mapped_column(JSON, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="characters", lazy="selectin")
    scenes = relationship("SceneCharacter", back_populates="character", lazy="selectin", cascade="all, delete-orphan")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    environment: Mapped[str] = mapped_column(Text, nullable=True)
    visual_references: Mapped[List[str]] = mapped_column(JSON, nullable=True)
    lighting: Mapped[str] = mapped_column(String(255), nullable=True)
    atmosphere: Mapped[str] = mapped_column(String(255), nullable=True)
    consistency_instructions: Mapped[str] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="locations", lazy="selectin")
    scenes = relationship("Scene", back_populates="location", lazy="selectin")


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    outline: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[EpisodeStatus] = mapped_column(Enum(EpisodeStatus), default=EpisodeStatus.PLANNED, nullable=False)
    production_notes: Mapped[str] = mapped_column(Text, nullable=True)
    estimated_cost: Mapped[float] = mapped_column(nullable=True)
    actual_cost: Mapped[float] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    project = relationship("Project", back_populates="episodes", lazy="selectin")
    scenes = relationship("Scene", back_populates="episode", lazy="selectin", cascade="all, delete-orphan", order_by="Scene.scene_number")
    assets = relationship("Asset", back_populates="episode", lazy="selectin", cascade="all, delete-orphan")
    revisions = relationship("EpisodeRevision", back_populates="episode", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "episode_number", name="uq_project_episode"),
        Index("ix_episode_project_number", "project_id", "episode_number"),
    )


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True)
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    shot_list: Mapped[List[dict]] = mapped_column(JSON, nullable=True)
    camera_directions: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[SceneStatus] = mapped_column(Enum(SceneStatus), default=SceneStatus.PLANNED, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    episode = relationship("Episode", back_populates="scenes", lazy="selectin")
    location = relationship("Location", back_populates="scenes", lazy="selectin")
    characters = relationship("SceneCharacter", back_populates="scene", lazy="selectin", cascade="all, delete-orphan")
    dialogues = relationship("Dialogue", back_populates="scene", lazy="selectin", cascade="all, delete-orphan")
    prompts = relationship("Prompt", back_populates="scene", lazy="selectin", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="scene", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("episode_id", "scene_number", name="uq_episode_scene"),
        Index("ix_scene_episode_number", "episode_id", "scene_number"),
    )


class SceneCharacter(Base):
    __tablename__ = "scene_characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    actions: Mapped[str] = mapped_column(Text, nullable=True)
    emotional_state: Mapped[str] = mapped_column(String(255), nullable=True)
    position: Mapped[str] = mapped_column(String(255), nullable=True)

    scene = relationship("Scene", back_populates="characters", lazy="selectin")
    character = relationship("Character", back_populates="scenes", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("scene_id", "character_id", name="uq_scene_character"),
    )


class Dialogue(Base):
    __tablename__ = "dialogues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=True)
    audio_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    scene = relationship("Scene", back_populates="dialogues", lazy="selectin")
    character = relationship("Character", lazy="selectin")


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=True, index=True)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=True, index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=True, index=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_type: Mapped[PromptType] = mapped_column(Enum(PromptType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    scene = relationship("Scene", back_populates="prompts", lazy="selectin")
    character = relationship("Character", lazy="selectin")
    location = relationship("Location", lazy="selectin")
    episode = relationship("Episode", lazy="selectin")
    project = relationship("Project", lazy="selectin")


class GoogleAccount(Base):
    __tablename__ = "google_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[GoogleAccountStatus] = mapped_column(Enum(GoogleAccountStatus), default=GoogleAccountStatus.DISCONNECTED, nullable=False)
    session_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    last_sync: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="google_accounts", lazy="selectin")
    projects = relationship("Project", back_populates="google_account", lazy="selectin", foreign_keys="Project.selected_google_account_id")

    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_user_google_email"),
    )


class FlowTask(Base):
    __tablename__ = "flow_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=True, index=True)
    scene_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    input_prompts: Mapped[List[dict]] = mapped_column(JSON, nullable=True)
    reference_assets: Mapped[List[str]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    output_files: Mapped[List[str]] = mapped_column(JSON, nullable=True)
    google_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("google_accounts.id", ondelete="SET NULL"), nullable=True)
    # Google-account fallback (Flow Bridge): account actually in use right now.
    # google_account_id keeps the account originally requested; active_account_id
    # moves when fallback switches to the next account. fallback_history is an
    # append-only audit trail: [{account_id, email, result, reason, at}].
    active_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("google_accounts.id", ondelete="SET NULL"), nullable=True)
    fallback_history: Mapped[List[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    project = relationship("Project", lazy="selectin")
    episode = relationship("Episode", lazy="selectin")
    scene = relationship("Scene", lazy="selectin")
    google_account = relationship("GoogleAccount", lazy="selectin", foreign_keys=[google_account_id])
    active_account = relationship("GoogleAccount", lazy="selectin", foreign_keys=[active_account_id])


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=True, index=True)
    scene_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=True, index=True)
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)
    asset_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="assets", lazy="selectin")
    episode = relationship("Episode", back_populates="assets", lazy="selectin")
    scene = relationship("Scene", back_populates="assets", lazy="selectin")


class EpisodeRevision(Base):
    __tablename__ = "episode_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    outline: Mapped[str] = mapped_column(Text, nullable=True)
    scenes_snapshot: Mapped[List[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    episode = relationship("Episode", back_populates="revisions", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("episode_id", "revision_number", name="uq_episode_revision"),
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Single-row settings table - only one record expected
    ai_providers: Mapped[list[dict]] = mapped_column(JSON, nullable=True)
    google_oauth_client_id_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    google_oauth_client_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="audit_logs", lazy="selectin")
    project = relationship("Project", back_populates="audit_logs", lazy="selectin")

    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_project_created", "project_id", "created_at"),
    )

class AutoGenerateJobStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AutoGenerateStepStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Auto-generate job steps, in run order (spec §4):
# 1 series_bible, 2 characters, 3 locations, 4 episodes, 5 prompts.
AUTO_GENERATE_STEPS = [
    ("series_bible", 1),
    ("characters", 2),
    ("locations", 3),
    ("episodes", 4),
    ("prompts", 5),
]


class AutoGenerateJob(Base):
    """One auto-generate run for a project: title in, bible + cast +
    locations + episodes + prompts out (spec §5)."""

    __tablename__ = "auto_generate_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(100), nullable=True)
    num_episodes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    premise: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[AutoGenerateJobStatus] = mapped_column(Enum(AutoGenerateJobStatus), default=AutoGenerateJobStatus.PENDING, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    project = relationship("Project", lazy="selectin")
    steps = relationship("AutoGenerateStep", back_populates="job", lazy="selectin",
                         cascade="all, delete-orphan", order_by="AutoGenerateStep.step_order")


class AutoGenerateStep(Base):
    """One step of an auto-generate job. result_summary holds small JSON
    (counts, names, and — for step 1 — the episode outline list so step 4
    can materialize episodes even on retry)."""

    __tablename__ = "auto_generate_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auto_generate_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_key: Mapped[str] = mapped_column(String(50), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AutoGenerateStepStatus] = mapped_column(Enum(AutoGenerateStepStatus), default=AutoGenerateStepStatus.PENDING, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    job = relationship("AutoGenerateJob", back_populates="steps", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("job_id", "step_key", name="uq_job_step"),
        Index("ix_step_job_order", "job_id", "step_order"),
    )


# ---------------------------------------------------------------------------
# Future-dev round 2 (20 Nov 2026): billing, timeline, consistency, subtitles
# ---------------------------------------------------------------------------

class SubscriptionStatus(PyEnum):
    INACTIVE = "inactive"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class Subscription(Base):
    """Langganan user. Provider SELALU 'test' (mode sandbox) — Di tidak
    punya kartu kredit; tidak ada live key, tidak ada penagihan nyata."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.INACTIVE, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="test")
    provider_customer_id: Mapped[str] = mapped_column(String(255), nullable=True)
    provider_subscription_id: Mapped[str] = mapped_column(String(255), nullable=True)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", lazy="selectin")

    __table_args__ = (UniqueConstraint("user_id", name="uq_subscription_user"),)


class BillingEvent(Base):
    """Audit trail event billing (checkout, webhook, cancel). Payload JSON
    mentah — TIDAK PERNAH berisi nomor kartu / secret key."""

    __tablename__ = "billing_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class VideoTimeline(Base):
    """Timeline editing per episode: daftar clip (track) dalam JSON.
    Satu timeline per episode. Clip: {id, track, start, duration,
    prompt_id, scene_id, asset_id, label, transition}."""

    __tablename__ = "video_timelines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Main timeline")
    clips: Mapped[List[dict]] = mapped_column(JSON, nullable=False, default=list)
    duration_seconds: Mapped[float] = mapped_column(nullable=False, default=0.0)
    fps: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    resolution: Mapped[str] = mapped_column(String(20), nullable=False, default="1080x1920")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    episode = relationship("Episode", lazy="selectin")
    project = relationship("Project", lazy="selectin")

    __table_args__ = (UniqueConstraint("episode_id", name="uq_timeline_episode"),)


class ConsistencyCheckStatus(PyEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CharacterConsistencyCheck(Base):
    """Hasil cek konsistensi karakter antar episode. issues: list
    {character, episode_number, type, severity, description, suggestion}."""

    __tablename__ = "character_consistency_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[ConsistencyCheckStatus] = mapped_column(Enum(ConsistencyCheckStatus), default=ConsistencyCheckStatus.RUNNING, nullable=False)
    checked_episodes: Mapped[List[int]] = mapped_column(JSON, nullable=True)
    issues: Mapped[List[dict]] = mapped_column(JSON, nullable=True)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    project = relationship("Project", lazy="selectin")


class SubtitleJobStatus(PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SubtitleJob(Base):
    """Job subtitle dari file audio/video lokal. segments: list
    {start, end, text}. srt/vtt disimpan sebagai file di UPLOAD_DIR."""

    __tablename__ = "subtitle_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    source_path: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[SubtitleJobStatus] = mapped_column(Enum(SubtitleJobStatus), default=SubtitleJobStatus.PENDING, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="id")
    engine: Mapped[str] = mapped_column(String(50), nullable=True)
    model_size: Mapped[str] = mapped_column(String(20), nullable=False, default="tiny")
    segments: Mapped[List[dict]] = mapped_column(JSON, nullable=True)
    srt_path: Mapped[str] = mapped_column(String(500), nullable=True)
    vtt_path: Mapped[str] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    project = relationship("Project", lazy="selectin")
    episode = relationship("Episode", lazy="selectin")


class CollabRoomState(Base):
    """State kolaborasi persisten per proyek (audit ronde 2, P1-2).

    Versi edit kolaboratif disimpan di DB, bukan di memori proses, supaya
    tahan restart dan konsisten antar worker. Presence per user ada di
    CollabPresence. Broadcast WS live tetap per-worker (tanpa Redis);
    lihat app/services/collab.py.
    """

    __tablename__ = "collab_room_states"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", lazy="selectin")


class CollabPresence(Base):
    """Satu baris = satu user sedang online di room proyek.

    Ditulis saat WS join/set_field, dihapus saat disconnect. Baris yang
    updated_at-nya lebih tua dari PRESENCE_STALE_SECONDS dianggap basi
    (proses mati mendadak tanpa disconnect bersih) dan dibersihkan saat
    presence dibaca.
    """

    __tablename__ = "collab_presence"

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    field: Mapped[str] = mapped_column(String(255), nullable=True)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#22D3EE")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", lazy="selectin")
