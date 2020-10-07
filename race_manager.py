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

# TODO Finish refactoring to use classes. RaceSelector was next to be done.

from typing import List

import numpy as np
import tkinter as tk
from tkinter import filedialog
import time
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
times_column = []
racing_column = []
on_deck_column = []
next_up_column1 = []
navigation_buttons = {}
rid = [[[], [], []], [[], [], []], [[], [], []], [[], [], []]]  # racer id tags
status_indicators = [[], [], [], []]
# dimensions are y = row x = column rid[y][x]
widths = {"Times Column": 450,
          "Race Column": 350,
          "Top Spacer": 33}
race_ready = [False, False, False, False]  # "Yellow LED"
race_complete = [True, True, True, True]
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


# GUI STUFF



def Race_Selector(parent):
    global event, race_selector, current_race_str, active_race_idx, race_count
    race = event.current_race
    rt = tk.Frame(parent)
    w = tk.Label(rt, text="Race log #", font=small_font)
    w.pack(side=tk.LEFT, fill=tk.X, expand=1)

    if len(race.race_number):
        option_list = [str(x) for x in race.race_number]
        option_list.append(event.current_race_log_idx)
    else:
        option_list = [str(event.current_race_log_idx), ]
    current_race_str = tk.StringVar(rt)
    if race.accepted_result_idx >= 0:
        idx = race.accepted_result_idx
        option_list[idx] += ' < ACC'
        active_race_idx = race.race_number[idx]
        current_race_str.set(option_list[idx])
        race_count = event.current_race.counts[idx]
    else:
        current_race_str.set(option_list[-1])
        active_race_idx = event.current_race_log_idx
    current_race_str.trace("w", load_previous_times)
    race_selector = tk.OptionMenu(rt, current_race_str, "0", *option_list,
                                  command=update_race_display(new_race=False))
    race_selector.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
    b = tk.Button(rt, text="add/reset", command=send_reset_to_track, font=small_font)
    b.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
    return rt


def update_race_selector(show_accepted_race=True):
    global event, race_selector, current_race_str, active_race_idx
    # Grab the embeded menu and change the choices
    embeded_menu = race_selector['menu']
    embeded_menu.delete(0, 'end')
    race = event.current_race

    # Create a new list
    if len(race.race_number):
        option_list = [str(x) for x in race.race_number]
        option_list.append(event.current_race_log_idx)
    else:
        option_list = [str(event.current_race_log_idx), ]

    if race.accepted_result_idx >= 0:
        idx = race.accepted_result_idx
        option_list[idx] += ' < ACC'
        if show_accepted_race:
            current_race_str.set(option_list[idx])
        else:
            current_race_str.set(str(active_race_idx))
    else:
        current_race_str.set(str(active_race_idx))

    for new_choice in option_list:
        embeded_menu.add_command(label=new_choice,
                                 command=tk._setit(current_race_str, new_choice))


def load_previous_times(*args):
    global event, race_running, current_race_str, status_indicators, active_race_idx
    global block_loading_previous_times
    if any(race_running):  # Do nothing if we are running
        print("Previous times will not be loaded while the race is running.")
        return
    if block_loading_previous_times:
        return

    # Record times, just in case
    record_race_results()

    # Figure out which race we are on
    cidx = int(current_race_str.get().split(' ')[0])
    print("Looking for {} in {}.".format(cidx, event.current_race.race_number))
    if len(event.current_race.race_number) > 0:
        for i, ridx in enumerate(event.current_race.race_number):
            idx = i
            if cidx == ridx:
                break
        # Now idx is appropriately set. Send a warning if no match was found
        if (cidx != event.current_race.race_number[idx]):
            if idx is not len(event.current_race.race_number):
                print("Warning no race index was found!")
            counts = [0, 0, 0, 0]  # A default
            active_race_idx = event.current_race_log_idx
        else:
            counts = event.current_race.counts[idx]
            active_race_idx = event.current_race.race_number[idx]
    else:
        counts = [0, 0, 0, 0]
        active_race_idx = event.current_race_log_idx

    for ri in range(event.n_lanes):
        race_count[ri] = counts[ri]

    print(race_count)
    show_results()




def disable_navigation():
    global navigation_buttons
    navigation_buttons["Move Forward"].configure(state='disabled')
    navigation_buttons["Move Back"].configure(state='disabled')


def enable_navigation():
    global navigation_buttons
    navigation_buttons["Move Forward"].configure(state='normal')
    navigation_buttons["Move Back"].configure(state='normal')




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
    race_running = {"text": "Race Running",
                     "fg": "#000000",
                     "bg": "#00ff2a",
                     "borderwidth": 3,
                     "relief": "raised",
                     "font": med_font}
    not_running =  {"text": "Not Running",
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
                 parent: RaceManagerGUI):
        self.parent = parent
        self.idx = idx
        self.background = background
        self.top = top

        si = tk.Frame(parent, bg=background)
        self.frame = si
        print("Updating the track status")
        if parent.race_ready[idx]:
            self.ready = tk.Label(si, **self.ready_to_race)
            self.ready.pack(fill=tk.X, side=tk.TOP, expand=1)
            self.running = tk.Label(si, **self.not_running)
            self.running.pack(fill=tk.X, side=tk.TOP, expand=1)
            self.complete = tk.Label(si, **self.not_complete)
            self.complete.pack(fill=tk.X, side=tk.TOP, expand=1)
        else:
            self.ready = tk.Label(si, **self.not_ready)
            self.ready.pack(fill=tk.X, side=tk.TOP, expand=1)
            if parent.race_running[idx]:
                self.running = tk.Label(si, **self.race_running)
                self.running.pack(fill=tk.X, side=tk.TOP, expand=1)
                self.complete = tk.Label(si, **self.not_complete)
                self.complete.pack(fill=tk.X, side=tk.TOP, expand=1)
            else:
                self.running = tk.Label(si, **self.not_running)
                self.running.pack(fill=tk.X, side=tk.TOP, expand=1)
                self.complete = tk.Label(si, **self.race_complete)
                self.complete.pack(fill=tk.X, side=tk.TOP, expand=1)


    def update(self, new_race=True):
        idx = self.idx
        parent = self.parent
        time_display = self.parent.
        if parent.race_ready[idx]:
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
            if parent.race_running[idx]:
                disable_navigation()
                self.running.config(**self.race_running)
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
                 parent: RaceManagerGUI):
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
                                                   **race_time_default)
        else:
            self.race_time_display = tk.Label(res_frm, bg=colors[idx], font=large_font,
                                               **race_time_default)
        self.race_time_display.pack(fill=tk.BOTH, expand=1)
        self.placement_display = tk.Label(res_frm, bg=colors[idx], font=large_font,
                                           **placement_default)
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
    def __init__(self,
                 parent: RaceManagerGUI):
        global widths, large_font
        self.parent = parent
        tc = tk.Frame(parent.window, width=widths["Times Column"])
        w = tk.Label(tc, text="Times", font=large_font)
        w.pack(fill=tk.X)
        rc = RaceSelector(tc, parent)
        rc.pack(fill=tk.X)
        self.race_times = [RaceTimes(tc, ri, parent) for ri in range(parent.n_lanes)]
        for rt in self.race_times:
            rt.frame.pack(fill=tk.BOTH, expand=1)

    def reset_race_time_display(self, idx):
        self.race_times[idx].reset_race_time_display()

    def update_race_time_display(self, idx):
        self.race_times[idx].update_race_time_display()

    def reset_race_placement_display(self, idx):
        self.race_times[idx].reset_placement_display()

    def update_race_placement_display(self, idx):
        self.race_times[idx].update_placement_display()


def Race_Column(parent, title, chips):
    global widths
    rc = tk.Frame(parent, width=widths["Race Column"])
    w = tk.Label(rc, text=title, font=large_font)
    w.pack(fill=tk.X)
    bc = tk.Frame(rc, height=widths["Top Spacer"])
    cl = tk.Label(bc, text="00", font=("Serif", 18))
    cl.pack(fill=tk.X)
    bc.pack(fill=tk.X)
    for j in range(4):
        rid = tk.Label(rc, bg=colors[j], **chips[j])
        rid.pack(fill=tk.BOTH, expand=1)
    return rc


def Update_Race_Column(column, chips, race_number):
    children = column.winfo_children()
    for idx in range(4):
        children[2 + idx].config(**chips[idx])
    column_label = children[1].winfo_children()
    column_label[0].config(text="#{}".format(race_number))



def Controls_Row(parent):
    global navigation_buttons
    cr = tk.Frame(parent, height=40)
    fb = tk.Button(cr, text="Move Back", command=goto_prev_race)
    fb.pack(side=tk.LEFT)
    navigation_buttons['Move Back'] = fb
    ab = tk.Button(cr, text="Accept Results", command=accept_results)
    ab.pack(side=tk.LEFT)
    bb = tk.Button(cr, text="Move Forward", command=goto_next_race)
    bb.pack(side=tk.LEFT)
    navigation_buttons['Move Forward'] = bb
    return cr





class RaceManagerGUI:
    window_size = "1850x1024"
    lane_colors = ["#1167e8", "#e51b00", "#e5e200", "#7fd23c"]
    n_lanes = 4
    timer_coms: TimerComs = None
    running = True
    times_column: TimesColumn = None
    clock_rate = 2000.0
    race_count: List[int] = []
    placements: List[int] = []


    def __init__(self,
                 hosts_file_name: str = None,
                 event_file_name: str = None,
                 log_file_name: str = None):
        self.event = Event(event_file_name, log_file_name, self.n_lanes)

        self.window = tk.Tk()
        window.title("Pack 402 Pinewood Derby")
        window.geometry(self.window_size)

        if hosts_file_name is not None:
            self.timer_coms = TimerComs(
                parent=self.window,
                hosts_file=hosts_file_name
            )

        self.add_menu_bar(self.window)

        self.race_count = [0 for _ in range(self.n_lanes)]
        self.placements = [-1 for _ in range(self.n_lanes)]

        self.main_frame = tk.Frame(self.window, bg='black')
        self.main_frame.pack(fill=tk.BOTH, expand=1)

        self.load_main_frame()

        self.controls_row = self.controls_row(window)

        # Add window delete callback
        self.window.protocol("WM_DELETE_WINDOW", self.close_manager)

    def mainloop(self):
        self.window.mainloop()

    def add_menu_bar(self):
        menu = tk.Menu(self.window)
        self.window.config(menu=menu)
        file_menu = tk.Menu(menu)
        file_menu.add_command(label="Generate Report", command=self.event.generate_report)
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
        global racing_column, on_deck_column, next_up_column1
        self.times_column = TimesColumn(mf)
        self.times_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        race_num = event.current_race_idx
        racing_column = RaceColumn(mf, "Racing", event.get_chips_for_race(race_num))
        racing_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        on_deck_column = RaceColumn(mf, "On Deck",
                                     event.get_chips_for_race(race_num + 1))
        on_deck_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        next_up_column1 = RaceColumn(mf, "Next Up",
                                      event.get_chips_for_race(race_num + 2))
        next_up_column1.pack(side=tk.LEFT, fill=tk.BOTH, expand=1):

    def reset_race_times_display(self, idx):
        self.times_column.reset_race_time_display(idx)

    def update_race_times_display(self, idx):
        self.times_column.update_race_time_display(idx)

    def reset_race_placement_display(self, idx):
        self.times_column.reset_race_placement_display(idx)

    def update_race_placement_display(self, idx):
        self.times_column.update_race_placement_display(idx)


def update_race_display(new_race=True):
    global track_status_indicator, event, racing_column, on_deck_column, next_up_column1
    try:
        status_indicators[0].winfo_children()
    except AttributeError:
        return
    for idx, tsi in enumerate(status_indicators):
        update_tsi_children(tsi, idx, new_race=new_race)
    race_idx = event.current_race_idx
    Update_Race_Column(racing_column, event.get_chips_for_race(race_idx), race_idx)
    if race_idx + 1 > event.last_race:
        race_idx = event.last_race
    else:
        race_idx += 1
    Update_Race_Column(on_deck_column, event.get_chips_for_race(race_idx), race_idx)
    if race_idx + 1 > event.last_race:
        race_idx = event.last_race
    else:
        race_idx += 1
    Update_Race_Column(next_up_column1, event.get_chips_for_race(race_idx), race_idx)


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
    global req_win, event
    req_win.destroy()
    record_race_results(accept=True)  # TODO See if this can be removed. LRB
    # TODO March 7 2020
    send_reset_to_track()
    update_race_display()


def just_move_on():
    global req_win, event
    req_win.destroy()
    event.goto_next_race()
    send_reset_to_track()
    update_race_display()


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
    global event, race_needs_written
    if race_needs_written:
        record_race_results(accept=True)
        race_needs_written = False
    event.goto_prev_race()
    update_race_selector(True)
    if event.current_race.accepted_result_idx >= 0:
        update_race_display(new_race=False)
    else:
        update_race_display(new_race=True)


def goto_next_race():
    global event, race_needs_written
    if race_needs_written:
        record_race_results(accept=True)
        race_needs_written = False
    event.goto_next_race()
    update_race_selector(True)
    if event.current_race.accepted_result_idx >= 0:
        update_race_display(new_race=False)
    else:
        update_race_display(new_race=True)


def accept_results():
    global event, race_complete, active_race_idx, race_ready, race_running, race_needs_written
    race_needs_written = True
    if all(race_complete):
        send_reset_to_track(accept=True)
        update_race_display(new_race=True)
    elif any(race_complete):
        request_to_post_results()
    else:
        print("{} {} {}".format(race_ready, race_running, race_complete))
        event.goto_next_race()
        send_reset_to_track()
        update_race_display(new_race=False)


def find_race_count(data):
    print(data)
    num = data.decode('utf-8').split(":")[1][:-1]
    count = int(num)
    print("Count = {}, Seconds = {}".format(count, np.float(count) / 2000.0))
    return count


def show_results():
    global race_count, event, placements
    # Find which lanes were 1st, 2nd, 3rd, and 4th
    ranks = np.argsort(race_count)
    place = 0;
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
    update_race_display(new_race=False)


def record_race_results(accept=False):
    global event, race_log_file, race_count, active_race_idx
    global block_loading_previous_times
    print("record_race_results is called")
    if event.current_race_log_idx is not active_race_idx:
        print("It looks like we are not current {} != {}.".format(
            event.current_race_log_idx, active_race_idx))
        # These results are already recorded
        if accept:
            # We need to change which race is accepted
            for idx, v in enumerate(event.current_race.race_number):
                if v == active_race_idx:
                    break
            if event.current_race.race_number[idx] != active_race_idx:
                idx = -1
            print("idx={},copying results".format(idx))
            event.current_race.post_results_to_racers(i=idx)
            times = [np.float(x) / clock_rate for x in race_count]
            tmp_idx = event.current_race_log_idx
            event.current_race_log_idx = active_race_idx
            event.record_race_results(times, race_count, accept)
            event.current_race_log_idx = tmp_idx
            update_race_selector(show_accepted_race=False)
            return
        else:
            return
    if any(race_count):
        times = [np.float(x) / clock_rate for x in race_count]
        event.record_race_results(times, race_count, accept)
        active_race_idx = event.current_race_log_idx
        block_loading_previous_times = True
        update_race_selector(show_accepted_race=False)
        block_loading_previous_times = False


# Socket Stuff
if __name__ == "__main__":
    post_placements = True
    cli_args = parser.parse_args()

    rm_gui = RaceManagerGUI(
        event_file_name=cli_args.event_file,
        log_file_name=cli_args.log_file,
        hosts_file_name=cli_args.hosts_file
    )

    window = initialize_window(event)

    timer_coms = TimerComs(window,
                           hosts_file=cli_args.hosts_file)

    timer_coms.connect()

    while program_running:
        "Waiting for data from track hosts."
        ready_sockets, open_sockets, error_sockets = select.select(sockets_, sockets_, sockets_, 0.05)
        open_conn = [4]
        if len(open_sockets) != 4:
            print("Socket disconnection detected.")
            for i in range(4):
                if sockets_[i] in open_sockets:
                    open_conn[i] = True
                else:
                    open_conn[i] = False
                    print("Disconnect on socket {}".format(i))
            update_race_display(new_race=False)
            connect_to_track_hosts()
        for ready_socket in ready_sockets:
            data = get_data_from_socket(ready_socket)
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
                update_race_selector(show_accepted_race=False)
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
                update_race_selector(show_accepted_race=False)
                update_race_display(new_race=True)
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
                    enable_navigation()
            else:
                if len(data) == 0:  # indicative of socket failure
                    connect_to_track_hosts()
                else:
                    print(data)

        if all(race_complete) and post_placements:
            show_results()
            post_placements = False

        if len(ready_sockets) > 0:
            update_race_display(new_race=False)

        window.update_idletasks()
        window.update()
