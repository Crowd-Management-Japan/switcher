# Switcher
Switcher is a very simple software which allows to switch Raspberry connected devices based on BLE scans obtained through blescan. Currently the code is being used to switch on/off electrical devices (lights, speakers, etc.) based on crowding conditions. Basically you would need to obtain some relays that can be be connected to the Raspberry GPIO pins and control electrical appliances based on the number of BLE devices nearby (which is typically a good indicator of the number of people).

# Installation
Installation is rather simple and common for a Git repository working on a linux machine. First clone the repository using:
`$ git clone https://github.com/Crowd-Management-Japan/switcher`
Later move into the repository folder:
`$ cd switcher`
Get permissions to execute the installation file
`$ chmod +x install.sh`
...and actually install the program:
`$ ./install.sh`

# Use
The program is set to automatically start on system boot. At startup the switches will be tested to allow checking whether everything was setup correctly. For new startups or if the device was not used for more than 2 minutes the startup routine is being called. For restart the startup routine is prevented, to avoid sudden changes.

# Settings
`switcher/config.py` contains the main settings of the program. You need to provide a unique number identifying the controller (in case you want to use many). Also, you need to provide the number of switches (or plugs) used. Finally, URL containing the switching parameters (see below) is provided along with the URL for the backend server of the blescan software (see [blescan-backend](https://github.com/Crowd-Management-Japan/blescan-backend)).

## Static parameters
Some parameters are contained in the `switcher/startup.py` and `switcher/main.py` codes. These are the numbers of the GPIO pins used and some more specific settings, like the repetition used at startup or the types of measurement used to evaluate the crowding condition.

## Switching settings
The software reads a CSV file located on a remote server to judge when a switch is needed and what are the devices scanning a specific area. For example, if you have 10 devices (with ID from 1 to 10) scanning a given areas, the value for the `scanner_id` field will be `1-10`. `switch_threshold` determines the threshold relative to each switch. For example, if you want to switch on switch 1 when 400 is reached, and switch 2 when 600 is reached the setting will be `400/600`. Positive threshold value indicate that the switch will be turned ON above the value, negative values that it will be turned OFF when the value is exceeded. Further settings, provide the measure that should be used to evaluate crowding conditions, and the sampling time used. Finally, a switching time is provided to avoid too frequent switching in case of conditions close to the threshold.
