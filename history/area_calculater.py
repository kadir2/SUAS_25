import math
import numpy as np
from geopy.distance import geodesic

def latlon_to_xy(ref_point, target_point):
    """Referans noktasına göre diğer noktanın (metre cinsinden) x, y ofsetini döndürür."""
    lat0, lon0 = ref_point
    lat1, lon1 = target_point
    # Yani y kuzey-güney (lat), x doğu-batı (lon)
    y = geodesic((lat0, lon0), (lat1, lon0)).meters
    if lat1 < lat0:
        y = -y
    x = geodesic((lat0, lon0), (lat0, lon1)).meters
    if lon1 < lon0:
        x = -x
    return (x, y)

def xy_to_latlon(ref_point, xy):
    """Ref noktadan metre bazında x,y ofsetini lat,lon'a çevirir."""
    lat0, lon0 = ref_point
    x, y = xy
    # Y (kuzey-güney) -> lat
    lat = geodesic(meters=abs(y)).destination((lat0, lon0), 0 if y >= 0 else 180).latitude
    # X (doğu-batı) -> lon
    lon = geodesic(meters=abs(x)).destination((lat0, lon0), 90 if x >= 0 else 270).longitude
    return (lat, lon)

def calculate_capture_grid_corners(
    camera_resolution=(4032, 3040),
    sensor_size=(6.287, 4.712),  # mm
    focal_length=12,         # mm
    altitude=20,             # metre
    fov_deg=30,              # yatay FOV
    overlap=0.6,
    corners=None             # [(lat, lon), (lat, lon), (lat, lon), (lat, lon)]
):
    if corners is None or len(corners) != 4:
        raise ValueError("Lütfen 4 köşe noktası verin: corners=[(lat1,lon1),...,(lat4,lon4)]")

    # Alanın merkezini bul
    lat_mean = sum([lat for lat, lon in corners]) / 4
    lon_mean = sum([lon for lat, lon in corners]) / 4
    center = (lat_mean, lon_mean)

    # Alanı X, Y düzlemine çevir (metre cinsinden)
    xy_corners = [latlon_to_xy(center, pt) for pt in corners]
    x_coords = [x for x, y in xy_corners]
    y_coords = [y for x, y in xy_corners]
    min_x, max_x = min(x_coords), max(x_coords)
    min_y, max_y = min(y_coords), max(y_coords)
    area_width = max_x - min_x
    area_height = max_y - min_y

    # Kamera parametreleri
    width_px, height_px = camera_resolution
    fov_h = math.radians(fov_deg)
    ground_width = 2 * altitude * math.tan(fov_h / 2)
    aspect_ratio = height_px / width_px
    ground_height = ground_width * aspect_ratio
    step_x = ground_width * (1 - overlap)
    step_y = ground_height * (1 - overlap)

    n_x = math.ceil((area_width - ground_width) / step_x) + 1
    n_y = math.ceil((area_height - ground_height) / step_y) + 1

    # Grid merkezlerini üret
    x_centers = [
        min_x + ground_width / 2 + i * step_x
        for i in range(n_x)
    ]
    y_centers = [
        min_y + ground_height / 2 + j * step_y
        for j in range(n_y)
    ]
    grid_xy_centers = [(x, y) for y in y_centers for x in x_centers]
    grid_latlon_centers = [xy_to_latlon(center, (x, y)) for (x, y) in grid_xy_centers]

    print(f"Bir fotoğraf yerde: {ground_width:.2f}m x {ground_height:.2f}m kaplar.")
    print(f"Alanda {n_x} x {n_y} = {n_x*n_y} fotoğraf gerekir.")
    print("Her fotoğrafın merkezi: (lat, lon)")
    for idx, (lat, lon) in enumerate(grid_latlon_centers):
        print(f"{idx+1}: {lat:.6f}, {lon:.6f}")

    return {
        "ground_width": ground_width,
        "ground_height": ground_height,
        "n_x": n_x,
        "n_y": n_y,
        "total_images": n_x * n_y,
        "grid_latlon_centers": grid_latlon_centers,
    }


# ÖRNEK KULLANIM
if __name__ == "__main__":
    # Sırasız 4 köşe noktası (lat, lon), örnekler:
    corners = [
        (41.1014155, 29.0231501),
        (41.1016980, 29.0230870),   
        (41.1017505, 29.0234771),
        (41.1014721, 29.0235421)
    ]
    calculate_capture_grid_corners(
        camera_resolution=(4056, 3040),
        sensor_size=(6.3, 4.7),
        focal_length=12,
        altitude=20,
        fov_deg=30,
        overlap=0.3,
        corners=corners
    )
