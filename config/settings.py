from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    # Camera
    camera_url: str = Field(..., env="CAMERA_URL")
    stream_width: int = Field(1280, env="STREAM_WIDTH")
    stream_height: int = Field(720, env="STREAM_HEIGHT")
    stream_fps: int = Field(15, env="STREAM_FPS")

    # AI Engine
    yolo_model: str = Field("yolov8n.pt", env="YOLO_MODEL")
    face_model: str = Field("ArcFace", env="FACE_MODEL")
    confidence_threshold: float = Field(0.60, env="CONFIDENCE_THRESHOLD")
    person_confirm_seconds: float = Field(1.0, env="PERSON_CONFIRM_SECONDS")
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