from contextlib import asynccontextmanager
from typing import Dict, List
import json
import os

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
        
        # Initialize SHAP explainer globally
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
        # Convert incoming Pydantic payload to single-row Pandas DataFrame
        data_dict = payload.dict()
        df = pd.DataFrame([data_dict])

        # --- THE HARDCODED SHAPE FIX ---
        expected_cols = [
            'engine_id',
            'cycle',
            'sensor_2',
            'sensor_3',
            'sensor_4',
            'sensor_7',
            'sensor_8',
            'sensor_9',
            'sensor_11',
            'sensor_12',
            'sensor_13',
            'sensor_14',
            'sensor_15',
            'sensor_17',
            'sensor_20',
            'sensor_21',
        ]

        # Pad missing columns with 0.0
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0.0

        # Force the exact order
        df = df[expected_cols]
        # ---------------------------------
        
        # Get prediction from the model
        prediction = model_store["model"].predict(df)
        if prediction is None or len(prediction) == 0:
            raise ValueError("Prediction returned no results")

        predicted_rul = float(np.asarray(prediction)[0])
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Model prediction failed: {exc}")
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model prediction failed: {e}")

    # Calculate risk level using threshold logic
    risk_level = classify_risk(predicted_rul)

    # Extract SHAP values for the single-row DataFrame
    try:
        shap_values_obj = model_store["explainer"](df)
        
        # Extract the shap values for the first (only) row
        shap_values_array = shap_values_obj.values[0]
        
        # Map SHAP values to column names (excluding 'cycle' from sensor columns)
        column_names = list(df.columns)
        shap_dict = {col: float(shap_values_array[i]) for i, col in enumerate(column_names)}
        
        # Sort by absolute magnitude and get top 3 sensors
        sorted_shap = sorted(
            [(col, val) for col, val in shap_dict.items() if col != 'cycle'],
            key=lambda x: abs(x[1]),
            reverse=True
        )
        top_sensors = [col for col, val in sorted_shap[:3]]
        
        # Return only top sensors' SHAP values in response
        shap_values_response = {col: shap_dict[col] for col, _ in sorted_shap[:5]}
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SHAP analysis failed: {exc}")

    # Mocked human-readable maintenance action
    maintenance_action = (
        "Schedule inspection within the next 24 hours and prioritize replacement of the top risk sensors."
    )

    response_dict = {
        "predicted_RUL": predicted_rul,
        "risk_level": risk_level,
        "shap_values": shap_values_response,
        "top_sensors": top_sensors,
        "maintenance_action": maintenance_action,
    }

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


@app.get("/shap")
async def shap_insights() -> Dict[str, object]:
    return {
        "top_sensors": ["sensor_2", "sensor_3", "sensor_4"],
        "shap_values": {
            "sensor_2": 0.14,
            "sensor_3": -0.09,
            "sensor_4": 0.06,
            "sensor_7": 0.02,
            "sensor_9": -0.01,
        },
        "summary": "Mocked SHAP summary: sensor_2 and sensor_3 are the highest contributors to the RUL prediction.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
