import tkinter as tk
import subprocess
import keyboard
import pyautogui
import win32gui
import win32con
import time
import configparser

def enum_callback(hwnd, param):
    window_title = "Ragnarok Origin Global"
    if win32gui.GetWindowText(hwnd) == window_title:
        param.append(hwnd)

def resize():
    hwnd_list = []
    win32gui.EnumWindows(enum_callback, hwnd_list)

    # Set the desired aspect ratio
    aspect_ratio = 16 / 9  # For example, 16:9

    # Set the desired width (or height)
    new_width = 900
    new_height = round(new_width / aspect_ratio)

    for hwnd in hwnd_list:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Calculate the new width and height based on aspect ratio
        new_width = round(new_height * aspect_ratio)
        new_height = round(new_width / aspect_ratio)

        win32gui.MoveWindow(hwnd, 0, 0, new_width, new_height, True)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.1)
        
def start_script():
    global script_process
    script_process = subprocess.Popen(["python", "tnlmacro.py"])
    stop_button.configure(state=tk.NORMAL)  # Enable the Stop button
    start_button.configure(state=tk.DISABLED)  # Disable the Start button
        
def start_fot_script():
    global script_process
    script_process = subprocess.Popen(["python", "NCFOTScript.py"])
    stop_button.configure(state=tk.NORMAL)  # Enable the Stop button
    start_button.configure(state=tk.DISABLED)  # Disable the Start button

def start_celano_req_script():
    global script_process
    script_process = subprocess.Popen(["python", "nc_celano_req.py"])
    stop_celano_req_button.configure(state=tk.NORMAL)  # Enable the Stop button
    start_celano_req_button.configure(state=tk.DISABLED)  # Disable the Start button

def stop_celano_req_script():
    global script_process
    script_process.terminate()
    script_process.wait()
    stop_celano_req_button.configure(state=tk.DISABLED)  # Enable the Stop button
    start_celano_req_button.configure(state=tk.NORMAL)  # Disable the Start button

def stop_script():
    global script_process
    script_process.terminate()
    script_process.wait()
    stop_button.configure(state=tk.DISABLED)  # Disable the Stop button
    start_button.configure(state=tk.NORMAL)
    
def stop_fot_script():
    global script_process
    script_process.terminate()
    script_process.wait()
    stop_button.configure(state=tk.DISABLED)  # Disable the Stop button
    start_button.configure(state=tk.NORMAL)

def toggle_value():
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    if config.has_option('DEFAULT', 'repots'):
        current_value = config.getint('DEFAULT', 'repots')
        new_value = 1 if current_value == 0 else 0
        config.set('DEFAULT', 'repots', str(new_value))
        
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

        toggle_button.config(
            text=f"Repots: ({'ON' if new_value else 'OFF'})",
            bg='green' if new_value else 'light coral'
        )

# def changeValues(event):
#     var, variable_name = event
#     var = var.get()
#     # Define the variable and its new value
#     # Read the contents of the file
#     with open("config.py", "r") as file:
#         file_contents = file.readlines()

#     # Find the line containing the variable assignment
#     variable_line_index = None
#     for i, line in enumerate(file_contents):
#         if line.startswith(event[1]+" ="):
#             variable_line_index = i
#             break

#     # Modify the variable value
#     if variable_line_index is not None:
#         file_contents[variable_line_index] = event[1]+" = {}\n".format(var)

#     # Write the modified contents back to the file
#     with open("config.py", "w") as file:
#         file.writelines(file_contents)

 
keyboard.add_hotkey("Ctrl+Shift+S", stop_script)       
keyboard.add_hotkey("Ctrl+Shift+A", start_script)    

config = configparser.ConfigParser()
config.read('config.ini')
current_value = config.getint('DEFAULT', 'repots', fallback=0)
initial_text = f"Repots: ({'ON' if current_value else 'OFF'})"
initial_bg = 'green' if current_value else 'light coral'

# Create the main GUI window
window = tk.Tk()
window.attributes('-topmost', True)
# Create a frame for buttons
button_frame = tk.Frame(window)
button_frame.pack()

# Create Start and Stop buttons
start_button = tk.Button(button_frame, text="START", command=start_script, height=5, width=15)
start_button.pack(side=tk.LEFT, padx=5, pady=5)

stop_button = tk.Button(button_frame, text="STOP", command=stop_script, height= 5, width=15)
stop_button.pack(side=tk.LEFT, padx=5, pady=5)

stop_button.configure(state=tk.DISABLED)

# toggle_button = tk.Button(button_frame, text=initial_text, command=toggle_value, height=5, width=15, bg=initial_bg)
# toggle_button.pack(side=tk.LEFT, padx=5, pady=5)


# button_frame2 = tk.Frame(window)
# button_frame2.pack()

# # Create Start and Stop buttons
# start_fot_button = tk.Button(button_frame2, text="START FoT", command=start_fot_script, height=5, width=15)
# start_fot_button.pack(side=tk.LEFT, padx=5, pady=5)

# stop_fot_button = tk.Button(button_frame2, text="STOP FoT", command=stop_fot_script, height= 5, width=15)
# stop_fot_button.pack(side=tk.LEFT, padx=5, pady=5)

# stop_fot_button.configure(state=tk.DISABLED)

# button_frame3 = tk.Frame(window)
# button_frame3.pack()

# # Create Start and Stop buttons
# start_celano_req_button = tk.Button(button_frame3, text="START CELANO REQ", command=start_celano_req_script, height=5, width=15)
# start_celano_req_button.pack(side=tk.LEFT, padx=5, pady=5)

# stop_celano_req_button = tk.Button(button_frame3, text="STOP CELANO REQ", command=stop_celano_req_script, height= 5, width=15)
# stop_celano_req_button.pack(side=tk.LEFT, padx=5, pady=5)

# stop_celano_req_button.configure(state=tk.DISABLED)

# Start the GUI event loop
window.mainloop()
# resize()
