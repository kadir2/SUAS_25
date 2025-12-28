import cv2
import os
import time
from datetime import datetime

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=3840,
    capture_height=2160,
    framerate=29,
    flip_method=0,
    awb_mode=0,
    exp_comp=0,
    aelock=False,
    awblock=False,
    sensor_mode=0,

):
    """
    Return GStreamer pipeline string for nvarguscamerasrc
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} aelock=false awblock=true wbmode=0 exposurecompensation=-1 ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! appsink"
    )

pipeline = gstreamer_pipeline()

cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

def take_photo_opencv(folder, index):
        try:    
            # Kamera ısınsın diye 3 saniye boyunca sürekli frame oku
            print("fonksiyon çalıştı")
            time.sleep(0.5)
            start_time = time.time()
            while time.time() - start_time <= 2.5:
                if cap.isOpened():
                    print(f"cap okunacak süre: {time.time() - start_time:.2f} saniye")
                    cap.read()
                    print("Kamera ısındı, frame okundu.")
                else:
                    print("Error: Unable to open camera for warm-up.")
                    return
            print("whileden çıkıldı")
            # Klasör yoksa oluştur
            if not os.path.exists(folder):
                os.makedirs(folder)
            print("Klasör oluşturuldu")
            if not cap.isOpened():
                print("Error: Unable to open camera for live preview.")
                cap.release()
                return

            ret, frame = cap.read()
            print("frame okundu")
            if not ret or frame is None:
                print("Error: Unable to read frame from camera.")
                cap.release()
                return

            img_path = os.path.join(folder, f"image_{index}.jpg")
            print(f"Resim kaydedilecek yol: {img_path}")
            cv2.imwrite(img_path, frame)
            print(f"Saved photo to {img_path}")
        except Exception as e:
            print(f"Error in take_photo_opencv: {e}")

take_photo_opencv("test_folder", 2)

print(f"Fotoğraf çekme işlemi tamamlandı. timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")