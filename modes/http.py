from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
from core.align import align_audio
import os
import uvicorn

app = FastAPI()

ALIGN_SECRET_KEY = os.environ.get("ALIGN_SECRET_KEY")

def verify_secret_key(Authorization: Optional[str] = Header(None)):
    if ALIGN_SECRET_KEY:
        if not Authorization or Authorization != ALIGN_SECRET_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing secret key.")
    return None

class AlignRequest(BaseModel):
    mp3_url: str
    text: str
    language: str = "ar"
    romanize: Optional[bool] = True
    batch_size: Optional[int] = 4


@app.post("/align")
def align(request: AlignRequest, _: Optional[str] = Depends(verify_secret_key)):
    return align_audio(
        request.mp3_url,
        request.text,
        batch_size = request.batch_size or 4,
        romanize = request.romanize or True,
        language = request.language or "ar"
    )

def start_http_server(host: str, port: int):
    reload = os.environ.get("RELOAD", "false").lower() == "true"
    uvicorn.run("modes.http:app", host=host, port=port, reload=reload)