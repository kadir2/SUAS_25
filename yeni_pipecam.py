import cv2
import time

def gstreamer_pipeline(
    sensor_id=0,
    sensor_mode=0,
    capture_width=1920,
    capture_height=1080,
    framerate=60,
    flip_method=0
):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} sensor-mode={sensor_mode} ! "
        f"video/x-raw(memory:NVMM), width={capture_width}, height={capture_height}, framerate={framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, format=BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=BGR ! appsink"
    )

def main():
    pipeline = gstreamer_pipeline()
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("Kamera açılamadı.")
        return

    print("Kamera açıldı. 'q' tuşuna basınca fotoğraf çekilecek ve kaydedilecek.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Kare alınamadı.")
            break

        cv2.imshow("Kamera", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            filename = f"photo_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            print(f"{filename} kaydedildi.")
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
