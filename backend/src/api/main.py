import asyncio
import json
import os
import random
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

try:
    import openai
except ImportError:
    openai = None

app = FastAPI()


def generate_nlp_explanation(rul: int, top_sensors_dict: Dict[str, float]) -> str:
    prompt = (
        f"System failing in {rul} cycles. Top anomalous sensors: {top_sensors_dict}. "
        "Write a concise, 2-sentence maintenance recommendation explaining the root cause."
    )

    if openai is not None:
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                openai.api_key = api_key

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a maintenance root-cause explainer."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=120,
                temperature=0.6,
            )
            if response and response.choices:
                text = response.choices[0].message.get("content", "").strip()
                if text:
                    return text
        except Exception:
            pass

    return (
        "Inspect the indicated sensors for abnormal readings and address the likely component issue immediately. "
        "This proactive maintenance recommendation is intended to prevent imminent failure and reduce operational risk."
    )


def build_mock_payload() -> Dict:
    rul = random.randint(8, 45)
    failure_probability = round(random.uniform(0.65, 0.95), 2)
    if rul <= 20:
        risk_level = "HIGH"
    elif rul <= 35:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    top_sensors_dict = {
        "sensor_11": round(random.uniform(0.18, 0.45), 3),
        "sensor_4": round(random.uniform(0.12, 0.35), 3),
        "sensor_7": round(random.uniform(0.05, 0.21), 3),
    }

    explanation = generate_nlp_explanation(rul, top_sensors_dict)

    return {
        "engine_id": "FD001",
        "predicted_rul_cycles": rul,
        "failure_probability": failure_probability,
        "risk_level": risk_level,
        "top_anomalous_sensors": list(top_sensors_dict.keys()),
        "root_cause_explanation": explanation,
    }


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = build_mock_payload()
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI NLP explainer bridge is running."}
