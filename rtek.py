import os
import asyncio
import aiomqtt
import logging
import sys
import base64
import json
import time

from devices import *
from config import load_rtek_config


doorbells = None
buttons = None
switches = None
lights = None
sensors = None
blinds = None
speakers = None
cameras = None

mqttTxQueue = asyncio.Queue()
rtekTxQueue = asyncio.Queue()

rtek_poll_received = False
frames_received = 0
debug = 0

cameraMaxFps = 0
cameraSecondsOn = 0
millisec_lastimg = int(round(time.time() * 1000))
baseTopic = ''

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s: %(message)s')
handler.setFormatter(formatter)

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.addHandler(handler)

##########################################################
def throttle_images_per_sec():
##########################################################
    global millisec_lastimg

    # throtle images per second to cameraMaxFps
    millisec_now = int(round(time.time() * 1000))
    if millisec_lastimg - millisec_now < 1000 / cameraMaxFps:
        time.sleep(1 / cameraMaxFps) # seconds
    millisec_lastimg = millisec_now



##########################################################
########################   MQTT   ########################
##########################################################


##########################################################
async def start_mqtt(config):
##########################################################
    reconnect_interval = 10

    subscribeTopic = baseTopic + "/+/+/+"
    availableTopic = baseTopic + "/server/available"

    # mqttHost = config['mqttHost']
    # mqttPort = config['mqttPort']
    # mqttUser = config['mqttUser']
    # mqttPassword = config['mqttPassword']
    mqttHost = os.environ["MQTTHOST"]
    mqttPort = int(os.environ["MQTTPORT"])
    mqttUser = os.environ["MQTTUSER"]
    mqttPassword = os.environ["MQTTPASSWORD"]

    will = aiomqtt.Will(availableTopic, "offline", 2, True)
    async with aiomqtt.Client(mqttHost, mqttPort,
            username = mqttUser, password = mqttPassword, will = will) as client:
        mqttTxQueue.put_nowait([availableTopic, "online", 2, True])
        await client.subscribe(subscribeTopic)

        log.info('Connected to MQTT server')

        mqtt_tg = asyncio.TaskGroup()
        try:
            async with mqtt_tg:
                mqtt_tg.create_task(mqtt_listen(mqtt_tg, client))
                mqtt_tg.create_task(mqtt_publish(mqtt_tg, client))

        except asyncio.CancelledError:
            log.info('---> MQTT task Cancelled!')

        except aiomqtt.MqttError as error:
            log.info(f'ERROR: MQTT task - {error}')

            mqtt_tg.create_task(force_terminate_task_group())

##########################################################
async def mqtt_listen(mqtt_tg, client):
##########################################################
    global rtekTxQueue
    global frames_received

    try:
        async for message in client.messages:
            array = str(message.topic).split('/')
            entity_type = array[1]
            entity_key = int(array[2])
            entity_topic = array[3]
            payload = str(message.payload.decode())

            if (debug > 0):
                if entity_type != 'camera':
                    log.info (f'---> MQTT received - type: {entity_type}, key: {entity_key}, {entity_topic}: {payload}')
                elif (debug > 1):
                    log.info (f'---> MQTT received - type: {entity_type}, key: {entity_key}, {entity_topic}: ...jpeg...')

            match entity_type:
                case 'sensor':
                    if entity_topic == 'state':
                        sensor = sensors[entity_key]
                        sensor.state = 1 if payload == 'ON' else 0

                    if (debug > 0):
                        log.info (f'========> SENSOR {payload}: {sensor.name}')

                case 'button':
                    if entity_topic == 'set' and payload == 'PRESS':
                        button = buttons[entity_key]
                        doorbell = button.doorbell

                        if doorbell is not None:        # Doorbell Button?
                            doorbell.handle_mqtt_button_press(
                                debug, log, mqttTxQueue, rtekTxQueue, button, payload)

                        else:
                            # no Rtek buttons yet
                            pass

                case 'switch':
                    if entity_topic == 'set':
                        switch = switches[entity_key]
                        doorbell = switch.doorbell

                        if doorbell is not None:    # Doorbell Switch
                            doorbell.handle_mqtt_switch_state(
                                debug, log, mqttTxQueue, rtekTxQueue, switch, payload)

                        else:       # Send to Rtek - switch
                            hex_key = "%0.4x" % entity_key
                            hex_value = '01' if value == 'ON' else '00'
                            packet = f'fa 02 00 48 00 00 00 09 00 00 {hex_key} 00 00 00 {hex_value} ab'
                            rtekTxQueue.put_nowait(packet)

                case 'light':       # Send to Rtek - light
                    if entity_topic == 'set':
                        hex_key = "%0.4x" % entity_key
                        hex_value = '01' if value == 'ON' else '00'
                        packet = f'fa 02 00 48 00 00 00 09 00 00 {hex_key} 00 00 00 {hex_value} ab'
                        rtekTxQueue.put_nowait(packet)

                case 'blind':       # Send to Rtek - blind
                    if entity_topic == 'set':
                        hex_value = '00'    # STOP
                        hex_key = "%0.4x" % entity_key
                        match value:
                            case 'OPEN':
                                hex_value = '01'
                            case 'CLOSE':
                                hex_value = '02'
                        packet = f'fa 02 00 48 00 00 00 09 00 00 {hex_key} 00 00 00 {hex_value} ab'
                        rtekTxQueue.put_nowait(packet)

                    elif entity_topic == 'set_position':
                        hex_key = "%0.4x" % (entity_key + 2)
                        position = int(value)
                        hex_position = "%0.4x" % position
                        packet = f'fa 02 00 48 00 00 00 09 00 00 {hex_key} 00 00 {hex_position} ab'
                        rtekTxQueue.put_nowait(packet)

    except asyncio.CancelledError:
        log.info('MQTT Listen was cancelled')

    except aiomqtt.MqttError:
        log.info(f'ERROR: MQTT Listen Aiomqtt error')

        # add an exception-raising task to force the group to terminate
        mqtt_tg.create_task(force_terminate_task_group())

##########################################################
async def mqtt_publish(mqtt_tg, client):
##########################################################
    global mqttTxQueue

    try:
        while True:
            msg = await mqttTxQueue.get()
            await client.publish(msg[0], payload=msg[1], qos=msg[2], retain=msg[3])

            if (debug > 1):
                log.info(f'---> MQTT published - Topic: {msg[0]}, Payload: {msg[1]}')

    except asyncio.CancelledError:
        log.info(f'MQTT Publish was cancelled')

    except aiomqtt.MqttError:
        log.info(f'ERROR: MQTT Publish Aiomqtt error')

        # add an exception-raising task to force the group to terminate
        mqtt_tg.create_task(force_terminate_task_group())


##########################################################
########################   RTEK   ########################
##########################################################


##########################################################
class RtekClient(asyncio.Protocol):
##########################################################
    def __init__(self, on_con_lost, user, pwd):
        self.on_con_lost = on_con_lost
        self.user = user
        self.pwd = pwd
        self.connected = False
        self.transport = None
        self.block = bytearray()
        self.blockLen = 0
        self.current_call_doorbell = None

    ############################################
    def connection_made(self, transport):
    ############################################
        # Start conversation
        startMessageStr = 'fa 02 00 44 ' + rtek_hex_block('Login', self.user + ':' + self.pwd)
        startMessageStr += 'fa 02 00 44 ' + rtek_hex_block('SupportedFeature', 'SetInteger32')
        startMessageStr += 'fa 02 00 44 ' + rtek_hex_block('SetUsername', 'HomeAssistant')
        startMessageStr += 'fa 02 00 44 ' + rtek_hex_block_zeros('SetAndroidPushCredentials', f'{0:0292x}')  # 146 bytes with 0
        startMessageStr += 'fa 02 00 40 00 00 00 01 ab'        # request init
        startMessageStr += 'fa 02 00 06 00 00 00 01 ab'        # request states

        startMessage = bytes.fromhex(startMessageStr)
        transport.write(startMessage)

        if doorbells is not None:
            for doorbell in doorbells.values():
                throttle_images_per_sec()

                # Send to Rtek - request new image
                packet ='fa 02 00 44 ' + rtek_hex_block('RequestServiceOnDemand', f'VideoDoorUndecodedImageOnDemand#{doorbell.name}')
                rtekTxQueue.put_nowait(packet)


    ############################################
    def data_received(self, data):
    ############################################
        global rtek_poll_received
        global frames_received

        pollHeader = bytes([0xfa, 0x02, 0x00, 0x00])
        deviceHeader = bytes([0xfa, 0x02, 0x00, 0x48])
        speakerHeader = bytes([0xfa, 0x02, 0x00, 0x49])
        imageHeader = bytes([0xfa, 0x02, 0x00, 0x50])
        doorbellHeader = bytes([0xfa, 0x02, 0x00, 0x44])
        audioHeader = bytes([0xfa, 0x02, 0x00, 0x53])

        for d in data:
            self.block.append(d)
            dataLen = len(self.block)

            if dataLen == 8:
                self.blockLen = int.from_bytes(self.block[4 : 8])
                continue
            elif dataLen < self.blockLen + 8:
                continue

            # at this point the whole block has been received

            blockHeader = self.block[: 4]

            #if blockHeader != deviceHeader:
            #    log.info('DEBUG - RTEK blockHeader: ' + ' '.join(f'{r:02x}' for r in self.block[:4]))
            #    log.info('DEBUG - RTEK blockLen: ' + str(self.blockLen))
            if (debug > 2):
                log.info('DEBUG - RTEK received - ' + ' '.join(f'{r:02x}' for r in self.block))

            # check if last byte is 0xab ??
            # if (d != 0xab):
            #   invalidate message ?? not for images

            ###############
            # poll
            if self.blockLen == 1 and blockHeader == pollHeader:
                rtek_poll_received = True

                if (debug > 1):
                    log.info('Poll received')
            # end poll
            ###############

            ###############
            # switches, lights, sensors and blinds
            elif self.blockLen == 9 and blockHeader == deviceHeader:
                key = (self.block[10] << 8) + self.block[11]
                state = (self.block[14] << 8) + self.block[15]

                ###############
                # switch?
                try:
                    if state != switches[key].state:
                        switches[key].state = state
                        mqttTxQueue.put_nowait([switches[key].topic + '/state', 'ON' if state == 1 else 'OFF', 0, True])

                        if debug > 0:
                            log.info("---> RTEK received - Switch: " + switches[key].label + " " + ("OFF" if state == 0 else "ON") + "\t" + switches[key].name)
                except:

                    ###############
                    # light?
                    try:
                        if state != lights[key].state:
                            lights[key].state = state
                            mqttTxQueue.put_nowait([lights[key].topic + '/state', 'ON' if state == 1 else 'OFF', 0, True])

                            if debug > 0:
                                log.info("---> RTEK received - Light: " + lights[key].label + " " + ("OFF" if state == 0 else "ON") + "\t" + lights[key].name)
                    except:

                        ###############
                        # sensor?
                        try:
                            if state != sensors[key].state:
                                sensors[key].state = state
                                mqttTxQueue.put_nowait([sensors[key].topic + '/state', 'ON' if state == 1 else 'OFF', 0, False])

                                if debug > 0:
                                    log.info("---> RTEK received - Sensor: " + sensors[key].label + " " + ("OFF" if state == 0 else "ON") + "\t" + sensors[key].name)
                        except:

                            ###############
                            # blind position?
                            try:
                                if state != blinds[key - 2].position:
                                    blinds[key - 2].position = state
                                    mqttTxQueue.put_nowait([blinds[key - 2].topic + '/position', state, 0, True])

                                    if debug > 0:
                                        log.info("---> RTEK received - Blind Position: " + blinds[key - 2].label + " " + "{0:d}".format(state) + "\t" + blinds[key - 2].name)
                            except:
                                pass
            # end - lights, sensors and blinds
            ###############

            ###############
            # speakers
            elif self.blockLen > 9 and blockHeader == speakerHeader:
                key = (self.block[12] - 0x30) * 10000 + (self.block[13] - 0x30) * 1000 + (self.block[14] - 0x30) * 100 + (self.block[15] - 0x30) * 10
                if self.blockLen > 20:
                    key += 1

                try:
                    mqttTxQueue.put_nowait([speakers[key].topic + '/state', 'ON', 0, True])
                    mqttTxQueue.put_nowait([speakers[key].topic + '/state', 'OFF', 0, True])

                    if (debug > 0):
                        log.info("---> RTEK received - Speaker: " + speakers[key].label + ' PRESSED')
                except:
                    pass
            # end - speakers
            ###############

            ###############
            # image
            elif blockHeader == imageHeader:
                field1Len = int.from_bytes(self.block[8 : 12])
                field1Start = 17

                imageLen = int.from_bytes(self.block[12 : 16])
                imageStart = field1Start + field1Len

                field1 = self.block[field1Start : field1Start + field1Len].decode()
                doorbell_name = field1.split('#')[1]

                for key, camera in cameras.items():
                    if camera.doorbell.name == doorbell_name:
                        # found doorbell
                        doorbell = camera.doorbell

                        if doorbell.active.state == 1:
                            call_inprogress = self.current_call_doorbell is not None

                            if call_inprogress:
                                throttle_images_per_sec()

                                # Send to Rtek - request new image
                                packet ='fa 02 00 44 ' + rtek_hex_block('RequestServiceOnDemand', f'VideoDoorUndecodedImageOnDemand#{doorbell_name}')
                                rtekTxQueue.put_nowait(packet)

                                if (debug > 0):
                                    log.info(f'================> Request new Image for: {doorbell_name}, Call In Progress')

                            else:
                                if frames_received < cameraSecondsOn * cameraMaxFps:
                                    throttle_images_per_sec()

                                    # Send to Rtek - request new image
                                    packet ='fa 02 00 44 ' + rtek_hex_block('RequestServiceOnDemand', f'VideoDoorUndecodedImageOnDemand#{doorbell_name}')
                                    rtekTxQueue.put_nowait(packet)

                                    # limit nr of frames while off call
                                    frames_received += 1

                                    if (debug > 0):
                                        log.info(f'================> Request new Image for: {doorbell_name}, frame = {frames_received}')

                                else:
                                    # set camera OFF
                                    mqttTxQueue.put_nowait([doorbell.active.topic + '/set', 'OFF', 0, False])

                                    frames_received = 0
                                # end - if frames_received
                            # end - if call_inprogress:
                        # end - if doorbell.active.state == 1:

                        image = base64.b64encode(self.block[imageStart :])
                        mqttTxQueue.put_nowait([camera.topic + '/image', image, 0, True])

                        break
                    # end -if camera.doorbell.name == doorbell_name:
                # end - for key, camera in cameras.items():
            # end - image
            ###############

            ###############
            # doorbell
            elif blockHeader == doorbellHeader:
                pointer = 8

                field1Len = int.from_bytes(self.block[pointer : pointer + 4])
                pointer += 4
                field1 = self.block[pointer : pointer + field1Len].decode()
                pointer += field1Len

                field2Len = int.from_bytes(self.block[pointer : pointer + 4])
                pointer += 4
                if field2Len == 0:
                    field2 = ''
                else:
                    field2 = self.block[pointer : pointer + field2Len].decode()

                match field1:
                    ###############
                    case 'StartCall':
                        if debug > 0:
                            log.info(f'========> Rtek START CALL: {field2}')

                        for doorbell in doorbells.values():
                            if field2.find(doorbell.name) >= 0:
                                self.current_call_doorbell = doorbell

                                # set camera ON
                                mqttTxQueue.put_nowait([doorbell.active.topic + '/set', 'ON', 0, False])

                                # set inprogress OFF, incoming ON
                                mqttTxQueue.put_nowait([doorbell.inprogress.topic + '/state', 'OFF', 0, False])
                                mqttTxQueue.put_nowait([doorbell.incoming.topic + '/state', 'ON', 0, False])

                                # Send to Rtek - accept call
                                packet ='fa 02 00 44 ' + rtek_hex_block('AcceptCall', 'all')
                                rtekTxQueue.put_nowait(packet)

                                if debug > 0:
                                    log.info(f'========> ACCEPT CALL {doorbell.name} =========')

                                break

                    ###############
                    case 'CallAccepted':
                        if debug > 0:
                            log.info(f'========> Rtek CALL ACCEPTED: {field2}')

                        if self.current_call_doorbell is not None:
                            doorbell = self.current_call_doorbell

                            if field2.find('HomeAssistant') >= 0:
                                # set incoming OFF
                                mqttTxQueue.put_nowait([doorbell.incoming.topic + '/state', 'OFF', 0, False])

                            else:
                                # inprogress OFF, incoming OFF
                                mqttTxQueue.put_nowait([doorbell.inprogress.topic + '/state', 'OFF', 0, False])
                                mqttTxQueue.put_nowait([doorbell.incoming.topic + '/state', 'OFF', 0, False])

                                self.current_call_doorbell = None

                    ###############
                    case 'CallInprogress':
                        if debug > 0:
                            log.info(f'========> Rtek CALL IN PROGRESS: {field2}')

                        if self.current_call_doorbell is not None:
                            doorbell = self.current_call_doorbell

                            if field2.find('HomeAssistant') >= 0:
                                # set inprogress ON
                                mqttTxQueue.put_nowait([doorbell.inprogress.topic + '/state', 'ON', 0, False])

                            else:
                                # inprogress OFF, incoming OFF
                                mqttTxQueue.put_nowait([doorbell.inprogress.topic + '/state', 'OFF', 0, False])
                                mqttTxQueue.put_nowait([doorbell.incoming.topic + '/state', 'OFF', 0, False])

                                self.current_call_doorbell = None

                    ###############
                    case 'EventLog':
                        if debug > 0:
                            eventLog = field2
                            log.info(f'========> Rtek EVENTLOG: {eventLog}')

                    ###############
                    case 'CallTerminated':
                        if self.current_call_doorbell is not None:
                            doorbell = self.current_call_doorbell

                            if debug > 0:
                                mobile = field2
                                log.info(f'========> CALL TERMINATED: {mobile}')

                            # inprogress OFF, incoming OFF
                            mqttTxQueue.put_nowait([doorbell.inprogress.topic + '/state', 'OFF', 0, False])
                            mqttTxQueue.put_nowait([doorbell.incoming.topic + '/state', 'OFF', 0, False])

                            # Send to Rtek - unrequest
                            packet ='fa 02 00 44 ' + rtek_hex_block('UnrequestService', f'VideoDoorUndecodedImageOnDemand#{doorbell.name}')
                            rtekTxQueue.put_nowait(packet)

                            if debug > 0:
                                log.info(f'========> UNREQUEST {doorbell.name} =========')

                            self.current_call_doorbell = None

                    ###############
                    case 'ServerVersion':
                        log.info(f'================> Server Version')
                        if debug > 1:
                            log.info(field2)

                        mqttTxQueue.put_nowait([baseTopic + "/server/version", field2, 0, True])

                    ###############
                    case 'MainEventLogFile':
                        log.info('================> Main Event Log')
                        if debug > 1:
                            log.info(field2)

                        mqttTxQueue.put_nowait([baseTopic + "/server/log", field2, 0, True])

                    ###############
                    case 'CamerasXMLFile':
                        log.info('================> Cameras XML')
                        if debug > 1:
                            log.info(field2)

                        mqttTxQueue.put_nowait([baseTopic + "/server/camerasxml", field2, 0, True])

                    ###############
                    case 'VideoDoorsXMLFile':
                        log.info('================> VideoDoors XML')
                        if debug > 1:
                            log.info(field2)

                        mqttTxQueue.put_nowait([baseTopic + "/server/videodoorsxml", field2, 0, True])

                    ###############
                    case 'AskCustomerSatisfactionLevel':
                        pass

                    ###############
                    case _:
                        log.info("================> UNKNOWN 44: " + ''.join('{:02x}'.format(x) for x in self.block))
            # end - doorbell
            ###############

            ###############
            # audio
            elif blockHeader == audioHeader:
                if debug > 1:
                    log.info('================> AUDIO PACKET')
            # end - audio
            ###############

            ###############
            # Unknown
            else:
                # log packet
                if (debug > 1 and dataLen > 0):
                    log.info("================> DEBUG - UNKNOWN: " + ''.join('{:02x}'.format(x) for x in self.block))
            # end - unknown
            ###############

            self.block.clear()
            self.blockLen = 0
        # end - for d in data:
        ###############


    ############################################
    def connection_lost(self, exc):
    ############################################
        log.info('WARNING: The RTEK server closed the connection')

        self.on_con_lost.set_result(True)

##########################################################
async def start_rtek(config):
##########################################################
    global rtek_poll_received

    rtekHost = config["rtekHost"]
    rtekPort = config["rtekPort"]
    rtekUser = config["rtekUser"]
    rtekPassword = "" if config["rtekPassword"] is None else config["rtekPassword"].strip()

    loop = asyncio.get_running_loop()
    on_con_lost = loop.create_future()
    transport, protocol = await loop.create_connection(
        lambda: RtekClient(on_con_lost, rtekUser, rtekPassword), rtekHost, rtekPort)

    if transport:
        log.info('Connected to RTEK server')
        rtek_poll_received = True

        rtek_tg = asyncio.TaskGroup()
        try:
            async with rtek_tg:
                rtek_tg.create_task(rtek_polling(rtek_tg))
                rtek_tg.create_task(rtek_publish(rtek_tg, transport))

            try:
                await on_con_lost
            finally:
                transport.close()

        except asyncio.CancelledError:
            log.info('RTEK task was cancelled')

        except aiomqtt.MqttError as error:
            log.info(f'ERROR: RTEK task - {error}')

            # add an exception-raising task to force the group to terminate
            rtek_tg.create_task(force_terminate_task_group())

##########################################################
async def rtek_publish(rtek_tg, transport):
##########################################################
    global rtekTxQueue

    try:
        while True:
            msg = await rtekTxQueue.get()
            msgBytes = bytes.fromhex(msg)

            transport.write(msgBytes)

            if (debug > 1):
                log.info(f'---> RTEK published: {msg}')

    except asyncio.CancelledError:
        log.info('RTEK Publish was cancelled')

    except aiomqtt.MqttError as error:
        log.info(f'ERROR: RTEK Publish error - {error}')

        # add an exception-raising task to force the group to terminate
        rtek_tg.create_task(force_terminate_task_group())

##########################################################
async def rtek_polling(rtek_tg):
##########################################################
    global rtek_poll_received

    tx_poll_packet = 'fa 01 00 00 00 01 ab'
    availableTopic = baseTopic + "/server/available"

    while (rtek_poll_received):
        rtek_poll_received = False

        # Send to Rtek - poll
        rtekTxQueue.put_nowait(tx_poll_packet)

        if (debug > 1):
            log.info('Poll sent')

        #mqttTxQueue.put_nowait([availableTopic, "online", 2, True])
        await asyncio.sleep(10)

    # While loop exited, poll was not received
    log.info('ERROR: RTEK Poll missed')

    # try to set server offline
    availableTopic = baseTopic + "/server/available"
    mqttTxQueue.put_nowait([availableTopic, "offline", 2, True])


    # add an exception-raising task to force the group to terminate
    rtek_tg.create_task(force_terminate_task_group())


##########################################################
########################   MAIN   ########################
##########################################################


##########################################################
def load_addon_config():
##########################################################
    global debug
    global cameraMaxFps
    global cameraSecondsOn
    global baseTopic

    addonConfig = dict()

    try:
        addonConfigFile = "/data/options.json"
        addonConfig = json.loads(open(addonConfigFile).read())
    except:
        log.info('ERROR: Could not open ADDON config file!')
        exit(1)

    debug = addonConfig["debug"]
    cameraSecondsOn = addonConfig["cameraMaxFps"]
    cameraMaxFps = addonConfig["cameraSecondsOn"]
    baseTopic = addonConfig['mqttBaseTopic']

    return addonConfig

##########################################################
class TerminateTaskGroup(Exception):
##########################################################
    """Exception raised to terminate a task group."""

##########################################################
async def force_terminate_task_group():
##########################################################
    """Used to force termination of a task group."""
    raise TerminateTaskGroup()
    # Exit, rely on Home Assistant Whatchdog to recover

##########################################################
async def main():
##########################################################
    global doorbells
    global cameras
    global buttons
    global switches
    global lights
    global sensors
    global blinds
    global speakers

    log.info("---> Starting")

    addonConfig = load_addon_config()

    devices = await load_rtek_config(log, mqttTxQueue, baseTopic)
    if devices is not None:
        doorbells = devices['doorbells']
        cameras = devices['cameras']
        buttons = devices['buttons']
        switches = devices['switches']
        lights = devices['lights']
        sensors = devices['sensors']
        blinds = devices['blinds']
        speakers = devices['speakers']

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(start_mqtt(addonConfig))
                tg.create_task(start_rtek(addonConfig))

        except asyncio.CancelledError:
            log.info('---> Cancelled!')

    log.info("---> Exiting")

    eventloop = asyncio.get_event_loop()
    eventloop.close()

    # close log handlers
    for handler in log.handlers:
        handler.close()
        log.removeFilter(handler)

    sys.exit(1)

##########################################################
if __name__ == '__main__':
##########################################################
    # Change to the "Selector" event loop if platform is Windows
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
        set_event_loop_policy(WindowsSelectorEventLoopPolicy())

    # Run your async application as usual
    asyncio.run(main())
