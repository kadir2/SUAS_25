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
import sys
import logging
from datetime import datetime


class Loggerr:
    def __init__(self):
        # Logger oluştur
        self.logger = logging.getLogger('Image_Processor')
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
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')  # Dosyaya yazdırılacak log formatı
        
        # Formatları handler'lara ekle
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)
        
        # Handler'ları logger'a ekle
        self.logger.addHandler(c_handler)
        self.logger.addHandler(f_handler)

logger_instance = Loggerr()  # Logger nesnesi oluştur
logger = logger_instance.logger  # Logger nesnesini al




# **Redis Bağlantısı**
def process_image(file_path, model, results_list, count, tile_size=4032, overlap=0, tolerance=10, counter=0): 
    
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
            results = model.predict(crop, conf=0.01, iou=0.5)  # NMS için iou=0.5

            # Kutuları ve confidence'ları topla
            dets = []
            for det in results:
                names = det.names
                for box in det.boxes:
                    xmin, ymin, xmax, ymax = box.xyxy[0].cpu().numpy().astype(int)
                    conf = round(box.conf.item(), 3)
                    cls_id = int(box.cls.item())
                    dets.append({
                        "xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                        "conf": conf, "cls_id": cls_id, "name": names[cls_id]
                    })

            # İç içe kutuları filtrele (en yüksek confidence olanı seç)
            filtered_dets = []
            for i, det in enumerate(dets):
                keep = True
                for j, other in enumerate(dets):
                    if i == j:
                        continue
                    # IoU hesaplama
                    x1 = max(det["xmin"], other["xmin"])
                    y1 = max(det["ymin"], other["ymin"])
                    x2 = min(det["xmax"], other["xmax"])
                    y2 = min(det["ymax"], other["ymax"])
                    intersection = max(0, x2 - x1) * max(0, y2 - y1)
                    area1 = (det["xmax"] - det["xmin"]) * (det["ymax"] - det["ymin"])
                    area2 = (other["xmax"] - other["xmin"]) * (other["ymax"] - other["ymin"])
                    union = area1 + area2 - intersection
                    iou = intersection / union if union > 0 else 0

                    if iou > 0.5 and det["cls_id"] == other["cls_id"] and other["conf"] > det["conf"]:
                        keep = False
                        break
                if keep:
                    filtered_dets.append(det)

            # Filtrelenmiş kutuları çiz
            text_positions = []
            for det in filtered_dets:
                xmin, ymin, xmax, ymax = det["xmin"], det["ymin"], det["xmax"], det["ymax"]
                conf = det["conf"]
                label = f"{det['name']} {conf}"

                # draw with blue color
                cv2.rectangle(crop, (xmin, ymin), (xmax, ymax), (255, 0, 0), 2)  # Mavi kutu

                # Yazı boyutlarını hesapla
                font_scale = 0.8
                thickness = 3
                (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)

                # Yazı pozisyonunu belirle (üstte, değilse altta veya yanda)
                text_x = xmin
                text_y = max(ymin - 5, text_height)  # Varsayılan: kutunun üstü
                text_rect = (text_x, text_y - text_height, text_x + text_width, text_y)

                # Çakışma kontrolü
                for pos in text_positions:
                    px, py, pw, ph = pos
                    if (text_rect[0] < px + pw and text_rect[0] + text_width > px and
                        text_rect[1] < py + ph and text_rect[1] + text_height > py):
                        # Çakışma varsa, yazıyı kutunun altına taşı
                        text_y = ymax + text_height + 5
                        text_rect = (text_x, text_y - text_height, text_x + text_width, text_y)
                        if text_y + text_height > crop.shape[0]:  # Eğer altta yer yoksa, sağa taşı
                            text_x = xmax + 5
                            text_y = ymin
                            text_rect = (text_x, text_y - text_height, text_x + text_width, text_y)

                # Arka plan kutusu çiz (yarı saydam beyaz)
                cv2.rectangle(crop, (text_rect[0], text_rect[1]), (text_rect[2], text_rect[3]), (255, 255, 255, 0.7), -1)
                # Yazıyı çiz
                cv2.putText(crop, label, (text_x, text_y),
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 0, 0), thickness)  # Mavi yazı
                # Pozisyonu kaydet
                text_positions.append(text_rect)

            save_path = os.path.join(f'yololu_goruntuler{counter}', os.path.basename(f"{count}_{y}_{x}.jpg"))
            cv2.imwrite(save_path, crop)
            
            for result in results:
                names = result.names
                for box in result.boxes:
                    xmin, ymin, xmax, ymax = box.xyxy[0].cpu().numpy()
                    conf = box.conf.item()
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
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    r.set('sicti', 'False')
    # config.json'dan ayarları yükle
    with open('config.json') as f:
        config = json.load(f)
    
    counter = config['counter']
    image_count = config['image_count']
    image_dir = config['image_dir'] + str(counter)
    # ----------------- added -----------------
    os.makedirs(image_dir, exist_ok=True)
    # -----------------------------------------
    image_pattern = config['image_pattern']
    full_pattern = os.path.join(image_dir, image_pattern)

    # Redis bağlantısı
   

    # Modeli yükle
    logger.debug("Loading YOLO model...")
    model = YOLO("yolo11x.pt").to("cuda")

    # start_ip bekle
    logger.debug("Waiting for 'start_ip'...")
    while True:
        if r.get('start_ip') and r.get('start_ip').decode() == 'True':
            break
        time.sleep(1)

    detection_results = []
    existing_files = set(glob.glob(full_pattern))
    processed_files = set()

    logger.debug(f"Watching {image_dir} for up to {image_count} new images...")
    while len(processed_files) < image_count:
        current = set(glob.glob(full_pattern))
        new_files = current - existing_files - processed_files

        try:
            sicti = r.get('sicti')

            # Try to check if sicti is a boolean or string representation of True
            if isinstance(sicti, bytes):
                sicti = sicti.decode('utf-8')  # Convert bytes to string if necessary

            # Check if the value is 'True' (string) or True (boolean)
            if sicti == 'True' or sicti == True:
                logger.debug("kamera sicti, breaking the image processor loop.")
                r.set('ip_done', 'True')  # Set the 'ip_done' signal
                r.set('cf_done', 'True')
                
                sys.exit(0)
                break

        except Exception as e:
            logger.error(f"Error reading 'sicti' value: {e}")
            # Continue processing even if there is an issue with Redis or the value
            pass

        if new_files:
            for file_path in sorted(new_files):
                # 1) Tiled detection as before
                detection_results = process_image(file_path, model, detection_results, len(processed_files), counter=counter)

                # None kontrolü ve len 0 kontrolü ekledik
                # if detection_results is None or len(detection_results) == 0:
                #     logger.info("Hiçbir obje tespit edilmedi.")
                #     r.set('ip_done', 'True')  # Set the 'ip_done' signal
                #     r.set('cf_done', 'True')
                #     r.set('sicti', 'True')
                #     sys.exit(0)
                # else:
                #     logger.info(f"Toplam {len(detection_results)} obje tespit edildi.")


                # 3) mark as processed
                processed_files.add(file_path)
                logger.debug(f"Processed {file_path} ({len(processed_files)}/{image_count})")
                if len(processed_files) >= image_count:
                    break
        time.sleep(0.5)

    logger.debug(f"All {image_count} images processed.")

    # DataFrame & CSV
    df = pd.DataFrame(detection_results)
    if df is None or df.empty:
        logger.info("Hiçbir obje tespit edilmedi, DataFrame boş.")
        r.set('ip_done', 'True')
        logger.info("ip_done True")

        r.set('cf_done', 'True')
        logger.info("cf_done True")

        r.set('sicti', 'True')
        logger.info("sicti True")

        sys.exit(0)
    else:
        logger.info(f"Toplam {len(df)} obje tespit edildi.")
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