# # import cv2
# # import threading
# # import time

# # frames_for_stitch = []
# # frames_lock = threading.Lock()
# # is_recording = True

# # def gstreamer_pipeline(
# #     sensor_id=0,
# #     capture_width=1920,
# #     capture_height=1080,
# #     framerate=50,
# #     flip_method=0,
# #     sensor_mode=2  # 1920x1080 için mode 2 (genellikle, ama sensörüne bak!)
# # ):
# #     return (
# #         f"nvarguscamerasrc sensor-id={sensor_id} sensor-mode={sensor_mode} ! "
# #         f"video/x-raw(memory:NVMM), width={capture_width}, height={capture_height}, framerate={framerate}/1 ! "
# #         f"nvvidconv flip-method={flip_method} ! "
# #         f"video/x-raw, format=(string)BGRx ! "
# #         f"videoconvert ! "
# #         f"video/x-raw, format=(string)BGR ! appsink"
# #     )

# # def video_capture_and_save(frames_for_stitch, frames_lock):
# #     pipeline = gstreamer_pipeline()
# #     cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
# #     if not cap.isOpened():
# #         print("Kamera açılamadı.")
# #         return

# #     width, height = 1920, 1080
# #     fourcc = cv2.VideoWriter_fourcc(*'MJPG')
# #     out = cv2.VideoWriter('kayit.avi', fourcc, 30.0, (width, height))

# #     global is_recording
# #     try:
# #         while is_recording:
# #             ret, frame = cap.read()
# #             if not ret:
# #                 print("Frame alınamadı.")
# #                 break

# #             out.write(frame)

# #             # Panoramik için frame ekle
# #             if int(time.time() * 2) % 2 == 0:
# #                 with frames_lock:
# #                     if len(frames_for_stitch) < 20:
# #                         frames_for_stitch.append(frame.copy())

# #             cv2.imshow("Canlı", frame)
# #             if cv2.waitKey(1) & 0xFF == ord('q'):
# #                 is_recording = False
# #                 break
# #     finally:
# #         cap.release()
# #         out.release()
# #         cv2.destroyAllWindows()

# # def panoramic_stitch(frames_for_stitch, frames_lock):
# #     stitcher = cv2.Stitcher_create()
# #     panorama_done = False

# #     while is_recording or not panorama_done:
# #         time.sleep(2)
# #         with frames_lock:
# #             if len(frames_for_stitch) >= 2 and not panorama_done:
# #                 images = frames_for_stitch[:]
# #                 status, pano = stitcher.stitch(images)
# #                 if status == cv2.Stitcher_OK:
# #                     cv2.imwrite("panorama3.jpg", pano)
# #                     print("Panoramik görüntü kaydedildi.")
# #                     panorama_done = True
# #                 else:
# #                     print("Stitch başarısız.")
# #         if panorama_done:
# #             break

# # def main():
# #     capture_thread = threading.Thread(target=video_capture_and_save, args=(frames_for_stitch, frames_lock))
# #     stitch_thread = threading.Thread(target=panoramic_stitch, args=(frames_for_stitch, frames_lock))

# #     capture_thread.start()
# #     stitch_thread.start()

# #     capture_thread.join()
# #     stitch_thread.join()

# #     print("Kayıt ve stitching işlemi tamamlandı.")

# # if __name__ == "__main__":
# #     main()



# import cv2
# import os
# import time

# def video_capture_and_save_from_mp4(video_file='video_20250620_235051.mp4', output_dir='frames_output', total_frames=60):
#     # Video dosyasını açıyoruz
#     cap = cv2.VideoCapture(video_file)
#     if not cap.isOpened():
#         print(f"Video dosyası açılamadı: {video_file}")
#         return

#     # Çıkış klasörünü oluşturuyoruz
#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)

#     frame_rate = cap.get(cv2.CAP_PROP_FPS)
#     print(f"Video frame rate: {frame_rate}")

#     # Toplam kaç kare alacağımızı ayarlıyoruz
#     frames_to_capture = total_frames
#     frame_count = 0

#     # Kareleri yakalayıp dosyaya kaydediyoruz
#     captured_frames = 0
#     while captured_frames < frames_to_capture:
#         ret, frame = cap.read()
#         if not ret:
#             print("Frame alınamadı.")
#             break

#         # Her N. kareyi kaydediyoruz
#         captured_frames += 1
#         time.sleep(0.1)
#          # Her 0.1 saniyede bir kare alıyoruz
#         if captured_frames % (int(frame_rate * 0.07)) == 0 and captured_frames>40:  # 0.1 saniyede bir kare
#             frame_filename = os.path.join(output_dir, f"frame_{captured_frames:03d}.jpg")
#             cv2.imwrite(frame_filename, frame)  # Kareyi kaydediyoruz
#             print(f"Kare {captured_frames} kaydedildi: {frame_filename}")

#     cap.release()

# def main():
#     video_file = 'AMERİKA_FOTOLAR/video_20250620_235051.mp4'  # MP4 dosyanızın yolu
#     output_dir = 'yeni_frames_output'  # Karelerin kaydedileceği klasör
#     total_frames = 200  # Alınacak kare sayısı

#     video_capture_and_save_from_mp4(video_file, output_dir, total_frames)
#     print(f"{total_frames} kare kaydedildi ve '{output_dir}' klasörüne eklendi.")

# if __name__ == "__main__":
#     main()


# import cv2
# import os
# import threading
# import time

# frames_for_stitch = []
# frames_lock = threading.Lock()
# is_reading_done = False

# def show_selected_frame(frame, index):
#     cv2.imshow(f"Seçilen Frame {index}", frame)
#     cv2.waitKey(500)  # 500 ms göster
#     cv2.destroyWindow(f"Seçilen Frame {index}")

# def extract_frames_from_video(video_path, frames_for_stitch, frames_lock, max_frames=60, interval=5, skip_first=10):
#     cap = cv2.VideoCapture(video_path)
#     if not cap.isOpened():
#         print("❌ Video açılamadı.")
#         return

#     total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#     print(f"📹 Toplam {total_frames} frame var.")

#     count = 0
#     saved = 0
#     while cap.isOpened() and saved < max_frames:
#         ret, frame = cap.read()
#         if not ret:
#             break

#         if count >= skip_first and (count % interval == 0):
#             with frames_lock:
#                 frames_for_stitch.append(frame.copy())
#             print(f"✔️ Frame {count} alındı ({saved+1}/{max_frames})")
#             show_selected_frame(frame, saved+1)  # Seçilen kareyi göster
#             saved += 1

#         count += 1

#     cap.release()
#     global is_reading_done
#     is_reading_done = True

# def panoramic_stitch(frames_for_stitch, frames_lock):
#     stitcher = cv2.Stitcher_create()
#     best_pano = None
#     best_count = 0

#     while not is_reading_done:
#         time.sleep(2)

#     with frames_lock:
#         images = frames_for_stitch[:]

#     # Önce klasik stitching denemesi (çoklu kare)
#     for i in range(len(images), 1, -1):
#         status, pano = stitcher.stitch(images[:i])
#         if status == cv2.Stitcher_OK:
#             print(f"✅ {i} kareyle stitching başarılı.")
#             cv2.imwrite(f"panorama_{i}_frames.jpg", pano)
#             if i > best_count:
#                 best_pano = pano
#                 best_count = i
#         else:
#             print(f"❌ {i} kareyle stitching başarısız.")

#     # İkili stitching denemeleri
#     for i in range(len(images) - 1):
#         for j in range(i + 1, len(images)):
#             status, pano = stitcher.stitch([images[i], images[j]])
#             if status == cv2.Stitcher_OK:
#                 print(f"✅ {i+1}. ve {j+1}. kareyle stitching başarılı.")
#                 cv2.imwrite(f"panorama_{i+1}_{j+1}_frames.jpg", pano)
#             else:
#                 print(f"❌ {i+1}. ve {j+1}. kareyle stitching başarısız.")

#     if best_pano is not None:
#         print(f"🎉 En iyi panorama {best_count} kareyle kaydedildi (panorama_{best_count}_frames.jpg).")
#     else:
#         print("Hiçbir stitching işlemi başarılı olmadı.")

# def main():
#     video_path = "AMERİKA_FOTOLAR/video_20250620_235051.mp4"
#     frame_interval =4 # Her 5. kareyi al
#     max_frames = 34
#     skip_first = 50  # İlk 10 kareyi atla

#     extract_thread = threading.Thread(
#         target=extract_frames_from_video,
#         args=(video_path, frames_for_stitch, frames_lock, max_frames, frame_interval, skip_first)
#     )
#     stitch_thread = threading.Thread(target=panoramic_stitch, args=(frames_for_stitch, frames_lock))

#     extract_thread.start()
#     stitch_thread.start()

#     extract_thread.join()
#     stitch_thread.join()

#     print("🎬 İşlem tamamlandı. panorama_from_video.jpg kaydedildi.")

# if __name__ == "__main__":
#     main()


import cv2
import numpy as np
import os

# === PARAMETRELER ===
video_path = 'AMERİKA_FOTOLAR/video_20250620_235051.mp4'
output_folder = 'frames'
output_image = 'panoramaa.jpg'
num_frames = 10  # Kaç kare alınsın
resize_width = 1080  # Her karenin yeniden boyutu (panoramanın genişliği = num_frames * resize_width)

# === KLASÖR OLUŞTUR ===
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# === VİDEODAN FRAME AL ===
cap = cv2.VideoCapture(video_path)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
interval = total_frames // num_frames

frames = []
print("Kareler çekiliyor...")
for i in range(num_frames):
    cap.set(cv2.CAP_PROP_POS_FRAMES, i * interval)
    ret, frame = cap.read()
    if not ret:
        continue
    frame = cv2.resize(frame, (resize_width, int(frame.shape[0] * resize_width / frame.shape[1])))
    frames.append(frame)

cap.release()
print(f"{len(frames)} kare alındı.")

# === KARELERİ YANA YAPIŞTIR ===
print("Kareler birleştiriliyor...")
panorama = np.hstack(frames)
cv2.imwrite(output_image, panorama)
print(f"Panorama kaydedildi: {output_image}")
