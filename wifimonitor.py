'''
In order to properly run, ensure that |iface| is in monitor mode.
Furthermore, run this Python script as sudo.

Dependencies: Scapy, SQLite, SQLAlchemy.
'''

import sys, os, signal, datetime
from scapy.all import *
from multiprocessing import Process
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Packet, createNewDatabase


# Database setup.
# TODO: Make this mutable.
TimeFileStamp=datetime.datetime.now()
date_str = TimeFileStamp.strftime("%Y-%m-%d_%H-%M-%S")
name=str("sniff-"+date_str+".db")
#
#def create():
#    try:
#        file=open(name, 'a')   # Trying to create a new file or open one
#        file.close()
#    except:
#        print('Something went wrong! Can\'t tell what?')
#        sys.exit(0) # quit Python
#create()
#name2=str("sqlite:///"+name)
#print(name2)
##createNewDatabase(name)
#engine = create_engine(name2)
engine = create_engine('sqlite:///%s.db' % name, convert_unicode=True)
Base.metadata.create_all(engine)
engine.raw_connection().connection.text_factory = str
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

PROBE_REQUEST_TYPE = 0
PROBE_REQUEST_SUBTYPE = 4

# Set non-statically in the future.
iface = 'wlan0'
channel = 1
os.system('sudo ifconfig wlan0 down ')
os.system('sudo iwconfig wlan0 mode monitor ')
os.system('sudo ifconfig wlan0 up ')

seen_mac_addresses = set()
seen_SSIDs = set()

def PacketHandler(pkt):
	if pkt.haslayer(Dot11):
		if pkt.type == PROBE_REQUEST_TYPE and pkt.subtype == PROBE_REQUEST_SUBTYPE and pkt.getlayer(Dot11ProbeReq).info != "":
			seen_mac_addresses.add(pkt.addr2)
			seen_SSIDs.add(pkt.getlayer(Dot11ProbeReq).info)
			print "MAC address: %s, SSID: %s, Signal Strength(-100 to 0): %d" % (pkt.addr2, pkt.getlayer(Dot11ProbeReq).info, -(256-ord(pkt.notdecoded[-4:-3])))

def AllPacketHandler():
	data = {'last_mac': None}
	def packetHandler(pkt):
		if pkt.haslayer(Dot11) and pkt.addr2 != data['last_mac'] and pkt.addr2 not in seen_mac_addresses:
				data['last_mac'] = pkt.addr2
				seen_mac_addresses.add(pkt.addr2)
				print -(256-ord(pkt.notdecoded[-4:-3]))
				print "MAC address detected: %s" % (pkt.addr2)
	return packetHandler

def PrintPackets(pkt):
	if pkt.type == PROBE_REQUEST_TYPE and pkt.subtype == PROBE_REQUEST_SUBTYPE:
		mac_address = pkt.addr2
		signal = -(256-ord(pkt.notdecoded[-4:-3]))
		ssid = pkt.getlayer(Dot11ProbeReq).info
		new_packet = Packet(mac=mac_address,ssid=ssid,signal=signal,time=datetime.datetime.now())
		session.add(new_packet)
		session.commit()
		print "MAC address: %s, SSID: %s, Signal Strength(-100 to 0): %d" % (mac_address, ssid, signal)

'''
Channel hopper.
'''
def hop_channels():
	channel = 0
	while True:
		try:
			channel = (channel % 11 + 1)
			os.system('iw dev %s set channel %d' % (iface, channel))
			print 'setting channel to %d' % (channel)
			time.sleep(5)
		except Exception as e:
			print "Channel hopping ceased."
			print e
			break

def signal_handler(signal, frame):
	p.terminate()
	p.join()
	print "Terminating monitoring."
	print "Now displaying detected IP addresses..."
	for address in seen_mac_addresses:
		print address

	print "Now printing observed SSID probe requests"
	for ssid in seen_SSIDs:
		print ssid

	print "-- %d MAC addresses detected --" % len(seen_mac_addresses)
	print "-- %d SSIDs addresses detected --" % len(seen_SSIDs)
	sys.exit(0)


def set_iface_to_monitor_mode(interface):
	'''
	try:
		# TODO(dhnishi): Make this fail if an ifconfig or iwconfig fails.
		err = os.system('ifconfig %s down' % interface)
		err = err + os.system('iwconfig %s mode monitor' % interface)
		err = err + os.system('ifconfig %s up' % interface)
		return (err == 0)
	except Exception as e:
		print e
		return False
	'''
	return True

if __name__ == '__main__':
	# TODO: Don't hardcore the interface.
	print "Starting interface into monitor mode..."
	if not set_iface_to_monitor_mode(iface):
		print "Error starting %s into monitor mode" % iface
		sys.exit(1)

	print "Beginning packet capture..."
	p = Process(target = hop_channels)
	p.start()
	signal.signal(signal.SIGINT, signal_handler)
	sniff(iface=iface, prn = PrintPackets, store=0)
