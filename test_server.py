from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

@app.get("/health")
def health():
    print("HEALTH HIT")
    return {
        "ok": True,
        "message": "test server working",
        "time": datetime.utcnow().isoformat() + "Z",
    }

@app.post("/worker/register")
def register_worker():
    print("REGISTER HIT")
    return {
        "ok": True,
        "worker_id": "test_worker",
    }