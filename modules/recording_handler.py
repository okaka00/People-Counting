"""
Recording Handler - IMPROVED
Manages Jetson stream recording with video validation
"""
import subprocess
import os
import time
import cv2
import gradio as gr

class RecordingHandler:
    """Handles video recording from Jetson stream with validation"""
    
    def __init__(self):
        self.recorder_process = None
        self.recording_active = False
        self.recorder_script = "stream_recorder.py"
    
    def start_recording(self):
        """Start recording from Jetson stream"""
        if self.recording_active:
            return "⚠️ Recording already active!", gr.update()
        
        if not os.path.exists(self.recorder_script):
            return f"❌ Error: {self.recorder_script} not found!\n\nMake sure stream_recorder.py exists", gr.update()
        
        try:
            # Start recorder subprocess
            self.recorder_process = subprocess.Popen(
                ['python', self.recorder_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.recording_active = True
            
            return (
                "✅ Recording Started!\n\n"
                "📹 Recording from Jetson stream\n"
                "⏱️ Duration: 60s (or press 'Q' in window)\n"
                "💾 Saving to: recorded_videos/\n\n"
                "ℹ️ Video will be validated after recording",
                gr.update()
            )
        
        except Exception as e:
            return f"❌ Error starting recording:\n{str(e)}", gr.update()
    
    def stop_recording(self):
        """Stop recording and validate video"""
        if not self.recording_active:
            return "⚠️ No active recording", gr.update()
        
        try:
            if self.recorder_process:
                # Terminate process
                self.recorder_process.terminate()
                
                try:
                    # Wait for process to finish
                    self.recorder_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't stop
                    self.recorder_process.kill()
                    self.recorder_process.wait()
            
            self.recording_active = False
            
            # Wait for file to be fully saved and processed
            print("⏳ Waiting for video to finalize...")
            time.sleep(3)
            
            # Get updated video list
            videos = self._get_video_list()
            
            if not videos:
                return (
                    "⚠️ Recording stopped but no video found!\n\n"
                    "Check console for errors.",
                    gr.update(choices=[], value=None)
                )
            
            # Validate the most recent video
            latest_video = videos[0]
            validation_result = self._validate_video(latest_video)
            
            return (
                f"✅ Recording stopped!\n\n"
                f"📁 Video: {latest_video}\n\n"
                f"{validation_result}\n\n"
                f"💡 Select from dropdown and click 'Process Video'",
                gr.update(choices=videos, value=latest_video)
            )
        
        except Exception as e:
            self.recording_active = False
            return f"❌ Error stopping recording:\n{str(e)}", gr.update()
    
    def _get_video_list(self):
        """Get list of recorded videos"""
        if not os.path.exists("recorded_videos"):
            return []
        
        videos = [f for f in os.listdir("recorded_videos") 
                  if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))]
        videos.sort(key=lambda x: os.path.getmtime(os.path.join("recorded_videos", x)), reverse=True)
        
        return videos
    
    def _validate_video(self, video_name):
        """
        Validate video file and check frame count
        Returns validation status message
        """
        video_path = os.path.join("recorded_videos", video_name)
        
        try:
            # Check file size
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            
            if file_size_mb < 0.1:
                return f"⚠️ Warning: Video is very small ({file_size_mb:.2f} MB)"
            
            # Check if video can be opened
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                cap.release()
                return "❌ Error: Cannot open video file"
            
            # Get video properties
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Try to read first frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return "❌ Error: Cannot read video frames"
            
            # Build validation message
            duration = frame_count / fps if fps > 0 and frame_count > 0 else 0
            
            validation_msg = "📊 Validation:\n"
            validation_msg += f"   ✅ Size: {file_size_mb:.2f} MB\n"
            validation_msg += f"   ✅ Resolution: {width}x{height}\n"
            validation_msg += f"   ✅ FPS: {fps:.1f}\n"
            
            if frame_count == 0:
                validation_msg += "   ⚠️ Frame count: Unknown (will auto-detect during processing)\n"
            else:
                validation_msg += f"   ✅ Frames: {frame_count} (~{duration:.1f}s)\n"
            
            validation_msg += "   ✅ Readable: Yes"
            
            return validation_msg
        
        except Exception as e:
            return f"❌ Validation error: {str(e)}"
    
    def validate_all_videos(self):
        """Validate all videos in recorded_videos folder"""
        videos = self._get_video_list()
        
        if not videos:
            return "No videos found"
        
        results = []
        for video in videos:
            result = self._validate_video(video)
            results.append(f"\n{video}:\n{result}")
        
        return "\n".join(results)
    
    def is_recording(self):
        """Check if currently recording"""
        return self.recording_active