from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import redis
import httpx
import os
import json
from datetime import datetime

DataBase_Url = os.getenv("DataBase_Url", "postgresql://arge_user:arge_pass@postgres:5432/telemetry_db")
Redis_Host = os.getenv("Redis_Host", "redis")
Service_Url = os.getenv("Service_Url", "http://anomaly_service:8001/predict")

# PostgreSQL ORM connection engine
engine = create_engine(DataBase_Url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

redis_client = redis.Redis(host=Redis_Host, port=6379, db=0, decode_responses=True)

# Crate SQL Table
class TelemetryRecord(Base):
    __tablename__ = "telemetry_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True) # Device Name
    temperature = Column(Float)
    vibration = Column(Float)
    pressure = Column(Float)
    voltage = Column(Float)
    anomaly_score = Column(Float)
    is_anomaly = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create table when app started
Base.metadata.create_all(bind=engine)

# Data validation
class TelemetryPayload(BaseModel):
    device_id: str = Field(..., example="TAI-ANKA-01")
    temperature: float = Field(..., ge=-50.0, le=300.0)
    vibration: float = Field(..., ge=0.0, le=500.0)
    pressure: float = Field(..., ge=0.0, le=100.0)
    voltage: float = Field(..., ge=0.0, le=50.0)

app = FastAPI(title="Ar-Ge Telemetry Service")

# Session func
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/v1/telemetry")
async def ingest_telemetry(payload: TelemetryPayload, db: Session = Depends(get_db)):

    # Connect service and check anomaly
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                Service_Url,
                json={
                    "temperature": payload.temperature,
                    "vibration": payload.vibration,
                    "pressure": payload.pressure,
                    "voltage": payload.voltage
                },
                timeout=10.0
            )
            data = resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Service Error: {repr(e)}")

    anomaly_score = data["anomaly_score"]
    is_anomaly = data["is_anomaly"]

    # Write redis newest data
    cache_data = {
        "device_id": payload.device_id,
        "temperature": payload.temperature,
        "vibration": payload.vibration,
        "anomaly_score": anomaly_score,
        "is_anomaly": is_anomaly,
        "updated_at": datetime.utcnow().isoformat()
    }
    redis_client.setex(f"latest:{payload.device_id}", 60, json.dumps(cache_data))


    new_record = TelemetryRecord(
        device_id=payload.device_id,
        temperature=payload.temperature,
        vibration=payload.vibration,
        pressure=payload.pressure,
        voltage=payload.voltage,
        anomaly_score=anomaly_score,
        is_anomaly=is_anomaly
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return {
        "status": "saved",
        "record_id": new_record.id,
        "anomaly_score": anomaly_score,
        "is_anomaly": is_anomaly
    }


# Endpoint for reading current state from Redis
@app.get("/api/v1/telemetry/latest/{device_id}")
def get_latest_status(device_id: str):
    cached = redis_client.get(f"latest:{device_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Can't find data last 60 second.")
    return json.loads(cached)


@app.get("/api/v1/telemetry/anomalies")
def get_recent_anomalies(db: Session = Depends(get_db)):
    # Return last 10 is_anomaly = True datas
    anomalies = (
        db.query(TelemetryRecord)
        .filter(TelemetryRecord.is_anomaly == True)
        .order_by(TelemetryRecord.timestamp.desc())
        .limit(10)
        .all()
    )
    return {"total_found": len(anomalies), "records": anomalies}