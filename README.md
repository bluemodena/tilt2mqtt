# tilt2mqtt
Reads the Tilt bluetooth hydrometer and send values to MQTT

Reads all awailable tilt hydrometers and send data to MQTT.
Runs perfect on a Raspberry Pi Zero W.

MQTT output looks like:
{"tilt": "red", "time": "2021-12-19 09:00:58.072411", "temperature": "60", "gravity": 1.012, "measurementID": "<some uuid>", "msg_uuid": "<another uuid>", "time_send": "2021-12-19 09:00:58.073402"}

Get you tilt form https://tilthydrometer.com/ and keep and eye on your beer fermenting.

