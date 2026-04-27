import cv2
import threading
import time
import os
import datetime
from ultralytics import YOLO

# Global settings and state
MODEL_PATH = os.path.join("fire_detection_model", "best3.pt")
fire_model = None

# We keep running status and the latest frames + detections for the API
cameras = {
    "pc_camera": {"index": 0, "running": False, "frame": None, "detections": []},
    "webcam": {"index": 1, "running": False, "frame": None, "detections": []}
}

# Notifications storage
notifications = []

def init_model():
    global fire_model
    if fire_model is None:
        try:
            fire_model = YOLO(MODEL_PATH)
            print("YOLO model loaded for cameras.")
        except Exception as e:
            print("Error loading YOLO model:", e)

def camera_loop(cam_id):
    global fire_model, notifications, cameras
    cam_info = cameras[cam_id]
    cap = cv2.VideoCapture(cam_info["index"])
    
    if not cap.isOpened():
        print(f"Cannot open camera {cam_id} (index {cam_info['index']})")
        cam_info["running"] = False
        return

    print(f"Started camera {cam_id}")

    os.makedirs(os.path.join("uploads", "notifications"), exist_ok=True)

    while cam_info["running"]:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue
            
        # Optional: run detection on every Nth frame to save CPU
        detections = []
        fire_detected = False
        if fire_model is not None:
            results = fire_model.predict(frame, imgsz=640, conf=0.4, verbose=False)
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf[0])
                    # Assuming class 0 is fire or just generally detected
                    detections.append({"label": "fire", "confidence": conf, "bbox": box.xyxy[0].tolist()})
                    fire_detected = True
        
        cam_info["detections"] = detections
        cam_info["frame"] = frame.copy()

        # Handle notification saving (throttle it so we don't save 30 images a second)
        if fire_detected:
            # Check last notification time for this cam
            recent = [n for n in notifications if n["source"] == cam_id]
            if not recent or (time.time() - recent[-1]["timestamp"] > 10):
                # Save frame
                timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{cam_id}_{timestamp_str}.jpg"
                filepath = os.path.join("uploads", "notifications", filename)
                
                # Draw boxes for saved image
                save_frame = frame.copy()
                for det in detections:
                    bbox = det["bbox"]
                    cv2.rectangle(save_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (0, 0, 255), 2)
                    cv2.putText(save_frame, "Fire", (int(bbox[0]), int(bbox[1])-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                
                cv2.imwrite(filepath, save_frame)
                
                notifications.append({
                    "id": str(len(notifications) + 1),
                    "source": cam_id,
                    "timestamp": time.time(),
                    "time_str": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "image": f"/static/notifications/{filename}"
                })

        time.sleep(0.05) # ~20 FPS reading

    cap.release()
    print(f"Stopped camera {cam_id}")

def start_camera(cam_id):
    init_model()
    if cam_id in cameras and not cameras[cam_id]["running"]:
        cameras[cam_id]["running"] = True
        t = threading.Thread(target=camera_loop, args=(cam_id,), daemon=True)
        t.start()
        return True
    return False

def stop_camera(cam_id):
    if cam_id in cameras:
        cameras[cam_id]["running"] = False
        return True
    return False

def get_camera_frame_generator(cam_id):
    while True:
        if cam_id not in cameras or not cameras[cam_id]["running"]:
             # Send a blank or warning image if offline
             # For simplicity, we just sleep. The frontend might timeout.
             time.sleep(1)
             continue
             
        frame = cameras[cam_id]["frame"]
        if frame is not None:
            # Draw detections
            draw_frame = frame.copy()
            for det in cameras[cam_id]["detections"]:
                bbox = det["bbox"]
                cv2.rectangle(draw_frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (0, 0, 255), 2)
            
            ret, buffer = cv2.imencode('.jpg', draw_frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
             time.sleep(0.1)

def get_notifications():
    # Return reverse chronological order
    return notifications[::-1]
