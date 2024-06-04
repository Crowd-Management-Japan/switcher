import RPi.GPIO as GPIO
import time
import sys
from datetime import datetime
import os

# Define constants
TIME_INFO_FILE = '/var/tmp/last_time.txt'
RELAY_PINS = [23, 24, 25, 26]
TEST_REPETITIONS = 2
TEST_DURATION = [5, 3]

# Open pins and setup operating mode
def setup_pins():
    # Set GPIO mode to BCM
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Setup the GPIO pin as an output
    for pin in RELAY_PINS:
        GPIO.setup(pin, GPIO.OUT)

# Change status for each pin (off/on)
def change_status(pin_status):
    for i in range(4):
        if pin_status[i] == -1:
            GPIO.output(RELAY_PINS[i], GPIO.LOW)
        elif pin_status[i] == 1:
            GPIO.output(RELAY_PINS[i], GPIO.HIGH)

# Perform switching test for 2-switches device
def test2(repetitions,duration):
    change_status([1, 1, 0, 0])
    time.sleep(duration[0])
    for i in range(repetitions):
        change_status([-1, -1, 0, 0])
        time.sleep(duration[1])
        change_status([1, -1, 0, 0])
        time.sleep(duration[1])
        change_status([1, 1, 0, 0])
        time.sleep(duration[1])      

# Perform switching test for 4-switches device
def test4(repetitions,duration):
    change_status([1, 1, 1, 1])
    time.sleep(duration[0])
    for i in range(repetitions):
        change_status([-1, -1, -1, -1])
        time.sleep(duration[1])
        change_status([1, -1, -1, -1])
        time.sleep(duration[1])
        change_status([1, 1, -1, -1])
        time.sleep(duration[1])
        change_status([1, 1, 1, -1])
        time.sleep(duration[1])
        change_status([1, 1, 1, 1])
        time.sleep(duration[1])

def main():
    start_time = time.time()

    # check if test is needed or not
    if os.path.exists(TIME_INFO_FILE):
        # wait for NTP time (internet connection) or hardware clock
        while datetime.now().year < 2024:
            time.sleep(1)
        # check if time from last reboot is more than 2 minutes (60 seconds)
        try:
            with open(TIME_INFO_FILE, 'r') as file:
                last_time_str = file.read()
            last_time = datetime.strptime(last_time_str, '%Y-%m-%d %H:%M:%S')
            elapsed_time = (datetime.now() - last_time).total_seconds()
            if elapsed_time > 120:
                do_test = True
            else:
                do_test = False
        except Exception as e:
            do_test = True
    else:
        do_test = True

    # write current time to file
    with open(TIME_INFO_FILE, 'w') as file:
        file.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
    # perform test
    if do_test:
        import config
        setup_pins()
        change_status([0, 0, 0, 0])
        if int(config.total_switches) == 2:
            test2(TEST_REPETITIONS,TEST_DURATION)
        elif int(config.total_switches) == 4:
            test4(TEST_REPETITIONS,TEST_DURATION)
        else:
            print('Invalid number of switches!')
            sys.exit(1)
        GPIO.cleanup()
    
    # wait the remaining time to ensure a 30 s time before main startup
    end_time = time.time()
    time_wait = 30 - (end_time - start_time)
    if time_wait > 0:
        time.sleep(time_wait)
    sys.exit(0)

if __name__ == "__main__":
    main()
