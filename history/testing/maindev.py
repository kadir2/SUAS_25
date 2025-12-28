from mavlinkHandler import MAVLinkHandlerDronekit as MAVLinkHandler
from dronekit import connect, VehicleMode
import logging
import redis
import time
import os
import json
import geopy
import itertools
from pymavlink import mavutil
import cv2
import pandas as pd
from redis_helper import RedisHelper

class BottleDropHandler():
    def __init__(self, vehicle, handler:MAVLinkHandler, config, drop_altitude=26, drop_delay=30):
        self.drop_wpl_counter = 0
        self.vehicle = vehicle
        self.config:dict = config
        self.drop_altitude = drop_altitude
        self.handler = handler
        self.drop_delay = drop_delay
        self.drop_info = [(self.config["ObjectServo"]["1"]["Channel"], self.config["ObjectServo"]["1"]["PWM"]),
                (self.config["ObjectServo"]["2"]["Channel"], self.config["ObjectServo"]["2"]["PWM"]),
                (self.config["ObjectServo"]["3"]["Channel"], self.config["ObjectServo"]["3"]["PWM"]),
                (self.config["ObjectServo"]["4"]["Channel"], self.config["ObjectServo"]["4"]["PWM"])]
        

    def drop_bottle(self, best_rois_coords):
        """
        best_rois_coords: [(lat, lon), ...] şeklinde en iyi ROI koordinatları listesi.
        Bu fonksiyon aracınızı sırasıyla drop noktalarına götürür, servo kontrolü ile şişeyi bırakır.
        """
        
        print("Best Coords: ", best_rois_coords)
        print("Drop Servo Info:", self.drop_info)

        time.sleep(2)
        
        shortest_path = self.updated_coords(best_rois_coords) # waypoint lap yaptığımız için bu aslında saçma
        
        try:
            for i in range(4):
                drop_speed = self.config.get('DROP_SPEED', 5)
                self.vehicle.parameters['WPNAV_SPEED'] = drop_speed
                
                lat, lon = shortest_path[i]
                self.handler.simple_go_to(lat, lon, self.ALT, block=True, distance_radius=1.5)
                logging.debug(f"Reached bottle drop: {i+1}")
                
                # SERVO CONTROL
                time.sleep(3)
                drop_index = best_rois_coords.index(shortest_path[i])
                # İşlem sonrası koordinatı işaretleyelim (örneğin, 0 yapalım)
                best_rois_coords[drop_index] = 0  
                print("Servo: ", self.drop_info[i])
                self.set_servo(self.drop_info[i][0], self.drop_info[i][1])
                time.sleep(2)
                self.set_servo(self.drop_info[i][0], 0)
                
                time.sleep(self.DROP_DELAY)
                logging.debug(f"Object {i+1} dropped successfully")

                print(f"Turn Lap: {i+2} Begin")
                self.turn_lap()
            
            logging.debug("All objects dropped successfully")
        except Exception as e:
            print(e)
            logging.error("Error occurred in drop_bottle function.")
            print("Error occurred!")

    def calculate_distance(self, path):
        """
        Verilen path (koordinat listesi) boyunca toplam mesafeyi (km cinsinden) hesaplar.
        Her iki nokta arasındaki mesafe geopy.distance.distance kullanılarak hesaplanır.
        """
        total = 0
        for i in range(len(path) - 1):
            total += geopy.distance.distance(path[i], path[i+1]).km
        return total


    def updated_coords(self, points):
        """
        Bu metod, araç başlangıç konumu, drop noktaları (points) ve iniş koordinatını içeren 
        tüm kombinasyonları (permutasyonları) değerlendirerek, toplam yol mesafesini minimize eden 
        en kısa yolu (optimum drop sırasını) bulur.
        
        İşleyişi:
         1. points listesindeki drop noktaları için tüm permutasyonlar oluşturulur.
         2. Her permutasyonun başına aracın mevcut konumu ve sonuna iniş (land_coord) koordinatı eklenir.
         3. Her bir yolun toplam mesafesi hesaplanır.
         4. En kısa mesafeye sahip yol seçilir.
         5. Seçilen yolun ilk elemanı (başlangıç noktası) hariç, belirli bir dilim döndürülür.
            (Bu örnekte dilimleme [1:6] yapılmış; sisteminizde drop noktası sayısına göre ayarlayın.)
        """
        all_permutations = itertools.permutations(points)  # Tüm permutasyonlar
        
        shortest_distance = float('inf')
        shortest_path = None

        # Her permutasyon için hesaplama yapılıyor:
        for path in all_permutations:
            # Mevcut aracın konumu, drop noktaları ve iniş koordinatını birleştiriyoruz.
            full_path = [(self.vehicle.location.global_relative_frame.lat, 
                          self.vehicle.location.global_relative_frame.lon)] + list(path) + [self.land_coord]
            distance = self.calculate_distance(full_path)
            
            if distance < shortest_distance:
                shortest_distance = distance
                shortest_path = full_path

        # Örneğin, drop noktalarının sayısı 5 ise; başlangıç noktasını çıkartıp sadece drop noktalarını alıyoruz.
        # Buradaki dilimleme sisteminize göre ayarlanabilir.
        shortest_path = shortest_path[1:6]  
        print("En kısa yol:", shortest_path)
        print("En kısa mesafe (km):", shortest_distance)
        return shortest_path
    

    def turn_lap(self):
        print("Turn Lap")
        with open('config.json') as f:
            data = json.load(f)
        self.vehicle.parameters['WPNAV_SPEED']=data['WP_SPEED']

        cmds = self.vehicle.commands
        cmds.download()
        cmds.wait_ready()
        print("Download Waypoints - Completed")
        self.vehicle.commands.next = 2
        print("WP SET TO 2")
        time.sleep(2)
        self.vehicle.mode = VehicleMode("AUTO")

        wp_num = len([cmd for cmd in cmds])

        while True:
            time.sleep(0.1)
            print(self.vehicle.commands.next)
            if self.vehicle.commands.next == wp_num :
                print("Air Drop Stage")
                break

        # Set the mode to GUIDED
        time.sleep(1)
        self.vehicle.mode = VehicleMode("GUIDED")
        time.sleep(1)



class System:
    def __init__(self, config):
        self.init_logger()
        self.config = config
        os.system("echo Bismillahirrahmanirrahim.")
        self.isSimActivated = self.config['isSimActivated']
        self.MAPPING_PATH = self.config['mapping_dir']
        self.SCAN_PATH = self.config['image_dir']
        self.rh = RedisHelper()
        self.r = self.rh.r
        SIM_IP = self.config["SIM_IP"] # Simulation
        SERIAL = '/dev/ttyACM0' # Autopilot
        if self.isSimActivated:
            self.mavlink_handler = MAVLinkHandler(SIM_IP)

        else:
            os.system("sudo chmod a+rw /dev/ttyACM0")
            self.mavlink_handler = MAVLinkHandler(SERIAL, wait_ready=True)

        self.vehicle = self.mavlink_handler.master
        self.mavlink_handler.set_parameter_value('WPNAV_SPEED', self.config['WP_SPEED'])
        """
        İNCELENMELİ!!!
        vehicle.parameters['WPNAV_RADIUS']=data['WP_RADIUS']
        vehicle.parameters['WPNAV_ACCEL']=data['WP_ACCEL']
        vehicle.parameters['WPNAV_SPEED_UP']=data['WP_SPEED_UP']
        vehicle.parameters['WPNAV_SPEED_DN']=data['WP_SPEED_DN']
        vehicle.parameters['WPNAV_LOIT_SPEED']=data['WP_LOIT_SPEED']
        vehicle.parameters['WPNAV_LOIT_RADIUS']=data['WP_LOIT_RADIUS']
        vehicle.parameters['WPNAV_ACCEL_Z']=data['WP_ACCEL_Z']
        vehicle.parameters['WPNAV_ACCEL_XY']=data['WP_ACCEL_XY']
        """

        self.r = redis.StrictRedis(host='localhost', port=6379, db=0)

        self.set_servo(self.vehicle, self.config["MechanismServo"]["Close"]["Channel"], self.config["MechanismServo"]["Close"]["PWM"]) # Mekanizma tutma asamasinda
        time.sleep(5)
        self.set_servo(self.vehicle, self.config["AttributeServo"]["Release"]["Channel"], self.config["AttributeServo"]["Release"]["PWM"]) # Motorları serbest bırak uçuş öncesi

    def init_logger(self):
        import logging
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

    def set_servo(self, vehicle, channel, pwm_value):
        try:
            pwm_value_int = int(pwm_value)
            msg = vehicle.message_factory.command_long_encode(
                0, 0, 
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,
                channel,
                pwm_value_int,
                0,0,0,0,0)

            vehicle.send_mavlink(msg)
            
        except Exception as e:
            print(e)

    def land(self, lat, lon, alt):
        self.mavlink_handler.simple_go_to(lat, lon, alt, block=True, distance_radius=2)
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
            mavutil.mavlink.MAV_CMD_CONDITION_YAW, #command
            0, #confirmation
            heading,    # param 1, yaw in degrees
            0,          # param 2, yaw speed deg/s
            1,          # param 3, direction -1 ccw, 1 cw
            is_relative, # param 4, relative offset 1, absolute angle 0
            0, 0, 0)    # param 5 ~ 7 not used
        # send command to vehicle
        self.vehicle.send_mavlink(msg)

    def take_photo_opencv(self,folder,index):
        if not os.path.exists(folder):
            os.makedirs(folder)
        t1= time.time()
        print ("Capturing is starting...")
        # exp=850
        # os.system(f'v4l2-ctl -d /dev/video0 --set-ctrl=exposure={exp}')
        output_path = f'./{folder}/image_{index}.jpg'
        self.cap = cv2.VideoCapture(self.gstreamer_pipeline(), cv2.CAP_GSTREAMER)
        time.sleep(1)
        if not self.cap.isOpened():
            print("Error: Unable to open camera")
        t1 = time.time()
        while True:
            time.sleep(0.1)
            ret, frame = self.cap.read()
            if not ret:
                print("Error: Unable to capture image")
            if time.time()-t1>=4:
                cv2.imwrite(output_path, frame)
                cv2.waitKey(1)
                break
        self.cap.release()
        print("Capturing is done...")
        t2=time.time()
        print(f"It took {t2-t1} ms")

    def take_screenshot_frame(self,folder,index):
        if not os.path.exists(folder):
            os.makedirs(folder)
        t1= time.time()
        output_path = f'./{folder}/image_{index}.jpg'
        frame = self.rh.from_redis('frame')
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
            self.mavlink_handler.simple_go_to(float(points[i-1][0]),float(points[i-1][1]),float(mapping_alt), block=True, distance_radius=1.5)
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

        for i in range(1,len(points)+1):
            time.sleep(0.5)
            self.logger.debug(f"Points: {points[i-1][0]} {points[i-1][1]}")
            self.mavlink_handler.simple_go_to(float(points[i-1][0]),float(points[i-1][1]),float(scan_alt), block=True, distance_radius=2)
            self.logger.debug("Reached the target point and going to take photo")
            if self.isSimActivated:
                self.take_screenshot_frame(self.SCAN_PATH, i)
            else:
                self.take_photo_opencv(self.SCAN_PATH, i)

        
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 1)
        self.logger.debug('SET Yaw Behaviour: 1, Face next waypoint')


    def main(self):
        
        ########
        # Waypoint list fix and upload
        cmds = self.vehicle.commands
        cmds.download()
        cmds.wait_ready()

        while len(cmds)<3:
            self.logger.debug("waypoint required ")
            time.sleep(1)

        missionlist=[]

        for cmd in cmds:
            missionlist.append(cmd)

        # # Check if the last waypoint is a DO_JUMP command
        # if missionlist[-1].command == mavutil.mavlink.MAV_CMD_DO_JUMP:
        #     self.logger.debug('------------------------------------------------------------------------')
        #     self.logger.debug("Last waypoint is DO_JUMP. Adding the previous waypoint to the end of the list.")
        #     self.logger.debug('------------------------------------------------------------------------')
        #     cmds.add(missionlist[-2])
        # else:
        #     self.logger.debug('------------------------------------------------------------------------')
        #     self.logger.debug('No DOJUMP')
        #     self.logger.debug('------------------------------------------------------------------------')
        #     cmds.add(missionlist[-1])

        # cmds.upload() # Send commands
        ########        

        os.system("bash system.sh") # Starts the processing system
        wp_num = len([cmd for cmd in cmds])
        self.mavlink_handler.set_parameter_value('WP_YAW_BEHAVIOR', 1)
        self.logger.debug('SET Yaw Behaviour: 1')
        n = wp_num # waypoint number before drop zone
        # Wait until the end of waypoint lap to conduct mapping and scanning.
        while True:
            self.logger.debug('wp next:')
            self.logger.debug(self.vehicle.commands.next)
            self.logger.debug('wp num:')
            self.logger.debug(wp_num)
            if self.vehicle.commands.next == wp_num :
                self.logger.debug("Completed waypoint laps.")
                break
            time.sleep(1)

        # Set the mode to GUIDED
        time.sleep(1)
        self.vehicle.mode = VehicleMode("GUIDED")
        # Wait until the mode has been set
        while not self.vehicle.mode.name == "GUIDED":
            self.logger.debug("Waiting for mode change to: GUIDED")
            time.sleep(1)
        self.logger.debug("Mode: GUIDED")


        self.mapping_points = [(self.config["MappingPoints"][f"{i}"]["Latitude"], self.config["MappingPoints"][f"{i}"]["Longitude"]) for i in range(1,len(self.config["MappingPoints"])+1)]
        self.mapping_yaw = self.config["mapping_yaw"]
        self.mapping_alt = self.config["mapping_alt"]
        
        # Start mapping photo capture
        self.start_mapping(points=self.mapping_points, mapping_yaw=self.mapping_yaw, mapping_alt=self.mapping_alt, sim=self.isSimActivated)
        self.r.set('start_mapping', 'True') # start mapping process


        self.r.set('start_ip', 'True') # start image processing 
        self.points = [(self.config["Points"][f"{i}"]["Latitude"], self.config["Points"][f"{i}"]["Longitude"]) for i in range(1,len(self.config["Points"])+1)]
        self.drop_yaw = self.config["DROP_YAW"]
        self.scan_alt = self.config["image_alt"]
        self.start_scanning(points=self.points, drop_yaw=self.drop_yaw, scan_alt=self.scan_alt, sim=self.isSimActivated)


        # Wait until 'image processing' is done
        while True:
            image_proc_done = self.r.get('image_proc_done')
            if image_proc_done and image_proc_done.decode('utf-8') == 'done':
                break
            time.sleep(1)

        dh = BottleDropHandler(vehicle=self.vehicle,handler=self.mavlink_handler, config=self.config)

        # ROI koordinatlarının bulunduğu CSV dosyasını okuyalım:
        try:
            df_roi = pd.read_csv("roi_results.csv")
            # df_roi, "roi_lat" ve "roi_lon" sütunlarını içeriyor
            best_rois_coords = list(df_roi[['roi_lat', 'roi_lon']].itertuples(index=False, name=None)) # example data: best_rois_coords = [(41.101, 29.002), (41.102, 29.003), (41.103, 29.004), (41.104, 29.005)]

        except Exception as e:
            print("Error reading roi_results.csv: ", e)
            best_rois_coords = []
        dh.drop_bottle(best_rois_coords)


        land_latitude = self.config["LandCoordinates"]["Latitude"]
        land_longitude = self.config["LandCoordinates"]["Longitude"]
        self.land(land_latitude, land_longitude, 26)



if __name__ == '__main__':
    with open('config.json') as f:
        config = json.load(f)

    system = System(config=config)
    system.main()