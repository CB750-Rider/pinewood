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
import numpy as np
import tkinter as tk
from tkinter import filedialog
import time
import select
from race_event import Event, Heat, Racer
import argparse

description = "A Graphical Interface for setting up Pinewood Derby Races"

parser = argparse.ArgumentParser(description=description)
parser.add_argument('--hosts_file', help='A file with the ip and port addresses of the lane timers (hosts).',
                    default='lane_hosts.csv')
parser.add_argument('--event_file', help='A file with the event plan listed.',
                    default='RacePlan.csv')
parser.add_argument('--log_file', help='The name of a file to save race times to.',
                    default='derby_race_log.csv')


class RegistrationWindow:
    def __init__(self,
                 top: tk.Tk,
                 event: Event):
        self.top = top
        self.event = event

        self.button_pane = ButtonPane(self, event)

        self.racer_list = RacerList(self)

        self.heat_list = HeatList(self, self.racer_list)

        self.active_heat = None

        self.set_heat_pane()

        self.check_racer_pane()

    def mainloop(self):
        self.top.mainloop()

    def check_racer_pane(self):
        cur_idx = self.heat_list.get_selected_heat_index()
        if cur_idx != self.active_heat:
            self.active_heat = cur_idx
            self.racer_list.set_racers_from_heat(self.active_heat)
        self.top.after(50, self.check_racer_pane)

    def set_heat_pane(self):
        self.heat_list.update_heat_list(self.event.heats)

    def get_racer_by_index(self, index):
        heat_index = self.heat_list.get_selected_heat_index()
        if heat_index == -1:
            " This is the trickier part "
            for heat in self.event.heats:
                try:
                    racer = heat.racers[index]
                except IndexError:
                    index -= len(heat.racers)
                else:
                    return racer
        else:
            heat = self.event.heats[heat_index]
            return heat.racers[index]


class RacerDialog:
    def __init__(self,
                 parent: RegistrationWindow,
                 racer: Racer = None):
        self.top = parent.top
        self.event = parent.event
        self.parent = parent
        self._window = tk.Toplevel(parent.top)
        self.new_racer = racer

        heat_idx = parent.heat_list.get_selected_heat_index()
        if heat_idx < 0:
            text = tk.Label(self._window, text="Please, select a heat before attempting to add a racer",
                            font=("Serif", 14))
            text.pack()
        else:
            self.heat = parent.event.heats[heat_idx]
            if racer is None:
                racer = Racer(name="<Name>", rank="", heat_name=self.heat.name, heat_index=heat_idx)
            text = tk.Label(self._window, text="Write the code for RacerDialog!",
                            font=("Serif", 14))
            text.pack()


class HeatDialog:
    def __init__(self,
                 parent: RegistrationWindow,
                 heat: Heat = None):
        self.top = parent.top
        self.parent = parent
        self.event = parent.event
        self._window = tk.Toplevel(self.top)

        if heat is None:
            heat = Heat(name="<Heat Name>")

        self.heat = heat
        self.hidden_frame = tk.Frame(self._window)
        self.hidden_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = tk.Frame(self._window)
        top_frame.pack(fill=tk.BOTH, expand=True)

        label = tk.Label(top_frame, text="Heat Name")
        label.pack(side=tk.LEFT)
        self.name = tk.Entry(top_frame, width=50)
        self.name.pack(side=tk.LEFT)
        self.name.insert(0, heat.name)

        label = tk.Label(top_frame, text="Grade")
        label.pack(side=tk.LEFT)
        self.grade = tk.Entry(top_frame, width=2)
        self.grade.pack(side=tk.LEFT)
        self.grade.insert(0, str(heat.ability_rank))

        bottom_frame = tk.Frame(self._window)
        bottom_frame.pack(fill=tk.BOTH, expand=True)

        button = tk.Button(bottom_frame, text="Accept", command=self.accept)
        button.pack(side=tk.LEFT)

        button = tk.Button(bottom_frame, text="Cancel", command=self._window.destroy)
        button.pack(side=tk.RIGHT)

    def add_error(self, message):
        label = tk.Label(self.hidden_frame, text=message, fg="red", bg="black")
        label.pack(fill=tk.BOTH, expand=True)

    def accept(self):
        name = self.name.get()
        grade = self.grade.get()
        self.heat.name = name
        self.heat.ability_rank = int(grade)

        if self.event.heat_index(heat=self.heat) < 0:
            try:
                self.event.add_heat(self.heat)
            except ValueError:
                self.add_error("Unable to add a heat with this name. Is there another heat with the same name?")
                return

        self.event.sort_heats()

        self.parent.set_heat_pane()
        self._window.destroy()


class ButtonPane:
    def __init__(self,
                 parent: RegistrationWindow,
                 event: Event):
        top = parent.top
        self.parent = parent
        self._button_frame = tk.Frame(top)
        self._button_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.top = top
        self.event = event

        add_racer_btn = tk.Button(self._button_frame, text="Add Racer", command=self.add_racer)
        add_racer_btn.pack()

        add_heat_btn = tk.Button(self._button_frame, text="Add Heat", command=self.add_heat)
        add_heat_btn.pack()

    def add_racer(self):
        RacerDialog(self.parent)
        self.parent.check_racer_pane()

    def add_heat(self):
        HeatDialog(self.parent)
        self.parent.set_heat_pane()


class RacerList:
    def __init__(self, parent: RegistrationWindow):
        top = parent.top
        self.top = top
        self.parent = parent
        self._outer_frame = tk.Frame(top)
        self._outer_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT)
        title = tk.Label(self._outer_frame, text="Racers", font=('Serif', 22))
        title.pack(expand=True, fill=tk.X)
        self.list_box = tk.Listbox(self._outer_frame, selectmode=tk.SINGLE)
        self.list_box.pack(expand=True, fill=tk.BOTH)

        edit_button = tk.Button(self._outer_frame, text="Edit", font=('Serif', 16),
                                command=self.edit_selected_racer)
        edit_button.pack(fill=tk.X, pady=2)

        delete_button = tk.Button(self._outer_frame, text="Delete", font=('Serif', 16),
                                  command=self.delete_selection)
        delete_button.pack(fill=tk.X, pady=16)

        self.set_racers_from_heat(-1)

    def set_racers_from_heat(self, heat_idx):
        self.list_box.delete(0, tk.END)
        if heat_idx < 0:
            for heat in self.parent.event.heats:
                self.add_racers_from_heat(heat)
        else:
            self.add_racers_from_heat(self.parent.event.heats[heat_idx])

    def add_racers_from_heat(self, heat: Heat):
        for racer in heat.racers:
            self.list_box.insert(tk.END, racer.name)

    def get_selected_racer_index(self):
        selected_value = self.list_box.curselection()
        if len(selected_value) > 0:
            return selected_value[0]
        else:
            return -1

    def delete_selection(self):
        idx = self.get_selected_racer_index()
        if idx >= 0:
            print("Write the delete racer selection funciton.")

    def edit_selected_racer(self):
        idx = self.get_selected_racer_index()
        if idx >= 0:
            racer = self.parent.get_racer_by_index(idx)
            RacerDialog(self.top, self.parent.event, racer=racer)


class HeatList:
    def __init__(self, parent: RegistrationWindow, racer_list: RacerList):
        top = parent.top
        self.parent = parent
        self.top = top
        self._outer_frame = tk.Frame(top)
        self._outer_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT)
        title = tk.Label(self._outer_frame, text="Heats", font=('Serif', 22))
        title.pack(expand=True, fill=tk.X)
        self.list_box = tk.Listbox(self._outer_frame, selectmode=tk.SINGLE)
        self.list_box.pack(expand=True, fill=tk.BOTH)

        edit_button = tk.Button(self._outer_frame, text="Edit", font=('Serif', 16),
                                command=self.edit_selected_heat)
        edit_button.pack(fill=tk.X, pady=2)

        delete_button = tk.Button(self._outer_frame, text="Delete", font=('Serif', 16),
                                  command=self.delete_selection)
        delete_button.pack(fill=tk.X, pady=16)

        self.update_heat_list()

    def update_heat_list(self, heats=None):
        self.list_box.delete(0, tk.END)
        self.list_box.insert(tk.END, "All Racers")
        for heat in self.parent.event.heats[:-1]:  # The last heat should stay hidden
            self.list_box.insert(tk.END, heat.name)

    def get_selected_heat_index(self):
        selected_value = self.list_box.curselection()
        if len(selected_value) > 0:
            return selected_value[0] - 1
        else:
            return -1

    def delete_selection(self):
        idx = self.get_selected_heat_index()
        if idx >= 0:
            print("Write the delete selection funciton.")

    def edit_selected_heat(self):
        idx = self.get_selected_heat_index()
        if idx >= 0:
            heat = self.parent.event.heats[idx]
            HeatDialog(self.parent, heat=heat)


if __name__ == "__main__":
    post_placements = True
    cli_args = parser.parse_args()

    event = Event(event_file=cli_args.event_file,
                  log_file=cli_args.log_file)

    main_window = RegistrationWindow(tk.Tk(), event)

    main_window.mainloop()
