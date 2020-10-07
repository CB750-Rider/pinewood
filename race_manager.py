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

from typing import List
import numpy as np
import tkinter as tk
from tkinter import filedialog
import select
from race_event import Event
import argparse
from rm_socket import TimerComs

description = "A Graphical Interface for managing Pinewood Derby Races"

parser = argparse.ArgumentParser(description=description)
parser.add_argument('--hosts_file', help='A file with the ip and port addresses of the lane timers (hosts).',
                    default=None)
parser.add_argument('--event_file', help='A file with the event plan listed.',
                    default=None)
parser.add_argument('--log_file', help='The name of a file to save race times to.',
                    default=None)

host = ['', '', '', '']
port = [0, 0, 0, 0]
stringlen = 64
reset_default_lane = 3
race_time_displays = [[], [], [], []]  # race time displays
placement_displays = [[], [], [], []]  # placement displays
placements = [-1, -1, -1, -1]
race_count = [0, 0, 0, 0]
status_indicators = [[], [], [], []]
# dimensions are y = row x = column rid[y][x]
widths = {"Times Column": 450,
          "Race Column": 350,
          "Top Spacer": 33}
race_ready = [False, False, False, False]  # "Yellow LED"
race_complete = [True, True, True, True]  # "Red LED"
race_running = [False, False, False, False]  # "Green LED"
reset_msg = "<reset>\n".encode('utf-8')
sockets_ = [[], [], [], []]  # Socket connections
s_conn = [False, False, False, False]  # Socket connection flags
small_font = ("Serif", 12)
med_font = ("Serif", 16)
large_font = ("Serif", 22)
program_running = True
race_needs_written = False
block_loading_previous_times = False
req_win = None


# GUI STUFF

class RaceSelector:
    race_menu: tk.OptionMenu = None
    add_reset_button: tk.Button = None
    current_race_str: tk.StringVar = None
    active_race_idx: int = 0
    race_count: int = 0
    event: Event = None

    def __init__(self,
                 outer_frame: tk.Frame,
                 parent):
        global timer_coms
        race = parent.event.current_race
        self.event = parent.event
        rt = tk.Frame(outer_frame)
        w = tk.Label(rt, text="Race log #", font=small_font)
        w.pack(side=tk.LEFT, fill=tk.X, expand=1)

        if len(race.race_number):
            option_list = [str(x) for x in race.race_number]
            option_list.append(self.event.current_race_log_idx)
        else:
            option_list = [str(self.event.current_race_log_idx), ]
        current_race_str = tk.StringVar(rt)
        if race.accepted_result_idx >= 0:
            idx = race.accepted_result_idx
            option_list[idx] += ' < ACC'
            self.active_race_idx = race.race_number[idx]
            current_race_str.set(option_list[idx])
            self.race_count = self.event.current_race.counts[idx]
        else:
            current_race_str.set(option_list[-1])
            self.active_race_idx = self.event.current_race_log_idx
        current_race_str.trace("w", self.load_previous_times)
        race_selector = tk.OptionMenu(rt, current_race_str, "0", *option_list,
                                      command=parent.update_race_display(new_race=False))
        race_selector.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.race_menu = race_selector
        # TODO Should the send_reset_to_track accept?
        b = tk.Button(rt, text="add/reset", command=timer_coms.send_reset_to_track, font=small_font)
        b.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.add_reset_button = b
        rt.pack(fill=tk.X)

    def update(self, show_accepted_race=True):
        # Grab the embeded menu and change the choices
        embeded_menu = self.race_menu['menu']
        embeded_menu.delete(0, 'end')
        race = self.event.current_race

        # Create a new list
        if len(race.race_number):
            option_list = [str(x) for x in race.race_number]
            option_list.append(self.event.current_race_log_idx)
        else:
            option_list = [str(self.event.current_race_log_idx), ]

        if race.accepted_result_idx >= 0:
            idx = race.accepted_result_idx
            option_list[idx] += ' < ACC'
            if show_accepted_race:
                self.current_race_str.set(option_list[idx])
            else:
                self.current_race_str.set(str(self.active_race_idx))
        else:
            self.current_race_str.set(str(self.active_race_idx))

        for new_choice in option_list:
            embeded_menu.add_command(label=new_choice,
                                     command=tk._setit(self.current_race_str, new_choice))

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
                self.active_race_idx = self.event.current_race_log_idx
            else:
                counts = self.event.current_race.counts[idx]
                self.active_race_idx = self.event.current_race.race_number[idx]
        else:
            counts = [0, 0, 0, 0]
            self.active_race_idx = self.event.current_race_log_idx

        for ri in range(self.event.n_lanes):
            race_count[ri] = counts[ri]

        print(race_count)
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
        self.parent = parent
        self.idx = idx
        self.background = background
        self.top = top
        si = tk.Frame(parent, bg=background)
        self.frame = si
        print("Updating the track status")
        if race_ready[idx]:
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
                parent.reset_race_time_display(idx)
                parent.reset_placement_display(idx)
            else:
                parent.update_race_time_display(idx)
                parent.update_placement_display(idx)
        else:
            self.ready.config(**self.not_ready)
            if race_running[idx]:
                parent.controls_row.disable_navigation()
                self.running.config(**self.race_is_running)
                self.complete.config(**self.not_complete)
                if new_race:
                    parent.reset_race_time_display(idx)
                    parent.reset_placement_display(idx)
                else:
                    parent.update_race_time_display(idx)
                    parent.update_placement_display(idx)
            else:
                self.running.config(**self.not_running)
                self.complete.config(**self.race_complete)
                parent.update_race_time_display(idx)
                parent.update_placement_display(idx)


class RaceTimes:
    race_time_default = {"text": "0.000", "fg": "gray"}
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
        self.parent = parent
        self.idx = idx
        self.top = top
        colors = self.parent.colors
        self.colors = colors

        rt = tk.Frame(top)
        self.frame = rt
        w = tk.Label(rt, text="Lane {0}".format(idx + 1),
                     bg=colors[idx], font=large_font)
        w.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.status_indicator = TrackStatusIndicator(rt, colors[idx], idx, parent)
        self.status_indicator.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        res_frm = tk.Frame(rt)
        if parent.event.current_race.times:  # If times were posted
            current_race = parent.event.current_race
            if current_race.accepted_result_idx >= 0:  # show the accepted race
                times = current_race.times[current_race.accepted_result_idx]
                self.race_time_display = tk.Label(res_frm, bg=colors[idx],
                                                  font=large_font, fg="#000000", text="{0:.3f}".format(times[idx]))
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
        if self.parent.race_count[self.idx]:
            final_time = self.parent.race_count[self.idx] / self.parent.clock_rate
            self.race_time_display.config(text="{0:.3f}".format(final_time), fg='#000000')
        else:
            self.race_time_display.config(**self.race_time_default)

    def update_placement_display(self):
        global placement_displays, placements
        if self.parent.placements[self.idx] >= 0:
            self.placement_display.config({"bg": self.colors[self.idx]})
            self.placement_display.config(self.placement_settings[placements[self.idx]])
        else:
            self.placement_display.config({"bg": self.colors[self.idx]})
            self.placement_display.config(self.placement_default)

    def reset_placement_display(self):
        global placement_displays
        self.placement_display.config({"bg": self.colors[self.idx]})
        self.placement_display.config(self.placement_default)


class TimesColumn:
    race_selector: RaceSelector = None
    mf: tk.Frame = None

    def __init__(self,
                 parent):
        global widths, large_font
        self.parent = parent
        tc = tk.Frame(parent.window, width=widths["Times Column"])
        w = tk.Label(tc, text="Times", font=large_font)
        w.pack(fill=tk.X)
        self.race_selector = RaceSelector(tc, parent)
        self.race_times = [RaceTimes(tc, ri, parent) for ri in range(parent.n_lanes)]
        for rt in self.race_times:
            rt.frame.pack(fill=tk.BOTH, expand=1)
        self.mf = tc

    def update_track_status_indicator(self, idx, new_race=True):
        self.race_times[idx].status_indicator.update(new_race=new_race)

    def update_track_status_indicators(self, new_race=True):
        for rt in self.race_times:
            rt.status_indicator.update(new_race=new_race)

    def reset_race_time_display(self, idx):
        self.race_times[idx].reset_race_time_display()

    def update_race_time_display(self, idx):
        self.race_times[idx].update_race_time_display()

    def reset_race_placement_display(self, idx):
        self.race_times[idx].reset_placement_display()

    def update_race_placement_display(self, idx):
        self.race_times[idx].update_placement_display()


class RaceColumn:
    racer_id: List[tk.Label] = []
    title: tk.Label = None
    column_label = tk.Label = None
    mf: tk.Frame = None

    def __init__(self,
                 parent,
                 title: str,
                 chips: list):
        global widths
        self.parent = parent
        rc = tk.Frame(parent.window, width=widths["Race Column"])
        self.title = tk.Label(rc, text=title, font=large_font)
        self.title.pack(fill=tk.X)
        bc = tk.Frame(rc, height=widths["Top Spacer"])
        self.column_label = tk.Label(bc, text="00", font=("Serif", 18))
        self.column_label.pack(fill=tk.X)
        bc.pack(fill=tk.X)
        for j in range(parent.n_lanes):
            self.racer_id.append(tk.Label(rc, bg=parent.lane_colors[j], **chips[j]))
            self.racer_id[j].pack(fill=tk.BOTH, expand=1)
        self.mf = rc

    def update(self, chips, race_number):
        for idx, rid in enumerate(self.racer_id):
            rid.config(**chips[idx])
        self.column_label.config(text="#{}".format(race_number))


class ControlsRow:
    navigation_buttons: dict = {}
    accept_button: tk.Button = None

    def __init__(self,
                 parent):
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
        cr.pack()

    def disable_navigation(self):
        self.navigation_buttons["Move Forward"].configure(state='disabled')
        self.navigation_buttons["Move Back"].configure(state='disabled')

    def enable_navigation(self):
        self.navigation_buttons["Move Forward"].configure(state='normal')
        self.navigation_buttons["Move Back"].configure(state='normal')


class RaceManagerGUI:
    window_size = "1850x1024"
    window: tk.Tk() = None
    lane_colors = ["#1167e8", "#e51b00", "#e5e200", "#7fd23c"]
    n_lanes = 4
    timer_coms: TimerComs = None
    running = True
    times_column: TimesColumn = None
    racing_column: RaceColumn = None
    on_deck_column: RaceColumn = None
    next_up_column1: RaceColumn = None
    controls_row: ControlsRow = None
    race_selector: RaceSelector = None
    event: Event = None
    clock_rate = 2000.0
    race_count: List[int] = []
    placements: List[int] = []

    def __init__(self,
                 hosts_file_name: str = None,
                 event_file_name: str = None,
                 log_file_name: str = None):
        self.event = Event(event_file_name, log_file_name, self.n_lanes)

        self.window = tk.Tk()
        self.window.title("Pack 402 Pinewood Derby")
        self.window.geometry(self.window_size)

        if hosts_file_name is not None:
            self.timer_coms = TimerComs(
                parent=self.window,
                hosts_file=hosts_file_name
            )

        self.add_menu_bar()

        self.race_count = [0 for _ in range(self.n_lanes)]
        self.placements = [-1 for _ in range(self.n_lanes)]

        self.main_frame = tk.Frame(self.window, bg='black')
        self.load_main_frame()
        self.main_frame.pack(fill=tk.BOTH, expand=1)

        self.controls_row = ControlsRow(self.window)

        # Add window delete callback
        self.window.protocol("WM_DELETE_WINDOW", self.close_manager)

    def mainloop(self):
        self.window.mainloop()

    def add_menu_bar(self):
        menu = tk.Menu(self.window)
        self.window.config(menu=menu)
        file_menu = tk.Menu(menu)
        file_menu.add_command(label="Generate Report", command=generate_report)
        open_menu = tk.Menu(file_menu)
        open_menu.add_command(label="Race Plan", command=self.load_race_plan)
        open_menu.add_command(label="Race Log", command=self.load_race_log)
        open_menu.add_command(label="Timer Hosts", command=self.load_timer_hosts)
        file_menu.add_cascade(label="Open", menu=open_menu)
        file_menu.add_command(label="Exit", command=self.close_manager)
        menu.add_cascade(label="File", menu=file_menu)
        settings_menu = tk.Menu(menu)
        settings_menu.add_command(label="Set Hosts", command=self.set_timer_hosts)
        menu.add_cascade(label="Settings", menu=settings_menu)

    def close_manager(self):
        global race_needs_written

        print("close manager called")
        if race_needs_written:
            record_race_results()
            race_needs_written = False
        print("Final race written to file.")
        self.event.close_log_file()
        self.timer_coms.shutdown()
        self.running = False

    def load_main_frame(self):
        self.times_column = TimesColumn(self)
        self.times_column.mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        race_num = event.current_race_idx
        self.racing_column = RaceColumn(self, "Racing", event.get_chips_for_race(race_num))
        self.racing_column.mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.on_deck_column = RaceColumn(self, "On Deck",
                                         event.get_chips_for_race(race_num + 1))
        self.on_deck_column.mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        self.next_up_column1 = RaceColumn(self, "Next Up",
                                          event.get_chips_for_race(race_num + 2))
        self.next_up_column1.mf.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

    def update_race_display(self, new_race=True):
        # global track_status_indicator, event, racing_column, on_deck_column, next_up_column1
        self.times_column.update_track_status_indicators(new_race=new_race)

        race_idx = event.current_race_idx
        self.racing_column.update(event.get_chips_for_race(race_idx), race_idx)
        if race_idx + 1 > event.last_race:
            race_idx = event.last_race
        else:
            race_idx += 1
        self.on_deck_column.update(event.get_chips_for_race(race_idx), race_idx)
        if race_idx + 1 > event.last_race:
            race_idx = event.last_race
        else:
            race_idx += 1
        self.next_up_column1.update(event.get_chips_for_race(race_idx), race_idx)

    def update_race_selector(self, show_accepted_race=True):
        self.race_selector.update(show_accepted_race=show_accepted_race)

    def load_race_plan(self, *args):
        print("Write load_race_plan.")

    def load_timer_hosts(self, *args):
        print("Write load_timer_hosts")

    def set_timer_hosts(self, *args):
        print("Write set_timer_hosts")

    def load_race_log(self, *args):
        print("Write load_race_log")


class RaceManager:
    event: Event = None
    rm_gui: RaceManagerGUI = None
    coms: TimerComs = None

    def __init__(self):
        print("Write RaceManager")


def request_to_post_results():
    global req_win
    req_win = tk.Toplevel()
    req_win.title("Post Results?")

    question = tk.Label(req_win, text="""Not all racers have completed their runs.
        Do you want to post the current results, or just move on to the next
                        race without posting?""")
    question.pack()
    fm = tk.Frame(req_win)
    ans1 = tk.Button(fm, text="Post Results", command=post_results)
    ans1.pack(side=tk.LEFT)
    ans2 = tk.Button(fm, text="Just Move On", command=just_move_on)
    ans2.pack(side=tk.LEFT)
    fm.pack()
    req_win.update()


# Race Viewer
def open_race_view_window():
    print("Write code to open a race viewer.")


# Heat Viewer
def open_heat_view_window():
    print("Write code to open a heat viewer.")


# Racer Viewer
def open_racer_view_window():
    print("Write code to open a racer viewer.")


# RACE Functions
def post_results():
    global req_win, event, timer_coms, rm_gui
    req_win.destroy()
    record_race_results(accept=True)  # TODO See if this can be removed. LRB
    # TODO March 7 2020
    timer_coms.send_reset_to_track()
    rm_gui.update_race_display()


def just_move_on():
    global req_win, event, timer_coms, rm_gui
    req_win.destroy()
    event.goto_next_race()
    timer_coms.send_reset_to_track()
    rm_gui.update_race_display()


def generate_report():
    global event
    print("Write code to generate a standings report for the race.")
    report_file_name = filedialog.asksaveasfilename(
        title='Select a File to Save the Report In',
        filetypes=(("Comma-Seperated Variable", "*.csv"),
                   ("Text", "*.txt"),
                   ("All Files", "*.*")))
    if len(report_file_name) > 0:
        rv = event.print_status_report(report_file_name)
        if rv == 0:
            di = tk.Toplevel()
            m = tk.Label(di, text="File Written.", height=6, width=24)
            m.pack()
            di.protocol("WM_DELETE_WINDOW", di.destroy)
            di.update()


def goto_prev_race():
    global event, race_needs_written, rm_gui
    if race_needs_written:
        record_race_results(accept=True)
        race_needs_written = False
    event.goto_prev_race()
    rm_gui.update_race_selector(True)
    if event.current_race.accepted_result_idx >= 0:
        rm_gui.update_race_display(new_race=False)
    else:
        rm_gui.update_race_display(new_race=True)


def goto_next_race():
    global event, race_needs_written, rm_gui
    if race_needs_written:
        record_race_results(accept=True)
        race_needs_written = False
    event.goto_next_race()
    rm_gui.update_race_selector(True)
    if event.current_race.accepted_result_idx >= 0:
        rm_gui.update_race_display(new_race=False)
    else:
        rm_gui.update_race_display(new_race=True)


def accept_results():
    global race_complete, race_ready, race_running, race_needs_written, timer_coms
    global rm_gui
    race_needs_written = True
    if all(race_complete):
        timer_coms.send_reset_to_track(accept=True)
        rm_gui.update_race_display(new_race=True)
    elif any(race_complete):
        request_to_post_results()
    else:
        print("{} {} {}".format(race_ready, race_running, race_complete))
        event.goto_next_race()
        timer_coms.send_reset_to_track()
        rm_gui.update_race_display(new_race=False)


def find_race_count(data):
    print(data)
    num = data.decode('utf-8').split(":")[1][:-1]
    count = int(num)
    print("Count = {}, Seconds = {}".format(count, np.float(count) / 2000.0))
    return count


def show_results():
    global race_count, event, placements, rm_gui
    # Find which lanes were 1st, 2nd, 3rd, and 4th
    ranks = np.argsort(race_count)
    place = 0
    for i in range(event.n_lanes):
        if event.current_race.is_empty[ranks[i]]:
            placements[ranks[i]] = -1
        elif race_count[ranks[i]] == 0:
            placements[ranks[i]] = -1
        else:
            placements[ranks[i]] = place
            place += 1
    print(placements)
    # Subtract any empty lanes as they will have counts of 0
    rm_gui.update_race_display(new_race=False)


def record_race_results(accept=False):
    global event, race_count, active_race_idx
    global block_loading_previous_times, rm_gui
    print("record_race_results is called")
    if event.current_race_log_idx is not active_race_idx:
        print("It looks like we are not current {} != {}.".format(
            event.current_race_log_idx, active_race_idx))
        # These results are already recorded
        if accept:
            # We need to change which race is accepted
            idx = -1
            for ii, v in enumerate(event.current_race.race_number):
                idx = ii
                if v == active_race_idx:
                    break
            if event.current_race.race_number[idx] != active_race_idx:
                idx = -1
            print("idx={},copying results".format(idx))
            event.current_race.post_results_to_racers(i=idx)
            times = [np.float(x) / rm_gui.clock_rate for x in race_count]
            tmp_idx = event.current_race_log_idx
            event.current_race_log_idx = active_race_idx
            event.record_race_results(times, race_count, accept)
            event.current_race_log_idx = tmp_idx
            rm_gui.update_race_selector(show_accepted_race=False)
            return
        else:
            return
    if any(race_count):
        times = [np.float(x) / rm_gui.clock_rate for x in race_count]
        event.record_race_results(times, race_count, accept)
        active_race_idx = event.current_race_log_idx
        block_loading_previous_times = True
        rm_gui.update_race_selector(show_accepted_race=False)
        block_loading_previous_times = False


if __name__ == "__main__":
    post_placements = True
    cli_args = parser.parse_args()

    rm_gui = RaceManagerGUI(
        event_file_name=cli_args.event_file,
        log_file_name=cli_args.log_file,
        hosts_file_name=cli_args.hosts_file
    )

    timer_coms = TimerComs(rm_gui.window,
                           hosts_file=cli_args.hosts_file)

    timer_coms.connect()

    event = rm_gui.event

    while program_running:
        "Waiting for data from track hosts."
        ready_sockets, open_sockets, error_sockets = select.select(
            sockets_, sockets_, sockets_, 0.05)
        open_conn = [4]
        if len(open_sockets) != 4:
            print("Socket disconnection detected.")
            for i in range(4):
                if sockets_[i] in open_sockets:
                    open_conn[i] = True
                else:
                    open_conn[i] = False
                    print("Disconnect on socket {}".format(i))
            rm_gui.update_race_display(new_race=False)
            timer_coms.connect_to_track_hosts()
        for ready_socket in ready_sockets:
            data = timer_coms.get_data_from_socket(ready_socket)
            s_idx = -1
            for i, sc in enumerate(sockets_):
                if ready_socket == sc:
                    s_idx = i
            if s_idx == -1:
                print("Unable to determine which socket has data")
                raise SystemExit
            if 'Ready to Race'.encode('utf-8') in data:
                if race_needs_written:
                    record_race_results()
                    race_needs_written = False
                print("Track {} ready.".format(s_idx + 1))
                active_race_idx = event.current_race_log_idx
                block_loading_previous_times = True
                rm_gui.update_race_selector(show_accepted_race=False)
                block_loading_previous_times = False
                race_ready[s_idx] = True
                race_running[s_idx] = False
                race_complete[s_idx] = (False or
                                        event.current_race.is_empty[s_idx])
                placements[s_idx] = -1
                race_count[s_idx] = 0
                post_placements = True
            elif 'GO!'.encode('utf-8') in data:
                race_needs_written = True
                active_race_idx = event.current_race_log_idx  # Force a jump to the new race when started
                rm_gui.update_race_selector(show_accepted_race=False)
                rm_gui.update_race_display(new_race=True)
                print("Track {} racing!".format(s_idx + 1))
                race_ready[s_idx] = False
                race_running[s_idx] = True
            elif 'Track count:'.encode('utf-8') in data:
                # This if statement makes debugging easier because the 
                # empty lanes will be ignored
                if not event.current_race.is_empty[s_idx]:
                    race_count[s_idx] = find_race_count(data)
                race_ready[s_idx] = False
                race_running[s_idx] = False
                race_complete[s_idx] = True
                if all(race_complete):
                    rm_gui.controls_row.enable_navigation()
            else:
                if len(data) == 0:  # indicative of socket failure
                    timer_coms.connect_to_track_hosts()
                else:
                    print(data)

        if all(race_complete) and post_placements:
            show_results()
            post_placements = False

        if len(ready_sockets) > 0:
            rm_gui.update_race_display(new_race=False)

        rm_gui.window.update_idletasks()
        rm_gui.window.update()
