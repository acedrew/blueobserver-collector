# blueobserver-collector
Collector that runs on a raspberry pi to sniff bluetooth MAC Addresses
See https://github.com/acedrew/blueobserver for the server side implementation. This collector will sniff Classic BT and BLE devices using the Raspberry Pi 3's built in BT stack

# Privacy
This project seeks to protect to some degree the privacy of the devices being sniffed by only transmitting argon2 hashed versions of the MAC, and on the server side only storing observation data relative to arbitrarily assigned UUIDs that expire after a set period of time.

# Requirements
I will try to compile the exact process of setting this up on a RPi running jessie-lite in the future. For now, see the system requirements in each of the packages in requirements.txt

The following packages need to be installed on a raspbian jessie-lite system:

    -   python3
    -   python3-virtualenv
    -   virtualenv
    -   libglib2.0-dev
    -   libpython3-dev
    -   libbluetooth-dev
    -   libboost-dev
    -   libboost-thread
    -   libboost-python-dev

Right now the collector expects to find an http server listening on localhost:5000, you can customize that to your specification. I've included a template autossh unit file for systemd if you want to tunnel a remote server to the collector.


# Setup
1. Clone this repo to /opt/projects/blueobserver-collector
2. cd to /opt/projects/blueobserver-collector
3. run 'virtualenv ./ python3'
4. copy blueobserver-collector.service to /etc/systemd/system/
5. edit blueobserver-collector.service with your environment data (see comments in file)
6. enable blueobserver-collector.service with 'systemctl enable blueobserver-collector.service'
7. start with 'systemctl start blueobserver-collector.service'
