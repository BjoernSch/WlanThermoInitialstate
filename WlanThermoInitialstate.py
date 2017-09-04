#!/usr/bin/python
import sys
import os
import urllib2
import json
import mmap, codecs
from ISStreamer.Streamer import Streamer

# --------- User Settings ---------
BUCKET_NAME = "xxxxxxxxxxxxxxxx"
BUCKET_KEY = "xxxxxxxxxxxxxxxx"
ACCESS_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# --------- local Path ---------
myfile='./WTdata.json'

# --------- local Tags ---------
force_data = False
sendCPU = True
sendPit = True

# ---------- depencies -----------------------
# run the following command to aktivate ISStreamer for Inital State:
# \curl -sSL https://get.initialstate.com/python -o - | sudo bash
# at console

# run cyclic as cron job
# crontab -e
# ad:
# * * * * * /usr/bin/python ./WlanThermoInitialstate.py
#                           ad your path here

# ---------- getting Data -----------------------
def read_loc_json():
	try: #pruefen der Datei und lesen des Inhaltes
		with open(myfile) as f:
			data= json.load(f)
	except IOError: # Wenn die Datei nicht vorhanden ist
		print('File not exists!') # Meldung ausgeben
		return[]	# leeres dict zurueckgeben
	f.close()
	return data

def write_loc_json(data):
	# schreiben der Datendatei
	with open(myfile, 'w') as f:
		json.dump(data, codecs.getwriter('utf-8')(f), ensure_ascii=False)
	f.close()

def delete_loc_json():
	## if file exists, delete it ##
	if os.path.isfile(myfile):
		os.remove(myfile)
	else:    ## Show an error ##
		print("Error: %s file not found" % myfile)

def get_values():
    api_conditions_url = "http://localhost/app.php"
    try:
		 f = urllib2.urlopen(api_conditions_url)
    except:
        print "Failed to get conditions"
        return []
    json_conditions = f.read()
    f.close()
    return json.loads(json_conditions)

def get_ext_config(cfgpath):
	import ConfigParser
	global myfile
	global sendCPU
	global sendPit
	cfg = ConfigParser.ConfigParser()
	cfg.read(cfgpath)
	myfile = cfg.get('Local','Temp_File')
	sendCPU = cfg.get('Options','sendCPU')
	sendPit = cfg.get('Options','sendPit')

def main():
	global sendCPU
	global sendPit

	# -------------- Kommandozeilen Parameter --------------
	for x in range(1, len(sys.argv)):
		print('Parameter ' + str(x) + ': ' +sys.argv[x])
		if sys.argv[x] == '/dT' or sys.argv[x] == '/fa' :
			delete_loc_json()
		elif sys.argv[x] == '/ft':
			force_data = True
		elif sys.argv[x] == '/nc':
			sendCPU = True
		elif sys.argv[x] == '/np':
			sendPit = True
		elif '/eC' == sys.argv[x][:3]:
			arg = sys.argv[x]
			cfgpath= arg.split('=')
			if os.path.isfile(cfgpath[1]):
				get_ext_config(cfgpath[1])
			else:
				print('Parameter /eC File %s not exists!' % cfgpath[1])
			print('Path: ' + myfile)
			print('CPU-Daten: ' + str(sendCPU))
			print('Pit-Daten: ' + str(sendPit))
			exit()
		else:
			print('Wrong Parameter %s in Commandline' % sys.argv[x])
			exit()

	# -------------- WlanThermo --------------
	#neue Daten lesen
	values = get_values()

	#alte Daten von file lesen
	values_old = read_loc_json()

	# pruefen auf inhalt
	force_new_data = ('temp_unit' not in values_old)

	# Manipulieren einzelner Werte
	values['cpu_load'] = round(values['cpu_load'],2)
	if values['temp_unit'] == 'celsius':
		values['temp_unit'] = "C"
	else:
		values['temp_unit'] = "F"

	print('force: ' + str(force_data))
	#erneute Pruefung der aktualdaten zur weiteren ausfuehrung
	if ('temp_unit' not in values):
		print "Error! Wlanthermo app.php reading failed!"
		exit()
	else:
		# init ISStreamer
		streamer = Streamer(bucket_name=BUCKET_NAME, bucket_key=BUCKET_KEY, access_key=ACCESS_KEY)

		# Variablen durcharbeiten
		for x in values:  #alle Basis Elemente durcharbeiten
			if ('pit' == str(x)[:3]): #pitmaster signale
				if sendPit:
					for y in values[x]:
						new_data = False
						if force_new_data:
							new_data = True
						elif force_data:
							if str(y) == 'setpoint':
								new_data = True
						else:
							new_data= not (values[x][y] == values_old[x][y])

						if 'timestamp' in y:
							new_data = False

						if new_data:
							#print(str(x) + '_' + str(y) + ': ' + str(values[x][y]))
							name = str(x) + '_' + str(y)
							value = values[x][y]
							streamer.log(name, value)

			elif (x == 'channel'):  #alle Temperatur Kanaele durcharbeiten
				for y in values[x]:
					for z in values[x][y]:
						new_data = False
						if force_new_data:
							new_data = True
						elif force_data:
							if (values[x][y]['state'] == 'ok'):
								if str(z)[:4] == 'temp':
									new_data = True
						else:
							new_data= not (values[x][y][z] == values_old[x][y][z])

						if new_data:
							#print(str(x)[:2] + str('0'+ y)[:2] + '_' + str(z) + ': ' + str(values[x][y][z]))
							name = str(x)[:2] + str('0'+ y)[:2] + '_' + str(z)
							value = values[x][y][z]
							streamer.log(name, value)
			elif ('cpu' == str(x)[:3]):
				if sendCPU:
					new_data = False
					if force_new_data:
						new_data = True
					else:
						new_data= not (values[x] == values_old[x])
					if new_data:
						#print(str(x) + ': ' + str(values[x]))
						name = str(x)
						value = values[x]
						streamer.log(name, value)

			else:  # alle anderen Signale
				new_data = False
				if force_new_data:
					new_data = True
				elif (x == 'timestamp'):
					new_data = False
				else:
					new_data= not (values[x] == values_old[x])

				if new_data:
						#print(str(x) + ': ' + str(values[x]))
						name = str(x)
						value = values[x]
						streamer.log(name, value)

	print('done')
	try:
		streamer.flush()
	except Exception:
		print('Daten senden nicht moeglich!')
		exit() # hier wird abgebrochen, damit der Zischenspeicher mit Initialstate synchron bleibt.

	# schreiben der lokalen Datei
	write_loc_json(values)


if __name__ == "__main__":
    main()
