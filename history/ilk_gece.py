import os
import re
import time
import cv2
from mavlinkHandler import MAVLinkHandlerDronekit as mavlinkHandler
from ultralytics import YOLO
import redis
import csv

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=3040,
    capture_height=2160,
    framerate=20,
    flip_method=2,
    awb_mode=0,
    exp_comp=0,
    aelock=False,
    awblock=False,
):
    """
    Return GStreamer pipeline string for nvarguscamerasrc
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} aelock=true awblock=true wbmode=-1 exposurecompensation=0 ee-mode=1 ee-strength=1 tnr-mode=1 tnr-strength=1 ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! appsink"
    )

pipeline = gstreamer_pipeline(
    sensor_id=0,
        capture_width=4056,
        capture_height=3040,
        framerate=21,
        flip_method=2
    )
print(cv2.getBuildInformation())
print(f"Opening camera with pipeline:\n{pipeline}")
cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
if not cap.isOpened():
    print("Error: Unable to open camera for live preview.")
    

# --- Run index belirle ---
max_idx = 1
for name in os.listdir('.'):
    if os.path.isdir(name):
        m = re.match(r'^images(\d+)$', name)
        if m:
            idx = int(m.group(1))
            if idx > max_idx:
                max_idx = idx
run_idx = max_idx + 1

# --- Yeni klasör ve dosya isimleri ---
img_dir  = f"images{run_idx}"
csv_path = f"output{run_idx}.csv"

os.makedirs(img_dir, exist_ok=True)

# --- CSV başlık satırı oluştur ---
with open(csv_path, mode='w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['timestamp','latitude','longitude','altitude','yaw','counter'])

# --- MAVLink, model, Redis init ---
vehicle = mavlinkHandler("/dev/ttyACM0")
model   = YOLO("yolo11x.pt")
r       = redis.Redis(host='localhost', port=6379, db=0)

# --- POSHOLD modunu bekle ---
while True:
    mod = vehicle.get_mode()
    print(mod)
    time.sleep(0.5)
    if mod == "POSHOLD":
        time.sleep(5)
        break

# --- Görüntü yakalama döngüsü ---
counter = 0


while counter <= 100000:
    ret, frame = cap.read()
    if not ret:
        break

    # Nesne tespiti ve kaydetme
    results   = model.predict(source=frame, conf=0.5)
    annotated = results[0].plot()
    cv2.imwrite(f"{img_dir}/frame{counter}.jpg", annotated)
    cv2.imwrite(f"{img_dir}/raw{counter}.jpg", frame)

    # Konum ve yön bilgisi
    lat, lon, alt = vehicle.get_location()
    yaw           = vehicle.get_heading()
    ts            = time.strftime("%Y%m%d_%H%M%S")

    # CSV’ye satır ekle
    with open(csv_path, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([ts, lat, lon, alt, yaw, counter])

    print(f"[{ts}] Kayıt #{counter}: ({lat}, {lon}, {alt}), yaw={yaw}")

    counter += 1
    time.sleep(1)

    # Mod dışına çıkılırsa POSHOLD bekle
    if vehicle.get_mode() != "POSHOLD":
        while vehicle.get_mode() != "POSHOLD":
            time.sleep(0.5)
        time.sleep(5)

cap.release()
cv2.destroyAllWindows()
