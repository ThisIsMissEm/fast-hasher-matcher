from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, status
from fastapi.responses import RedirectResponse

from .storage.database.connection import engine

from .settings import settings
from .routers import hashing, matching
from .ui import app as ui

@asynccontextmanager
async def lifespan(app: FastAPI):
  print(f"App Started {app.title}")
  yield
  engine.dispose()
  print("App stopped")

app = FastAPI(title="Fast Hasher Matcher", lifespan=lifespan)

if settings.role_hasher:
  app.include_router(
    hashing.router,
    prefix="/h"
  )

if settings.role_matcher:
  app.include_router(
    matching.router,
    prefix="/m"
  )

if settings.ui_enabled:
  app.mount("/ui", ui.app)

@app.get("/", response_class=RedirectResponse)
async def root():
  if settings.ui_enabled:
    return RedirectResponse('/ui')
  else:
    return RedirectResponse('/status')

@app.get("/status", status_code=status.HTTP_200_OK, responses={
  503: {"description": "The index is stale"},
})
def server_status(response: Response):
  """
  Liveness/readiness check endpoint for your favourite Layer 7 load balancer
  """
  if settings.role_matcher:
    # if matching.index_cache_is_stale():
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return "INDEX-STALE"

  # if app.config.get("ROLE_MATCHER", False):
  return "I-AM-ALIVE"
