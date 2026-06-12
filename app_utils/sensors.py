"""
Sensor data fetching and processing functions
"""
import cv2
import numpy as np
import requests # type: ignore
from threading import Thread
import time
from app_utils.state import car_state, JETSON_STREAM_URL
from db.db_manager import db_manager

db = db_manager()

def fetch_stream_frame():
    """Fetch video stream frames"""
    try:
        r = requests.get(f"http://{JETSON_STREAM_URL}:8000/video_feed", stream=True)
        bytes_data = b''
        for chunk in r.iter_content(chunk_size=1024):
            bytes_data += chunk
            a = bytes_data.find(b'\xff\xd8')
            b = bytes_data.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = bytes_data[a:b+2]
                bytes_data = bytes_data[b+2:]
                img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                yield cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    except Exception as e:
        print("Error fetching video:", e)

def update_stream_feed():
    """Update stream feed with status"""
    try:
        frame_gen = fetch_stream_frame()
        img = next(frame_gen, None)
        if img is None:
            return None, "⚠️ No frame received"
        status = (
            f"Position: ({car_state['position'][0]}, {car_state['position'][1]}) | "
            f"Angle: {car_state['angle']}° | People: {car_state['people_count']}"
        )
        return img, status
    except Exception as e:
        print("Error update_stream_feed:", e)
        return None, "⚠️ Error in stream"

def fetch_people_count():
    """Fetch people count from Jetson"""
    try:
        response = requests.get(f"http://{JETSON_STREAM_URL}:8000/people_count")
        data = response.json()
        return data['people_count']
    except Exception as e:
        print("❌ Error fetching people count:", e)
        return None

def update_people_count_loop():
    """Background thread to update people count"""
    while True:
        count = fetch_people_count()
        if count is not None:
            car_state["people_count"] = count
            car_state["total_people"] += count
            session_id = car_state["session_id"]
            if session_id:
                db.save_people_count(session_id, count)
                print(f"✅ Saved people count: {count}")
        time.sleep(1)

def start_people_count_thread():
    """Start the background thread for people counting"""
    Thread(target=update_people_count_loop, daemon=True).start()