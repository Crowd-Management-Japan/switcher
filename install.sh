#!/bin/bash

# disable services if existing
sudo systemctl disable switcher.service
sudo systemctl stop switcher.service
echo -------- service disabled -------- 

# update system
#sudo apt update -y
#sudo apt upgrade -y
echo -------- apt installation done -------- 

# copy and rename configuration time
template_file="etc/config_template.txt"
config_file="switcher/config.py"
if [[ -e "$config_file" ]]; then
    echo "configuration file already exists, will not overwrite"
else
    cp "$template_file" "$config_file"
fi
echo -------- configuration file ready -------- 

# prepare python and packages
pip3 install -r requirements.txt
echo -------- python environment ready -------- 

# install systemd service for switcher
directory=`pwd`
cp etc/switcher_service_template etc/switcher.service
sed "s|SWITCHER_DIRECTORY|$directory|g" etc/switcher_service_template > etc/switcher.service
sudo cp -f etc/switcher.service /lib/systemd/system/
sudo systemctl enable switcher.service
echo -------- service added --------

# add crontab for daily reset:
CRON_REBOOT="0 2 * * * /sbin/shutdown -r now"
(sudo crontab -l | grep -Fxq "$CRON_REBOOT") || (sudo crontab -l; echo "$CRON_REBOOT") | sudo crontab -
CRON_RESTART="0 3 * * * systemctl restart switcher"
(sudo crontab -l | grep -Fxq "$CRON_RESTART") || (sudo crontab -l; echo "$CRON_RESTART") | sudo crontab -
echo -------- crontab commands added --------

# finally reboot or state that user should reboot
echo please reboot the device to finish the setup
