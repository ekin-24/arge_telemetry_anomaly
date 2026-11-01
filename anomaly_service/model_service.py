from fastapi import FastAPI
from pydantic import BaseModel
import torch
import torch.nn as nn
import numpy as np

app = FastAPI(title="Ar-Ge Anomaly Service")

class Autoencoder(nn.Module):
    def __init__(self, input_dim: int = 4):
        super(Autoencoder, self).__init__()
        
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 8), # İnput layer 4 to 8
            nn.ReLU(), 
            nn.Linear(8, 2), # Output layer 8 to  2
            nn.ReLU()
        )
        
        self.decoder = nn.Sequential(
            nn.Linear(2, 8), # Input layer 2 to 8
            nn.ReLU(),
            nn.Linear(8, input_dim) # Output layer 8 to 4
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded

# Create model and turn mode to test
model = Autoencoder(input_dim=4)
model.eval()

# Reproducibility
torch.manual_seed(42)
for param in model.parameters():
    nn.init.normal_(param, mean=0.0, std=0.1)

Normal_Mean = np.array([75.0, 20.0, 10.0, 24.0], dtype=np.float32)
Normal_Std = np.array([5.0, 3.0, 1.5, 0.8], dtype=np.float32)

Anomaly_Threshold = 1.50

# Json schema
class SensorFeatures(BaseModel):
    temperature: float
    vibration: float
    pressure: float
    voltage: float

@app.post("/predict")
def predict_anomaly(features: SensorFeatures):
    # Convert coming data to numpy array
    raw_data = np.array([
        features.temperature,
        features.vibration,
        features.pressure,
        features.voltage
    ], dtype=np.float32)
    
    # Z-Score Normalization
    normalized_data = (raw_data - Normal_Mean) / Normal_Std

    # Convert numpy array to pytorch tensor and add batch dimension
    input_tensor = torch.tensor(normalized_data).unsqueeze(0)
    
    # Close gradient calculation for ram
    with torch.no_grad():
        reconstructed_tensor = model(input_tensor)
        # Calculate mse between input and output
        mse_loss = nn.functional.mse_loss(reconstructed_tensor, input_tensor).item()
    
    # If mse_loss g than threshold then turn True
    is_anomaly = bool(mse_loss > Anomaly_Threshold)
    
    return {
        "anomaly_score": round(mse_loss, 4),
        "threshold": Anomaly_Threshold,
        "is_anomaly": is_anomaly
    }