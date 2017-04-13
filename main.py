from bluetooth.ble import DiscoveryService
import bluetooth
import time
import argon2
import requests
import base64
import os

service = DiscoveryService()
state = {"devices": {}}
salt = os.environ['BLUE_COLLECTOR_HASH_SALT']
location = os.environ['BLUE_COLLECTOR_LOCATION_NAME']


def publish_new_device(address, timestamp, location):
    observation = {}
    observation['hash'] = str(base64.urlsafe_b64encode(argon2.argon2_hash(address, salt)))
    observation['location'] = location
    observation['timestamp'] = timestamp
    try:
        r = requests.post("http://localhost:5000/observations", json=observation)
        print(r)
    except:
        print('connection failed')
        pass


def scan_ble(timeout=5):
    return service.discover(timeout)


def scan_bluez(timeout=5):
    return bluetooth.discover_devices(
        duration=timeout, lookup_names=True, flush_cache=True,
        lookup_class=False)


def get_all_devices():
    devices = scan_ble(5)
    devices.update({i[0]: i[1] for i in scan_bluez(5)})
    return devices


def process_devices(devices, timestamp):
    state['new_devices'] = {}
    state['removed_devices'] = {}
    for (address, name) in devices.items():
        if address not in state['devices']:
            state['new_devices'][address] = {"name": name, "ts": timestamp}
        state['devices'][address] = {"name": name, "ts": timestamp}


def main():
    while 1:
        devices = get_all_devices()
        timestamp = time.time()
        process_devices(devices, timestamp)

        for (address, data) in state['new_devices'].items():
            print("New Device: name: {}, address: {}".format(
                data['name'], address))
            publish_new_device(address, timestamp, location)
        for (address, data) in state['devices'].items():
            if data['ts'] < timestamp - 60:
                state['removed_devices'][address] = data
        for address in state['removed_devices']:
            del state['devices'][address]

        for (address, name) in state['removed_devices'].items():
            print("Device Removed: name: {}, address: {}".format(
                name, address))


if __name__ == "__main__":
    main()
