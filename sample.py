import pyautogui
import keyboard
import threading
import time
import random
from PIL import ImageGrab
from functools import partial
ImageGrab.grab = partial(ImageGrab.grab, all_screens=True)
import asyncio
import random
import configparser
import win32gui
import win32con
import pygetwindow as gw
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioMeterInformation


while True:
    noMorePotion = pyautogui.locateOnScreen("l9/assets/ui/hud/potion_empty.png", confidence=0.9)
    if str(noMorePotion) != 'None':
        print('found')
    else:
        print('still has potion')