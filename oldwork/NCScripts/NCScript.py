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

config = configparser.ConfigParser()
config.read('config.ini')

clicking = False
stop_script = False

async def get_application_audio_levels():
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name() == "MadGlobal-Win64-Shipping.exe":  # Replace with your target application's executable name
            volume = session._ctl.QueryInterface(IAudioMeterInformation)
            peak = volume.GetPeakValue()
            if peak > 0:
                return bool(1)
            else:
                return bool(0)

async def checkIfAttacked():
    hasSound = await get_application_audio_levels()
    if hasSound:
        fw = False
        while not fw:
            fw = focus_window()
            time.sleep(0.5)
            while True:
                move = pyautogui.locateOnScreen('movetext.png',confidence=0.9) 
                if str(move) != 'None':
                    pyautogui.press('y')
                else:
                    print('teleported')
                    break
            time.sleep(3)
            await repots()
            time.sleep(random.uniform(10, 75))
            await goToSpot()

# def dismantle():

async def repots():
    findAndClickSomething('sundries.png')
    time.sleep(10)
    test = findAndClickSomething('purchaseall.png')
    if test:
        findAndClickSomething('purchase.png')
        time.sleep(1)
        pyautogui.click()
    else:
        findAndClickSomething('exit.png')
    findAndClickSomething('exit.png')


def fly():
    pyautogui.keyDown('s')
    time.sleep(0.5)
    pyautogui.press('space')
    time.sleep(0.5)
    pyautogui.keyUp('s')
     
spot1coord = {'x' : 100, 'y' : -370, 'ctr' : 5, 'hasSpace' : True, 'spaceCtr' : 3}
spot2coord = {'x' : 100, 'y' : -350, 'ctr' : 9, 'hasSpace' : False, 'spaceCtr' : 0}
spot3coord = {'x' : 100, 'y' : -340, 'ctr' : 7, 'hasSpace' : True, 'spaceCtr' : 5}
spot4coord = {'x' : 100, 'y' : -370, 'ctr' : 6, 'hasSpace' : False, 'spaceCtr' : 3}

coords = [spot2coord, spot3coord, spot4coord]

async def goToSpot():
    fw = focus_window()
    time.sleep(0.5)
    pyautogui.press('m')
    time.sleep(1)
    clickMove = pyautogui.locateOnScreen('55mobs.png', confidence=0.9)
    if str(clickMove) != 'None':
        selected_coord = random.choice(coords)
        pyautogui.click(x=clickMove.left+selected_coord['x'],y=clickMove.top+selected_coord['y'])
        time.sleep(1)
        move = findAndClickSomething('move.png')    
        time.sleep(3)
        findAndClickSomething('exit.png')
        time.sleep(8)
        ctr = selected_coord['ctr']
        while ctr > 0:
            ctr -= 1
            fly()
            time.sleep(2)
        if selected_coord['hasSpace']:
            spacectr =selected_coord['spaceCtr']
            while spacectr > 0:
                spacectr -= 1
                pyautogui.press('space')
                time.sleep(3)
        time.sleep(6)
        pyautogui.press('q')
        time.sleep(2)
        pyautogui.press('m')
        time.sleep(0.4)
        findAndClickSomething('bookmark.png')
        town = pyautogui.locateOnScreen('town.png',confidence=0.9) 
        if str(town) != 'None':
            moved = False
            pyautogui.click(x=town.left+253,y=town.top+10)
            pyautogui.click()

def findAndClickSomething(imageStr,conf = 0.9):
    data = pyautogui.locateOnScreen(imageStr, confidence = conf)
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
            print(f"Found window: {window.title}")
            print(f"Window is active: {window.isActive}")
            print(f"Window is minimized: {window.isMinimized}")
            if not window.isActive or window.isMinimized:
                window.minimize()
                time.sleep(0.5)
                window.restore()  # Restore the window if it's minimized
                pyautogui.getWindowsWithTitle(window_title)[0].activate()  # Bring the window to the foreground
            return True
        except (IndexError, gw.PyGetWindowException) as e:
            print(f"Error: {e}")


async def check_if_in_masarta():
    time.sleep(2)
    dialies = pyautogui.locateOnScreen('masarta.png',confidence=0.9)
    if str(dialies) != 'None':
        print('still grinding')
        return bool(0)
    else: 
        went = await go_to_grinding_spot()
        return went

async def main():
    while True:
        # await checkIfAttacked()
        pyautogui.click()
        time.sleep(5)

asyncio.run(main())
