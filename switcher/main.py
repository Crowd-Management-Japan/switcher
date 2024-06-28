import logging
import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import sys
import socket
import platform
from io import StringIO
import config

# read settings from config file
TOTAL_SWITCHES = config.total_switches
CONTROLLER_ID = config.controller_id
SETTINGS_URL = config.settings_url
BACKEND_ADDRESS = config.scanner_server_address

# define constants
TIME_INFO_FILE = '/var/tmp/last_time.txt'
RELAY_PINS = [23, 24, 25, 26]
DATA_TYPE_STR = ['tot_all','tot_close','inst_all','inst_close','stat_all','stat_close']

# define variables
TIME_AVG = 0
SCANNER_LIST = list()
DATA_TYPE = 0
SWITCH_THRESHOLD = list()
SWITCH_TIME = 0
DATAFILE = 0

# check if code is being run from raspberry or from a PC/Mac
def check_raspberry_pi():
    try:
        # Check the platform name
        if platform.system() == 'Linux':
            # Check for specific file that exists only on Raspberry Pi
            with open('/proc/cpuinfo', 'r') as cpuinfo:
                for line in cpuinfo:
                    if 'Raspberry Pi' in line:
                        return True
        return False
    except Exception as e:
        logger.error("Error while checking OS environment:", e)
        return False

# setup logging
def setup_logging():
    log_path = os.path.expanduser("~") + "/switcher/logs"
    if not os.path.exists(log_path):
        os.mkdir(log_path)

    previous_month = datetime.now() - timedelta(days=30)
    old_filename = f"{log_path}/log_{previous_month.strftime('%m%d')}.txt"
    new_filename = f"{log_path}/log_{datetime.now().strftime('%m%d')}.txt"

    if os.path.exists(old_filename):
        os.remove(old_filename)
    
    logger = logging.getLogger('switch controller')
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        log_format = "%(asctime)s - %(levelname)s: %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S" 
        formatter = logging.Formatter(log_format, date_format)
        file_handler = logging.FileHandler(new_filename)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger.info("**********************************************************")
    logger.info("Logger configured and program started")
    return logger

# setup GPIO pins
def setup_pins():
    import RPi.GPIO as GPIO
    GPIO.setwarnings(False)
    try:
        GPIO.setmode(GPIO.BCM)
        for i in range(0,len(RELAY_PINS)):
            GPIO.setup(RELAY_PINS[i], GPIO.OUT)
            GPIO.output(RELAY_PINS[i], GPIO.LOW)
    except Exception as e:
        logger.error("Error while setting up GPIO configurations:", e)
        sys.exit(1)
    return GPIO

# initialize recordings file
def initialize_file():
    global DATAFILE
    if not os.path.exists(os.path.expanduser("~") + "/switch_data"):
        os.mkdir(os.path.expanduser("~") + "/switch_data")
    now = datetime.now()
    filename = os.path.expanduser("~") + "/switch_data/"+now.strftime("%Y%m%d")+".csv"
    DATAFILE = open(filename,"a")
    if os.stat(filename).st_size == 0:
        DATAFILE.write("Date,Time,BLE devices,Switch #,Operation\n")

# check for internet connectivity    
def check_internet_connection(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except:
        return False    

# function reading the settings for this controller from the CSV file online
def read_settings(): 
    # define global variables
    global TIME_AVG
    global SCANNER_LIST
    global DATA_TYPE
    global SWITCH_THRESHOLD
    global SWITCH_TIME
    
    if check_internet_connection():
        # read table containing main settings
        try:
            settings_table = pd.read_csv(SETTINGS_URL, header=None)
            settings_table = settings_table.transpose()
            new_header = settings_table.iloc[0]
            settings_table = settings_table[1:]
            settings_table.columns = new_header
            if is_raspberry:
                logger.info("Switcher settings retrieved")
        except Exception as e:
            if is_raspberry:
                logger.error("Error occurred while retrieving controller settings:", e)
            sys.exit(1)
    
        # identify the setting for this controller
        try:
            # search for local controller
            for index, row in settings_table.iterrows():
                if row['controller_id'] == str(CONTROLLER_ID):
                    break
            else:
                if is_raspberry:
                    logger.error(f"{CONTROLLER_ID} not found in the settings table")
                sys.exit(1)
            
            # read switch thresholds
            switch_threshold_str = settings_table.loc[index, 'switch_threshold']
            threshold_parts = switch_threshold_str.split("/")
            SWITCH_THRESHOLD = list()
            if len(threshold_parts) != TOTAL_SWITCHES:
                if is_raspberry:
                    logger.error("Invalid pin settings or threshold settings, check whether both sizes are consistent")
                sys.exit(1)
            for i in range(0,len(threshold_parts)):
                SWITCH_THRESHOLD.append(int(threshold_parts[i]))
                if is_raspberry:
                    logger.info(f"Threshold value {i+1} is {int(threshold_parts[i])}")
                    
            # read additional settings
            TIME_AVG = int(settings_table.loc[index, 'avg_time'])
            DATA_TYPE = int(settings_table.loc[index, 'data_type'])
            SWITCH_TIME = int(settings_table.loc[index, 'switch_time'])
            SCANNER_LIST = settings_table.loc[index, 'scanner_id']
            if is_raspberry:
                logger.info(f"{len(threshold_parts)} switches will be used")
                logger.info(f"Moving average time set to {TIME_AVG} min")
                logger.info(f"Data type {DATA_TYPE} will be used in switching")
                logger.info(f"Switch interval is set to {SWITCH_TIME} s")
                logger.info(f"Scanners {SCANNER_LIST} will be used for monitoring")
            if '-' in SCANNER_LIST:
                index = SCANNER_LIST.index('-')
                SCANNER_LIST = list(range(int(SCANNER_LIST[:index]), int(SCANNER_LIST[index + 1:])))
            else:
                SCANNER_LIST = int(SCANNER_LIST)
        except Exception as e:
            if is_raspberry:
                logger.error("Error occurred while reading controller settings:", e)
            sys.exit(1)
    else:
        SWITCH_THRESHOLD = np.zeros(len(threshold_parts))
        if is_raspberry:
            logger.error("No internet connectivity, could not retrieve settings")
    
# main loop
def main():
    global logger
    global GPIO
    global is_raspberry
    is_raspberry = check_raspberry_pi()
    if is_raspberry:
        logger = setup_logging()
        GPIO = setup_pins()
        initialize_file()
    read_settings()
    time_delta = timedelta(minutes=TIME_AVG)
    last_switch = datetime.now()
    switch_state = np.zeros(TOTAL_SWITCHES)
    if is_raspberry:
        logger.info("Switching process started")
    try:
        while True:
            # check if renewal of settings is needed and/or filename has changed
            if time.localtime().tm_sec == 0:
                if is_raspberry:
                    initialize_file()
                read_settings()
            
            # check number of BLE devices and determine if switching is needed
            if time.localtime().tm_sec % 10 == 0:
                # Write current time (needed at reboot to judge if swith test is needed)
                current_time = datetime.now()
                with open(TIME_INFO_FILE, 'w') as file:
                    file.write(current_time.strftime('%Y-%m-%d %H:%M:%S'))
            
                # get the total number of BLE devices
                now = datetime.now()
                total_result = 0
                try:
                    if check_internet_connection():
                        for scanner_id in SCANNER_LIST: 
                            after_time = (now - time_delta).strftime('%Y-%m-%d %H:%M:%S')
                            before_time = now.strftime('%Y-%m-%d %H:%M:%S')
                            endpoint = f"/database/export_data?id={scanner_id}&after={after_time}&before={before_time}"
                            req = requests.get(f"{BACKEND_ADDRESS}{endpoint}")
                            json_data = StringIO(req.text)
                            ble_data = pd.read_json(json_data)
                            if not ble_data.empty:
                                total_result += ble_data[DATA_TYPE_STR[DATA_TYPE]].mean()
                    else:
                        if is_raspberry:
                            logger.error("No internet connectivity, could not connect to scanners")
                except Exception as e:
                    if is_raspberry:
                        logger.error("Error occurred while obtaining counts:", e)
                    sys.exit(1)
                total_result = round(total_result)
                if is_raspberry:
                    logger.info(f"Current total number of BLE devices is {total_result}")
                else:
                    print(f"Current total number of BLE devices is {total_result}")
                
                # determine if switching is necessary
                try:
                    for i in range(0,TOTAL_SWITCHES):
                        if total_result >= abs(SWITCH_THRESHOLD[i]):
                            if (datetime.now() - last_switch).total_seconds() > SWITCH_TIME:
                                if SWITCH_THRESHOLD[i] > 0 and switch_state[i] == 0:
                                    if is_raspberry:
                                        GPIO.output(RELAY_PINS[i], GPIO.HIGH)
                                        logger.info(f" --> Switch {i+1} turned ON <--")
                                    switch_state[i] = 1
                                if SWITCH_THRESHOLD[i] < 0 and switch_state[i] == 1:
                                    if is_raspberry:
                                        GPIO.output(RELAY_PINS[i], GPIO.LOW)
                                        logger.info(f" <-- Switch {i+1} turned OFF -->")
                                    switch_state[i] = 0
                        if total_result < abs(SWITCH_THRESHOLD[i]):
                            if (datetime.now() - last_switch).total_seconds() > SWITCH_TIME:
                                if SWITCH_THRESHOLD[i] > 0 and switch_state[i] == 1:
                                    if is_raspberry:
                                        GPIO.output(RELAY_PINS[i], GPIO.LOW)
                                        logger.info(f" --> Switch {i+1} turned OFF <--")
                                    switch_state[i] = 0
                                if SWITCH_THRESHOLD[i] < 0 and switch_state[i] == 0:
                                    if is_raspberry:
                                        GPIO.output(RELAY_PINS[i], GPIO.HIGH)
                                        logger.info(f" <-- Switch {i+1} turned ON -->")
                                    switch_state[i] = 1  
                except Exception as e:
                    if is_raspberry:
                        logger.error("Error occurred while switching:", e)
                    sys.exit(1)
                    
                # write data if needed
                if is_raspberry:
                    try:
                        for i in range(0,TOTAL_SWITCHES):
                            DATAFILE.write(now.strftime("%Y-%m-%d,%H:%M:%S")+","+str(total_result)+","+str(i+1)+","+str(int(switch_state[i]))+"\n")
                            DATAFILE.flush()             
                    except Exception as e:
                        logger.error("While writing data:", e)
                        sys.exit(1)
                    
                
            time.sleep(0.25)

    except KeyboardInterrupt:
        print("\nclosing program...")

    finally:
        if is_raspberry:
            GPIO.cleanup()

if __name__ == "__main__":
    main()