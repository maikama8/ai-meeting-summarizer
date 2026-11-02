"""
AI Meeting Summarizer - Scaffold
Simple FastAPI entry point.
"""

from fastapi import FastAPI, UploadFile, File
from typing import Optional

app = FastAPI(title="AI Meeting Summarizer")

@app.get("/")
def root():
    return {"message": "AI Meeting Summarizer API - Scaffold ready"}

@app.post("/summarize")
async def summarize(audio: UploadFile = File(...), language: Optional[str] = "en"):
    # TODO: Implement transcription + summarization
    return {
        "filename": audio.filename,
        "status": "scaffold",
        "summary": "This is a placeholder. Implement Whisper + LLM logic here."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
