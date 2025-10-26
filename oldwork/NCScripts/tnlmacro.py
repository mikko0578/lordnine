import pyautogui
import time

# List of keys to press
keys = ['1', '2', '3', '4', '5']

# Delay time in seconds
delay = 0.5

# Loop indefinitely
while True:
    for key in keys:
        pyautogui.press(key)
        time.sleep(delay)
