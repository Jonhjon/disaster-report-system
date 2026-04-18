from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, chat, events, reports, monitor, webhooks
from app.config import settings

app = FastAPI(title="智慧災害通報系統 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(events.router, prefix="/api", tags=["Events"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(monitor.router, prefix="/api", tags=["Monitor"])
app.include_router(webhooks.router, prefix="/api", tags=["Webhooks"])
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root():
    return {"message": "智慧災害通報系統 API", "docs": "/docs"}
