pi@homelab-fermpi:~/tilt2mqtt $ cat tilt2mqtt.py 
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#Last Modified: 2021/01/30 10:08:58
import blescan
import logging
import logging.handlers
import configparser
import sys
import os
import json
import argparse
import datetime
import decimal
import time
import uuid
import bluetooth._bluetooth as bluez

conf = configparser.ConfigParser()
conf.read(['tilt2mqtt.ini','tilt2mqtt_local.ini'])

log = logging.getLogger(__name__)
logging.basicConfig(
    level=conf["LOG"]["LEVEL"],
    format="%(levelname)s %(module)s.%(funcName)s %(message)s",
)
log.info(f"Starting service loglevel={conf['LOG']['LEVEL']} ")



scriptname=os.path.basename(__file__)

import paho.mqtt.client as mqtt
mqtt_client = mqtt.Client(scriptname)

INTERVAL = int(conf["TILT"]["Interval"])
log.info(f"Checking every {INTERVAL} second")


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
		log.info(f"Retrieving data every {pause} seconds")

	def distinct(self,objects):
		seen = set()
		unique = []
		for obj in objects:
			#print (obj)
			obj_list = obj.split(",")
			#print (obj_list[1])
			if obj_list[1] not in seen:
				unique.append(obj)
				seen.add(obj_list[1])
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
			log.error('error accessing bluetooth device...')
			sys.exit(1)
		blescan.hci_le_set_scan_parameters(self.sock)
		blescan.hci_enable_le_scan(self.sock)

		while True:
				log.debug("check tilts for data")
				a=blescan.parse_events(self.sock, 100)
				beacons = self.distinct(a)
				for beacon in beacons:
					beacon_list = beacon.split(",")	
					if beacon_list[1] in self.TILTS.keys():
						print (beacon)
						data ={
							'tilt': self.TILTS[beacon_list[1]],
							'time': str(datetime.datetime.now()),
							'temperature': beacon_list[2],
							#'temperature': self.to_celsius(beacon_list[2]),
							#'temperature_cal': self.calibrate_Tc( self.to_celsius(beacon_list[2])),
							#'temperature_cal': beacon_list[2],
							'gravity': int(beacon_list[3])/1000,
							#'sg_cal': self.calibrate_SG(beacon_list[3]),
							#'sg_cal': beacon_list[3],
							'measurementID' : str(uuid.uuid4())
						}
						log.debug(data)		
						self.callback(data)
				time.sleep(self.pause)
		

def tiltCallback(data):
	data['msg_uuid']=str(uuid.uuid4())
	data['time_send']=str(datetime.datetime.now())	
	mqtt_client.username_pw_set(conf['MQTT']['username'],conf['MQTT']['password'])
	mqtt_client.connect(conf['MQTT']['ip'], int(conf['MQTT']['port']), 60)		
	mqtt_topic=conf['MQTT']['channel'] + "/" + data['tilt']
	response=mqtt_client.publish(mqtt_topic,json.dumps(data),1,True)
	log.debug(f"Success: {response.rc}" )
	mqtt_client.disconnect()
		
def main():
	t = TiltMonitor(INTERVAL,tiltCallback)
	t.run()

if __name__ == "__main__":
    main()

