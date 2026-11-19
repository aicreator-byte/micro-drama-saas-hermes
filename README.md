# Micro Drama SaaS - AI-Powered Micro Drama Production Platform

A full-stack SaaS platform for creating micro drama series from concept to final video production using AI-powered tools.

## Features

- **User Management**: Registration, authentication, multi-tenant isolation
- **Project Studio**: Create and manage multiple drama projects
- **Series Bible**: Define premise, plot, characters, world settings, tone, visual style
- **Character Studio**: Create up to 6 characters per project with detailed profiles
- **Location Studio**: Manage shooting locations with environment and lighting details
- **Story Engine**: AI-powered 20-episode series generation from premise
- **Scene Engine**: Break down episodes into scenes with shot lists and camera directions
- **Prompt Studio**: Generate structured AI prompts for images, video, audio
- **Episode Manager**: Track production status, costs, revisions, assets
- **Google Account Manager**: Connect up to 20 Google accounts per user for Flow integration
- **Flow Bridge**: Export prompts for Google Flow, import generated results
- **Asset Manager**: Upload and organize production assets (images, video, audio, subtitles)
- **Post-Production**: FFmpeg-based video assembly and subtitle burning

## Auto-Generate (title in → full series out)

Give only a title and the AI fills everything, step by step: **Series Bible → Characters → Locations → Episodes → Video Prompts** (1–50 episodes). Video itself is NOT generated — the prompts are used manually in Google Flow.

- **Async with live progress**: `POST /api/v1/projects/{id}/auto-generate` returns **202 Accepted** immediately and the job runs in the background; the modal polls `GET …/auto-generate/{job_id}` every 2s and shows per-step status plus a summary with real numbers (e.g. `created count: 5`). A failed step can be retried alone (`POST …/retry/{step_key}`).
- **Genre inference**: if you leave Genre empty, step 1 asks the LLM to guess it from the title (romance, drama, thriller, …). If the guess fails, the job honestly records genre `unknown` — it never silently defaults to "drama".
- **Prompt chunking**: video prompts are generated in chunks of 5 episodes per LLM call (max 4000 tokens each), with per-chunk coverage validation — a 30-episode job no longer risks truncation from a single 8000-token call.
- **Manual bible protection**: a Series Bible created/edited by hand (`source: "manual"`) is never overwritten by auto-generate; the LLM outline is still used to create the episodes. Auto-generated bibles are marked `source: "auto"`.
- **Transactional steps**: if a step fails halfway, its partial rows are rolled back — no half-written data recorded as success.
- **Job title ≠ project title**: the title you type is the job's title; the project is never renamed silently. Blank-only titles are rejected (422 backend + form validation).

## Google Accounts, fallback & browser login

- **Google Accounts**: up to 20 per user; credentials (OAuth client id/secret, account passwords) are stored encrypted in Settings / per account. The Google OAuth redirect URI is configurable via env `GOOGLE_OAUTH_REDIRECT_URI` (default `http://localhost:3000/dashboard/google-accounts/callback`) — see `backend/.env.example`.
- **Account fallback**: when an account fails (token refresh failed, Flow blocked, browser challenge), the next account is tried automatically; every attempt and its reason are recorded in `fallback_history`.
- **Browser login** (no Google Cloud Console needed): each account logs into Google in its own persistent browser profile (`browser-profiles/`), then Flow is used manually in that browser. Login state requires positive evidence (a logged-in marker on the page) — an account is never reported `logged_in` just because no sign-in form was found (fixed 19 Nov 2026, see `backend/tests/test_browser_login.py`).
- **Settings are admin-only**: `PATCH /api/v1/settings` returns 403 for non-admin users (AppSettings is one global row shared by all tenants); reading settings is allowed for any active user.

## Tech Stack

- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS, Zustand
- **Backend**: FastAPI, Python 3.11+, SQLAlchemy 2.0, PostgreSQL, Redis
- **Auth**: JWT tokens with bcrypt password hashing
- **Database Migrations**: Alembic
- **Video Processing**: FFmpeg
- **Containerization**: Docker, Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.11+ (for backend development)

### Using Docker Compose (Recommended)

1. Clone the repository and navigate to the project root:
   ```bash
   cd micro-drama-saas/hermes
   ```

2. Copy the environment example file:
   ```bash
   cp backend/.env.example backend/.env
   ```

3. Edit `backend/.env` with your configuration (especially `SECRET_KEY`)

4. Start all services:
   ```bash
   docker-compose up -d
   ```

5. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Local Development

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Run database migrations
alembic upgrade head

# Start development server (ALWAYS via start.sh — it cds to the
# backend dir first, so .env is found no matter where you run it from;
# the app reads .env relative to the backend directory, not the CWD)
./start.sh
# …or explicitly: PORT=8001 ./start.sh
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

## Project Structure

```
micro-drama-saas/hermes/
├── backend/
│   ├── app/
│   │   ├── api/           # API routes
│   │   ├── core/          # Config, security
│   │   ├── db/            # Database session
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   └── utils/         # Utilities (encryption)
│   ├── alembic/           # Database migrations
│   ├── tests/             # Pytest tests
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js App Router pages
│   │   ├── components/    # React components
│   │   ├── lib/           # API client, stores
│   │   └── types/         # TypeScript types
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/me` - Get current user

### Projects
- `POST /api/v1/projects` - Create project
- `GET /api/v1/projects` - List projects
- `GET /api/v1/projects/{id}` - Get project
- `PATCH /api/v1/projects/{id}` - Update project
- `DELETE /api/v1/projects/{id}` - Delete project

### Series Bible
- `POST /api/v1/series-bible/{project_id}` - Create series bible
- `GET /api/v1/series-bible/{project_id}` - Get series bible
- `PATCH /api/v1/series-bible/{project_id}` - Update series bible

### Characters
- `POST /api/v1/characters/{project_id}` - Create character (max 6 per project)
- `GET /api/v1/characters/{project_id}` - List characters
- `PATCH /api/v1/characters/{project_id}/{character_id}` - Update character
- `DELETE /api/v1/characters/{project_id}/{character_id}` - Delete character
- `POST /api/v1/characters/{project_id}/reorder` - Reorder characters

### Locations
- `POST /api/v1/locations/{project_id}` - Create location
- `GET /api/v1/locations/{project_id}` - List locations
- `PATCH /api/v1/locations/{project_id}/{location_id}` - Update location
- `DELETE /api/v1/locations/{project_id}/{location_id}` - Delete location
- `POST /api/v1/locations/{project_id}/reorder` - Reorder locations

### Episodes
- `POST /api/v1/episodes/{project_id}` - Create episode
- `GET /api/v1/episodes/{project_id}` - List episodes
- `PATCH /api/v1/episodes/{project_id}/{episode_id}` - Update episode
- `DELETE /api/v1/episodes/{project_id}/{episode_id}` - Delete episode

### Scenes
- `POST /api/v1/scenes/{project_id}/episodes/{episode_id}` - Create scene
- `GET /api/v1/scenes/{project_id}/episodes/{episode_id}` - List scenes
- `PATCH /api/v1/scenes/{project_id}/episodes/{episode_id}/{scene_id}` - Update scene
- `DELETE /api/v1/scenes/{project_id}/episodes/{episode_id}/{scene_id}` - Delete scene

### Prompts
- `POST /api/v1/prompts/{project_id}` - Create prompt
- `GET /api/v1/prompts/{project_id}` - List prompts
- `POST /api/v1/prompts/generate` - Generate prompt with AI
- `POST /api/v1/prompts/{project_id}/episodes/{episode_id}/scenes/{scene_id}/generate-all` - Generate all scene prompts

### Auto-Generate
- `POST /api/v1/projects/{id}/auto-generate` - Start auto-generate job (202, async; body: `title`, `genre?`, `num_episodes`, `premise?`)
- `GET /api/v1/projects/{id}/auto-generate/{job_id}` - Poll job status + per-step progress
- `POST /api/v1/projects/{id}/auto-generate/{job_id}/retry/{step_key}` - Retry one failed step (409 while running)

### Settings
- `GET /api/v1/settings` - Get app settings (secrets masked)
- `PATCH /api/v1/settings` - Update settings (**admin only**, 403 otherwise)

### Google Accounts
- `POST /api/v1/google-accounts` - Connect Google account (max 20 per user)
- `GET /api/v1/google-accounts` - List accounts
- `PATCH /api/v1/google-accounts/{id}` - Update account
- `DELETE /api/v1/google-accounts/{id}` - Disconnect account
- `POST /api/v1/google-accounts/{id}/sync` - Sync account session

### Flow Bridge
- `POST /api/v1/flow/{project_id}/tasks` - Create flow task
- `GET /api/v1/flow/{project_id}/tasks` - List tasks
- `POST /api/v1/flow/{project_id}/export-prompts` - Export prompts for Flow
- `POST /api/v1/flow/{project_id}/import-results` - Import Flow results

### Assets
- `POST /api/v1/assets/{project_id}/upload` - Upload asset
- `GET /api/v1/assets/{project_id}` - List assets
- `POST /api/v1/assets/{project_id}/episodes/{episode_id}/assemble` - Assemble episode video
- `POST /api/v1/assets/{project_id}/episodes/{episode_id}/add-subtitles` - Add subtitles to video

### Story Engine
- `POST /api/v1/story-engine/{project_id}/generate-series` - Generate series outline
- `POST /api/v1/story-engine/{project_id}/episodes/{episode_id}/breakdown` - Break down episode into scenes

## Multi-Tenant Security

- All data is isolated by user ownership
- Every API endpoint verifies project ownership
- Google accounts are user-scoped (max 20 per user)
- Session data is encrypted at rest
- Audit logs track sensitive operations

## Testing

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

## Deployment

### Production Considerations

1. **Change SECRET_KEY** - Generate a strong random key
2. **Use PostgreSQL** - Configure production DATABASE_URL
3. **Use Redis** - Configure production REDIS_URL
4. **Set DEBUG=false** - Disable debug mode
5. **Configure CORS** - Set BACKEND_CORS_ORIGINS to your domain
6. **Use HTTPS** - Configure reverse proxy with SSL
7. **Set up monitoring** - Add logging, metrics, health checks

### Docker Production Build

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Known Limitations

1. **Video Generation** — prompts are generated, but video is produced manually in Google Flow; there is no automated video generation or Flow submission from this app.
2. **Google login is not verified end-to-end with a real account** — the fallback mechanism is tested with test accounts (browser reaches Google's real sign-in form, Google asks for verification / bot detection); a real login + real Flow video run have not been done from this VM.
3. **No live per-step progress on very slow LLM calls** — the job polls fine, but a single LLM call can take minutes when the provider is slow (live smoke 19 Nov: a 1-episode job took ~7 min total).
4. **Real-time Collaboration** - Not implemented
5. **Payment/Billing** - Not implemented

## Future Improvements (not yet done)

1. ~~Integrate actual LLM APIs~~ — done (Nvidia NIM via Settings + `NVIDIA_API_KEY` env fallback)
2. ~~Add browser automation for Google Flow~~ — done for login (persistent browser profiles + fallback); Flow video submission itself stays manual
3. Implement real-time collaboration
4. Add payment integration
5. Mobile app (React Native)
6. Advanced video editing timeline
7. AI-powered character consistency checking
8. Automated subtitle generation (Whisper)

See `FUTURE-DEV-REPORT.md` for what was implemented on 19 Nov 2026 (async auto-generate, genre inference, prompt chunking, manual-bible protection, admin-only Settings, env-based redirect URI, CWD-independent `.env`) and what is still NOT VERIFIED.

## License

Proprietary - All rights reserved.