from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from config.settings import settings
from api.services.pipeline import build_pipeline, get_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info("Home Vision IDS starting up...")
    logger.info(f"Camera URL: {settings.camera_url}")
    logger.info(f"API running at http://{settings.api_host}:{settings.api_port}")
    logger.info("Docs available at http://localhost:8000/docs")

    # Build the pipeline once (loads YOLO + recognizer models a single time)
    # and start the background loop. A missing/unreachable camera must NOT stop
    # the API from coming up — log it and let /stream report 503 until it's back.
    pipeline = build_pipeline()
    try:
        pipeline.start()
    except Exception as e:
        logger.error(f"Vision pipeline failed to start (camera unavailable?): {e}")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("Home Vision IDS shutting down.")
    p = get_pipeline()
    if p is not None:
        p.stop()


app = FastAPI(
    title="Home Vision IDS",
    description="AI-powered home surveillance and intrusion detection system.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────
# Every data route requires a valid X-API-Key header (see api/security.py).
from fastapi import Depends
from api.security import require_api_key
from api.routes import stream, alerts, members, devices

_auth = [Depends(require_api_key)]
app.include_router(stream.router, prefix="/stream", tags=["Stream"], dependencies=_auth)
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"], dependencies=_auth)
app.include_router(members.router, prefix="/members", tags=["Members"], dependencies=_auth)
app.include_router(devices.router, prefix="/devices", tags=["Devices"], dependencies=_auth)


@app.get("/", tags=["System"])
async def root():
    return {"message": "Home Vision IDS is running", "docs": "/docs"}


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "online",
        "version": "0.1.0",
        "camera": settings.camera_url,
    }


if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )