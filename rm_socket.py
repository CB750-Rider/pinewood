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
import datetime
import numpy as np

message_color = "\033[94m"
normal_color = "\033[0m"
lane_colors = ["#1167e8", "#e51b00", "#e5e200", "#7fd23c"]

small_font = ("Serif", 16)
med_font = ("Times", 21)
large_font = ("Times", 25)

# Pipe messages for controlling _TimerSocket
_conf_msg = "confirmed".encode('utf-8')
_shutdown_msg = "shutdown".encode('utf-8')
_connect_msg = "connect".encode('utf-8')
_check_connection_msg = "check_conn".encode('utf-8')
_socket_reset_msg = "reset_socket".encode('utf-8')
_connection_success_msg = "successful_conn".encode('utf-8')
_connectien_dropped_msg = "dropped_conn".encode('utf-8')
_test_on_msg = "test_on".encode('utf-8')
_test_off_msg = "test_off".encode('utf-8')

# Socket messages for controlling the timers
_test_msg = "<test>".encode('utf-8')
_reset_msg = "<reset>".encode('utf-8')
_resend_data_msg = "<resend>".encode('utf-8')
_get_cal = "<get_Cal>".encode('utf-8')
counter_messages = [_test_msg, _reset_msg, _resend_data_msg, _get_cal]

# Used to indicate no data on the socket
_null_data = "".encode('utf-8')

_rb_connected = {'fg': '#000000', 'bg': '#ffffff'}
_rb_flash = {'fg': '#18ff00', 'bg': '#404040'}
_rb_disconnected = {'fg': '#ff0000', 'bg': '#ffffff'}


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
                 index: int = -1,
                 test_active: bool = False):
        self.address = address
        self.port = port
        self.pipe = pipe
        self.verbose = verbose
        self.index = index
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.queue = queue
        self.test_active = test_active
        try:
            self.connect()
        except Exception as e:
            # self._vprint(repr(e))
            pass
        self.running = True
        self.connection_active = False
        self.last_check = datetime.datetime.now()

    def _vprint(self, msg):
        if self.verbose:
            print(f"{message_color}rm_socket._TimerSocket: {msg} {normal_color}")

    def set_test_active(self, state: bool):
        self.test_active = state

    def reset_socket(self):
        """ Closes and resets the socket. """
        self._close_socket()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.connect()

    def _close_socket(self):

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()

    def _shutdown(self):
        self._vprint(f"Shutting down process {self.index + 1}.")
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
        elif msg == _test_on_msg:
            self.set_test_active(True)
            self.pipe.send(_test_on_msg)
        elif msg == _test_off_msg:
            self.set_test_active(False)
            self.pipe.send(_test_off_msg)
        elif msg in counter_messages:
            if n_writer < 1:
                raise ConnectionError("Unable to send message to socket")
            try:
                self.socket.sendall(msg)
                self.pipe.send(_conf_msg)
            except Exception as e:
                self.pipe.send(repr(e).encode('utf-8'))
        elif "<cal ".encode('utf-8') in msg:
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
            # out = socket_data
            # while len(socket_data) > 0:
            #    socket_data = self.socket.recv(64)
            #    out += socket_data

        except ConnectionResetError:
            return _null_data
        return socket_data

    def check_connection(self):
        if datetime.datetime.now() - self.last_check < datetime.timedelta(seconds=4.0):
            return self.connection_active

        self.last_check = datetime.datetime.now()
        rdr, wrtr, _ = select.select([self.socket, ],
                                       [self.socket, ],
                                       [self.socket, ],
                                       0.25)
        if len(wrtr) == 1:
            try:
                if self.test_active:
                    self.socket.sendall(_test_msg)
                time.sleep(0.1)

            except Exception as e:
                self._vprint(f"!!Error line 195 {repr(e)} found with socket {self.index + 1}!!")
                self.connection_active = False
                try:
                    self.reset_socket()
                except Exception:
                    pass
                return False

        if len(rdr) == 1:
            try:
                rv = self.get_data_from_socket()
                self.connection_active = True
                return True
            except Exception as e:
                self._vprint(f"!!Error line 205 {repr(e)} found with socket {self.index + 1}!!")
                self.connection_active = False
                return False

    def connect(self):
        self.socket.connect((self.address, self.port))
        self.socket.setblocking(False)

    def send(self, msg: bytes):
        " Sends data to the socket. "
        self.socket.sendall(msg)

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
                        self._vprint(f"{self.index + 1} Sent {data.decode('utf-8')}")
                except Exception as e:
                    self.pipe.send(('line 231: ' + repr(e)).encode('utf-8'))
                    try:
                        self.connect()
                    except:
                        pass
                    else:
                        self.pipe.send(_connection_success_msg)
                    # Manage error message density by checking every second.
                    time.sleep(1.0)

            self._check_pipe(len(wrtr))

            if len(err) > 0:
                self._vprint(f"An error was found with the socket. Resetting.")
                time.sleep(5.0)
                self.reset_socket()

            self.check_connection()


def _create_connection(address, port, pipe, queue, verbose, index, tst_state):
    """
    Starts up the connection and keeps it going in a loop until
    it closes
    :return:
    """

    connection = _TimerSocket(address, port, pipe, queue, verbose, index, tst_state)

    connection.run()


class TimerConnection:
    """ This is a silly little intermediary that spawns a new process
    to handle the socket connection asynchronously. """

    def __init__(self,
                 address: str,
                 port: int,
                 queue: Queue,
                 parent,
                 verbose: bool = False,
                 index: int = -1,
                 test_active: bool = False):
        """
        Sets up a separate process for handling communications with the
        timer. Uses a Pipe to send commands to that process and to get
        data from the process.
        """
        self.parent = parent
        self.pipe, child_pipe = Pipe(duplex=True)
        self.p = Process(target=_create_connection,
                         args=(address, port, child_pipe,
                               queue, verbose, index, test_active))
        self.p.start()
        self.test_active = test_active
        self.index = index
        self.address = address
        self.port = port
        self.verbose = verbose
        self.index = index
        self.connected = self.is_connected(quick=False)
        self.queue = queue
        self.cal_constant = self.load_cal()

    def load_cal(self):
        fname = f"cal_constant_{self.index}"
        try:
            with open(fname) as infile:
                cc = infile.readline()
            return int(cc)
        except: 
            return 0
    
    def set_cal_constant(self, cc):
        self.cal_constant = cc
        self.save_cal()
        
    def save_cal(self):
        fname = f"cal_constant_{self.index}"
        msg = str(self.cal_constant)
        try:
            with open(fname, "w") as outfile:
                outfile.writelines(msg)
        except Exception as e:
            pass
            
    def _vprint(self, msg):
        if self.verbose:
            print(f"{message_color}rm_socket.TimerConnection: {msg} {normal_color}")

    def set_test_active(self, state: bool):
        if state:
            self.pipe.send(_test_on_msg)
        else:
            self.pipe.send(_test_off_msg)
        rtn_msg = self.pipe.recv()
        if rtn_msg == _test_on_msg:
            self.test_active = True
        elif rtn_msg == _test_off_msg:
            self.test_active = False
        else:
            self._vprint("Unable to successfully set the test state.")
        return self.test_active

    def send_calibration(self, cal: int):
        msg = f"<cal {cal} >".encode('utf-8')
        self.pipe.send(msg)
        #self.save_cal()

    def shutdown(self):
        self.pipe.send(_shutdown_msg)
        self._await_conf()
        self.connected = False
        self._vprint(
            f"{message_color}rm_socket.TimerConneciton: Waiting for connection {self.index} to close.{normal_color}")
        self.p.join()
        self.p.close()
        self.save_cal()

    def _await_conf(self):
        msg = self.pipe.recv()
        if msg == _conf_msg:
            return True
        else:
            return False

    def is_connected(self, quick=True):
        if quick:
            while self.pipe.poll():
                try:
                    msg = self.pipe.recv()
                    if msg == _connection_success_msg:
                        self.connected = True
                    elif b"Error" in msg:
                        self.connected = False
                    self._vprint(msg)
                except:
                    break
            return self.connected
        else:
            try:
                self.pipe.send(_check_connection_msg)
                self.connected = self._await_conf()
            except BrokenPipeError:
                self.connected = False
        return self.connected

    def reset_socket(self):
        try:
            self.pipe.send(_socket_reset_msg)
        except BrokenPipeError:
            pass

    def send_reset(self):
        self.pipe.send(_reset_msg)

    def request_counts(self):
        self.pipe.send(_resend_data_msg)

    def send_test(self):
        if self.test_active:
            self.pipe.send(_test_msg)
        else:
            print("Not sending tests.")

    def new_connection(self, address, port):
        self.shutdown()
        self.pipe.close()

        self.address = address
        self.port = port

        self.pipe, child_pipe = Pipe(duplex=True)
        self.p = Process(target=_create_connection,
                         args=(address, port, child_pipe,
                               self.queue, self.verbose, self.index,
                               self.test_active))
        self.p.start()
        self.connected = self.is_connected(quick=False)

    def get_average_count(self):
        timer_comms = self.parent
        rm_gui = timer_comms.parent
        event = rm_gui.event
        return event.get_lane_average_counts(self.index)

    def get_cal(self):
        return self.cal_constant

    def suggest_cal(self):
        timer_comms = self.parent
        rm_gui = timer_comms.parent
        event = rm_gui.event
        my_avg = event.get_lane_average_counts(self.index)
        my_dev = event.get_lane_average_deviation(self.index)
        return my_avg, my_dev


class TimerComs:

    def __init__(self,
                 parent,
                 addresses: List[str] = None,
                 hosts_file: str = None,
                 n_lanes: int = 4,
                 reset_lane: int = 0,
                 verbose: bool = False):
        if addresses is None and hosts_file is None:
            raise ValueError("You must provide a list of hosts, or a hosts file when creating sockets.")

        self.q = Queue()
        self.timer_window = None
        self.socket_frame = None
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

    def set_socket_frame(self, frame):
        self.socket_frame = frame

    def window_update(self):
        if self.connection_window_open:
            self.connect_to_track_hosts()

    def shutdown(self):
        for i in range(self.n_lanes):
            try:
                self.comms[i].shutdown()
            except Exception as e:
                self._vprint(f"Error {repr(e)} encountered and ignored when attempting to shutdown.")
                pass

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
        out = TimerConnection(self.hosts[i], self.ports[i], self.q, self, self.verbose, i)
        self._vprint(f"{i + 1} Connected.")

        return out

    def reset_sockets(self):
        for tc in self.comms:
            tc.reset_socket()

    def close_conn_window(self):
        self.connection_window_open = False

    def run(self):
        self.connection_window_open = True
        self.connect_to_track_hosts()

    def stop(self):
        self.connection_window_open = False

    def connect_to_track_hosts(self, reset=False):
        self.connection_window_open = True

        if reset:
            self.reset_sockets()

        if self.socket_frame is None:
            popup = tk.Toplevel(self.parent.window)
            popup.wm_title("Connection To Track")
            popup.protocol("WM_DELETE_WINDOW", self.close_conn_window)
        else:
            popup = self.socket_frame

        self.timer_window = TimerWindow(popup, self, lane_colors)

        while self.connection_window_open:
            self.timer_window.update()

        if self.socket_frame is None:
            popup.destroy()

    def send_reset_to_track(self):
        self._vprint("Sending Reset to the Track")
        self.comms[self.reset_lane].send_reset()


class _TimerFrame:

    def __init__(self,
                 outer_frame: tk.Frame,
                 timer: TimerConnection,
                 host: str,
                 port: int,
                 color: str,
                 idx: int):

        self.outer_frame = outer_frame
        self.frame = tk.Frame(outer_frame, bg=color)
        self.frame.pack(fill=tk.BOTH, expand=1)
        self.color = color
        self.idx = idx

        self.timer = timer
        self.host = host
        self.port = port

        self.port_text = tk.StringVar()
        self.port_text.set(f"{host}:{port}")
        self.tst_btn_text = tk.StringVar()
        self.tst_btn_text.set("Test Button")
        self.cal_text = tk.StringVar()
        self.cal_text.set("0")
        self.left_cal_text2 = tk.StringVar()
        self.left_cal_text2.set("Lane average count = 0.0")
        self.left_cal_text = tk.StringVar()
        self.left_cal_text.set("Lane Calibration (current/suggested) = 0 / 0")

        self._left_section()

        self._middle_section()

        self._right_section()

        self.toggle_testing()
    
    def set_left_cal_text(self):
        cal = self.timer.get_cal()
        my_avg, sgst_cal = self.timer.suggest_cal()
        sgst_cal = np.round(sgst_cal)
        text=f"Calibration (current/suggested) = {cal} / {sgst_cal}"
        self.left_cal_text.set(text)
        text=f"Average Count = {my_avg}"
        self.left_cal_text2.set(text)
        #self.cal_text.set(f"{cal}")
        

    def _left_section(self):
        self.left_frame = tk.Frame(self.frame, bg=self.color)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        label = tk.Label(self.left_frame, text=f"Lane {self.idx + 1}", font=large_font, bg=self.color)
        label.pack(pady=7)

        tk.Label(self.left_frame, textvariable=self.left_cal_text2,
                 font=small_font, bg=self.color).pack(pady=2)


        self.set_left_cal_text()
        tk.Label(self.left_frame, textvariable=self.left_cal_text, font=small_font, 
                 bg=self.color).pack(pady=2)
        
        self.status_text = tk.StringVar()
        self.status_label = tk.Label(self.left_frame, textvariable=self.status_text, bg=self.color,
                                     font=med_font)
        self.status_label.pack()
        if self.timer.connected:
            self.status_text.set(f"Connected")
        else:
            self.status_text.set(f"Disconnected")

        self.testing_button = tk.Button(self.left_frame, textvariable=self.tst_btn_text, width=20,
                                        command=self.toggle_testing)
        self.testing_button.pack(pady=5)
        tst_frame = tk.Frame(self.left_frame, bg=self.color)
        tst_frame.pack()
        tk.Label(tst_frame, text="Testing Status", bg=self.color).pack(side=tk.LEFT)
        self.tst_canvas = tk.Canvas(tst_frame, width=24, height=24, bg=self.color)
        self.tst_canvas.pack(side=tk.LEFT)
        self.tst_indicator = self.tst_canvas.create_oval(8, 7, 20, 20)

    def _middle_section(self):
        self.middle_frame = tk.Frame(self.frame, bg=self.color)
        self.middle_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True)
        label = tk.Label(self.middle_frame, text=f"Set Timer IPv4:Port", bg=self.color, font=med_font)
        label.pack(pady=5)
        self.rb = tk.Entry(self.middle_frame, textvariable=self.port_text)
        self.rb.pack(pady=10)

        label = tk.Label(self.middle_frame, text=f"Socket Controls", font=small_font, bg=self.color)
        label.pack(pady=5)
        btn = tk.Button(self.middle_frame, text="Connect", command=self.update_connection)
        btn.pack(pady=5)
        btn = tk.Button(self.middle_frame, text="Reset Connection", command=self.timer.reset_socket)
        btn.pack(pady=5)


    def _right_section(self):
        self.right_frame = tk.Frame(self.frame, bg=self.color)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(self.right_frame, text="Timer Commands", font=large_font, bg=self.color).pack(pady=5)

        tk.Button(self.right_frame, text="Reset Timer", command=self.timer.send_reset).pack(pady=10)
        tk.Button(self.right_frame, text="Request Count", command=self.timer.request_counts).pack(pady=10)
        # tk.Button(self.right_frame, text="Stop Timer", command=self.timer.send_stop).pack(pady=10)
        tk.Button(self.right_frame, text="Update Cal", command=self.send_cal).pack(pady=10)
        self.cal_etry = tk.Entry(self.right_frame,
                                 textvariable=self.cal_text)
        self.cal_etry.pack()

    def send_cal(self):
        cal_txt = self.cal_text.get()
        try:
            cal = int(cal_txt)
        except ValueError:
            cal = 0
        self.timer.send_calibration(cal)

    def toggle_testing(self):
        """ Attempt to set the state, and get the result. """
        cur_state = self.timer.test_active
        tst_state = self.timer.set_test_active(not cur_state)
        if tst_state:  # Testing on
            self.tst_btn_text.set("Connection Test Off")
            self.tst_canvas.itemconfig(self.tst_indicator, fill='#00e417')
        else:
            self.tst_btn_text.set("Connection Test On")
            self.tst_canvas.itemconfig(self.tst_indicator, fill='#001c03')

    def update(self):
        self.check_status()

    def check_status(self):
        if self.timer.is_connected(quick=True):
            self.set_left_cal_text()
            self.rb.config(**_rb_connected)
            self.status_text.set(f"Connected")
            self.status_label.config(bg=self.color, fg='black')
        else:
            self.rb.config(**_rb_disconnected)
            self.status_text.set(f"Disconnected")
            self.status_label.config(bg='black', fg='red')

    def update_connection(self):
        txt = self.port_text.get()
        self.host = txt.split(':')[0]
        self.port = int(txt.split(':')[-1])
        self.timer.new_connection(self.host, self.port)


class MainWindow:

    def __init__(self, outer_frame):
        self.outer_frame = outer_frame
        self.active = False
        self.child_frames = []

    def run(self):
        self.active = True

    def stop(self):
        if self.active:
            self.forget()
        self.active = False

    def update(self):
        if self.active:
            self._update()

    def forget(self):
        self.outer_frame.forget()
        self._forget()

    def pack(self):
        self.outer_frame.pack(fill=tk.BOTH, expand=1)
        self._pack()

    def tkraise(self):
        self.outer_frame.tkraise()
        self._tkraise()

    def _tkraise(self):
        raise NotImplementedError("""Each derived class must describe 
        what to do when calling tkraise.""")

    def _update(self):
        raise NotImplementedError("""Each derived class must describe what
        to do when updating.""")

    def _forget(self):
        raise NotImplementedError("""Each derived class must describe what
        to do when forget is called.""")

    def _pack(self):
        raise NotImplementedError("""Each derived class must describe 
        what to do when packing.""")


class TimerWindow(MainWindow):

    def __init__(self,
                 outer_frame: tk.Frame,
                 timer_coms: TimerComs,
                 lane_colors_: List[str],
                 verbose: bool = False
                 ):

        super().__init__(outer_frame)

        self.lane_colors = lane_colors_
        self.outer_frame = outer_frame
        self.timer_coms = timer_coms
        self.verbose = verbose

        self.timer_frame = []
        self.db = tk.Label(outer_frame, width=45)
        self.db.pack()

        for i in range(timer_coms.n_lanes):
            self.timer_frame.append(_TimerFrame(outer_frame,
                                                timer_coms.comms[i],
                                                timer_coms.hosts[i],
                                                timer_coms.ports[i],
                                                lane_colors_[i],
                                                i))

        self.bottom_frame = tk.Frame(outer_frame).pack()
        tk.Button(self.bottom_frame, text="Reset All", command=timer_coms.reset_sockets).pack(side=tk.LEFT)
        tk.Button(self.bottom_frame, text="Exit", command=timer_coms.close_conn_window).pack(side=tk.RIGHT)
        self.stats_text = tk.StringVar()
        self.stats_text.set("")
        tk.Label(self.bottom_frame, textvariable=self.stats_text).pack(side=tk.LEFT)
        self.last_time = time.clock_gettime(time.CLOCK_MONOTONIC) - 10.0

        if timer_coms.all_connected():
            for i in range(timer_coms.n_lanes):
                self.timer_frame[i].rb.config(**{'fg': '#18ff00', 'bg': '#404040'})

    def _set_stats_text(self):
        rm_gui = self.timer_coms.parent
        event = rm_gui.event
        cr = rm_gui.clock_rate
        mean, std = event.get_average_counts()
        msg = f"Count standard deviation = {std}. Time standard deviation = {std/cr}."
        self.stats_text.set(msg)
        
    def _vprint(self, msg):
        if self.verbose:
            print(f"{message_color}rm_socket.TimerWindow: {msg} {normal_color}")

    def _update(self):
        self._set_stats_text()
        tcs = self.timer_coms
        if tcs.all_connected():
            self.db.config(text='Connected. Press Reset to drop and reconnect.')
        # time_diff = time.clock_gettime(time.CLOCK_MONOTONIC) - self.last_time

        for i in range(tcs.n_lanes):
            tf = self.timer_frame[i]
            tf.update()
            tc = tcs.comms[i]
            if not tc.is_connected():
                tf.rb.config(**_rb_connected)
                tf.timer.reset_socket()
                self.db.config(text=f"Attempting to connect to {tf.host}:{tf.port}")

                self._vprint(f"Attempting to connect to {tf.host}:{tf.port}")

                if tc.is_connected(quick=False):
                    self._vprint(f"Connection from {tf.host}:{tf.port} established.")
                    tf.rb.config(**_rb_flash)
                    tf.send_cal()
                else:
                    tf.rb.config(**_rb_disconnected)
                    time.sleep(0.1)
        if not tcs.all_connected():
            self._vprint("Waiting 1 second and re-attempting connection.")
            self.db.config(text="""Waiting 1 second1 and re-attempting connection.""")
            self.last_time = time.clock_gettime(time.CLOCK_MONOTONIC)

    def _pack(self):
        return

    def _forget(self):
        return

    def _tkraise(self):
        return
