"""
rm_socket.py

author: Dr. Lee Burchett

A class for managing the NodeMCU communication sockets for the Race Manager GUI

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
from typing import List
import socket
import tkinter as tk
import time

class TimerComs:
    def __init__(self,
                 parent: tk.Tk,
                 addresses: List[str] = None,
                 hosts_file: str = None,
                 n_lanes: int = 4,
                 reset_lane: int = 1):
        if addresses is None and hosts_file is None:
            raise ValueError("You must provide a list of hosts, or a hosts file when creating sockets.")

        self.n_lanes = n_lanes
        self.hosts = [str(x) for x in range(n_lanes)]
        self.ports = [int(x) for x in range(n_lanes)]
        self.is_conn = [False for _ in range(n_lanes)]
        self.sockets = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(4)]
        self.parent=parent
        self.reset_lane = reset_lane

        if addresses is not None:
            for li, address in enumerate(addresses):
                self.set_address(li, address)
        if hosts_file is not None:
            self.get_hosts_and_ports(hosts_file)

    def shutdown(self):
        for i in range(self.n_lanes):
            self.sockets[i].shutdown(socket.SHUT_RDWR)

    def get_hosts_and_ports(self, hosts_file):
        # TODO Add YAML parser
        with open(hosts_file) as fp:
            for line in fp:
                laneNumber, hostAddress, hostPort = line.split(',')
                li = int(laneNumber) - 1
                self.hosts[li] = hostAddress
                self.ports[li] = int(hostPort)

    def set_address(self, idx, address):
        ip, port = address.split(':')
        self.ports[idx] = int(port)
        self.set_address[idx] = ip

    def connect(self):
        return self.connect_to_track_hosts()

    def connect_to_track_hosts(self):
        rb = [[], [], [], []]
        for i, sckt in enumerate(self.sockets):
            if self.is_conn[i]:
                self.is_conn[i] = False
                sckt.shutdown(socket.SHUT_RDWR)

        popup = tk.Toplevel(self.parent)
        popup.wm_title("Connection To Track")
        db = tk.Label(popup)
        db.pack()
        for i in range(4):
            rb[i] = tk.Label(popup, text="{}:{}".format(
                self.hosts[i], self.ports[i], fg='#050505'))
            rb[i].pack()
        while not all(self.is_conn):
            for i in range(4):
                if not self.is_conn[i]:
                    db.config(text="""Attempting to connect to
                                  {}:{}""".format(self.hosts[i], self.ports[i]))
                    popup.update()
                    print("Attempting to connect to {}:{}".format(self.hosts[i], self.ports[i]))
                    try:
                        self.sockets[i].connect((self.hosts[i], self.ports[i]))
                    except:
                        continue
                self.is_conn[i] = True
                print("Connection from {}:{} established.".format(host[i], port[i]))
                rb[i].config(**{'fg': '#18ff00', 'bg': '#000000'})
                time.sleep(0.1)
            if not all(self.is_conn):
                print("Waiting 5 seconds and re-attempting connection.")
                db.config(text="""Waiting 5 seconds and re-attempting
                          connection.""")
                time.sleep(5)
        popup.destroy()

    def send_reset_to_track(self, accept=False):
        global sockets_, race_needs_written, race_running
        race_running = [False, False, False, False]
        self.parent.enable_navigation()
        if self.parent.race_needs_written:
            self.parent.record_race_results(accept=accept)
            self.parent.race_needs_written = False
        print("Sending Reset to the Track")
        self.sockets[self.reset_lane].sendall("<reset>".encode('utf-8'))

    def get_data_from_socket(self, open_socket):
        socket_data = open_socket.recv(64)
        return socket_data

