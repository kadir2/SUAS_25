import cv2
import os
import numpy as np

def stitch_images_right_to_left(folder_path, output_path="stitched_output.jpg"):
    # Dosya isimlerini al ve sıralı şekilde tersten sırala (sağdan sola birleştirme için)
    image_files = sorted(
        [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))],
        reverse=True  # SAĞDAN sola
    )

    if not image_files:
        print("Görüntü bulunamadı.")
        return

    images = []
    for file in image_files:
        img_path = os.path.join(folder_path, file)
        img = cv2.imread(img_path)
        if img is not None:
            images.append(img)
        else:
            print(f"Okunamayan dosya atlandı: {file}")

    if len(images) < 2:
        print("Yeterli görüntü yok.")
        return

    try:
        # OpenCV'nin stitcher'ı yerine yatay birleştirme
        stitched = np.hstack(images)
        cv2.imwrite(output_path, stitched)
        print(f"Birleştirilmiş çıktı kaydedildi: {output_path}")
    except Exception as e:
        print(f"Hata oluştu: {e}")

# KULLANIM
folder_path = "panarrr"  # klasör adını buraya yaz
stitch_images_right_to_left(folder_path)
