from race_event import Event, Heat, Racer, Race

#plan_file = 'RacePlan.csv'
plan_file = 'test_entries.yaml'
log_file = 'race_log.csv'

print("Creating the event.")
event = Event(event_file=plan_file,
              log_file=log_file,
              verbose=True)

print("Generating a plan")
event.generate_race_plan()

print("Creating a new racer")
new_racer = Racer(name="Tom")

print("Attempting to add the racer with no heat defined.")
try:
    event.add_racer(new_racer)
except ValueError:
    print("Success!")
else:
    print("Fail.")

new_racer = Racer(name="Tom", heat_name="engineer")

print("Attempting to add a racer that already exists.")
try:
    event.add_racer(new_racer)
except ValueError:
    print("Success!")
else:
    print("Fail.")

print("Attempting to add a heat that already exists.")
if event.heat_index(heat_name="engineer") < 0:
    event.add_heat(Heat(name="engineer"))
try:
    event.add_heat(Heat(name="engineer"))
except ValueError:
    print("Success!")
else:
    print("Failure.")

print("Attempting to add the racer with a heat and name that already exists.")
if event.racer_index(heat_name="engineer", racer_name="Tom") < 0:
    event.add_racer(new_racer)
try:
    event.add_racer(new_racer)
except ValueError:
    print("Success!")
else:
    print("Failure")

print("Attempting to add a new racer.")
try:
    event.add_racer(Racer("Bob",heat_name='engineer'))
except Exception:
    print("Fail")
    raise
else:
    print("Success!")


print("Attempting to remove a racer that does not exist.")
if event.remove_racer(racer_name="Not a racer"):
    print("Failure.")
else:
    print("Success!")
not_racer = Racer(name="Tom", heat_name="engineer")
if event.remove_racer(racer=not_racer):
    print("Fail.")
else:
    print("Success!")

print("Attempting to remove a racer that does exist.")
if event.remove_racer(racer_name="Tom"):
    print("Success!")
    event.add_racer(new_racer)
else:
    print("Fail.")
if event.remove_racer(racer=new_racer):
    print("Success!")
    event.add_racer(new_racer)
else:
    print("Fail.")

print("Attempting to remove a heat that does not exist.")
not_heat = Heat()
if event.remove_heat(heat=not_heat):
    print("Fail.")
else:
    print("Success!")
if event.remove_heat(heat_name="Not a heat"):
    print("Fail.")
else:
    print("Success!")

print("Attempting to remove the empty heat.")
empty_heat = event.heats[-1]
if event.remove_heat(heat=empty_heat):
    print("Fail.")
else:
    print("Success!")
if event.remove_heat(heat_name="Empty"):
    print("Fail.")
else:
    print("Success!")

print("Attempting to remove a heat that does exist")
tmp = event.heats[-2]
tmp_name = tmp.name
if event.remove_heat(heat=tmp):
    print("Success!")
    event.add_heat(tmp)
else:
    print("Fail.")
if event.remove_heat(heat_name=tmp_name):
    print("Success!")
    event.add_heat(tmp)
else:
    print("Fail.")

print("Attempting to add a race")
heats = [event.heats[-1], event.heats[-1], event.heats[-1], event.heats[-1]]
heat = heats[0]
racers = [heat.racers[0], heat.racers[1], heat.racers[2], heat.racers[3]]
new_race = Race(heats, racers, 70, [False, False, True, True])
event.add_race(new_race, location='next')
event.add_race(new_race, location=-1)
count = 0
for race in event.races:
    if race is new_race:
        count += 1
if count == 2:
    print("Success!")
else:
    print("Failure.")
if event.remove_race(idx=-2):
    print("Success!")
else:
    print("Failure.")
if event.remove_race(race=new_race):
    print("Success!")
else:
    print("Failure.")
print("Attempting to remove a race that does not exist.")
if event.remove_race(race=new_race):
    print("Failure.")
else:
    print("Success!")

print("Race added successfully. Recreating the plan.")
event.generate_race_plan()

print("Writing the plan")
event.print_plan_yaml(file_name="test_plan.yaml")

print("Read test_plan.yaml.")

print("creating a new event from the plan we just saved.")
event2 = Event(event_file="test_plan.yaml")

print("That worked.")

