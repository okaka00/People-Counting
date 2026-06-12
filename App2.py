"""
Main application entry point
Integrated with Flask backend + Email Notifications + Downloadable Reports
- Before running the system, ensure that the hotspot IP address is correctly configured. 
1) Please check your current hotspot IP address
2) update it accordingly in both state.py and stream_recorder.py files.

This ensures proper communication between devices during system operation

"""
from threading import Thread
import gradio as gr
import time
import requests
from flask import Flask, request, jsonify # type: ignore
from datetime import datetime

# Import utilities
from app_utils.state import car_state, JETSON_STREAM_URL
from app_utils.session import start_session, stop_session
from db.db_manager import db_manager

# Import email notifications
from app_utils.email_notifications import (
    send_alert_email, 
    send_report_email, 
    alert_tracker,
    test_email,
    HIGH_DENSITY_THRESHOLD,
    CRITICAL_DENSITY_THRESHOLD,
    MQ2_WARNING_THRESHOLD,
    MQ2_CRITICAL_THRESHOLD
)

# Import tab components
from navigation.dashboard_tab import create_dashboard_tab
from navigation.control_tab import create_control_tab
from navigation.history_tab import create_history_tab

# ========================================
# FLASK BACKEND FOR OPENCV DATA
# ========================================
flask_app = Flask(__name__)

@flask_app.route('/api/update_count', methods=['POST'])
def update_count():
    """
    Receive people count from OpenCV processor
    Check for alerts ONLY if MQ2 sensor shows poor air quality
    """
    try:
        data = request.get_json()
        count = data.get("people_count", 0)
        unique_ids = data.get("unique_ids", 0)
        
        # Update car_state
        car_state["people_count"] = count
        car_state["total_people"] = max(car_state["total_people"], unique_ids)
        car_state["last_update"] = datetime.now()
        
        # Save to database if session active
        if car_state["session_id"] and car_state["session_active"]:
            db = db_manager()
            db.save_people_count(car_state["session_id"], count)
            print(f"✅ Saved: {count} people (Unique: {unique_ids})")
            
            # ========================================
            # SMART EMAIL ALERTS
            # ========================================
            user_email = car_state.get("user_email")
            mq2_value = car_state.get("air_quality", {}).get("mq2", 0)
            
            # Convert mq2 to number if needed
            if isinstance(mq2_value, str):
                try:
                    mq2_value = float(mq2_value) if mq2_value != "N/A" else 0
                except:
                    mq2_value = 0
            
        if user_email and mq2_value >= MQ2_WARNING_THRESHOLD:
            # CRITICAL ALERT: High crowd + Poor air
            if count >= CRITICAL_DENSITY_THRESHOLD:
                if alert_tracker.should_send_alert("critical"):
                    print(f"🚨 CRITICAL ALERT: {count} people + MQ2: {mq2_value}")
                    print(f"📧 Sending email to {user_email}")
                    send_alert_email(user_email, count, unique_ids, mq2_value, "critical")
            
            # HIGH ALERT: Medium-high crowd + Poor air
            elif count >= HIGH_DENSITY_THRESHOLD:
                if alert_tracker.should_send_alert("high"):
                    print(f"⚠️ HIGH ALERT: {count} people + MQ2: {mq2_value}")
                    print(f"📧 Sending email to {user_email}")
                    send_alert_email(user_email, count, unique_ids, mq2_value, "high")
            
            # NEW: MQ2 ALERT: Poor air quality (regardless of crowd)
            else:
                if alert_tracker.should_send_alert("air_quality"):
                    print(f"🌡️ AIR QUALITY ALERT: MQ2: {mq2_value} (People: {count})")
                    print(f"📧 Sending email to {user_email}")
                    send_alert_email(user_email, count, unique_ids, mq2_value, "air_quality")

        # NEW: CRITICAL MQ2 ALERT: Very high MQ2 reading
        elif user_email and mq2_value >= MQ2_CRITICAL_THRESHOLD:
            if alert_tracker.should_send_alert("critical_air"):
                print(f"🚨🌡️ CRITICAL AIR QUALITY: MQ2: {mq2_value} (People: {count})")
                print(f"📧 Sending email to {user_email}")
                send_alert_email(user_email, count, unique_ids, mq2_value, "critical_air")

        # High crowd but good air quality (info only, no alert)
        elif user_email and count >= HIGH_DENSITY_THRESHOLD:
            print(f"ℹ️ High density ({count} people) but air quality OK (MQ2: {mq2_value}) - No alert sent")
        else:
            print(f"📊 Received: {count} people (Unique: {unique_ids}) | No active session")
        
        return jsonify({"status": "ok"})
    
    except Exception as e:
        print(f"❌ Error in update_count: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@flask_app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status"""
    return jsonify({
        "people_count": car_state["people_count"],
        "total_people": car_state["total_people"],
        "session_active": car_state["session_active"],
        "session_id": car_state["session_id"],
        "user_email": car_state.get("user_email", "")
    })

@flask_app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "online",
        "car_state": {
            "people_count": car_state["people_count"],
            "total_people": car_state["total_people"],
            "session_active": car_state["session_active"]
        }
    })

def run_flask():
    """Run Flask backend in separate thread"""
    print("📊 Starting Flask backend on port 7860...")
    flask_app.run(host="0.0.0.0", port=7860, debug=False, use_reloader=False)

# ========================================
# BACKGROUND DATA FETCHING
# ========================================

def fetch_sensor_data():
    """Fetch sensor data from Jetson (MQ2, etc.)"""
    try:
        response = requests.get(f"http://{JETSON_STREAM_URL}:8000/sensor/latest", timeout=1)
        data = response.json()
        car_state["air_quality"]["mq2"] = data.get("mq2", 0)
        return data.get("mq2", 0)
    except Exception as e:
        return None

def update_sensor_data_loop():
    """Background thread to fetch sensor data"""
    while True:
        fetch_sensor_data()
        time.sleep(5)

# Start sensor data fetching in background
Thread(target=update_sensor_data_loop, daemon=True).start()

# ========================================
# SESSION FUNCTIONS WITH EMAIL
# ========================================

def start_session_with_email(email):
    """Start session and save user email"""
    # Validate email
    if not email or "@" not in email:
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            "❌ Please enter a valid email address",
            "",
            gr.update(value="")
        )
    
    # Save email to car_state
    car_state["user_email"] = email.strip()
    
    # Reset alert tracker for new session
    alert_tracker.reset()
    
    # Test email (send welcome email)
    print(f"📧 Sending welcome email to {email}...")
    if test_email(email):
        print("✅ Welcome email sent!")
    else:
        print("⚠️ Email test failed - check configuration")
    
    # Start session normally
    result = start_session()
    
    # Return with email display
    email_display = f"📧 {email}"
    return result + (gr.update(value=email_display),)

def stop_session_with_email():
    """Stop session WITHOUT automatically sending report"""
    result = stop_session()
    return result

# ========================================
# LOAD EXTERNAL ASSETS
# ========================================

def load_file(filepath):
    """Load external file content"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"⚠️ Error loading {filepath}: {e}")
        return ""

custom_css = load_file("custom.css")
keyboard_js = load_file("js/keyboard_control.js")

# ========================================
# CREATE GRADIO INTERFACE
# ========================================

with gr.Blocks(
    css=custom_css,
    title="Robotics Car People Counting System",
    theme=gr.themes.Soft(),
    head=f"<script>{keyboard_js}</script>"
) as demo:
    
    # ========================================
    # START PAGE WITH EMAIL INPUT
    # ========================================
    with gr.Column(visible=True) as start_page:
        gr.HTML("""
        <div class="start-container">
            <h1 class="hero-title">Robotics Car System</h1>
            <p class="hero-subtitle">People Counting & Monitoring Platform</p>
        </div>
        """)
        
        # Email input
        email_input = gr.Textbox(
            label="📧 Your Email Address",
            placeholder="example@email.com",
            info="You'll receive alerts when crowd density + air quality require attention",
            elem_id="email-input"
        )
        
        start_btn = gr.Button("Start Session", size="lg", elem_classes=["start-button"])
    
    # ========================================
    # MAIN INTERFACE
    # ========================================
    with gr.Column(visible=False) as main_interface:
        with gr.Row():
            with gr.Column(scale=4):
                gr.HTML("""
                <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin-bottom: 20px;'>
                    <h1 style='margin: 0;'>Robotics Car System</h1>
                    <p style='margin: 5px 0 0 0; opacity: 0.9;'>YOLOv5 + DeepSORT | People Counting | Smart Alerts 🌡️📧</p>
                </div>
                """)
            with gr.Column(scale=1):
                session_id_display = gr.Textbox(label="Active Session", interactive=False)
                stop_btn = gr.Button("🛑 Stop Session", variant="stop", size="lg")
        
        session_status = gr.Textbox(label="Status", visible=False)
        
        # Show active email
        with gr.Row():
             with gr.Column(scale=4):
                gr.HTML("""
                    <div class="info-box">
                        <p>
                            <strong>🌡️ Smart Alerts:</strong> Emails sent ONLY when high crowd (50+) + poor air quality<br>
                            <strong>📊 Reports:</strong> Download or email reports from Dashboard tab
                        </p>
                    </div>
                    """)
                with gr.Column(scale=4):
                    active_email = gr.Textbox(
                        label="📧 Email Notifications Active",
                        value="",
                        interactive=False
                    )
        
        
        # ========================================
        # TABS
        # ========================================
        with gr.Tabs():
            create_dashboard_tab()
            create_control_tab()
            create_history_tab()
        
        # ========================================
        # FOOTER
        # ========================================
        gr.HTML("""
        <div style='text-align: center; padding: 30px; margin-top: 20px; border-top: 2px solid rgba(102, 126, 234, 0.3); color: rgba(255,255,255,0.8);'>
            <p style='opacity: 0.5; margin-top: 20px;'>© 2024 Robotics Car System | OpenCV + YOLOv5 + DeepSORT + MQ2 + Smart Alerts</p>
        </div>
        """)
    
    # ========================================
    # EVENT HANDLERS
    # ========================================
    start_btn.click(
        start_session_with_email,
        inputs=[email_input],
        outputs=[start_page, main_interface, session_status, session_id_display, active_email]
    )
    
    stop_btn.click(
        stop_session_with_email, 
        outputs=[start_page, main_interface, session_status, session_id_display]
    )

# ========================================
# MAIN
# ========================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 ROBOTICS CAR CONTROL SYSTEM + SMART ALERTS")
    print("=" * 60)
    print("📊 Flask API: http://localhost:7860/api/update_count")
    print("🌐 Gradio UI: http://localhost:7861")
    print("📧 Smart Email Alerts: Enabled")
    print("🌡️ MQ2 Air Quality Sensor: Monitoring")
    print("=" * 60)
    print("\n⚠️ EMAIL CONFIGURATION:")
    print("Edit utils/email_notifications.py and set:")
    print("  - API key (line 12)")
    print("  - Get key from your email service")
    print("=" * 60)
    print("\n✅ Starting servers...\n")
    
    # Start Flask backend
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    time.sleep(2)
    print("\n🎬 Launching Gradio...\n")
    
    # Launch Gradio
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        show_error=True
    )