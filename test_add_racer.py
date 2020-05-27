from race_event import Event, Heat, Racer

plan_file = 'test_plan.yaml'
log_file = 'race_log.csv'

print("Creating the event.")
event = Event(event_file = plan_file,
              log_file = log_file,
              verbose=True)

print("Generating a plan")
event.generate_race_plan()

print("Creating a new racer")
new_racer = Racer(name="Tom")

print("Attempting to add the racer 0")
try:
    event.add_racer(new_racer)
except ValueError:
    print("Failed as expected.")
    pass

new_racer = Racer(name="Tom", heat_name="engineer")

print("Attempting to add the racer 1")
try:
    event.add_racer(new_racer)
except ValueError:
    print("Failed as expected")
    pass

print("Attempting to add a heat")
event.add_heat(Heat(name="engineer"))

print("Attempting to add the racer 2")
event.add_racer(new_racer)

print("Racer added successfully. Recreating the plan.")
event.generate_race_plan()

print("Writing the plan")
event.print_plan_yaml(file_name="test_plan.yaml")

print("Read test_plan.yaml.")

print("creating a new event from the plan we just saved.")
event2 = Event(event_file="test_plan.yaml")

print("That worked.")

# TODO
#  1. Test Removing Racers,
#  2. Test Removing Heats, and
#  3. Test adding/removing races.
#  Then, convert the race log to yaml.
#  Next, Add a web+GUI interface for registering scouts.
#  After That, Add a web interface for scout families to see their progress.
#  Finally, convert the app to a web interface, or refactor the GUI code to better use classes.