import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, chat, events, health, notifications, reports, monitor
from app.config import settings


def _configure_logging() -> None:
    """統一配置 root logger。

    `force=True` 確保即使 uvicorn / pytest 已預設 handler，也會被本 app 的格式覆蓋，
    讓生產環境 log 走一致 format，方便 ELK / CloudWatch 解析。
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )


_configure_logging()


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
app.include_router(notifications.router, prefix="/api", tags=["Notifications"])
# Health/readiness 刻意不掛 /api prefix：K8s / docker-compose probe 傳統路徑慣例。
app.include_router(health.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root():
    return {"message": "智慧災害通報系統 API", "docs": "/docs"}
