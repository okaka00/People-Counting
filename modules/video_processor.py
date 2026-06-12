"""
Video Processing Utilities
Handles YOLO + DeepSORT processing for images and videos
"""
import cv2
import numpy as np
import torch
from deep_sort_realtime.deepsort_tracker import DeepSort
from PIL import Image
import gc
import os
import time
from datetime import datetime

class VideoProcessor:
    """Handles video and image processing with YOLO + DeepSORT"""
    
    def __init__(self):
        self.yolo_model = None
        self.deep_sort = None
        
    def load_models(self):
        """Load YOLO and DeepSORT models"""
        print("🔄 Loading YOLO...")
        self.yolo_model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
        self.yolo_model.conf = 0.5
        self.yolo_model.classes = [0]  # Person class only
        
        if torch.cuda.is_available():
            self.yolo_model.cuda()
            print("✅ Using GPU")
        else:
            print("✅ Using CPU")
        
        print("🔄 Loading DeepSORT...")
        self.deep_sort = DeepSort(
            max_age=30,
            n_init=3,
            max_iou_distance=0.7,
            embedder="mobilenet",
            half=True,
            embedder_gpu=torch.cuda.is_available(),
            max_cosine_distance=0.4
        )
        print("✅ Models loaded")
    
    def process_image(self, image_path, output_path):
        """
        Process single image with YOLO detection
        Returns: (people_count, processed_image_pil)
        """
        if self.yolo_model is None:
            self.load_models()
        
        # Read image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError("Cannot read image")
        
        # YOLO detection
        with torch.no_grad():
            results = self.yolo_model(image)
        
        detections = results.xyxy[0].cpu().numpy()
        
        # Count and draw
        people_count = 0
        processed_image = image.copy()
        
        for det in detections:
            if int(det[5]) == 0:  # Person class
                people_count += 1
                x1, y1, x2, y2, conf = det[:5]
                
                # Draw bounding box
                cv2.rectangle(processed_image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)
                cv2.putText(processed_image, f"Person #{people_count}", (int(x1), int(y1) - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Add overlay
        cv2.putText(processed_image, f"TOTAL People: {people_count}", (20, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 4)
        
        # Save
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, processed_image)
        
        # Convert to PIL
        frame_rgb = cv2.cvtColor(processed_image, cv2.COLOR_BGR2RGB)
        frame_pil = Image.fromarray(frame_rgb)
        
        return people_count, frame_pil
    
    def process_video(self, video_path, output_path, progress_callback=None):
        if self.yolo_model is None or self.deep_sort is None:
            self.load_models()
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Cannot open video")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Setup output
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, video_fps, (width, height))
        
        # Process
        unique_ids = set()
        count_history = []
        frame_number = 0
        fps_calc = 0
        fps_start = time.time()
        fps_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_number += 1
            
            # YOLO detection
            with torch.no_grad():
                results = self.yolo_model(frame)
            
            detections = results.xyxy[0].cpu().numpy()
            
            # DeepSORT
            deep_sort_detections = []
            for det in detections:
                if int(det[5]) == 0:
                    x1, y1, x2, y2, conf = det[:5]
                    w, h = x2 - x1, y2 - y1
                    deep_sort_detections.append(([x1, y1, w, h], conf, 0))
            
            tracks = self.deep_sort.update_tracks(deep_sort_detections, frame=frame)
            
            # Count and draw
            people_count = 0
            processed_frame = frame.copy()
            
            for track in tracks:
                if not track.is_confirmed():
                    continue
                
                people_count += 1
                track_id = track.track_id
                unique_ids.add(track_id)
                
                ltrb = track.to_ltrb()
                x1, y1, x2, y2 = int(ltrb[0]), int(ltrb[1]), int(ltrb[2]), int(ltrb[3])
                
                cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(processed_frame, f"ID: {track_id}", (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            count_history.append(people_count)
            
            # FPS
            fps_count += 1
            if time.time() - fps_start > 1.0:
                fps_calc = fps_count / (time.time() - fps_start)
                fps_count = 0
                fps_start = time.time()
            
            # Progress
            progress = (frame_number / total_frames) * 100
            
            # Overlay
            cv2.putText(processed_frame, f"TOTAL Unique: {len(unique_ids)}", (10, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
            cv2.putText(processed_frame, f"Current Frame: {people_count}", (10, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
            cv2.putText(processed_frame, f"FPS: {fps_calc:.1f}", (10, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(processed_frame, f"{frame_number}/{total_frames}", (10, 160),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            cv2.putText(processed_frame, f"{progress:.1f}%", (10, 200),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Convert for callback
            frame_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            frame_pil = Image.fromarray(frame_rgb)
            frame_pil = frame_pil.resize((640, 480), Image.LANCZOS)
            
            # Callback
            if progress_callback:
                progress_callback(frame_number, total_frames, people_count, len(unique_ids), frame_pil, fps_calc)
            
            # Save
            out.write(processed_frame)
            
            # Cleanup
            if frame_number % 100 == 0:
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        
        # Cleanup
        cap.release()
        out.release()
        gc.collect()
        
        # Stats
        return {
            "total_frames": frame_number,
            "unique_people": len(unique_ids),
            "avg_per_frame": np.mean(count_history) if count_history else 0,
            "max_per_frame": max(count_history) if count_history else 0
        }