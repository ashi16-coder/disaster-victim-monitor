from fastapi import FastAPI

app = FastAPI(title="Disaster Victim Monitor")


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Service is healthy"}
