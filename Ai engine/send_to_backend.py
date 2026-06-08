"""
Connects AI detections to the backend API.
Run this alongside test_pipeline.py to send
real detections to your backend.

Configuration:
  Copy config.env.example → config.env and fill in your values.
"""

import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv("config.env")

CLOUD_API_URL    = os.getenv("CLOUD_API_URL", "http://localhost:8000")
FACILITY_API_KEY = os.getenv("FACILITY_API_KEY", "")
GATE_ID          = os.getenv("GATE_ID", "")

HEADERS = {"X-API-Key": FACILITY_API_KEY}


async def send_scan(plate_number: str = None, face_embedding: list = None, confidence: float = 0.9):
    payload = {
        "gate_id": GATE_ID,
        "plate_number": plate_number,
        "plate_confidence": 0.85,
        "persons": [
            {
                "face_embedding": face_embedding,
                "face_confidence": confidence,
            }
        ] if face_embedding else [],
        "edge_timestamp": None,
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{CLOUD_API_URL}/api/scan/",
            json=payload,
            headers=HEADERS,
        )
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        return resp.json() if resp.text else {}


async def test():
    print("\n--- Test 1: Unknown plate, no face ---")
    result = await send_scan(plate_number="ABC123")
    print(result)

    print("\n--- Test 2: No plate, no face ---")
    result = await send_scan()
    print(result)

    print("\n--- Test 3: Unknown plate with random face ---")
    import numpy as np
    fake_embedding = np.random.rand(512).tolist()
    result = await send_scan(plate_number="XYZ999", face_embedding=fake_embedding, confidence=0.92)
    print(result)


if __name__ == "__main__":
    asyncio.run(test())