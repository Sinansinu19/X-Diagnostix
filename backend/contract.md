# Pathfinder Real-Time Contract

## 1. Architecture & Data Flow

1. The IoT Simulator reads one row of sensor telemetry from the CMAPSS dataset and sends it to the backend via a `POST /predict` request.
2. The FastAPI backend converts that payload into a pandas DataFrame, runs it through the XGBoost RUL model, and computes SHAP values using the global SHAP explainer.
3. Immediately after prediction, the backend broadcasts the resulting JSON payload to all connected frontend clients through the WebSocket tunnel at `/ws/dashboard`.

This creates a live pipeline where simulated telemetry enters the backend via REST and exits to the dashboard via WebSockets.

## 2. Connection Details

- Protocol: Secure WebSockets (`wss://`)
- Endpoint: `wss://[YOUR_NGROK_URL]/ws/dashboard`

The frontend must handle the full connection lifecycle:
- `onopen` to detect successful connection
- `onmessage` to receive payloads
- `onclose` to handle disconnects and optionally reconnect

Each incoming WebSocket message should be parsed with `JSON.parse(event.data)`.

## 3. The JSON Payload Schema

The frontend receives a JSON payload every time the backend broadcasts a new prediction. The exact schema is:

```json
{
  "predicted_RUL": 42.0,
  "risk_level": "MEDIUM",
  "shap_values": {
    "sensor_2": 0.12,
    "sensor_3": -0.08,
    "sensor_4": 0.05,
    "sensor_7": 0.03,
    "sensor_9": -0.02
  },
  "top_sensors": ["sensor_2", "sensor_3", "sensor_4"],
  "maintenance_action": "Schedule inspection within the next 24 hours and prioritize replacement of the top risk sensors."
}
```

### Field definitions

- `predicted_RUL` (float): The calculated Remaining Useful Life of the engine in cycles.
- `risk_level` (string): The categorical risk assessment returned by the threshold logic. Valid values are `LOW`, `MEDIUM`, or `HIGH`.
- `shap_values` (object): A dictionary mapping sensor names to their SHAP contribution values. Contains up to 5 sensor entries.
- `top_sensors` (array of strings): The top 3 sensors contributing most to the risk prediction.
- `maintenance_action` (string): A human-readable recommended maintenance action.

## 4. Frontend Implementation Example

```jsx
import { useEffect, useState } from 'react';

function Dashboard() {
  const [predictedRUL, setPredictedRUL] = useState(null);
  const [riskLevel, setRiskLevel] = useState('');
  const [shapValues, setShapValues] = useState({});
  const [topSensors, setTopSensors] = useState([]);
  const [maintenanceAction, setMaintenanceAction] = useState('');

  useEffect(() => {
    const ws = new WebSocket('wss://[YOUR_NGROK_URL]/ws/dashboard');

    ws.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPredictedRUL(data.predicted_RUL);
      setRiskLevel(data.risk_level);
      setShapValues(data.shap_values);
      setTopSensors(data.top_sensors);
      setMaintenanceAction(data.maintenance_action);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    return () => ws.close();
  }, []);

  return (
    <div>
      <div>RUL: {predictedRUL}</div>
      <div>Risk Level: {riskLevel}</div>
      <div>Top Sensors: {topSensors.join(', ')}</div>
      <div>Maintenance Action: {maintenanceAction}</div>
      <pre>{JSON.stringify(shapValues, null, 2)}</pre>
    </div>
  );
}

export default Dashboard;
```

This example demonstrates how to connect, parse incoming messages, and map payload properties to React state.
