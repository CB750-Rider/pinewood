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
from multiprocessing import Queue, Process, Pipe
from pip._vendor.requests.utils import _null

message_color = "\033[94m"
normal_color = "\033[0m"

# Pipe messages for controlling _TimerSocket
_conf_msg = "confirmed".encode('utf-8')
_shutdown_msg = "shutdown".encode('utf-8')
_connect_msg = "connect".encode('utf-8')
_check_connection_msg = "check_conn".encode('utf-8')
_socket_reset_msg = "reset_socket".encode('utf-8')

# Socket messages for controlling the timers
_test_msg = "<test>".encode('utf-8')
_reset_msg = "<reset>".encode('utf-8')
_resend_data_msg = "<resend>".encode('utf-8')
_stop_counting = "<stopCt>".encode('utf-8')
counter_messages = [_test_msg, _reset_msg, _resend_data_msg, _stop_counting]

# Used to indicate no data on the socket
_null_data = "".encode('utf-8')


class _TimerSocket:
    """
    _TimerSocket is a class that actually connects to a timer using
    a socket. It is expected that this class will be started in a
    multiprocess module and communicate with the main program via
    a Pipe (for command and control) and a Queue (for passing messages
    along)
    """

    def __init__(self,
                 address: str,
                 port: int,
                 pipe: Pipe,
                 queue: Queue,
                 verbose: bool = False,
                 index: int = -1):
        self.address = address
        self.port = port
        self.pipe = pipe
        self.verbose = verbose
        self.index = index
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.queue = queue
        try:
            self.connect()
        except Exception as e:
            pass
        self.running = True

    def _vprint(self, msg):
        if self.verbose:
            print(f"{message_color}rm_socket._TimerSocket: {msg} {normal_color}")

    def reset_socket(self):
        """ Closes and resets the socket. """
        self._close_socket()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def _close_socket(self):
        if self.check_connection():
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.socket.close()

    def _shutdown(self):
        self.running = False
        self._close_socket()

    def _check_pipe(self, n_writer):
        if self.pipe.poll():
            msg = self.pipe.recv()
        else:
            return
        try:
            self._parse_pipe_msg(msg, n_writer)
        except ConnectionError:
            for i in range(5):
                self._vprint(f"Attempt {i} of 5 to reconnect the socket.")
                self.reset_socket()
                _, wrtr, _ = select.select([], [self.socket], [])
                if len(wrtr) == 0:
                    continue
                else:
                    self._parse_pipe_msg(msg, len(wrtr))
                    break

    def _parse_pipe_msg(self, msg, n_writer):
        if msg == _conf_msg:
            self.pipe.send(_conf_msg)
        elif msg == _shutdown_msg:
            self._shutdown()
            self.pipe.send(_conf_msg)
        elif msg == _connect_msg:
            try:
                self.connect()
                self.pipe.send(_conf_msg)
            except Exception as e:
                self.pipe.send(repr(e).encode('utf-8'))
        elif msg == _check_connection_msg:
            try:
                self.check_connection()
                self.pipe.send(_conf_msg)
            except Exception as e:
                self.pipe.send(repr(e).encode('utf-8'))
        elif msg == _socket_reset_msg:
            try:
                self.reset_socket()
                self.pipe.send(_conf_msg)
            except Exception as e:
                self.pipe.send(repr(e).encode('utf-8'))

        elif msg in counter_messages: 
            if n_writer < 1:
                raise ConnectionError("Unable to send message to socket")
            try:
                self.socket.sendall(msg)
                self.pipe.send(_conf_msg)
            except Exception as e:
                self.pipe.send(repr(e).encode('utf-8'))
        else:
            self.pipe.send("UnknownCommand".encode('utf-8'))

    def get_data_from_socket(self):
        try:
            socket_data = self.socket.recv(64)
        except ConnectionResetError:
            return _null_data
        return socket_data

    def check_connection(self):
        try:
            self.socket.send(_test_msg)
            return True
        except Exception as e:
            self._vprint(f"!!Error found with socket {self.index}!!")
            raise e

    def connect(self):
        self.socket.connect((self.address, self.port))
        self.socket.setblocking(False)

    def run(self):
        while self.running:
            rdr, wrtr, err = select.select([self.socket, ],
                                           [self.socket, ],
                                           [self.socket, ],
                                           0.25)
            if len(rdr) > 0:
                try:
                    data = self.get_data_from_socket()
                    if len(data) > len(_null_data):
                        self.queue.put({'idx': self.index, 'data': data})
                        self._vprint(f"{self.index} Sent {data.decode('utf-8')}")
                except Exception as e:
                    self.pipe.send(repr(e).encode('utf-8'))

            self._check_pipe(len(wrtr))

            if len(err) > 0:
                self._vprint(f"An error was found with the socket. Resetting.")
                time.sleep(5.0)
                self.reset_socket()


def _create_connection(address, port, pipe, queue, verbose, index):
    """
    Starts up the connection and keeps it going in a loop until
    it closes
    :return:
    """

    connection = _TimerSocket(address, port, pipe, queue, verbose, index)

    connection.run()


class TimerConnection:
    """ This is a silly little intermediary that spawns a new process
    to handle the socket connection asynchronously. """

    def __init__(self,
                 address: str,
                 port: int,
                 queue: Queue,
                 verbose: bool = False,
                 index: int = -1):
        """
        Sets up a separate process for handling communications with the
        timer. Uses a Pipe to send commands to that process and to get
        data from the process.
        """
        self.pipe, child_pipe = Pipe(duplex=True)
        self.p = Process(target=_create_connection,
                         args=(address, port, child_pipe,
                               queue, verbose, index))
        self.p.start()
        self.index = index
        self.address = address
        self.port = port
        self.verbose = verbose
        self.index = index
        self.connected = self.is_connected(quick=False)

    def _vprint(self, msg):
        if self.verbose:
            print(f"{message_color}rm_socket.TimerConnection: {msg} {normal_color}")

    def shutdown(self):
        self.pipe.send(_shutdown_msg)
        self._await_conf()
        self.connected = False
        self.p.close()
        self._vprint(
            f"{message_color}rm_socket.TimerConneciton: Waiting for connection {self.index} to close.{normal_color}")
        self.p.join()

    def _await_conf(self):
        msg = self.pipe.recv()
        if msg == _conf_msg:
            return True
        else:
            return False

    def is_connected(self, quick=True):
        if quick:
            return self.connected
        else:
            self.pipe.send(_check_connection_msg)
            self.connected = self._await_conf()
        return self.connected


    def reset_socket(self):
        self.pipe.send(_socket_reset_msg)

    def send_reset(self):
        self.pipe.send(_reset_msg)

    def send_stop(self):
        self.pipe.send(_stop_counting)

class TimerComs:

    def __init__(self,
                 parent: tk.Tk,
                 addresses: List[str] = None,
                 hosts_file: str = None,
                 n_lanes: int = 4,
                 reset_lane: int = 0,
                 verbose: bool = False):
        if addresses is None and hosts_file is None:
            raise ValueError("You must provide a list of hosts, or a hosts file when creating sockets.")

        self.q = Queue()
        self.n_lanes = n_lanes
        self.hosts = [str(x) for x in range(n_lanes)]
        self.ports = [int(x) for x in range(n_lanes)]
        self.entry_widgets = [[]] * n_lanes
        # self.sockets = [socket.socket(socket.AF_INET, socket.SOCK_STREAM) for _ in range(4)]
        self.parent = parent
        self.reset_lane = reset_lane
        self.connection_window_open = False
        self.verbose = verbose

        if addresses is not None:
            for li, address in enumerate(addresses):
                self.set_address(li, address)
        if hosts_file is not None:
            self.get_hosts_and_ports(hosts_file)

        self.comms = []
        for i in range(self.n_lanes):
            self.comms.append(self.set_up_comms(i))

    def _vprint(self, msg):
        if self.verbose:
            print(f"{message_color}rm_socket.TimerComs: {msg} {normal_color}")

    def shutdown(self):
        for i in range(self.n_lanes):
            try:
                self.comms[i].shutdown()
            except Exception as e:
                self._vprint(f"Error {repr(e)} encountered and ignored when attempting to shutdown.")
                pass

    def send_stop(self, idx):
        self.comms[idx].send_stop()
        
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
            lane_number = 1
            for hst, port in zip(self.hosts, self.ports):
                outfile.write(','.join([str(lane_number), hst, str(port)]) + '\n')

    def set_address(self, idx, address):
        ip, port = address.split(':')
        self.ports[idx] = int(port)
        self.hosts[idx] = ip

    def all_connected(self, report=False):
        out = True
        for i in range(self.n_lanes):
            try:
                out = out and self.comms[i].is_connected()
            except Exception as e:
                self._vprint(repr(e))
                self._vprint("Continuing.")
            else:
                if report:
                    self._vprint(f"Connection from {self.hosts[i]}:{self.ports[i]} established.")
        return out

    def set_up_comms(self, i):
        self._vprint(f"Setting up connection {i + 1} to {self.hosts[i]} on port {self.ports[i]}.")
        out = TimerConnection(self.hosts[i], self.ports[i], self.q, self.verbose, i)
        self._vprint(f"{i + 1} Connected.")

        return out

    def reset_sockets(self):
        for tc in self.comms:
            tc.reset_socket()

    def close_conn_window(self):
        self.connection_window_open = False

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
            rb[i] = tk.Entry(popup, textvariable=port_text[i])
            rb[i].pack()

        tk.Button(popup, text="Reset", command=self.reset_sockets).pack()
        tk.Button(popup, text="Exit", command=self.close_conn_window).pack()
        last_time = time.clock_gettime(time.CLOCK_MONOTONIC) - 10.0
        loop_count = 5

        popup.lift()

        if self.all_connected():
            for i in range(self.n_lanes):
                rb[i].config(**{'fg': '#18ff00', 'bg': '#404040'})

        while self.connection_window_open:
            if self.all_connected():
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
                db.config(text=f"Re-attempting in {1 - loop_count} second.")
                popup.update_idletasks()
                popup.update()
                time.sleep(0.01)
                continue
            else:
                loop_count = 0

            has_focus = self.parent.focus_get()
            i = 0
            while i < self.n_lanes:
                while self.entry_widgets[i] == has_focus:
                    db.config(text=f"Re-attempting connection after editing.")
                    i = -1
                    time.sleep(0.05)
                    popup.update_idletasks()
                    popup.update()
                    has_focus = self.parent.focus_get()
                i += 1
            self.parent.focus_set()
            for i in range(self.n_lanes):
                self.hosts[i] = port_text[i].get().split(':')[0]
                try:
                    self.ports[i] = int(port_text[i].get().split(':')[-1])
                except ValueError:
                    pass
            for i in range(self.n_lanes):
                if not self.comms[i].is_connected():
                    rb[i].config(**{'fg': '#000000', 'bg': '#ffffff'})
                    db.config(text="Attempting to connect to {}:{}".format(
                        self.hosts[i], self.ports[i]))
                    popup.update()
                    self._vprint("Attempting to connect to {}:{}".format(
                        self.hosts[i], self.ports[i]))
                    try:
                        self.comms[i].connect()
                    except Exception as e:
                        rb[i].config(**{'fg': '#ff0000', 'bg': '#ffffff'})
                    else:
                        self._vprint("Connection from {}:{} established.".format(
                            self.hosts[i], self.ports[i]))
                        rb[i].config(**{'fg': '#18ff00', 'bg': '#404040'})
                        time.sleep(0.1)
            if not self.all_connected():
                self._vprint("Waiting 1 second and re-attempting connection.")
                db.config(text="""Waiting 1 second1 and re-attempting connection.""")
                last_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            else:
                if autoclose:
                    self.connection_window_open = False
            popup.update_idletasks()
            popup.update()
        popup.destroy()

    def send_reset_to_track(self, accept=False):
        self._vprint("Sending Reset to the Track")
        self.comms[self.reset_lane].send_reset()
