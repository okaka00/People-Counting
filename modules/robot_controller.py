"""
Robot Control Utilities
Handles robot mode switching and movement commands
"""
import requests
import gradio as gr

class RobotController:
    """Handles robot control modes and movements"""
    
    def __init__(self, jetson_url, car_state):
        self.jetson_url = jetson_url
        self.car_state = car_state
    
    def set_mode_manual(self):
        """Switch to manual (Jetson) control mode"""
        try:
            response = requests.post(
                f"http://{self.jetson_url}:8000/set_mode",
                json={"mode": "manual"},
                timeout=2
            )
            if response.status_code == 200:
                self.car_state["control_mode"] = "manual"
                return (
                    "✅ Manual Mode Active",
                    "🖥️ Manual",
                    gr.update(visible=True),
                    gr.update(value="<script>if(window.setControlsEnabled)window.setControlsEnabled(true);</script>")
                )
        except Exception as e:
            print(f"Error setting manual mode: {e}")
        
        return "❌ Connection Error", "Error", gr.update(), gr.update()
    
    def set_mode_ps5(self):
        """Switch to PS5 controller mode"""
        try:
            response = requests.post(
                f"http://{self.jetson_url}:8000/set_mode",
                json={"mode": "ps5"},
                timeout=2
            )
            if response.status_code == 200:
                self.car_state["control_mode"] = "ps5"
                return (
                    "✅ PS5 Controller Mode\n\n🎮 Hold PS + Share to pair",
                    "🎮 PS5",
                    gr.update(visible=False),
                    gr.update(value="<script>if(window.setControlsEnabled)window.setControlsEnabled(false);</script>")
                )
        except Exception as e:
            print(f"Error setting PS5 mode: {e}")
        
        return "❌ Connection Error", "Error", gr.update(), gr.update()
    
    def set_mode_autonomous(self):
        """Switch to autonomous mode"""
        try:
            response = requests.post(
                f"http://{self.jetson_url}:8000/set_mode",
                json={"mode": "auto"},
                timeout=2
            )
            if response.status_code == 200:
                self.car_state["control_mode"] = "auto"
                return (
                    "✅ Autonomous Mode Active",
                    "🤖 Autonomous",
                    gr.update(visible=False),
                    gr.update(value="<script>if(window.setControlsEnabled)window.setControlsEnabled(false);</script>")
                )
        except Exception as e:
            print(f"Error setting autonomous mode: {e}")
        
        return "❌ Connection Error", "Error", gr.update(), gr.update()
    
    def send_command(self, direction):
        """Send movement command to robot"""
        if self.car_state.get("control_mode") != "manual":
            return "⚠️ Manual mode only!"
        
        try:
            requests.post(
                f"http://{self.jetson_url}:8000/control",
                json={"direction": direction},
                timeout=1
            )
        except Exception as e:
            print(f"Error sending command: {e}")
        
        movements = {
            "forward": "Forward ⬆️",
            "backward": "Backward ⬇️",
            "left": "Left ⬅️",
            "right": "Right ➡️",
            "stop": "Stop 🛑"
        }
        return movements.get(direction, "Unknown")