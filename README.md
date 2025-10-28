# QEMU Network Lab

A web-based network lab environment for running and managing multiple QEMU-based Alpine Linux VMs, with browser-based terminal access via Apache Guacamole. Includes a Python FastAPI backend, a React frontend, and Dockerized infrastructure for easy setup.

## Features
- Launch and manage multiple isolated Alpine Linux VMs (nodes) using QEMU and overlay images
- Web-based terminal access to each node via Guacamole (no SSH or VNC client needed)
- Add, start, stop, wipe, and delete nodes from the web UI
- Supports running multiple terminals simultaneously without session conflicts
- Persistent node state using SQLite and overlay images

## Architecture
- **Backend:** Python FastAPI (REST API), SQLAlchemy, QEMU process management, Guacamole API integration
- **Frontend:** React (Node.js), connects to backend API
- **Guacamole:** Provides browser-based terminal access to each node
- **Database:** SQLite (for node state)
- **Docker Compose:** Orchestrates Guacamole, PostgreSQL, and guacd services

## Folder Structure
```
network-lab/
├── backend/         # FastAPI backend, QEMU logic, Guacamole API
├── frontend/        # React frontend (Node.js)
├── images/          # Base VM images (.qcow2)
├── overlays/        # Per-node overlay images
├── docker-compose.yml
├── initdb.sql       # Guacamole DB schema
└── .gitignore
```

## Prerequisites
- Python 3.8+
- Node.js 16+
- QEMU (with qemu-img and qemu-system-x86_64 in PATH)
- Docker & Docker Compose
- Windows (tested) or Linux

## Setup Instructions

### 1. Clone the repository
```
git clone <repo-url>
cd network-lab
```

### 2. Start Guacamole and Database
```
docker-compose up -d
```
- Guacamole web: http://localhost:8080/guacamole
- Default login: `guacadmin` / `guacadmin`

### 3. Backend Setup
```
cd backend
pip install -r requirements.txt  # (create if missing)
python main.py
```
- Backend API: http://localhost:8000

### 4. Frontend Setup
```
cd frontend
npm install
npm start
```
- Frontend: http://localhost:3000

### 5. Using the Lab
- Open http://localhost:3000 in your browser
- Add nodes, start/stop/wipe/delete them
- Click "Open" to launch a terminal for each node (multiple terminals supported)

## Notes
- Each node is an Alpine Linux 3.22 VM (customizable via `images/base.qcow2`)
- Overlay images are created per node in `overlays/`
- Backend creates a unique Guacamole user per terminal session to avoid session conflicts
- For production, secure the backend and Guacamole admin credentials

## Troubleshooting
- Ensure QEMU and Docker are installed and in your PATH
- If terminals don't open, check backend logs and Guacamole container logs
- For VM login, use the credentials set in your base image (default Alpine: `root` with password you set)

## License
MIT License

---
Contributions welcome!