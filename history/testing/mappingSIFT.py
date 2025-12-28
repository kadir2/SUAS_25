import redis
import time
import json
import os
import glob
import cv2
import numpy as np

def stitch_pair(img1, img2):
    """
    İki resmi SIFT algoritması ve homography hesaplaması kullanarak birleştirir.
    """
    # SIFT ile anahtar noktaları ve descriptor'ları tespit et
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)

    # BFMatcher ile eşleştirme yap (L2 norm kullanılarak)
    bf = cv2.BFMatcher(cv2.NORM_L2)
    matches = bf.knnMatch(des1, des2, k=2)

    # Lowe'nun oran testi ile iyi eşleşmeleri filtrele
    good_matches = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)

    if len(good_matches) < 4:
        print("Yeterli eşleşme bulunamadı!")
        return None

    # İki resim arasındaki homography'yi RANSAC ile hesapla
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    H, status = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    if H is None:
        print("Homography hesaplanamadı!")
        return None

    # H matrisinde olağan dışı (çok yüksek) değerleri kontrol et
    if np.abs(H).max() > 1e5:
        print("H matrisinde olağan dışı değerler var. Stitching iptal ediliyor.")
        return None

    # Resim boyutlarını al
    height1, width1 = img1.shape[:2]
    height2, width2 = img2.shape[:2]

    # img2'nin köşe koordinatlarını hesapla ve H ile dönüştür
    corners_img2 = np.float32([[0,0], [0,height2], [width2,height2], [width2,0]]).reshape(-1, 1, 2)
    warped_corners_img2 = cv2.perspectiveTransform(corners_img2, H)

    # img1'in köşe koordinatları
    corners_img1 = np.float32([[0,0], [0,height1], [width1,height1], [width1,0]]).reshape(-1, 1, 2)

    # Her iki resmin köşe koordinatlarını birleştirip panorama için yeni boyutları hesapla
    all_corners = np.concatenate((corners_img1, warped_corners_img2), axis=0)
    [xmin, ymin] = np.int32(all_corners.min(axis=0).ravel() - 0.5)
    [xmax, ymax] = np.int32(all_corners.max(axis=0).ravel() + 0.5)
    translation = [-xmin, -ymin]
    print(f"Panorama boyutları: xmin={xmin}, ymin={ymin}, xmax={xmax}, ymax={ymax}")

    width  = xmax - xmin
    height = ymax - ymin

    # Çıktı panorama için maksimum boyut sınırlarını belirle (örneğin 4000x4000 piksel)
    max_width = 4000
    max_height = 4000
    scale = min(1, max_width/width, max_height/height)
    if scale < 1:
        print(f"Panorama boyutu çok büyük, {scale:.3f} ölçek faktörü uygulanıyor.")

    # Çeviri matrisini oluştur
    H_translated = np.array([[1, 0, translation[0]], 
                             [0, 1, translation[1]], 
                             [0, 0, 1]])
    # Birleştirme matrisini oluştur
    M = H_translated.dot(H)
    # Ölçekleme matrisini oluştur
    S = np.array([[scale, 0, 0],
                  [0, scale, 0],
                  [0,    0, 1]])
    M_scaled = S.dot(M)
    new_width  = int(width * scale)
    new_height = int(height * scale)
    
    try:
        result_img = cv2.warpPerspective(img2, M_scaled, (new_width, new_height))
    except cv2.error as e:
        print("cv2.warpPerspective hatası:", e)
        return None

    # img1'i de ölçekleyerek yerleştir
    scaled_translation = (int(translation[0]*scale), int(translation[1]*scale))
    img1_resized = cv2.resize(img1, (int(width1*scale), int(height1*scale)))
    h1, w1 = img1_resized.shape[:2]
    # Sonuç görüntüsüne img1'i yerleştir (varsa üst üste binmeleri göz önünde bulundurulabilir)
    result_img[scaled_translation[1]:scaled_translation[1]+h1, 
               scaled_translation[0]:scaled_translation[0]+w1] = img1_resized

    return result_img

def combine_images(image_paths, output_path):
    """
    Verilen resimlerin SIFT algoritması kullanılarak manuel olarak panoramik birleşimini oluşturur
    ve output_path'e kaydeder.
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

    # Eğer sadece bir resim varsa, doğrudan kaydet
    if len(images) == 1:
        cv2.imwrite(output_path, images[0])
        print(f"Tek resim {output_path} dosyasına kaydedildi.")
        return

    # İlk resmi panorama olarak başlat
    panorama = images[0]

    # Sırayla diğer resimleri panorama üzerine ekle
    for i in range(1, len(images)):
        print(f"Resim {i+1} ile stitching işlemi yapılıyor...")
        panorama_new = stitch_pair(panorama, images[i])
        if panorama_new is None:
            print("Stitching işlemi başarısız oldu.")
            return
        panorama = panorama_new

    # Birleştirilmiş panoramayı kaydet
    cv2.imwrite(output_path, panorama)
    print(f"Birleştirilmiş resim {output_path} dosyasına kaydedildi.")

def get_current_files(mapping_dir, mapping_pattern):
    """
    mapping_pattern hem tek bir string hem de stringlerden oluşan bir liste olabilir.
    Her iki durumda da dosya yollarını döndürür.
    """
    if isinstance(mapping_pattern, str):
        return set(glob.glob(os.path.join(mapping_dir, mapping_pattern)))
    elif isinstance(mapping_pattern, list):
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
    mapping_dir = config['mapping_dir']
    mapping_pattern = config['mapping_pattern']
    output_image = config.get('output_image', 'mapping_resultWsift.jpg')
    
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
    existing_files = get_current_files(mapping_dir, mapping_pattern)
    processed_files = set()
    
    print(f"Monitoring directory: {mapping_dir} for mapping images...")
    while len(processed_files) < mapping_image_count:
        # Kalıba uyan mevcut dosyaları güncelle
        current_files = get_current_files(mapping_dir, mapping_pattern)
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
    combine_images(image_paths, output_image)
    
    # Mapping işleminin tamamlandığını Redis üzerinden bildir
    r.set('mapping_done', 'True')

if __name__ == "__main__":
    main()
