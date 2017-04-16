from bluetooth.ble import DiscoveryService
import bluetooth
import time
import argon2
import requests
import base64
import os
import multiprocessing
from wifi import Cell

salt = os.environ['BLUE_COLLECTOR_HASH_SALT']
location = os.environ['BLUE_COLLECTOR_LOCATION_NAME']
geo_point_str = os.environ.get('BLUE_COLLECTOR_GEO_POINT', "0.0,0.0")
geo_point = [float(a) for a in geo_point_str.split(',')]

geo_locator = os.environ.get('BLUE_COLLECTOR_GEO_SOURCE', None)
if geo_locator:
    geo_api_key = os.environ['BLUE_COLLECTOR_GEO_API_KEY']


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

    def __init__(self, observation_queue, location_queue):
        multiprocessing.Process.__init__(self)
        self.observations = observation_queue
        self.locations = location_queue
        self.seen_devices = {}
        self.cleanup_counter = 0
        self.geo_point = geo_point

    def run(self):
        while True:
            observation = self.observations.get()
            self.process_observation(observation)
            print(observation)
            try:
                location = self.locations.get(block=False)
                self.process_location(location)
            except:
                pass

    def process_location(self, location):
        self.geo_point = location

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
        self.cleanup_counter += 1
        if self.cleanup_counter > 100:
            self.cleanup_devices()

    def cleanup_devices(self):
        now = time.time()
        remove_devices = []
        for mac, seen_time in self.seen_devices.items():
            if now - 600 > seen_time:
                remove_devices.append(mac)
        for mac in remove_devices:
            del self.seen_devices[mac]
        self.cleanup_counter = 0

    def publish_observation(self, mac, obs_time):
        observation = {}
        observation['hash'] = base64.urlsafe_b64encode(
            argon2.argon2_hash(mac, salt)).decode()
        observation['location'] = location
        observation['geo_point'] = self.geo_point
        observation['timestamp'] = obs_time
        try:
            r = requests.post("http://localhost:5000/observations",
                              json=observation)
        except Exception as e:
            print('publish failed for observation: ' + observation['hash'] +
                  'with exception: ' + str(e) + " http code: " + str(r.status_code))
            self.observations.put((mac, obs_time))
            pass


class LocationService(multiprocessing.Process):

    def __init__(self, location_queue, api_key, interval=60):
        multiprocessing.Process.__init__(self)
        self.locations = location_queue
        self.last_scan = 0
        self.interval = interval
        self.geo_api_url = ('https://www.googleapis.com/geolocation/v1/'
                            'geolocate?key=') + api_key

    def run(self):
        while True:
            now = time.time()
            if now > self.last_scan + self.interval:
                self.get_location()
                self.last_scan = now
            time.sleep(5)

    def get_location(self):
        ap_scan = Cell.all('wlan0')
        aps = []
        for bssid in ap_scan:
            ap = {}
            ap['macAddress'] = bssid.address
            ap['signalStrength'] = bssid.signal
            ap['channel'] = bssid.channel
            aps.append(ap)
        r = requests.post(self.geo_api_url,  json={"wifiAccessPoints": aps,
                                                   "considerIp": "false"
                                                   })
        if r.status_code == 200:
            response = r.json()
            location = (response.location.lat, response.location.lng)
            self.locations.put(location)


def main():
    print(geo_point)
    observations = multiprocessing.Queue()
    locations = multiprocessing.Queue()
    ble_scanner = BLEScanner(observations)
    bt_scanner = BTScanner(observations)
    publisher = DevicePublisher(observations, locations)
    if geo_locator:
        locator = LocationService(locations, geo_api_key)
        locator.start()
    ble_scanner.start()
    bt_scanner.start()
    publisher.start()

if __name__ == "__main__":
    main()
