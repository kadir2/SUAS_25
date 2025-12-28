from mavlinkHandler import MAVLinkHandlerDronekit as MAVLinkHandler
from dronekit import connect, VehicleMode
import redis
import time
import os
import json
from pymavlink import mavutil
import cv2
import pandas as pd
from redis_helper import RedisHelper
import math
import logging



def gstreamer_pipeline(
    sensor_id=0,
    capture_width=3840,
    capture_height=2160,
    framerate=21,
    flip_method=0,
    awb_mode=0,
    exp_comp=0,
    aelock=False,
    awblock=False,
):
    """
    Return GStreamer pipeline string for nvarguscamerasrc
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} aelock=true awblock=true wbmode=-1 exposurecompensation=2 ee-mode=1 ee-strength=1 tnr-mode=1 tnr-strength=1 ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! appsink"
    )

class System:
    def __init__(self, config):

        self.img_dir = config['image_dir']
        

# --- Yeni klasör ve d
        self.init_logger()
        self.config = config
        os.system("echo Bismillahirrahmanirrahim.")
        self.isSimActivated = self.config['isSimActivated']
        self.counter = self.config['counter']
        self.MAPPING_PATH = self.config['mapping_dir'] + str(self.counter)
        self.SCAN_PATH = self.config['image_dir'] + str(self.counter)
        if not os.path.exists(self.SCAN_PATH):
            os.makedirs(self.SCAN_PATH)

        self.r = redis.Redis(host='localhost', port=6379, db=0)
        self.rhrh = RedisHelper()
        SERIAL = '/dev/ttyACM0' # Autopilot
        self.mavlink_handler = MAVLinkHandler(SERIAL)
        print(self.mavlink_handler.get_location())
        self.vehicle = self.mavlink_handler.master

        pipeline = gstreamer_pipeline(
        sensor_id=0,
        capture_width=3840,
        capture_height=2160,
        framerate=21,
        flip_method=0
        )
        self.logger.debug(f"Opening camera with pipeline:\n{pipeline}")
        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        # self.take_photo_opencv(self.SCAN_PATH, 1)
        # time.sleep(1)
        # self.take_photo_opencv(self.SCAN_PATH, 2)
        # time.sleep(1)
        # self.take_photo_opencv(self.SCAN_PATH, 3)
        
    def init_logger(self):
        self.logger = logging.Logger('main')
        # Set the log level
        self.logger.setLevel(logging.DEBUG)
        # Create handlers
        c_handler = logging.StreamHandler()
        f_handler = logging.FileHandler('LOGS/main.log')

        # Set levels for handlers
        c_handler.setLevel(logging.DEBUG)
        f_handler.setLevel(logging.DEBUG)

        # Create formatters and add it to handlers
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers to the self.logger
        self.logger.addHandler(c_handler)
        self.logger.addHandler(f_handler)

        # Add handlers to the root self.logger to capture all logs
        root_logger = logging.getLogger()
        root_logger.addHandler(c_handler)
        root_logger.addHandler(f_handler)

    def land(self, lat, lon, alt):
        self.mavlink_handler.simple_go_to(lat, lon, alt, block=True, distance_radius=1)
        time.sleep(2)
        self.logger.debug("Landing...")
        self.vehicle.mode = VehicleMode("LAND")

    def set_yaw(self,heading, relative=False):
        if relative:
            is_relative=1 #yaw relative to direction of travel
        else:
            is_relative=0 #yaw is an absolute angle
            print("Using absolute direction")
        # create the CONDITION_YAW command using command_long_encode()
        msg = self.vehicle.message_factory.command_long_encode(
            0, 0,    # target system, target component
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,  # DOĞRU! Komut olarak sabit MAVLink komutu kullanılmalı.
            0, # confirmation
            heading,    # param 1, hedef yaw açısı
            0,          # param 2, yaw dönüş hızı (isteğe bağlı artırabilirsin)
            1,          # param 3, CW veya CCW dönüş yönü
            is_relative, # param 4, relative offset 1, absolute angle 0
            0, 0, 0)    # param 5 ~ 7 not used
        # send command to vehicle
        self.vehicle.send_mavlink(msg)
        is_yawing = True
        while is_yawing:
            current_yaw = int(self.vehicle.attitude.yaw * (180 / math.pi))
            if current_yaw< 0:
                current_yaw +=360

            if heading-3 < current_yaw < heading+3:
                print("YAW BİTTİ")
                is_yawing = False
            else:
                print("YAWİNG DEVAM EDİYOR")
                time.sleep(0.5)
                continue
    def take_photo_opencv(self, folder, index):
        # Kamera ısınsın diye 3 saniye boyunca sürekli frame oku
        start_time = time.time()
        while time.time() - start_time < 3.5:
            if self.cap.isOpened():
                self.cap.read()
            else:
                self.logger.debug("Error: Unable to open camera for warm-up.")
                return

        # Klasör yoksa oluştur
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        if not self.cap.isOpened():
            self.logger.debug("Error: Unable to open camera for live preview.")
            self.cap.release()
            return

        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.logger.debug("Error: Unable to read frame from camera.")
            self.cap.release()
            return

        img_path = os.path.join(folder, f"image_{index}.jpg")
        cv2.imwrite(img_path, frame)
        self.logger.debug(f"Saved photo to {img_path}")




    def take_screenshot_frame(self,folder,index):
        if not os.path.exists(folder):
            os.makedirs(folder)
        t1= time.time()
        output_path = f'./{folder}/image_{index}.jpg'
        frame = self.rhrh.from_redis('frame')
        time.sleep(1)
        while True:
            time.sleep(0.1)
            if time.time()-t1>=4:
                cv2.imwrite(output_path, frame)
                cv2.waitKey(1)
                break
        print("Capturing is done...")
        t2=time.time()
        print(f"It took {t2-t1} ms")

    def get_vehicle_position(self):
        """
        Eski json() fonksiyonunun işlevini gören, drone'ın konum bilgilerini ve diğer verileri sözlük olarak döndüren fonksiyon.
        """
        jsonlat = self.vehicle.location.global_relative_frame.lat
        jsonlon = self.vehicle.location.global_relative_frame.lon
        jsonalt = self.vehicle.location.global_relative_frame.alt
        jsonheading = self.vehicle.heading
        return {"lat": jsonlat, "lon": jsonlon, "alt": jsonalt, "yaw": jsonheading}
        
                
    def start_mapping(self, points, mapping_yaw, mapping_alt,sim=False):
        time.sleep(2)
        self.set_yaw(mapping_yaw)
        """
        0
        Never change yaw
        1
        Face next waypoint
        2
        Face next waypoint except RTL
        3
        Face along GPS course
        """
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 0)
        self.logger.debug('SET Yaw Behaviour: 0, Never change yaw')
        time.sleep(1)

        for i in range(1,len(points)+1):
            time.sleep(0.5)
            self.logger.debug(f"Points: {points[i-1][0]}, {points[i-1][1]}")
            self.mavlink_handler.simple_go_to(float(points[i-1][0]),float(points[i-1][1]),20, block=True, distance_radius=1.5)
            self.logger.debug("Reached the target point and going to take photo")

            if self.isSimActivated:
                self.take_screenshot_frame(self.MAPPING_PATH, i)
            else:
                self.take_photo_opencv(self.MAPPING_PATH, i)

        
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 1)
        self.logger.debug('SET Yaw Behaviour: 1, Face next waypoint')
        self.logger.debug('FINISHED MAPPING')

    def start_scanning(self,points, drop_yaw, scan_alt,sim=False):
        time.sleep(2)
        self.set_yaw(drop_yaw)
        """
        0
        Never change yaw
        1
        Face next waypoint
        2
        Face next waypoint except RTL
        3
        Face along GPS course
        """
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 0)
        self.logger.debug('SET Yaw Behaviour: 0, Never change yaw')
        time.sleep(1)

        # Konum verilerini saklamak için liste
        position_data = []

        for i in range(1,len(points)+1):
            time.sleep(0.5)
            self.logger.debug(f"Points: {points[i-1][0]} {points[i-1][1]}")
            self.mavlink_handler.simple_go_to(float(points[i-1][0]),float(points[i-1][1]),20, block=True, distance_radius=1)
            self.logger.debug("Reached the target point and going to take photo")

            # Konum verilerini al ve ilgili fotoğraf ismiyle ilişkilendir.
            pos_data = self.get_vehicle_position()
            pos_data["image"] = f"image_{i}.jpg"
            position_data.append(pos_data)

            if self.isSimActivated:
                time.sleep(1)
                self.take_screenshot_frame(self.SCAN_PATH, i)
                time.sleep(0.1)
            else:
                self.take_photo_opencv(self.SCAN_PATH, i)

        # Döngü tamamlandıktan sonra, konum verilerini CSV'ye yazalım.
        df_positions = pd.DataFrame(position_data)
        csv_path = f"position_data{self.counter}.csv"
        
        if os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0:
            with open(csv_path, 'w') as f:
                f.truncate(0)
            print(f"{csv_path} dosyasının içeriği temizlendi.")
        else:
            print(f"{csv_path} dosyası ya mevcut değil ya da zaten boş.")

        df_positions.to_csv(csv_path, index=False)
        print(f"Position data saved to {csv_path}")

        
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 1)
        self.logger.debug('SET Yaw Behaviour: 1, Face next waypoint')

    def sim_fake_drop(self,coords):
        count = 0
        for roi in coords:
            self.logger.debug(f"konuma gidiliyor: {roi}")
            lat, lon = roi
            self.mavlink_handler.simple_go_to(lat,lon,20, block=True, distance_radius=1)
            time.sleep(2) #drop yapma süresi dümenden
            self.logger.debug(f"droplandı")
            count += 1
            print(f"count={count}")
            if count <= 4:
                time.sleep(5)
                self.logger.debug(f"drop içibn sağlamlaştrımabeklemesiş")
            else:
                pass
            
        self.logger.debug("GÖREV TAMAM")

    def main(self):
        self.r.set('start_mapping', 'False')
        self.r.set('ip_done', 'False')
        self.r.set('start_ip', 'False')
        self.r.set('cf_done', 'False')   
        os.system("bash system.sh") # Starts the processing system
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 1)
        self.logger.debug('SET Yaw Behaviour: 1')

        # Set the mode to GUIDED
        time.sleep(1)
        # self.vehicle.mode = VehicleMode("GUIDED")
        
        # Wait until the mode has been set
        while not self.vehicle.mode.name == "GUIDED":
            self.logger.debug("Waiting for mode change to: GUIDED")
            time.sleep(0.5)
        self.logger.debug("Mode: GUIDED")

        self.r.set('start_ip', 'True') # start image processing 
        self.points = [(self.config["Points"][f"{i}"]["Latitude"], self.config["Points"][f"{i}"]["Longitude"]) for i in range(1,len(self.config["Points"])+1)]
        self.drop_yaw = self.config["DROP_YAW"]
        self.scan_alt = self.config["image_alt"]
        self.start_scanning(points=self.points, drop_yaw=self.drop_yaw, scan_alt=self.scan_alt, sim=self.isSimActivated)

        # Wait until 'image processing' is done
        while True:
            image_proc_done = self.r.get('ip_done')
            if image_proc_done:
                break
            time.sleep(1)

        # 'cf_done' sinyalini bekle
        print("Waiting for 'cf_done' signal...")
        while True:
            start_ip = self.r.get('cf_done')
            if start_ip and start_ip.decode('utf-8') == 'True':
                time.sleep(5)
                break
            time.sleep(1)
        print("CF DONE")
        
        # ROI koordinatlarının bulunduğu CSV dosyasını okuyalım:
        try:
            df_roi = pd.read_csv(f"roi_results{self.counter}.csv")
            # df_roi, "roi_lat" ve "roi_lon" sütunlarını içeriyor
            best_rois_coords = list(df_roi[['roi_lat', 'roi_lon']].itertuples(index=False, name=None)) # example data: best_rois_coords = [(41.101, 29.002), (41.102, 29.003), (41.103, 29.004), (41.104, 29.005)]
            print(f"best_rois: {best_rois_coords}")
        except Exception as e:
            print("Error reading roi_results.csv: ", e)
            best_rois_coords = []

        self.sim_fake_drop(best_rois_coords)

        # land_latitude = self.config["LandCoordinates"]["Latitude"]
        # land_longitude = self.config["LandCoordinates"]["Longitude"]
        # print(f"landing on: {land_latitude},{land_longitude}")
        # self.land(land_latitude, land_longitude, 26)

if __name__ == '__main__':
    with open('config.json') as f:
        config = json.load(f)

    system = System(config=config)
    system.main()