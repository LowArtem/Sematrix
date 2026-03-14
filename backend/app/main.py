from fastapi import FastAPI


app = FastAPI(title="Sematrix API")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"service": "sematrix-backend"}


@app.get("/api/health")
def read_health() -> dict[str, str]:
    return {"status": "ok"}
