"""
Global state management for the robotics car system
"""

car_state = {
    "session_active": False,
    "session_id": None,
    "session_start_time": None,
    "people_count": 0,
    "total_people": 0,
    "density_data": [],
    "air_quality": {"mq2": 0},
    "session_history": [],
    "position": [0, 0],
    "angle": 0,
    "speed": 0,
    "control_mode": "manual"
}

# API endpoints
JETSON_STREAM_URL = "10.102.82.69"
STREAM_URL = f"http://{JETSON_STREAM_URL}:8000/video_feed"
UPDATE_SENSOR = f"http://{JETSON_STREAM_URL}:8000/sensor/update"
LATEST_SENSOR = f"http://{JETSON_STREAM_URL}:8000/sensor/latest"
MOVEMENT_UPDATE = f"http://{JETSON_STREAM_URL}:8000/control"