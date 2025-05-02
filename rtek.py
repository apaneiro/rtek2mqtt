import sys
import yaml

from rclasses import *
from mdefs import *


lights = None
sensors = None
blinds = None
speakers = None

mqttTxQueue = asyncio.Queue()
rtekTxQueue = asyncio.Queue()

rtek_poll_received = False
debug = 0

##########################################################
def load_addon_config():
##########################################################
    global debug
    addonConfig = dict()

    try:
        addonConfigFile = "/data/options.json"
        addonConfig = json.loads(open(addonConfigFile).read())
    except:
        print('Could not open ADDON config file!')
        exit(1)

    debug = addonConfig["debug"]
    return addonConfig


##########################################################
def rtek_hex_string(str):
##########################################################
    # an rtek string is preceded by its length in 4 bytes
    strHex = ''.join('{:02x}'.format(ord(c)) for c in str)
    blockLen = len(str)
    strLen = f'{blockLen:08x}'   # 4 bytes
    return blockLen + 4, strLen + strHex

##########################################################
async def load_rtek_config(addonConfig):
##########################################################
    global lights
    global sensors
    global blinds
    global speakers
    global mqttTxQueue

    try:
        rtekConfigFile = "/homeassistant/rtek/config.yaml"
        with open(rtekConfigFile, "r") as f:
            rtekConfig = yaml.safe_load(f)
    except:
        print('Could not open RTEK config file!')
        exit(1)

    # Create rtek devices and queue MQTT discovery messages
    lights = dict()
    light_config = rtekConfig['lights']
    if (light_config):
      for key in light_config.keys():
        config_entry = light_config[key]
        lights[key] = Light(key, config_entry, mqtt_device_topic(addonConfig['mqttBaseTopic'], 'light', key))
        mqttTxQueue.put_nowait(mqtt_discovery(addonConfig['mqttBaseTopic'], 'light', key, config_entry))

    sensors = dict()
    sensor_config = rtekConfig['sensors']
    if (sensor_config):
      for key in sensor_config.keys():
        config_entry = sensor_config[key]
        sensors[key] = Sensor(key, config_entry, mqtt_device_topic(addonConfig['mqttBaseTopic'], 'sensor', key))
        mqttTxQueue.put_nowait(mqtt_discovery(addonConfig['mqttBaseTopic'], 'sensor', key, config_entry))

    blinds = dict()
    blind_config = rtekConfig['blinds']
    if (blind_config):
      for key in blind_config.keys():
        config_entry = blind_config[key]
        blinds[key] = Blind(key, config_entry, mqtt_device_topic(addonConfig['mqttBaseTopic'], 'blind', key))
        mqttTxQueue.put_nowait(mqtt_discovery(addonConfig['mqttBaseTopic'], 'blind', key, config_entry))

    speakers = dict()
    speaker_config = rtekConfig['speakers']
    if (speaker_config):
      for key in speaker_config.keys():
        config_entry = speaker_config[key]
        speakers[key] = Speaker(key, config_entry, mqtt_device_topic(addonConfig['mqttBaseTopic'], 'speaker', key))
        mqttTxQueue.put_nowait(mqtt_discovery(addonConfig['mqttBaseTopic'], 'speaker', key, config_entry))

##########################################################
class RtekClient(asyncio.Protocol):
##########################################################
    def __init__(self, on_con_lost, user, pwd):
        self.on_con_lost = on_con_lost
        self.user = user
        self.pwd = pwd
        self.received =  []
        self.connected = False
        self.transport = None

    def connection_made(self, transport):
        login = rtek_hex_string('Login')
        loginHex = login[1]

        user = rtek_hex_string(self.user)
        userHex = user[1]

        blockLen = user[0] + login[0] + 2
        blockLenHex = f'{blockLen:08x}'   # 4 bytes

        # Login ... user
        startMessageStr = 'fa 02 00 44 ' + blockLenHex + loginHex + userHex + ' 3a ab '
        # SupportedFeature .. SetInteger32
        startMessageStr += 'fa 02 00 44 00 00 00 25 00 00 00 10 53 75 70 70 6f 72 74 65 64 46 65 61 74 75 72 65 00 00 00 0c 53 65 74 49 6e 74 65 67 65 72 33 32 ab '
        # SetUsername .. Mobile1
        startMessageStr += 'fa 02 00 44 00 00 00 1b 00 00 00 0b 53 65 74 55 73 65 72 6e 61 6d 65 00 00 00 07 4d 6f 62 69 6c 65 31 ab '
        # SetAndroidPushCredentials .. followed by 146 bytes with 0
        startMessageStr += 'fa 02 00 44 00 00 00 b0 00 00 00 19 53 65 74 41 6e 64 72 6f 69 64 50 75 73 68 43 72 65 64 65 6e 74 69 61 6c 73 ' + f'{0:0292x}' + ' ab '
        # request states?
        startMessageStr += 'fa 02 00 06 00 00 00 01 ab'

        startMessage = bytes.fromhex(startMessageStr)
        transport.write(startMessage)


    def data_received(self, data):
        global rtek_poll_received
        global mqttTxQueue

        rx_poll_packet = [0xfa, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0xab]
        lsb_header = [0xfa, 0x02, 0x00, 0x48, 0x00, 0x00, 0x00, 0x09]
        spk_stopped_header = [0xfa, 0x02, 0x00, 0x49, 0x00, 0x00, 0x00, 0x14, 0x00, 0x00, 0x00, 0x04]
        spk_playing_header = [0xfa, 0x02, 0x00, 0x49, 0x00, 0x00, 0x00, 0x42, 0x00, 0x00, 0x00, 0x04]

        for d in data:
            self.received.append(d)

            if (d == 0xab):
                if (self.received == rx_poll_packet):
                    rtek_poll_received = True
                    if (debug > 0):
                        print('---> Poll received')
                    self.received.clear()

                elif (len(self.received) >= 17):
                    # lights, sensors and blinds
                    if (len(self.received) == 17 and self.received[:len(lsb_header)] == lsb_header):
                        id = (self.received[10] << 8) + self.received[11]
                        state = (self.received[14] << 8) + self.received[15]
                        if (debug > 2):
                            print(' '.join(f'{r:02x}' for r in self.received))

                        # light?
                        try:
                            if (debug > 0 and state != lights[id].state or debug > 1):
                                print("Light: ", lights[id].label, " \t", ("OFF" if state == 0 else "ON"), " \t", lights[id].name)
                            if (state != lights[id].state):
                                lights[id].state = state
                                mqttTxQueue.put_nowait([lights[id].topic + '/state', 'ON' if state == 1 else 'OFF', 0, True])

                        except:

                            # sensor?
                            try:
                                if (debug > 0 and state != sensors[id].state or debug > 1):
                                    print("Sensor: ", sensors[id].label, " \t", ("OFF" if state == 0 else "ON"), " \t", sensors[id].name)
                                if (state != sensors[id].state):
                                    sensors[id].state = state
                                    mqttTxQueue.put_nowait([sensors[id].topic + '/state', 'ON' if state == 1 else 'OFF', 0, True])

                            except:

                                # blind position?
                                try:
                                    if (debug > 0 and state != blinds[id - 2].position or debug > 1):
                                        print("Blind Position: ", blinds[id - 2].label, " \t", "{0:d}".format(state), " \t", blinds[id - 2].name)
                                    if (state != blinds[id - 2].position):
                                        blinds[id - 2].position = state
                                        mqttTxQueue.put_nowait([blinds[id - 2].topic + '/position', state, 0, True])

                                except:
                                    pass
                    # end - lights, sensors and blinds

                    # speakers
                    elif (self.received[:12] == spk_stopped_header or self.received[:12] == spk_playing_header):
                        id = (self.received[12] - 0x30) * 10000 + (self.received[13] - 0x30) * 1000 + (self.received[14] - 0x30) * 100 + (self.received[15] - 0x30) * 10
                        if (self.received[:12] == spk_playing_header):
                            id = id + 1

                        try:
                            if (debug > 0):
                                print('Speaker: ', speakers[id].label, ' \t PRESSED')
                            mqttTxQueue.put_nowait([speakers[id].topic + '/state', 'ON', 0, False])
                            mqttTxQueue.put_nowait([speakers[id].topic + '/state', 'OFF', 0, False])

                        except:

                            # print packet
                            if (debug > 1):
                                print('---> Data received: ', ''.join('{:02x}'.format(x) for x in self.received))
                    # end - speakers

                    # print packet
                    if (debug > 1 and len(self.received) > 0):
                        print('---> Data received: ', ''.join('{:02x}'.format(x) for x in self.received))
                    self.received.clear()

    def connection_lost(self, exc):
        self.on_con_lost.set_result(True)
        if (debug > 0):
            print('---> The RTEK server closed the connection')

##########################################################
async def start_rtek(config):
##########################################################
    global rtek_poll_received
    reconnect_interval = 10

    while True:
        tasks = set()
        try:
            loop = asyncio.get_running_loop()
            on_con_lost = loop.create_future()

            transport, protocol = await loop.create_connection(
                lambda: RtekClient(on_con_lost, config["rtekUser"], config["rtekPassword"]),
                    config["rtekHost"], config["rtekPort"])

            if transport:
                print('---> Connected to RTEK server')
                rtek_poll_received = True

                async with asyncio.TaskGroup() as tg:
                    tasks.add(tg.create_task(rtek_polling(config)))
                    tasks.add(tg.create_task(rtek_publish(transport)))
            try:
                await on_con_lost

            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks)
                print(f'---> Connection lost, econnecting to RTEK in {reconnect_interval} seconds.')
                await asyncio.sleep(reconnect_interval)

        except Exception as exception:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks)
            print(f'---> ERROR {exception}: Reconnecting to RTEK in {reconnect_interval} seconds.')
            await asyncio.sleep(reconnect_interval)

##########################################################
async def rtek_publish(transport):
##########################################################
    global rtekTxQueue

    try:
        while True:
            msg = await rtekTxQueue.get()
            msgBytes = bytes.fromhex(msg)

            transport.write(msgBytes)

            if (debug > 1):
                print(f'---> RTEK published: {msg}')

    except asyncio.CancelledError:
        pass
    except aiomqtt.MqttError:
        pass

##########################################################
async def rtek_polling(config):
##########################################################
    global rtek_poll_received
    global mqttTxQueue
    global rtekTxQueue

    tx_poll_packet = 'fa 01 00 00 00 01 ab'
    availableTopic = config['mqttBaseTopic'] + "/server/available"

    try:
        while (rtek_poll_received):
            rtek_poll_received = False
            rtekTxQueue.put_nowait(tx_poll_packet)

            if (debug > 0):
                print('---> Poll sent')

            mqttTxQueue.put_nowait([availableTopic, "online", 2, True])
            await asyncio.sleep(10)

        if (debug > 0):
            print('---> Poll missed')

    except asyncio.CancelledError:
        pass
    except aiomqtt.MqttError:
        pass

##########################################################
async def main():
##########################################################
    tasks = set()

    print("---> Starting...")

    addonConfig = load_addon_config()
    await load_rtek_config(addonConfig)

    try:
        async with asyncio.TaskGroup() as tg:
            tasks.add(tg.create_task(start_mqtt(addonConfig, rtekTxQueue, mqttTxQueue)))
            tasks.add(tg.create_task(start_rtek(addonConfig)))

    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        print('---> Cancelled.')

##########################################################
if __name__ == '__main__':
##########################################################
    # Change to the "Selector" event loop if platform is Windows
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    # Run your async application as usual
    asyncio.run(main())
