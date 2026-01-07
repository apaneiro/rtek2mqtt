import asyncio

from enum import Enum
from time import time
from base64 import b64encode


##########################################################
class Device():
##########################################################
    def __init__(self, key, config_entity, topic):
        self.__key = key
        self.__label = config_entity['label']
        self.__name = config_entity['name']
        self.__area = config_entity['area']
        self.__topic = topic

    @property
    def key(self):
        return self.__key

    @property
    def label(self):
        return self.__label

    @property
    def name(self):
        return self.__name

    @property
    def area(self):
        return self.__area

    @property
    def topic(self):
        return self.__topic

##########################################################
class Doorbell(Device):
##########################################################
    def __init__(self, key, config_entity, topic):
        super().__init__(key, config_entity, topic)
        self.__camera = None
        self.__ison_switch = None
        self.__incoming = None
        self.__inprogress = None

    @property
    def camera(self):
        return self.__camera

    @camera.setter
    def camera(self, value):
        self.__camera = value

    @property
    def ison_switch(self):
        return self.__ison_switch

    @ison_switch.setter
    def ison_switch(self, value):
        self.__ison_switch = value

    @property
    def incoming(self):
        return self.__incoming

    @incoming.setter
    def incoming(self, value):
        self.__incoming = value

    @property
    def inprogress(self):
        return self.__inprogress

    @inprogress.setter
    def inprogress(self, value):
        self.__inprogress = value

    ######################################
    def handle_mqtt_button_press(self, debug, log, mqttTxQueue, rtekTxQueue, button, payload):
    ######################################
        if (debug > 0):
            log.info (f'========> BUTTON {payload}: {button.name}')

        doorbell = self

        match button.function:
            case ButtonF.STARTCALL:
                # Green button, set camera ON
                mqttTxQueue.put_nowait([doorbell.ison_switch.topic + '/set', 'ON', 0, False])
                if debug > 0:
                    log.info('========> CAMERA ON =========')

                if doorbell.incoming.state == 1:
                    # Send to Rtek - accept call
                    packet ='fa 02 00 44 ' + rtek_hex_block('AcceptCall', 'all')
                    rtekTxQueue.put_nowait(packet)
                    if debug > 0:
                        log.info(f'========> ACCEPT {doorbell.name} =========')

            case ButtonF.ENDCALL:
                # Red button
                if doorbell.inprogress.state == 1:
                    # Send to Rtek - hangup
                    packet ='fa 02 00 44 ' + rtek_hex_block('HangupCall', doorbell.name)
                    rtekTxQueue.put_nowait(packet)
                    if debug > 0:
                        log.info(f'========> HANGUP {doorbell.name} =========')

                    # set camera OFF??
                    #mqttTxQueue.put_nowait([doorbell.ison_switch.topic + '/set', 'OFF', 0, False])

                elif doorbell.ison_switch.state == 1:
                    # set camera OFF
                    mqttTxQueue.put_nowait([doorbell.ison_switch.topic + '/set', 'OFF', 0, False])

    ######################################
    def handle_mqtt_switch_state(self, debug, log, mqttTxQueue, rtekTxQueue, switch, payload):
    ######################################
        if (debug > 0):
            log.info (f'========> SWITCH {payload}: {switch.name}')

        doorbell = self

        # Update state
        switch.state = 1 if payload == 'ON' else 0
        mqttTxQueue.put_nowait([switch.topic + '/state', payload, 0, True])

        match switch.function:
            case SwitchF.OPENDOOR:
                if payload == 'ON':
                    # Send to Rtek - open door
                    packet ='fa 02 00 44 ' + rtek_hex_block('OpenDoor', doorbell.name)
                    rtekTxQueue.put_nowait(packet)

                    # OPENDOOR is momentary press
                    mqttTxQueue.put_nowait([switch.topic + '/set', 'OFF', 0, False])

                    if debug > 0:
                        log.info(f'========> OPEN DOOR: {doorbell.name} =========')

            case SwitchF.ENABLECAM:
                if payload == 'ON':
                    log.info(f'========> CAMERA ON: {doorbell.name}')

                    doorbell.camera.ison_time = time()

                    # Send to Rtek
                    packet ='fa 02 00 44 ' + rtek_hex_block('RequestServiceOnDemand', f'VideoDoorUndecodedImageOnDemand#{doorbell.name}')
                    rtekTxQueue.put_nowait(packet)
                else:
                    log.info(f'========> CAMERA OFF: {doorbell.name}')

                    doorbell.camera.ison_time = 0


##########################################################
class Camera(Device):
##########################################################
#    def __init__(self, key, config_entity, topic, maxfps, maxsecondson, doorbell = None):
    def __init__(self, key, config_entity, topic, maxsecondson, doorbell = None):
        super().__init__(key, config_entity, topic)
        self.__doorbell = doorbell
#        self.__maxfps = maxfps
        self.__maxsecondson = maxsecondson
        self.__ison_time = 0
        self.__last_image_time = time()
        self.__is_processing = False

    @property
    def doorbell(self):
        return self.__doorbell

    @property
    def ison_time(self):
        return self.__ison_time

    @ison_time.setter
    def ison_time(self, value):
        self.__ison_time = value

    @property
    def last_image_time(self):
        return self.__last_image_time

    @last_image_time.setter
    def last_image_time(self, value):
        self.__last_image_time = value

    @property
    def is_processing(self):
        return self.__is_processing

    @is_processing.setter
    def is_processing(self, value):
        self.__is_processing = value

#    @property
#    def maxfps(self):
#        return self.__maxfps

    @property
    def maxsecondson(self):
        return self.__maxsecondson

'''
    ######################################
    async def handle_new_image(self, log, debug, rtekTxQueue):
    ######################################
        is_processing = self.is_processing
        last_image_time = self.last_image_time
        camera = self

        # wait for previous instance to finish
        while is_processing:
            await asyncio.sleep(0.01)
        is_processing = True

        topic = camera.topic
        doorbell_name = camera.doorbell.name

        # throtle images per second to cameraMaxFps
        time_now = time()
        millisecs_elapsed = (time_now - last_image_time) * 1000
        millisecs_per_image = 1000 / self.maxfps

        if millisecs_elapsed < millisecs_per_image:
            await asyncio.sleep((millisecs_per_image - millisecs_elapsed) / 1000) # in seconds

        # Send to Rtek - request new image
        packet ='fa 02 00 44 ' + rtek_hex_block('RequestServiceOnDemand', f'VideoDoorUndecodedImageOnDemand#{doorbell_name}')
        rtekTxQueue.put_nowait(packet)

        if (debug > 0):
            log.info(f'================> Request new Image for: {doorbell_name}')

        last_image_time = time()
        is_processing = False

    ######################################
    async def async_b64encode(self, data: bytes):
    ######################################
        loop = asyncio.get_running_loop()
        # Offload CPU-heavy task to a thread pool
        return await loop.run_in_executor(None, b64encode, data)
'''

##########################################################
class Button(Device):
##########################################################
    def __init__(self, key, config_entity, topic, doorbell = None, function = None):
        super().__init__(key, config_entity, topic)
        self.__doorbell = doorbell
        self.__function = function

    @property
    def doorbell(self):
        return self.__doorbell

    @property
    def function(self):
        return self.__function

##########################################################
class Switch(Device):
##########################################################
    def __init__(self, key, config_entity, topic, doorbell = None, function = None):
        super().__init__(key, config_entity, topic)
        self.__state = -1
        self.__doorbell = doorbell
        self.__function = function

    @property
    def state(self):
        return self.__state

    @state.setter
    def state(self, value):
        self.__state = value

    @property
    def doorbell(self):
        return self.__doorbell

    @property
    def function(self):
        return self.__function

##########################################################
class Light(Device):
##########################################################
    def __init__(self, key, config_entity, topic):
        super().__init__(key, config_entity, topic)
        self.__state = -1

    @property
    def state(self):
        return self.__state

    @state.setter
    def state(self, value):
        self.__state = value

##########################################################
class Sensor(Device):
##########################################################
    def __init__(self, key, config_entity, topic, state = -1): #, doorbell = None, function = None):
        super().__init__(key, config_entity, topic)
        self.__state = state
#        self.__doorbell = doorbell
#        self.__function = function

    @property
    def state(self):
        return self.__state

    @state.setter
    def state(self, value):
        self.__state = value

#    @property
#    def doorbell(self):
#        return self.__doorbell

#    @property
#    def function(self):
#        return self.__function

##########################################################
class Blind(Device):
##########################################################
    def __init__(self, key, config_entity, topic):
        super().__init__(key, config_entity, topic)
        self.__position = -1
        self.__position_open = -1
        self.__position_closed = -1

    @property
    def position(self):
        return self.__position

    @position.setter
    def position(self, value):
        self.__position = value

    @property
    def position_open(self):
        return self.__position_open

    @property
    def position_closed(self):
        return self.__position_closed



##########################################################
class ButtonF(Enum):
##########################################################
    STARTCALL = 1
    ENDCALL = 2
#    OPENDOOR = 3

##########################################################
class SwitchF(Enum):
##########################################################
    ENABLECAM = 1
    OPENDOOR = 2

##########################################################
#class SensorF(Enum):
##########################################################
#    CALLREQUEST = 1
#    INPROGRESS = 2


##########################################################
def rtek_hex_block(field1, field2):
##########################################################
    # an rtek string is preceded by its length in 4 bytes
    field1Len = len(field1)
    field1LenHex = f'{field1Len:08x}'   # 4 bytes
    field1Hex = ''.join('{:02x}'.format(ord(c)) for c in field1)

    field2Len = len(field2)
    field2LenHex = f'{field2Len:08x}'   # 4 bytes
    field2Hex = ''.join('{:02x}'.format(ord(c)) for c in field2)

    blockLen = field1Len + field2Len + 9
    blockLenHex = f'{blockLen:08x}'     # 4 bytes

    return blockLenHex + field1LenHex + field1Hex + field2LenHex + field2Hex + 'ab'

##########################################################
def rtek_hex_block_zeros(field1, zeros):
##########################################################
    # an rtek string is preceded by its length in 4 bytes
    field1Len = len(field1)
    field1LenHex = f'{field1Len:08x}'   # 4 bytes
    field1Hex = ''.join('{:02x}'.format(ord(c)) for c in field1)

    zerosLen = len(zeros) >> 1          # divide by 2

    blockLen = field1Len + zerosLen + 5
    blockLenHex = f'{blockLen:08x}'     # 4 bytes

    return blockLenHex + field1LenHex + field1Hex + zeros + 'ab'
