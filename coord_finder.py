import os
import math
import time
import cv2
import logging
import pandas as pd
import numpy as np
import geopy.distance as gp
import json
import shutil
from datetime import datetime
import redis

class Loggerr:
    def __init__(self):
        # Logger oluştur
        self.logger = logging.Logger('Coord_Finder')
        self.logger.setLevel(logging.DEBUG)  # Log seviyesi DEBUG olarak ayarlanır
        
        # Handlers: Konsol ve Dosya
        c_handler = logging.StreamHandler()  # Konsol için handler
        log_file_path = 'Coord_Finder.log'  # Log dosyasının adı
        old_logs_dir = "old_logs_SUAS"  # Eski log dosyalarının taşınacağı klasör

        # Eski log dosyalarını yedekle
        if not os.path.exists(old_logs_dir):  # Eğer klasör yoksa oluştur
            os.makedirs(old_logs_dir)
        if os.path.exists(log_file_path):  # Eğer log dosyası varsa
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # Zaman damgası oluştur
            new_log_file_name = f"Coord_Finder_{timestamp}.log"  # Yeni log dosyasının adı
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

# --------------------------------------------------------------------
# 1. Yardımcı Fonksiyon: Her sınıftan en yüksek confidence'a sahip satırı seçmek
# --------------------------------------------------------------------
def select_top_confidence_rows(df):
    """
    Her sınıf için en yüksek confidence değerine sahip satırı seçer.
    Eğer 4'ten fazla farklı sınıf varsa, en yüksek 4 confidence'lı örneği döndürür.
    Eğer dataframe içinde 4'ten az sınıf varsa, geriye kalan satırlardan
    en yüksek confidence değerine sahip satırları ekleyerek toplamda 4 satıra tamamlar.
    """
    # Her sınıfın en yüksek confidence'lı satırını seçelim.
    top_rows = df.loc[df.groupby("class_name")["confidence"].idxmax()]
    
    if len(top_rows) < 4:
        additional_needed = 4 - len(top_rows)
        # Seçilmemiş satırları alalım.
        remaining = df.drop(index=top_rows.index)
        # Kalan satırları confidence değerine göre azalan sırada sıralayalım.
        remaining_sorted = remaining.sort_values(by="confidence", ascending=False)
        # İhtiyaç duyulan sayıda satırı ekleyelim.
        additional_rows = remaining_sorted.head(additional_needed)
        top_rows = pd.concat([top_rows, additional_rows])
    elif len(top_rows) > 4:
        top_rows = top_rows.nlargest(4, "confidence")
    
    return top_rows

# --------------------------------------------------------------------
# 2. CoordinateFinder Sınıfı (Localizasyon İşlemleri)
# --------------------------------------------------------------------
class CoordinateFinder():
    def __init__(self, img_shape: tuple, live_location: list, drone_yaw, focal_length, sensor_size, drone_altitude) -> None:
        # Loglama ayarları ve dizin kontrolü
        if not os.path.exists("LOGS"):
            os.makedirs("LOGS")
        logging.basicConfig(
            format='%(levelname)s %(asctime)s: %(message)s (Line: %(lineno)d)',
            level=logging.DEBUG,
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[logging.StreamHandler()]
        )
        try:    
            self.img_shape = img_shape  # (genişlik, yükseklik)
            self.live_location = live_location  # [lat, lon]
            self.drone_yaw = drone_yaw  
            self.img_shape_x = img_shape[0]  # genişlik
            self.img_shape_y = img_shape[1]  # yükseklik
            self.img_center_x = img_shape[0] // 2
            self.img_center_y = img_shape[1] // 2
            self.img_center = (self.img_center_x, self.img_center_y)
            self.focal_length = focal_length
            self.sensor_size = sensor_size
            self.drone_altitude = drone_altitude
            logging.info("CoordinateFinder __init__ fonksiyonu başarıyla çalıştı.")
        except Exception as e:
            logging.error("CoordinateFinder __init__ fonksiyonunda hata: {}".format(e))

    def find_hfov_vfov(self):
        try:
            aov_h = 2 * math.atan(self.sensor_size[0] / (2 * self.focal_length))
            aov_v = 2 * math.atan(self.sensor_size[1] / (2 * self.focal_length))
            h_fov = 2 * math.tan(aov_h / 2) * self.drone_altitude
            v_fov = 2 * math.tan(aov_v / 2) * self.drone_altitude
            logging.info("find_hfov_vfov fonksiyonu başarıyla çalıştı.")
        except Exception as e:
            logging.error("find_hfov_vfov fonksiyonunda hata: {}".format(e)) 
        return h_fov, v_fov
    
    def pixel_to_meter(self):
        try:
            h_fov, v_fov = self.find_hfov_vfov()
            # Yatay ve dikey her pikselin karşılığı (metre cinsinden)
            w_coeff = v_fov / self.img_shape_x  
            h_coeff = h_fov / self.img_shape_y  
            logging.info("pixel_to_meter fonksiyonu başarıyla çalıştı.")
        except Exception as e:
            logging.error("pixel_to_meter fonksiyonunda hata: {}".format(e))
        return w_coeff, h_coeff 
    
    def location_from_a_point(self, coord, dist, direction):
        if (coord is None) or (dist is None) or (direction is None):
            logging.error("location_from_a_point fonksiyonu için argüman eksik.")
        try:
            destination = gp.distance(meters=dist).destination((coord[0], coord[1]), bearing=direction)
            logging.info("location_from_a_point fonksiyonu başarıyla çalıştı.")
        except Exception as e:
            logging.error("location_from_a_point fonksiyonunda hata: {}".format(e))
        return destination

    def radian_to_angle(self, angle):
        if angle is None:
            logging.error("radian_to_angle fonksiyonu için argüman eksik.")
        logging.info("radian_to_angle fonksiyonu çalıştı.")
        return angle * (180 / math.pi)
    
    def calculate_roi_coord_with_line_len(self, distance_to_center, roi_angle, center):
        if (distance_to_center is None) or (roi_angle is None) or (center is None):
            logging.error("calculate_roi_coord_with_line_len fonksiyonu için argüman eksik.")
        try:
            norm_angle = 360 - self.drone_yaw
            final_angle = roi_angle - norm_angle
            logging.info("calculate_roi_coord_with_line_len fonksiyonu çalıştı.")
        except Exception as e:
            logging.error("calculate_roi_coord_with_line_len fonksiyonunda hata: {}".format(e))
        return self.location_from_a_point(center, distance_to_center, roi_angle)
    
    def roi_geo_coord_finder(self, roi_pixel_coords):
        """
        Verilen normalized ROI piksel koordinatlarına göre,
        drone'ın canlı konumu ve kamera parametreleriyle
        coğrafi koordinatları (lat, lon) hesaplar.
        """
        roi_coords = []
        try:
            w_coeff, h_coeff = self.pixel_to_meter()
            for coord in roi_pixel_coords:
                # Normalized koordinatlardan gerçek piksel koordinatlarına geçelim:
                x_center = round(coord[0] * self.img_shape_x)
                y_center = round(coord[1] * self.img_shape_y)
                x_diff = abs(x_center - self.img_center_x)
                y_diff = abs(y_center - self.img_center_y)
                # Merkezden ROI’ye olan mesafe (metre cinsinden):
                line_length = math.sqrt((x_diff * w_coeff)**2 + (y_diff * h_coeff)**2)
                # Merkeze göre açıyı hesaplayalım:
                angle = self.radian_to_angle(math.atan2(y_diff, x_diff))
                # Görüntünün hangi bölgesinde olduğuna göre açıyı ayarlıyoruz:
                if x_center >= self.img_center_x and y_center < self.img_center_y:
                    adjusted_angle = angle
                elif x_center < self.img_center_x and y_center < self.img_center_y:
                    adjusted_angle = 180 - angle
                elif x_center < self.img_center_x and y_center >= self.img_center_y:
                    adjusted_angle = angle + 180
                elif x_center >= self.img_center_x and y_center >= self.img_center_y:
                    adjusted_angle = 360 - angle
                # Drone yönü (yaw) ile birleştirip, rota açısını hesaplıyoruz.
                bearing = 450 - adjusted_angle + self.drone_yaw
                roi_destination = self.calculate_roi_coord_with_line_len(line_length, bearing, center=self.live_location)
                roi_coords.append((roi_destination.latitude, roi_destination.longitude))
            logging.info("roi_geo_coord_finder fonksiyonu başarıyla çalıştı.")
        except Exception as e:
            logging.error("roi_geo_coord_finder fonksiyonunda hata: {}".format(e))
        return roi_coords

def run_production_mode():
    logger.debug("=== PRODUCTION MODE ===")
    # Redis bağlantısı (parametreleri kendi ortamınıza göre ayarlayın)
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.set('cf_done', 'False')
    # 'ip_done' parametresinin "True" olarak ayarlanmasını bekleyelim
    logger.debug("Redis üzerinden ip_done parametresinin 'True' olmasını bekliyorum...")
    while r.get('ip_done') != b'True':
        time.sleep(1)
    logger.debug("ip_done 'True' olarak ayarlandı, production moduna geçiliyor.")
    time.sleep(2)
    
    # Dosyalardan veri okuma (örneğin CSV formatında)
    with open("config.json", "r") as f:
        config = json.load(f)
        counter = config['counter']
        detection_file = config['detection_file'] + str(counter) + ".csv"
        position_file = config['position_file'] + str(counter) + ".csv"
        
    
    # DataFrame'leri dosyalardan okuyalım:
    try:
        df_results = pd.read_csv(detection_file)
        df_positions = pd.read_csv(position_file)
        logger.debug("Detection DataFrame (df_results) başarıyla okundu:")
        logger.debug("\n{}".format(df_results.head()))
        logger.debug("Position DataFrame (df_positions) başarıyla okundu:")
        logger.debug("\n{}".format(df_positions.head()))
    except Exception as e:
        logging.error("Dosyalardan okuma sırasında hata: {}".format(e))
        return
    
    # Karar algoritması: Her sınıftan en yüksek confidence'a sahip satırları seçelim (4'e tamamlanarak)
    top_confidence_row_df = select_top_confidence_rows(df_results)
    
    # Fotoğraf isimlerine göre iki DataFrame'i birleştirelim:
    merged_df = pd.merge(top_confidence_row_df, df_positions, on="image", how="inner")
    logger.debug(merged_df)
    # Sabit kamera parametreleri ve görüntü boyutu (örnek değerler)
    image_shape = (3840, 2160)   # (genişlik, yükseklik)
    focal_length = 8          # örnek odak uzaklığı
    sensor_size = [6.287, 4.712]  # örnek sensör boyutları (mm cinsinden)
    
    # Her satır için ROI'nin geo koordinatlarını hesaplayalım:
    roi_results = []
    for idx, row in merged_df.iterrows():
        norm_x = row['center_x'] / image_shape[0]
        norm_y = row['center_y'] / image_shape[1]
        roi_pixel_coord = [(norm_x, norm_y)]
        
        live_location = [row['lat'], row['lon']]
        drone_yaw = row['yaw']
        drone_altitude = row['alt']
        
        cf = CoordinateFinder(img_shape=image_shape,
                              live_location=live_location,
                              drone_yaw=drone_yaw,
                              focal_length=focal_length,
                              sensor_size=sensor_size,
                              drone_altitude=drone_altitude)
        
        roi_geo = cf.roi_geo_coord_finder(roi_pixel_coord)
        if roi_geo:
            roi_coord = roi_geo[0]
        else:
            roi_coord = (None, None)
        
        roi_results.append({
            "image": row["image"],
            "class_name": row["class_name"],
            "roi_lat": roi_coord[0],
            "roi_lon": roi_coord[1]
        })
    
    # ROI sonuçlarını topladıktan sonra, eğer 4’ten azsa
    # ilk kaydı kopyalayarak 4’e tamamlayalım
    if len(roi_results) < 4:
        needed = 4 - len(roi_results)
        first = roi_results[0].copy()
        for _ in range(needed):
            roi_results.append(first)
        logger.debug(f"roi_results listesi {len(roi_results)-needed} elemanken, ilk kayıt kopyalanıp 4 elemana tamamlandı.")

    df_roi_results = pd.DataFrame(roi_results)
    # Hesaplanan ROI sonuçlarını bir dosyaya yazalım
    output_file = f"roi_results{counter}.csv"

    if os.path.isfile(output_file) and os.path.getsize(output_file) > 0:
        with open(output_file, 'w') as f:
            f.truncate(0)
        logger.debug(f"{output_file} dosyasının içeriği temizlendi.")
    else:
        logger.debug(f"{output_file} dosyası ya mevcut değil ya da zaten boş.")
    
    df_roi_results.to_csv(output_file, index=False)
    logger.debug("Hesaplanan ROI Geo Koordinatları '{}' dosyasına kaydedildi.".format(output_file))
    r.set('cf_done', 'True')

# --------------------------------------------------------------------
# Ana blok: Mod seçimine göre test veya production modu çalıştırılır.
# --------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ROI Localization Script")
    parser.add_argument('--mode', choices=['test', 'prod'], default='prod', help="Çalışma modu: test veya prod")
    args = parser.parse_args()
    run_production_mode()
