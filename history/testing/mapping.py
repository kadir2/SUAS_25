import redis
import time
import json
import os
import glob
import cv2

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
            print(f"Resim yüklenemedi: {path}")
    
    if not images:
        print("Birleştirilecek geçerli resim bulunamadı.")
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
        print(f"Birleştirilmiş resim {output_path} dosyasına kaydedildi.")
    else:
        print("Resim birleştirme sırasında hata oluştu. Status kodu:", status)

def main():
    # mapping_config.json dosyasından yapılandırma ayarlarını yükle
    with open('config.json') as f:
        config = json.load(f)
    
    mapping_image_count = config['mapping_image_count']
    mapping_dir = config['mapping_dir']
    mapping_pattern = config['mapping_pattern']
    jpg = os.path.join(mapping_dir, mapping_pattern[0])
    png = os.path.join(mapping_dir, mapping_pattern[1])
    full_pattern = [jpg,png]
    output_image = config.get('output_image', 'mapping_resultWstitching.jpg')
    
    # Redis ile bağlantı kur
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    
    # Redis üzerinden 'start_mapping' sinyalini bekle
    print("Waiting for 'start_mapping' signal...")
    while True:
        start_mapping = r.get('start_mapping')
        if start_mapping and start_mapping.decode('utf-8') == 'True':
            break
        time.sleep(1)
    
    # İlk mevcut dosyaları belirleyerek sadece yeni eklenenleri takip et
    existing_files = set(glob.glob(full_pattern))
    processed_files = set()
    
    print(f"Monitoring directory: {mapping_dir} for mapping images...")
    while len(processed_files) < mapping_image_count:
        # Kalıba uyan mevcut dosyaları güncelle
        current_files = set(glob.glob(full_pattern))
        # İşlenmemiş yeni dosyaları belirle
        new_files = current_files - existing_files - processed_files
        
        if new_files:
            for file_path in sorted(new_files):
                processed_files.add(file_path)
                print(f"Yeni mapping resmi bulundu: {file_path} ({len(processed_files)}/{mapping_image_count})")
                if len(processed_files) >= mapping_image_count:
                    break
        
        # Aşırı CPU kullanımını önlemek için kısa uyku
        time.sleep(0.5)
    
    print("Tüm mapping resimleri toplandı.")
    
    # Toplanan resimlerin birleşiminden panorama oluştur
    image_paths = sorted(list(processed_files))
    #combine_images(image_paths, output_image)
    combine_images(image_paths, "mapping_resultWstitching.jpg")
    
    
    # Mapping işleminin tamamlandığını Redis üzerinden bildir
    r.set('mapping_done', 'True')

if __name__ == "__main__":
    main()
