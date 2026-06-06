from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from routers import students, knowledge, mistakes, analysis, export

app = FastAPI(title="错题分析系统", version="1.0.0")

app.include_router(students.router)
app.include_router(knowledge.router)
app.include_router(mistakes.router)
app.include_router(analysis.router)
app.include_router(export.router)

static_path = Path("static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "错题分析系统 API"}


@app.get("/health")
async def health():
    return {"status": "ok"}
