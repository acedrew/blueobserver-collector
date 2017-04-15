from bluetooth.ble import DiscoveryService
import bluetooth
import time
import argon2
import requests
import base64
import os
import multiprocessing

salt = os.environ['BLUE_COLLECTOR_HASH_SALT']
location = os.environ['BLUE_COLLECTOR_LOCATION_NAME']
if 'BLUE_COLLECTOR_GEO_POINT' in os.environ:
    geo_point = [ float(a) for a in os.environ[
        'BLUE_COLLECTOR_GEO_POINT'].split(',') ]


class DeviceScanner(multiprocessing.Process):

    def __init__(self, observation_queue):
        multiprocessing.Process.__init__(self)
        self.observation_queue = observation_queue
        self.timeout = 5

    def run(self):
        while True:
            devices = self.scan()
            self.process_devices(devices)

    def set_timeout(self, timeout):
        self.timeout = timeout


    def process_devices(self, devices):
        now = time.time()
        for device in devices:
            self.observation_queue.put((device, now))

class BTScanner(DeviceScanner):

    def __init__(self, observation_queue):
        DeviceScanner.__init__(self, observation_queue)

    def scan(self):
        return {i[0]: i[1] for i in bluetooth.discover_devices(
            duration=self.timeout, lookup_names=True, flush_cache=True,
            lookup_class=False)}


class BLEScanner(DeviceScanner):

    def __init__(self, observation_queue):
        DeviceScanner.__init__(self, observation_queue)
        self.service = DiscoveryService()

    def scan(self):
        return self.service.discover(self.timeout)

class DevicePublisher(multiprocessing.Process):

    def __init__(self, observation_queue):
        multiprocessing.Process.__init__(self)
        self.observations = observation_queue
        self.seen_devices = {}
        self.cleanup_counter = 0

    def run(self):
        while True:
            observation = self.observations.get()
            self.process_observation(observation)
            print(observation)

    def process_observation(self, observation):
        (mac, obs_time) = observation
        if mac in self.seen_devices:
            if self.seen_devices[mac] + 300 < obs_time:
                self.publish_observation(mac, obs_time)
            else:
                self.seen_devices[mac] = obs_time
        else:
            self.seen_devices[mac] = obs_time
            self.publish_observation(mac, obs_time)

    def cleanup_devices(self):
        now = time.time()
        remove_devices = []
        for mac, seen_time in self.seen_devices.items():
            if now - 600 > seen_time:
                remove_devices.append(mac)
        for mac in remove_devices:
            del self.seen_devices[mac]

    def publish_observation(self, mac, obs_time):
        observation = {}
        observation['hash'] = base64.urlsafe_b64encode(
            argon2.argon2_hash(mac, salt)).decode()
        observation['location'] = location
        observation['geo_point'] = geo_point
        observation['timestamp'] = obs_time
        try:
            r = requests.post("http://localhost:5000/observations", json=observation)
        except Exception as e:
            print('publish failed for observation: ' + observation['hash'] + 'with exception: ' + str(e))
            pass


def main():
    print(geo_point)
    observations = multiprocessing.Queue()
    ble_scanner = BLEScanner(observations)
    bt_scanner = BTScanner(observations)
    publisher = DevicePublisher(observations)
    ble_scanner.start()
    bt_scanner.start()
    publisher.start()

if __name__ == "__main__":
    main()
