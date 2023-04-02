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
import select
import string


class TimerComs:
    n_lanes: int = 0
    hosts: list = []
    ports: list = []
    sockets: list = []

    def __init__(self,
                 parent: tk.Tk,
                 addresses: List[str] = None,
                 hosts_file: str = None,
                 n_lanes: int = 4,
                 reset_lane: int = 3):
        if addresses is None and hosts_file is None:
            raise ValueError("You must provide a list of hosts, or a hosts file when creating sockets.")

        self.n_lanes = n_lanes
        self.hosts = [str(x) for x in range(n_lanes)]
        self.ports = [int(x) for x in range(n_lanes)]
        self.is_conn = [False for _ in range(n_lanes)]
        self.entry_widgets = [[]]*n_lanes
        self.sockets = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(4)]
        self.parent = parent
        self.reset_lane = reset_lane
        self.all_connected = False
        self.connection_window_open = False

        if addresses is not None:
            for li, address in enumerate(addresses):
                self.set_address(li, address)
        if hosts_file is not None:
            self.get_hosts_and_ports(hosts_file)

    def shutdown(self):
        for i in range(self.n_lanes):
            try:
                self.sockets[i].shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sockets[i].close()

    def get_hosts_and_ports(self, hosts_file):
        # TODO Add YAML parser
        with open(hosts_file) as fp:
            for line in fp:
                laneNumber, hostAddress, hostPort = line.split(',')
                li = int(laneNumber) - 1
                self.hosts[li] = hostAddress
                self.ports[li] = int(hostPort)

    def save_timer_hosts(self, file_name):
        # TODO Add YAML saver
        with open(file_name, 'w') as outfile:
            lane_number=1
            for hst, port in zip(self.hosts, self.ports):
                outfile.write(','.join([str(lane_number), hst, str(port)])+'\n')

    def set_address(self, idx, address):
        ip, port = address.split(':')
        self.ports[idx] = int(port)
        self.hosts[idx] = ip

    def reset_socket(self, sock: socket.socket):
        """Closes and resets the socket matching sock  """
        for i, sock2 in enumerate(self.sockets):
            if sock is sock2:
                break

        if self.is_conn[i]:
            self.is_conn[i] = False
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

        self.all_connected = False
        self.sockets[i] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def reset_sockets(self):
        "Closes and resets all sockets "
        for sckt in self.sockets:
            self.reset_socket(sckt)

    def close_conn_window(self):
        self.connection_window_open=False

    def connect_to_track_hosts(self, autoclose=False, reset=False):
        self.connection_window_open = True

        if reset:
            self.reset_sockets()

        rb = self.entry_widgets
        port_text = [[]] * self.n_lanes

        popup = tk.Toplevel(self.parent)
        popup.wm_title("Connection To Track")
        popup.protocol("WM_DELETE_WINDOW", self.close_conn_window)
        db = tk.Label(popup, width=45)
        db.pack()
        for i in range(self.n_lanes):
            port_text[i] = tk.StringVar()
            port_text[i].set(f"{self.hosts[i]}:{self.ports[i]}")
            #rb[i] = tk.Label(popup, tex="{}:{}".format(
            #    self.hosts[i], self.ports[i], fg='#050505'))
            rb[i] = tk.Entry(popup, textvariable=port_text[i])
            rb[i].pack()
        reset_button = tk.Button(popup, text="Reset", command=self.reset_sockets).pack()
        exit_button = tk.Button(popup, text="Exit", command=self.close_conn_window).pack()
        last_time = time.clock_gettime(time.CLOCK_MONOTONIC) - 10.0
        loop_count = 5

        popup.lift()

        if self.all_connected:
            for i in range(self.n_lanes):
                rb[i].config(**{'fg': '#18ff00', 'bg': '#404040'})

        while self.connection_window_open:
            if self.all_connected:
                db.config(text="Connected. Press Reset to drop and reconnect.")
                popup.update_idletasks()
                popup.update()
                time.sleep(0.05)
                continue
            time_diff = time.clock_gettime(time.CLOCK_MONOTONIC) - last_time
            if time_diff < 1.0:
                popup.update_idletasks()
                popup.update()
                time.sleep(0.01)
                continue
            elif loop_count < 1:
                loop_count += 1
                last_time = time.clock_gettime(time.CLOCK_MONOTONIC)
                db.config(text=f"Re-attempting in {1-loop_count} second.")
                popup.update_idletasks()
                popup.update()
                time.sleep(0.01)
                continue
            else:
                loop_count = 0

            has_focus = self.parent.focus_get()
            i=0
            while i < self.n_lanes:
                while self.entry_widgets[i] == has_focus:
                    db.config(text=f"Re-attempting connection after editing.")
                    i=-1
                    time.sleep(0.05)
                    popup.update_idletasks()
                    popup.update()
                    has_focus = self.parent.focus_get()
                i+=1
            self.parent.focus_set()
            for i in range(self.n_lanes):
                self.hosts[i] = port_text[i].get().split(':')[0]
                try:
                    self.ports[i] = int(port_text[i].get().split(':')[-1])
                except ValueError:
                    pass
            for i in range(self.n_lanes):
                if not self.is_conn[i]:
                    rb[i].config(**{'fg': '#000000', 'bg': '#ffffff'})
                    db.config(text="Attempting to connect to {}:{}".format(
                        self.hosts[i], self.ports[i]))
                    popup.update()
                    print("Attempting to connect to {}:{}".format(
                        self.hosts[i], self.ports[i]))
                    try:
                        self.sockets[i].setblocking(False)
                        self.sockets[i].connect((self.hosts[i], self.ports[i]))
                    except InterruptedError:
                        continue
                    except ConnectionRefusedError:
                        continue
                    except:
                        rb[i].config(**{'fg': '#ff0000', 'bg': '#ffffff'})
                    else:
                        self.is_conn[i] = True
                        print("Connection from {}:{} established.".format(
                            self.hosts[i], self.ports[i]))
                        rb[i].config(**{'fg': '#18ff00', 'bg': '#404040'})
                        time.sleep(0.1)
            if not all(self.is_conn):
                print("Waiting 1 second and re-attempting connection.")
                db.config(text="""Waiting 1 second1 and re-attempting connection.""")
                last_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            else:
                self.all_connected = True
                if autoclose:
                    self.connection_window_open = False
            popup.update_idletasks()
            popup.update()
        popup.destroy()

    def check_connections(self):
        for i in range(self.n_lanes):
            if not self.is_conn[i]:
                try:
                    self.sockets[i].setblocking(False)
                    self.sockets[i].connect((self.hosts[i], self.ports[i]))
                except:
                    continue
                else:
                    self.is_conn[i] = True
                    print("Connection from {}:{} established.".format(
                        self.hosts[i], self.ports[i]))
        return self.is_conn

    def send_reset_to_track(self, accept=False):
        print("Sending Reset to the Track")
        if self.is_conn[self.reset_lane]:
            self.sockets[self.reset_lane].sendall("<reset>".encode('utf-8'))
        else:
            self.connect_to_track_hosts()

    def get_data_from_socket(self, open_socket):
        try:
            socket_data = open_socket.recv(64)
        except ConnectionResetError:
            return "".encode('utf-8')
        return socket_data

    def select(self, wait_len=0.05):
        return select.select(self.sockets, self.sockets, self.sockets, wait_len)

    def socket_index(self, test_socket):
        for i, sc in enumerate(self.sockets):
            if test_socket == sc:
                return i
        raise ValueError("Unable to find a matching socket.")

    def sockets_are_in_list(self, test_list):
        results = [False] * self.n_lanes
        for idx, sc in enumerate(self.sockets):
            results[idx] = sc in test_list
        return results




