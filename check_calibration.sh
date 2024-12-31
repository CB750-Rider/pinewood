#!/bin/bash

rm -f calibration.log

python race_manager.py --hosts_file lane_hosts_wifi.csv --event_file CalPlan --log_file calibration.log
