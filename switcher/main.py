import logging
import os
import csv
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
LOCAL_DATA_PATH = config.local_data

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
            logger.info("Switcher settings retrieved")
        except Exception as e:
            logger.error("Error occurred while retrieving controller settings:", e)
            sys.exit(1)
    
        # identify the setting for this controller
        try:
            # search for local controller
            for index, row in settings_table.iterrows():
                if row['controller_id'] == str(CONTROLLER_ID):
                    break
            else:
                logger.error(f"{CONTROLLER_ID} not found in the settings table")
                sys.exit(1)
            
            # read switch thresholds
            switch_threshold_str = settings_table.loc[index, 'switch_threshold']
            threshold_parts = switch_threshold_str.split("/")
            logger.info(f"{len(threshold_parts)} switches will be used")
            SWITCH_THRESHOLD = list()
            if len(threshold_parts) != TOTAL_SWITCHES:
                logger.error("Invalid pin settings or threshold settings, check whether both sizes are consistent")
                sys.exit(1)
            for i in range(0,len(threshold_parts)):
                SWITCH_THRESHOLD.append(int(threshold_parts[i]))
                logger.info(f"Threshold value {i+1} is {int(threshold_parts[i])}")
                    
            # read additional settings
            TIME_AVG = int(settings_table.loc[index, 'avg_time'])
            DATA_TYPE = int(settings_table.loc[index, 'data_type'])
            SWITCH_TIME = int(settings_table.loc[index, 'switch_time'])
            SCANNER_LIST = settings_table.loc[index, 'scanner_id']
            logger.info(f"Moving average time set to {TIME_AVG} min")
            logger.info(f"Data type {DATA_TYPE_STR[DATA_TYPE]} will be used in switching")
            logger.info(f"Switch interval is set to {SWITCH_TIME} s")

            # check if switcher needs to work with remote scanners or local data
            if SCANNER_LIST == '-1':
                SCANNER_LIST = [int(SCANNER_LIST)]
                logger.info("Using data from local scanner")
            else:
                try:
                    logger.info(f"Scanner(s) {SCANNER_LIST} will be used for monitoring")
                    if '-' in SCANNER_LIST:
                        index = SCANNER_LIST.index('-')
                        SCANNER_LIST = list(range(int(SCANNER_LIST[:index]), int(SCANNER_LIST[index + 1:])))
                    else:
                        SCANNER_LIST = [int(SCANNER_LIST)]
                except Exception as e:
                    logger.error("Error occurred while retrieving scanner list:", e)
                    SCANNER_LIST = [int(SCANNER_LIST)]
                    logger.info("Using data from local scanner")

                
        except Exception as e:
            logger.error("Error occurred while reading controller settings:", e)
            sys.exit(1)
    else:
        logger.error("No internet connectivity, could not retrieve settings, will use default settings and local data")
        DATA_TYPE, TIME_AVG, SWITCH_TIME, SCANNER_LIST = [0, 5, 0, 'local']
        SWITCH_THRESHOLD = [100] * TOTAL_SWITCHES

        # show settings in use
        logger.info(f"{TOTAL_SWITCHES} switches will be used")
        for i in range(0,TOTAL_SWITCHES):
                logger.info(f"Threshold value {i+1} is {int(SWITCH_THRESHOLD[i])}")
        logger.info(f"Moving average time set to {TIME_AVG} min")
        logger.info(f"Data type {DATA_TYPE} will be used in switching")
        logger.info(f"Switch interval is set to {SWITCH_TIME} s")

def get_daily_subfolder(parent_folder):
    subdirs = [os.path.join(parent_folder, name) for name in os.listdir(parent_folder)
               if os.path.isdir(os.path.join(parent_folder, name))]
    if len(subdirs) != 1:
        logger.error(f"Expected exactly one subfolder in '{parent_folder}', found {len(subdirs)}.")
    return os.path.join(parent_folder, subdirs[0])

def get_relevant_files(now, time_avg, folder_path):
    files = []
    for i in range(time_avg + 10):
        time = now - timedelta(minutes=i)
        file_name = time.strftime('%H%M') + '_summary.csv'
        full_path = os.path.join(folder_path, file_name)
        if os.path.isfile(full_path) and full_path not in files:
            files.append(full_path)
    return files

def extract_values(file_path, start_time, end_time, data_column):
    values = []
    try:
        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) <= data_column or len(row) < 2:
                    continue 
                try:
                    row_time = datetime.strptime(row[1].strip(), "%H:%M:%S").time()
                    row_dt = datetime.combine(datetime.now().date(), row_time)
                except ValueError:
                    continue
                if start_time <= row_dt <= end_time:
                    value = row[data_column].strip()
                    if value != '':
                        values.append(float(value))
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
    
    return values

def get_local_values(now, time_delta):
    # get list of files to check
    folder_path = get_daily_subfolder(LOCAL_DATA_PATH)
    files = get_relevant_files(now, TIME_AVG, folder_path)
    files.reverse()                   

    # extract values from file and compute average
    all_values = []
    start_time = now - time_delta
    for file in files:
        values = extract_values(file, start_time, now, 4 + DATA_TYPE)
        all_values.extend(values)
        total_result = sum(values) / len(values)

    return total_result  

# main loop
def main():
    global logger
    global GPIO

    logger = setup_logging()
    GPIO = setup_pins()
    initialize_file()
    read_settings()
    time_delta = timedelta(minutes=TIME_AVG)
    last_switch = datetime.now()
    last_checked_sec = -1
    switch_state = np.zeros(TOTAL_SWITCHES)
    logger.info("Switching process started")

    try:
        while True:
            # check if renewal of settings is needed and/or filename has changed
            if time.localtime().tm_sec == 0:
                initialize_file()
                read_settings()
            
            # check number of BLE devices and determine if switching is needed
            current_sec = time.localtime().tm_sec
            if (time.localtime().tm_sec % 10 == 0) and (current_sec != last_checked_sec):
                last_checked_sec = current_sec

                # write current time (needed at reboot to judge if swith test is needed)
                current_time = datetime.now()
                with open(TIME_INFO_FILE, 'w') as file:
                    file.write(current_time.strftime('%Y-%m-%d %H:%M:%S'))
            
                # get the total number of BLE devices
                now = datetime.now()
                total_result = 0
                try:
                    if check_internet_connection():
                        if (len(SCANNER_LIST) == 1) and (SCANNER_LIST[0] < 0):
                            total_result = get_local_values(now, time_delta)
                        else:
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
                        total_result = get_local_values(now, time_delta)
                        
                except Exception as e:
                    logger.error("Error occurred while obtaining counts:", e)
                    sys.exit(1)
                total_result = round(total_result)
                logger.info(f"Current total number of BLE devices is {total_result}")
                
                # determine if switching is necessary
                try:
                    for i in range(0,TOTAL_SWITCHES):
                        if total_result >= abs(SWITCH_THRESHOLD[i]):
                            if (datetime.now() - last_switch).total_seconds() > SWITCH_TIME:
                                if SWITCH_THRESHOLD[i] > 0 and switch_state[i] == 0:
                                    GPIO.output(RELAY_PINS[i], GPIO.HIGH)
                                    logger.info(f" --> Switch {i+1} turned ON <--")
                                    switch_state[i] = 1
                                if SWITCH_THRESHOLD[i] < 0 and switch_state[i] == 1:
                                    GPIO.output(RELAY_PINS[i], GPIO.LOW)
                                    logger.info(f" <-- Switch {i+1} turned OFF -->")
                                    switch_state[i] = 0
                        if total_result < abs(SWITCH_THRESHOLD[i]):
                            if (datetime.now() - last_switch).total_seconds() > SWITCH_TIME:
                                if SWITCH_THRESHOLD[i] > 0 and switch_state[i] == 1:
                                    GPIO.output(RELAY_PINS[i], GPIO.LOW)
                                    logger.info(f" --> Switch {i+1} turned OFF <--")
                                    switch_state[i] = 0
                                if SWITCH_THRESHOLD[i] < 0 and switch_state[i] == 0:
                                    GPIO.output(RELAY_PINS[i], GPIO.HIGH)
                                    logger.info(f" <-- Switch {i+1} turned ON -->")
                                    switch_state[i] = 1  
                except Exception as e:
                    logger.error("Error occurred while switching:", e)
                    sys.exit(1)
                    
                # write data if needed
                try:
                    for i in range(0,TOTAL_SWITCHES):
                        DATAFILE.write(now.strftime("%Y-%m-%d,%H:%M:%S")+","+str(total_result)+","+str(i+1)+","+str(int(switch_state[i]))+"\n")
                        DATAFILE.flush()             
                except Exception as e:
                    logger.error("While writing data:", e)
                    sys.exit(1)
                    
            time.sleep(0.25)

    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()