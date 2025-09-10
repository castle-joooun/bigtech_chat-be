from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_databases, close_databases
from app.api.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_databases()
    yield
    # Shutdown
    await close_databases()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
