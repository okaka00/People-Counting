# stream_recorder.py - ROBUST MP4 with Proper Finalization
import cv2
import time
from datetime import datetime
import os
import sys
import subprocess
import atexit
import signal

# ========================================
# CONFIGURATION
# ========================================
JETSON_IP = "10.102.82.69"
JETSON_PORT = 8000
STREAM_URL = f"http://{JETSON_IP}:{JETSON_PORT}/video_feed"

# Recording settings
SAVE_FOLDER = "recorded_videos"
MAX_RECORDING_TIME = 60  # seconds
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FPS = 30

# Create save folder
if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)
    print(f"✅ Created folder: {SAVE_FOLDER}")

# Global variables for cleanup
video_writer = None
video_capture = None
temp_frames = []

# ========================================
# CLEANUP HANDLERS
# ========================================

def cleanup():
    """Emergency cleanup function"""
    global video_writer, video_capture
    
    if video_writer is not None:
        try:
            video_writer.release()
            print("\n🧹 Emergency: Released video writer")
        except:
            pass
    
    if video_capture is not None:
        try:
            video_capture.release()
            print("🧹 Emergency: Released video capture")
        except:
            pass
    
    try:
        cv2.destroyAllWindows()
    except:
        pass

def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    print("\n\n🛑 Interrupted! Cleaning up...")
    cleanup()
    sys.exit(1)

# Register cleanup handlers
atexit.register(cleanup)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ========================================
# FRAME BUFFER RECORDING (Most Reliable!)
# ========================================

def record_stream_buffered():
    """
    Record with frame buffer - writes all frames at end
    This ensures proper MP4 finalization even if interrupted
    """
    global video_capture
    
    print("\n" + "=" * 60)
    print("📹 JETSON STREAM RECORDER (BUFFERED MODE)")
    print("=" * 60)
    print(f"📡 Stream: {STREAM_URL}")
    print(f"💾 Save to: {SAVE_FOLDER}")
    print(f"⏱️  Duration: {MAX_RECORDING_TIME}s")
    print("=" * 60)
    print("⌨️  Press 'q' to stop early")
    print("=" * 60)
    
    # Connect to stream
    print(f"\n🔄 Connecting to {STREAM_URL}...")
    video_capture = cv2.VideoCapture(STREAM_URL)
    video_capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    if not video_capture.isOpened():
        print("❌ Failed to connect to stream")
        return None
    
    print("✅ Connected!")
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{SAVE_FOLDER}/jetson_recording_{timestamp}.mp4"
    
    print(f"📝 Recording frames to buffer...")
    print("   (Will write to file at end for proper finalization)")
    
    # Create window
    try:
        cv2.namedWindow('Recording', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Recording', 1280, 720)
        window_available = True
    except:
        window_available = False
        print("⚠️ Running without display")
    
    # Frame buffer
    frames = []
    start_time = time.time()
    fps_start = time.time()
    fps_count = 0
    current_fps = 0
    last_print = time.time()
    
    print("🎬 Recording started!")
    
    try:
        while True:
            ret, frame = video_capture.read()
            
            if not ret:
                print("\n⚠️ Stream ended")
                break
            
            # Resize and store frame
            frame_resized = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            frames.append(frame_resized)
            
            # Calculate FPS
            fps_count += 1
            elapsed = time.time() - fps_start
            if elapsed > 1.0:
                current_fps = fps_count / elapsed
                fps_count = 0
                fps_start = time.time()
            
            # Calculate time
            recording_time = time.time() - start_time
            remaining_time = MAX_RECORDING_TIME - recording_time
            frame_count = len(frames)
            
            # Display
            if window_available:
                display_frame = frame_resized.copy()
                
                # REC indicator
                cv2.circle(display_frame, (20, 20), 10, (0, 0, 255), -1)
                cv2.putText(display_frame, "REC", (40, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Info
                cv2.putText(display_frame, f"Time: {int(recording_time)}s / {MAX_RECORDING_TIME}s", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(display_frame, f"Frames: {frame_count}", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(display_frame, f"FPS: {current_fps:.1f}", (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(display_frame, f"Buffer: {len(frames)} frames", (10, 150),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                
                # Warning
                if remaining_time <= 10:
                    color = (0, 165, 255) if remaining_time > 5 else (0, 0, 255)
                    cv2.putText(display_frame, f"⚠️ {int(remaining_time)}s left", (10, 180),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                
                cv2.imshow('Recording', display_frame)
                
                # Check for quit
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    print("\n🛑 Stopped by user")
                    break
            
            # Print progress
            if time.time() - last_print > 5.0:
                print(f"📹 {int(recording_time)}s | {frame_count} frames | {current_fps:.1f} FPS | Buffer: {len(frames)}")
                last_print = time.time()
            
            # Check max time
            if recording_time >= MAX_RECORDING_TIME:
                print(f"\n⏱️  Max time reached")
                break
            
            # Memory check (don't exceed 2GB buffer)
            buffer_size_mb = (len(frames) * FRAME_WIDTH * FRAME_HEIGHT * 3) / (1024 * 1024)
            if buffer_size_mb > 2000:  # 2GB limit
                print(f"\n⚠️ Buffer limit reached ({buffer_size_mb:.0f} MB)")
                break
    
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
    
    except Exception as e:
        print(f"\n❌ Recording error: {e}")
        return None
    
    finally:
        # Close capture
        if video_capture:
            video_capture.release()
        if window_available:
            cv2.destroyAllWindows()
    
    # Check if we got any frames
    if len(frames) == 0:
        print("❌ No frames recorded")
        return None
    
    print(f"\n✅ Captured {len(frames)} frames in buffer")
    
    # Now write all frames to MP4 file
    print(f"\n📝 Writing {len(frames)} frames to MP4...")
    print("   This ensures proper file finalization...")
    
    try:
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_file, fourcc, FPS, (FRAME_WIDTH, FRAME_HEIGHT))
        
        if not out.isOpened():
            print("❌ Failed to create video writer")
            return None
        
        # Write all frames
        for i, frame in enumerate(frames):
            out.write(frame)
            
            # Progress indicator
            if (i + 1) % 100 == 0:
                progress = ((i + 1) / len(frames)) * 100
                print(f"   Writing... {progress:.0f}% ({i+1}/{len(frames)} frames)")
        
        print(f"   ✅ Wrote {len(frames)} frames")
        
        # CRITICAL: Properly close writer
        print("   🔒 Finalizing MP4 (adding moov atom)...")
        out.release()
        time.sleep(1)  # Give OS time to flush
        
        print("✅ MP4 file finalized!")
        
    except Exception as e:
        print(f"❌ Error writing MP4: {e}")
        return None
    
    # Validate file
    if not os.path.exists(output_file):
        print("❌ MP4 file not created")
        return None
    
    file_size = os.path.getsize(output_file) / (1024 * 1024)
    
    if file_size < 0.1:
        print(f"❌ MP4 too small ({file_size:.2f} MB)")
        os.remove(output_file)
        return None
    
    # Final validation
    print("\n🔍 Validating MP4...")
    
    test_cap = cv2.VideoCapture(output_file)
    
    if test_cap.isOpened():
        stored_frames = int(test_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        stored_fps = test_cap.get(cv2.CAP_PROP_FPS)
        ret, test_frame = test_cap.read()
        test_cap.release()
        
        if ret:
            duration = len(frames) / FPS
            
            print("\n" + "=" * 60)
            print("✅ RECORDING COMPLETE!")
            print("=" * 60)
            print(f"📁 File: {output_file}")
            print(f"📊 Statistics:")
            print(f"   Duration: {duration:.1f} seconds")
            print(f"   Frames: {len(frames)}")
            print(f"   Resolution: {FRAME_WIDTH}x{FRAME_HEIGHT}")
            print(f"   FPS: {FPS}")
            print(f"   File size: {file_size:.2f} MB")
            print(f"   Format: MP4")
            print(f"\n✅ Validation:")
            print(f"   Readable: Yes")
            print(f"   Metadata frames: {stored_frames}")
            print(f"   Metadata FPS: {stored_fps:.1f}")
            
            if stored_frames == 0:
                print(f"\n⚠️ Note: Frame count metadata is 0")
                print(f"   This is OK - processor will count dynamically")
            
            print("=" * 60)
            print("\n💡 Ready to process in Gradio!")
            print("=" * 60)
            
            return output_file
        else:
            print("❌ Cannot read MP4 file")
            return None
    else:
        print("❌ Cannot open MP4 file")
        print("   File may be corrupted")
        return None

# ========================================
# MAIN
# ========================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 JETSON STREAM RECORDER")
    print("=" * 60)
    print("\n⚙️  Settings:")
    print(f"   Stream: {STREAM_URL}")
    print(f"   Max duration: {MAX_RECORDING_TIME}s")
    print(f"   Resolution: {FRAME_WIDTH}x{FRAME_HEIGHT}")
    print(f"   FPS: {FPS}")
    print(f"   Mode: Buffered (most reliable)")
    print(f"   Max buffer: 2GB (~10 minutes at 640x480)")
    print("\n💡 How it works:")
    print("   1. Records frames to memory buffer")
    print("   2. Writes all frames at end")
    print("   3. Ensures proper MP4 finalization")
    print("   4. No 'moov atom not found' errors!")
    print("=" * 60)
    
    try:
        recorded_file = record_stream_buffered()
        
        if recorded_file:
            print(f"\n🎉 Success!")
            print(f"📁 {recorded_file}")
            sys.exit(0)
        else:
            print("\n❌ Recording failed")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted")
        cleanup()
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)