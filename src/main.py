from pydantic import BaseModel
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from pathlib import Path

from db import DatabaseManager

# ==================== Application Setup ====================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    global db_manager
    # Startup
    db_manager = DatabaseManager(settings.db_path)
    print(f"📦 Database initialized at {settings.db_path}")
    yield
    # Shutdown
    if db_manager:
        db_manager.close()
    print("👋 Application shutdown complete")
    
    
class Settings(BaseModel):
    """Application settings"""
    app_name: str = "Anime.js FastAPI App"
    version: str = "1.0.0"
    db_path: str = "data/db.json"
    template_dir: str = "templates"
    static_dir: str = "static"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

settings = Settings()


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan
)

# Setup static files and templates
static_path = Path(settings.static_dir)
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

templates_path = Path(settings.template_dir)
templates_path.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=settings.template_dir)

# ==================== API Routes ====================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render home page with anime.js demo"""
    return templates.TemplateResponse(
        "demo.html",
        {"request": request, "title": settings.app_name}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )