"""FastAPI app: serves the web page and the patient records API.

Run:  python -m uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR
from app.database import Base, engine
from app.errors import register_error_handlers
from app.routers import patients

STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # create the table on first run
    yield


app = FastAPI(title="Health Prediction App", version="1.0.0", lifespan=lifespan)
register_error_handlers(app)
app.include_router(patients.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
