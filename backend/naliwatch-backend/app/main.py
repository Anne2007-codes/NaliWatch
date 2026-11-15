from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import admin, auth, bot, dev, flags, health, jobs, map, metrics, plant, reports, tanks, trips, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:
        init_db()
    yield


app = FastAPI(title="NaliWatch API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for r in (auth, tanks, reports, health, jobs, trips, plant, flags, admin, map, metrics, bot, ws, dev):
    app.include_router(r.router)


@app.get("/healthz", tags=["meta"])
def healthz():
    return {"ok": True}


# Find the frontend folder by walking up the directory tree.
# Works on the laptop (NaliWatch/frontend) and in Docker (no frontend -> skipped).
_frontend = None
for _p in Path(__file__).resolve().parents:
    if (_p / "frontend").is_dir():
        _frontend = _p / "frontend"
        break

if _frontend is not None:
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")