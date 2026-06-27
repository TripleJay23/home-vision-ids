# 🏠 Home Vision IDS

AI home intrusion detection: a phone camera + on-device computer vision that recognises household members and pushes a phone alert (with a snapshot) when an **unknown** person appears.

## How it works

```
IP Webcam (phone) ──MJPEG──▶ FastAPI backend
                              ├─ YOLOv8n + ByteTrack   detect + track people
                              ├─ DeepFace / ArcFace     recognise known faces
                              └─ unknown person ──▶ snapshot + Firebase FCM push
                                                          │
                       Flutter app ◀── live stream · alerts · members ──┘
```

Face data stays on-device; only push notifications go through Firebase.

## Stack

| Layer | Tech |
|---|---|
| Detection / tracking | YOLOv8n + ByteTrack (Ultralytics) |
| Face recognition | DeepFace (ArcFace + YuNet) |
| Backend | FastAPI + Uvicorn (Python 3.11+) |
| Camera | IP Webcam app → MJPEG |
| Push | Firebase Cloud Messaging |
| Mobile | Flutter + Riverpod |

## Quick start

```bash
# Backend
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env                             # set CAMERA_URL
python -m api.main                                 # http://localhost:8000/docs

# App
cd app && flutter pub get && flutter run           # set the backend URL in Settings
```

Run the **IP Webcam** app on a phone pointed at the room, put its `http://<ip>:8080/video` URL in `CAMERA_URL`, start the backend, then enroll members from the app (Members → Enroll) or the CLI (`scripts/enroll_face.py`).

## Features

- Real-time person detection + multi-person tracking
- Face recognition with margin-checking and temporal-consistency voting (resists single-frame false matches)
- Unknown-person alerts → push notification with a snapshot, anywhere (FCM)
- Live MJPEG view, alert history, and member roster in the app
- In-app member enrollment from the phone camera
- Optional remote access via an ngrok tunnel

## Structure

```
engine/   AI engine: detector, recognizer, face DB, track state, alerter, enrollment
api/      FastAPI app + routes (/stream /alerts /members /devices) + pipeline service
app/      Flutter mobile app
scripts/  CLI tools (enrollment, live/static recognition tests)
config/   Pydantic settings + ByteTrack config
docs/     development_journal.md — full build-from-scratch guide
```

## Status

Functional prototype — engine, API, app, push, remote access, accuracy mitigation, and in-app enrollment all working. Recognition is bounded by consumer-camera image quality (documented in `docs/development_journal.md`); mitigated by vote-smoothing and an alert-on-stranger bias.

## License

MIT.
