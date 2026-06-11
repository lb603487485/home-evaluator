"""FastAPI app: CORS for the Vite dev server, dataset ensured on startup."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import get_runtime, router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_runtime()  # build comps.parquet + graph before first request
    yield


app = FastAPI(title="home-evaluator", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
