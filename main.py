from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(override=True)

from middleware.auth import AuthMiddleware
from routers import ai, auth, admin, stocks, payments
from services.api_keys import init_db

app = FastAPI(
    title="주식 AI 분석 API",
    description="한국 주식(KOSPI/KOSDAQ) + Claude AI 분석 서비스",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(ai.router)
app.include_router(payments.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    init_db()


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0", "service": "stock-ai"}


@app.get("/")
def index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "주식 AI 분석 API", "docs": "/docs"}


@app.get("/demo.html")
def demo():
    demo_file = static_dir / "demo.html"
    if demo_file.exists():
        return FileResponse(str(demo_file))
    return {"detail": "Not Found"}


@app.get("/dashboard")
def dashboard():
    dashboard_file = static_dir / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(str(dashboard_file))
    return {"detail": "Not Found"}


@app.get("/terms")
def terms():
    terms_file = static_dir / "terms.html"
    if terms_file.exists():
        return FileResponse(str(terms_file))
    return {"detail": "Not Found"}


@app.get("/privacy")
def privacy():
    privacy_file = static_dir / "privacy.html"
    if privacy_file.exists():
        return FileResponse(str(privacy_file))
    return {"detail": "Not Found"}
