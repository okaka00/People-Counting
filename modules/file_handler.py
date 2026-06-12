"""
File Upload Handler
Manages image and video file uploads
"""
import os
import shutil
from datetime import datetime
import gradio as gr

class FileUploadHandler:
    """Handles file uploads (images and videos)"""
    
    def __init__(self):
        self.last_uploaded_image = None
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        self.video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
    
    def handle_upload(self, file):
        """
        Handle file upload
        Returns: (status_message, video_dropdown_update, process_button_visibility)
        """
        if file is None:
            return "⚠️ No file uploaded!", gr.update(), gr.update(visible=False)
        
        try:
            original_filename = os.path.basename(file.name)
            file_ext = os.path.splitext(original_filename)[1].lower()
            
            if file_ext in self.image_extensions:
                return self._upload_image(file, original_filename)
            elif file_ext in self.video_extensions:
                return self._upload_video(file, original_filename)
            else:
                return (
                    f"❌ Unsupported file type: {file_ext}\n\n"
                    f"Supported: Images ({', '.join(self.image_extensions)}) "
                    f"or Videos ({', '.join(self.video_extensions)})",
                    gr.update(),
                    gr.update(visible=False)
                )
        
        except Exception as e:
            return f"❌ Upload failed: {str(e)}", gr.update(), gr.update(visible=False)
    
    def _upload_image(self, file, original_filename):
        """Handle image upload"""
        try:
            os.makedirs("uploaded_images", exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"img_{timestamp}_{original_filename}"
            destination = os.path.join("uploaded_images", new_filename)
            
            shutil.copy(file.name, destination)
            self.last_uploaded_image = destination
            
            return (
                f"✅ Image uploaded!\n\n"
                f"📁 Saved as: {new_filename}\n"
                f"💡 Click 'Process Image' button to analyze",
                gr.update(),
                gr.update(visible=True)  # Show process button
            )
        
        except Exception as e:
            return f"❌ Image upload failed: {str(e)}", gr.update(), gr.update(visible=False)
    
    def _upload_video(self, file, original_filename):
        """Handle video upload"""
        try:
            self.last_uploaded_image = None  # Clear image
            os.makedirs("recorded_videos", exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"uploaded_{timestamp}_{original_filename}"
            destination = os.path.join("recorded_videos", new_filename)
            
            shutil.copy(file.name, destination)
            
            # Get video list
            videos = self._get_video_list()
            
            return (
                f"✅ Video uploaded!\n\n"
                f"📁 Saved as: {new_filename}\n"
                f"💡 Select from dropdown and click 'Process Video'",
                gr.update(choices=videos, value=new_filename),
                gr.update(visible=False)  # Hide image process button
            )
        
        except Exception as e:
            return f"❌ Video upload failed: {str(e)}", gr.update(), gr.update(visible=False)
    
    def _get_video_list(self):
        """Get list of videos"""
        if not os.path.exists("recorded_videos"):
            return []
        
        videos = [f for f in os.listdir("recorded_videos") 
                  if f.endswith(tuple(self.video_extensions))]
        videos.sort(key=lambda x: os.path.getmtime(os.path.join("recorded_videos", x)), reverse=True)
        
        return videos
    
    def get_last_image_path(self):
        """Get path of last uploaded image"""
        return self.last_uploaded_image