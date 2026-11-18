from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.db.session import init_db
from app.api import (
    auth, projects, series_bible, characters, locations,
    episodes, scenes, prompts, google_accounts, flow_bridge,
    assets, story_engine, settings as settings_api
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered Micro Drama Production SaaS Platform",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
app.include_router(series_bible.router, prefix=settings.API_V1_PREFIX)
app.include_router(characters.router, prefix=settings.API_V1_PREFIX)
app.include_router(locations.router, prefix=settings.API_V1_PREFIX)
app.include_router(episodes.router, prefix=settings.API_V1_PREFIX)
app.include_router(scenes.router, prefix=settings.API_V1_PREFIX)
app.include_router(prompts.router, prefix=settings.API_V1_PREFIX)
app.include_router(google_accounts.router, prefix=settings.API_V1_PREFIX)
app.include_router(flow_bridge.router, prefix=settings.API_V1_PREFIX)
app.include_router(assets.router, prefix=settings.API_V1_PREFIX)
app.include_router(story_engine.router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_api.router, prefix=settings.API_V1_PREFIX)


# Malformed UUIDs / values in path or body -> 400, not 500.
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": f"Invalid value: {exc}"})


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}