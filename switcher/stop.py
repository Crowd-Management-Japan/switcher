
import RPi.GPIO as GPIO

# Define the GPIO pin for the relay
RELAY_PINS = [23, 24, 25, 26]

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

def main():
    import config
    setup_pins()
    change_status([0, 0, 0, 0])
    if int(config.total_switches) == 2:
        change_status([-1, -1, 0, 0])
    elif int(config.total_switches) == 4:
        change_status([-1, -1, -1, -1])
    GPIO.cleanup()

if __name__ == "__main__":
    main()