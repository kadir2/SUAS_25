import time
import math
from dronekit import connect, VehicleMode
from pymavlink import mavutil

# Yardımcı: Bir değeri belirtilen min ve max sınırları arasında tutar.
def clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))

class MappingMission:
    def __init__(self, connection_string, mapping_rect, target_altitude=15):
        self.connection_string = connection_string
        self.mapping_rect = mapping_rect  # [(x, y), ...] şeklinde, yerel koordinatlarda dikdörtgenin köşeleri
        self.target_altitude = target_altitude

        # Kontrol kazançları (NED komutları için)
        self.kp_north = 0.05
        self.kp_east = 0.05
        self.kp_vertical = 0.05

        # Ofset ve adım parametreleri
        self.offset_x_start = 15   # Başlangıç için x ofseti
        self.offset_x_end = 7      # Bitiş için x ofseti
        self.offset_y = 7          # Y ekseninde kenardan içeri ofset
        self.line_increment = 10   # Her 10 m’de bir nokta
        self.row_shift = 15        # Satır geçişinde y ekseninde kaydırma

        # Drone bağlantısı
        print(f"[Drone] {self.connection_string} üzerinden bağlanılıyor...")
        self.vehicle = connect(connection_string, wait_ready=True)

    def initialize_vehicle(self):
        print("[Drone] GUIDED moda geçiliyor...")
        self.vehicle.mode = VehicleMode("GUIDED")
        time.sleep(1)
        print("[Drone] Arm ediliyor...")
        self.vehicle.armed = True
        while not self.vehicle.armed:
            print("[Drone] Arm bekleniyor...")
            time.sleep(1)
        print(f"[Drone] {self.target_altitude} m irtifaya kalkış yapılıyor...")
        self.vehicle.simple_takeoff(self.target_altitude)
        while True:
            alt = self.vehicle.location.global_relative_frame.alt
            print(f"[Drone] İrtifa: {alt:.2f} m")
            if alt >= self.target_altitude * 0.95:
                print("[Drone] Hedef irtifaya ulaşıldı.")
                break
            time.sleep(1)

    def send_velocity_command(self, vx, vy, vz):
        """
        NED (North, East, Down) komutlarına göre hız gönderimi.
        vx: North yönü hızı (m/s)
        vy: East yönü hızı (m/s)
        vz: Down yönü hızı (m/s) – yukarı çıkmak için negatif değer kullanılmalı.
        """
        msg = self.vehicle.message_factory.set_position_target_local_ned_encode(
            0, 
            self.vehicle._master.target_system,
            self.vehicle._master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111000111,  # Sadece hız bileşenleri aktif
            0, 0, 0,             # Pozisyon bilgisi kullanılmıyor
            vx, vy, vz,          # Hız bileşenleri
            0, 0, 0,             # İvme bilgisi kullanılmıyor
            0, 0
        )
        self.vehicle.send_mavlink(msg)
        self.vehicle.flush()

    def get_current_position(self):
        """
        Drone’un mevcut yerel konumunu (north, east, altitude) döndürür.
        """
        try:
            current_north = self.vehicle.location.local_frame.north
            current_east = self.vehicle.location.local_frame.east
            current_alt = self.vehicle.location.global_relative_frame.alt  # İrtifa bilgisi
            return (current_north, current_east, current_alt)
        except Exception as e:
            print("[Drone] Yerel konum bilgisi alınamadı, örnek değer kullanılıyor.")
            return (0, 0, self.target_altitude)

    def calculate_mapping_path(self):
        """
        Mapping yapılacak dikdörtgenin köşeleri ve drone'un başlangıç konumuna göre,
        'lawnmower' deseniyle hedef noktaları (yerel koordinatlarda) hesaplar.
        """
        xs = [p[0] for p in self.mapping_rect]
        ys = [p[1] for p in self.mapping_rect]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        # Drone'un mevcut konumu
        current_pos = self.get_current_position()  # (north, east, alt)
        drone_x, drone_y, _ = current_pos
        
        # Dikdörtgen içinde drone'un en yakın noktası:
        closest_x = clamp(drone_x, min_x, max_x)
        closest_y = clamp(drone_y, min_y, max_y)
        
        # Drone hangi kenara daha yakın? (alt kenar mı yoksa üst kenar mı)
        if abs(drone_y - min_y) < abs(drone_y - max_y):
            flight_y = min_y + self.offset_y
            if abs(drone_x - min_x) < abs(drone_x - max_x):
                x_start = min_x + self.offset_x_start
                x_end = max_x - self.offset_x_end
                x_direction = 1
            else:
                x_start = max_x - self.offset_x_start
                x_end = min_x + self.offset_x_end
                x_direction = -1
        else:
            flight_y = max_y - self.offset_y
            if abs(drone_x - min_x) < abs(drone_x - max_x):
                x_start = min_x + self.offset_x_start
                x_end = max_x - self.offset_x_end
                x_direction = 1
            else:
                x_start = max_x - self.offset_x_start
                x_end = min_x + self.offset_x_end
                x_direction = -1
        
        start_point = (x_start, flight_y, self.target_altitude)
        waypoints = []
        current_point = start_point
        current_direction = x_direction
        
        if flight_y == min_y + self.offset_y:
            y_increment = self.row_shift   # yukarıya doğru
            y_limit = max_y - self.offset_y
        else:
            y_increment = -self.row_shift  # aşağıya doğru
            y_limit = min_y + self.offset_y

        # Her bir hat boyunca; x ekseninde lineer artışla noktalar oluşturuluyor.
        while True:
            line_points = []
            x_current = current_point[0]
            if current_direction > 0:
                while x_current <= x_end:
                    line_points.append((x_current, current_point[1], self.target_altitude))
                    x_current += self.line_increment
                if line_points[-1][0] < x_end:
                    line_points.append((x_end, current_point[1], self.target_altitude))
            else:
                while x_current >= x_end:
                    line_points.append((x_current, current_point[1], self.target_altitude))
                    x_current -= self.line_increment
                if line_points[-1][0] > x_end:
                    line_points.append((x_end, current_point[1], self.target_altitude))
            
            waypoints.extend(line_points)
            
            # Hat sonuna ulaşıldıktan sonra y ekseninde kaydırma yap
            new_y = current_point[1] + y_increment
            if (y_increment > 0 and new_y > y_limit) or (y_increment < 0 and new_y < y_limit):
                break
            new_point = (line_points[-1][0], new_y, self.target_altitude)
            waypoints.append(new_point)
            current_point = new_point
            current_direction *= -1
            x_start, x_end = x_end, x_start
        
        print("[Mapping] Hesaplanan hedef noktalar:")
        for idx, pt in enumerate(waypoints):
            print(f"  {idx+1}: {pt}")
        return waypoints

    def move_to_target(self, target, threshold=2.0):
        """
        Hedef konuma, drone'un mevcut konumu baz alınarak NED komutlarıyla hareket ettirir.
        Hata mesafesi 'threshold' altında olduğunda hareket durur.
        """
        print(f"[Mapping] Hedef nokta: {target}")
        while True:
            current_pos = self.get_current_position()
            error_north = target[0] - current_pos[0]
            error_east = target[1] - current_pos[1]
            error_alt = target[2] - current_pos[2]
            
            distance = math.sqrt(error_north**2 + error_east**2 + error_alt**2)
            print(f"[Mapping] Hata mesafesi: {distance:.2f} m")
            
            if distance < threshold:
                print("[Mapping] Hedefe ulaşıldı.")
                self.send_velocity_command(0, 0, 0)
                break
            
            vx = self.kp_north * error_north
            vy = self.kp_east * error_east
            vz = -self.kp_vertical * error_alt  # Hedef irtifaya ulaşmak için negatif komut (NED: down pozitif)
            self.send_velocity_command(vx, vy, vz)
            time.sleep(0.5)

    def run_mission(self):
        self.initialize_vehicle()
        waypoints = self.calculate_mapping_path()
        for pt in waypoints:
            self.move_to_target(pt)
            print("[Mapping] 5 saniye bekleniyor (fotoğraf çekim simülasyonu)...")
            time.sleep(5)
        print("[Mapping] Görev tamamlandı.")

if __name__ == '__main__':
    # Mapping yapılacak dikdörtgenin köşeleri (örnek değerler, yerel koordinat, metre cinsinden)
    mapping_rect = [(0, 0), (100, 0), (100, 50), (0, 50)]
    mission = MappingMission('udp:127.0.0.1:14551', mapping_rect, target_altitude=15)
    mission.run_mission()
