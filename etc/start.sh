#!/bin/bash

directory=`pwd`

# update git repository
echo update software from git...
git pull origin master

# check if test program should be started or not
echo starting test program...
startup_script=$directory"/switcher/startup.py"
python3 -u $startup_script

# start main program
echo starting main program...
main_script=$directory"/switcher/main.py"
python3 -u $main_script
