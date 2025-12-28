
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
import geopy
import itertools
from datetime import datetime
import shutil

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=3840,
    capture_height=2160,
    framerate=30,
    flip_method=0,
):
    """
    Return GStreamer pipeline string for nvarguscamerasrc
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} aelock=true awblock=true wbmode=-1 exposurecompensation=-1.5 ee-mode=1 ee-strength=1 tnr-mode=1 tnr-strength=1 ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! appsink"
    )

class Loggerr:
    def __init__(self):
        # Logger oluştur
        self.logger = logging.Logger('UAV_Handler')
        self.logger.setLevel(logging.DEBUG)  # Log seviyesi DEBUG olarak ayarlanır
        
        # Handlers: Konsol ve Dosya
        c_handler = logging.StreamHandler()  # Konsol için handler
        log_file_path = 'UAV_Handler.log'  # Log dosyasının adı
        old_logs_dir = "old_logs_UAV_Handler"  # Eski log dosyalarının taşınacağı klasör

        # Eski log dosyalarını yedekle
        if not os.path.exists(old_logs_dir):  # Eğer klasör yoksa oluştur
            os.makedirs(old_logs_dir)
        if os.path.exists(log_file_path):  # Eğer log dosyası varsa
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # Zaman damgası oluştur
            new_log_file_name = f"UAV_Handler_{timestamp}.log"  # Yeni log dosyasının adı
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
# Kullanım
logger_instance = Loggerr()  # Logger nesnesi oluştur
logger = logger_instance.logger   # Logger nesnesini al

class System:
    def __init__(self, config):

        self.img_dir = config['image_dir']

# --- Yeni klasör ve d
        self.config = config
        os.system("echo Bismillahirrahmanirrahim.")
        self.isSimActivated = self.config['isSimActivated']
        self.counter = self.config['counter']
        self.MAPPING_PATH = self.config['mapping_dir'] + str(self.counter)
        self.SCAN_PATH = self.config['image_dir'] + str(self.counter)
    
        if not os.path.exists(self.SCAN_PATH):
            os.makedirs(self.SCAN_PATH)
        
        if not os.path.exists(self.MAPPING_PATH):
            os.makedirs(self.MAPPING_PATH)

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
        logger.debug(f"Opening camera with pipeline:\n{pipeline}")
        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        # self.take_photo_opencv(self.SCAN_PATH, 1)
        # time.sleep(1)
        # self.take_photo_opencv(self.SCAN_PATH, 2)
        # time.sleep(1)
        # self.take_photo_opencv(self.SCAN_PATH, 3)
        self.drop_info =[
            (self.config["ObjectServo"]["1"]["Channel"], self.config["ObjectServo"]["1"]["PWM"]),
            (self.config["ObjectServo"]["2"]["Channel"], self.config["ObjectServo"]["2"]["PWM"]),
            (self.config["ObjectServo"]["3"]["Channel"], self.config["ObjectServo"]["3"]["PWM"]),
            (self.config["ObjectServo"]["4"]["Channel"], self.config["ObjectServo"]["4"]["PWM"])
            ]
        
        self.set_servo(self.config["MechanismServo"]["Close"]["Channel"], self.config["MechanismServo"]["Close"]["PWM"]) # Mekanizma tutma asamasinda
        time.sleep(5)
        self.set_servo(self.config["AttributeServo"]["Release"]["Channel"], self.config["AttributeServo"]["Release"]["PWM"]) # Motorları serbest bırak uçuş öncesi

    def set_servo(self, channel, pwm_value):
            if (channel is None) or (pwm_value is None):
                logging.error("set_servo function doesn't have arguments.")

            try:
                pwm_value_int = int(pwm_value)
                msg = self.vehicle.message_factory.command_long_encode(
                    0, 0, 
                    mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                    0,
                    channel,
                    pwm_value_int,
                    0,0,0,0,0)

                self.vehicle.send_mavlink(msg)
                
                logger.debug(f"set_servo function has successfully executed. With arguments: Channel: {channel}, PWM Value: {pwm_value}")
            except Exception as e:
                logger.debug(f"Error occured in set_servo function: {e}")

    # def land(self, lat, lon, alt):
    #     self.mavlink_handler.simple_go_to(lat, lon, alt, block=True, distance_radius=1)
    #     time.sleep(2)
    #     logger.debug("Landing...")
    #     self.vehicle.mode = VehicleMode("LAND")

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
                logger.debug("Error: Unable to open camera for warm-up.")
                return

        # Klasör yoksa oluştur
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        if not self.cap.isOpened():
            logger.debug("Error: Unable to open camera for live preview.")
            self.cap.release()
            return

        ret, frame = self.cap.read()
        if not ret or frame is None:
            logger.debug("Error: Unable to read frame from camera.")
            self.cap.release()
            return

        img_path = os.path.join(folder, f"image_{index}.jpg")
        cv2.imwrite(img_path, frame)
        logger.debug(f"Saved photo to {img_path}")

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
        logger.debug('SET Yaw Behaviour: 0, Never change yaw')
        time.sleep(1)

        for i in range(1,len(points)+1):
            time.sleep(0.5)
            logger.debug(f"Points: {points[i-1][0]}, {points[i-1][1]}")
            self.mavlink_handler.simple_go_to(float(points[i-1][0]),float(points[i-1][1]),20, block=True, distance_radius=1.5)
            logger.debug("Reached the target point and going to take photo")

            self.take_photo_opencv(self.MAPPING_PATH, i)

        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 1)
        logger.debug('SET Yaw Behaviour: 1, Face next waypoint')
        logger.debug('FINISHED MAPPING')

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
        logger.debug('SET Yaw Behaviour: 0, Never change yaw')
        time.sleep(1)

        # Konum verilerini saklamak için liste
        position_data = []

        for i in range(1,len(points)+1):
            time.sleep(0.5)
            logger.debug(f"Points: {points[i-1][0]} {points[i-1][1]}")
            self.mavlink_handler.simple_go_to(float(points[i-1][0]),float(points[i-1][1]),20, block=True, distance_radius=1)
            logger.debug("Reached the target point and going to take photo")

            # Konum verilerini al ve ilgili fotoğraf ismiyle ilişkilendir.
            pos_data = self.get_vehicle_position()
            pos_data["image"] = f"image_{i}.jpg"
            position_data.append(pos_data)

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
        logger.debug('SET Yaw Behaviour: 1, Face next waypoint')

    def fake_drop(self,coords):
        count = 0
        for roi in coords:
            logger.debug(f"konuma gidiliyor: {roi}")
            lat, lon = roi
            self.mavlink_handler.simple_go_to(lat,lon,20, block=True, distance_radius=1)
            time.sleep(2) #drop yapma süresi dümenden
            logger.debug(f"droplandı")
            count += 1
            print(f"count={count}")
            if count <= 4:
                time.sleep(5)
                logger.debug(f"drop içibn sağlamlaştrımabeklemesiş")
            else:
                pass
            
        logger.debug("GÖREV TAMAM")

    def real_drop(self, coords):
        """
        Gerçek drop işlemi: her koordinatta servo çalıştırılır.
        coords: [(lat, lon), ...]
        """
        for idx, (lat, lon) in enumerate(coords):
            logger.debug(f"konuma gidiliyor: {(lat, lon)}")
            # Hedefe git
            self.mavlink_handler.simple_go_to(lat, lon, 20, block=True, distance_radius=1)
            # Servo bilgisini al
            try:
                channel, pwm = self.drop_info[idx]
            except IndexError:
                logger.error(f"Drop info bulunamadı index: {idx}")
                continue
            # Servoyu aktive et
            self.set_servo(channel, pwm)
            logger.debug(f"Servo activated: channel={channel, pwm}")
            # Bırakma süresi
            time.sleep(30)
            # Servoyu resetle (PWM=0)
            self.set_servo(channel, 0)
            logger.debug(f"Servo deactivated: channel={channel}")
        logger.debug("GÖREV TAMAM")

    def main(self):
        self.r.set('start_mapping', 'False')
        self.r.set('ip_done', 'False')
        self.r.set('start_ip', 'False')
        self.r.set('cf_done', 'False')   
        os.system("bash system.sh") # Starts the processing system
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 1)
        logger.debug('SET Yaw Behaviour: 1')

        # Set the mode to GUIDED
        time.sleep(1)
        # self.vehicle.mode = VehicleMode("GUIDED")
        
        # Wait until the mode has been set
        while not self.vehicle.mode.name == "GUIDED":
            logger.debug("Waiting for mode change to: GUIDED")
            time.sleep(0.5)
        logger.debug("Mode: GUIDED")

        self.mapping_points = [(self.config["MappingPoints"][f"{i}"]["Latitude"], self.config["MappingPoints"][f"{i}"]["Longitude"]) for i in range(1,len(self.config["MappingPoints"])+1)]
        self.mapping_yaw = self.config["mapping_yaw"]
        self.mapping_alt = self.config["mapping_alt"]
        
        # Start mapping photo capture
        self.r.set('start_mapping', 'True')
        self.start_mapping(points=self.mapping_points, mapping_yaw=self.mapping_yaw, mapping_alt=self.mapping_alt, sim=self.isSimActivated)

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

        self.real_drop(best_rois_coords)
        # self.fake_drop(best_rois_coords)

if __name__ == '__main__':
    with open('config.json') as f:
        config = json.load(f)

    system = System(config=config)
    system.main()