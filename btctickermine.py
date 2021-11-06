#!/usr/bin/python3
from PIL import Image, ImageOps
from PIL import ImageFont
from PIL import ImageDraw
import currency
import os
import sys
import logging
import RPi.GPIO as GPIO
from waveshare_epd import epd2in7
import time
import requests
import urllib, json
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import yaml
import socket
import textwrap
import argparse
import decimal

import sys
sys.path.append(r'lib')
import signal
import epd2in7b
import epdconfig
import time
from PIL import Image, ImageDraw, ImageFont
import traceback


import pyowm


if sys.version_info[0] < 3:
    raise Exception("Must be using Python 3")

owm = pyowm.OWM('ed8083c1eb08141269b061b1e8677907')

# You can invoke the weather apis by City Name, City ID, Lat/Long or
# by Zip Code.
# According to Open Weather Map "We recommend to call API by city ID to get unambiguous result for your city."
#
# Find your own city id here:
# http://bulk.openweathermap.org/sample/city.list.json.gz
# Replace city_id below with the city id of your choice
#

# REPLACE WITH YOUR CITY ID
city_id = 2786345  # Mountain View, CA, USA

# An easy way to display icons and artwork on your ePaper display is to use a font like
# Meteocons, which maps font letters to specific icons, so by printing a character "B" you can print
# a Sunny icon!
#
# Open Weather Map has weather codes for the current weather report, that correspond to different
# conditions like sunny, cloudy, etc. Check Weather Condition Codes under
# https://openweathermap.org/weather-conditions
# for the full list of weather codes.
#
# Map weather code from OWM to meteocon icons.
#
# This enables us to easily use artwork and icons
# for display by simply using the character corresponding to that icon!
#
# Refer to http://www.alessioatzeni.com/meteocons/ for the mapping of meteocons to characters,
# and modify the dictionary below to change icons you want to use for different weather conditions!
# Meteocons is free to use - you can customize the icons - do consider contributing back to Meteocons!

weather_icon_dict = {200: "6", 201: "6", 202: "6", 210: "6", 211: "6", 212: "6",
                     221: "6", 230: "6", 231: "6", 232: "6",

                     300: "7", 301: "7", 302: "8", 310: "7", 311: "8", 312: "8",
                     313: "8", 314: "8", 321: "8",

                     500: "7", 501: "7", 502: "8", 503: "8", 504: "8", 511: "8",
                     520: "7", 521: "7", 522: "8", 531: "8",

                     600: "V", 601: "V", 602: "W", 611: "X", 612: "X", 613: "X",
                     615: "V", 616: "V", 620: "V", 621: "W", 622: "W",

                     701: "M", 711: "M", 721: "M", 731: "M", 741: "M", 751: "M",
                     761: "M", 762: "M", 771: "M", 781: "M",

                     800: "1",

                     801: "H", 802: "N", 803: "N", 804: "Y"
                     }

dirname = os.path.dirname(__file__)
picdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'images')
fontdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fonts/googlefonts')
configfile = os.path.join(os.path.dirname(os.path.realpath(__file__)),'config.yaml')
font_date = ImageFont.truetype(os.path.join(fontdir,'PixelSplitter-Bold.ttf'),11)
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
button_pressed = 0

def internet(hostname="google.com"):
    """
    Host: google.com
    """
    try:
        # see if we can resolve the host name -- tells us if there is
        # a DNS listening
        host = socket.gethostbyname(hostname)
        # connect to the host -- tells us if the host is actually
        # reachable
        s = socket.create_connection((host, 80), 2)
        s.close()
        return True
    except:
        logging.info("Google says No")
        time.sleep(1)
    return False

def human_format(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

def _place_text(img, text, x_offset=0, y_offset=0,fontsize=40,fontstring="Forum-Regular", fill=0):
    '''
    Put some centered text at a location on the image.
    '''
    draw = ImageDraw.Draw(img)
    try:
        filename = os.path.join(dirname, './fonts/googlefonts/'+fontstring+'.ttf')
        font = ImageFont.truetype(filename, fontsize)
    except OSError:
        font = ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf', fontsize)
    img_width, img_height = img.size
    text_width, _ = font.getsize(text)
    text_height = fontsize
    draw_x = (img_width - text_width)//2 + x_offset
    draw_y = (img_height - text_height)//2 + y_offset
    draw.text((draw_x, draw_y), text, font=font,fill=fill )

def writewrappedlines(img,text,fontsize=16,y_text=20,height=15, width=25,fontstring="Roboto-Light"):
    lines = textwrap.wrap(text, width)
    numoflines=0
    for line in lines:
        _place_text(img, line,0, y_text, fontsize,fontstring)
        y_text += height
        numoflines+=1
    return img

def getgecko(url):
    try:
        geckojson=requests.get(url, headers=headers).json()
        connectfail=False
    except requests.exceptions.RequestException as e:
        logging.error("Issue with CoinGecko")
        connectfail=True
        geckojson={}
    return geckojson, connectfail

def getData(config,other):
    """
    The function to grab the data (TO DO: need to test properly)
    """

    sleep_time = 10
    num_retries = 5
    whichcoin,fiat=configtocoinandfiat(config)
    logging.info("Getting Data")
    days_ago=int(config['ticker']['sparklinedays'])
    endtime = int(time.time())
    starttime = endtime - 60*60*24*days_ago
    starttimeseconds = starttime
    endtimeseconds = endtime
    geckourlhistorical = "https://api.coingecko.com/api/v3/coins/"+whichcoin+"/market_chart/range?vs_currency="+fiat+"&from="+str(starttimeseconds)+"&to="+str(endtimeseconds)
    logging.debug(geckourlhistorical)
    timeseriesstack = []
    for x in range(0, num_retries):
        rawtimeseries, connectfail=  getgecko(geckourlhistorical)
        if connectfail== True:
            pass
        else:
            logging.debug("Got price for the last "+str(days_ago)+" days from CoinGecko")
            timeseriesarray = rawtimeseries['prices']
            length=len (timeseriesarray)
            i=0
            while i < length:
                timeseriesstack.append(float (timeseriesarray[i][1]))
                i+=1
            # A little pause before hiting the api again
            time.sleep(1)
            # Get the price
        if config['ticker']['exchange']=='default':
            geckourl = "https://api.coingecko.com/api/v3/coins/markets?vs_currency="+fiat+"&ids="+whichcoin
            logging.debug(geckourl)
            rawlivecoin , connectfail = getgecko(geckourl)
            if connectfail==True:
                pass
            else:
                logging.debug(rawlivecoin[0])
                liveprice = rawlivecoin[0]
                pricenow= float(liveprice['current_price'])
                alltimehigh = float(liveprice['ath'])
                # Quick workaround for error being thrown for obscure coins. TO DO: Examine further
                try:
                    other['market_cap_rank'] = int(liveprice['market_cap_rank'])
                except:
                    config['display']['showrank']=False
                    other['market_cap_rank'] = 0
                other['volume'] = float(liveprice['total_volume'])
                timeseriesstack.append(pricenow)
                if pricenow>alltimehigh:
                    other['ATH']=True
                else:
                    other['ATH']=False
        else:
            geckourl= "https://api.coingecko.com/api/v3/exchanges/"+config['ticker']['exchange']+"/tickers?coin_ids="+whichcoin+"&include_exchange_logo=false"
            logging.debug(geckourl)
            rawlivecoin, connectfail = getgecko(geckourl)
            if connectfail==True:
                pass
            else:
                theindex=-1
                upperfiat=fiat.upper()
                for i in range (len(rawlivecoin['tickers'])):
                    target=rawlivecoin['tickers'][i]['target']
                    if target==upperfiat:
                        theindex=i
                        logging.debug("Found "+upperfiat+" at index " + str(i))
        #       if UPPERFIAT is not listed as a target theindex==-1 and it is time to go to sleep
                if  theindex==-1:
                    logging.error("The exchange is not listing in "+upperfiat+". Misconfigured - shutting down script")
                    sys.exit()
                liveprice= rawlivecoin['tickers'][theindex]
                pricenow= float(liveprice['last'])
                other['market_cap_rank'] = 0 # For non-default the Rank does not show in the API, so leave blank
                other['volume'] = float(liveprice['converted_volume']['usd'])
                alltimehigh = 1000000.0   # For non-default the ATH does not show in the API, so show it when price reaches *pinky in mouth* ONE MILLION DOLLARS
                logging.debug("Got Live Data From CoinGecko")
                timeseriesstack.append(pricenow)
                if pricenow>alltimehigh:
                    other['ATH']=True
                else:
                    other['ATH']=False
        if connectfail==True:
            message="Trying again in ", sleep_time, " seconds"
            logging.warn(message)
            time.sleep(sleep_time)  # wait before trying to fetch the data again
            sleep_time *= 2  # exponential backoff
        else:
            break
    return timeseriesstack, other

def beanaproblem(message):
#   A visual cue that the wheels have fallen off
    thebean = Image.open(os.path.join(picdir,'thebean.bmp'))
    image = Image.new('L', (264, 176), 255)    # 255: clear the image with white
    draw = ImageDraw.Draw(image)
    image.paste(thebean, (60,45))
    draw.text((95,15),str(time.strftime("%-H:%M %p, %-d %b %Y")),font =font_date,fill = 0)
    writewrappedlines(image, "Issue: "+message)
    return image

def makeSpark(pricestack):
    # Draw and save the sparkline that represents historical data
    # Subtract the mean from the sparkline to make the mean appear on the plot (it's really the x axis)
    themean= sum(pricestack)/float(len(pricestack))
    x = [xx - themean for xx in pricestack]
    fig, ax = plt.subplots(1,1,figsize=(10,3))
    plt.plot(x, color='k', linewidth=6)
    plt.plot(len(x)-1, x[-1], color='r', marker='o')
    # Remove the Y axis
    for k,v in ax.spines.items():
        v.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axhline(c='k', linewidth=4, linestyle=(0, (5, 2, 1, 2)))
    # Save the resulting bmp file to the images directory
    plt.savefig(os.path.join(picdir,'spark.png'), dpi=17)
    imgspk = Image.open(os.path.join(picdir,'spark.png'))
    file_out = os.path.join(picdir,'spark.bmp')
    imgspk.save(file_out)
    plt.close(fig)
    plt.cla() # Close plot to prevent memory error
    ax.cla() # Close axis to prevent memory error
    imgspk.close()
    return

def updateDisplay(config,pricestack,other):
    """
    Takes the price data, the desired coin/fiat combo along with the config info for formatting
    if config is re-written following adustment we could avoid passing the last two arguments as
    they will just be the first two items of their string in config
    """
    with open(configfile) as f:
        originalconfig = yaml.load(f, Loader=yaml.FullLoader)
    originalcoin=originalconfig['ticker']['currency']
    originalcoin_list = originalcoin.split(",")
    originalcoin_list = [x.strip(' ') for x in originalcoin_list]
    whichcoin,fiat=configtocoinandfiat(config)
    days_ago=int(config['ticker']['sparklinedays'])
    symbolstring=currency.symbol(fiat.upper())
    if fiat=="jpy" or fiat=="cny":
        symbolstring="¥"
    pricenow = pricestack[-1]
    if config['display']['inverted'] == True:
        currencythumbnail= 'currency/'+whichcoin+'INV.bmp'
    else:
        currencythumbnail= 'currency/'+whichcoin+'.bmp'
    tokenfilename = os.path.join(picdir,currencythumbnail)
    sparkbitmap = Image.open(os.path.join(picdir,'spark.bmp'))
    ATHbitmap= Image.open(os.path.join(picdir,'ATH.bmp'))
#   Check for token image, if there isn't one, get on off coingecko, resize it and pop it on a white background
    if os.path.isfile(tokenfilename):
        logging.debug("Getting token Image from Image directory")
        tokenimage = Image.open(tokenfilename).convert("RGBA")
    else:
        logging.debug("Getting token Image from Coingecko")
        tokenimageurl = "https://api.coingecko.com/api/v3/coins/"+whichcoin+"?tickers=false&market_data=false&community_data=false&developer_data=false&sparkline=false"
        rawimage = requests.get(tokenimageurl, headers=headers).json()
        tokenimage = Image.open(requests.get(rawimage['image']['large'], headers = headers, stream=True).raw).convert("RGBA")
        resize = 100,100
        tokenimage.thumbnail(resize, Image.ANTIALIAS)
        # If inverted is true, invert the token symbol before placing if on the white BG so that it is uninverted at the end - this will make things more
        # legible on a black display
        if config['display']['inverted'] == True:
            #PIL doesnt like to invert binary images, so convert to RGB, invert and then convert back to RGBA
            tokenimage = ImageOps.invert( tokenimage.convert('RGB') )
            tokenimage = tokenimage.convert('RGBA')
        new_image = Image.new("RGBA", (120,120), "WHITE") # Create a white rgba background with a 10 pixel border
        new_image.paste(tokenimage, (10, 10), tokenimage)
        tokenimage=new_image
        tokenimage.thumbnail((100,100),Image.ANTIALIAS)
        tokenimage.save(tokenfilename)
    pricechangeraw = round((pricestack[-1]-pricestack[0])/pricestack[-1]*100,2)
    if pricechangeraw >= 10:
        pricechange = str("%+d" % pricechangeraw)+"%"
    else:
        pricechange = str("%+.2f" % pricechangeraw)+"%"
    d = decimal.Decimal(str(pricenow)).as_tuple().exponent
    if pricenow > 1000:
        pricenowstring =str(format(int(pricenow),","))
    elif pricenow < 1000 and d == -1:
        pricenowstring ="{:.2f}".format(pricenow)
    else:
        pricenowstring ="{:.5g}".format(pricenow)
    if '24h' in config['display'] and config['display']['24h']:
        timestamp= str(time.strftime("%-H:%M, %d %b %Y"))
    else:
        timestamp= str(time.strftime("%-I:%M %p, %d %b %Y"))
    if config['display']['orientation'] == 0 or config['display']['orientation'] == 180 :
        image = Image.new('L', (176,264), 255)    # 255: clear the image with white
        draw = ImageDraw.Draw(image)
        draw.text((110,80),str(days_ago)+"day :",font =font_date,fill = 0)
        draw.text((110,95),pricechange,font =font_date,fill = 0)
        writewrappedlines(image, symbolstring+pricenowstring,40,65,8,10,"Roboto-Medium" )
        draw.text((10,10),timestamp,font =font_date,fill = 0)
        image.paste(tokenimage, (10,25))
        image.paste(sparkbitmap,(10,125))
        if config['display']['orientation'] == 180 :
            image=image.rotate(180, expand=True)
    if config['display']['orientation'] == 90 or config['display']['orientation'] == 270 :
        image = Image.new('L', (264,176), 255)    # 255: clear the image with white
        draw = ImageDraw.Draw(image)
        if other['ATH']==True:
            image.paste(ATHbitmap,(205,85))
        draw.text((110,90),str(days_ago)+" day : "+pricechange,font =font_date,fill = 0)
        if 'showvolume' in config['display'] and config['display']['showvolume']:
            draw.text((110,105),"24h vol : " + human_format(other['volume']),font =font_date,fill = 0)

        writewrappedlines(image, symbolstring+pricenowstring,50,55,8,10,"Roboto-Medium" )
        image.paste(sparkbitmap,(80,40))
        image.paste(tokenimage, (0,10))
        # Don't show rank for #1 coin, #1 doesn't need to show off
        if 'showrank' in config['display'] and config['display']['showrank'] and other['market_cap_rank'] > 1:
            draw.text((10,105),"Rank: " + str("%d" % other['market_cap_rank']),font =font_date,fill = 0)
        if (config['display']['trendingmode']==True) and not (str(whichcoin) in originalcoin_list):
            draw.text((95,28),whichcoin,font =font_date,fill = 0)
#       draw.text((5,110),"In retrospect, it was inevitable",font =font_date,fill = 0)
        draw.text((95,15),timestamp,font =font_date,fill = 0)
        if config['display']['orientation'] == 270 :
            image=image.rotate(180, expand=True)
#       This is a hack to deal with the mirroring that goes on in older waveshare libraries Uncomment line below if needed
#       image = ImageOps.mirror(image)
#   If the display is inverted, invert the image usinng ImageOps
    if config['display']['inverted'] == True:
        image = ImageOps.invert(image)
#   Return the ticker image
    return image

def currencystringtolist(currstring):
    # Takes the string for currencies in the config.yaml file and turns it into a list
    curr_list = currstring.split(",")
    curr_list = [x.strip(' ') for x in curr_list]
    return curr_list

def currencycycle(curr_string):
    curr_list=currencystringtolist(curr_string)
    # Rotate the array of currencies from config.... [a b c] becomes [b c a]
    curr_list = curr_list[1:]+curr_list[:1]
    return curr_list

def display_image(img):
    epd = epd2in7.EPD()
    epd.Init_4Gray()
    epd.display_4Gray(epd.getbuffer_4Gray(img))
    epd.sleep()
    thekeys=initkeys()
#   Have to remove and add key events to make them work again
    removekeyevent(thekeys)
    addkeyevent(thekeys)
    return

def initkeys():
    key1 = 5
    key2 = 6
    key3 = 13
    key4 = 19
    logging.debug('Setup GPIO keys')
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(key1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(key2, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(key3, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(key4, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    thekeys=[key1,key2,key3,key4]
    return thekeys

def addkeyevent(thekeys):
#   Add keypress events
    logging.debug('Add key events')
    btime = 300
    GPIO.add_event_detect(thekeys[0], GPIO.FALLING, callback=keypress, bouncetime=btime)
    GPIO.add_event_detect(thekeys[1], GPIO.FALLING, callback=keypress, bouncetime=btime)
    GPIO.add_event_detect(thekeys[2], GPIO.FALLING, callback=keypress, bouncetime=btime)
    GPIO.add_event_detect(thekeys[3], GPIO.FALLING, callback=keypress, bouncetime=btime)
    return

def removekeyevent(thekeys):
#   Remove keypress events
    logging.debug('Remove key events')
    GPIO.remove_event_detect(thekeys[0])
    GPIO.remove_event_detect(thekeys[1])
    GPIO.remove_event_detect(thekeys[2])
    GPIO.remove_event_detect(thekeys[3])
    return

def keypress(channel):
    global button_pressed
    with open(configfile) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    lastcoinfetch = time.time()
    if channel == 5 and button_pressed == 0:
        logging.info('Cycle currencies')
        button_pressed = 1
        crypto_list = currencycycle(config['ticker']['currency'])
        config['ticker']['currency']=",".join(crypto_list)
        lastcoinfetch=fullupdate(config, lastcoinfetch)
        configwrite(config)
        return
    elif channel == 6 and button_pressed == 0:
        logging.info('Rotate - 90')
        button_pressed = 1
        config['display']['orientation'] = (config['display']['orientation']+90) % 360
        lastcoinfetch=fullupdate(config,lastcoinfetch)
        configwrite(config)
        return
    elif channel == 13 and button_pressed == 0:
        logging.info('Invert Display')
        button_pressed = 1
        config['display']['inverted'] = not config['display']['inverted']
        lastcoinfetch=fullupdate(config,lastcoinfetch)
        configwrite(config)
        return
    elif channel == 19 and button_pressed == 0:
        logging.info('Cycle fiat')
        button_pressed = 1
        fiat_list = currencycycle(config['ticker']['fiatcurrency'])
        config['ticker']['fiatcurrency']=",".join(fiat_list)
        lastcoinfetch=fullupdate(config,lastcoinfetch)
        configwrite(config)
        return
    return

def configwrite(config):
    """
        Write the config file following an adjustment made using the buttons
        This is so that the unit returns to its last state after it has been
        powered off
    """
    with open(configfile, 'w') as f:
        data = yaml.dump(config, f)
#   Reset button pressed state after config is written
    global button_pressed
    button_pressed = 0

def fullupdate(config,lastcoinfetch):
    """
    The steps required for a full update of the display
    Earlier versions of the code didn't grab new data for some operations
    but the e-Paper is too slow to bother the coingecko API
    """
    other={}
    try:
        pricestack, ATH = getData(config, other)
        # generate sparkline
        makeSpark(pricestack)
        # update display
        image=updateDisplay(config, pricestack, other)
        display_image(image)
        lastgrab=time.time()
        time.sleep(0.2)
    except Exception as e:
        message="Data pull/print problem"
        image=beanaproblem(str(e)+" Line: "+str(e.__traceback__.tb_lineno))
        display_image(image)
        time.sleep(20)
        lastgrab=lastcoinfetch
    return lastgrab

def configtocoinandfiat(config):
    crypto_list = currencystringtolist(config['ticker']['currency'])
    fiat_list=currencystringtolist(config['ticker']['fiatcurrency'])
    currency=crypto_list[0]
    fiat=fiat_list[0]
    return currency, fiat

def gettrending(config):
    print("ADD TRENDING")
    coinlist=config['ticker']['currency']
    url="https://api.coingecko.com/api/v3/search/trending"
#   Cycle must be true if trending mode is on
    config['display']['cycle']=True
    trendingcoins = requests.get(url, headers=headers).json()
    for i in range(0,(len(trendingcoins['coins']))):
        print(trendingcoins['coins'][i]['item']['id'])
        coinlist+=","+str(trendingcoins['coins'][i]['item']['id'])
    config['ticker']['currency']=coinlist
    return config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default='info', help='Set the log level (default: info)')
    args = parser.parse_args()

    loglevel = getattr(logging, args.log.upper(), logging.WARN)
    logging.basicConfig(level=loglevel)
    # Set timezone based on ip address
    try:
        os.system("sudo /home/pi/.local/bin/tzupdate")
    except:
        logging.info("Timezone Not Set")
    try:
        logging.info("epd2in7 BTC Frame")
#       Get the configuration from config.yaml
        with open(configfile) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        logging.info(config)
        config['display']['orientation']=int(config['display']['orientation'])
        staticcoins=config['ticker']['currency']
#       Get the buttons for 2.7in EPD set up
        thekeys=initkeys()
#       Add key events
        addkeyevent(thekeys)
#       Note how many coins in original config file
        howmanycoins=len(config['ticker']['currency'].split(","))
#       Note that there has been no data pull yet
        datapulled=False
#       Time of start
        lastcoinfetch = time.time()
#       Quick Sanity check on update frequency, waveshare says no faster than 180 seconds, but we'll make 60 the lower limit
        if float(config['ticker']['updatefrequency'])<60:
            logging.info("Throttling update frequency to 60 seconds")
            updatefrequency=60.0
        else:
            updatefrequency=float(config['ticker']['updatefrequency'])
        while internet() ==False:
            logging.info("Waiting for internet")
        while True:
            while True:

                # Get Weather data from OWM
                obs = owm.weather_at_id(city_id)
                location = obs.get_location().get_name()
                weather = obs.get_weather()
                reftime = weather.get_reference_time()
                description = weather.get_detailed_status()
                temperature = weather.get_temperature(unit='celsius')
                humidity = weather.get_humidity()
                pressure = weather.get_pressure()
                clouds = weather.get_clouds()
                wind = weather.get_wind()
                rain = weather.get_rain()
                sunrise = weather.get_sunrise_time()
                sunset = weather.get_sunset_time()

                print("location: " + location)
                print("weather: " + str(weather))
                print("description: " + description)
                print("temperature: " + str(temperature))
                print("humidity: " + str(humidity))
                print("pressure: " + str(pressure))
                print("clouds: " + str(clouds))
                print("wind: " + str(wind))
                print("rain: " + str(rain))
                print("sunrise: " + time.strftime('%H:%M', time.localtime(sunrise)))
                print("sunset: " + time.strftime('%H:%M', time.localtime(sunset)))

                # Display Weather Information on e-Paper Display
                try:
                    print("Clear...")
                    epd.init()
                    epd.Clear()

                    # Drawing on the Horizontal image
                    HBlackimage = Image.new('1', (epd2in7b.EPD_HEIGHT, epd2in7b.EPD_WIDTH), 255)  # 298*126
                    HRedimage = Image.new('1', (epd2in7b.EPD_HEIGHT, epd2in7b.EPD_WIDTH), 255)  # 298*126

                    print("Drawing")
                    drawblack = ImageDraw.Draw(HBlackimage)
                    drawred = ImageDraw.Draw(HRedimage)
                    font24 = ImageFont.truetype('fonts/arial.ttf', 24)
                    font16 = ImageFont.truetype('fonts/arial.ttf', 16)
                    font20 = ImageFont.truetype('fonts/arial.ttf', 20)
                    fontweather = ImageFont.truetype('fonts/meteocons-webfont.ttf', 30)
                    fontweatherbig = ImageFont.truetype('fonts/meteocons-webfont.ttf', 60)

                    w1, h1 = font24.getsize(location)
                    w2, h2 = font20.getsize(description)
                    w3, h3 = fontweatherbig.getsize(weather_icon_dict[weather.get_weather_code()])

                    drawblack.text((10, 0), location, font=font24, fill=0)
                    drawblack.text((10 + (w1 / 2 - w2 / 2), 25), description, font=font20, fill=0)
                    drawred.text((264 - w3 - 10, 0), weather_icon_dict[weather.get_weather_code()], font=fontweatherbig,
                                 fill=0)
                    drawblack.text((10, 45), "Observed at: " + time.strftime('%I:%M %p', time.localtime(reftime)),
                                   font=font16, fill=0)

                    tempstr = str("{0}{1}C".format(int(round(temperature['temp'])), u'\u00b0'))
                    print(tempstr)
                    w4, h4 = font24.getsize(tempstr)
                    drawblack.text((10, 70), tempstr, font=font24, fill=0)
                    drawred.text((10 + w4, 70), "'", font=fontweather, fill=0)
                    drawblack.text((150, 70),
                                   str("{0}{1} | {2}{3}".format(int(round(temperature['temp_min'])), u'\u00b0',
                                                                int(round(temperature['temp_max'])), u'\u00b0')),
                                   font=font24, fill=0)

                    drawblack.text((10, 100), str("{} hPA".format(int(round(pressure['press'])))), font=font20, fill=0)
                    drawblack.text((150, 100), str("{}% RH".format(int(round(humidity)))), font=font20, fill=0)

                    drawred.text((20, 120), "A", font=fontweather, fill=0)
                    drawred.text((160, 120), "J", font=fontweather, fill=0)
                    drawblack.text((10, 150), time.strftime('%I:%M %p', time.localtime(sunrise)), font=font20, fill=0)
                    drawblack.text((150, 150), time.strftime('%I:%M %p', time.localtime(sunset)), font=font20, fill=0)

                    epd.display(epd.getbuffer(HBlackimage), epd.getbuffer(HRedimage))
                    time.sleep(2)

                    epd.sleep()

                except IOError as e:
                    print ('traceback.format_exc():\n%s', traceback.format_exc())
                    epdconfig.module_init()
                    epdconfig.module_exit()
                    exit()

                # Sleep for 10 minutes - loop will continue after 10 minutes
                time.sleep(100)  # Wake up every 10 minutes to update weather display


            if config['display']['trendingmode']==True:
                # The hard-coded 7 is for the number of trending coins to show. Consider revising
                if (time.time() - lastcoinfetch > (7+howmanycoins)*updatefrequency) or (datapulled==False):
                    # Reset coin list to static (non trending coins from config file)
                    config['ticker']['currency']=staticcoins
                    config=gettrending(config)
            if (time.time() - lastcoinfetch > updatefrequency) or (datapulled==False):
                if config['display']['cycle']==True and (datapulled==True):
                    crypto_list = currencycycle(config['ticker']['currency'])
                    config['ticker']['currency']=",".join(crypto_list)
                    # configwrite(config)
                lastcoinfetch=fullupdate(config,lastcoinfetch)
                datapulled = True
#           Reduces CPU load during that while loop
            time.sleep(0.01)
    except IOError as e:
        logging.error(e)
        image=beanaproblem(str(e)+" Line: "+str(e.__traceback__.tb_lineno))
        display_image(image)
    except Exception as e:
        logging.error(e)
        image=beanaproblem(str(e)+" Line: "+str(e.__traceback__.tb_lineno))
        display_image(image)  
    except KeyboardInterrupt:    
        logging.info("ctrl + c:")
        image=beanaproblem("Keyboard Interrupt")
        display_image(image)
        epd2in7.epdconfig.module_exit()
        GPIO.cleanup()
        exit()

if __name__ == '__main__':
    main()
