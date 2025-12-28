import cv2
import numpy as np
import glob
import os
import json
import redis
import time
import logging
from datetime import datetime
import shutil

class Loggerr:
    def __init__(self):
        # Logger oluştur
        self.logger = logging.Logger('Mapping')
        self.logger.setLevel(logging.DEBUG)  # Log seviyesi DEBUG olarak ayarlanır
        
        # Handlers: Konsol ve Dosya
        c_handler = logging.StreamHandler()  # Konsol için handler
        log_file_path = 'Mapping.log'  # Log dosyasının adı
        old_logs_dir = "old_logs_SUAS"  # Eski log dosyalarının taşınacağı klasör

        # Eski log dosyalarını yedekle
        if not os.path.exists(old_logs_dir):  # Eğer klasör yoksa oluştur
            os.makedirs(old_logs_dir)
        if os.path.exists(log_file_path):  # Eğer log dosyası varsa
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # Zaman damgası oluştur
            new_log_file_name = f"Mapping_{timestamp}.log"  # Yeni log dosyasının adı
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


# ——— Birinci koddaki Fisheye parametreleri (birebir)
K = np.array([[2.48955267e+03, 0, 2.01600000e+03],
              [0, 2.48955267e+03, 1.52000000e+03],
              [0, 0, 1]])
D = np.array([0.006, 0.00, 0.001, 0.00])

def undistort_fisheye(img, K, D):

    h, w = img.shape[:2]
    new_K, roi = cv2.getOptimalNewCameraMatrix(K, D, (w, h), 1, (w, h))
    undistorted = cv2.undistort(img, K, D, None, new_K)
    x, y, w_roi, h_roi = roi
    if w_roi > 0 and h_roi > 0:
        undistorted = undistorted[y:y+h_roi, x:x+w_roi]
    return undistorted

def load_images_from_list(paths, resize_width=None):
    """
    klasördeki tüm '*.jpg' yerine, parametre olarak verilen 'paths' listesini okur.
    - paths: tam dosya yolu listesi (ordered).
    - resize_width is None olduğu için hiçbir resize yapılmaz.
    """
    imgs = []
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            logger.debug(f"UYARI: {p} okunamadı")
            continue
        img = undistort_fisheye(img, K, D)
        if resize_width is not None:
            h, w = img.shape[:2]
            if w > resize_width:
                scale = resize_width / w
                img = cv2.resize(img, (resize_width, int(h * scale)), interpolation=cv2.INTER_AREA)
        imgs.append(img)
    return imgs

def stitch_images_horizontally(images):
    """
    - İlk resimden başlayarak, her defasında bir sonraki resimle stitch eder.
    """
    stitcher = cv2.Stitcher_create()
    stitcher.setPanoConfidenceThresh(0.3)
    pano = images[0]
    for img in images[1:]:
        status, result = stitcher.stitch([pano, img])
        if status != cv2.Stitcher_OK:
            logger.debug(f"Yatay stitching başarısız, status: {status}")
            return pano
        pano = result
    return pano

def stitch_images_vertically(pano_top, pano_bottom):
    """
    - Hata alırsa fallback olarak vconcat
    """
    stitcher = cv2.Stitcher_create()
    stitcher.setPanoConfidenceThresh(0.3)
    status, result = stitcher.stitch([pano_top, pano_bottom])
    if status != cv2.Stitcher_OK:
        logger.debug(f"Dikey stitching başarısız, status: {status}")
        h_top, w_top = pano_top.shape[:2]
        h_bot, w_bot = pano_bottom.shape[:2]
        width = max(w_top, w_bot)
        new_top = cv2.copyMakeBorder(pano_top, 0, 0, 0, width - w_top, cv2.BORDER_CONSTANT)
        new_bot = cv2.copyMakeBorder(pano_bottom, 0, 0, 0, width - w_bot, cv2.BORDER_CONSTANT)
        combined = cv2.vconcat([new_top, new_bot])
        return combined
    return result

def get_current_files(folder, patterns):
    """
    Klasördeki mevcut dosyaları, 'patterns' listesindeki her pattern için bulup set halinde döner.
    Örneğin patterns = ["*.JPG", "*.png", "*.jpg"] ise,
    bunları ayrı ayrı glob’layıp sonuçları tek bir sette toplarız.
    """
    all_files = set()
    for pat in patterns:
        full_pattern = os.path.join(folder, pat)
        for p in glob.glob(full_pattern):
            all_files.add(p)
    return all_files

if __name__ == '__main__':
    # 1) config.json'u oku
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
                          
    output_path         = config.get('output_image', 'stitched_output.jpg')
    mapping_image_count = config['mapping_image_count']
    counter = config['counter']
    mapping_dir = config['mapping_dir'] + counter
    mapping_pattern = config['mapping_pattern']
    resize_width        = None      

                          

    r = redis.StrictRedis(host='localhost', port=6379, db=0)

    # 3) 'start_mapping' sinyalini bekle
    logger.debug("Waiting for 'start_mapping' signal...")
    while True:
        val = r.get('start_mapping')
        if val and val.decode('utf-8') == 'True':
            break
        time.sleep(1)

    # 4) Dosyalar klasöre geldikçe topla, mapping_image_count adedine ulaştığında çık
    existing_files  = get_current_files(mapping_dir, mapping_pattern)
    processed_files = set()

    logger.debug(f"Monitoring directory: {mapping_dir} for mapping images...")
    while len(processed_files) < mapping_image_count:
        current_files = get_current_files(mapping_dir, mapping_pattern)
        # Yeni eklenen = current_files − existing_files − processed_files
        new_files = current_files - existing_files - processed_files

        if new_files:
            for file_path in sorted(new_files):
                processed_files.add(file_path)
                logger.debug(f"Yeni mapping resmi bulundu: {file_path} ({len(processed_files)}/{mapping_image_count})")
                if len(processed_files) >= mapping_image_count:
                    break
        time.sleep(0.5)

    logger.debug("Tüm mapping resimleri toplandı.")

    # 5) Sadece processed_files listesindeki dosyaları stitch etmek üzere al:
    selected_paths = sorted(processed_files)
    images = load_images_from_list(selected_paths, resize_width=resize_width)

    if len(images) < 2:
        raise RuntimeError("En az iki resim olmalı.")

    if len(images) <= 3:
        pano = stitch_images_horizontally(images)
    elif len(images) >= 6:
        bottom_row = stitch_images_horizontally(images[0:3])
        top_row    = stitch_images_horizontally(images[3:6])
        pano       = stitch_images_vertically(top_row, bottom_row)
    else:
        pano = stitch_images_horizontally(images)

    cv2.imwrite(output_path, pano)
    logger.debug(f"Son panorama kaydedildi: {output_path}")

    #r.set('mapping_done', 'True')
