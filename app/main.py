from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.models import Invoice, Transaction
from app.routers import actions, chat, dashboard, invoices, matches, transactions

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="LedgerAI Virtual CA", lifespan=lifespan)

app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(matches.router, prefix="/api/matches", tags=["matches"])
app.include_router(actions.router, prefix="/api/actions", tags=["actions"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])


@app.get("/api/health")
def health():
    from app.config import GEMINI_API_KEY

    return {
        "status": "ok",
        "ocr_ready": bool(GEMINI_API_KEY),
    }


@app.get("/api/status")
def app_status(db: Session = Depends(get_db)):
    from app.services.data_loader import get_data_status

    return get_data_status(db)


@app.post("/api/reset")
def reset_database(db: Session = Depends(get_db)):
    db.query(Transaction).delete()
    db.query(Invoice).delete()
    db.commit()
    return {"reset": True}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
