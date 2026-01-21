from gpiozero import Button
from signal import pause
import pygame
import sys
import os
import time
import threading
import subprocess
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from enum import Enum

# EINK SETUP
base_dir = os.path.dirname(os.path.abspath(__file__))
libdir = os.path.join(base_dir, 'epaperlib')
if os.path.exists(libdir):
    sys.path.append(libdir)
from waveshare_epd import epd3in97
eink = epd3in97.EPD()

# UI SETUP
font_path_dejavu = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
font_time = ImageFont.truetype(font_path_dejavu, 120)
font_alarm_time = ImageFont.truetype(font_path_dejavu, 30)

class Mode(Enum):
    DEFAULT = 0
    CHANGE_ALARM_TIME = 1 
    CHANGE_SYSTEM_TIME = 2
    CHANGE_VOLUME = 3

class Changing(Enum):
    HOUR = 0
    MINUTE = 1
    

currentmode = Mode.DEFAULT
changing = Changing.HOUR
willalarmgo = False

def changemode():
    global currentmode
    global changing

    currentmode = Mode((currentmode.value + 1) % len(Mode))
    changing = Changing.HOUR


# CREATE TIME UI
alarmtimehour = 8
alarmtimeminute = 15

def changesystemhour(increment):
    
    now = datetime.now()
    new_time = now + timedelta(hours=(1 if increment else -1))
    formatted_time = new_time.strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(["sudo", "timedatectl", "set-time", formatted_time], check=True)
    print(f"System time successfully advanced to: {formatted_time}")

def changesystemminute(increment):
    now = datetime.now()
    new_time = now + timedelta(minutes=(1 if increment else -1))
    formatted_time = new_time.strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(["sudo", "timedatectl", "set-time", formatted_time], check=True)
    print(f"System time successfully advanced to: {formatted_time}")


def alarmtimestring():
    hour = ("0" if alarmtimehour < 10 else "") +  str(alarmtimehour)
    minute = ("0" if alarmtimeminute < 10 else "") + str(alarmtimeminute)
    return hour + ":" + minute

# SOUNDS/SPEAKER SETUP
pygame.mixer.init()
alarmsound = pygame.mixer.Sound("/home/devonstarr123/Documents/beep.wav")
alarmsoundchannel = None
alarmgoingoff = False
soundpadding = 0.3
volume = 50

# Eink blank screen to start
eink.init()
image = Image.new('1', (eink.width, eink.height), 255)
eink.display_Base(eink.getbuffer(image))

# partial update
image = Image.new('1', (eink.width, eink.height), 0)
draw = ImageDraw.Draw(image)

partialrefreshes = 0

def buildUI():
    global partialrefreshes
    draw.rectangle((0, 0, eink.width, eink.height), fill = 255)
    match currentmode:
        case Mode.DEFAULT:
            # Draw current time text
            current_time = datetime.now().strftime("%H:%M")
            bbox = draw.textbbox((0,0), current_time, font=font_time)
            textwidth = bbox[2] - bbox[0]
            textheight = bbox[3] - bbox[1]
            x = (eink.width - textwidth) // 2
            y = (eink.height - textheight) // 2
            draw.text((x,y), current_time, font=font_time, fill=0)

            # Draw the alarm time text
            padding = 10
            alarm_time_text = ("alarm set:  " + alarmtimestring()) if willalarmgo else "alarm off"
            bbox = draw.textbbox((0,0), alarm_time_text, font=font_alarm_time)
            textwidth = bbox[2] - bbox[0]
            textheight = bbox[3] - bbox[1]
            x = eink.width - textwidth - padding
            y = padding
            draw.text((x,y), alarm_time_text, font=font_alarm_time, fill=0)
        case Mode.CHANGE_ALARM_TIME:
            # Mode description top left
            padding = 10
            text = "Editing alarm time:"
            x = padding
            y = padding
            draw.text((x,y), text, font=font_alarm_time, fill=0)

            # Alarm time text
            alarm_time = alarmtimestring()
            bbox = draw.textbbox((0,0), alarm_time, font=font_time)
            textwidth = bbox[2] - bbox[0]
            textheight = bbox[3] - bbox[1]
            x = (eink.width - textwidth) // 2
            y = (eink.height - textheight) // 2
            draw.text((x,y), alarm_time, font=font_time, fill=0)

            # Underline for hour
            if changing == Changing.HOUR:
                underline_y = y + 125
                underlinewidth = 5
                draw.rectangle([x, underline_y, x + textwidth // 2 - 20, underline_y + underlinewidth], fill=0)

            # Underline for minute
            if changing == Changing.MINUTE:
                underline_y = y + 125
                underlinewidth = 5
                draw.rectangle([x + textwidth // 2 + 20, underline_y, x + textwidth, underline_y + underlinewidth], fill=0)

        case Mode.CHANGE_SYSTEM_TIME:
            # Changing volume:
            padding = 10
            text = "Changing system time:"
            x = padding
            y = padding
            draw.text((x,y), text, font=font_alarm_time, fill=0)

            # System time text
            current_time = datetime.now().strftime("%H:%M")
            bbox = draw.textbbox((0,0), current_time, font=font_time)
            textwidth = bbox[2] - bbox[0]
            textheight = bbox[3] - bbox[1]
            x = (eink.width - textwidth) // 2
            y = (eink.height - textheight) // 2
            draw.text((x,y), current_time, font=font_time, fill=0)

            # Underline for hour
            if changing == Changing.HOUR:
                underline_y = y + 125
                underlinewidth = 5
                draw.rectangle([x, underline_y, x + textwidth // 2 - 20, underline_y + underlinewidth], fill=0)

            # Underline for minute
            if changing == Changing.MINUTE:
                underline_y = y + 125
                underlinewidth = 5
                draw.rectangle([x + textwidth // 2 + 20, underline_y, x + textwidth, underline_y + underlinewidth], fill=0)

        case Mode.CHANGE_VOLUME:
            # Changing volume:
            padding = 10
            text = "Changing volume:"
            x = padding
            y = padding
            draw.text((x,y), text, font=font_alarm_time, fill=0)

            # Volume center text
            volume_text = f"{volume}%"
            bbox = draw.textbbox((0,0), volume_text, font=font_time)
            textwidth = bbox[2] - bbox[0]
            textheight = bbox[3] - bbox[1]
            x = (eink.width - textwidth) // 2
            y = (eink.height - textheight) // 2
            draw.text((x,y), volume_text, font=font_time, fill=0)

        case _:
             print("uncaught case found...")
             exit()


    # Finally, display the image
    if partialrefreshes >= 200:
        eink.display(eink.getbuffer(image))
        partialrefreshes = 0
    else:
        eink.display_Partial(eink.getbuffer(image),0, eink.height, eink.width, eink.height * 2)


UIThread = None
buildUISchedules = None

def buildUIThreadFunction():
    global buildUISchedules
    global UIThread
    buildUISchedules = 1
    lastBuildUISchedules = 0
    while buildUISchedules != lastBuildUISchedules:
        print("last: ", lastBuildUISchedules, " | new: ", buildUISchedules)
        lastBuildUISchedules = buildUISchedules
        time.sleep(0.5)
    print("schedules are the same.")
    buildUI()
    UIThread = None


def scheduleBuildUI():
    global buildUISchedules
    global UIThread
    if UIThread is None:
        UIThread = threading.Thread(target=buildUIThreadFunction, daemon=True)
        UIThread.start()
        return
    buildUISchedules += 1

scheduleBuildUI()


# RF BUTTONS SETUP
A = Button(23)
B = Button(22)
C = Button(27)
D = Button(17)



def set_volume_os(percentage):
    command = f"amixer -c 1 sset 'PCM' {percentage}%"
    os.system(command)
set_volume_os(volume)

def offgoalarm():
    global alarmsoundchannel
    while alarmgoingoff:
        alarmsoundchannel = alarmsound.play()
        time.sleep(alarmsound.get_length() + soundpadding)
alarmthread = threading.Thread(target=offgoalarm, daemon=True)

def startalarm():
    global alarmgoingoff
    alarmgoingoff = True
    alarmthread.start()

def stopalarm():
    global alarmgoingoff
    global alarmthread
    if alarmsoundchannel:
        alarmsoundchannel.stop()
    alarmgoingoff = False
    alarmthread = threading.Thread(target=offgoalarm, daemon=True)

def timeloop():
    lastminute = datetime.now().minute
    while True:
        newminute = datetime.now().minute
        if lastminute != newminute:

            newhour = datetime.now().hour
            if newhour == alarmtimehour and newminute == alarmtimeminute and willalarmgo:
                startalarm()

            lastminute = newminute

            scheduleBuildUI()
        time.sleep(5)
clock_thread = threading.Thread(target=timeloop, daemon=True)


# This one will be for switching modes / turning off the alarm
def buttonA():
    global currentmode
    print("Button A pressed")
    if alarmgoingoff:
        stopalarm()
        return
    
    # switch modes
    changemode()
    # print("new mode: ", currentmode, " Changing: ", changing)
    scheduleBuildUI()
    
    
# This will be for changing what you're changing
def buttonB():
    global willalarmgo
    global changing
    match currentmode:
        case Mode.DEFAULT:
            willalarmgo = not willalarmgo
            scheduleBuildUI()
        case Mode.CHANGE_ALARM_TIME:
            changing = Changing((changing.value + 1) % len(Changing))
            scheduleBuildUI()
        case Mode.CHANGE_SYSTEM_TIME:
            changing = Changing((changing.value + 1) % len(Changing))
            scheduleBuildUI()
        case Mode.CHANGE_VOLUME:
            alarmsound.play()
        case _:
            print("unknown case caught...")
            exit()
    
# This will be for changing the hour
def buttonC():
    global alarmtimehour
    global alarmtimeminute
    global volume
    match currentmode:
        case Mode.DEFAULT:
            pass
        case Mode.CHANGE_ALARM_TIME:
            if changing == Changing.HOUR:
                alarmtimehour = (alarmtimehour + 1) % 24
            else:
                alarmtimeminute = (alarmtimeminute + 5) % 60
            scheduleBuildUI()
        case Mode.CHANGE_SYSTEM_TIME:
            if changing == Changing.HOUR:
                changesystemhour(True)
            else:
                changesystemminute(True)
            scheduleBuildUI()
        case Mode.CHANGE_VOLUME:
            volume = min(volume + 5, 100)
            set_volume_os(volume)
            scheduleBuildUI()
        case _:
            print("unknown case caught...")
            exit()
    
# This will be for changing the minute
def buttonD():
    global alarmtimehour
    global alarmtimeminute
    global volume
    match currentmode:
        case Mode.DEFAULT:
            pass
        case Mode.CHANGE_ALARM_TIME:
            if changing == Changing.HOUR:
                alarmtimehour = (alarmtimehour + 23) % 24
            else:
                alarmtimeminute = (alarmtimeminute + 55) % 60
            scheduleBuildUI()
        case Mode.CHANGE_SYSTEM_TIME:
            if changing == Changing.HOUR:
                changesystemhour(False)
            else:
                changesystemminute(False)
            scheduleBuildUI()
        case Mode.CHANGE_VOLUME:
            volume = max(volume - 5, 0)
            set_volume_os(volume)
            scheduleBuildUI()
        case _:
            print("unknown case caught...")
            exit()

A.when_pressed = buttonA
B.when_pressed = buttonB
C.when_pressed = buttonC
D.when_pressed = buttonD

print("waiting for signal...")

clock_thread.start()

pause()
    
