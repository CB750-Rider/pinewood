import tkinter as tk
from race_event import Event
from rm_socket import MainWindow


class ResultsWindow(MainWindow):

    def __init__(self,
                 outer_frame: tk.Frame,
                 event: Event):
        super().__init__(outer_frame)

        self.label = tk.Label(outer_frame, text="Impliment me in results.py:ResultsWindow.")
        self.label.pack()

        self.outer_frame = outer_frame
        self.event = event
        self.window_open = False

    def window_update(self):
        window = self.outer_frame

        if self.window_open:
            window.update_idletasks()
            window.update()

    def _pack(self):
        return

    def _forget(self):
        return

    def _tkraise(self):
        return

    def _update(self):
        return

