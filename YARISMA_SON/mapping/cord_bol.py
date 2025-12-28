import csv
import os

start_lat, start_lon = 38.8502466, -76.7000837
end_lat, end_lon = 38.8513676, -76.6994487
num_points = 16
print("Current working directory:", os.getcwd())
def speed_profile(t):
    # t: [0,1] aralığında. İlk 1/3'te parabolik hızlanma, sonra sabit.
    if t < 1/3:
        # s = 1.5 * t**2 (alanı 1/3'e normalize etmek için katsayı 1.5)
        return 1.5 * t * t
    else:
        # Sabit hız kısmı (alan devamı için offset)
        return 1.5 * (1/3)**2 + (t - 1/3) * (1 - 1.5 * (1/3)**2) / (2/3)

cumulative = [speed_profile(i/(num_points-1)) for i in range(num_points)]
# Normalize (son değer tam 1 olsun, toplam yolun tamamı alınsın)
minv, maxv = min(cumulative), max(cumulative)
cumulative = [(x-minv)/(maxv-minv) for x in cumulative]

with open("fotolar.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["filename", "GPSLatitude", "GPSLongitude"])
    for i, t in enumerate(cumulative):
        lat = start_lat + t * (end_lat - start_lat)
        lon = start_lon + t * (end_lon - start_lon)
        writer.writerow([f"mapframes/frame_{i+1:04d}.jpg", f"{lat:.7f}", f"{lon:.7f}"])
