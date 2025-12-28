import cv2


# def gstreamer_pipeline(
#     sensor_id=0,
#     sensor_mode=0,          # Kip 0 = 4032 × 3040
#     capture_width=4032,
#     capture_height=3040,
#     framerate=21,           # Kip 0 için güvenli değer
#     flip_method=2,
#     wbmode=0,
#     aelock=True,
#     awblock=True,
# ):
#     return (
#         f"nvarguscamerasrc sensor-id={sensor_id} sensor-mode={sensor_mode} "
#         f"wbmode={wbmode} aelock={'true' if aelock else 'false'} "
#         f"awblock={'true' if awblock else 'false'} exposurecompensation=0 "
#         f"ee-mode=1 ee-strength=1 tnr-mode=1 tnr-strength=1 ! "
#         f"video/x-raw(memory:NVMM),width={capture_width},height={capture_height},"
#         f"framerate={framerate}/1 ! "
#         f"nvvidconv flip-method={flip_method} ! "
#         f"video/x-raw,format=BGRx ! videoconvert ! "
#         f"video/x-raw,format=BGR ! appsink drop=true sync=false"
#     )

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 ,
    capture_height=1080,
    framerate=60,
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


def main():
    # Build pipeline for live preview
    pipeline = gstreamer_pipeline()
    print(cv2.getBuildInformation())
    print(f"Opening camera with pipeline:\n{pipeline}")
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("Error: Unable to open camera for live preview.")
        return


    import time
    try: 
        while True:

            ret, frame = cap.read()
            if not ret:
                print("Warning: Frame not received.")
                break
            cv2.imshow("cap", cv2.resize(frame, (1920, 1080)))
            # cv2.imshow("cap", frame)

            
            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                cv2.imwrite("frame10.jpg", frame)
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
