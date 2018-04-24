import base64
import prometheus_client
import traceback
import urllib.request
import urllib.parse

from xml.etree import ElementTree

from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, UntypedMetricFamily

def probe(target, user, pass_):
    '''
    Returns a collector populated with metrics from the target array.
    '''
    auth = b'Basic ' + base64.b64encode('{}:{}'.format(user, pass_).encode('latin1'))
    url = urllib.parse.urlunsplit(('http', target, '/admin/opstats.asp', None, None))
    req = urllib.request.Request(url)
    req.add_header(b'Authorization', auth)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return Collector(ElementTree.parse(resp))

class Collector:
    def __init__(self, opstats):
        self.__opstats = opstats
        self.__parent_map = {c: p for p in opstats.iter() for c in p}

        self.__nexsan_sys_details = UntypedMetricFamily('nexsan_sys_details', '', labels=['friendly_name', 'system_name', 'system_id', 'firmware_version'])
        self.__nexsan_sys_date = CounterMetricFamily('nexsan_sys_date', '')
        self.__nexsan_env_psu_power_good = GaugeMetricFamily('nexsan_env_psu_power_good', '', labels=['psu', 'enclosure'])
        self.__nexsan_env_psu_power_watts = GaugeMetricFamily('nexsan_env_psu_power_watts', '', labels=['psu', 'enclosure'])
        self.__nexsan_env_psu_temp_celsius = GaugeMetricFamily('nexsan_env_psu_temp_celsius', '', labels=['psu', 'enclosure'])
        self.__nexsan_env_psu_temp_good = GaugeMetricFamily('nexsan_env_psu_temp_good', '', labels=['psu', 'enclosure'])
        self.__nexsan_env_psu_blower_rpm = GaugeMetricFamily('nexsan_env_psu_blower_rpm', '', labels=['psu', 'enclosure', 'blower'])
        self.__nexsan_env_psu_blower_good = GaugeMetricFamily('nexsan_env_psu_blower_good', '', labels=['psu', 'enclosure', 'blower'])
        self.__nexsan_env_controller_voltage_volts = GaugeMetricFamily('nexsan_env_controller_voltage_volts', '', labels=['controller', 'enclosure', 'voltage'])
        self.__nexsan_env_controller_voltage_good = GaugeMetricFamily('nexsan_env_controller_voltage_good', '', labels=['controller', 'enclosure', 'voltage'])
        self.__nexsan_env_controller_temp_celsius = GaugeMetricFamily('nexsan_env_controller_temp_celsius', '', labels=['controller', 'enclosure', 'temp'])
        self.__nexsan_env_controller_temp_good = GaugeMetricFamily('nexsan_env_controller_temp_good', '', labels=['controller', 'enclosure', 'temp'])
        self.__nexsan_env_controller_battery_charge_good = GaugeMetricFamily('nexsan_env_controller_battery_charge_good', '', labels=['controller', 'enclosure', 'battery'])
        self.__nexsan_env_pod_voltage_volts = GaugeMetricFamily('nexsan_env_pod_voltage_volts', '', labels=['pod', 'enclosure', 'voltage'])
        self.__nexsan_env_pod_voltage_good = GaugeMetricFamily('nexsan_env_pod_voltage_good', '', labels=['pod', 'enclosure', 'voltage'])
        self.__nexsan_env_pod_temp_celsius = GaugeMetricFamily('nexsan_env_pod_temp_celsius', '', labels=['pod', 'enclosure', 'temp'])
        self.__nexsan_env_pod_temp_good = GaugeMetricFamily('nexsan_env_pod_temp_good', '', labels=['pod', 'enclosure', 'temp'])
        self.__nexsan_env_pod_front_blower_rpm = GaugeMetricFamily('nexsan_env_pod_front_blower_rpm', '', labels=['pod', 'enclosure', 'blower'])
        self.__nexsan_env_pod_front_blower_good = GaugeMetricFamily('nexsan_env_pod_front_blower_good', '', labels=['pod', 'enclosure', 'blower'])
        self.__nexsan_env_pod_tray_blower_rpm = GaugeMetricFamily('nexsan_env_pod_tray_blower_rpm', '', labels=['pod', 'enclosure', 'blower'])
        self.__nexsan_env_pod_tray_blower_good = GaugeMetricFamily('nexsan_env_pod_tray_blower_good', '', labels=['pod', 'enclosure', 'blower'])

    def isgood(self, elem):
        if elem.attrib['good'] == 'yes':
            return 1
        else:
            return 0

    def collect(self):
        for child in self.__opstats.iterfind('./*'):
            if child.tag == 'nexsan_sys_details':
                self.collect_sys_details(child)
            elif child.tag == 'nexsan_env_status':
                self.collect_env_status(child)

        yield from (v for k, v in self.__dict__.items() if k.startswith('_Collector__nexsan_'))

    def collect_sys_details(self, sys_details):
        self.__nexsan_sys_details.add_metric([sys_details.findtext('./' + l) for l in self.__nexsan_sys_details._labelnames], 1)
        self.__nexsan_sys_date.add_metric([], int(sys_details.findtext('./date')))

    def collect_env_status(self, env_status):
        for psu in env_status.iterfind('.//psu'):
            self.collect_psu(psu)
        for c in env_status.iterfind('.//controller'):
            self.collect_controller(c)
        for pod in env_status.iterfind('.//pod'):
            self.collect_pod(pod)

    def collect_psu(self, psu):
        values = [psu.attrib['id'], self.__parent_map[psu].attrib['id']]

        self.__nexsan_env_psu_power_good.add_metric(values, self.isgood(psu.find('./state')))
        self.__nexsan_env_psu_power_watts.add_metric(values, int(psu.find('./state').attrib['power_watt']))
        self.__nexsan_env_psu_temp_celsius.add_metric(values, int(psu.find('./temperature_deg_c').text))
        self.__nexsan_env_psu_temp_good.add_metric(values, self.isgood(psu.find('./temperature_deg_c')))

        for b in psu.iterfind('./blower_rpm'):
            self.__nexsan_env_psu_blower_rpm.add_metric(values + [b.attrib['id']], int(b.text))
            self.__nexsan_env_psu_blower_good.add_metric(values + [b.attrib['id']], self.isgood(b))

    def collect_controller(self, controller):
        values = [controller.attrib['id'], self.__parent_map[controller].attrib['id']]

        for v in controller.iterfind('./voltage'):
            self.__nexsan_env_controller_voltage_volts.add_metric(values + [v.attrib['id']], float(v.text))
            self.__nexsan_env_controller_voltage_good.add_metric(values + [v.attrib['id']], self.isgood(v))

        for t in controller.iterfind('./temperature_deg_c'):
            self.__nexsan_env_controller_temp_celsius.add_metric(values + [t.attrib['id']], float(t.text))
            self.__nexsan_env_controller_temp_good.add_metric(values + [t.attrib['id']], self.isgood(t))

        for b in controller.iterfind('./battery'):
            self.__nexsan_env_controller_battery_charge_good.add_metric(values + [b.attrib['id']], self.isgood(b.find('./charge_state')))

    def collect_pod(self, pod):
        values = [pod.attrib['id'], self.__parent_map[pod].attrib['id']]

        for v in pod.iterfind('./voltage'):
            self.__nexsan_env_pod_voltage_volts.add_metric(values + [v.attrib['id']], float(v.text))
            self.__nexsan_env_pod_voltage_good.add_metric(values + [v.attrib['id']], self.isgood(v))

        for t in pod.iterfind('./temperature_deg_c'):
            self.__nexsan_env_pod_temp_celsius.add_metric(values + [t.attrib['id']], float(t.text))
            self.__nexsan_env_pod_temp_good.add_metric(values + [t.attrib['id']], self.isgood(t))

        for b1 in pod.iterfind('./front_panel/blower_rpm'):
            self.__nexsan_env_pod_front_blower_rpm.add_metric(values + [b1.attrib['id']], float(b1.text))
            self.__nexsan_env_pod_front_blower_good.add_metric(values + [b1.attrib['id']], self.isgood(b1))

        for b2 in pod.iterfind('./fan_tray/blower_rpm'):
            self.__nexsan_env_pod_tray_blower_rpm.add_metric(values + [b2.attrib['id']], float(b2.text))
            self.__nexsan_env_pod_tray_blower_good.add_metric(values + [b2.attrib['id']], self.isgood(b2))
