import piexif
from PIL import Image
import pandas as pd
import os

def decimal_to_dms_rational(decimal):
    deg = int(decimal)
    min_float = abs((decimal - deg) * 60)
    minute = int(min_float)
    sec = round((min_float - minute) * 60 * 100)
    return ((abs(deg), 1), (minute, 1), (sec, 100))

df = pd.read_csv("fotolar.csv")
print("Fotolar CSV dosyası yüklendi.")
os.makedirs("meta_fotolar/mapframes", exist_ok=True)

for idx, row in df.iterrows():
    filename = row['filename']
    lat = float(row['GPSLatitude'])
    lon = float(row['GPSLongitude'])

    gps_ifd = {
        piexif.GPSIFD.GPSLatitude: decimal_to_dms_rational(lat),
        piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
        piexif.GPSIFD.GPSLongitude: decimal_to_dms_rational(lon),
        piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W'
    }
    zeroth_ifd = {
        piexif.ImageIFD.Make: u"NVIDIA",
        piexif.ImageIFD.Model: u"Jetson Orin NX IMX477"
    }
    exif_ifd = {
        piexif.ExifIFD.FocalLength: (8, 1),
        piexif.ExifIFD.FNumber: (14, 10),
        42036: u"CS2308ZM05 8mm F1.4"  # LensModel burada olacak!
    }

    exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd, "GPS": gps_ifd}

    try:
        img = Image.open(filename)
        exif_bytes = piexif.dump(exif_dict)
        out_path = os.path.join("meta_fotolar", filename)
        img.save(out_path, exif=exif_bytes)
        print(f"{filename} --> meta_fotolar/{filename}  (EXIF yazıldı)")
    except Exception as e:
        print(f"{filename} hata: {e}")
