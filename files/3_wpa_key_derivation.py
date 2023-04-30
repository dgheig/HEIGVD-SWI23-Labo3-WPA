#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

"""

__author__      = "Abraham Rubinstein et Yann Lederrey"
__copyright__   = "Copyright 2017, HEIG-VD"
__license__ 	= "GPL"
__version__ 	= "1.0"
__email__ 		= "abraham.rubinstein@heig-vd.ch"
__status__ 		= "Prototype"

from scapy.all import *
from binascii import a2b_hex, b2a_hex
#from pbkdf2 import pbkdf2_hex
from pbkdf2 import *
from numpy import array_split
from numpy import array
import hmac, hashlib
import argparse
import binascii

parser = argparse.ArgumentParser(description='Process .pcap file and wordlist file')
parser.add_argument('-c', '--pcap', type=str, required=True,help='path to .pcap file')
parser.add_argument('-w', '--wordlist', type=str, required=True,help='path to wordlist file')

args = parser.parse_args()

pcap = args.pcap
wordlist = args.wordlist


# Custom class to store the SSID and MAC address of an AP   
class AP(NamedTuple):
    ssid: str
    mac_address: str

# Function used to get APs from a pcap capture
def find_ssid(pcap):
    # Initialize and empty dictionary to contain APs
    ssids = {}
    # Iterate over all packets in capture
    for packet in pcap:
        # If the packet is a 802.11 beacon
        if packet.haslayer(Dot11Beacon):
            # Retrieve the SSID
            ssid = packet[Dot11Elt].info.decode()
            # Add AP to dict if not seen before
            if ssid not in ssids:
                ssids[ssid] = packet.addr2
    # If there is only one AP found, return its SSID and MAC in an AP object
    if len(ssids) == 1:
        ssid, mac = next(iter(ssids.items()))
        return AP(ssid=ssid, mac_address=mac)
    # If there are multiple, ask user to choose and return the chosen one
    elif len(ssids) > 1:
        ssid_infos = []
        for ssid, mac in ssids.items():
            ssid_infos.append(AP(ssid=ssid, mac_address=mac))
        print("Multiple SSIDs found:")
        for i, ssid_info in enumerate(ssid_infos):
            print(f"{i}: SSID: {ssid_info.ssid} | MAC Address: {ssid_info.mac_address}")
        chosen_ssid_index = input("Please choose an SSID by typing its index: ")
        while not chosen_ssid_index.isdigit() or int(chosen_ssid_index) not in range(len(ssids)):
            chosen_ssid_index = input("Invalid choice. Please choose an SSID by typing its index: ")
        chosen_ssid = ssid_infos[int(chosen_ssid_index)].ssid
        mac = ssids[chosen_ssid]
        return AP(ssid=chosen_ssid, mac_address=mac)
    else:
        print("No AP found in capture, exiting...")
        exit()

# Function used to get wifi clients from a wireshark capture
def get_wifi_clients(pcap):
    # Initialize and empty dictionnary to contain clients
    clients = {}
    # Iterate over all the packets
    for packet in pcap:
        # If packet is a 802.11 packet
        if packet.haslayer(Dot11):
            # add client to dict if not seen before
            if packet.addr2 not in clients:
                clients[packet.addr2] = 0
            # check if packet is a beacon
            if packet.haslayer(Dot11Beacon):
                # increment beacon count for this client
                clients[packet.addr2] += 1
    # filter out clients that have emitted a beacon
    clients = {k:v for k,v in clients.items() if v == 0}
    # Get the number of 
    num_clients = len(clients)
    # If there is exactly one client, return it's MAC address
    if num_clients == 1:
        return list(clients.keys())[0]
    # If there is more than one client, ask user which to select
    elif num_clients > 1:
        print("Found multiple WiFi clients:")
        for i, client in enumerate(clients.keys()):
            print(f"{i+1}. {client}")
        choice = input("Enter the number of the client to choose: ")
        return list(clients.keys())[int(choice)-1]
    else:
        print("No WiFi clients found, exiting...")
        exit()

# Function used to retrive the PMKID from the 1st packet of a WPA 4-way handshake
def get_wpa_pmkid(pcap, client_mac, ap_mac):
    for packet in pcap:
        # check if the packet is the fourth packet of a 4-way handshake from the client to the AP
        if (packet.haslayer(EAPOL) 
        and packet[EAPOL].type == 3 
        and packet.addr1.lower() == client_mac
        and packet.addr2.lower() == ap_mac):
            # Extract the PMKID value from the packet
            pmkid = packet[EAPOL].load[-16:].hex()
            return pmkid
    # if no WPA MIC is found, return None
    print("PMKID not found")
    exit()

def make_pmkid(ap_mac, client_mac, ssid, passphrase):
    # derive pmk from passphrase and ssid
    # https://cylab.be/blog/32/how-does-wpawpa2-wifi-security-work-and-how-to-crack-it

    pmk = hashlib.pbkdf2_hmac('sha1', passphrase.encode(), ssid.encode(), 4096)

    print('PMK:', pmk.hex())

    ap_mac_bytes = bytes(bytes.fromhex(ap_mac.replace(':','')))
    client_mac_bytes = bytes(bytes.fromhex(client_mac.replace(':','')))
    pmk_name_bytes = bytes("PMK Name".encode())


    data = pmk_name_bytes + ap_mac_bytes + client_mac_bytes
    
    #data = "PMK Name".encode() + ap_mac.replace(':', '').encode()  + client_mac.replace(':', '').upper().encode()
    print(f'DAta: ', data.hex())
    pmkid = hashlib.pbkdf2_hmac('sha1', pmk, data, 1)[:16]
    print(f'pmkid : ', pmkid.hex())




if pcap == "":
    wpa=rdpcap("PMKID_handshake.pcap") 
else:
    wpa=rdpcap(pcap)

# Important parameters for key derivation - most of them can be obtained from the pcap file
passPhrase  = "actuelle"
A           = "Pairwise key expansion" #this string is used in the pseudo-random function
# Construct an AP object from the capture
AP          = find_ssid(wpa)
# Get the client mac address
cl_mac      = get_wifi_clients(wpa)
# Get the ssid from the AP object
ssid        = AP.ssid
ap_mac      = AP.mac_address



pmkid_to_check = get_wpa_pmkid(wpa, cl_mac, AP.mac_address)
print(f'PMKID from cap : {pmkid_to_check}')

pmkid_attempt = make_pmkid(ap_mac, cl_mac, ssid, "admin123")
print(f'PMKID built : {pmkid_attempt}')