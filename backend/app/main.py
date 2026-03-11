from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import chat, events, reports, monitor

app = FastAPI(title="智慧災害通報系統 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(events.router, prefix="/api", tags=["Events"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(monitor.router, prefix="/api", tags=["Monitor"])
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root():
    return {"message": "智慧災害通報系統 API", "docs": "/docs"}
