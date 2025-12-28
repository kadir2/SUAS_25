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
import redis
import sys
from datetime import datetime

class Loggerr:
    def __init__(self):
        # Logger oluştur
        self.logger = logging.Logger('Coord_Finder')
        self.logger.setLevel(logging.DEBUG)  # Log seviyesi DEBUG olarak ayarlanır
        
        # Konsol handler
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.DEBUG)
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)

        # Dosya handler
        log_file_path = 'Coord_Finder.log'
        old_logs_dir = "old_logs_SUAS"
        if not os.path.exists(old_logs_dir):
            os.makedirs(old_logs_dir)
        if os.path.exists(log_file_path):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            new_log = f"Coord_Finder_{timestamp}.log"
            shutil.move(log_file_path, os.path.join(old_logs_dir, new_log))
        f_handler = logging.FileHandler(log_file_path)
        f_handler.setLevel(logging.DEBUG)
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)

        self.logger.addHandler(c_handler)
        self.logger.addHandler(f_handler)

logger = Loggerr().logger


def filter_by_spatial_distance(detections, threshold_m=3, max_results=4):
    """
    Conflicting detections arasındaki mesafeyi kontrol eder ve
    yakınsa yalnızca yüksek confidence'lısını seçer. Toplam max_results adet döner.
    detections: list of dict: {image, class_name, confidence, roi_lat, roi_lon}
    """
    selected = []
    remaining = []
    # Confidence'a göre azalan sırada sırala
    sorted_dets = sorted(detections, key=lambda x: x['confidence'], reverse=True)
    for det in sorted_dets:
        if len(selected) >= max_results:
            break
        lat, lon = det['roi_lat'], det['roi_lon']
        if lat is None or lon is None:
            continue
        too_close = False
        for sel in selected:
            dist = gp.distance((lat, lon), (sel['roi_lat'], sel['roi_lon'])).meters
            if dist < threshold_m:
                too_close = True
                break
        if not too_close:
            selected.append(det)
        else:
            remaining.append(det)
    # Eğer yeterli sayıya ulaşamadıysa, kalanları ekle
    for det in remaining:
        if len(selected) >= max_results:
            break
        selected.append(det)
    return selected

class CoordinateFinder():
    def __init__(self, img_shape: tuple, live_location: list, drone_yaw, focal_length, sensor_size, drone_altitude) -> None:
        if not os.path.exists("LOGS"):
            os.makedirs("LOGS")
        logging.basicConfig(
            format='%(levelname)s %(asctime)s: %(message)s (Line: %(lineno)d)',
            level=logging.DEBUG,
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[logging.StreamHandler()]
        )
        try:
            self.img_shape = img_shape
            self.live_location = live_location
            self.drone_yaw = drone_yaw
            self.img_center_x = img_shape[0] // 2
            self.img_center_y = img_shape[1] // 2
            self.focal_length = focal_length
            self.sensor_size = sensor_size
            self.drone_altitude = drone_altitude
            logger.debug("CoordinateFinder initialized.")
        except Exception as e:
            logger.debug(f"Init error: {e}")

    def find_hfov_vfov(self):
        aov_h = 2 * math.atan(self.sensor_size[0] / (2 * self.focal_length))
        aov_v = 2 * math.atan(self.sensor_size[1] / (2 * self.focal_length))
        h_fov = 2 * math.tan(aov_h / 2) * self.drone_altitude
        v_fov = 2 * math.tan(aov_v / 2) * self.drone_altitude
        return h_fov, v_fov

    def pixel_to_meter(self):
        h_fov, v_fov = self.find_hfov_vfov()
        w_coeff = v_fov / self.img_shape[0]
        h_coeff = h_fov / self.img_shape[1]
        return w_coeff, h_coeff

    def location_from_a_point(self, coord, dist, direction):
        return gp.distance(meters=dist).destination((coord[0], coord[1]), bearing=direction)

    def radian_to_angle(self, angle):
        return angle * (180 / math.pi)

    def calculate_roi_coord_with_line_len(self, distance_to_center, roi_angle, center):
        norm_angle = 360 - self.drone_yaw
        final_angle = roi_angle - norm_angle
        return self.location_from_a_point(center, distance_to_center, roi_angle)

    def roi_geo_coord_finder(self, roi_pixel_coords):
        coords = []
        w_coeff, h_coeff = self.pixel_to_meter()
        for coord in roi_pixel_coords:
            x_center = round(coord[0] * self.img_shape[0])
            y_center = round(coord[1] * self.img_shape[1])
            x_diff = abs(x_center - self.img_center_x)
            y_diff = abs(y_center - self.img_center_y)
            line_len = math.sqrt((x_diff * w_coeff)**2 + (y_diff * h_coeff)**2)
            angle = self.radian_to_angle(math.atan2(y_diff, x_diff))
            if x_center >= self.img_center_x and y_center < self.img_center_y:
                adjusted_angle = angle
            elif x_center < self.img_center_x and y_center < self.img_center_y:
                adjusted_angle = 180 - angle
            elif x_center < self.img_center_x and y_center >= self.img_center_y:
                adjusted_angle = angle + 180
            else:
                adjusted_angle = 360 - angle
            bearing = 450 - adjusted_angle + self.drone_yaw
            dest = self.calculate_roi_coord_with_line_len(line_len, bearing, center=self.live_location)
            coords.append((dest.latitude, dest.longitude))
        return coords


def run_production_mode():
    logger.debug("=== PRODUCTION MODE ===")
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.set('cf_done', 'False')
    while r.get('ip_done') != b'True':
        time.sleep(1)
    time.sleep(2)

    if r.get('sicti') == b'True':
        logger.debug("Exiting due to sicti flag.")
        r.set('cf_done', 'True')
        sys.exit()

    with open("config.json", "r") as f:
        config = json.load(f)
    counter = config['counter']
    detection_file = config['detection_file'] + str(counter) + ".csv"
    position_file = config['position_file'] + str(counter) + ".csv"

    try:
        df_results = pd.read_csv(detection_file)
        df_positions = pd.read_csv(position_file)
    except Exception as e:
        logger.debug(f"File read error: {e}")
        return

    merged_df = pd.merge(df_results, df_positions, on="image", how="inner")
    image_shape = (4032, 3040)
    focal_length = 8
    sensor_size = [6.287, 4.712]

    roi_results = []
    for _, row in merged_df.iterrows():
        norm_x = row['center_x'] / image_shape[0]
        norm_y = row['center_y'] / image_shape[1]
        cf = CoordinateFinder(
            img_shape=image_shape,
            live_location=[row['lat'], row['lon']],
            drone_yaw=row['yaw'],
            focal_length=focal_length,
            sensor_size=sensor_size,
            drone_altitude=row['alt']
        )
        coords = cf.roi_geo_coord_finder([(norm_x, norm_y)])
        lat, lon = coords[0] if coords else (None, None)
        roi_results.append({
            "image": row["image"],
            "class_name": row["class_name"],
            "confidence": row["confidence"],
            "roi_lat": lat,
            "roi_lon": lon
        })

    filtered = filter_by_spatial_distance(roi_results)
    df_roi_results = pd.DataFrame(filtered)
    # Eğer 4'ten az satır varsa, en tepedekini kopyalayarak tamamla
    if len(df_roi_results) < 4 and len(df_roi_results) > 0:
        top_row = df_roi_results.iloc[0]
        missing_count = 4 - len(df_roi_results)
        additional_rows = pd.DataFrame([top_row.to_dict()] * missing_count)
        df_roi_results = pd.concat([df_roi_results, additional_rows], ignore_index=True)


    
    output_file = f"roi_results{counter}.csv"
    df_roi_results.to_csv(output_file, index=False)
    logger.debug(f"ROI coordinates saved to '{output_file}'.")
    r.set('cf_done', 'True')

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ROI Localization Script")
    parser.add_argument('--mode', choices=['test', 'prod'], default='prod')
    args = parser.parse_args()
    run_production_mode()
