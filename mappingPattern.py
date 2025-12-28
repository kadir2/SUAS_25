import redis
import time
import json
import os
import glob
import cv2
import shutil
import logging
from datetime import datetime

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


def copy_to_usb(source_path, usb_mount_point):
    if os.path.isfile(source_path):
        try:
            destination_path = os.path.join(usb_mount_point, os.path.basename(source_path))
            shutil.copy2(source_path, destination_path)
            print(f"{source_path} USB'ye başarıyla kopyalandı: {destination_path}")
        except Exception as e:
            print(f"USB'ye kopyalama sırasında hata: {e}")
    else:
        print(f"Kopyalanacak dosya bulunamadı: {source_path}")


def combine_images(image_paths, output_path):
    """
    OpenCV'nin stitching algoritmasını kullanarak verilen resimlerin
    birleşiminden tek bir panorama oluşturur ve output_path'e kaydeder.
    """
    # Resimleri OpenCV ile yükle
    images = []
    for path in image_paths:
        img = cv2.imread(path)
        if img is not None:
            images.append(img)
        else:
            logger.debug(f"Resim yüklenemedi: {path}")
    
    if not images:
        logger.debug("Birleştirilecek geçerli resim bulunamadı.")
        return

    # OpenCV stitching modülü kullanımı
    # OpenCV versiyonuna bağlı olarak Stitcher_create veya createStitcher kullanılabilir.
    if hasattr(cv2, 'Stitcher_create'):
        stitcher = cv2.Stitcher_create()
    else:
        stitcher = cv2.createStitcher()

    status, stitched = stitcher.stitch(images)
    if status == cv2.Stitcher_OK:
        cv2.imwrite(output_path, stitched)
        logger.debug(f"Birleştirilmiş resim {output_path} dosyasına kaydedildi.")
    else:
        logger.debug("Resim birleştirme sırasında hata oluştu. Status kodu:", status)

def get_current_files(mapping_dir, mapping_pattern):
    """
    mapping_pattern hem tek bir string hem de stringlerden oluşan bir liste olabilir.
    Burada her iki durumda da dosya yolunu topluca döndürüyoruz.
    """
    if isinstance(mapping_pattern, str):
        # Tek bir kalıp varsa doğrudan onu kullan
        return set(glob.glob(os.path.join(mapping_dir, mapping_pattern)))
    elif isinstance(mapping_pattern, list):
        # Birden çok kalıp varsa hepsini bir set içinde toplayalım
        all_files = set()
        for pat in mapping_pattern:
            all_files.update(glob.glob(os.path.join(mapping_dir, pat)))
        return all_files
    else:
        raise ValueError("mapping_pattern must be a string or a list of strings.")

def main():
    # config.json dosyasından yapılandırma ayarlarını yükle
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    mapping_image_count = config['mapping_image_count']
    counter = config['counter']
    mapping_dir = config['mapping_dir'] + counter
    mapping_pattern = config['mapping_pattern']
    output_image = config.get('output_image', 'mapping_resultWstitching.jpg')


    if not os.path.exists(mapping_dir):
        os.makedirs(mapping_dir)

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    r.set('start_mapping', 'True')

    # Redis üzerinden 'start_mapping' sinyalini bekle
    logger.debug("Waiting for 'start_mapping' signal...")
    while True:
        start_mapping = r.get('start_mapping')
        if start_mapping and start_mapping.decode('utf-8') == 'True':
            break
        time.sleep(1)
    
    # İlk mevcut dosyaları belirleyerek sadece yeni eklenenleri takip et
    existing_files = get_current_files(mapping_dir, mapping_pattern)
    processed_files = set()
    
    logger.debug(f"Monitoring directory: {mapping_dir} for mapping images...")
    while len(processed_files) < mapping_image_count:
        # Kalıba uyan mevcut dosyaları güncelle
        current_files = get_current_files(mapping_dir, mapping_pattern)
        # İşlenmemiş yeni dosyaları belirle
        new_files = current_files - existing_files - processed_files
        
        if new_files:
            for file_path in sorted(new_files):
                processed_files.add(file_path)
                logger.debug(f"Yeni mapping resmi bulundu: {file_path} ({len(processed_files)}/{mapping_image_count})")
                if len(processed_files) >= mapping_image_count:
                    break
        
        # Aşırı CPU kullanımını önlemek için kısa uyku
        time.sleep(0.5)
    
    logger.debug("Tüm mapping resimleri toplandı.")
    
    # Toplanan resimlerin birleşiminden panorama oluştur
    image_paths = sorted(list(processed_files))
    ip_done= r.get('ip_done')
    while ip_done and ip_done.decode('utf-8') != 'True':
        logger.debug("Waiting for 'ip_done' signal...")
        time.sleep(1)
        ip_done = r.get('ip_done')
        
    combine_images(image_paths, output_image)
    usb_mount = '/media/itunom/toshiba'  # senin USB mount noktan
    copy_to_usb(output_image, usb_mount)
    
    # Mapping işleminin tamamlandığını Redis üzerinden bildir
    r.set('mapping_done', 'True')

if __name__ == "__main__":
    main()
