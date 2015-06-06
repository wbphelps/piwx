#!/usr/bin/python

# PiTFT display engine for weewx
# This must run as root (sudo python lapse.py) due to framebuffer, etc.
#
# http://www.adafruit.com/products/998  (Raspberry Pi Model B)
# http://www.adafruit.com/products/1601 (PiTFT Mini Kit)
#
# Prerequisite tutorials: aside from the basic Raspbian setup and PiTFT setup
# http://learn.adafruit.com/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi
#
# (c) Copyright 2015 William B. Phelps

import argparse
import gc
import errno
import os, sys, signal, linecache
import traceback

#os.environ['PYGAME_FREETYPE'] = '1'
import pygame
from pygame.locals import *

from time import sleep, time
from datetime import datetime, timedelta
#import ephem #, ephem.stars
import math
import logging

import threading
from multiprocessing import Event
from multiprocessing.connection import Client
from types import NoneType

from virtualKeyboard import VirtualKeyboard
from pyColors import pyColors
Colors = pyColors()

parser = argparse.ArgumentParser(description='piwx weather data display')
parser.add_argument('host', default='127.0.0.1', nargs='?', help='hostname or ip address')
parser.add_argument('--key', default='wxdata key', nargs='?', help='security key')
Bparser.add_argument('--port', default=6000, type=int, nargs='?', help='port number')
args = parser.parse_args()
print args

_address = args.host
_port = args.port
_key = args.key

_lock = threading.Lock()

pid = str(os.getpid())
file("/var/run/piwx.pid",'w+').write("%s\n" % pid)

# -------------------------------------------------------------

switch_1 = 1 # GPIO pin 18 - left to right with switches on the top
switch_2 = 2 # GPIO pin 21/27
switch_3 = 3 # GPIO pin 22
switch_4 = 4 # GPIO pin 23

backlightpin = 252

#tNow = datetime.utcnow()

# ---------------------------------------------------------------

_wxdata = {}
_wdlist = []
_wdmean = 0
_wxname = "No Data"
_wxreq=('wxloop', 'dateTime','outTemp','dewpoint','outHumidity','dayRain','rainRate','barometer','windGust','windGustDir','radiation','windSpeed','windDir')

def printException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print 'EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj)

def getWxData(address, key, req):
  try:
    conn = None
#    print "connecting {}".format(address)
    conn = Client(address, authkey=key)
#    print "send 'wxloop'"
#    conn.send('wxloop') # request loop data
    conn.send(req) # request data
    data = conn.recv() # get data packet
#    print "received {}".format(len(data))
    conn.close()
    return data
  except Exception, e:
#    syslog.syslog(syslog.LOG_ERR, "wxdata: error: %s" % e)
    print("conn error: %s" % e)
    if not isinstance(conn,NoneType):
      print "closing"
      conn.close()
    conn = None
    del conn
    gc.collect()  # try to get connection to clear
    sleep(5)
    return { None }

class wxFetch(threading.Thread):
  def __init__(self, address, key):
    global _wxname
    self.address = address
    self.key = key
    self.exit = Event()
    self.lastwd = 0
    self.wdlist = []
    self.wdmean = 0
    super(wxFetch, self).__init__()
#    print "wxFetch init"
    name = getWxData(self.address, self.key, "wxname")  # get station name
    if isinstance(name,str):  _wxname = name
    print "station name: {}".format(_wxname)
  def run(self):
    global _wxdata, _wdmean, _wdlist, _wxreq, _wxname, _lock
    print 'server address:' + format(self.address)
    print 'server process id:', os.getpid()
    while True:
      st = time()
      if self.exit.is_set():
        print "exiting..."
        break
      data = getWxData(self.address, self.key, _wxreq)
      if isinstance(data,dict) and len(data)>11:
#        print "wxdata: {}".format(data)
        wd = data['windDir']
        if isinstance(wd,float):
          wdi = int(wd)
          self.lastwd = wdi
        else:
          wdi = self.lastwd
        if abs(wdi-self.wdmean)>180:
          if wdi<180: wdi += 360
#        self.wdlist.append(wdi)
#        self.wdlist = self.wdlist[-30:]
        self.wdlist = (self.wdlist+[wdi])[-30:]  # concatenate new wd and truncate list
        self.wdmean = sum(self.wdlist)/len(self.wdlist)  # calculate new mean
#        with _lock:
        _wxdata = data
        _wdlist = self.wdlist
        _wdmean = self.wdmean
#          print "wdlist: ", _wdlist
#           _wdlow = min(_wdlist)
#           _wdhigh = max(_wdlist)
#           print "wdlist: min {}, max {}".format(wdl, wdh)
      dt = 2-(time()-st)
#      print "dt={}".format(dt)
      if dt>0:  sleep(dt)

    print "server ended"

  def stop(self):
    print "stopping server"
    self.exit.set()
    
def invert(img):
   inv = pygame.Surface(img.get_rect().size, pygame.SRCALPHA)
   inv.fill((255,255,255,255))
   inv.blit(img, (0,0), None, BLEND_RGB_SUB)
   return inv

def enum(**enums):
    return type('Enum', (), enums)

def StopAll():
    print 'StopAll'
#    global blinkstick_on, BLST, gps_on
    _thread1.stop()
    pygame.quit()
    sleep(1)
#    if blinkstick_on:
#      BLST.stop()

def Exit():
    print 'Exit'
    StopAll()
    sys.exit(0)

def signal_handler(signal, frame):
    print 'SIGNAL {}'.format(signal)
    Exit()

def osCmd(cmd):
    out = os.popen(cmd).read()
    logging.info(cmd)
    logging.info(out)
#    logging.error(err)

def backlight(set):
    os.system("echo 252 > /sys/class/gpio/export")
    os.system("echo 'out' > /sys/class/gpio/gpio252/direction")
    if (set):
#        gpio.digitalWrite(backlightpin,gpio.LOW)
        os.system("echo '1' > /sys/class/gpio/gpio252/value")
    else:
#        gpio.digitalWrite(backlightpin,gpio.HIGH)
        os.system("echo '0' > /sys/class/gpio/gpio252/value")

def Shutdown():
    print 'Shutdown'
    StopAll()
    sleep(1)
    os.system("/usr/bin/sudo /sbin/shutdown -h now")
    sys.exit(0)

def Reboot():
    print 'Shutdown'
    StopAll()
    sleep(1)
    os.system("/usr/bin/sudo /sbin/reboot")
    sys.exit(0)

# ---------------------------------------------------------------------

# Set up GPIO pins
#gpio = wiringpi.GPIO(wiringpi.GPIO.WPI_MODE_GPIO)
import os
# Init framebuffer/touchscreen environment variables
#os.putenv('FRAMEBUFFER', '/dev/fb1') # wbp
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV'      , '/dev/fb1')
os.putenv('SDL_MOUSEDRV'   , 'TSLIB')
#os.putenv('SDL_MOUSEDEV'   , '/dev/input/event0')
os.putenv('SDL_MOUSEDEV'   , '/dev/input/touchscreen')

# ---------------------------------------------------------------------

def pageAuto():
#  from showInfo import showInfo
#  from showSky import showSky
  from showWx import showWx
  global _page, Screen, _wxname, _wxdata, _wdmean, _wdlist, _lock
#  stime = 1
  print 'Auto'

#  print "wxname: ", _wxname
  swx = showWx(Screen, _wxname)
  while (_page == pageAuto):
#    wxdata = getWxData()
#    with _lock:
#      wdl = _wdlist
    if len(_wxdata)>10:
      swx.show(_wxdata, _wdmean, _wdlist)
    else:
      print "data error: {}".format(_wxdata)
    if checkEvent(): return
    sleep(1)

  print 'end Auto'

# ---------------------------------------------------------------------

def pageAddress():
  global Screen, _page, _address, _thread1
  print 'Address'
  while _page == pageAddress:
    if checkEvent(): return
    vkey = VirtualKeyboard(Screen,Colors.White,Colors.Yellow) # create a virtual keyboard
    txt = vkey.run(_address)
    if len(txt)>0:
      try:
        _address = txt
        _thread1.stop()  # stop the server
        sleep(5)
        _thread1 = wxFetch((_address,_port), _key)
        _thread1.daemon = True
        _thread1.start()
      except:
        printException()
        pass

    _page = pageMenu
    return

# ---------------------------------------------------------------------

def pagePort():
  global Screen, _page, _port, _thread1
  print 'Port'
  while _page == pagePort:
    if checkEvent(): return
    vkey = VirtualKeyboard(Screen,Colors.White,Colors.Yellow) # create a virtual keyboard
    txt = vkey.run(format(_port))
    if len(txt)>0:
      try:
          _port = int(txt)
          _thread1.stop()  # stop the server
          sleep(5)
          _thread1 = wxFetch((_address,_port), _key)
          _thread1.daemon = True
          _thread1.start()
      except:
          printException()
          pass

    _page = pageMenu
    return

#  ----------------------------------------------------------------

def pageSaveScreen():
  global Screen, _page
  print 'SaveScreen'

#  vkey = VirtualKeyboard(Screen,Colors.White,Colors.Yellow) # create a virtual keyboard
#  txt = vkey.run(datetime.now().strftime('screen-%y%m%d-%H%M%S.jpg'))
#  if len(txt)>0:
#    pygame.image.save(screen_copy, txt)

  _page = pageMenu
  return

#  ----------------------------------------------------------------

def pageWifi():
  global _page
  print 'Wifi'
  _page = pageMenu # temp
  return # temp
#  while (page == pageWifi):
#    if checkEvent():
#      return
#      sleep(0.5)

#  ----------------------------------------------------------------

def pageRedOnly():
  global Menu, _page
  print 'RedOnly'

#  Menu = setMenu()
#  _page = pageMenu # temp
  return # temp

#  ----------------------------------------------------------------

def pageExit():
    # confirm with a prompt?
    Exit()

def pageReboot():
    # confirm with a prompt?
    Reboot()

def pageShutdown():
    # confirm with a prompt?
    Shutdown()

def pageSleep():
    global _page
    print 'Sleep'
    backlight(False)
    while (_page == pageSleep):
        if checkEvent():
            backlight(True)
            break
        sleep(1)

#  ----------------------------------------------------------------

def pageCalibrate():
    global _page
    print 'Calibrate'

    osCmd('sudo TSLIB_FBDEVICE=/dev/fb1 TSLIB_TSDEVICE=/dev/input/event0 ts_calibrate')

    _page = pageMenu
    return

#  ----------------------------------------------------------------

class menuItem():
    def __init__(self,caption,position,font,color,_page,escapeKey=False,subMenu=False,screenCap=False):
        self.caption = caption
        self.position = position
        self.font = font
        self.color = color
        self.page = _page
        self.escapeKey = escapeKey
        self.subMenu = subMenu
        self.screenCap = screenCap

def setMenu():
#    global menuScrn, Menu
    Menu = []

#    txtFont = pygame.font.SysFont('Courier', 23, bold=True)
    txtFont = pygame.font.SysFont('Courier', 20, bold=True)
    item = menuItem('X',(Width-25,5),txtFont,pygame.Color("Red"),None,escapeKey=True) # escape key
#    item.escapekey = True # tag special key
    Menu.append(item)

#    txtFont = pygame.font.SysFont("Arial", 23, bold=True)
    txtFont = pygame.font.SysFont("Arial", 20, bold=True)
    txt = txtFont.render('XXXX', 1, Colors.Yellow)
    txtR = txt.get_rect()

    lx = 5 # left side
    ly = 5 # line position
#    lh = 28 # line height
    lh = txtR.height # line height

    Menu.append(menuItem('Auto',   (lx,ly),txtFont,pygame.Color("Yellow"),pageAuto))
    ly += lh
#    Menu.append(menuItem('Demo',   (lx,ly),txtFont,pygame.Color("Yellow"),pageDemo))
    ly += lh
#    Menu.append(menuItem('Sky',    (lx,ly),txtFont,pygame.Color("Yellow"),pageSky))
    ly += lh
#    Menu.append(menuItem('Crew', (lx,ly),txtFont,pygame.Color("Yellow"),pageCrew))
    ly += lh
#    Menu.append(menuItem('Passes', (lx,ly),txtFont,pygame.Color("Yellow"),pagePasses))
    ly += lh
#    Menu.append(menuItem('GPS',    (lx,ly),txtFont,pygame.Color("Yellow"),pageGPS)) # temp
    ly += lh/2
    ly += lh
#    if Colors.RedOnly:
#      Menu.append(menuItem('FullColor', (lx,ly),txtFont,Colors.Red,pageRedOnly))
#    else:
#      Menu.append(menuItem('RedOnly',   (lx,ly),txtFont,Colors.Red,pageRedOnly))
    ly += lh
#    Menu.append(menuItem('Wifi',   (lx,ly),txtFont,Colors.Yellow,pageWifi))

    lx = Width/2 # right half
    ly = 5 # line position
#    lh = 28 # line height
    Menu.append(menuItem('Address', (lx,ly),txtFont,pygame.Color("Yellow"),pageAddress))
    ly += lh
    Menu.append(menuItem('Port', (lx,ly),txtFont,pygame.Color("Yellow"),pagePort))
    ly += lh
#    Menu.append(menuItem('TLEs',     (lx,ly),txtFont,pygame.Color("Yellow"),pageTLEs))
    ly += lh
    ly += lh/2
    Menu.append(menuItem('Calibrate',(lx,ly),txtFont,pygame.Color("LightBlue"),pageCalibrate))
    ly += lh
    Menu.append(menuItem('Save',     (lx,ly),txtFont,pygame.Color("LightBlue"),pageSaveScreen,screenCap=True))
    ly += lh
#    Menu.append(menuItem('Sleep',    (lx,ly),txtFont,pygame.Color("LightBlue"),pageSleep))
    ly += lh

    Menu.append(menuItem('Exit',     (lx,ly),txtFont,pygame.Color("Red"),pageExit))
    ly += lh
    ly += lh/2
    Menu.append(menuItem('Reboot', (lx,ly),txtFont,pygame.Color("Red"),pageReboot))
    ly += lh
    Menu.append(menuItem('Shutdown', (lx,ly),txtFont,pygame.Color("Red"),pageShutdown))

    drawMenu(Menu)
    return Menu

def drawMenu(Menu):
    global Screen,  menuScrn, menuRect

    menuScrn = pygame.Surface((Width,Height)) # use the entire screen for the menu
    menuRect = menuScrn.get_rect()

    for item in Menu:
        txt = item.font.render(item.caption, 1, item.color)
        item.rect = menuScrn.blit(txt, item.position)
        if item.escapeKey:
#            item.rect.x, item.rect.y, item.rect.width, item.rect.height = Width-32, 4, 28, 28 # make the X easier to hit
            item.rect.x, item.rect.y, item.rect.width, item.rect.height = Width-32, 4, 25, 25 # make the X easier to hit
            pygame.draw.rect(menuScrn, pygame.Color("Red"), item.rect, 1)

    return Menu

def pageMenu():
    global Screen, menuScrn, menuRect
    global screen_copy
    print 'Menu'

    Screen.blit(menuScrn, menuRect)
    pygame.display.update()

    while _page == pageMenu:
        if checkEvent(): break
    gc.collect()

#  ----------------------------------------------------------------

global menuScrn,  Menu

def checkEvent():
    global Screen, _page
    global menuScrn, menuRect, Menu, pageLast
    global screen_copy
    global tGPSupdate
    global mouseX, mouseY

#    sw1 = not wiringpi.digitalRead(switch_1) # Read switch
#    if sw1: print 'switch 1'
#    sw2 = not wiringpi.digitalRead(switch_2) # Read switch
#    if sw2: print 'switch 2'
#    sw3 = not wiringpi.digitalRead(switch_3) # Read switch
#    if sw3: print 'switch 3'
#    sw4 = not wiringpi.digitalRead(switch_4) # Read switch
#    if sw4: print 'switch 4'
    
#    buttons = Buttons.get()
#    if Buttons.keybits:
#      print 'buttons {} {}'.format(Buttons.keybits, buttons)
#    if Buttons.keybits == 17:
#      Exit()

#    ev = pygame.event.poll()
    ret = False
    evl = pygame.event.get()
    for ev in evl:
        if (ev.type == pygame.NOEVENT):
            print 'NOEVENT' # ???
            pass
#    print "ev: {}".format(ev)

        if (ev.type == pygame.MOUSEBUTTONDOWN):
          print "mouse dn, x,y = {}, page={}".format(ev.pos,_page)
          mouseX,mouseY = ev.pos # remember position
          if _page == pageMenu: # what numerical value ???
            for item in Menu:
              if item.rect.collidepoint(mouseX,mouseY):
                pygame.draw.rect(Screen, pygame.Color("Cyan"), item.rect, 1)
            pygame.display.update()
          else:
            screen_copy = Screen.copy() # don't capture menu screen

        if (ev.type == pygame.MOUSEBUTTONUP):
          print "mouse up, x,y = {}".format(ev.pos)
          x,y = ev.pos # use mouse down positions for menu selection

#          print "page {}".format(_page)
          if _page != pageMenu: # other menu pages???
              pageLast = _page # for escape key
              _page = pageMenu
              Screen.blit(menuScrn, menuRect)
              ret = True
          else:
#            print "check xy {},{}".format(mouseX,mouseY)
            for item in Menu:
              if item.rect.collidepoint(mouseX,mouseY):
                if item.escapeKey:
                    _page = pageLast
                    ret = True
#                if item.subMenu:
#                    item.page() # call it now
#                    break
#                elif item.screenCap:
#                    pygame.image.save(screen_copy, "screenshot.jpg")
#                    _page = pageLast
#                    ret = True
                elif item.page == None:
                    pass
                else:
#                    print "--> page {}".format(item.caption)
                    _page = item.page
                    ret = True
                break

    return ret


#  ----------------------------------------------------------------

#Colors = pyColors()

# Init pygame and screen
pygame.display.init()
pygame.font.init()
pygame.mouse.set_visible(False)

size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
print "Framebuffer size: %d x %d" % (size[0], size[1])
#screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
Screen = pygame.display.set_mode(size)

bg = Screen.copy()
bgRect = bg.get_rect()
Width = bgRect.width
Height = bgRect.height

#bg.fill((255,255,255))
#Screen.blit(bg, bgRect)
#pygame.display.update()
#sleep(3)

bg.fill((0,0,0))

txtColor = pygame.Color("Yellow")
txtFont = pygame.font.SysFont("Arial", 30, bold=True)
txt = txtFont.render('Weather Pi' , 1, txtColor)
bg.blit(txt, (15, 28))
txt = txtFont.render('by' , 1, txtColor)
bg.blit(txt, (15, 64))
txt = txtFont.render('William Phelps' , 1, txtColor)
bg.blit(txt, (15, 100))
Screen.blit(bg, bgRect)
pygame.display.update()
sleep(1)

#logging.basicConfig(filename='/home/pi/isstracker/isstracker.log',filemode='w',level=logging.DEBUG)
#logging.info("ISS-Tracker System Startup")

#atexit.register(Exit)

#net = checkNet()
#if net.up:
#    logging.info("Network up {}".format(net.interface))
#else:
#    logging.info("Network down")

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)
#print "sigterm handler set"

#Buttons = lcdButtons()

#    if opt.blinkstick:
#if True:
#    blinkstick_on = True
#    BLST = BlinkStick()
#    BLST.start(-3, 90, 3)
#    sleep(2)
#    BLST.stop()

Menu = setMenu() # set up menu
_page = pageAuto
#_page = pageMenu

# start a thread to request the data from the weewx server
_thread1 = wxFetch((_address,_port), _key)
_thread1.daemon = True
_thread1.start()
print "fetcher started"

#fonts = pygame.font.get_fonts()
#print fonts

while(True):

  try:
    _page()
    gc.collect()

  except SystemExit:
    print 'SystemExit'
    sys.exit(0)
  except:
    print '"Except:', sys.exc_info()[0]
    _page = None
#    print traceback.format_exc()
    StopAll()
    raise
