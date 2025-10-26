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
from datetime import datetime


config = configparser.ConfigParser()
config.read('config.ini')

clicking = False
stop_script = False

def findAndClickSomething(imageStr,conf = 0.9):
    data = pyautogui.locateOnScreen('requests/'+imageStr, confidence = conf)
    time.sleep(0.5)
    if data != 'None':
        pyautogui.click(data)
        return bool(1)
    else :
        return bool(0)
    
def focus_window():
    window_title = "NIGHT CROWS(1)"
    while True:
        try:
            window = gw.getWindowsWithTitle(window_title)[0]
            # print(f"Found window: {window.title}")
            # print(f"Window is active: {window.isActive}")
            # print(f"Window is minimized: {window.isMinimized}")
            if not window.isActive or window.isMinimized:
                window.minimize()
                time.sleep(0.5)
                window.restore()  # Restore the window if it's minimized
                pyautogui.getWindowsWithTitle(window_title)[0].activate()  # Bring the window to the foreground
            return True
        except (IndexError, gw.PyGetWindowException) as e:
            print(f"Error: {e}")

async def check_existing_request():
    focus_window()
    time.sleep(1)
    menu = pyautogui.locateOnScreen('requests/menu_open.png',confidence=0.9)
    if str(menu) == 'None':
        pyautogui.press('=')
    time.sleep(0.5)
    findAndClickSomething('requests.png')
    time.sleep(0.5)
    findAndClickSomething('region_request.png')
    time.sleep(0.5)
    findAndClickSomething('manage.png')
    while True:
        completed = pyautogui.locateOnScreen('requests/obtain_reward.png',confidence=0.9)
        if str(completed) != 'None':
            pyautogui.click(completed)
            now = datetime.now()
            print("Current date and time:", now)
            time.sleep(1)
            findAndClickSomething('exit.png')
            break
    return

async def get_request():
    focus_window()
    time.sleep(1)
    menu = pyautogui.locateOnScreen('requests/menu_open.png',confidence=0.9)
    if str(menu) == 'None':
        pyautogui.press('=')
    time.sleep(1)
    findAndClickSomething('requests.png')
    time.sleep(1)
    findAndClickSomething('region_request.png')
    time.sleep(1)
    findAndClickSomething('celano.png')
    time.sleep(1)
    no_req = pyautogui.locateOnScreen('requests/no_requests.png',confidence=0.9)
    if str(no_req) == 'None':
        findAndClickSomething('go_to_bulletin.png')
        time.sleep(0.5)
        pyautogui.press('y')
        time.sleep(20)
        findAndClickSomething('region_request.png')
        time.sleep(0.5)
        findAndClickSomething('region_request.png')
        time.sleep(0.5)
        findAndClickSomething('celano.png')
        time.sleep(0.5)
        findAndClickSomething('request_reward.png')
        time.sleep(0.5)
        findAndClickSomething('accept.png')
        time.sleep(0.5)
        pyautogui.press('y')
        time.sleep(0.5)
        findAndClickSomething('manage.png')
        time.sleep(0.5)
        findAndClickSomething('teleport.png')
        time.sleep(0.5)
        pyautogui.press('y')
        now = datetime.now()
        print("Current date and time:", now)

        return bool(1)
    else:
        return bool(0)

    
async def main():
    while True:
        has_req = await get_request()
        if not has_req:
            print('no more requests. ending script')
            findAndClickSomething('exit.png')
            break
        else:
            await check_existing_request()
asyncio.run(main())
