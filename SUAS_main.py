
from mavlinkHandler import MAVLinkHandlerDronekit as MAVLinkHandler
from dronekit import connect, VehicleMode
import redis
import time
import os
import json
from pymavlink import mavutil
import cv2
import pandas as pd
import math
import logging
import geopy
import itertools
from datetime import datetime
import shutil
import threading
import sys


#bu kodu değiştirmeyin izinsiz pushlanmayın trashe atmayın



def gstreamer_pipeline(
    sensor_id=0,
    capture_width=3840,
    capture_height=2160,
    framerate=29,
    flip_method=0,
    awb_mode=0,
    exp_comp=0,
    aelock=False,
    awblock=False,
    sensor_mode=0,

):
    """
    Return GStreamer pipeline string for nvarguscamerasrc
    """
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} aelock=false awblock=true wbmode=0 exposurecompensation=-1 ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! appsink"
    )

class Loggerr:
    def __init__(self):
        self.logger = logging.getLogger('SUAS')
        self.logger.setLevel(logging.DEBUG)

        c_handler = logging.StreamHandler()
        log_file_path = 'SUAS.log'
        old_logs_dir = "old_logs_SUAS"

        if not os.path.exists(old_logs_dir):
            os.makedirs(old_logs_dir)
        if os.path.exists(log_file_path):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            new_log_file_path = os.path.join(old_logs_dir, f"SUAS_{timestamp}.log")
            shutil.move(log_file_path, new_log_file_path)

        f_handler = logging.FileHandler(log_file_path)

        c_handler.setLevel(logging.DEBUG)
        f_handler.setLevel(logging.DEBUG)

        # Konsol ve dosya için fonksiyon ve satır numarası gibi detayları içeren format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
        )

        c_handler.setFormatter(formatter)
        f_handler.setFormatter(formatter)

        self.logger.addHandler(c_handler)
        self.logger.addHandler(f_handler)

# Kullanım örneği
logger_instance = Loggerr()
logger = logger_instance.logger



class Stop():
    def __init__(self):
        try:
        # Reference mavlink handler and logger from global system
            self.mavlink_handler = system.mavlink_handler

            # Event to control pause/resume
            self.pulse_event = threading.Event()
            self.pulse_event.set()

            # Begin tracing in all threads
            sys.settrace(self.trace)
            threading.settrace(self.trace)

            # Initialize prev_mode to the actual current flight mode
            self.prev_mode = self.mavlink_handler.get_mode()
            logger.debug(f"Initial flight mode: {self.prev_mode}")
            
            #print(self.mavlink_handler.get_mode())
            self.time_interval = 0.01
            self.last_wp = None
            self.state = 1
        except Exception as e:
            logger.debug(f"Error initializing Stop class: {e}")

        # Launch watcher thread
        threading.Thread(target=self.watcher, daemon=True).start()

    def trace(self, frame, event, arg):
        # Pause execution at each new line if event is cleared
        if event == "line":
            self.pulse_event.wait()
        return self.trace
    
    def pasue(self, mode):
        logger.debug(f"Pausing execution in mode: {mode}")
        system.wait_state = 0
        self.state = 0
        self.pulse_event.clear()
    
    def resume(self, mode):
        if self.last_wp and mode == "GUIDED":
            logger.debug(f"Resuming at last waypoint: {self.last_wp}")
            # Send resume command
            self.mavlink_handler.simple_go_to(self.last_wp[0], self.last_wp[1], self.last_wp[2], block=True, distance_radius=1.5)
            system.wait_state = 1
        self.state = 1
        self.pulse_event.set()


    
    def watcher(self):
        # Disable tracing inside watcher itself
        sys.settrace(None)
        threading.settrace(None)

        while True:
            try:
                # Check for flight mode changes
                mode = self.mavlink_handler.get_mode()
                self.last_wp = system.last_wp
                if mode != self.prev_mode:
                    logger.debug(f"Mode changed: {self.prev_mode} -> {mode}")
                    self.on_mode_change(mode)
                    self.prev_mode = mode
                time.sleep(self.time_interval)
            except Exception as e:
                logger.debug(f"Error in watcher: {e}")
                time.sleep(0.1)

    def on_mode_change(self, mode):
        # Resume execution when re-entering GUIDED/AUTO
        if self.state == 0 and mode in ["GUIDED", "AUTO"]:
            self.resume(mode)
            
        # Pause execution when leaving GUIDED/AUTO
        elif self.state == 1 and mode not in ["GUIDED", "AUTO"]:
            self.pasue(mode)

        else:
            logger.debug(f"Unhandled mode change: {mode}")







class System:
    def __init__(self, config):
    
# --- Yeni klasör ve d
        self.config = config
        os.system("echo Bismillahirrahmanirrahim.")
        self.isSimActivated = self.config['isSimActivated']
        self.counter = self.config['counter']
        self.SCAN_PATH = self.config['image_dir'] + str(self.counter)
        self.DropAltitude = self.config['DropAltitude']  # Default drop altitude
        self.scan_alt = self.config["image_alt"]
        self.mapping_alt = self.config["mapping_alt"]
        self.points = [(self.config["Points"][f"{i}"]["Latitude"], self.config["Points"][f"{i}"]["Longitude"]) for i in range(1,len(self.config["Points"])+1)]
        self.drop_yaw = self.config["DROP_YAW"]
        self.WP_SPEED = self.config["WP_SPEED"]
        self.DROP_SPEED = self.config["DROP_SPEED"]
        self.DropDelay = self.config["DropDelay"]

        self.last_wp = None
        self.wait_state = None
        if not os.path.exists(self.SCAN_PATH):
            os.makedirs(self.SCAN_PATH)
        

        self.r = redis.Redis(host='localhost', port=6379, db=0)
        SERIAL = "/dev/ttyACM0"
        #'/dev/ttyACM0' # Autopilot
        self.mavlink_handler = MAVLinkHandler(SERIAL)
        logger.debug(self.mavlink_handler.get_location())
        self.vehicle = self.mavlink_handler.master
        self.last_wp = None
        self.wait_state = None
        try:
            pipeline = gstreamer_pipeline()
            logger.debug(f"Opening camera with pipeline:\n{pipeline}")

            self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        except Exception as e:
            logger.debug(f"Error opening camera: {e}")
            self.cap = None

        # self.take_photo_opencv('init_test_photo', 1)
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
        
    def set_servo(self, channel, pwm_value):
            if (channel is None) or (pwm_value is None):
                logger.debug("set_servo function doesn't have arguments.")

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


    def land(self, lat, lon, alt):
        self.mavlink_handler.simple_go_to(lat, lon, alt, block=True, distance_radius=1.5)
        time.sleep(1)
        logger.debug("Landing...")
        self.vehicle.mode = VehicleMode("LAND")


    def wait(self, target, distance_radius=1.5):
        logger.debug(f"waite girildi timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(0.1)
        logger.debug("Waiting for the vehicle to reach the target point...")
        while True:
            try:
                logger.debug(f"pozisyon alınıyor timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                current_pos = self.get_vehicle_position()
                logger.debug(f"pozisyon alındı: timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                distance = geopy.distance.distance((current_pos["lat"], current_pos["lon"]), (target[0], target[1])).m
                #print(f"Distance to target: {distance} m")
                if distance < distance_radius or self.wait_state == 1:
                    logger.debug("Reached the target point after the break")
                    self.wait_state = 0
                    break
            except Exception as e:
                logger.debug(f"Error in wait function: {e}")

    def set_yaw(self,heading, relative=False):
        if relative:
            is_relative=1 #yaw relative to direction of travel
        else:
            is_relative=0 #yaw is an absolute angle
            logger.debug("Using absolute direction")
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
                logger.debug("YAW BİTTİ")
                is_yawing = False
            else:
                logger.debug("YAWİNG DEVAM EDİYOR")
                time.sleep(0.5)
                continue
    def take_photo_opencv(self, folder, index):
        try:    
            # Kamera ısınsın diye 3 saniye boyunca sürekli frame oku
            time.sleep(0.5)
            start_time = time.time()
            while time.time() - start_time <= 3:
                if self.cap.isOpened():
                    self.cap.read()
                else:
                    logger.debug("Error: Unable to open camera for warm-up.")
                    return

            # Klasör yoksa oluştur
            if not os.path.exists(folder):
                os.makedirs(folder)
            
            # if not self.cap.isOpened():
            #     logger.debug("Error: Unable to open camera for live preview.")
            #     self.cap.release()
            #     return

            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.debug("Error: Unable to read frame from camera.")
                self.cap.release()
                return

            img_path = os.path.join(folder, f"image_{index}.jpg")
            cv2.imwrite(img_path, frame)
            logger.debug(f"Saved photo to {img_path}")
        except Exception as e:
            logger.debug(f"Error in take_photo_opencv: {e}")

    def get_vehicle_position(self):
        """
        Eski json() fonksiyonunun işlevini gören, drone'ın konum bilgilerini ve diğer verileri sözlük olarak döndüren fonksiyon.
        """
        jsonlat = self.vehicle.location.global_relative_frame.lat
        jsonlon = self.vehicle.location.global_relative_frame.lon
        jsonalt = self.vehicle.location.global_relative_frame.alt
        jsonheading = self.vehicle.heading
        return {"lat": jsonlat, "lon": jsonlon, "alt": jsonalt, "yaw": jsonheading}

    



    def start_scanning(self,points, drop_yaw, scan_alt,sim=False):

        time.sleep(1.5)
        self.set_yaw(drop_yaw)
        """
        0
        Never change yaw
        1
        Face next waypoint
        2
        Face next waypoint except RTL
        3
        Face along GPS course1
        """
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 0)
        logger.debug('SET Yaw Behaviour: 0, Never change yaw')
        time.sleep(1)

        # Konum verilerini saklamak için liste
        position_data = []

        for i in range(1,len(points)+1):  
          
            time.sleep(0.5)
            logger.debug(f"Points: {points[i-1][0]} {points[i-1][1]}")
            self.last_wp = (float(points[i-1][0]), float(points[i-1][1]), float(self.scan_alt))
            logger.debug(f"scanning noktasına gidiliyor: timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.mavlink_handler.simple_go_to(float(points[i-1][0]),float(points[i-1][1]),self.scan_alt, block=False, distance_radius=1.5)
            logger.debug(f"simplegoto verildi: timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.wait((float(points[i-1][0]), float(points[i-1][1])), distance_radius=3)
            logger.debug(f"wait fonksiyonu bitti: timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.debug("Reached the target point and going to take photo")

            #-----------------------------------------------------------------------
            #
            #        CONFİGDEKİ MAPPING IMAGE DIR'İ DEĞİŞTİRMEYİ UNUTMA
            #
            #-----------------------------------------------------------------------

            # Konum verilerini al ve ilgili fotoğraf ismiyle ilişkilendir.
            pos_data = self.get_vehicle_position()
            pos_data["image"] = f"image_{i}.jpg"
            position_data.append(pos_data)
            logger.debug(f"fotoğraf çekilecek. timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.take_photo_opencv(self.SCAN_PATH, i)
            logger.debug(f"fotoğraf çekildi. timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Döngü tamamlandıktan sonra, konum verilerini CSV'ye yazalım.
        df_positions = pd.DataFrame(position_data)
        csv_path = f"position_data{self.counter}.csv"
        
        if os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0:
            with open(csv_path, 'w') as f:
                f.truncate(0)
            logger.debug(f"{csv_path} dosyasının içeriği temizlendi.")
        else:
            logger.debug(f"{csv_path} dosyası ya mevcut değil ya da zaten boş.")

        df_positions.to_csv(csv_path, index=False)
        logger.debug(f"Position data saved to {csv_path}")

        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 1)
        logger.debug('SET Yaw Behaviour: 1, Face next waypoint')

    def fake_drop(self,coords):
        count = 0
        for roi in coords:
            logger.debug(f"konuma gidiliyor: {roi}")
            lat, lon = roi
            self.mavlink_handler.simple_go_to(lat,lon,20, block=False, distance_radius=1.5)
            self.last_wp = (lat, lon, 30)
            self.wait(lat, lon, distance_radius=3)
            time.sleep(2) #drop yapma süresi dümenden
            logger.debug(f"droplandı")
            count += 1
            logger.debug(f"count={count}")
            if count <= 4:
                time.sleep(5)
                logger.debug(f"drop için sağlamlaştrıma beklememiş")
            else:
                pass
            
        logger.debug("GÖREV TAMAM")

    def real_drop(self, coords):
        """
        Gerçek drop işlemi: her koordinatta servo çalıştırılır.
        coords: [(lat, lon), ...]
        """
        try:
            for idx, (lat, lon) in enumerate(coords):    
                
                logger.debug(f"konuma gidiliyor: {(lat, lon)}")
                # Hedefe git
                self.vehicle.parameters['WP_YAW_BEHAVIOR'] = 1
                self.last_wp = (lat, lon, self.DropAltitude)
                self.mavlink_handler.simple_go_to(lat, lon, self.DropAltitude, block=False, distance_radius=1.5)
                self.wait((lat, lon), distance_radius=3)
                # Servo bilgisini al
                try:
                    channel, pwm = self.drop_info[idx]
                except IndexError:
                    logger.debug(f"Drop info bulunamadı index: {idx}")
                    continue
                # Servoyu aktive et
                self.set_servo(channel, pwm)
                logger.debug(f"Servo activated: channel={channel, pwm}")
                time.sleep(2)
                # Servoyu resetle (PWM=0)
                self.set_servo(channel, 0)
                logger.debug(f"Servo deactivated: channel={channel}")
                # Bırakma süresit
                time.sleep(self.DropDelay)
                if idx < 3 :
                    self.vehicle.parameters['WP_YAW_BEHAVIOR'] = 1
                    self.turn_lap()
                    logger.debug(f"Pathe gidiliyor {idx+2}")
        except Exception as e:
            logger.debug(f"Error during drop operation: {e}")
    


    def turn_lap(self):
        try:

            logger.debug("Turn Lap")

            self.vehicle.parameters['WPNAV_SPEED'] = self.WP_SPEED

            cmds = self.vehicle.commands
            cmds.download()
            cmds.wait_ready()
            logger.debug("Download Waypoints - Completed")
            self.vehicle.commands.next = 2
            logger.debug("WP SET TO 1")
            time.sleep(0.5)
            if self.vehicle.mode == "GUIDED":
                self.vehicle.mode = VehicleMode("AUTO")
                time.sleep(0.05)
                logger.debug(f"{self.vehicle.mode} moduna geçildi")
            else:
                logger.debug("Vehicle is not in GUIDED mode, exiting turn lap.")

            wp_num = len([cmd for cmd in cmds])

            while True:
                time.sleep(0.05)
                logger.debug(f"next wp: {self.vehicle.commands.next}")
                logger.debug(f"wp_num:{wp_num}")
                if self.vehicle.commands.next == wp_num :
                    logger.debug("Air Drop Stage")
                    break

            # Set the mode to GUIDED
            time.sleep(0.5)
            if self.vehicle.mode == "AUTO":
                self.vehicle.mode = VehicleMode("GUIDED")
                time.sleep(0.05)
                logger.debug(f"{self.vehicle.mode} moduna geçildi")
            else:
                logger.debug("Vehicle is not in AUTO mode, exiting turn lap.")


            self.vehicle.parameters['WPNAV_SPEED'] = self.DROP_SPEED

        except Exception as e:
            logger.debug(f"Error during turn lap: {e}")


    def main(self):
        self.r.set('start_mapping', 'False')
        self.r.set('ip_done', 'False')
        self.r.set('start_ip', 'False')
        self.r.set('cf_done', 'False')   
        os.system("bash system.sh") # Starts the processing system
        #os.system("echo '1' | sudo -S chmod a+rw /dev/ttyACM0") # Starts the processing syste
        self.vehicle.parameters['WP_YAW_BEHAVIOR'] = 1
        

        cmds = self.vehicle.commands
        cmds.download()
        cmds.wait_ready()
        logger.debug("Download Waypoints - Completed")

        self.vehicle.commands.next = 2
        logger.debug("WP SET TO 1")

        time.sleep(1)

        while len(cmds)<3:
            logger.debug("waypoint required ")
            time.sleep(0.05)

        missionlist=[]

        for cmd in cmds:
            missionlist.append(cmd)
        logger.debug(f"------------------------------{len(missionlist)}---------------------------")

        # Check if the last waypoint is a DO_JUMP command
        if missionlist[-1].command == mavutil.mavlink.MAV_CMD_DO_JUMP:
            logger.debug('------------------------------------------------------------------------')
            logger.debug("Last waypoint is DO_JUMP. Adding the previous waypoint to the end of the list.")
            logger.debug('------------------------------------------------------------------------')
            cmds.add(missionlist[-2])
        else:
            logger.debug('------------------------------------------------------------------------')
            logger.debug('No DOJUMP')
            logger.debug('------------------------------------------------------------------------')
            cmds.add(missionlist[-1])
           

        cmds.upload() # Send commands

        cmds = self.vehicle.commands
        cmds.download()
        cmds.wait_ready()
        logger.debug("Download Changed Waypoints - Completed")

        
        missionlist=[]

        for cmd in cmds:
            missionlist.append(cmd)
        logger.debug(f"------------------------------{len(missionlist)} - updated---------------------------")

        wp_num = len([cmd for cmd in cmds])


        # Wait until the mode has been set
        while not self.vehicle.mode.name == "AUTO":
            logger.debug("Waiting for mode change to: AUTO")
            time.sleep(0.5)
        
   
        self.land_poostition = self.mavlink_handler.get_location()
        logger.debug(f"Land Location: {self.land_poostition}")
        logger.debug("Mode: AUTO")

        logger.debug("aga ilk otoyol")

        self.vehicle.parameters['WPNAV_SPEED'] = self.WP_SPEED

        while True:
            time.sleep(1)
            logger.debug(f"next wp: {self.vehicle.commands.next}")
            logger.debug(f"wp_num:{wp_num}")
            if self.vehicle.commands.next  == wp_num  :
                logger.debug("Air Drop Stage")
                break

        # Set the mode to GUIDED
        time.sleep(1.5)
        if self.vehicle.mode == "AUTO":
           self.vehicle.mode = VehicleMode("GUIDED")
           time.sleep(0.05)
           logger.debug(f"{self.vehicle.mode} moduna geçildi")
        else:
            logger.debug("Vehicle is not in AUTO mode, exiting main.")

        self.vehicle.parameters['WPNAV_SPEED'] = self.DROP_SPEED

       
        self.r.set('start_ip', 'True') # start image processing 


        self.start_scanning(points=self.points, drop_yaw=self.drop_yaw, scan_alt=self.scan_alt, sim=self.isSimActivated)

        # Wait until 'image processing' is done
        while True:
            image_proc_done = self.r.get('ip_done')
            if image_proc_done:
                logger.debug("Image processing done")
                break
            time.sleep(0.5)

        self.r.set('start_mapping', 'True')
        # 'cf_done' sinyalini bekle
        logger.debug("Waiting for 'cf_done' signal...")
        
        while True:
            start_ip = self.r.get('cf_done')
            if start_ip and start_ip.decode('utf-8') == 'True':
                time.sleep(2)
                break
            
        logger.debug("CF DONE")
        
        # ROI koordinatlarının bulunduğu CSV dosyasını okuyalım:
        try:
            df_roi = pd.read_csv(f"roi_results{self.counter}.csv")
            # df_roi, "roi_lat" ve "roi_lon" sütunlarını içeriyor
            best_rois_coords = list(df_roi[['roi_lat', 'roi_lon']].itertuples(index=False, name=None)) # example data: best_rois_coords = [(41.101, 29.002), (41.102, 29.003), (41.103, 29.004), (41.104, 29.005)]
            logger.debug(f"best_rois: {best_rois_coords}")
        except Exception as e:
            logger.debug("Error reading roi_results.csv: ", e)
            best_rois_coords = []



        
        self.real_drop(best_rois_coords)
        # self.fake_drop(best_rois_coords)

        # landing process
        lat,lon, alt = self.land_poostition

        self.land(lat, lon, self.DropAltitude)
        logger.debug("Landing completed")

        logger.debug("Görev tamamlandı")

if __name__ == '__main__':
    with open('config.json') as f:
        config = json.load(f)

    system = System(config=config)
    stop = Stop()
    system.main()

