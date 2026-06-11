from scr.notification_app.router import note_router
from scr.notification_app.pref_router import pref_router
from scr.feature_flag_app.router import flag_router
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from typing import Annotated
from .database import get_session, async_engine
from .feature_flag_app.models import FeatureFlag
from sqlmodel.ext.asyncio.session import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        yield
    await async_engine.dispose()


app = FastAPI(title="Core Engine Panel", lifespan=lifespan)

app.include_router(note_router)
app.include_router(pref_router)
app.include_router(flag_router)


# Initialize Jinja2 templates directory target mapping
templates = Jinja2Templates(directory="scr/templates")


@app.get("/", response_class=HTMLResponse)
async def render_admin_dashboard(request: Request, db: Annotated[AsyncSession, Depends(get_session)]):
    # Pull flags out of the database to show their state on load
    statement = select(FeatureFlag)
    result = await db.exec(statement)
    flags_list = result.all()
 
    # Modern FastAPI TemplateResponse Syntax
    return templates.TemplateResponse(
        request,                    # 1. Pass request explicitly as a kwarg
        "dashboard.html",              # 2. Pass the template filename string
        {"flags": flags_list}       # 3. Pass your data template variables here
    )