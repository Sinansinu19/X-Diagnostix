from contextlib import asynccontextmanager
from typing import Dict, List
import json
import os
import traceback

import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sklearn.base import BaseEstimator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "xgb_rul_model.pkl")
APP_VERSION = "1.0.0"

model_store: Dict[str, object] = {"model": None, "loaded": False, "explainer": None}

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

class SensorPayload(BaseModel):
    cycle: int = Field(..., description="Current operating cycle")
    sensor_2: float
    sensor_3: float
    sensor_4: float
    sensor_7: float
    sensor_9: float
    sensor_11: float
    sensor_12: float
    sensor_14: float
    sensor_15: float

class PredictionResponse(BaseModel):
    predicted_RUL: float
    risk_level: str
    shap_values: Dict[str, float]
    top_sensors: List[str]
    maintenance_action: str

def classify_risk(predicted_rul: float) -> str:
    if predicted_rul <= 25:
        return "HIGH"
    if predicted_rul <= 50:
        return "MEDIUM"
    return "LOW"

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        model = joblib.load(MODEL_PATH)
        if not isinstance(model, BaseEstimator):
            raise TypeError("Loaded object is not a scikit-learn compatible model")

        model_store["model"] = model
        model_store["loaded"] = True
        app.state.model = model
        app.state.model_loaded = True
        
        explainer = shap.Explainer(model)
        model_store["explainer"] = explainer
        app.state.explainer = explainer
    except Exception:
        model_store["model"] = None
        model_store["loaded"] = False
        model_store["explainer"] = None
        app.state.model = None
        app.state.model_loaded = False
        app.state.explainer = None
    yield

app = FastAPI(lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.get("/health")
async def health_check() -> Dict[str, object]:
    return {
        "status": "ok",
        "model_loaded": bool(app.state.model_loaded),
        "version": APP_VERSION,
    }

@app.post("/predict", response_model=PredictionResponse)
async def predict(payload: SensorPayload):
    if not model_store.get("loaded") or model_store.get("model") is None:
        raise HTTPException(status_code=503, detail="Model is not available for prediction")
    
    if model_store.get("explainer") is None:
        raise HTTPException(status_code=503, detail="SHAP explainer is not available")

    try:
        data_dict = payload.dict()
        df = pd.DataFrame([data_dict])

        expected_cols = [
            'engine_id', 'cycle', 'sensor_2', 'sensor_3', 'sensor_4', 'sensor_7',
            'sensor_8', 'sensor_9', 'sensor_11', 'sensor_12', 'sensor_13', 'sensor_14',
            'sensor_15', 'sensor_17', 'sensor_20', 'sensor_21'
        ]

        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0.0

        df = df[expected_cols]
        
        prediction = model_store["model"].predict(df)
        if prediction is None or len(prediction) == 0:
            raise ValueError("Prediction returned no results")

        predicted_rul = float(np.asarray(prediction)[0])
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Model prediction failed: {exc}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model prediction failed: {e}")

    risk_level = classify_risk(predicted_rul)

    try:
        shap_values_obj = model_store["explainer"](df)
        shap_values_array = shap_values_obj.values[0]
        column_names = list(df.columns)
        shap_dict = {col: float(shap_values_array[i]) for i, col in enumerate(column_names)}
        
        sorted_shap = sorted(
            [(col, val) for col, val in shap_dict.items() if col != 'cycle'],
            key=lambda x: abs(x[1]),
            reverse=True
        )
        top_sensors = [col for col, val in sorted_shap[:3]]
        shap_values_response = {col: shap_dict[col] for col, _ in sorted_shap[:5]}
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SHAP analysis failed: {exc}")

    import requests
    
    # --- NLP Microservice Integration ---
    nlp_payload = {
        "predicted_rul": float(predicted_rul),
        "risk_level": str(risk_level),
        "top_sensors": top_sensors
    }
    
    try:
        nlp_url = "https://starless-lethargy-scrunch.ngrok-free.dev/generate_explanation"
        
        # REQUIRED FIX: Bypass the Ngrok warning page and set proper Content-Type
        headers = {
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true" 
        }
        
        # REQUIRED FIX: Increase timeout to 15s to allow Llama 3 to generate text
        nlp_response = requests.post(nlp_url, json=nlp_payload, headers=headers, timeout=15.0)
        
        if nlp_response.status_code == 200:
            maintenance_action = nlp_response.json().get("maintenance_action", "Fallback: Schedule inspection.")
            print("🟢 Successfully injected Llama 3 text!")
        else:
            maintenance_action = f"NLP Engine Error {nlp_response.status_code}."
            print(f"🔴 NLP Server Rejected Request: {nlp_response.text}")
            
    except requests.exceptions.Timeout:
        print("🔴 NLP Connection Timed Out (Llama 3 took too long)")
        maintenance_action = "Schedule inspection within the next 24 hours."
    except Exception as e:
        print(f"🔴 NLP Connection Failed: {e}")
        maintenance_action = "Schedule inspection within the next 24 hours."
    # ------------------------------------

    response_dict = {
        "predicted_RUL": predicted_rul,
        "risk_level": risk_level,
        "shap_values": shap_values_response,
        "top_sensors": top_sensors,
        "maintenance_action": maintenance_action,
    }

    print(f"🟢 Broadcasting data to {len(manager.active_connections)} connected clients!")
    await manager.broadcast(json.dumps(response_dict))

    return PredictionResponse(**response_dict)

@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)