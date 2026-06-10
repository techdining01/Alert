from fastapi import FastAPI
from scr.notification_app.router import note_router
from scr.notification_app.preference import pref_router


app = FastAPI()

app.include_router(note_router)
app.include_router(pref_router)
