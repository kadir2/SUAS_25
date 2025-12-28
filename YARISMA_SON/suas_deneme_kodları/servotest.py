from mavlinkHandler import MAVLinkHandlerDronekit as MAVLinkHandler
from dronekit import connect, VehicleMode
import time
from pymavlink import mavutil

vehicle = MAVLinkHandler("/dev/ttyACM0").master

def set_servo(channel, pwm_value):
    if (channel  or pwm_value ):
        pwm_value_int = int(pwm_value)
        print(f"pwm_value_int: {pwm_value_int}")
        msg = vehicle.message_factory.command_long_encode(
            0, 0, 
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,
            channel,
            pwm_value_int,
            0,0,0,0,0)

        vehicle.send_mavlink(msg)

def real_drop(channel, pwm):

    # Servoyu aktive et
    set_servo(channel, pwm)
    print(f"Servo activated: channel={channel, pwm}")
    # Bırakma süresi
    time.sleep(3)
    # # Servoyu resetle (PWM=0)
    set_servo(channel, 0)
    print(f"Servo deactivated: channel={channel}")


real_drop(12, 1975)


# 1100
# 1400
# 1600
# 1800
