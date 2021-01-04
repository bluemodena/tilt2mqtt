#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#Modified: 2020/10/05 20:33:45
import blescan
import logging
import logging.handlers
import configparser
import sys
import os
import json
import argparse
import datetime
import time
import uuid
import bluetooth._bluetooth as bluez
sys.path.append("/usr/local/python")
from daemon import daemon
conf = configparser.ConfigParser()
conf.read('/usr/local/python/avzdk.ini')
scriptname=os.path.basename(__file__)

import paho.mqtt.client as mqtt
mqtt_client = mqtt.Client(scriptname)


LOG_FILENAME = '/var/log/python/'+scriptname+'.log'
LOG_LEVEL = logging.INFO  # Could be e.g. "DEBUG" or "WARNING"
INTERVAL = 15*60 #15 minuter

DAEMON_PIDFILE = '/tmp/'+scriptname+'.pid'
parser = argparse.ArgumentParser(description="Tilt2")
parser.add_argument("action",help="Action to perform start/stop/restart/run")
parser.add_argument("-ll", "--loglevel", help="loglevel (default "+ str(LOG_LEVEL) + ")" )
parser.add_argument("-i", "--interval", help="interval(default "+ str(INTERVAL) + ")" )
args = parser.parse_args()
if args.loglevel: LOG_LEVEL = args.loglevel
if args.action:	ACTION = args.action
if args.interval:	INTERVAL = int(args.interval)

logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)
handler = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME, when="midnight", backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s'))
logger.addHandler(handler)

class MyLogger(object):
		def __init__(self, logger, level):
				self.logger = logger
				self.level = level

		def write(self, message):
				# Only log if there is a message (not just a new line)
				if message.rstrip() != "":
						self.logger.log(self.level, message.rstrip())
		def flush(self):
			pass

if ACTION == "run": # Hvis det koeres som service sendes stdout ot stderr til logfil.
	
	logger.addHandler(logging.StreamHandler(sys.stdout))
else:  # ellers sendes log til stdout
	sys.stdout = MyLogger(logger, logging.INFO)
	sys.stderr = MyLogger(logger, logging.ERROR)
	
# >>>LOGGING STOP



class lineCalibration():

    def __init__(self,p1,p2):
        self.p1=p1
        self.p2=p2
        self.x1, self.y1 = p1
        self.x2, self.y2 = p2
    
    @property
    def a(self):
        return(self.y2-self.y1)/(self.x2-self.x1)
    
    @property
    def b(self):
        return self.y1 - self.a*self.x1

    def y(self,x):
        return (self.b+self.a*x)


class TiltMonitor():

	TILTS = {
		'a495bb10c5b14b44b5121370f02d74de': 'red',
		'a495bb20c5b14b44b5121370f02d74de': 'green',
		'a495bb30c5b14b44b5121370f02d74de': 'black',
		'a495bb40c5b14b44b5121370f02d74de': 'purple',
		'a495bb50c5b14b44b5121370f02d74de': 'orange',
		'a495bb60c5b14b44b5121370f02d74de': 'blue',
		'a495bb70c5b14b44b5121370f02d74de': 'yellow',
		'a495bb80c5b14b44b5121370f02d74de': 'pink',
	}

	
	def __init__(self,pause,callback):
		self.pause = pause
		self.callback=callback
		logger.info(f"Retrieving data every {pause} seconds")

	def distinct(self,objects):
		seen = set()
		unique = []
		for obj in objects:
			if obj['uuid'] not in seen:
				unique.append(obj)
				seen.add(obj['uuid'])
		return unique

	def to_celsius(self,fahrenheit):
		return round((fahrenheit - 32.0) / 1.8, 2)

	def calibrate_SG(self,sg):
		#1001 -> 999 målt 1001 er 999 (ved 16 grader)
		#1010 -> 1010 målt med alc 1010 er 1010
		#1072 -> 1074 er målt refractometer 1074 
		lc=lineCalibration((1001,999),(1072,1074))
		return lc.y(sg)

	def calibrate_Tc(self,t):
			#Kalibrering af celcius
			#målt 18.33 er 18.0
			#målt 21.67 er 21.5
			#målt 16.1 er 16.0
		return t-0.3	

	def run(self):		
		self.dev_id = 0

		try:
			self.sock = bluez.hci_open_dev(self.dev_id)
		
		except:
			logger.error('error accessing bluetooth device...')
			sys.exit(1)
		blescan.hci_le_set_scan_parameters(self.sock)
		blescan.hci_enable_le_scan(self.sock)

		while True:
				
				logger.debug("check tilts for data")
				
				a=blescan.parse_events(self.sock, 100)
				
				beacons = self.distinct(a)
				
				for beacon in beacons:
					
					if beacon['uuid'] in self.TILTS.keys():
						data ={
							'tilt': self.TILTS[beacon['uuid']],
							'time': str(datetime.datetime.now()),
							'temperature': self.to_celsius(beacon['major']),
							'temperature_cal': self.calibrate_Tc( self.to_celsius(beacon['major'])),
							'sg': beacon['minor'],
							'sg_cal': self.calibrate_SG(beacon['minor']),
							'measurementID' : str(uuid.uuid4())
						}
						logger.debug(data)
		
						self.callback(data)
				
				time.sleep(self.pause)
		

def tiltCallback(data):
	data['msg_uuid']=str(uuid.uuid4())
	data['time_send']=str(datetime.datetime.now())	
	mqtt_client.connect(conf['MQTT']['Ip'])		
	response=mqtt_client.publish(conf['MQTT']['tilt'],json.dumps(data))
	logger.debug(f"Succes: {response.rc}" )
	mqtt_client.disconnect()



class MyDaemon(daemon):

	def run(self):
		t = TiltMonitor(INTERVAL,tiltCallback)
		t.run()
		

daemon = MyDaemon(DAEMON_PIDFILE)

if 'start' == ACTION :
	logger.info("Daemon - Starting service --------------------------")
	daemon.start()
	
elif 'stop' == ACTION :
	logger.info("Daemon - Stopping service --------------------------")
	daemon.stop()
elif 'restart' == ACTION :
	logger.info("Daemon - Restarting service --------------------------")
	daemon.restart()
elif 'run' == ACTION :
	logger.info("Daemon - Running foreground")
	daemon.run()
elif 'status' == ACTION :
	daemon.is_running()
else:
	print("Ukendt kommando")
	sys.exit(2)
