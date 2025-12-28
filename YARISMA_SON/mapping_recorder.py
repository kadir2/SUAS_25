import cv2
import redis
import time
from datetime import datetime
import sys
import os
import shutil
import logging

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1920,
    capture_height=1080,
    framerate=59,
    flip_method=0,
    wbmode=6,
    exp_comp=-1.5,
    aelock=False,
    awblock=True,
    sensor_mode=0,
):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} aelock={str(aelock).lower()} "
        f"awblock={awblock} wbmode={wbmode} exposurecompensation={exp_comp} ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, "
        f"height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, format=(string)BGRx ! "
        f"videoconvert ! video/x-raw, format=(string)BGR ! appsink"
    )
class Loggerr:
    def __init__(self):
        self.logger = logging.getLogger('map_video')
        self.logger.setLevel(logging.DEBUG)

        c_handler = logging.StreamHandler()
        log_file_path = 'map_vid.log'
        old_logs_dir = "old_logs_SUAS"

        if not os.path.exists(old_logs_dir):
            os.makedirs(old_logs_dir)
        if os.path.exists(log_file_path):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            new_log_file_path = os.path.join(old_logs_dir, f"map_livee_{timestamp}.log")
            shutil.move(log_file_path, new_log_file_path)

        f_handler = logging.FileHandler(log_file_path)

        c_handler.setLevel(logging.DEBUG)
        f_handler.setLevel(logging.DEBUG)

        # Konsol ve dosya için fonksiyon ve satır numarası gibi detayları içeren format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
        )

        c_handler.setFormatter(formatter)
        f_handler.setFormatter(formatter)

        self.logger.addHandler(c_handler)
        self.logger.addHandler(f_handler)

# Kullanım örneği
logger_instance = Loggerr()
logger = logger_instance.logger






import subprocess, os, time

# ───────── CONFIG ──────────────────────────────────────────────
GROUND_IP   = "100.118.155.118"          # Tailscale IP of ground computer
GROUND_DIR  = "/home/aziz/incoming"      # Directory ground script watches
SSH_USER    = "aziz"                     # User on ground computer
FRAME_RATE_FALLBACK = 30
# ----------------------------------------------------------------

def check_connection():
    print(f"Checking connectivity to {SSH_USER}@{GROUND_IP}...")
    while True:
        try:
            subprocess.check_call(
                ["ssh", "-o", "BatchMode=yes", "-q", f"{SSH_USER}@{GROUND_IP}", "exit"]
            )
            print("Connectivity OK")
            break
        except subprocess.CalledProcessError:
            print("Connectivity failed, retrying in 5 seconds...")
            time.sleep(5)


def send_video(local_path: str):
    """
    Copy file to ground computer, then atomically rename it so the watcher
    starts only after the transfer is complete.  Retries indefinitely on
    any failure with exponential back-off that maxes out at 300 s.
    """
    check_connection()
    tmp = os.path.basename(local_path) + ".part"
    delay = 5                       # seconds; initial back-off
    attempt = 1

    while True:
        try:
            subprocess.check_call([
                "scp", "-q", local_path,
                f"{SSH_USER}@{GROUND_IP}:{GROUND_DIR}/{tmp}"
            ])
            subprocess.check_call([
                "ssh", f"{SSH_USER}@{GROUND_IP}",
                f"mv {GROUND_DIR}/{tmp} {GROUND_DIR}/{os.path.basename(local_path)}"
            ])
            print(f"Video sent → {GROUND_IP}:{GROUND_DIR}")
            break                              # success – exit loop
        except subprocess.CalledProcessError as e:
            print(f"SCP failed (attempt {attempt}): {e}")
        except Exception as e:
            print(f"Unexpected error (attempt {attempt}): {e}")

        attempt += 1
        print(f"Retrying in {delay} s…")
        time.sleep(delay)
        delay = min(delay * 2, 300)   # exponential back-off, max 5 min


def main():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.get('start_rec') == 'False'  # Başlangıçta kayıt bayrağı False
    cap = None
    writer = None

    # Test kısmı - İlk 10 saniye video kaydı yapılıyor
    logger.debug("Test başlatılıyor: 10 saniye video kaydı.")
    pipeline = gstreamer_pipeline()
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        logger.debug("Kamera açılamadı, çıkılıyor.")
        sys.exit(1)

    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"test_video_{now}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30  # FPS bilgisi yoksa 30 varsayılan
    writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    logger.debug(f"[{now}] Test video kaydı başladı → {filename}")

    # 10 saniye video kaydediliyor
    start_time = time.time()
    while time.time() - start_time < 5:
        ret, frame = cap.read()
        if not ret:
            logger.debug("Frame okunamadı, çıkılıyor.")
            break
        writer.write(frame)

    # Test bitiminde kaydı durdurup serbest bırakıyoruz
    logger.debug(f"[{datetime.now().strftime('%H:%M:%S')}] Test kaydı durduruluyor.")
    writer.release()
    cap.release()
    cv2.destroyAllWindows()

    # Ana işlem başlatılıyor
    cap = None
    writer = None
    logger.debug("Ana işlem başlatılıyor. Redis ile iletişim kurulacak.")
    try:
        
        logger.debug("beklemedyiz hacıdayı")
        while True:
            flag = (r.get('start_rec') == 'True')
            logger.debug(f"[{datetime.now().strftime('%H:%M:%S')}] Redndı: {flag}")
            time.sleep(1)  # Redis sorgusunu çok sık yapmamak için bekleme süresi
            if flag:
                break
        
        
        while True:
        # Başlatma: bayrak True olduysa ve cap henüz açılmadıysa
            flag = (r.get('start_rec') == 'True')

            if flag and cap is None:
                logger.debug(f"[{datetime.now().strftime('%H:%M:%S')}] Kayıt başlatılıyor.")
                pipeline = gstreamer_pipeline()
                cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
                if not cap.isOpened():
                    logger.debug("Kamera açılamadı, çıkılıyor.")
                    sys.exit(1)

                # VideoWriter oluştur
                now = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"video_{now}.mp4"
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS) or 0.0  # FPS bilgisi yoksa 30 varsayılan
                writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
                logger.debug(f"[{now}] Kayıt başladı → {filename}")

            # Durdurma: bayrak False olduysa ve cap açıksa
            if not flag and cap is not None:
                logger.debug(f"[{datetime.now().strftime('%H:%M:%S')}] Kayıt durduruluyor ve çıkılıyor.")
                writer.release()
                cap.release()
                cv2.destroyAllWindows()
                send_video(filename)

                break

            # Kaydediliyorsa frame okuyup yaz
            if cap is not None:
                ret, frame = cap.read()
                if not ret:
                    logger.debug("Frame okunamadı, çıkılıyor.")
                    break
                writer.write(frame)
            # Çok sık Redis sorgusunu engellemek için kısa bekleme
            time.sleep(0.05)

    finally:
        # Güvenlik için bir kez daha kapat
        if writer:
            writer.release()
        if cap:
            cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
































#usb ye atankod


# import cv2
# import redis
# import time
# from datetime import datetime
# import sys
# import os
# import shutil
# import logging

# # USB’ye aktarılacak dizin (gerçek mountpoint)
# DEST_DIR = "/media/itunom/1988-D002"


# def gstreamer_pipeline(
#     sensor_id=0,
#     capture_width=4032,
#     capture_height=3040,
#     framerate=19,
#     flip_method=0,
#     wbmode=6,
#     exp_comp=-1.7,
#     aelock=False,
#     awblock=True,
#     sensor_mode=0,
# ):
#     return (
#         f"nvarguscamerasrc sensor-id={sensor_id} aelock={str(aelock).lower()} "
#         f"awblock={str(awblock).lower()} wbmode={wbmode} exposurecompensation={exp_comp} ! "
#         f"video/x-raw(memory:NVMM), width=(int){capture_width}, "
#         f"height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
#         f"nvvidconv flip-method={flip_method} ! "
#         f"video/x-raw, format=(string)BGRx ! "
#         f"videoconvert ! video/x-raw, format=(string)BGR ! appsink"
#     )

# class Loggerr:
#     def __init__(self):
#         self.logger = logging.getLogger('map_video')
#         self.logger.setLevel(logging.DEBUG)

#         c_handler = logging.StreamHandler()
#         log_file_path = 'map_vid.log'
#         old_logs_dir = "old_logs_SUAS"

#         if not os.path.exists(old_logs_dir):
#             os.makedirs(old_logs_dir)
#         if os.path.exists(log_file_path):
#             timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#             new_log_file_path = os.path.join(old_logs_dir, f"map_livee_{timestamp}.log")
#             shutil.move(log_file_path, new_log_file_path)

#         f_handler = logging.FileHandler(log_file_path)
#         c_handler.setLevel(logging.DEBUG)
#         f_handler.setLevel(logging.DEBUG)

#         formatter = logging.Formatter(
#             '%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
#         )
#         c_handler.setFormatter(formatter)
#         f_handler.setFormatter(formatter)

#         self.logger.addHandler(c_handler)
#         self.logger.addHandler(f_handler)

# logger = Loggerr().logger

# def move_to_usb(filepath):
#     try:
#         if not os.path.isdir(DEST_DIR):
#             logger.error(f"USB dizini bulunamadı: {DEST_DIR}")
#             return
#         shutil.move(filepath, DEST_DIR)
#         logger.debug(f"Video USB'ye taşındı: {os.path.basename(filepath)} → {DEST_DIR}")
#     except Exception as e:
#         logger.error(f"Video taşınırken hata: {e}")

# def main():
#     r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

#     # --- TEST KAYDI (10 saniye) ---
#     logger.debug("Test başlatılıyor: 10 saniye video kaydı.")
#     cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
#     if not cap.isOpened():
#         logger.debug("Kamera açılamadı, çıkılıyor.")
#         sys.exit(1)

#     now = datetime.now().strftime('%Y%m%d_%H%M%S')
#     test_filename = f"test_video_{now}.mp4"
#     fourcc = cv2.VideoWriter_fourcc(*'mp4v')
#     width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     fps = cap.get(cv2.CAP_PROP_FPS) or 30
#     writer = cv2.VideoWriter(test_filename, fourcc, fps, (width, height))
#     logger.debug(f"[{now}] Test video kaydı başladı → {test_filename}")

#     start_time = time.time()
#     while time.time() - start_time < 10:
#         ret, frame = cap.read()
#         if not ret:
#             logger.debug("Frame okunamadı, test kaydı sonlandırılıyor.")
#             break
#         writer.write(frame)

#     writer.release()
#     cap.release()
#     cv2.destroyAllWindows()
#     logger.debug("Test kaydı tamamlandı, USB'ye taşınıyor.")
#     move_to_usb(test_filename)

#     # --- ANA İŞLEM: REDIS FLAG VE NORMAL KAYIT ---
#     logger.debug("Ana işlem başlatılıyor. Redis ile iletişim kurulacak.")
#     try:
#         # start_rec True olana dek bekle
#         while r.get('start_rec') != 'True':
#             logger.debug(f"[{datetime.now().strftime('%H:%M:%S')}] Beklemede... start_rec=False")
#             time.sleep(1)

#         # kayıt başlat
#         cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
#         if not cap.isOpened():
#             logger.debug("Kamera açılamadı, çıkılıyor.")
#             sys.exit(1)
#         now = datetime.now().strftime('%Y%m%d_%H%M%S')
#         normal_filename = f"video_{now}.mp4"
#         writer = cv2.VideoWriter(
#             normal_filename,
#             cv2.VideoWriter_fourcc(*'mp4v'),
#             cap.get(cv2.CAP_PROP_FPS) or 30,
#             (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
#         )
#         logger.debug(f"[{now}] Normal kayıt başladı → {normal_filename}")

#         # kayıt devam ederken flag False olana dek
#         while r.get('start_rec') == 'True':
#             ret, frame = cap.read()
#             if not ret:
#                 logger.debug("Frame okunamadı, kayıt durduruluyor.")
#                 break
#             writer.write(frame)
#             time.sleep(0.05)

#         # kayıt durdur
#         writer.release()
#         cap.release()
#         cv2.destroyAllWindows()
#         logger.debug("Normal kayıt tamamlandı, USB'ye taşınıyor.")
#         move_to_usb(normal_filename)

#     finally:
#         if 'writer' in locals() and writer:
#             writer.release()
#         if 'cap' in locals() and cap:
#             cap.release()
#         cv2.destroyAllWindows()

# if __name__ == "__main__":
#     main()
