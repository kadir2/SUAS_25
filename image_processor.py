import redis
import time
import json
import os
import glob
import pandas as pd
import torch
from ultralytics import YOLO
import shutil
import cv2
import numpy as np
import struct
import logging
from datetime import datetime


class Loggerr:
    def __init__(self):
        # Logger oluştur
        self.logger = logging.Logger('Image_Processor')
        self.logger.setLevel(logging.DEBUG)  # Log seviyesi DEBUG olarak ayarlanır
        
        # Handlers: Konsol ve Dosya
        c_handler = logging.StreamHandler()  # Konsol için handler
        log_file_path = 'Image_Processor.log'  # Log dosyasının adı
        old_logs_dir = "old_logs_SUAS"  # Eski log dosyalarının taşınacağı klasör

        # Eski log dosyalarını yedekle
        if not os.path.exists(old_logs_dir):  # Eğer klasör yoksa oluştur
            os.makedirs(old_logs_dir)
        if os.path.exists(log_file_path):  # Eğer log dosyası varsa
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # Zaman damgası oluştur
            new_log_file_name = f"Image_Processor_{timestamp}.log"  # Yeni log dosyasının adı
            new_log_file_path = os.path.join(old_logs_dir, new_log_file_name)  # Yeni log dosyasının yolu
            shutil.move(log_file_path, new_log_file_path)  # Eski log dosyasını taşı
        
        f_handler = logging.FileHandler(log_file_path)  # Log dosyasına handler
        
        # Seviyeleri belirle
        c_handler.setLevel(logging.DEBUG)  # Konsola yazdırılacak log seviyesi
        f_handler.setLevel(logging.DEBUG)  # Dosyaya yazdırılacak log seviyesi
        
        # Formatlar
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')  # Konsol formatı
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s') # dosyaya yazdırılacak log formatı

        
        # Formatları handler'lara ekle
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)
        
        # Handler'ları logger'a ekle
        self.logger.addHandler(c_handler)
        self.logger.addHandler(f_handler)

logger_instance = Loggerr()  # Logger nesnesi oluştur
logger = logger_instance.logger   # Logger nesnesini al


# **Redis Bağlantısı**
def process_image(file_path, model, results_list, count, tile_size=1280, overlap=0.5, tolerance=10, counter=0): 
    """
    Verilen dosya yolundaki resmi tile/sliding-window ile işler,
    her bir ROI için sınıf adı, confidence ve bounding-box merkez koordinatlarını
    results_list'e ekler (orijinal resim koordinatlarına göre).

    center_x ve center_y integer’a çevrilir. Eğer mevcut results_list içindeki
    herhangi bir öğeyle |center_x1 - center_x2| <= tolerance ve
    |center_y1 - center_y2| <= tolerance ise o deteksiyon atlanır.
    """
    logger.debug(f"Processing image (tiled): {file_path}")
    img = cv2.imread(file_path)
    h, w, _ = img.shape
    stride = int(tile_size * (1 - overlap))


                    # 2) Draw full‐frame detections & save
    os.makedirs(f'yololu_goruntuler{counter}', exist_ok=True)

    for y in range(0, max(1, h - tile_size + 1), stride):
        for x in range(0, max(1, w - tile_size + 1), stride):
            y2 = min(y + tile_size, h)
            x2 = min(x + tile_size, w)
            crop = img[y:y2, x:x2]

            # exclude surfboard(37) and bench(13)
            results = model.predict(crop, conf=0.01)

            dets = results
            for det in dets:
                names = det.names
                for box in det.boxes:
                    # get coords
                    xmin, ymin, xmax, ymax = box.xyxy[0].cpu().numpy().astype(int)
                    conf = round(box.conf.item(), 3)
                    cls_id = int(box.cls.item())
                    label = f"{names[cls_id]} {conf}"
                    # draw
                    cv2.rectangle(crop, (xmin, ymin), (xmax, ymax), (0,255,0), 2)
                    cv2.putText(crop, label, (xmin, max(ymin-5,0)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
            save_path = os.path.join(f'yololu_goruntuler{counter}', os.path.basename(f"{count}_{y}_{x}.jpg"))
            cv2.imwrite(save_path, crop)
            
            for result in results:
                names = result.names
                for box in result.boxes:
                    xmin, ymin, xmax, ymax = box.xyxy[0].cpu().numpy()
                    conf   = box.conf.item()
                    conf = round(conf, 3)
                    cls_id = int(box.cls.item())
                    cls_name = names[cls_id]

                    # Orijinal koordinatlara dönüştür
                    gxmin, gymin = xmin + x, ymin + y
                    gxmax, gymax = xmax + x, ymax + y

                    # Merkez noktaları (float)
                    cx = (gxmin + gxmax) / 2
                    cy = (gymin + gymax) / 2

                    # Tam sayı kısmını al
                    icx, icy = int(cx), int(cy)

                    # Aynı nesneyi bulmaya çalış
                    duplicate_idx = None
                    for idx, prev in enumerate(results_list):
                        if prev["class_name"] == cls_name and prev["image"] == os.path.basename(file_path):
                            duplicate_idx = idx
                            break

                    if duplicate_idx is not None:
                        # Aynı nesne, confidence en yüksek olana güncelle
                        if conf > results_list[duplicate_idx]["confidence"]:
                            results_list[duplicate_idx].update({
                                "image":      os.path.basename(file_path),
                                "confidence": conf
                            })
                    else:
                        if cls_name == "bench" or cls_name == "surfboard" or cls_name == "bird" or cls_name == "tv":
                            continue
                        # Yeni nesne
                        results_list.append({
                            "image":      os.path.basename(file_path),
                            "class_name": cls_name,
                            "confidence": conf,
                            "center_x":   icx,
                            "center_y":   icy
                        })

    return results_list

def main():
    # config.json'dan ayarları yükle
    with open('config.json') as f:
        config = json.load(f)
    
    counter = config['counter']
    image_count = config['image_count']
    image_dir   = config['image_dir'] + str(counter)
    # ----------------- added -----------------
    os.makedirs(image_dir, exist_ok=True)
    # -----------------------------------------
    image_pattern = config['image_pattern']
    full_pattern  = os.path.join(image_dir, image_pattern)
    

    # klasörü temizle
    # if os.path.isdir(image_dir) and os.listdir(image_dir):
    #     for item in os.listdir(image_dir):
    #         item_path = os.path.join(image_dir, item)
    #         try:
    #             if os.path.isfile(item_path) or os.path.islink(item_path):
    #                 os.unlink(item_path)
    #             elif os.path.isdir(item_path):
    #                 shutil.rmtree(item_path)
    #         except Exception as e:
    #             logger.debug(f"{item_path} silinemedi. Hata: {e}")
    #     logger.debug(f"{image_dir} klasörü temizlendi.")
    # else:
    #     logger.debug(f"{image_dir} ya yok ya da zaten boş.")

    # CSV'i temizle
    # if os.path.isfile("detections.csv") and os.path.getsize("detections.csv") > 0:
    #     open("detections.csv",'w').close()
    #     logger.debug("detections.csv temizlendi.")
    # else:
    #     logger.debug("detections.csv ya yok ya da zaten boş.")

    # Redis bağlantısı
    r = redis.StrictRedis(host='localhost', port=6379, db=0)

    # Modeli yükle
    logger.debug("Loading YOLO model...")
    # /home/itunom/Desktop/System/yolo11x.pt
    model = YOLO("yolo11x.pt").to("cuda")

    # start_ip bekle
    logger.debug("Waiting for 'start_ip'...")
    while True:
        if r.get('start_ip') and r.get('start_ip').decode() == 'True':
            break
        time.sleep(1)

    detection_results = []
    existing_files  = set(glob.glob(full_pattern))
    processed_files = set()

    logger.debug(f"Watching {image_dir} for up to {image_count} new images...")
    while len(processed_files) < image_count:
        current = set(glob.glob(full_pattern))
        new_files = current - existing_files - processed_files

        if new_files:
            for file_path in sorted(new_files):
                # 1) Tiled detection as before
                detection_results = process_image(file_path, model, detection_results,len(processed_files),counter=counter)
                
                # 3) mark as processed
                processed_files.add(file_path)
                logger.debug(f"Processed {file_path} ({len(processed_files)}/{image_count})")
                if len(processed_files) >= image_count:
                    break
        time.sleep(0.5)

    logger.debug(f"All {image_count} images processed.")

    # DataFrame & CSV
    df = pd.DataFrame(detection_results)
    df = df.sort_values(by="confidence", ascending=False)

    # CSV dosya adı config’den okunuyor
    counter = config['counter']
    detection_path = config['detection_file'] + str(counter) + ".csv"
    df.to_csv(detection_path, index=False)
    logger.debug(f"Saved {detection_path}")

    # bitiş sinyali
    r.set('ip_done', 'True')


if __name__ == "__main__":
    main()
