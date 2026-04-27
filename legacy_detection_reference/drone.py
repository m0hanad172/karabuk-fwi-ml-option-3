import cv2
import threading
import time
from djitellopy import Tello
from ultralytics import YOLO
import os
import datetime
import time as time_mod
from cameras import notifications# ==== Initialize Drone (lazy init, not on import) ====
tello = None
fire_model = YOLO("fire_detection_model/best3.pt")

# ==== Shared state ====
drone_running = False
frame = None
last_drone_frame = None
last_alert_ts = 0


def init_drone():
    """Initialize Tello connection if not already connected."""
    global tello
    if tello is None:
        tello = Tello()
        tello.connect()
        print(f"🔋 Battery: {tello.get_battery()}%")
    return tello

last_detections = []

def capture_frames():
    global frame, last_drone_frame, drone_running, tello, last_detections
    tello = init_drone()
    tello.streamon()
    time.sleep(2)
    cap = tello.get_frame_read()

    while drone_running:
        img = cap.frame
        if img is not None:
            img = cv2.resize(img, (640, 480))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            last_drone_frame = img.copy()

            #  YOLO fire detection
            results = fire_model.predict(img, imgsz=640, conf=0.4, verbose=False)
            detections = []
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = [int(x) for x in box.xyxy[0]]
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(img, f"FIRE {conf:.2f}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    detections.append({
                        "label": "fire",
                        "confidence": conf,
                        "bbox": [x1, y1, x2, y2]
                    })

            if len(detections) > 0:
                # Check recent drone notifications
                recent = [n for n in notifications if n["source"] == "drone"]
                if not recent or (time.time() - recent[-1]["timestamp"] > 10):
                    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"drone_{timestamp_str}.jpg"
                    os.makedirs(os.path.join("uploads", "notifications"), exist_ok=True)
                    filepath = os.path.join("uploads", "notifications", filename)
                    # Convert RGB back to BGR for saving
                    cv2.imwrite(filepath, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                    notifications.append({
                        "id": str(len(notifications) + 1),
                        "source": "drone",
                        "timestamp": time.time(),
                        "time_str": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "image": f"/static/notifications/{filename}"
                    })

            # update global states
            last_detections = detections
            last_drone_frame = img.copy()
            _, jpeg = cv2.imencode(".jpg", img)
            frame = jpeg.tobytes()

    #  safely stop stream
    try:
        tello.streamoff()
    except Exception as e:
        print(f"[WARN] Could not stop stream after loop: {e}")


def get_last_detections():
    global last_detections
    return last_detections


def auto_takeoff_and_land():
    """Take off, hover for 60 sec, then land"""
    global tello
    try:
        #  remove: tello = init_drone()
        if tello is None:
            print("[ERROR] Tello not initialized")
            return
        
        #  wait until video is streaming before takeoff
        time.sleep(5)

        print("🚁 Taking off...")
        tello.takeoff()
        tello.send_rc_control(0,0,0,0)

        print("🚁 Hovering for 60 seconds...")
        time.sleep(20)

        print("🚁 Landing...")
        tello.land()
        print(" Mission complete")

    except Exception as e:
        print(f"[ERROR] Auto takeoff/land failed: {e}")



def start_drone():
    """Start drone streaming + detection, and run auto mission"""
    global drone_running, tello
    if not drone_running:
        drone_running = True

        #  Initialize drone here once
        tello = init_drone()

        thread = threading.Thread(target=capture_frames, daemon=True)
        thread.start()

        # #  Run mission in parallel
        # mission_thread = threading.Thread(target=auto_takeoff_and_land, daemon=True)
        # mission_thread.start()

    return {"status": "started"}




def stop_drone():
    """Stop drone streaming safely"""
    global drone_running, tello
    drone_running = False
    if tello is not None:
        try:
            # Only stop stream if still connected
            tello.streamoff()
        except Exception as e:
            print(f"[WARN] Could not stop stream: {e}")
    return {"status": "stopped"}



def get_frame_generator():
    """ Stream the YOLO-annotated frames as MJPEG """
    global frame
    while True:
        if frame is None:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )


def get_last_frame():
    global last_drone_frame
    return last_drone_frame
