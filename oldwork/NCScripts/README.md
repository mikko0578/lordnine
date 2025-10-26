## Installation

### Install python 3.8.7

After installing python, run the ff command on your terminal:

```bash
pip install pyautogui==0.9.52
```
```bash
pip install pyscreeze==0.1.26
```

Edit run-macro.bat change the second line to cd { path to NCScript folder }

### To ensure that the macro works, check the images on the folder and recapture it based on the game resolution you have while the game is opened. Save it as {current name}.png or just replace the image with your new screenshot with the same filename. 

## Usage
### Configuration for quests:
Open config.ini and change the following:
1. bastiumQuestCount - max number of quests to be taken from the {bastiumstart.png} in bastium region
2. celanoQuestCount - max number of quests to be taken in celano region

### Images to change based on your character:

#### BOOKMARK the area where your character will grind after dailies

1. grindingregion.png - what region your character will grind after dailies
2. grindingarea.png - where your character will grind in the region you chose
3. bastiumstart.png

### 2 ways to use:
1. Set up via task scheduler and make sure to check the Run with highest privileges under General. (automated)
2. Open terminal (run as administrator) and navigate to this folder and run: (manual)
```bash 
python NCScript.py 
```