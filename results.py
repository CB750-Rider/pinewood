import tkinter as tk
from race_event import Event

class ResultsWindow:

    def __init__(self,
                 outer_frame: tk.Frame,
                 event: Event):
        
                
        self.label = tk.Label(outer_frame, text="Impliment me in results.py:ResultsWindow.")
        self.label.pack()
        
        self.outer_frame = outer_frame
        self.event = event
        self.window_open = False
        
    
    def run(self):
        self.window_open = True
        
    def stop(self):
        self.window_open = False
        
    def window_update(self):
        window = self.outer_frame
        
        if self.window_open:
            window.update_idletasks()
            window.update()
    