"""
Session management functions
"""
import gradio as gr
from datetime import datetime
from app_utils.state import car_state
from db.db_manager import db_manager

db = db_manager()

def start_session():
    """Start a new monitoring session with database integration"""
    if not car_state["session_active"]:
        car_state["session_active"] = True
        car_state["session_id"] = db.start_session()
        car_state["session_start_time"] = datetime.now()
        status_msg = f"✅ Session Started: {car_state['session_id']}"
        return (gr.update(visible=False), gr.update(visible=True), status_msg, car_state["session_id"])
    return gr.update(), gr.update(), "⚠️ Session already active", car_state["session_id"]

def stop_session():
    """Stop the current monitoring session with database integration"""
    if car_state["session_active"]:
        db.stop_session(car_state["session_id"])
        car_state["session_active"] = False
        car_state["session_id"] = None
        status_msg = "✅ Session Stopped Successfully (Data Saved to Database)"
        return (gr.update(visible=True), gr.update(visible=False), status_msg, "")
    return gr.update(), gr.update(), "⚠️ No active session", ""

def save_current_data():
    """Save current sensor data to database"""
    if not car_state["session_active"]:
        return
    session_id = car_state["session_id"]
    db.save_people_count(session_id, car_state["people_count"])
    if car_state["density_data"]:
        current_density = car_state["density_data"][-1]
        db.save_crowd_density(session_id, current_density)
    db.save_air_quality(session_id, car_state["air_quality"]["mq2"])