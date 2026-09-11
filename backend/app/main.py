from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import dialogs, issues, overview

settings = get_settings()

app = FastAPI(title="DQA Monitoring API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(overview.router)
app.include_router(issues.router)
app.include_router(dialogs.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "mock_data": settings.use_mock_data, "project": settings.gcp_project_id}
