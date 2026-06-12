"""
Control Tab - IMPROVED UI
1. Better video dropdown (always visible, larger, searchable)
2. Removed control mode textbox
3. Responsive mode buttons with color feedback
"""
import gradio as gr
import os
import threading
from datetime import datetime

# Import custom modules
from modules.video_processor import VideoProcessor
from modules.robot_controller import RobotController
from modules.file_handler import FileUploadHandler
from modules.recording_handler import RecordingHandler

# Import app utilities
from app_utils.state import car_state, JETSON_STREAM_URL
from db.db_manager import db_manager

# ========================================
# GLOBAL INSTANCES
# ========================================
db = db_manager()
video_processor = VideoProcessor()
robot_controller = RobotController(JETSON_STREAM_URL, car_state)
file_handler = FileUploadHandler()
recording_handler = RecordingHandler()

# Processing state
processing_active = False

# Live stats for auto-refresh
live_stats = {
    "current_count": 0,
    "total_count": 0,
    "unique_people": 0,
    "frame_number": 0,
    "total_frames": 0,
    "progress_percent": 0.0,
    "fps": 0.0,
    "status": "Idle",
    "preview_frame": None
}

# Session cumulative tracking
session_cumulative = {
    "total_people": 0,
    "videos_processed": 0,
    "current_session_id": None
}

# ========================================
# CUMULATIVE COUNT HELPERS
# ========================================

def reset_session_cumulative():
    """Reset cumulative count for new session"""
    global session_cumulative
    session_cumulative = {
        "total_people": 0,
        "videos_processed": 0,
        "current_session_id": None
    }
    print("🔄 Session cumulative counter reset")

def add_to_session_cumulative(people_count, session_id):
    """Add people count to session cumulative total"""
    global session_cumulative
    
    if session_cumulative["current_session_id"] != session_id:
        reset_session_cumulative()
        session_cumulative["current_session_id"] = session_id
    
    session_cumulative["total_people"] += people_count
    session_cumulative["videos_processed"] += 1
    
    print(f"📊 Cumulative: {session_cumulative['total_people']} people across {session_cumulative['videos_processed']} videos/images")
    
    return session_cumulative["total_people"]

# ========================================
# MODE SWITCHING
# ========================================

def switch_mode(mode):
    """Switch between Upload and Record modes"""
    if mode == "Upload File":
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False)
        )
    else:
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False)
        )

# ========================================
# UPLOAD HANDLERS
# ========================================

def handle_upload(file):
    """Handle file upload"""
    status, dropdown, button_vis = file_handler.handle_upload(file)
    return status, dropdown, button_vis, gr.update(visible=False)

def process_image_click():
    """Start image processing"""
    global processing_active
    
    image_path = file_handler.get_last_image_path()
    
    if image_path is None:
        return "⚠️ No image uploaded!", gr.update(visible=False)
    
    if not os.path.exists(image_path):
        return "❌ Image not found", gr.update(visible=False)
    
    if processing_active:
        return "⚠️ Processing already active!", gr.update(visible=False)
    
    thread = threading.Thread(target=process_image_thread, args=(image_path,))
    thread.daemon = True
    thread.start()
    
    return "✅ Processing image...\n\n🎯 Detecting people with YOLO", gr.update(visible=True)

# ========================================
# RECORDING HANDLERS
# ========================================

def start_recording():
    """Start Jetson stream recording"""
    global processing_active
    
    if processing_active:
        return "⚠️ Cannot record while processing!", gr.update()
    
    return recording_handler.start_recording()

def stop_recording():
    """Stop Jetson stream recording"""
    return recording_handler.stop_recording()

def process_video_click_from_record(selected_video):
    """Process video from record mode"""
    status = process_video_click(selected_video)
    return status, gr.update(visible=True)

def process_image_thread(image_path):
    """Process image - Save cumulative total only"""
    global processing_active, live_stats
    
    try:
        processing_active = True
        live_stats["status"] = "Processing image..."
        
        output_folder = "processed_images"
        output_filename = os.path.basename(image_path).replace('.jpg', '_processed.jpg').replace('.png', '_processed.png')
        output_path = os.path.join(output_folder, output_filename)
        
        people_count, processed_pil = video_processor.process_image(image_path, output_path)
        
        if not car_state.get("session_active"):
            session_id = db.start_session()
            car_state["session_id"] = session_id
            car_state["session_active"] = True
            car_state["session_start_time"] = datetime.now()
            car_state["current_density_data"] = []
        else:
            session_id = car_state["session_id"]
        
        cumulative_total = add_to_session_cumulative(people_count, session_id)
        
        if "current_density_data" not in car_state:
            car_state["current_density_data"] = []
        car_state["current_density_data"].append(people_count)
        
        live_stats["current_count"] = people_count
        live_stats["total_count"] = cumulative_total
        live_stats["unique_people"] = people_count
        live_stats["frame_number"] = 1
        live_stats["total_frames"] = 1
        live_stats["progress_percent"] = 100.0
        live_stats["status"] = f"✅ Complete! Current: {people_count} | Total: {cumulative_total}"
        live_stats["preview_frame"] = processed_pil
        
        car_state["people_count"] = people_count
        car_state["total_people"] = cumulative_total
        
        db.save_people_count(session_id, cumulative_total)
        db.save_crowd_density(session_id, people_count * 10)
        
        print(f"✅ Image complete: current={people_count}, cumulative={cumulative_total}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        live_stats["status"] = "❌ Error"
    
    finally:
        processing_active = False

# ========================================
# VIDEO HANDLERS
# ========================================

def process_video_click(selected_video):
    """Start video processing"""
    global processing_active, live_stats
    
    if processing_active:
        return "⚠️ Processing already active!"
    
    if not selected_video:
        return "⚠️ No video selected!"
    
    try:
        actual_filename = get_actual_filename(selected_video)
        video_path = os.path.join("recorded_videos", actual_filename)
        
        if not os.path.exists(video_path):
            return f"❌ Video not found: {actual_filename}"
        
        live_stats["current_count"] = 0
        live_stats["unique_people"] = 0
        live_stats["frame_number"] = 0
        live_stats["total_frames"] = 0
        live_stats["progress_percent"] = 0.0
        live_stats["fps"] = 0.0
        live_stats["status"] = "Starting..."
        live_stats["preview_frame"] = None
        
        thread = threading.Thread(target=process_video_thread, args=(video_path,))
        thread.daemon = True
        thread.start()
        
        processing_active = True
        
        return f"✅ Processing Started!\n\n📹 {actual_filename}\n🎯 YOLO + DeepSORT"
    
    except Exception as e:
        return f"❌ Error: {str(e)}"

def process_video_thread(video_path):
    """Process video - Save cumulative total only"""
    global processing_active, live_stats
    
    try:
        processing_active = True
        
        output_folder = "processed_videos"
        video_name = os.path.basename(video_path).replace('.mp4', '_processed.mp4').replace('.avi', '_processed.mp4')
        output_path = os.path.join(output_folder, video_name)
        
        if not car_state.get("session_active"):
            session_id = db.start_session()
            car_state["session_id"] = session_id
            car_state["session_active"] = True
            car_state["session_start_time"] = datetime.now()
            car_state["current_density_data"] = []
        else:
            session_id = car_state["session_id"]
        
        def update_progress(frame_num, total_frames, people_count, unique_ids, processed_pil, fps):
            progress = (frame_num / total_frames) * 100 if total_frames > 0 else 0
            cumulative_total = session_cumulative["total_people"] + unique_ids
            
            live_stats["frame_number"] = frame_num
            live_stats["total_frames"] = total_frames
            live_stats["current_count"] = unique_ids
            live_stats["total_count"] = cumulative_total
            live_stats["unique_people"] = unique_ids
            live_stats["fps"] = fps
            live_stats["progress_percent"] = progress
            live_stats["status"] = f"Processing... {progress:.1f}% | Current: {unique_ids} | Total: {cumulative_total}"
            live_stats["preview_frame"] = processed_pil
            
            car_state["people_count"] = unique_ids
            car_state["total_people"] = cumulative_total
            
            if frame_num % 30 == 0:
                db.save_crowd_density(session_id, people_count * 10)
        
        stats = video_processor.process_video(video_path, output_path, update_progress)
        
        cumulative_total = add_to_session_cumulative(stats['unique_people'], session_id)
        
        if "current_density_data" not in car_state:
            car_state["current_density_data"] = []
        car_state["current_density_data"].append(stats['unique_people'])
        
        live_stats["current_count"] = stats['unique_people']
        live_stats["total_count"] = cumulative_total
        live_stats["status"] = f"✅ Complete! Current: {stats['unique_people']} | Total: {cumulative_total}"
        live_stats["progress_percent"] = 100.0
        
        car_state["people_count"] = stats['unique_people']
        car_state["total_people"] = cumulative_total
        
        db.save_people_count(session_id, cumulative_total)
        
        print(f"✅ Video complete: current={stats['unique_people']}, cumulative={cumulative_total}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        live_stats["status"] = "❌ Error"
    
    finally:
        processing_active = False

def get_video_list():
    """Get list of videos with enhanced display format"""
    if not os.path.exists("recorded_videos"):
        return []
    
    videos = []
    for f in os.listdir("recorded_videos"):
        if f.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            filepath = os.path.join("recorded_videos", f)
            
            try:
                mtime = os.path.getmtime(filepath)
                file_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                size_mb = os.path.getsize(filepath) / (1024 * 1024)
                display_name = f"{f} ({file_date}, {size_mb:.1f} MB)"
                videos.append((display_name, f))
            except:
                videos.append((f, f))
    
    videos.sort(key=lambda x: os.path.getmtime(os.path.join("recorded_videos", x[1])), reverse=True)
    
    return [v[0] for v in videos]

def get_actual_filename(display_name):
    """Extract actual filename from display name"""
    if " (" in display_name:
        return display_name.split(" (")[0]
    return display_name

def refresh_video_list():
    """Refresh dropdown with enhanced video info"""
    videos = get_video_list()
    
    if not videos:
        return gr.update(choices=[], value=None), "No videos found in recorded_videos folder"
    
    return gr.update(choices=videos, value=videos[0]), f"✅ Found {len(videos)} video(s)\n📹 Showing: filename, date, size"

# ========================================
# STATS REFRESH
# ========================================

def get_live_stats():
    """Get current stats for auto-refresh"""
    progress_value = live_stats["progress_percent"] / 100.0
    
    return (
        live_stats["preview_frame"],
        f"👥 Current: {live_stats['current_count']}",
        f"📊 Total: {live_stats['total_count']}",
        f"📊 {live_stats['frame_number']}/{live_stats['total_frames']}",
        f"⚡ {live_stats['fps']:.1f} FPS",
        live_stats['status'],
        progress_value
    )

# ========================================
# ROBOT CONTROL MODE SWITCHING WITH VISUAL FEEDBACK
# ========================================

def set_mode_with_feedback(mode):
    """Set robot mode and return button color updates"""
    if mode == "manual":
        result = robot_controller.set_mode_manual()
        return (
            result[0],  # Status message
            gr.update(variant="primary"),   # Manual button - ACTIVE
            gr.update(variant="secondary"), # PS5 button - INACTIVE
            gr.update(variant="secondary"), # Auto button - INACTIVE
            result[2],  # Control group
            result[3]   # JS executor
        )
    elif mode == "ps5":
        result = robot_controller.set_mode_ps5()
        return (
            result[0],
            gr.update(variant="secondary"), # Manual button - INACTIVE
            gr.update(variant="primary"),   # PS5 button - ACTIVE
            gr.update(variant="secondary"), # Auto button - INACTIVE
            result[2],
            result[3]
        )
    else:  # auto
        result = robot_controller.set_mode_autonomous()
        return (
            result[0],
            gr.update(variant="secondary"), # Manual button - INACTIVE
            gr.update(variant="secondary"), # PS5 button - INACTIVE
            gr.update(variant="primary"),   # Auto button - ACTIVE
            result[2],
            result[3]
        )

# ========================================
# CREATE TAB
# ========================================

def create_control_tab():
    """Create control tab with improved UI"""
    
    with gr.Tab("🎮 Control Panel"):
        with gr.Column(scale=1, elem_id="control-tab-container"):
            # Header
            gr.HTML("""
            <div class='section-header'>
                🎮 Robot Control Center
            </div>
            """)
            
            # Mode Selection
            gr.HTML("<h2 class='section-header'>📹 Step 1: Choose Input Method</h2>")
            
            mode_selector = gr.Radio(
                choices=["Upload File", "Record from Jetson"],
                value="Upload File",
                label="Select Input Method",
                interactive=True
            )
            
            # ========================================
            # UPLOAD SECTION
            # ========================================
            with gr.Group(visible=True) as upload_section:
                gr.HTML("<h3>📤 Upload Image or Video</h3>")
                
                upload_file_input = gr.File(label="Select File", file_types=["image", "video"])
                upload_btn = gr.Button("📤 Upload File", variant="secondary", size="lg")
                upload_status = gr.Textbox(label="Status", value="Select an image or video file", lines=2, interactive=False)
                
                with gr.Row():
                    process_image_btn = gr.Button("🖼️ Process Image", variant="primary", size="lg", visible=False)
            
            # ========================================
            # RECORD SECTION - IMPROVED DROPDOWN
            # ========================================
            with gr.Group(visible=False) as record_section:
                gr.HTML("<h3>📹 Record from Jetson Stream</h3>")
                
                with gr.Row():
                    start_recording_btn = gr.Button("🔴 Start Recording", variant="primary", scale=1)
                    stop_recording_btn = gr.Button("⏹️ Stop Recording", variant="stop", scale=1)
                
                recording_status = gr.Textbox(label="Recording Status", value="Ready to record", lines=2, interactive=False)
                
                gr.HTML("<hr style='margin: 20px 0;'>")
                
                gr.HTML("<h3>📂 Select Recorded Video</h3>")
                
                gr.HTML("""
                <div style='background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; margin-bottom: 10px;'>
                    💡 <strong>Tip:</strong> Videos are sorted by newest first. Select a video from the list below.
                </div>
                """)
                
                # CLEAN: Use Radio buttons with scrollable container (much cleaner!)
                video_list = get_video_list()
                video_selector = gr.Radio(
                    choices=video_list,
                    label="🎥 Available Videos",
                    value=video_list[0] if video_list else None,
                    interactive=True,
                    elem_id="video_selector_radio"
                )
                
                with gr.Row():
                    refresh_list_btn = gr.Button("🔄 Refresh List", variant="secondary", size="sm", scale=1)
                    video_info = gr.Textbox(
                        label="📊 Video Count", 
                        value=f"✅ Found {len(video_list)} video(s)" if video_list else "No videos found",
                        lines=1, 
                        interactive=False, 
                        scale=2
                    )
                
                process_video_btn = gr.Button("▶️ Process Selected Video", variant="primary", size="lg")
                processing_status_record = gr.Textbox(label="Status", value="Ready", lines=2, interactive=False)
                
                # Clean CSS for scrollable radio list
                gr.HTML("""
                <style>
                    /* Scrollable radio button container */
                    #video_selector_radio {
                        max-height: 300px !important;
                        overflow-y: auto !important;
                        padding: 10px !important;
                        background: rgba(255,255,255,0.05) !important;
                        border-radius: 8px !important;
                        border: 1px solid rgba(102, 126, 234, 0.3) !important;
                    }
                    
                    #video_selector_radio label {
                        font-size: 14px !important;
                        padding: 8px 12px !important;
                        margin: 4px 0 !important;
                        border-radius: 6px !important;
                        transition: all 0.2s !important;
                        cursor: pointer !important;
                    }
                    
                    #video_selector_radio label:hover {
                        background: rgba(102, 126, 234, 0.1) !important;
                    }
                    
                    #video_selector_radio input[type="radio"]:checked + label {
                        background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%) !important;
                        border-left: 4px solid #667eea !important;
                        font-weight: 600 !important;
                    }
                    
                    /* Custom scrollbar */
                    #video_selector_radio::-webkit-scrollbar {
                        width: 8px !important;
                    }
                    
                    #video_selector_radio::-webkit-scrollbar-track {
                        background: rgba(255,255,255,0.05) !important;
                        border-radius: 10px !important;
                    }
                    
                    #video_selector_radio::-webkit-scrollbar-thumb {
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
                        border-radius: 10px !important;
                    }
                    
                    #video_selector_radio::-webkit-scrollbar-thumb:hover {
                        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%) !important;
                    }
                </style>
                """)
            
            # ========================================
            # RESULTS SECTION
            # ========================================
            with gr.Group(visible=False) as results_section:
                gr.HTML("<h2 class='section-header'>📺 Processing Results</h2>")
                
                gr.HTML("""
                <div class='file-info'>
                    ℹ️ <strong>Current</strong> = This video/image | <strong>Total</strong> = Cumulative across session
                </div>
                """)
                
                with gr.Row():
                    with gr.Column(scale=2):
                        video_preview = gr.Image(label="Preview", type="pil", height=400)
                    
                    with gr.Column(scale=1):
                        current_people_display = gr.Textbox(label="👥 Current Count", value="Current: 0", interactive=False)
                        total_people_display = gr.Textbox(label="📊 Total (Session)", value="Total: 0", interactive=False)
                        frame_progress_display = gr.Textbox(label="📊 Frames", value="0/0", interactive=False)
                        fps_display = gr.Textbox(label="⚡ Speed", value="0 FPS", interactive=False)
                        processing_status_live = gr.Textbox(label="Status", value="Idle", interactive=False)
                
                progress_bar = gr.Slider(minimum=0, maximum=1, value=0, label="Progress", interactive=False)
            
            # ========================================
            # ROBOT CONTROL - IMPROVED (NO TEXTBOX, RESPONSIVE BUTTONS)
            # ========================================
            gr.HTML("<hr style='margin: 40px 0;'>")
            gr.HTML("<h2 class='section-header'>🤖 Robot Control</h2>")
            
            gr.HTML("""
            <div style='background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
                <strong>Select Control Mode:</strong>
                <ul style='margin: 10px 0 0 0; padding-left: 20px;'>
                    <li><strong>🖥️ Manual:</strong> Control with buttons or keyboard (↑↓←→)</li>
                    <li><strong>🎮 PS5:</strong> Control with PS5 controller</li>
                    <li><strong>🤖 Auto:</strong> Autonomous navigation mode</li>
                </ul>
            </div>
            """)
            
            with gr.Row():
                mode_manual_btn = gr.Button("🖥️ Manual", variant="primary", scale=1)
                mode_ps5_btn = gr.Button("🎮 PS5", variant="secondary", scale=1)
                mode_auto_btn = gr.Button("🤖 Auto", variant="secondary", scale=1)
            
            # NO TEXTBOX HERE - Removed!
            
            with gr.Group(elem_id="control-buttons") as control_group:
                with gr.Row():
                    gr.Button("", interactive=False, visible=False)
                    forward_btn = gr.Button("⬆️", variant="primary", scale=2)
                    gr.Button("", interactive=False, visible=False)
                with gr.Row():
                    left_btn = gr.Button("⬅️", variant="secondary")
                    stop_btn = gr.Button("🛑", variant="stop")
                    right_btn = gr.Button("➡️", variant="secondary")
                with gr.Row():
                    gr.Button("", interactive=False, visible=False)
                    backward_btn = gr.Button("⬇️", variant="primary", scale=2)
                    gr.Button("", interactive=False, visible=False)
            
            movement_status = gr.Textbox(label="Movement Status", value="Ready", interactive=False, lines=1)
            
            # JavaScript for keyboard controls
            gr.HTML("""<script>
            window.controlsEnabled=true;window.setControlsEnabled=function(e){window.controlsEnabled=e};
            let keysPressed=new Set(),lastDirection=null;
            function triggerButtonClick(e){if(!window.controlsEnabled)return;document.querySelectorAll("#control-buttons button").forEach(t=>{t.getAttribute("data-direction")===e&&t.click()})}
            document.addEventListener("keydown",function(e){if("INPUT"===e.target.tagName||"TEXTAREA"===e.target.tagName||!window.controlsEnabled)return;
            ["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "].includes(e.key)&&e.preventDefault();
            if(keysPressed.has(e.key))return;keysPressed.add(e.key);let t=null;"ArrowUp"===e.key?t="forward":"ArrowDown"===e.key?t="backward":"ArrowLeft"===e.key?t="left":"ArrowRight"===e.key?t="right":" "===e.key&&(t="stop");
            t&&t!==lastDirection&&(triggerButtonClick(t),lastDirection=t)});
            document.addEventListener("keyup",function(e){keysPressed.delete(e.key);["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.key)&&(triggerButtonClick("stop"),lastDirection="stop")});
            setTimeout(()=>{document.querySelectorAll("#control-buttons button").forEach(e=>{const t=e.textContent.trim();
            t.includes("⬆️")?e.setAttribute("data-direction","forward"):t.includes("⬇️")?e.setAttribute("data-direction","backward"):
            t.includes("⬅️")?e.setAttribute("data-direction","left"):t.includes("➡️")?e.setAttribute("data-direction","right"):
            t.includes("🛑")&&e.setAttribute("data-direction","stop")})},1e3);
            </script>""")
            
            js_executor = gr.HTML(visible=False)
            
            # ========================================
            # EVENT HANDLERS
            # ========================================
            
            mode_selector.change(fn=switch_mode, inputs=[mode_selector], outputs=[upload_section, record_section, results_section])
            upload_btn.click(fn=handle_upload, inputs=[upload_file_input], outputs=[upload_status, video_selector, process_image_btn, results_section])
            process_image_btn.click(fn=process_image_click, outputs=[upload_status, results_section])
            start_recording_btn.click(fn=start_recording, outputs=[recording_status, video_selector])
            stop_recording_btn.click(fn=stop_recording, outputs=[recording_status, video_selector])
            refresh_list_btn.click(fn=refresh_video_list, outputs=[video_selector, video_info])
            process_video_btn.click(fn=process_video_click_from_record, inputs=[video_selector], outputs=[processing_status_record, results_section])
            
            # Auto-refresh
            auto_refresh = gr.Timer(value=0.5, active=True)
            auto_refresh.tick(fn=get_live_stats, outputs=[video_preview, current_people_display, total_people_display,
                                                           frame_progress_display, fps_display, processing_status_live, progress_bar])
            
            # Robot control - IMPROVED with visual feedback
            mode_manual_btn.click(
                fn=lambda: set_mode_with_feedback("manual"),
                outputs=[movement_status, mode_manual_btn, mode_ps5_btn, mode_auto_btn, control_group, js_executor]
            )
            mode_ps5_btn.click(
                fn=lambda: set_mode_with_feedback("ps5"),
                outputs=[movement_status, mode_manual_btn, mode_ps5_btn, mode_auto_btn, control_group, js_executor]
            )
            mode_auto_btn.click(
                fn=lambda: set_mode_with_feedback("auto"),
                outputs=[movement_status, mode_manual_btn, mode_ps5_btn, mode_auto_btn, control_group, js_executor]
            )
            
            forward_btn.click(fn=lambda: robot_controller.send_command("forward"), outputs=movement_status)
            backward_btn.click(fn=lambda: robot_controller.send_command("backward"), outputs=movement_status)
            left_btn.click(fn=lambda: robot_controller.send_command("left"), outputs=movement_status)
            right_btn.click(fn=lambda: robot_controller.send_command("right"), outputs=movement_status)
            stop_btn.click(fn=lambda: robot_controller.send_command("stop"), outputs=movement_status)
        
        return {
            "video_preview": video_preview,
            "progress_bar": progress_bar
        }