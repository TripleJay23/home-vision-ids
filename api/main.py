from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from config.settings import settings

app = FastAPI(
    title="Home Vision IDS",
    description="AI-powered home surveillance and intrusion detection system.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes (import as they are built) ────────────────────────
# from api.routes import stream, alerts, members
# app.include_router(stream.router, prefix="/stream", tags=["Stream"])
# app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
# app.include_router(members.router, prefix="/members", tags=["Members"])


@app.on_event("startup")
async def startup():
    logger.info("Home Vision IDS starting up...")
    logger.info(f"Camera URL: {settings.camera_url}")
    logger.info(f"API running at http://{settings.api_host}:{settings.api_port}")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Home Vision IDS shutting down.")


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