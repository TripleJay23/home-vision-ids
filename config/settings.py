from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    # Camera
    camera_url: str = Field(..., env="CAMERA_URL")
    stream_width: int = Field(1280, env="STREAM_WIDTH")
    stream_height: int = Field(720, env="STREAM_HEIGHT")
    stream_fps: int = Field(15, env="STREAM_FPS")
    # Seconds without a fresh camera frame before the feed is treated as lost:
    # the reader invalidates its last frame and the pipeline publishes a
    # "signal lost" placeholder instead of freezing on the last good frame.
    camera_stale_seconds: float = Field(2.0, env="CAMERA_STALE_SECONDS")
    # JPEG quality (1-100) for the annotated /stream. Lower = smaller frames =
    # less encode/transport/decode → a smoother preview on the phone.
    stream_jpeg_quality: int = Field(60, env="STREAM_JPEG_QUALITY")

    # AI Engine
    yolo_model: str = Field("yolov8s.pt", env="YOLO_MODEL")
    face_model: str = Field("ArcFace", env="FACE_MODEL")
    # DeepFace detector backend used for BOTH enrollment and runtime (must match,
    # or embeddings won't be comparable). "retinaface" aligns faces far better
    # than "yunet" → tighter embeddings; slower per call, but recognition runs
    # off the hot path (threaded + deferred). Re-enroll after changing this.
    face_detector_backend: str = Field("retinaface", env="FACE_DETECTOR_BACKEND")
    confidence_threshold: float = Field(0.60, env="CONFIDENCE_THRESHOLD")
    person_confirm_seconds: float = Field(1.0, env="PERSON_CONFIRM_SECONDS")
    vote_window: int = Field(3, env="VOTE_WINDOW")
    vote_min_agree: int = Field(2, env="VOTE_MIN_AGREE")
    alert_cooldown_seconds: int = Field(60, env="ALERT_COOLDOWN_SECONDS")
    # Minimum person bbox height (px) before attempting face recognition.
    # Below this the face is too small to recognise reliably. Tune to the room:
    # LOWER = recognises people further away (top-corner placement) but with less
    # reliable embeddings; RAISE if distant faces produce bad matches. At 720p.
    min_person_box_height: int = Field(120, env="MIN_PERSON_BOX_HEIGHT")

    # Paths
    faces_db_path: Path = Field(Path("data/faces"), env="FACES_DB_PATH")
    embeddings_path: Path = Field(Path("data/embeddings"), env="EMBEDDINGS_PATH")
    models_path: Path = Field(Path("engine/models"), env="MODELS_PATH")
    logs_path: Path = Field(Path("data/logs"), env="LOGS_PATH")
    alerts_path: Path = Field(Path("data/alerts"), env="ALERTS_PATH")
    # SQLite database of alert records, so alert history survives a restart.
    alerts_db_path: Path = Field(Path("data/alerts.db"), env="ALERTS_DB_PATH")

    # Firebase
    firebase_credentials_path: Path = Field(..., env="FIREBASE_CREDENTIALS_PATH")
    firebase_storage_bucket: str = Field(..., env="FIREBASE_STORAGE_BUCKET")
    fcm_tokens_path: Path = Field(Path("data/fcm_tokens.json"), env="FCM_TOKENS_PATH")

    # API
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    api_secret_key: str = Field(..., env="API_SECRET_KEY")

    # Relay
    relay_enabled: bool = Field(False, env="RELAY_ENABLED")
    relay_url: str = Field("", env="RELAY_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()