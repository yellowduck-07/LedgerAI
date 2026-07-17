# from pathlib import Path

# from fastapi import FastAPI
# from fastapi.responses import FileResponse
# from fastapi.staticfiles import StaticFiles

# from app.database import Base, engine
# from app.routers import invoices, transactions, matches, dashboard, chat, actions

# app = FastAPI()

# STATIC_DIR = Path(__file__).parent / "static"

# # create DB tables on startup
# Base.metadata.create_all(bind=engine)


# @app.get("/api/health")
# def health():
#     return {"status": "ok"}


# # --- feature routers, all under /api ---
# app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
# app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
# app.include_router(matches.router, prefix="/api/matches", tags=["matches"])
# app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
# app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
# app.include_router(actions.router, prefix="/api/actions", tags=["actions"])


# @app.get("/")
# def index():
#     return FileResponse(STATIC_DIR / "index.html")


# app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


