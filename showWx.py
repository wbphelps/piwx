# show main Wx  page

import pygame
from pygame.locals import *
import math
from datetime import datetime, timedelta
import calendar
import ephem
from time import sleep
import time
import syslog
import linecache, sys

R90 = math.radians(90) # 90 degrees in radians

Black = (0,0,0)

col1 = 5
col2 = 112

lsize = 20
line0 = 6
line1 = 14+lsize
line2 = line1+lsize
line3 = line2+lsize
line4 = line3+lsize
line5 = line4+lsize
line6 = line5+lsize
line7 = line6+lsize
line8 = line7+lsize
line9 = line8+lsize

def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print 'EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj)

def utc_to_local(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)

class showWx():

  def getxy(self, alt, azi): # alt, az in radians
# thanks to John at Wobbleworks for the algorithm
    r = (R90 - alt)/R90
    x = r * math.sin(azi)
    y = r * math.cos(azi)
    x = int(self.cX + x * self.cD) # scale to radius, center on plot
    y = int(self.cY - y * self.cD) # scale to radius, center on plot
    return (x,y)

  def getxyD(self, alt, azi): # alt, az in degrees
    return self.getxy(math.radians(alt), math.radians(azi))

  def getval(self, wxdata, str): # fetch value from wxdata dict, convert to number
    s = wxdata[str]
    try:
      return int(s)
    except ValueError:
      return float(s)

  def __init__(self, screen, wxname):
#    self.screen = pygame.Surface((320,240)) # a new screen layer
    self.screen = screen
#    self.bgColor = (0,0,0)
    self.bg = screen.copy()
    self.bg.fill((0,0,0))
    self.bgRect = self.bg.get_rect()
    self.width = self.bgRect.width
    self.height = self.bgRect.height
#    self.cX = 360
#    self.cY = 160
#    self.cD = 60
    self.cX = 245
    self.cY = 120
    self.cD = 55
    self.wszero = 0
    self.lasttr = 0  # time of last record

    txtColor = pygame.Color("red")

#    txtFont = pygame.font.SysFont("Arial", 30, bold=True)
    txtFont = pygame.font.SysFont("LiberationSansNarrow", 24, bold=True)
#    txt = txtFont.render('Weather Data' , 1, txtColor)
    txt = txtFont.render(wxname, 1, txtColor)
    self.bg.blit(txt, (col1, line0))

#    txtFont = pygame.font.SysFont("Arial", 24, bold=True)
    txtFont = pygame.font.SysFont("LiberationSansNarrow", 20, bold=True)
    txt = txtFont.render("Temperature:" , 1, txtColor)
    self.bg.blit(txt, (col1, line1))
    txt = txtFont.render("Dew Point:" , 1, txtColor)
    self.bg.blit(txt, (col1, line2))
    txt = txtFont.render("Humidity:" , 1, txtColor)
    self.bg.blit(txt, (col1, line3))
    txt = txtFont.render("Rain Rate:" , 1, txtColor)
    self.bg.blit(txt, (col1, line4))
    txt = txtFont.render("Rain today:" , 1, txtColor)
    self.bg.blit(txt, (col1, line5))
    txt = txtFont.render("Barometer:" , 1, txtColor)
    self.bg.blit(txt, (col1, line6))
    txt = txtFont.render("Wind Gust:" , 1, txtColor)
    self.bg.blit(txt, (col1, line7))
    txt = txtFont.render("Direction:" , 1, txtColor)
    self.bg.blit(txt, (col1, line8))
    txt = txtFont.render("Solar:" , 1, txtColor)
    self.bg.blit(txt, (col1, line9))

    txtColor = pygame.Color("cyan")
#    txtFont = pygame.font.SysFont("Arial", 20, bold=True)
    txtFont = pygame.font.SysFont("Arial", 16, bold=True)
    rOff = -20

    pygame.draw.circle(self.bg, txtColor, (self.cX, self.cY), self.cD, 2)

    txt = txtFont.render("N" , 1, txtColor)
    rect = txt.get_rect()
    rect.centerx, rect.centery = self.getxyD(rOff,0)
    self.bg.blit(txt, rect)
    txt = txtFont.render("E" , 1, txtColor)
    rect = txt.get_rect()
    rect.centerx, rect.centery = self.getxyD(rOff,90)
    self.bg.blit(txt, rect)
    txt = txtFont.render("S" , 1, txtColor)
    rect = txt.get_rect()
    rect.centerx, rect.centery = self.getxyD(rOff,180)
    self.bg.blit(txt, rect)
    txt = txtFont.render("W" , 1, txtColor)
    rect = txt.get_rect()
    rect.centerx, rect.centery = self.getxyD(rOff-4,270) # W is bigger
    self.bg.blit(txt, rect)

    txtFont = pygame.font.SysFont("Arial", 15, bold=True)
    txt = txtFont.render("mph" , 1, txtColor)
    rect = txt.get_rect()
    rect.centerx, rect.centery = (self.cX,self.cY+14)
    self.bg.blit(txt, rect)

#    txtFont = pygame.font.SysFont("Arial", 15, bold=True)  ???
    txtFont = pygame.font.SysFont("Arial", 15, bold=True)
    txt = txtFont.render('Touch Screen for Menu' , 1, pygame.Color("yellow"))
    rect = txt.get_rect()
    rect.right = self.width-10
    rect.bottom = self.height
    self.bg.blit(txt, rect)

    screen.blit(self.bg, self.bgRect)
    pygame.display.update()

# ######################################################################################

  def show(self,wxdata,wdmean,wdlist):

    lastwd = wdlist[-1]

    txtColor = pygame.Color("red")
#    txtFont = pygame.font.SysFont("Arial", 24, bold=True)
    txtFont = pygame.font.SysFont("LiberationMono", 19, bold=True)
    self.screen.blit(self.bg, self.bgRect) # write background image

    try:
      if not isinstance(wxdata,dict) or len(wxdata) < 12:
        txt = txtFont.render("Bad Data", 1, txtColor)
        rect = txt.get_rect()
        rect.right = self.width-10
        rect.top = line0+30
        self.screen.blit(txt, rect)
        pygame.display.flip()
        return

      tvc = pygame.Color("green")

#      txt = txtFont.render(time.strftime("%b %d, %Y %H:%M:%S",time.localtime()), 1, tvc)
      txt = txtFont.render(time.strftime("%H:%M:%S",time.localtime()), 1, tvc)
      rect = txt.get_rect()
      rect.right = self.width-10
      rect.top = line0+3
      self.screen.blit(txt, rect)
#      self.screen.blit(txt, (144,line0+3))

      tr = wxdata['dateTime']
      if tr == None:
        txt = txtFont.render("No Data", 1, txtColor)
        rect = txt.get_rect()
        rect.right = self.width-10
#        rect.top = line0+30
        rect.top = line0+20
        self.screen.blit(txt, rect)
        pygame.display.flip()
        pygame.display.flip()
        return  # if not even dateTime, nothing more we can do

      txtFont = pygame.font.SysFont("LiberationSansNarrow", 19, bold=True)

      td = int(time.time() - tr) # delta between localtime and dateTime in record
#      print "td: {}".format(td)
      tdc = pygame.Color("red") if td > 30 else tvc
#      txt = txtFont.render(time.strftime("%H:%M:%S",time.localtime(int(wxdata['dateTime']))), 1, tdc)
      txt = txtFont.render(format(td), 1, tdc)
#      self.screen.blit(txt, (375, line0+30))
      rect = txt.get_rect()
      rect.right = self.width-10
#      rect.top = line0+30
      rect.top = line0+20
      self.screen.blit(txt, rect)

      txt = txtFont.render(format(wxdata['outTemp'],"0.1f"), 1, tvc)
      self.screen.blit(txt, (col2, line1))

      tv = wxdata['dewpoint']
      tv = "---" if tv == None else format(tv,"0.1f")
      txt = txtFont.render(tv, 1, tvc)
      self.screen.blit(txt, (col2, line2))

      txt = txtFont.render(format(wxdata['outHumidity'],"0.0f"), 1, tvc)
      self.screen.blit(txt, (col2, line3))

      txt = txtFont.render(format(wxdata['rainRate'],"0.1f"), 1, tvc)
      self.screen.blit(txt, (col2, line4))

      txt = txtFont.render(format(wxdata['dayRain'],"0.2f"), 1, tvc)
      self.screen.blit(txt, (col2, line5))

      txt = txtFont.render(format(wxdata['barometer'],"0.2f"), 1, tvc)
      self.screen.blit(txt, (col2, line6))

      txt = txtFont.render(format(wxdata['windGust'],"0.0f"), 1, tvc)
      self.screen.blit(txt, (col2, line7))

      tv = wxdata['windGustDir']
      tv = "---" if tv == None else format(tv,"0.0f")
      txt = txtFont.render(tv, 1, tvc)
      self.screen.blit(txt, (col2, line8))

      tv = wxdata['radiation']
      tv = "---" if tv == None else format(tv,"0.0f")
      txt = txtFont.render(tv, 1, tvc)
      self.screen.blit(txt, (col2, line9))

#  wind gauge

#      wsFont = pygame.font.SysFont("Arial", 30, bold=True)
      wsFont = pygame.font.SysFont("Arial", 24, bold=True)

#  wind speed
      ws = wxdata['windSpeed']
      tv = format(ws, "0.0f")
      wsc = pygame.Color("green")
      if ws == 0:
        self.wszero += 1
        if self.wszero > 30:
          wsc = pygame.Color("grey")
      else:
        self.wszero = 0

      txt = wsFont.render(tv, 1, wsc)
      rect = txt.get_rect()
      rect.centerx, rect.centery = (self.cX,self.cY-6)
      self.screen.blit(txt, rect)

#  wind direction
      tv = wxdata['windDir']
      wd = lastwd if tv == None else int(tv)

#      wdt = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"][int(((wd+22.5/2)%360)/22.5)]
#      txt = txtFont.render(wdt, 1, wsc)
#      rect = txt.get_rect()
#      rect.centerx, rect.centery = (self.cX,self.cY+100)
#      self.screen.blit(txt, rect)

      txt = txtFont.render(format(wd), 1, wsc)
      rect = txt.get_rect()
#      rect.centerx, rect.centery = (self.cX,self.cY+100)
      rect.centerx, rect.centery = (self.cX,self.cY+self.cD+30)
      self.screen.blit(txt, rect)

#      pwd = lastwd

#      tw = 8 # triangle base offset from center
#      to = -5 # triangle base offset past circle
#      tp = 30 # triangle point
      tw = 10 # triangle base offset from center
      tb = 28 # triangle base offset 
      tp = -6 # triangle point offset

      # show wind direction limits (last 60 seconds)
      wlc = pygame.Color("blue")
      wdlow = min(wdlist)
      wdhigh = max(wdlist)
      pygame.draw.lines(self.screen, wlc, False, (self.getxyD(tb,wdlow+tw), self.getxyD(tp,wdlow), self.getxyD(tb,wdlow-tw)), 3)
      pygame.draw.lines(self.screen, wlc, False, (self.getxyD(tb,wdhigh+tw), self.getxyD(tp,wdhigh), self.getxyD(tb,wdhigh-tw)), 3)
#      pygame.draw.line(self.screen, wlc, self.getxyD(to+1,wdlow), self.getxyD(tp-1,wdlow), 2)
#      pygame.draw.line(self.screen, wlc, self.getxyD(to+1,wdhigh), self.getxyD(tp-1,wdhigh), 2)

#      # if wd is changing, draw triangles to show motion
#      if (wd != pwd):
#        if abs(wd-pwd)>180:
#          if wd<180: wd += 360
#          if pwd<180: pwd += 360
#      # draw the first wd limit line
#        if (wd>pwd):  # increasing
#          l = range(pwd,wd,12)
#        else: # decreasing or no change
#          l = range(pwd,wd,-12)
#        for i in l:
#          d = i%360
##          pygame.draw.polygon(self.screen, wsc, (self.getxyD(to,d+tw), self.getxyD(tp,d), self.getxyD(to,d-tw)), 2)
#          pygame.draw.polygon(self.screen, wsc, (self.getxyD(tb,d+tw), self.getxyD(tp,d), self.getxyD(tb,d-tw)), 1)
#          pygame.display.flip()
#          sleep(0.02)

      wd = wd%360
      pygame.draw.polygon(self.screen, wsc, (self.getxyD(tb,wd+tw-1), self.getxyD(tp+2,wd), self.getxyD(tb,wd-tw+1)), 0)

      pygame.display.flip()
#    pygame.display.update()

#      self.lastwd = wd
      self.lasttr = tr

    except Exception, e:
      print "showWx: error"
#      print "Except:", sys.exc_info()[0]
      PrintException()
      print "wxdata:", wxdata
