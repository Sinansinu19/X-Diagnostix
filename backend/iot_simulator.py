import csv
import json
import os
import time
from pathlib import Path

import requests

DATA_FILE = Path("data/test_FD001.txt")

# Check for ngrok URL in environment variable, fallback to localhost
NGROK_URL = os.getenv("NGROK_URL", "http://localhost:8080")
ENDPOINT_URL = f"http://localhost:8080/predict"

POST_TIMEOUT_SECONDS = 20.0
SLEEP_SECONDS = 1.0


COLUMN_NAMES = [
    "unit_number",
    "cycle",
    "op1",
    "op2",
    "op3",
] + [f"sensor_{i}" for i in range(1, 22)]

FILTERED_FIELDS = [
    "cycle",
    "sensor_2",
    "sensor_3",
    "sensor_4",
    "sensor_7",
    "sensor_9",
    "sensor_11",
    "sensor_12",
    "sensor_14",
    "sensor_15",
]


def build_payload(row_values):
    if len(row_values) != len(COLUMN_NAMES):
        raise ValueError(
            f"Expected {len(COLUMN_NAMES)} columns, got {len(row_values)} columns"
        )

    raw_row = dict(zip(COLUMN_NAMES, row_values))
    payload = {field: float(raw_row[field]) for field in FILTERED_FIELDS}
    payload["cycle"] = int(raw_row["cycle"])
    return payload


def send_payload(payload):
    response = requests.post(
        ENDPOINT_URL,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=POST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def print_response(response_data, row_index):
    predicted_rul = response_data.get("predicted_RUL")
    risk_level = response_data.get("risk_level")
    maintenance_action = response_data.get("maintenance_action")
    print(
        f"[{row_index}] predicted_RUL={predicted_rul} | risk_level={risk_level} | maintenance_action={maintenance_action}"
    )


def simulate(stream_file: Path):
    if not stream_file.exists():
        raise FileNotFoundError(f"Data file not found: {stream_file}")

    with stream_file.open("r", newline="") as csv_file:
        reader = csv.reader(csv_file, delimiter=" ", skipinitialspace=True)
        for row_index, row in enumerate(reader, start=1):
            if not row:
                continue

            # REQUIRED FIX: Remove empty strings caused by trailing spaces in the text file
            cleaned_row = [val for val in row if val.strip() != ""]

            try:
                payload = build_payload(cleaned_row)
            except ValueError as exc:
                print(f"Skipping row {row_index}: invalid row format ({exc})")
                continue

            try:
                response_data = send_payload(payload)
                print_response(response_data, row_index)
            except requests.exceptions.RequestException as exc:
                print(f"Request error on row {row_index}: {exc}")
            except ValueError as exc:
                print(f"Invalid JSON response on row {row_index}: {exc}")
            except Exception as exc:
                print(f"Unexpected error on row {row_index}: {exc}")

            time.sleep(SLEEP_SECONDS)


def main():
    try:
        print(f"Starting IoT simulator using file: {DATA_FILE}")
        simulate(DATA_FILE)
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")
    except Exception as exc:
        print(f"Simulation failed: {exc}")


if __name__ == "__main__":
    main()
