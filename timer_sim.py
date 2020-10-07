"""
timer_sim.py

simulates the timer hardware for debugging of the pinewood applications.

Copyright [2019] [Lee R. Burchett]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
import socket
import numpy as np
import select
import time
import tkinter as tk

host = ['', '', '', '']
port = [0, 0, 0, 0]
infile = "lane_hosts.csv"
ready_msg = "<Ready to Race.>".encode('utf-8')
go_msg = "<GO!>".encode('utf-8')
reset_msg = "<Reset recieved.>".encode('utf-8')
time_prefix = "<Track count:".encode('utf-8')
time_suffix = ">".encode('utf-8')
stringlen = 64
race_ready = False
running_race = True
report_lane = [[], [], [], []]


def toggle_racing():
    global t_btn, running_race
    if t_btn.config('text')[-1] == "Racing":
        t_btn.config(text="On Hold")
        running_race = False
    else:
        t_btn.config(text="Racing")
        running_race = True


def make_str(race_number):
    new_times = 12.0 + np.random.randn(4) / 10.0
    time_str = ["{:5.3f}".format(x) for x in new_times]
    time_str.insert(0, "{:5}".format(race_number))
    return ','.join(time_str), race_number + 1


def set_host_and_port():
    global infile, host, port
    with open(infile) as fp:
        for line in fp:
            laneNumber, hostAddress, hostPort = line.split(',')
            li = int(laneNumber) - 1
            host[li] = hostAddress
            port[li] = int(hostPort)


def race_reset():
    global race_ready, conn
    for socket in conn:
        socket.sendall(reset_msg)
        socket.sendall(ready_msg)
    race_ready = True


def time_msg():
    """Normally distributed random numbers around 4 seconds"""
    racer_time = np.random.randn() * 0.1 + 4.0
    "Convert to counts"
    print("Time = {}".format(racer_time))
    racer_time = np.array(racer_time * 2000.0).astype(np.int32)
    print("Counts = {}".format(racer_time))
    time_message = "{}".format(racer_time).encode('utf-8')
    return time_message


def close_sockets(connection):
    for socket in connection:
        socket.close()


def not_ready():
    print("The connections are not ready yet!")


def run_race(conn):
    global report_lane
    for socket in conn:
        socket.sendall(go_msg)
    time.sleep(3)
    for idx, socket in enumerate(conn):
        if report_lane[idx].get():
            socket.sendall(time_prefix + time_msg() + time_suffix)
        time.sleep(np.random.rand() / 2.0)


def close_manager():
    global conn, end_program
    end_program = True
    for cn in conn:
        cn.shutdown(socket.SHUT_RDWR)
    raise SystemExit


if __name__ == "__main__":
    #    global infile,host,port,race_ready
    end_program = False
    sockets_ = [[], [], [], []]
    cb = [[], [], [], []]
    conn = [[], [], [], []]
    addr = [[], [], [], []]
    prompt_reset = True
    if len(sys.argv) == 1:
        print("Using the hosts in {}.".format(infile))
        print("Pass a file name if you would like to use a different file.")
    elif len(sys.argv) == 2:
        infile = sys.argv[1]
    else:
        infile = sys.argv[1]
        print("Only the first argument is used")

    set_host_and_port()

    window = tk.Tk()
    for i in range(4):
        report_lane[i] = tk.BooleanVar()
        report_lane[i].set(True)
        cb[i] = tk.Checkbutton(window, text="Lane {}".format(i + 1)
                               , variable=report_lane[i])
        cb[i].pack()
    bt = tk.Button(window, text="Reset", command=not_ready)
    bt.pack()
    t_btn = tk.Button(window, text="Racing", command=toggle_racing)
    t_btn.pack()
    window.protocol("WM_DELETE_WINDOW", close_manager)
    window.update()

    for i in range(4):
        print("Setting up connection to {}:{}".format(host[i], port[i]))
        sockets_[i] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockets_[i].bind((host[i], port[i]))
        sockets_[i].listen(2)
        print("Awaiting connection on {}:{}".format(host[i], port[i]))
        conn[i], addr[i] = sockets_[i].accept()
        print("Connection from {} established.".format(addr[i]))

    connections_ready = True
    bt.config(command=race_reset)

    while connections_ready:
        if not race_ready:
            ready_sockets, writy_sockets, _ = select.select(conn, conn, [], 5.0)
            for socket in ready_sockets:
                data = socket.recv(64).decode('utf-8')
                if 'reset' in data:
                    race_reset()

        if len(writy_sockets) < 4:
            print("A socket disconnected. We should restart")
            close_sockets(conn)
            connections_ready = False

        if race_ready and running_race:
            print("Running Race in 2 seconds.")
            time.sleep(2)
            run_race(conn)
            race_ready = False

        window.update_idletasks()
        window.update()

        if end_program:
            break;
