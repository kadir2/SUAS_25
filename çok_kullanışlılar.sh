#!/bin/bash


#v4l2-ctl --list-devices

#gst-launch-1.0 nvarguscamerasrc sensor-id=0 sensor-mode=3 !   'video/x-raw(memory:NVMM),width=1920,height=1080,format=NV12,framerate=20/1' !   nvvidconv flip-method=2 ! 'video/x-raw,format=BGRx' !   videoconvert ! 'video/x-raw,format=BGR' !   xvimagesink

PASSWORD="1"

# ttyACM0'a erişim izni veriliyor
echo "$PASSWORD" | sudo -S chmod a+rw /dev/ttyACM0

# Jetson fan komutu çalıştırılıyor
echo "$PASSWORD" | sudo -S jetson_clocks --fan

exit

