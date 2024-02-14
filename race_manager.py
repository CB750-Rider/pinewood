"""
rm_gui.py

author: Dr. Lee Burchett

An application for creating a gui that managers of a Pinewood Derby can use
to set up and run a pinewood derby race.

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
import queue
import numpy as np
import tkinter as tk
from tkinter import filedialog, IntVar
from race_event import Event, get_placements
import argparse
from rm_socket import TimerComs, normal_color, TimerWindow, MainWindow, _test_msg
from results import ResultsWindow
import registration
from copy import deepcopy
from tkinter import TclError

# Strings to set terminal text color.
green = "\033[92m"
yellow = "\033[93m"

""" Set up Argparse """
description = "A Graphical Interface for managing Pinewood Derby Races"

parser = argparse.ArgumentParser(description=description)
parser.add_argument('--hosts_file', help='A file with the ip and port addresses of the lane timers (hosts).',
                    default='lane_hosts_LOCAL.csv')
parser.add_argument('--event_file', help='A file with the event plan listed.',
                    default='demo_race.yaml')
parser.add_argument('--log_file', help='The name of a file to save race times to.',
                    default='log_file.yaml')
parser.add_argument('--verbose', action='store_true')

# dimensions are y = row x = column rid[y][x]
widths = {"Times Column": 430,
          "Race Column": 350,
          "Top Spacer": 30}
race_ready = [False, False, False, False]  # "Yellow LED"
race_complete = [True, True, True, True]  # "Red LED"
race_running = [False, False, False, False]  # "Green LED"
small_font = ("Serif", 16)
med_font = ("Times", 21)
large_font = ("Times", 25)
program_running = True
race_needs_written = False
block_loading_previous_times = False
clock_rate = 4000.0

# GUI ELEMENTS
""" These classes are for the different GUI portions. They are in a 
hierarchical order, more or less. The later classes contain instances
of the earlier classes. """


class RaceSelector:

    def __init__(self,
                 outer_frame: tk.Frame,
                 parent):
        self.parent = parent
        self.event = parent.event
        rt = tk.Frame(outer_frame)
        self.base_frame = rt
        w = tk.Label(rt, text="Race log #", font=small_font)
        w.pack(side=tk.LEFT, fill=tk.X, expand=1)

        if self.event.current_race is None:
            self.option_list = [str(self.event.current_race_log_idx), ]
            self.event.generate_race_plan()
            if self.event.current_race is None:
                tk.messagebox.showerror("Unusable Plan Error",
                                        """The race plan was not sufficient to create even one race.
                Please create a usable plan and re-run. 
                See demo_race.yaml for an example.""")
                raise ValueError("Unusable race plan.")
            else:
                result = tk.messagebox.askquestion('Race Plan Generated',
                                                   'Would you like to open the planning dialog so you can save/edit the plan?')
                if result == 'yes':
                    parent.edit_race_plan()
            race = self.event.current_race
        else:
            race = self.event.current_race

        if len(race.race_number):
            self.option_list = [str(x) for x in race.race_number]
            self.option_list.append(self.event.current_race_log_idx)
        else:
            self.option_list = [self.str(self.event.current_race_idx,
                                         self.event.current_race_log_idx), ]
        if len(self.option_list) == 0:
            self.option_list = ["0", ]

        self.current_race_str = tk.StringVar(rt)
        if race.accepted_result_idx >= 0:
            idx = race.accepted_result_idx
            self.option_list[idx] += ' < ACC'
            self.active_race_log_idx = race.race_number[idx]
            self.current_race_str.set(self.option_list[idx])
        else:
            self.current_race_str.set(self.option_list[-1])
            self.active_race_log_idx = self.event.current_race_log_idx
        self.current_race_str.trace("w", self.load_previous_times)
        self.selector_frame = tk.Frame(rt)
        race_selector = tk.OptionMenu(
            self.selector_frame, self.current_race_str,
            *self.option_list, command=self.on_selected)
        race_selector.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.selector_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.race_menu = race_selector
        # TODO Should the send_reset_to_track accept?
        b = tk.Button(rt, text="add/reset", command=send_reset_to_track,
                      font=small_font)
        b.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.add_reset_button = b
        rt.pack(fill=tk.X)

    def str(self, ri, rln):
        return "{}:{}".format(ri + 1, rln)

    def update(self,
               show_accepted_race=True,
               race_idx=-1,
               race_log_idx=-1):
        if race_idx < 0:
            race_idx = self.event.current_race_idx
        if race_log_idx < 0:
            race_log_idx = self.event.current_race_log_idx

        # Grab the embeded menu and change the choices
        race = self.event.races[race_idx]
        self.active_race_log_idx = race_log_idx

        for child in self.selector_frame.winfo_children():
            child.destroy()
        self.current_race_str = tk.StringVar(self.base_frame)

        # Create a new list
        if len(race.race_number):
            self.option_list = [self.str(race_idx, x) for x in race.race_number]
            self.option_list.append(
                self.str(race_idx, self.event.current_race_log_idx))
        else:
            self.option_list = [
                self.str(race_idx, self.event.current_race_log_idx), ]

        if race.accepted_result_idx >= 0:
            idx = race.accepted_result_idx
            self.option_list[idx] += ' < ACC'
            if show_accepted_race:
                self.current_race_str.set(self.option_list[idx])
            else:
                self.current_race_str.set(
                    self.str(race_idx, self.active_race_log_idx))
        else:
            self.current_race_str.set(
                self.str(race_idx, self.active_race_log_idx))

        self.race_menu = tk.OptionMenu(self.selector_frame,
                                       self.current_race_str,
                                       *self.option_list,
                                       command=self.on_selected)
        self.race_menu.pack(fill=tk.BOTH, expand=1)

    def on_selected(self, *args):
        global race_needs_written, race_running, rm_gui
        self.active_race_log_idx = self.get_race_idx_from_selector()
        if race_needs_written:
            record_race_results(accept=False)
            race_needs_written = False
        show_results()
        race_running = [False] * rm_gui.n_lanes
        self.parent.update_race_display(new_race=False)

    def get_race_idx_from_selector(self):
        s1 = self.current_race_str.get().split(':')[-1]
        s2 = s1.split(' ')[0]
        return int(s2)

    def load_previous_times(self, *args):
        global race_running, block_loading_previous_times
        if any(race_running):  # Do nothing if we are running
            print("Previous times will not be loaded while the race is running.")
            return
        if block_loading_previous_times:
            return

        # Record times, just in case
        record_race_results()

        # Figure out which race we are on
        cidx = int(self.current_race_str.get().split(' ')[0])
        print("Looking for {} in {}.".format(cidx, self.event.current_race.race_number))
        if len(self.event.current_race.race_number) > 0:
            idx = 0
            for ii, ridx in enumerate(self.event.current_race.race_number):
                idx = ii
                if cidx == ridx:
                    break
            # Now idx is appropriately set. Send a warning if no match was found
            if cidx != self.event.current_race.race_number[idx]:
                if idx is not len(self.event.current_race.race_number):
                    print("Warning no race index was found!")
                counts = [0, 0, 0, 0]  # A default
                self.active_race_log_idx = self.event.current_race_log_idx
            else:
                counts = self.event.current_race.counts[idx]
                self.active_race_log_idx = self.event.current_race.race_number[idx]
        else:
            counts = [0, 0, 0, 0]
            self.active_race_log_idx = self.event.current_race_log_idx

        print(counts)
        show_results()


class TrackStatusIndicator:
    ready_to_race = {"text": "Ready to Race",
                     "bg": "#fff600",
                     "fg": "#000000",
                     "borderwidth": 3,
                     "relief": "raised",
                     "font": med_font}
    not_ready = {"text": "Not Ready",
                 "fg": "#565726",
                 "bg": "#7e7400",
                 "borderwidth": 3,
                 "relief": "sunken",
                 "font": med_font}
    race_is_running = {"text": "Race Running",
                       "fg": "#000000",
                       "bg": "#00ff2a",
                       "borderwidth": 3,
                       "relief": "raised",
                       "font": med_font}
    not_running = {"text": "Not Running",
                   "fg": "#21ae39",
                   "bg": "#027415",
                   "borderwidth": 3,
                   "relief": "sunken",
                   "font": med_font}
    race_complete = {"text": "Race Complete",
                     "fg": "#000000",
                     "bg": "#ff0000",
                     "borderwidth": 3,
                     "relief": "raised",
                     "font": med_font}
    not_complete = {"text": "Not Complete",
                    "fg": "#b50d0d",
                    "bg": "#660101",
                    "borderwidth": 3,
                    "relief": "sunken",
                    "font": med_font}

    def __init__(self,
                 top: tk.Frame,
                 background: str,
                 idx: int,
                 parent):
        global race_ready, race_running
        self.stop_count = 0
        self.parent = parent  # Parent is RaceTimes
        self.idx = idx
        self.background = background
        self.top = top
        si = tk.Frame(top, bg=background)
        self.frame = si
        print("Updating the track status")
        if race_ready[idx]:
            self.hide_stop()
            self.ready = tk.Label(si, **self.ready_to_race)
            self.ready.pack(fill=tk.X, side=tk.TOP, expand=1)
            self.running = tk.Label(si, **self.not_running)
            self.running.pack(fill=tk.X, side=tk.TOP, expand=1)
            self.complete = tk.Label(si, **self.not_complete)
            self.complete.pack(fill=tk.X, side=tk.TOP, expand=1)
        else:
            self.ready = tk.Label(si, **self.not_ready)
            self.ready.pack(fill=tk.X, side=tk.TOP, expand=1)
            if race_running[idx]:
                self.running = tk.Label(si, **self.race_is_running)
                self.running.pack(fill=tk.X, side=tk.TOP, expand=1)
                self.complete = tk.Label(si, **self.not_complete)
                self.complete.pack(fill=tk.X, side=tk.TOP, expand=1)
            else:
                self.running = tk.Label(si, **self.not_running)
                self.running.pack(fill=tk.X, side=tk.TOP, expand=1)
                self.complete = tk.Label(si, **self.race_complete)
                self.complete.pack(fill=tk.X, side=tk.TOP, expand=1)

    def update(self, new_race=True):
        global race_ready, race_running
        idx = self.idx
        parent = self.parent
        if race_ready[idx]:
            self.ready.config(**self.ready_to_race)
            self.running.config(**self.not_running)
            self.complete.config(**self.not_complete)
            if new_race:
                parent.reset_race_time_display()
                parent.reset_placement_display()
            else:
                parent.update_race_time_display()
                parent.update_placement_display()
        else:
            self.ready.config(**self.not_ready)
            if race_running[idx]:
                parent.parent.parent.controls_row.disable_navigation()
                self.running.config(**self.race_is_running)
                self.complete.config(**self.not_complete)
                if new_race:
                    parent.reset_race_time_display()
                    parent.reset_placement_display()
                else:
                    parent.update_race_time_display()
                    parent.update_placement_display()
            else:
                self.running.config(**self.not_running)
                self.complete.config(**self.race_complete)
                parent.update_race_time_display()
                parent.update_placement_display()


class RaceTimes:
    race_time_default = {"text": "0.0", "fg": "gray"}
    placement_default = {"text": "Ready", "fg": "gray"}
    placement_settings = [{"text": "1st", "fg": "#ff9600", "bg": "#000000"},
                          {"text": "2nd", "fg": "#000000"},
                          {"text": "3rd", "fg": "#000000"},
                          {"text": "4th", "fg": "#000000"}]

    def __init__(self,
                 top: tk.Frame,
                 idx: int,
                 parent):
        global large_font
        self.parent = parent  # Parent is times column
        self.idx = idx
        self.top = top
        colors = self.parent.parent.parent.lane_colors
        self.colors = colors

        rt = tk.Frame(top)
        self.frame = rt
        lane_label_box = tk.Frame(rt, bg=colors[idx])
        w = tk.Label(lane_label_box, text="Lane {0}".format(idx + 1),
                     bg=colors[idx], font=large_font)
        w.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        self.sckt_conn_text = tk.StringVar()
        self.sckt_conn_text.set("Not Connected")
        self.sckt_curr_conn_status = False
        self.sckt_conn_status_label = tk.Label(lane_label_box,
                                               textvariable=self.sckt_conn_text,
                                               bg='black', fg='red',
                                               font=med_font)
        lane_label_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.sckt_conn_status_label.pack(side=tk.BOTTOM)
        self.status_indicator = TrackStatusIndicator(rt, colors[idx], idx, self)
        self.status_indicator.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.placement = -1
        res_frm = tk.Frame(rt)
        if parent.event.current_race.times:  # If times were posted
            current_race = parent.event.current_race
            if current_race.accepted_result_idx >= 0:  # show the accepted race
                times = current_race.times[current_race.accepted_result_idx]
                self.race_time_display = tk.Label(res_frm, bg=colors[idx],
                                                  font=large_font, fg="#000000", text="{0:.4f}".format(times[idx]))
            else:
                self.race_time_display = tk.Label(res_frm, bg=colors[idx], font=large_font,
                                                  **self.race_time_default)
        else:
            self.race_time_display = tk.Label(res_frm, bg=colors[idx], font=large_font,
                                              **self.race_time_default)
        self.race_time_display.pack(fill=tk.BOTH, expand=1)
        self.placement_display = tk.Label(res_frm, bg=colors[idx], font=large_font,
                                          **self.placement_default)
        self.placement_display.pack(fill=tk.BOTH, expand=1)
        res_frm.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        rt.pack(fill=tk.BOTH, expand=1)

    def reset_race_time_display(self):
        self.race_time_display.config(self.race_time_default)

    def update_race_time_display(self):
        global rm_gui
        race_idx = rm_gui.times_column.race_selector.get_race_idx_from_selector()
        updated_counts = rm_gui.event.get_counts_for_race(race_idx)
        if updated_counts[self.idx]:
            final_time = np.round(updated_counts[self.idx] / self.parent.parent.parent.clock_rate, 4)
            self.race_time_display.config(text="{0:.4f}".format(final_time), fg='#000000')
            return True
        else:
            self.race_time_display.config(self.race_time_default)
            self.reset_placement_display()
            return False

    def update_placement_display(self):
        global placement_displays
        rm_gui.times_column.race_selector.get_race_idx_from_selector()
        if self.placement >= 0:
            self.placement_display.config({"bg": self.colors[self.idx]})
            self.placement_display.config(self.placement_settings[self.placement])
        else:
            self.placement_display.config({"bg": self.colors[self.idx]})
            self.placement_display.config(self.placement_default)

    def reset_placement_display(self):
        global placement_displays
        self.placement_display.config({"bg": self.colors[self.idx]})
        self.placement_display.config(self.placement_default)

    def update_socket_status(self, is_connected: bool):
        if is_connected:
            if self.sckt_curr_conn_status:
                return
            else:
                self.sckt_conn_text.set("Connected")
                self.sckt_conn_status_label.configure(
                    fg='black', bg=self.colors[self.idx])
        else:
            if self.sckt_curr_conn_status:
                self.sckt_conn_text.set("Not Connected")
                self.sckt_conn_status_label.configure(
                    fg='red', bg='black'
                )
        self.sckt_curr_conn_status = is_connected


class TimesColumn:

    def __init__(self,
                 parent,
                 parent_widget):
        global widths, large_font
        self.parent = parent  # Parent is RaceManagerGUI
        self.event = parent.event
        tc = tk.Frame(parent_widget, width=widths["Times Column"])
        ti = tk.Frame(tc)
        ti.pack(side='top', fill=tk.BOTH)
        w = tk.Label(ti, text="      ", font=large_font)
        w.pack(side='left', fill=tk.X, expand=1)
        w = tk.Label(ti, text="Status", font=large_font)
        w.pack(side='left', fill=tk.X, expand=1)
        w = tk.Label(ti, text=" Times", font=large_font)
        w.pack(side='left', fill=tk.X, expand=1)
        self.race_selector = RaceSelector(tc, parent)
        self.race_times = [RaceTimes(tc, ri, self) for ri in range(parent.parent.n_lanes)]
        for rt in self.race_times:
            rt.frame.pack(fill=tk.BOTH, expand=1)
        self.mf = tc

    def update_track_status_indicator(self, idx, new_race=True):
        self.race_times[idx].status_indicator.update(new_race=new_race)

    def update(self, new_race=True):
        for rt in self.race_times:
            rt.status_indicator.update(new_race=new_race)
            if rt.update_race_time_display():
                rt.update_placement_display()

    def reset_race_time_display(self, idx):
        self.race_times[idx].reset_race_time_display()

    def update_race_time_display(self, idx):
        self.race_times[idx].update_race_time_display()

    def reset_race_placement_display(self, idx):
        self.race_times[idx].reset_placement_display()

    def update_race_placement_display(self, idx):
        self.race_times[idx].update_placement_display()


class RaceColumn:

    def __init__(self,
                 parent,
                 parent_widget,
                 title: str,
                 chips: list):

        global widths
        self.parent = parent
        rc = tk.Frame(parent_widget, width=widths["Race Column"])
        self.title = tk.Label(rc, text=title, font=large_font)
        self.title.pack(fill=tk.X)
        bc = tk.Frame(rc, height=widths["Top Spacer"])
        self.column_label = tk.Label(bc, text="00", font=med_font)
        self.column_label.pack(fill=tk.X)
        bc.pack(fill=tk.X)
        self.racer_id = []
        for j in range(parent.n_lanes):
            self.racer_id.append(tk.Label(rc, bg=parent.lane_colors[j], **chips[j]))
            self.racer_id[j].pack(fill=tk.BOTH, expand=1)
        self.mf = rc

    def update(self, chips, race_number):
        for idx, rid in enumerate(self.racer_id):
            rid.config(**chips[idx])
        if race_number > self.parent.event.last_race:
            self.column_label.config(text="#--")
            # race_number = self.parent.event.last_race
        else:
            self.column_label.config(text="#{}".format(race_number + 1))


class ControlsRow:

    def __init__(self,
                 parent):
        self.navigation_buttons: dict = {}
        self.accept_button: tk.Button = None
        self.autoReset: IntVar = None

        cr = tk.Frame(parent, height=40)
        self.navigation_buttons['Move Back'] = tk.Button(cr, text="Move Back",
                                                         command=goto_prev_race)
        self.navigation_buttons['Move Back'].pack(side=tk.LEFT)
        ab = tk.Button(cr, text="Accept Results", command=accept_results)
        ab.pack(side=tk.LEFT)
        self.accept_button = ab
        bb = tk.Button(cr, text="Move Forward", command=goto_next_race)
        bb.pack(side=tk.LEFT)
        self.navigation_buttons['Move Forward'] = bb
        self.autoReset = IntVar()
        ta = tk.Checkbutton(cr, text="Auto Reset", variable=self.autoReset, onvalue=1, offvalue=0)
        ta.pack(side=tk.LEFT)
        self.navigation_buttons['Auto Reset'] = ta
        cr.pack()

    def disable_navigation(self):
        self.navigation_buttons["Move Forward"].configure(state='disabled')
        self.navigation_buttons["Move Back"].configure(state='disabled')

    def enable_navigation(self):
        self.navigation_buttons["Move Forward"].configure(state='normal')
        self.navigation_buttons["Move Back"].configure(state='normal')


class RaceDisplay(MainWindow):

    def __init__(self,
                 top: tk.Frame,
                 parent):
        super().__init__(top)

        self.times_column: TimesColumn = None
        self.racing_column: RaceColumn = None
        self.on_deck_column: RaceColumn = None
        self.next_up_column1: RaceColumn = None
        self.controls_row: ControlsRow = None

        self.outer_frame = top
        self.parent = parent
        self.event = parent.event
        self.n_lanes = parent.event.n_lanes
        self.lane_colors = parent.lane_colors
        self.main_frame = tk.Frame(top, bg='black')

        self.main_frame.pack(fill=tk.BOTH, expand=1)
        self.load_main_frame()
        self.controls_row = ControlsRow(top)

    def load_main_frame(self):
        self.times_column = TimesColumn(self, self.main_frame)
        self.times_column.mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        race_num = self.parent.event.current_race_idx
        self.racing_column = RaceColumn(self, self.main_frame,
                                        "Racing", self.parent.event.get_chips_for_race(race_num))
        self.racing_column.mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.on_deck_column = RaceColumn(self, self.main_frame, "On Deck",
                                         self.parent.event.get_chips_for_race(race_num + 1))
        self.on_deck_column.mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.next_up_column1 = RaceColumn(self, self.main_frame, "Next Up",
                                          self.parent.event.get_chips_for_race(race_num + 2))
        self.next_up_column1.mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

    def _pack(self):
        return

    def _forget(self):
        return

    def _tkraise(self):
        return

    def _update(self):
        return


# THE GUI


class RaceManagerGUI:
    window_size = "1850x1024"
    lane_colors = ["#1167e8", "#e51b00", "#e5e200", "#7fd23c"]
    clock_rate = clock_rate

    def __init__(self,
                 hosts_file_name: str = None,
                 event_file_name: str = None,
                 log_file_name: str = None,
                 reset_lane: int = 0,
                 parent=None,
                 verbose: bool = False,
                 n_lanes: int = 4):

        self.n_lanes = n_lanes
        self.timer_coms: TimerComs = None
        self.running = True

        self.event_file_name = event_file_name
        self.event = Event(event_file_name, log_file_name, self.n_lanes)
        self.log_file_name = log_file_name
        self.verbose = verbose

        self.window = tk.Tk()
        self.window.title("Pack 402 Pinewood Derby")
        self.window.geometry(self.window_size)
        if parent is None:
            self.parent = self.window
        else:
            self.parent = parent

        if hosts_file_name is not None:
            self.timer_coms = TimerComs(
                parent=self,
                hosts_file=hosts_file_name,
                reset_lane=reset_lane,
                verbose=verbose,
            )

        self.root_frame = tk.Frame(self.window)
        self.root_frame.pack(fill=tk.BOTH, expand=1)
        self.frames = {"race_display": tk.Frame(self.root_frame),
                       "planning_display": tk.Frame(self.root_frame),
                       "socket_display": tk.Frame(self.root_frame),
                       "cailibration_display": tk.Frame(self.root_frame),
                       "results_display": tk.Frame(self.root_frame)}
        self.add_menu_bar()

        """ Set up the Results display. After setting it up, we will
        forget it because we want to start with the race disylay instead
        but be ready to switch to it later."""
        # self.frames['results_display'].pack()
        self.displays = {"results_display": ResultsWindow(
            self.frames['results_display'], self.event)}
        self.displays['results_display'].pack()
        self.displays['results_display'].forget()

        " Set up the socket display."
        self.displays['socket_display'] = TimerWindow(
            self.frames['socket_display'], self.timer_coms,
            self.lane_colors, self.verbose)
        self.timer_coms.set_socket_frame(self.frames['socket_display'])
        self.displays['socket_display'].pack()
        self.displays['socket_display'].forget()

        " Set up the race planning display."
        self.displays['planning_display'] = registration.RegistrationWindow(
            self.frames['planning_display'], self.event_file_name,
            self.event, parent=self
        )
        self.displays['planning_display'].pack()
        self.displays['planning_display'].forget()

        " Set up the race display. "
        " Set this as the active frame"
        self.displays['race_display'] = RaceDisplay(
            self.frames['race_display'], self)
        self.displays['race_display'].pack()

        self.times_column = self.displays['race_display'].times_column
        self.racing_column = self.displays['race_display'].racing_column
        self.on_deck_column = self.displays['race_display'].on_deck_column
        self.next_up_column1 = self.displays['race_display'].next_up_column1
        self.controls_row = self.displays['race_display'].controls_row

        self.displays['race_display'].forget()

        # Add window delete callback
        self.window.protocol("WM_DELETE_WINDOW", self.close_manager)
        self.parent = parent
        self.next_frame = None
        self.switch_to('race_display')

    def mainloop(self):
        self.window.mainloop()

    def add_menu_bar(self):
        menu = tk.Menu(self.window)
        app = self.parent
        self.window.config(menu=menu)
        file_menu = tk.Menu(menu)
        file_menu.add_command(label="Generate Report", command=app.generate_report)
        open_menu = tk.Menu(file_menu)
        open_menu.add_command(label="Event File", command=self.load_event_file)
        open_menu.add_command(label="Race Log", command=self.load_race_log)
        open_menu.add_command(label="Timer Hosts", command=self.load_timer_hosts)
        file_menu.add_cascade(label="Open", menu=open_menu)
        save_menu = tk.Menu(file_menu)
        save_menu.add_command(label="Event File", command=self.save_event_file)
        save_menu.add_command(label="Race Log", command=self.save_race_log)
        save_menu.add_command(label="Timer Hosts", command=self.save_timer_hosts)
        file_menu.add_cascade(label="Save", menu=save_menu)
        file_menu.add_command(label="Exit", command=self.close_manager)
        menu.add_cascade(label="File", menu=file_menu)
        settings_menu = tk.Menu(menu)
        settings_menu.add_command(label="Race Display", command=self.open_race_display)
        settings_menu.add_command(label="Sockets", command=self.edit_timer_hosts)
        settings_menu.add_command(label="Plan", command=self.edit_race_plan)
        settings_menu.add_command(label="Results", command=self.edit_results_file)
        menu.add_cascade(label="Windows", menu=settings_menu)

    """ Functions to switch the main window. """

    def switch_to(self, which_frame: str):
        """Shut down all displays activities. """
        for _, dis in self.displays.items():
            dis.stop()

        try:
            self.displays[which_frame].tkraise()
        except TclError:
            pass
        self.displays[which_frame].pack()

        self.displays[which_frame].run()

    def open_race_display(self, ):
        self.next_frame = 'race_display'

    def edit_timer_hosts(self, *args):
        self.next_frame = 'socket_display'

    def edit_race_plan(self, *args):
        self.next_frame = 'planning_display'

    def edit_results_file(self, *args):
        self.next_frame = 'results_display'

    def close_manager(self):
        global race_needs_written, program_running

        print("close manager called")
        if race_needs_written:
            record_race_results()
            race_needs_written = False
        print("Final race written to file.")
        self.event.close_log_file()
        self.timer_coms.shutdown()
        self.running = False
        program_running = False

    def update_race_display(self, new_race=True):        
        if self.times_column is None:
            return
        self.times_column.update(new_race=new_race)

        race_idx = rm_gui.event.current_race_idx
        self.racing_column.update(rm_gui.event.get_chips_for_race(race_idx), race_idx)
        if race_idx > rm_gui.event.last_race:
            race_idx = rm_gui.event.last_race + 1
        else:
            race_idx += 1
        self.on_deck_column.update(rm_gui.event.get_chips_for_race(race_idx), race_idx)
        if race_idx > rm_gui.event.last_race:
            race_idx = rm_gui.event.last_race + 1
        else:
            race_idx += 1
        self.next_up_column1.update(rm_gui.event.get_chips_for_race(race_idx), race_idx)

    def update_race_selector(self,
                             show_accepted_race=True,
                             race_idx=-2, race_log_idx=-1, ):
        if race_idx == -1:
            race_idx = self.event.current_race_idx
        if race_log_idx == -1:
            race_log_idx = self.event.current_race_log_idx
        self.times_column.race_selector.update(
            show_accepted_race=show_accepted_race,
            race_idx=race_idx, race_log_idx=race_log_idx
        )

    def update_socket_status(self):
        times_column = self.displays['race_display'].times_column
        for i in range(self.n_lanes):
            times_column.race_times[i].update_socket_status(
                timer_coms.comms[i].is_connected())

    def set_active_race_log_idx(self, idx):
        global block_loading_previous_times
        self.times_column.race_selector.active_race_log_idx = idx
        block_loading_previous_times = True
        self.update_race_selector(show_accepted_race=False,
                                  race_idx=self.event.current_race_idx,
                                  race_log_idx=idx)
        block_loading_previous_times = False

    def get_active_race_log_idx(self):
        return self.times_column.race_selector.active_race_log_idx

    def get_active_race_idx(self):
        return self.event.current_race_idx

    def load_event_file(self, *args):
        file_name = filedialog.askopenfilename(
            title="Select Race Plan",
            filetypes=(("YAML (preferred)", "*.yaml"),
                       ("comma separated variables", "*.csv")))
        if len(file_name) > 0:
            self.event_file_name = file_name
            self.reload_event()
        else:
            print("Event load canceled.")

    def save_event_file(self, *args):
        file_name = filedialog.asksaveasfilename(
            title="Select File Name",
            defaultextension=".yaml")
        if len(file_name) > 0:
            self.event_file_name = file_name
            self.event.print_plan_yaml(self.event_file_name)
        else:
            print("Unable to save file.")

    def reload_event(self):
        if self.log_file_name == '/dev/null':
            self.event.close_log_file()
            self.event = Event(event_file=self.event_file_name, log_file=None,
                               n_lanes=self.n_lanes)
        else:
            self.event = Event(event_file=self.event_file_name,
                               log_file=self.log_file_name,
                               n_lanes=self.n_lanes)
        self.set_active_race_log_idx(0)
        self.update_race_display(new_race=False)

    def load_timer_hosts(self, *args):
        file_name = filedialog.askopenfilename(
            title="Select Timer Hosts File",
            defaultextension=".csv")
        if len(file_name) > 0:
            self.timer_coms.reset_sockets()
            self.timer_coms.get_hosts_and_ports(file_name)
            self.timer_coms.connect_to_track_hosts(autoclose=True)
        else:
            print("Timer host load canceled.")

    def save_timer_hosts(self, *args):
        file_name = filedialog.asksaveasfilename(
            title="Select File Name",
            defaultextension=".yaml")
        if len(file_name) > 0:
            self.timer_coms.save_timer_hosts(file_name)
        else:
            print("Unable to save file.")

    def load_race_log(self, *args):
        file_name = filedialog.askopenfilename(
            title="Select Race Log",
            defaultextension=".log")
        if len(file_name) > 0:
            self.log_file_name = file_name
            self.reload_event()
        else:
            print("Event load canceled.")

    def save_race_log(self, *args):
        file_name = filedialog.asksaveasfilename(
            title="Select File Name",
            defaultextension=".log")
        if len(file_name) > 0:
            if self.event.log_file_name == file_name:  # We are always saving
                return
            # Close the existing log file
            self.event.close_log_file()
            # Change the file names
            self.log_file_name = file_name
            # Reload the event
            self.reload_event()
        else:
            print("Unable to save file.")

    def get_messages_from_timers(self):
        out = []
        while True:
            try:
                out.append(self.timer_coms.q.get(block=False))
            except queue.Empty:
                break
        if len(out) >= 1:
            if self.verbose:
                print(out)
        return out


# FUNCTIONAL CODE


class RaceManager:

    def __init__(self,
                 event_file_name: str = None,
                 hosts_file_name: str = None,
                 log_file_name: str = "race_manager.log",
                 reset_lane: int = 0,  # gets the reset signal.
                 verbose: bool = False,
                 ):
        self.rm_gui = RaceManagerGUI(
            event_file_name=event_file_name,
            log_file_name=log_file_name,
            hosts_file_name=hosts_file_name,
            reset_lane=reset_lane,
            parent=self,
            verbose=verbose,
        )
        self.event = self.rm_gui.event
        self.race_needs_written = False
        self.req_win: tk.Toplevel = None
        self.verbose = verbose

        # self.rm_gui.timer_coms.connect_to_track_hosts(autoclose=True)

    def request_to_post_results(self):
        req_win = tk.Toplevel()
        req_win.title("Post Results?")

        question = tk.Label(req_win, text=
        """Not all racers have completed their runs.
Do you want to: 
 1. post the current results, 
 2. wait a little longer, or
 3. just move on to the next race without posting?""")
        question.pack()
        fm = tk.Frame(req_win)
        ans1 = tk.Button(fm, text="Post Results", command=self.post_results)
        ans1.pack(side=tk.LEFT)
        ans2 = tk.Button(fm, text="Wait", command=self.keep_waiting)
        ans2.pack(side=tk.LEFT)
        ans3 = tk.Button(fm, text="Just Move On", command=self.just_move_on)
        ans3.pack(side=tk.LEFT)
        fm.pack()
        req_win.update()
        self.req_win = req_win

    def post_results(self):
        self.req_win.destroy()
        record_race_results(accept=True)  # TODO See if this can be removed. LRB
        self.rm_gui.update_race_display()

    def keep_waiting(self):
        self.req_win.destroy()

    def just_move_on(self):
        self.req_win.destroy()
        self.rm_gui.event.goto_next_race()
        self.rm_gui.update_race_display()

    def generate_report(self):
        report_file_name = filedialog.asksaveasfilename(
            title='Select a File to Save the Report In',
            filetypes=(("Comma-Seperated Variable", "*.csv"),
                       ("Text", "*.txt"),
                       ("All Files", "*.*")))
        if len(report_file_name) > 0:
            rv = self.rm_gui.event.print_status_report(report_file_name)
            if rv == 0:
                di = tk.Toplevel()
                m = tk.Label(di, text="File Written.", height=6, width=24)
                m.pack()
                di.protocol("WM_DELETE_WINDOW", di.destroy)
                di.update()


def goto_prev_race():
    global race_needs_written, rm_gui
    if race_needs_written:
        record_race_results(accept=False)
        race_needs_written = False
    rm_gui.event.goto_prev_race()
    rm_gui.update_race_selector(True,
                                race_log_idx=rm_gui.event.current_race_log_idx,
                                race_idx=rm_gui.event.current_race_idx)
    if rm_gui.event.current_race.accepted_result_idx >= 0:
        rm_gui.update_race_display(new_race=False)
    else:
        rm_gui.update_race_display(new_race=True)


def goto_next_race():
    global race_needs_written, rm_gui
    if race_needs_written:
        record_race_results(accept=False)
        race_needs_written = False
    rm_gui.event.goto_next_race()
    rm_gui.update_race_selector(True,
                                race_log_idx=rm_gui.event.current_race_log_idx,
                                race_idx=rm_gui.event.current_race_idx)
    if rm_gui.event.current_race.accepted_result_idx >= 0:
        rm_gui.update_race_display(new_race=False)
    else:
        rm_gui.update_race_display(new_race=True)


def accept_results():
    # Called when the "Accept Results" button is pressed.
    global race_complete, race_ready, race_running, race_needs_written, timer_coms
    global rm_gui, program
    race_needs_written = True
    if all(race_complete):
        send_reset_to_track(accept=True,
                            send_reset=bool(
                                rm_gui.controls_row.autoReset.get()))
        rm_gui.update_race_display(new_race=True)
    elif any(race_complete):
        program.request_to_post_results()
    else:
        print("{} {} {}".format(race_ready, race_running, race_complete))
        rm_gui.event.goto_next_race()
        send_reset_to_track(accept=False,
                            send_reset=bool(
                                rm_gui.controls_row.autoReset.get()))
        rm_gui.update_race_display(new_race=False)


def find_race_count(data, s_idx, race_num, log_num):
    num = data.decode('utf-8').split(":")[1][:-1]
    num = num.split('>')[0]
    count = int(num)
    print(
        f"{green}Track {s_idx + 1}: Count = {count}, Seconds = {float(count) / clock_rate}. Race:Log {race_num}:{log_num}{normal_color}")
    return count


def show_results():
    global rm_gui
    race_selector = rm_gui.displays['race_display'].times_column.race_selector
    race_idx = race_selector.get_race_idx_from_selector()
    updated_counts = rm_gui.event.get_counts_for_race(race_idx)
    race_count = deepcopy(updated_counts)

    # Find which lanes were 1st, 2nd, 3rd, and 4th
    race_times = rm_gui.displays['race_display'].times_column.race_times
    max_count = max(race_count) + 1
    
    # For empty lanes or cars that did not finish, give them the max time
    for i, cnt in enumerate(race_count):
        if cnt <= 0 or rm_gui.event.current_race.is_empty(i):
            race_count[i] = max_count
            race_times[i].placement = -1
    
    # Sort the results, accounting for ties    
    ranks = get_placements(race_count) - 1 
    
    for i, rank in enumerate(ranks):
        if race_count[i] == max_count:
            continue
        race_times[i].placement = rank

    rm_gui.update_race_display(new_race=False)


def record_race_results(accept=False):
    global block_loading_previous_times, rm_gui
    if accept:
        print("****ACCEPTING RESULTS*****\n")
    race_log_idx = rm_gui.get_active_race_log_idx()  # This is the one the user said they want to accept
    race_idx = rm_gui.get_active_race_idx()  # This is the one the log says is accepted
    try:
        race_counts = rm_gui.event.counts[race_log_idx]
    except IndexError: # Maybe we hit the button early?
        return
    if rm_gui.event.current_race_log_idx is not race_log_idx:
        print("It looks like we are not current {} != {}.".format(
            rm_gui.event.current_race_log_idx, race_log_idx))
        # These results are already recorded
        if accept:
            # We need to change which race is accepted
            idx = -1
            """ rm_gui.event.current_race.race_number lists which of the
            recorded race times (race_number is the index of the recorded
            times) were attributed to this set of racers (a.k.a. "current race".
            We will go through and figure out which race_number matches the one
            we pulled up so that we can get its data."""
            for ii, v in enumerate(rm_gui.event.current_race.race_number):
                idx = ii
                if v == race_log_idx:
                    break
            if rm_gui.event.current_race.race_number[idx] != race_log_idx:
                idx = -1
            print("idx={},copying results".format(idx))
            rm_gui.event.current_race.post_results_to_racers(i=idx)
            times = [float(x) / rm_gui.clock_rate for x in race_counts]
            tmp_idx = rm_gui.event.current_race_log_idx
            rm_gui.event.current_race_log_idx = race_log_idx
            rm_gui.event.record_race_results(times, race_counts,
                                             race_idx, race_log_idx,
                                             accept)
            rm_gui.update_race_selector(show_accepted_race=True,
                                        race_idx=rm_gui.event.current_race_idx,
                                        race_log_idx=race_log_idx)
            rm_gui.event.current_race_log_idx = tmp_idx
            return
    if any(race_counts):
        times = [float(x) / rm_gui.clock_rate for x in race_counts]
        rm_gui.event.record_race_results(times, race_counts, race_idx,
                                         race_log_idx, accept)
        rm_gui.set_active_race_log_idx(rm_gui.event.current_race_log_idx)


def send_reset_to_track(accept=False, send_reset=True):
    """ This used to always send a reset. Now it only does if you tell it to, but
    we already have a function named "accept_results" and this just does
    part of that."""
    global timer_coms, race_needs_written, rm_gui, race_running
    if send_reset:
        timer_coms.send_reset_to_track()
    if race_needs_written:
        record_race_results(accept=accept)
        race_needs_written = False
    rm_gui.controls_row.enable_navigation()
    race_running = [False] * rm_gui.n_lanes


if __name__ == "__main__":
    post_placements = True
    cli_args = parser.parse_args()
    verbose = cli_args.verbose

    program = RaceManager(
        event_file_name=cli_args.event_file,
        log_file_name=cli_args.log_file,
        hosts_file_name=cli_args.hosts_file,
        reset_lane=0,
        verbose=cli_args.verbose,
    )

    rm_gui = program.rm_gui

    timer_coms = rm_gui.timer_coms

    complain = True

    while program_running:
        "Waiting for data from track hosts."
        rm_gui.update_socket_status()
        for msg in rm_gui.get_messages_from_timers():
            s_idx = msg['idx']
            data = msg['data']
            crn = rm_gui.event.current_race.plan_number
            rli = rm_gui.event.current_race_log_idx
            if data == _test_msg:
                rm_gui.timer_coms.comms[s_idx].connected = True
            if 'Ready to Race'.encode('utf-8') in data:
                if race_needs_written:
                    record_race_results()
                    race_needs_written = False
                print(f"{yellow}Track {s_idx + 1} ready. Race {crn}. Log Entry {rli}.{normal_color}")
                rm_gui.set_active_race_log_idx(rm_gui.event.current_race_log_idx)
                race_ready[s_idx] = True
                race_running[s_idx] = False
                race_complete[s_idx] = (False or
                                        rm_gui.event.current_race.is_empty(s_idx))
                rm_gui.times_column.race_times[s_idx].placement = -1
                post_placements = True
                rm_gui.update_race_display()
            elif 'GO!'.encode('utf-8') in data:
                race_needs_written = True
                rm_gui.set_active_race_log_idx(
                    rm_gui.event.current_race_log_idx)  # Force a jump to the new race when started
                # rm_gui.update_race_display(new_race=True)
                if verbose:
                    print(f"Track {s_idx + 1} racing! Race {crn}. Log Entry {rli}")
                race_ready[s_idx] = False
                race_running[s_idx] = True
                rm_gui.update_race_display(new_race=True)
            elif 'Track count:'.encode('utf-8') in data:
                if rm_gui.event.current_race.is_empty(s_idx):
                    race_count = 0
                else:
                    race_count = find_race_count(data, s_idx, crn, rli)
                rm_gui.event.set_counts_for_race(s_idx, race_count)
                if verbose:
                    print(
                        f"{green}{s_idx + 1}, count={race_count}, data={data}. Race {crn}. Log Entry {rli}.{normal_color}")
                race_ready[s_idx] = False
                race_running[s_idx] = False
                race_complete[s_idx] = True
                rm_gui.times_column.update_race_time_display(s_idx)
                rm_gui.update_race_display(new_race=False)
                if all(race_complete):
                    rm_gui.controls_row.enable_navigation()
            if 'Calibration:'.encode('utf-8') in data:
                cc = data.decode('utf-8').split(":")[-1]
                cc = cc.split('>')[0]
                try:
                    rm_gui.timer_coms.comms[s_idx].set_cal_constant(int(cc))
                except ValueError:
                    pass 
                rm_gui.displays['socket_display'].timer_frame[s_idx].set_left_cal_text()
            else:
                if len(data) == 0:  # indicative of no data available
                    continue
                else:
                    if verbose:
                        print(data)

        if all(race_complete) and post_placements:
            show_results()
            post_placements = False

        # if rm_gui.running:
        rm_gui.window.update_idletasks()
        rm_gui.window.update()
        for _, disp in rm_gui.displays.items():
            disp.update()

        if rm_gui.next_frame is not None:
            rm_gui.switch_to(rm_gui.next_frame)

        rm_gui.next_frame = None
