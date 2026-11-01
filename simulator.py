import httpx
import random
import time
import json

Ingestion_Url = "http://localhost:8000/api/v1/telemetry"
Anomalies_Url = "http://localhost:8000/api/v1/telemetry/anomalies"
Latest_Url = "http://localhost:8000/api/v1/telemetry/latest/TAI-ANKA-02"

devices = ["BAYKAR-AKINCI-01", "TAI-ANKA-02", "ASELSAN-RADAR-03"]

print("Simulation Is Starting")

for i in range(15):
    device = random.choice(devices)
    
    # Create normal data 80% chance, create anomaly data 20% chance
    if random.random() < 0.80:
        payload = { # Normal
            "device_id": device,
            "temperature": round(random.uniform(72.0, 78.0), 2),
            "vibration": round(random.uniform(18.0, 22.0), 2),
            "pressure": round(random.uniform(9.5, 10.5), 2),
            "voltage": round(random.uniform(23.8, 24.2), 2)
        }
    else:
        payload = { # Anomaly
            "device_id": device,
            "temperature": round(random.uniform(95.0, 115.0), 2),
            "vibration": round(random.uniform(45.0, 65.0), 2),
            "pressure": round(random.uniform(14.0, 18.0), 2),
            "voltage": round(random.uniform(19.0, 21.0), 2)
        }

    # Send data to ingestion service
    response = httpx.post(Ingestion_Url, json=payload)
    res_data = response.json()
    
    # --- EKLENEN KONTROL: Sunucu hata verirse çökme, hatayı ekrana yaz! ---
    if response.status_code != 200:
        print(f"\n[!] SUNUCU HATASI (Kod: {response.status_code}):")
        print(res_data)
        break
    # ----------------------------------------------------------------------

    status = "Anomaly Detect" if res_data["is_anomaly"] else "Normal"
    print(f"[{i+1}/15] Device: {device} | Temperature: {payload['temperature']}°C | Score: {res_data['anomaly_score']} -> {status}")
    time.sleep(0.3)

print("\nLatest Status From Redis")
latest_resp = httpx.get(Latest_Url)
print(json.dumps(latest_resp.json(), indent=2, ensure_ascii=False))

print("\nRecent Anomalies From PostgreSQL")
anomaly_resp = httpx.get(Anomalies_Url)
print(json.dumps(anomaly_resp.json(), indent=2, ensure_ascii=False))