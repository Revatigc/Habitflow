from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router

app = FastAPI(title="HabitFlow API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])
app.include_router(router, prefix="/api")

@app.get("/health")
def health(): return {"status": "ok"}
