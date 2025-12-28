import matplotlib.pyplot as plt
import numpy as np

# Dikdörtgenlerin köşe koordinatları
large_rectangle = [
    (38.314816, -76.548947),  # Sol alt
    (38.315460, -76.552653),  # Sağ alt
    (38.316639, -76.55233),   # Sağ üst
    (38.316016, -76.54860)    # Sol üst
]

small_rectangle = [
    (38.315386, -76.550875),  # Sol alt
    (38.315683, -76.552586),  # Sağ alt
    (38.315895, -76.552519),  # Sağ üst
    (38.315607, -76.550800)   # Sol üst
]

# Uçuş parametreleri
flight_altitude = 50  # Uçuş yüksekliği (metre)
camera_coverage_width = 60  # Kamera görüş genişliği (metre)
camera_overlap = 0.7  # Görüntü örtüşme oranı

# Görüntüleme aralıklarının hesaplanması
step_size = camera_coverage_width * (1 - camera_overlap)

# Büyük dikdörtgeni taramak için rotayı oluşturma
large_latitudes = np.arange(large_rectangle[0][0], large_rectangle[2][0], step_size / 111320)  # 1 derece ~111.32 km
large_routes = []
for i, lat in enumerate(large_latitudes):
    if i % 2 == 0:
        large_routes.append([(lat, large_rectangle[0][1]), (lat, large_rectangle[1][1])])
    else:
        large_routes.append([(lat, large_rectangle[1][1]), (lat, large_rectangle[0][1])])

# Küçük dikdörtgen için rotayı oluşturma
small_latitudes = np.arange(small_rectangle[0][0], small_rectangle[2][0], step_size / 111320)
small_routes = []
for i, lat in enumerate(small_latitudes):
    if i % 2 == 0:
        small_routes.append([(lat, small_rectangle[0][1]), (lat, small_rectangle[1][1])])
    else:
        small_routes.append([(lat, small_rectangle[1][1]), (lat, small_rectangle[0][1])])

# Görselleştirme
plt.figure(figsize=(12, 8))

# Büyük dikdörtgeni çizme
large_x, large_y = zip(*large_rectangle + [large_rectangle[0]])
plt.plot(large_y, large_x, 'b-', label='Büyük Dikdörtgen')

# Küçük dikdörtgeni çizme
small_x, small_y = zip(*small_rectangle + [small_rectangle[0]])
plt.plot(small_y, small_x, 'g-', label='Küçük Dikdörtgen')

# Büyük dikdörtgen rotasını çizme
for route in large_routes:
    lats, lons = zip(*route)
    plt.plot(lons, lats, 'r--')

# Küçük dikdörtgen rotasını çizme
for route in small_routes:
    lats, lons = zip(*route)
    plt.plot(lons, lats, 'orange')

# Detaylar
plt.title('Drone Uçuş Rotası')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.legend()
plt.grid(True)
plt.axis('equal')
plt.show()
