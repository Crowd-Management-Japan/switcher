#!/bin/bash

# update git repository
#echo update software from git...
#cd switcher
#git pull origin master
#cd ..

# check if test program should be started or not
directory=`pwd`
poweroff_file="/var/tmp/poweroff_check.txt"

if [ -f "$poweroff_file" ]; then
    echo "true"
else
    echo "false"
fi

if [ -f "$poweroff_file" ]; then
    echo waiting to ensure LTE is powered on...
    #sleep 30
else
    echo starting test program...
    startup_script=$directory"/switcher/switcher/startup.py"
    python3 -u $startup_script
fi
date +'%Y-%m-%d %H:%M:%S' > "$poweroff_file"

# start main program
echo starting main program...
main_script=$directory"/switcher/switcher/main.py"
python3 -u $main_script
