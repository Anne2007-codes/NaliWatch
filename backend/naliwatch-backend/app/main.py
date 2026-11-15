from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
