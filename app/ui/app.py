from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pathlib

base = pathlib.Path(__file__).parent.resolve()

app = FastAPI(
    default_response_class=HTMLResponse,
)

app.mount("/static", StaticFiles(directory=base.joinpath('static')), name="static")

templates = Jinja2Templates(directory=base.joinpath('templates'), autoescape=False, auto_reload=True)

@app.get("/", name="home")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html.j2"
    )

# @app.get("/", name="banks")
# async def banks(request: Request):
#     return templates.TemplateResponse(
#         request=request, name="banks.html.j2"
#     )