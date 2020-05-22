#!/usr/bin/python3
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
import socket
import sys
import numpy as np
import tkinter as tk
from tkinter import filedialog
import time
import select
from race_manager.DerbyTimer import Race_Event

host = ['', '', '', '']
port = [0, 0, 0, 0]
stringlen = 64
reset_default_lane = 3
colors = ["#1167e8", "#e51b00", "#e5e200", "#7fd23c"]
window = []
window_size = "1850x1024"
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
hostsfile = "lane_hosts.csv"
logfile = "derby_race_log.csv"
eventfile = "RacePlan.csv"
race_ready = [False, False, False, False]  # "Yellow LED"
race_complete = [True, True, True, True]
race_running = [False, False, False, False]  # "Green LED"
reset_msg = "<reset>\n".encode('utf-8')
s = [[], [], [], []]  # Socket connections
s_conn = [False, False, False, False]  # Socket connection flags
clock_rate = 2000.0
small_font = ("Serif", 12)
med_font = ("Serif", 16)
large_font = ("Serif", 22)
program_running = True
race_needs_written = False
block_loading_previous_times = False
race_time_default = {"text": "0.000", "fg": "gray"}
placement_default = {"text": "Ready", "fg": "gray"}
placement_settings = [{"text": "1st", "fg": "#ff9600", "bg": "#000000"},
                      {"text": "2nd", "fg": "#000000"},
                      {"text": "3rd", "fg": "#000000"},
                      {"text": "4th", "fg": "#000000"}]
status_indicator_options = {"Ready to Race": {"text": "Ready to Race",
                                              "bg": "#fff600",
                                              "fg": "#000000",
                                              "borderwidth": 3,
                                              "relief": "raised",
                                              "font": med_font},
                            "Not Ready": {"text": "Not Ready",
                                          "fg": "#565726",
                                          "bg": "#7e7400",
                                          "borderwidth": 3,
                                          "relief": "sunken",
                                          "font": med_font},
                            "Race Running": {"text": "Race Running",
                                             "fg": "#000000",
                                             "bg": "#00ff2a",
                                             "borderwidth": 3,
                                             "relief": "raised",
                                             "font": med_font},
                            "Not Running": {"text": "Not Running",
                                            "fg": "#21ae39",
                                            "bg": "#027415",
                                            "borderwidth": 3,
                                            "relief": "sunken",
                                            "font": med_font},
                            "Race Complete": {"text": "Race Complete",
                                              "fg": "#000000",
                                              "bg": "#ff0000",
                                              "borderwidth": 3,
                                              "relief": "raised",
                                              "font": med_font},
                            "Not Complete": {"text": "Not Complete",
                                             "fg": "#b50d0d",
                                             "bg": "#660101",
                                             "borderwidth": 3,
                                             "relief": "sunken",
                                             "font": med_font}}


# GUI STUFF
def close_manager():
    global program_running, s, race_needs_written, event

    print("close manager called")
    if race_needs_written:
        record_race_results()
        race_needs_written = False
    print("Final race written to file.")
    event.close_log_file()
    for i in range(4):
        s[i].shutdown(socket.SHUT_RDWR);
    program_running = False


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


def update_race_time_display(idx):
    global race_time_displays, race_count, clock_rate, event
    if race_count[idx]:
        final_time = race_count[idx] / clock_rate
        race_time_displays[idx].config(text="{0:.3f}".format(final_time), fg='#000000')
    else:
        race_time_displays[idx].config(**race_time_default)


def reset_race_time_display(idx):
    global race_time_displays
    race_time_displays[idx].config(race_time_default)


def update_placement_display(idx):
    global placement_displays, placements
    if placements[idx] >= 0:
        placement_displays[idx].config({"bg": colors[idx]})
        placement_displays[idx].config(placement_settings[placements[idx]])
    else:
        placement_displays[idx].config({"bg": colors[idx]})
        placement_displays[idx].config(placement_default)


def reset_placement_display(idx):
    global placement_displays
    placement_displays[idx].config({"bg": colors[idx]})
    placement_displays[idx].config(placement_default)


def disable_navigation():
    global navigation_buttons
    navigation_buttons["Move Forward"].configure(state='disabled')
    navigation_buttons["Move Back"].configure(state='disabled')


def enable_navigation():
    global navigation_buttons
    navigation_buttons["Move Forward"].configure(state='normal')
    navigation_buttons["Move Back"].configure(state='normal')


def update_tsi_children(tsi, idx, new_race=True):
    children = tsi.winfo_children()
    if race_ready[idx]:
        children[0].config(**status_indicator_options["Ready to Race"])
        children[1].config(**status_indicator_options["Not Running"])
        children[2].config(**status_indicator_options["Not Complete"])
        if new_race:
            reset_race_time_display(idx)
            reset_placement_display(idx)
        else:
            update_race_time_display(idx)
            update_placement_display(idx)
    else:
        children[0].config(**status_indicator_options["Not Ready"])
        if race_running[idx]:
            disable_navigation()
            children[1].config(**status_indicator_options["Race Running"])
            children[2].config(**status_indicator_options["Not Complete"])
            if new_race:
                reset_race_time_display(idx)
                reset_placement_display(idx)
            else:
                update_race_time_display(idx)
                update_placement_display(idx)
        else:
            children[1].config(**status_indicator_options["Not Running"])
            children[2].config(**status_indicator_options["Race Complete"])
            update_race_time_display(idx)
            update_placement_display(idx)


def track_status_indicator(parent, background, idx):
    global race_ready, race_running, status_indicator_options
    si = tk.Frame(parent, bg=background)
    print("Updating the track status")
    if (race_ready[idx]):
        w = tk.Label(si, **status_indicator_options["Ready to Race"])
        w.pack(fill=tk.X, side=tk.TOP, expand=1)
        x = tk.Label(si, **status_indicator_options["Not Running"])
        x.pack(fill=tk.X, side=tk.TOP, expand=1)
        y = tk.Label(si, **status_indicator_options["Not Complete"])
        y.pack(fill=tk.X, side=tk.TOP, expand=1)
    else:
        w = tk.Label(si, **status_indicator_options["Not Ready"])
        w.pack(fill=tk.X, side=tk.TOP, expand=1)
        if (race_running[idx]):
            x = tk.Label(si, **status_indicator_options["Race Running"])
            x.pack(fill=tk.X, side=tk.TOP, expand=1)
            y = tk.Label(si, **status_indicator_options["Not Complete"])
            y.pack(fill=tk.X, side=tk.TOP, expand=1)
        else:
            x = tk.Label(si, **status_indicator_options["Not Running"])
            x.pack(fill=tk.X, side=tk.TOP, expand=1)
            y = tk.Label(si, **status_indicator_options["Race Complete"])
            y.pack(fill=tk.X, side=tk.TOP, expand=1)
    return si


def Race_Times(parent, idx):
    global colors, status_indicators, placements, event, race_time_displays
    rt = tk.Frame(parent)
    w = tk.Label(rt, text="Lane {0}".format(idx + 1),
                 bg=colors[idx], font=large_font)
    w.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
    status_indicators[idx] = track_status_indicator(rt, colors[idx], idx)
    status_indicators[idx].pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
    res_frm = tk.Frame(rt)
    if (event.current_race.times):  # If times were posted
        if (event.current_race.accepted_result_idx >= 0):  # show the accepted race
            times = event.current_race.times[event.current_race.accepted_result_idx]
            race_time_displays[idx] = tk.Label(res_frm, bg=colors[idx],
                                               font=large_font, fg="#000000", text="{0:.3f}".format(times[idx]))
        else:
            race_time_displays[idx] = tk.Label(res_frm, bg=colors[idx], font=large_font,
                                               **race_time_default)
    else:
        race_time_displays[idx] = tk.Label(res_frm, bg=colors[idx], font=large_font,
                                           **race_time_default)
    print(race_time_displays[idx])
    race_time_displays[idx].pack(fill=tk.BOTH, expand=1)
    placement_displays[idx] = tk.Label(res_frm, bg=colors[idx], font=large_font,
                                       **placement_default)
    placement_displays[idx].pack(fill=tk.BOTH, expand=1)
    res_frm.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
    rt.pack(fill=tk.BOTH, expand=1)
    return w


def Times_Column(parent):
    global widths, rt
    tc = tk.Frame(parent, width=widths["Times Column"])
    w = tk.Label(tc, text="Times", font=large_font)
    w.pack(fill=tk.X)
    rc = Race_Selector(tc)
    rc.pack(fill=tk.X)
    for ri in range(4):
        rt = Race_Times(tc, ri)
        rt.pack(fill=tk.BOTH, expand=1)
    return tc


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


def load_main_frame(mf, event):
    global times_column, racing_column, on_deck_column, next_up_column1
    times_column = Times_Column(mf)
    times_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
    race_num = event.current_race_idx
    racing_column = Race_Column(mf, "Racing", event.get_chips_for_race(race_num))
    racing_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
    on_deck_column = Race_Column(mf, "On Deck",
                                 event.get_chips_for_race(race_num + 1))
    on_deck_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
    next_up_column1 = Race_Column(mf, "Next Up",
                                  event.get_chips_for_race(race_num + 2))
    next_up_column1.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)


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


def add_menu_bar(parent):
    menu = tk.Menu(parent)
    parent.config(menu=menu)
    file_menu = tk.Menu(menu)
    file_menu.add_command(label="Generate Report", command=generate_report)
    file_menu.add_command(label="Exit", command=close_manager)
    menu.add_cascade(label="File", menu=file_menu)
    window_menu = tk.Menu(menu)
    window_menu.add_command(label="Race Viewer", command=open_race_view_window)
    window_menu.add_command(label="Heat Viewer", command=open_heat_view_window)
    window_menu.add_command(label="""Racer Viewer""",
                            command=open_racer_view_window)
    menu.add_cascade(label="Windows", menu=window_menu)


def initialize_window(event):
    global window
    window = tk.Tk()
    window.title("Pack 402 Pinewood Derby")
    window.geometry(window_size)
    add_menu_bar(window)
    main_frame = tk.Frame(window, bg='black')
    main_frame.pack(fill=tk.BOTH, expand=1)
    load_main_frame(main_frame, event)
    controls_row = Controls_Row(window)
    controls_row.pack()
    # Add window delete callback
    window.protocol("WM_DELETE_WINDOW", close_manager)
    window.update()


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
    rv = event.print_status_report(report_file_name)
    if (rv == 0):
        di = tk.Toplevel()
        m = tk.Label(di, text="File Written.", height=6, width=24)
        m.pack()
        di.protocol("WM_DELETE_WINDOW", di.destroy)
        di.update()


def goto_prev_race():
    global event, race_needs_written
    if race_needs_written:
        record_race_results(accept=True)
        race_needs_written=False
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
        race_needs_written=False
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
def set_host_and_port():
    global hostsfile, host, port
    with open(hostsfile) as fp:
        for line in fp:
            laneNumber, hostAddress, hostPort = line.split(',')
            li = int(laneNumber) - 1
            host[li] = hostAddress
            port[li] = int(hostPort)


def connect_to_track_hosts():
    global s, s_conn, window
    rb = [[], [], [], []]
    for i, sckt in enumerate(s):
        if s_conn[i]:
            s_conn[i] = False
            sckt.shutdown(socket.SHUT_RDWR)

    popup = tk.Toplevel()
    popup.wm_title("Connection To Track")
    db = tk.Label(popup)
    db.pack()
    for i in range(4):
        rb[i] = tk.Label(popup, text="{}:{}".format(
            host[i], port[i], fg='#050505'))
        rb[i].pack()
    while not all(s_conn):
        for i in range(4):
            if not s_conn[i]:
                db.config(text="""Attempting to connect to
                              {}:{}""".format(host[i], port[i]))
                popup.update()
                print("Attempting to connect to {}:{}".format(host[i], port[i]))
                try:
                    s[i].connect((host[i], port[i]))
                except:
                    continue
            s_conn[i] = True
            print("Connection from {}:{} established.".format(host[i], port[i]))
            rb[i].config(**{'fg': '#18ff00', 'bg': '#000000'})
            time.sleep(0.1)
        if not all(s_conn):
            print("Waiting 5 seconds and re-attempting connection.")
            db.config(text="""Waiting 5 seconds and re-attempting
                      connection.""")
            time.sleep(5)
            window.update_idletasks()
            window.update()
    popup.destroy()


def send_reset_to_track(lane=reset_default_lane, accept=False):
    global s, race_needs_written, race_running
    race_running = [False, False, False, False]
    enable_navigation()
    if race_needs_written:
        record_race_results(accept=accept)
        race_needs_written = False
    print("Sending Reset to the Track")
    s[lane].sendall("<reset>".encode('utf-8'))


def get_data_from_socket(sckt):
    data = sckt.recv(64)
    return data


if __name__ == "__main__":
    post_placements = True
    if len(sys.argv) == 1:
        print("""Using the hosts in {}, the event in {}, and outputing to
              {}.""".format(hostsfile, eventfile, logfile))
        print("""Pass a hosts file, event file and log file name (in that order) if you would 
              like to use different files.""")
    elif len(sys.argv) == 2:
        hostsfile = sys.argv[1]
    elif len(sys.argv) == 3:
        hostsfile = sys.argv[1]
        eventfile = sys.argv[2]
    elif len(sys.argv) == 4:
        hostsfile = sys.argv[1]
        eventfile = sys.argv[2]
        logfile = sys.argv[3]
    else:
        hostsfile = sys.argv[1]
        eventfile = sys.argv[2]
        logfile = sys.argv[3]
        print("Only the first three arguments are used")

    set_host_and_port()

    event = Race_Event.event(eventfile, logfile)

    initialize_window(event)

    for i in range(4):
        s[i] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    connect_to_track_hosts()

    while program_running:
        "Waiting for data from track hosts."
        ready_sockets, open_sockets, error_sockets = select.select(s, s, s, 0.05)
        open_conn=[4]
        if len(open_sockets) != 4:
            print("Socket disconnection detected.")
            for i in range(4):
                if s[i] in open_sockets:
                    open_conn[i] = True
                else:
                    open_conn[i] = False
                    print("Dissconnnect on socket {}".format(i))
            update_race_display(new_race=False)
            connect_to_track_hosts()
        for sckt in ready_sockets:
            data = get_data_from_socket(sckt)
            s_idx = -1
            for i, sc in enumerate(s):
                if sckt == sc:
                    s_idx = i
            if (s_idx == -1):
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
                active_race_idx = event.current_race_log_idx # Force a jump to the new race when started
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
