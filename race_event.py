"""
race_event.py

Class file for managing race events. These classes
include:

racer:      A class for holding the information for a racer

heat:       A class for holding a group of racers who are compeating against
each other. Heats can be any size, and each race may involve racers from
multiple heats.

race:       A class for holding the information for a single race where one or
more racers go down the track.

event:      A class for holding all racers, heats, and races that comprise a
single event. 

Generally, the user will create an instance of an event, and populate that
event from a text file.

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
import numpy as np
import yaml
from typing import List

default_heat_name = "No_Heat"


# CLASS STUFF
class Racer:
    global default_heat_name

    def __init__(self,
                 car_number=0,
                 name="No_Name",
                 rank="No_Rank",
                 heat_name=default_heat_name,
                 heat_index=-1,
                 n_lanes=4,
                 car_status=None):
        self.name = name
        self.rank = rank
        self.n_lanes = n_lanes
        self.heat_name = heat_name
        self.index_in_heat = heat_index
        self.race_times = np.zeros(self.n_lanes)
        self.race_counts = np.zeros(self.n_lanes)
        self.race_plan_nums = np.zeros(self.n_lanes)
        self.race_log_nums = np.zeros(self.n_lanes)
        self.race_positions = np.zeros(self.n_lanes)
        self.car_number = car_number
        self.hist = {}
        if car_status is None:
            self.car_status = {
                'passed_weight': [False, 'less than 5 oz.'],
                'passed_length': [False, 'less than 7"'],
                'passed_height': [False, 'less than 3 1/2"'],
                'passed_underbody_clearance': [False, 'greater than 3/8"'],
                'passed_width': [False, 'less than 2 3/4"'],
                'wheel_diameter': [False, 'greater than 1.170"'],
                'wheel_base': [False, 'less than 4 3/4" (axle to axle)'],
                'passed_nose': [False, 'no notch'],
                'questions': {
                    'made_this_year': False,
                    'use_kit_nail': False,
                    'use_official_wheel': False,
                    'no_liquid_lubricant': False,
                    'no_loose_materials': False,
                    'no_wheel_bearings': False,
                    'no_wheel_washers': False,
                    'no_solid_axles': False,
                    'no_springs_or_shocks': False,
                    'no_removal_of_wheel_tread': False,
                    'no_rounding_of_outside_wheel_edge': False,
                    'no_rounding_of_inside_wheel_edge': False,
                    'no_rounding_of_the_inside_wheel_hub': False,
                    'no_bore_or_cone_for_the_wheel_hub': False,
                    'no_dome_on_outside_hub': False,
                    'no_wheel_reshaping': False,
                    'no_nail_groove': False,
                    'no_graphite_paint_on_nail': False
                },
                'notes': ''
            }
        else:
            self.car_status = car_status

    def to_dict(self):
        return {
            'name': self.name,
            'rank': self.rank,
            'race_times': self.race_times,
            'race_counts': self.race_counts,
            'race_plan_nums': self.race_plan_nums,
            'race_log_nums': self.race_log_nums,
            'race_positions': self.race_positions,
            'heat_name': self.heat_name,
            'heat_index': self.heat_index,
            'car_status': self.car_status
        }

    def from_dict(self, dict):
        if 'name' in dict.keys():
            self.name = dict['name']
        if 'rank' in dict.keys():
            self.rank = dict['rank']
        if 'race_times' in dict.keys():
            self.race_times = dict['race_times']
        if 'race_counts' in dict.keys():
            self.race_counts = dict['race_counts']
        if 'race_plan_nums' in dict.keys():
            self.race_plan_nums = dict['race_plan_nums']
        if 'race_log_nums' in dict.keys():
            self.race_log_nums = dict['race_log_nums']
        if 'race_positions' in dict.keys():
            self.race_positions = dict['race_positions']
        if 'heat_name' in dict.keys():
            self.heat_name = dict['heat_name']
        if 'heat_index' in dict.keys():
            self.index_in_heat = dict['heat_index']
        if 'car_status' in dict.keys():
            self.car_status = dict['car_status']

    def chip(self):
        chip = {"text": "{}:{}".format(self.name, self.heat_name), "font": ("Serif", 16)}
        return chip

    def set_heat(self, heat_name, heat_index):
        self.clear_races()  # Must do this BEFORE setting the new heat name!
        self.heat_name = heat_name
        self.heat_index = heat_index

    def post_result(self, lane_idx, race_log_num, race_plan_num, time,
                    count, position):
        self.race_log_nums[lane_idx] = race_log_num
        self.race_plan_nums[lane_idx] = race_plan_num
        self.race_times[lane_idx] = time
        self.race_counts[lane_idx] = count
        self.race_positions[lane_idx] = position

    def get_average(self):
        if any(self.race_times > 0.0):
            return np.mean(self.race_times[self.race_times > 0.0])
        else:
            return 0.0

    def get_worst(self):
        return np.max(self.race_times)

    def get_best(self):
        if any(self.race_times > 0.0):
            return np.min(self.race_times[self.race_times > 0.0])
        else:
            return 0.0

    def save_heat(self):
        self.hist[self.heat] = [self.race_log_nums, self.race_plan_nums,
                                self.race_times, self.race_positions]
    def clear_races(self):
        if self.get_worst() > 0.0:
            self.save_heat()
        self.race_times = np.zeros(self.n_lanes)
        self.race_log_nums = np.zeros(self.n_lanes)
        self.race_plan_nums = np.zeros(self.n_lanes)
        self.race_positions = np.zeros(self.n_lanes)

    def passed_inspection(self):
        for key in self.car_status.keys():
            if key == 'questions' or key == 'notes' or self.car_status[key]:
                continue
            return False
        for key in self.car_status['questions'].keys():
            if self.car_status['questions'][key]:
                continue
            return False
        return True


class Heat:
    def __init__(self,
                 name=default_heat_name,
                 racers: List[Racer] = [],
                 ability_rank=-1):
        self.name = name
        self.racers = racers
        for ri, racer in enumerate(racers):
            racer.set_heat(name, ri)
        # self.races = []
        self.ability_rank = ability_rank

    def add_racer(self, racer):
        if racer.heat_name != self.name:
            raise ValueError("Unable to add a racer to '{}' because their heat is '{}'".format(
                self.name, racer.heat_name
            ))
        for existing_racer in self.racers:
            if racer.name == existing_racer.name:
                raise ValueError(f"A racer named '{racer.name}' already exists in the {self.name} heat.")
        idx = len(self.racers)
        self.racers.append(racer)
        racer.set_heat(self.name, idx)

    def remove_racer(self, racer=None, racer_name=None):
        if racer is not None:
            for racer_idx, existing_racer in enumerate(self.racers):
                if existing_racer is racer:
                    self.racers.pop(racer_idx)
        elif racer_name is not None:
            for racer_idx, existing_racer in enumerate(self.racers):
                if existing_racer.name == racer_name:
                    self.racers.pop(racer_idx)
        else:
            raise ValueError("You must provide a racer or racer name to be removed.")

    def to_dict(self):
        racers = []
        for racer in self.racers:
            racers.append({
                'name': racer.name,
                'rank': racer.rank
            })
        return {
            'name': self.name,
            'racers': racers,
            'ability_rank': self.ability_rank
        }

    def add_race(self, racers, race_idx):
        # Racers are expected to be in order of lane number
        new_race = {"Race_Number": -1,
                    "Racers": racers,
                    "Times": self.times}
        self.races.insert(race_idx, new_race)

    def racer_index(self, racer=None, racer_name=None):
        if racer is None and racer_name is None:
            raise ValueError("When calling racer_index, you must provide either a racer or racer_name.")
        for racer_idx, each_racer in enumerate(self.racers):
            if racer is None:
                if racer_name == each_racer.name:
                    return racer_idx
            else:
                if racer is each_racer:
                    return racer_idx
        return -1

    def get_racer(self, racer_name):
        idx = self.racer_index(racer_name=racer_name)
        return self.racers[idx]

    #   def set_current_race_idx(self, idx):
    #       self.current_race_idx = idx

    def get_ranks(self):
        times = []
        names = []
        for racer in self.racers:
            times.append(racer.mean_time())
            names.append(racer.name)
        times = np.array(times)
        idx = np.argsort(times)
        return names[idx], times[idx]

    """def swap_racer(self, old_racer, new_racer):
        for i in range(len(self.racers)):
            if self.racers[i] == old_racer:
                self.racers[i] = new_racer
                self.racers[i].set_heat(self.name, new_racer.heat_index + 1)"""


class Race:
    def __init__(self, heats, racers, number, is_empty, n_lanes=4):
        self.heats = heats  # 1 x n_lanes
        self.racers = racers  # 1 x n_lanes
        self.plan_number = number  # The number from the race plan
        self.race_number = []  # The race number(s) from the track recorder
        self.times = []
        self.counts = []
        self.placements = []
        self.current_race = 0
        self.is_empty = is_empty  # 1 x n_lanes
        self.accepted_result_idx = -1  # The index of the race result that
        self.n_lanes = n_lanes
        # was accepted or -1 if none have been.

    def get_placements(self, times):
        return np.argsort(times) + 1

    def save_results(self, race_number, race_times, counts):
        # Post results to the current race number
        self.race_number.append(race_number)
        self.times.append(race_times)
        self.counts.append(counts)
        self.placements.append(self.get_placements(race_times))
        self.current_race = len(self.race_number) - 1

    def set_current_race(self, idx):
        if idx <= 0:
            self.current_race = 0
        elif idx >= len(self.race_times):
            self.current_race = len(self.race_times) - 1
        else:
            self.current_race = idx

    def post_results_to_racers(self, i=-1):
        if i < 0:
            i = self.current_race
        for lane_idx, racer, time, count, placement in zip(range(self.n_lanes), self.racers,
                                                           self.times[i], self.counts[i], self.placements[i]):
            racer.post_result(lane_idx, self.race_number[i], self.plan_number,
                              time, count, placement)
        self.accepted_result_idx = i

    def to_dict(self):
        entries = []
        for heat, racer, is_empty in zip(self.heats, self.racers, self.is_empty):
            entries.append({'racer': racer.name,
                            'heat': heat.name,
                            'empty_lane': is_empty})
        if self.accepted_result_idx < 0:
            out = {'planned_number': self.plan_number,
                   'entries': entries,
                   'accepted_result_idx': self.accepted_result_idx}
        else:
            self.set_current_race(self.accepted_result_idx)
            out = {'planned_number': self.plan_number,
                   'entries': entries,
                   'accepted_result_idx': self.accepted_result_idx,
                   'times': self.times,
                   'counts': self.counts,
                   'index_of_race(s)_in_log': self.race_number,
                   'placements': self.placements}
        return out

    def get_racer_list(self, out=[]):
        for racer in self.racers:
            if racer.heat_name == "Empty":
                out.append("")
            else:
                out.append(f"{racer.name} : {racer.heat_name}")
        return out


class Event:
    def __init__(self,
                 event_file=None,
                 log_file=None,
                 n_lanes=4,
                 verbose=False,
                 check_log_file=True):
        self.verbose = verbose
        self.n_lanes = n_lanes

        # Load the race data
        self.heats = [self.create_empty_lane_heat(), ]
        self.races = []
        self.current_race = None
        self.current_race_idx = 0  # Race plan race number
        self.current_race_log_idx = 0  # Race log race number
        self.last_race = 0
        self.plan_dictionary = None
        if event_file is not None:
            self.event_file_name = event_file
            self.load_races_from_file(event_file)

        # Load the log file that gives what part of the race has
        # already run
        # TODO Check the log file to make sure it matches the plan
        # TODO Start here with converting the log to YAML
        self.race_log_file = None
        if log_file is not None:
            self.read_log_file(log_file)

            # we will be recording race data as it comes in, so open
            # the logfile for appending.
            try:
                self.race_log_file = open(log_file, "a+")
            except OSError:
                print("Unable to open {} for writing.")
                pass
        if self.race_log_file is None and check_log_file:
            decision = input("Attempt to use the default log file? [Y/n]")
            if 'n' or 'N' in decision:
                try:
                    self.race_log_file = open("log_file.yaml", "a+")
                except OSError:
                    print("Unable to open {} for writing.".format("log_file.yaml"))
                    raise
            else:
                decision = input("Continue without logging? [y/N]")
                if 'y' or 'Y' in decision:
                    print("Continuing on.")
                    self.race_log_file = open("/dev/null", "w")
                else:
                    raise ValueError

    def create_empty_lane_heat(self,
                               ability_rank=100000000000000):
        racer_names = ["empty {}".format(i + 1) for i in range(self.n_lanes)]
        racers = [Racer(name=x, heat_name="Empty") for x in racer_names]
        return Heat(name="Empty",
                    racers=racers,
                    ability_rank=ability_rank)

    def load_races_from_file(self, file_name):
        try:
            f = open(file_name)
        except FileNotFoundError:
            print("Unable to open {} for reading.")
            return

        if '.yaml' in file_name:
            self.load_races_from_yaml(file_name)

        with open(file_name) as infile:
            for line in infile:
                if 'Heat' in line:
                    self.add_heat(create_heat_from_line(line))
            if self.verbose:
                self.print_heats()
            infile.seek(0, 0)
            for line in infile:
                if 'Race' in line:
                    self.races.append(
                        create_race_from_line(line, self.heats))
        try:
            self.current_race = self.races[0]
        except IndexError:
            self.current_race = None
        self.last_race = len(self.races) - 1

    def load_races_from_yaml(self, file_name):
        with open(file_name, 'r') as infile:
            self.plan_dictionary = yaml.safe_load(infile)
        for heat in self.plan_dictionary['heats']:
            self.add_heat(create_heat_from_dict(heat))
        if self.verbose:
            self.print_heats()
        if 'races' in self.plan_dictionary.keys():
            for race in self.plan_dictionary['races']:
                self.races.append(create_race_from_dict(race, self.heats))

    def print_heats(self):
        print("The race heats are as follows.")
        for heat in self.heats:
            print(heat.name, end=': ')
            racer_names = [x.name for x in heat.racers]
            print(racer_names)

    def heat_index(self, heat=None, heat_name=None):
        if heat is None and heat_name is None:
            raise ValueError("You must provide a heat or heat name to be removed.")
        elif heat is not None:
            for heat_idx, test in enumerate(self.heats):
                if heat is test:
                    return heat_idx
        else:
            for heat_idx, test, in enumerate(self.heats[:-1]):
                if test.name == heat_name:
                    return heat_idx
        return -1

    def racer_index(self, heat=None, heat_name=None, racer=None, racer_name=None):
        heat_idx = self.heat_index(heat=heat, heat_name=heat_name)
        if heat_idx < 0:
            return heat_idx
        return self.heats[heat_idx].racer_index(racer=racer, racer_name=racer_name)

    def add_heat(self, heat):
        for existing_heat in self.heats:
            if existing_heat.name == heat.name:
                raise ValueError(f"A heat with the name '{heat.name}' already exists.")
        self.heats.insert(-1, heat)

    def add_racer(self, racer):
        global default_heat_name
        was_added = False
        for heat in self.heats:
            if heat.name == racer.heat_name:
                was_added = heat.add_racer(racer)
                break
        if was_added is False:
            if racer.heat_name == default_heat_name:
                raise ValueError('No heat was found to match heat {} of {}. '.format(
                    racer.heat_name, racer.name) +
                                 'Since {} is the default heat name you may need to set the'.format(default_heat_name) +
                                 ' heat name of {}.'.format(racer.name))
            else:
                raise ValueError(
                    'No heat was found to match heat {} of {}. '.format(
                        racer.heat_name, racer.name) +
                    'If this is a new heat, then add the heat before adding the racer.')

    def add_race(self, race, location=-1):
        if location == 'next':
            self.races.insert(self.current_race_idx, race)
        elif location == 'end':
            self.races.append(race)
        else:
            self.races.insert(location, race)

    def remove_heat(self, heat=None, heat_name=None):
        removed = False
        if heat is None and heat_name is None:
            raise ValueError("You must provide a heat or heat name to be removed.")
        elif heat is not None:
            if heat is self.heats[-1]:
                print("You may not remove the empty heat.")
            for heat_idx, test in enumerate(self.heats[:-1]):
                if heat is test:
                    self.heats.pop(heat_idx)
                    removed = True
        else:
            if heat_name == 'Empty':
                print("You may not remove the empty heat.")
            for heat_idx, test, in enumerate(self.heats[:-1]):
                if test.name == heat_name:
                    self.heats.pop(heat_idx)
                    removed = True
        return removed

    def remove_racer(self, racer=None, racer_name=None):
        removed = False
        if racer is None and racer_name is None:
            raise ValueError("You must provide a racer or racer name to be removed.")
        elif racer is not None:
            for heat in self.heats:
                for racer_idx, test in enumerate(heat.racers):
                    if racer is test:
                        heat.racers.pop(racer_idx)
                        removed = True
        else:
            for heat in self.heats:
                for racer_idx, test in enumerate(heat.racers):
                    if racer_name == test.name:
                        heat.racers.pop(racer_idx)
                        removed = True
        return removed

    def remove_race(self, race=None, idx=None):
        removed = False
        if race is None and idx is None:
            raise ValueError("You must provide a race or index.")
        elif race is not None:
            for race_idx, test in enumerate(self.races):
                if test is race:
                    self.races.pop(race_idx)
                    removed = True
        else:
            if idx == -1:
                idx = -2
            self.races.pop(idx)
            removed = True
        return removed

    def record_race_results(self, times, counts, accept):
        race = self.current_race
        racers = self.current_race.racers
        if self.race_log_file:
            self.race_log_file.write("{},{}".format(
                self.current_race_log_idx,
                self.current_race_idx))
            for ri in range(self.n_lanes):
                self.race_log_file.write(",{},{},{}".format(
                    racers[ri].name, times[ri], counts[ri]))
            if accept:
                self.race_log_file.write(",Accepted\n");
            else:
                self.race_log_file.write(",NA\n");
        race.save_results(self.current_race_log_idx, times, counts)
        if accept:
            self.accept_results()
        self.current_race_log_idx += 1

    def print_status_report(self, fname):
        racer_names = []
        times = []
        heat_names = []

        for heat in self.heats:
            for racer in heat.racers:
                racer_names.append(racer.name)
                times.append(racer.get_average())
                heat_names.append(heat.name)

        times = np.array(times)
        racer_names = np.array(racer_names)
        heat_names = np.array(heat_names)
        si = np.argsort(times)

        with open(fname, "w") as outfile:
            header = ''.join(("Rank".rjust(8), "Name".rjust(30),
                              "Rank".rjust(12), "Time".rjust(10), '\n'))
            outfile.write(header)
            rank = 1
            for i in range(len(times)):
                if times[si[i]] > 0:
                    line = "{0:8d}{1}{2}{3:10.4f}\n".format(rank,
                                                            racer_names[si[i]].rjust(30),
                                                            heat_names[si[i]].rjust(12),
                                                            times[si[i]])
                    outfile.write(line)
                    rank += 1
        return 0

    def read_log_file(self, logfile):
        print("Inputting previous results from {}:".format(logfile))
        try:
            infile = open(logfile, "r")
        except OSError:
            print("No previous results were found.")
            return
        for line in infile:
            print(line)
            self.get_results_from_line(line)
        infile.close()

    def get_results_from_line(self, line):
        fields = line.split(',')
        self.current_race_log_idx = int(fields[0])
        self.goto_race(int(fields[1]))
        times = [float(x) for x in fields[3::3]]
        counts = [int(x) for x in fields[4::3]]
        if "Accepted" in line:
            self.record_race_results(times, counts, True)
        else:
            self.record_race_results(times, counts, False)

    def close_log_file(self):
        if self.race_log_file:
            self.race_log_file.close()

    def get_chips_for_race(self, race_number):
        chips = [[], [], [], []]
        if race_number < 0:
            print("""illegal race number, {}, requested. Returning
                  race[0]""".format(race_number))
            race_number = 0
        elif race_number > self.last_race:
            print("""illegal race number, {}, requested. Returning the last race,
                  race[{}]""".format(race_number, self.last_race))
            race_number = self.last_race
        race = self.races[race_number]
        for i in range(self.n_lanes):
            chips[i] = race.racers[i].chip()
        return chips

    def goto_next_race(self):
        self.goto_race(self.current_race_idx + 1)

    def goto_prev_race(self):
        self.goto_race(self.current_race_idx - 1)

    def goto_race(self, idx):
        if idx < 0:
            self.goto_race(0)
        elif idx > self.last_race:
            self.goto_race(self.last_race)
        else:
            self.current_race_idx = idx
            self.current_race = self.races[idx]

    def accept_results(self):
        self.current_race.post_results_to_racers()
        self.goto_next_race()

    def print_plan_yaml(self,
                        file_name='race_plan.yaml',
                        revised_plan=None):
        if revised_plan is None:
            self.generate_race_plan()
        else:
            self.adopt_revised_plan(revised_plan)

        plan_dict = {
            'heats': [],
            'races': []
        }
        for heat in self.heats[:-1]:
            plan_dict['heats'].append(heat.to_dict())

        for race in self.races:
            plan_dict['races'].append(race.to_dict())

        with open(file_name, 'w') as outfile:
            yaml.safe_dump(plan_dict, outfile, indent=2)

    def sort_heats(self):
        " Put heats in order of ability index. "
        ar = []

        for heat in self.heats:
            ar.append(heat.ability_rank)

        # We want our "empty heat" to come out last so we make its
        # ability index the highest.
        max_ar = np.max(ar)
        if ar[-1] < max_ar:
            ar[-1] = max_ar + 1

        order = np.argsort(ar)

        new_heats = []

        for idx in order:
            new_heats.append(self.heats[idx])

        self.heats = new_heats

    def generate_race_plan(self):
        new_plan = []

        """
        TODO Figure out how to add racers in the middle
        of an event!
        # Copy over any races that have already been recorded
        for old_race in self.races:
            if old_race.accepted_result_idx >= 0:
                new_plan.append(old_race)
                
        """
        self.sort_heats()

        # We want to know who still needs to run in each lane
        # The commented line is only useful if you want to track
        # which lanes that racers have already run in.
        needs_lane = [[], [], [], []]
        racer_count = 0
        for hi, heat in enumerate(self.heats[:-1]):
            for lane_idx in range(self.n_lanes):
                for ri, racer in enumerate(heat.racers):
                    # if racer.race_counts[lane_idx] == 0:
                    needs_lane[lane_idx].append((hi, ri, ri + racer_count))
            racer_count += len(heat.racers)

        # We have to figure out how to 'cycle' all the racers.
        # A method is to make sure that there are N racers so
        # that N%n_lanes = 1 or N%n_lanes = n_lanes-1. We can
        # always add 'empty slots', so here we figure out how
        # man empty slots to add.
        remainder = len(needs_lane[0]) % self.n_lanes
        n_empty = 0
        if remainder == 0:
            n_empty += 1
        elif remainder > 1:
            n_empty = self.n_lanes - 1 - remainder

        # Add the empty heat slots.
        empty_heat = len(self.heats) - 1
        for lane_idx in range(self.n_lanes):
            for idx in range(n_empty):
                needs_lane[lane_idx].append((empty_heat, idx, idx + racer_count))

        # Line all the entries up by re-arranging the entries
        new_races = []
        for xi in range(len(needs_lane[0])):
            heats = []
            racers = []
            is_empty = []
            for yi in range(self.n_lanes):
                # We need to calculate the index for a transposed
                # array.
                linear_idx = xi * 4 + yi
                li = linear_idx // len(needs_lane[0])
                ri = linear_idx % len(needs_lane[0])
                data = needs_lane[li][ri]
                heats.append(self.heats[data[0]])
                racers.append(self.heats[data[0]].racers[data[1]])
                is_empty.append(data[2] == empty_heat)
            new_races.append(Race(heats, racers, xi, is_empty, n_lanes=self.n_lanes))

        self.races = new_races

        if self.current_race is None:
            try:
                self.current_race = self.races[0]
            except IndexError:
                self.current_race = None

    def parse_cell_text(self, text):
        racer_name, heat_name = text.split(":")
        out_heat = self.heats[-1]
        out_racer = out_heat.racers[0]
        for heat in self.heats:
            if heat.name in heat_name:
                out_heat = heat
                break
        for racer in out_heat.racers:
            if racer.name in racer_name:
                out_racer = racer
                break
        if racer.heat_name in heat_name:
            return out_heat, out_racer
        else:
            return self.heats[-1], self.heats[-1].racers[0]

    def create_race_from_list(self, race_list, idx):
        racers = []
        heats = []
        is_empty = []
        empty_idx = 0
        for entry in race_list:
            heat, racer = self.parse_cell_text(entry)
            heats.append(heat)
            if heats[-1] is self.heats[-1]:
                is_empty.append(True)
                racers.append(self.heats[-1].racers[empty_idx])
                empty_idx += 1
            else:
                is_empty.append(False)
                racers.append(racer)
        return Race(heats, racers, idx, is_empty)

    def adopt_revised_plan(self, revised_plan):
        new_races = []

        for idx, race in enumerate(revised_plan):
            new_races.append(self.create_race_from_list(race, idx))

        self.races = new_races

        if self.current_race is None:
            try:
                self.current_race = self.races[0]
            except IndexError:
                self.current_race = None

    def get_race_plan(self):
        self.generate_race_plan()

        out_list = []
        for idx, race in enumerate(self.races):
            out_list.append(race.get_racer_list([]))

        return out_list


# DATA LOAD
def create_heat_from_line(line):
    entries = line.split(',')
    heat_name = ' '.join(entries[0].split(' ')[:-1])
    racers = []
    for rcr in list(filter(None, entries[1:])):
        if len(rcr) < 2:
            continue
        name = ' '.join(rcr.split(':')[:-1])
        rank = rcr.split(':')[-1]
        racers.append(Racer(name=name, rank=rank, heat_name=heat_name))
    return Heat(name=heat_name, racers=racers)


def create_racer_from_dict(rcr_dict, heat_name):
    out = Racer(name=rcr_dict['name'],
                rank=rcr_dict['rank'],
                heat_name=heat_name)
    if 'car_status' in rcr_dict.keys():
        car_status = rcr_dict['car_status']
        for key in car_status:
            out.car_status[key] = car_status[key]
    return out


def create_heat_from_dict(heat):
    racers = []
    out = Heat(name=heat['name'],
               racers=[],
               ability_rank=heat['ability_rank'])
    for rcr in heat['racers']:
        racer = create_racer_from_dict(rcr, heat['name'])
        out.add_racer(racer)
    return out


def create_race_from_line(line, all_heats):
    entries = line.split(',')
    race_num = int(entries[0].split(' ')[-1])
    heats = []
    racers = []
    is_empty = [False, False, False, False]
    for li, ent in enumerate(entries[1:5]):
        if len(ent) < 3:
            heats.append(all_heats[-1])
            racers.append(all_heats[-1].racers[li])
            is_empty[li] = True
        racer_name = ' '.join(ent.split(':')[:-1])
        heat_name = ent.split(':')[-1]
        for heat in all_heats:
            if heat_name == heat.name:
                heats.append(heat)
                for known_racer in heat.racers:
                    if racer_name == known_racer.name:
                        racers.append(known_racer)
                        break
                break
    out_str = str(race_num)
    for i in range(4):
        out_str = out_str + " {}:{}".format(racers[i].name, heats[i].name)
    print(out_str)
    return Race(heats, racers, race_num, is_empty)


def create_race_from_dict(race, available_heats):
    race_num = race['planned_number']
    heats = []
    racers = []
    is_empty = np.zeros(len(race['entries']), dtype=np.bool)
    for li, ent in enumerate(race['entries']):
        if ent['empty_lane']:
            heats.append(available_heats[-1])
            racers.append(available_heats[-1].racers[li])
            is_empty[li] = True
        else:
            racer_name = ent['racer']
            heat_name = ent['heat']
            for heat in available_heats:
                if heat.name == heat_name:
                    heats.append(heat)
                    for available_racer in heat.racers:
                        if racer_name == available_racer.name:
                            racers.append(available_racer)
                            break
                    break
    if race['accepted_result_idx'] >= 0:
        print("Write code to load the rest!")

    out_str = str(race_num)
    for racer, heat in zip(racers, heats):
        out_str += " {}:{}".format(racer.name, heat.name)
    print(out_str)
    return Race(heats, racers, race_num, is_empty)
