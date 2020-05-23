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


# CLASS STUFF
class Racer:
    def __init__(self, name, rank):
        self.name = name
        self.rank = rank
        self.race_times = np.zeros(4)
        self.race_counts = np.zeros(4)
        self.race_plan_nums = np.zeros(4)
        self.race_log_nums = np.zeros(4)
        self.race_positions = np.zeros(4)
        self.hist = {}
        self.heat_name = "Heat0"
        self.heat_index = 0

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
        self.race_times = np.zeros(4)
        self.race_log_nums = np.zeros(4)
        self.race_plan_nums = np.zeros(4)
        self.race_positions = np.zeros(4)


class Heat:
    def __init__(self, name, racers, racer_names):
        self.name = name
        self.racers = racers
        self.racer_names = racer_names
        for ri, racer in enumerate(racers):
            racer.set_heat(name, ri)
        self.races = []
        self.current_race_idx = 0

    def add_race(self, racers, race_idx):
        # Racers are expected to be in order of lane number
        new_race = {"Race_Number": -1,
                    "Racers": racers,
                    "Times": self.times}
        self.races.insert(race_idx, new_race)

    def set_current_race_idx(self, idx):
        self.current_race_idx = idx

    def get_ranks(self):
        times = []
        names = []
        for racer in self.racers:
            times.append(racer.mean_time())
            names.append(racer.name)
        times = np.array(times)
        idx = np.argsort(times)
        return names[idx], times[idx]

    def swap_racer(self, old_racer, new_racer):
        for i in range(len(self.racers)):
            if self.racers[i] == old_racer:
                self.racers[i] = new_racer
                self.racers[i].set_heat(self.name, new_racer.heat_index + 1)


class Race:
    def __init__(self, heats, racers, number, is_empty):
        self.heats = heats  # 1 x 4
        self.racers = racers  # 1 x 4
        self.plan_number = number  # The number from the race plan
        self.race_number = []  # The race number(s) from the track recorder
        self.times = []
        self.counts = []
        self.placements = []
        self.current_race = 0
        self.is_empty = is_empty  # 1 x 4
        self.accepted_result_idx = -1  # The index of the race result that
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
        for lane_idx, racer, time, count, placement in zip(range(4), self.racers,
                                                           self.times[i], self.counts[i], self.placements[i]):
            racer.post_result(lane_idx, self.race_number[i], self.plan_number,
                              time, count, placement)
        self.accepted_result_idx = i


class Event:
    def __init__(self, event_file, logfile):
        self.heats, self.races, self.heat_names = load_races_from_file(
            event_file)
        self.current_race_idx = 0  # Race plan race number
        self.current_race_log_idx = 0  # The index in the log
        self.n_lanes = 4
        self.current_race = self.races[0]
        self.last_race = len(self.races) - 1
        self.race_log_file = []
        self.read_log_file(logfile)
        try:
            self.race_log_file = open(logfile, "a+")
        except:
            print("Unable to open {} for writing.")
            descision = input("Continue without logging? [y/N]")
            if 'y' or 'Y' in descision:
                print("Continuing on.")
            else:
                raise SystemExit

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
                if (times[si[i]] > 0):
                    line = "{0:8d}{1}{2}{3:10.4f}\n".format(rank,
                                                            racer_names[si[i]].rjust(30),
                                                            heat_names[si[i]].rjust(12),
                                                            times[si[i]])
                    outfile.write(line)
                    rank += 1
        return 0

    def read_log_file(self, logfile):
        print("Inputing previous results from {}:".format(logfile))
        try:
            infile = open(logfile, "r")
        except:
            print("No previous results were found.")
            return
        for line in infile:
            print(line)
            self.get_results_from_line(line)

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


# DATA LOAD
def create_heat_from_line(line):
    entries = line.split(',')
    heat_name = ' '.join(entries[0].split(' ')[:-1])
    racers = []
    racer_names = []
    for rcr in list(filter(None, entries[1:])):
        if (len(rcr) < 2):
            continue
        name = ' '.join(rcr.split(':')[:-1])
        rank = rcr.split(':')[-1]
        racers.append(Racer(name, rank))
        racer_names.append(name)
    return Heat(heat_name, racers, racer_names), heat_name


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
        racr_name = ' '.join(ent.split(':')[:-1])
        heat_name = ent.split(':')[-1]
        for heat in all_heats:
            if heat_name == heat.name:
                heats.append(heat)
                for i, rname in enumerate(heat.racer_names):
                    if racr_name == rname:
                        racers.append(heat.racers[i])
                        break
                break
    out_str = str(race_num)
    for i in range(4):
        out_str = out_str + " {}:{}".format(racers[i].name, heats[i].name)
    print(out_str)
    return Race(heats, racers, race_num, is_empty)


def create_empty_lane_heat():
    racer_names = ["empty {}".format(i + 1) for i in range(4)]
    racers = [Racer(x, "Empty") for x in racer_names]
    return Heat("Empty", racers, racer_names)


def set_host_and_port():
    global infile, host, port
    with open(infile) as fp:
        for line in fp:
            laneNumber, hostAddress, hostPort = line.split(',')
            li = int(laneNumber) - 1
            host[li] = hostAddress
            port[li] = int(hostPort)


def load_races_from_file(fname):
    heats = []
    races = []
    heat_names = []
    with open(fname) as infile:
        for line in infile:
            if 'Heat' in line:
                new_heat, heat_name = create_heat_from_line(line)
                heats.append(new_heat)
                heat_names.append(heat_name)
        heats.append(create_empty_lane_heat())
        for heat in heats:
            print(heat.name)
            print(heat.racer_names)
        infile.seek(0, 0)
        for line in infile:
            if 'Race' in line:
                races.append(create_race_from_line(line, heats))
    return heats, races, heat_names
