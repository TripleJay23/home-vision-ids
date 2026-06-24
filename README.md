# 🏠 Home Vision IDS

An AI-powered home surveillance and intrusion detection system using pre-trained deep learning models.

## Overview

Home Vision IDS monitors a home environment in real time, detecting people, pets, and objects using **YOLOv8n**, identifying known household members via **DeepFace (ArcFace)**, and alerting the admin via push notification with a cropped snapshot when an unrecognized person is detected.

## Architecture

```
Camera Hub (Pixel 4a)
    ↓ MJPEG stream
Python Vision Engine (FastAPI)
    ├── YOLOv8n — object detection
    └── DeepFace — face recognition
         ├── Known member → log quietly
         └── Unknown person → crop → Firebase → FCM → Flutter app
```

## Tech Stack

| Layer | Technology |
|---|---|
| Detection | YOLOv8n (Ultralytics) |
| Recognition | DeepFace (ArcFace backend) |
| Backend | FastAPI + Uvicorn |
| Camera | IP Webcam (Pixel 4a) |
| Cloud alerts | Firebase Storage + FCM |
| Mobile app | Flutter |

## Quick Start

```bash
# 1. Clone and enter project
cd C:\Users\jtrip\Desktop\Projects\home-vision-ids

# 2. Run setup (Windows CMD)
setup.bat

# 3. Fill in your .env values
# Edit .env with your CAMERA_URL and Firebase config

# 4. Start the API
python -m api.main
```

## Project Structure

```
home-vision-ids/
├── engine/              # AI vision engine
│   ├── core/            # Detector, recognizer, alert logic
│   ├── models/          # Pre-trained model files (.pt, .onnx)
│   └── utils/           # Frame helpers, image utils
├── api/                 # FastAPI backend
│   ├── routes/          # Endpoints: /stream, /alerts, /members
│   ├── services/        # Business logic
│   └── schemas/         # Pydantic request/response models
├── scripts/             # Admin CLI scripts (face registration etc.)
├── data/
│   ├── faces/           # Registered member photos (NOT committed)
│   ├── embeddings/      # Face embedding cache (NOT committed)
│   └── logs/            # System logs
├── config/              # Settings and credentials
├── tests/               # Unit and integration tests
├── docs/                # Documentation and diagrams
├── .env.example         # Environment variable template
├── requirements.txt     # Python dependencies
└── setup.bat            # One-click Windows setup script
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
CAMERA_URL=http://192.168.x.x:8080/video
FIREBASE_CREDENTIALS_PATH=config/firebase-credentials.json
FIREBASE_STORAGE_BUCKET=your-app.appspot.com
API_SECRET_KEY=your-strong-secret-key
```

## Development Phases

- [x] Phase 0 — Project setup
- [x] Phase 1 — Vision engine (YOLOv8n + DeepFace)
- [ ] Phase 2 — Backend & Firebase connectivity
- [ ] Phase 3 — Flutter mobile app
- [ ] Phase 4 — Integration testing
- [ ] Phase 5 — Documentation & report

## License

MIT — free to use, modify, and commercialise.