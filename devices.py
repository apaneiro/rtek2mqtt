from enum import Enum

##########################################################
class Device():
##########################################################
    def __init__(self, key, device, topic):
        self.__key = key
        self.__label = device['label']
        self.__name = device['name']
        self.__area = device['area']
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
    def __init__(self, key, device, topic):
        super().__init__(key, device, topic)
        self.__camera = None
        self.__active = None
        self.__incoming = None
        self.__inprogress = None

    @property
    def camera(self):
        return self.__camera

    @camera.setter
    def camera(self, value):
        self.__camera = value

    @property
    def active(self):
        return self.__active

    @active.setter
    def active(self, value):
        self.__active = value

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

        if button.function is ButtonF.STARTCALL:
            # Green button, set camera ON
            mqttTxQueue.put_nowait([doorbell.active.topic + '/set', 'ON', 0, False])
            if debug > 0:
                log.info('========> CAMERA ON =========')

            if doorbell.incoming.state == 1:
                # Send to Rtek - accept call
                packet ='fa 02 00 44 ' + rtek_hex_block('AcceptCall', 'all')
                rtekTxQueue.put_nowait(packet)
                if debug > 0:
                    log.info(f'========> ACCEPT {doorbell.name} =========')

        elif button.function is ButtonF.ENDCALL:
            # Red button
            if doorbell.inprogress.state == 1:
                # Send to Rtek - hangup
                packet ='fa 02 00 44 ' + rtek_hex_block('HangupCall', doorbell.name)
                rtekTxQueue.put_nowait(packet)
                if debug > 0:
                    log.info(f'========> HANGUP {doorbell.name} =========')

                # set camera OFF??
                #mqttTxQueue.put_nowait([doorbell.active.topic + '/set', 'OFF', 0, False])

            elif doorbell.active.state == 1:
                # set camera OFF
                mqttTxQueue.put_nowait([doorbell.active.topic + '/set', 'OFF', 0, False])

    ######################################
    def handle_mqtt_switch_state(self, debug, log, mqttTxQueue, rtekTxQueue, switch, payload):
    ######################################
        if (debug > 0):
            log.info (f'========> SWITCH {payload}: {switch.name}')

        doorbell = self

        # Update state
        switch.state = 1 if payload == 'ON' else 0
        mqttTxQueue.put_nowait([switch.topic + '/state', payload, 0, True])

        # Open Door
        if switch.function is SwitchF.OPENDOOR:
            if payload == 'ON':
                # Send to Rtek - open door
                packet ='fa 02 00 44 ' + rtek_hex_block('OpenDoor', doorbell.name)
                rtekTxQueue.put_nowait(packet)

                # OPENDOOR is momentary press
                mqttTxQueue.put_nowait([switch.topic + '/set', 'OFF', 0, False])

                if debug > 0:
                    log.info(f'========> OPEN DOOR: {doorbell.name} =========')

        # Camera ON/OFF
        elif switch.function is SwitchF.ENABLECAM:
            if payload == 'ON':
                log.info(f'========> CAMERA ON: {doorbell.name}')

                # Send to Rtek
                packet ='fa 02 00 44 ' + rtek_hex_block('RequestServiceOnDemand', f'VideoDoorUndecodedImageOnDemand#{doorbell.name}')
                rtekTxQueue.put_nowait(packet)
            else:
                log.info(f'========> CAMERA OFF: {doorbell.name}')


##########################################################
class Alarm(Device):
##########################################################
    def __init__(self, key, device, topic):
        super().__init__(key, device, topic)
        self.__state = AlarmF.DISARM
        self.__code_arm_required = device['arm_requires_pin']
        self.__code_disarm_required = device['disarm_requires_pin']
        self.__code_trigger_required = device['trigger_requires_pin']
        self.__code = device['pin']

    @property
    def state(self):
        return self.__state

    @state.setter
    def state(self, value):
        self.__state = value

    @property
    def code_arm_required(self):
        return self.__code_arm_required

    @property
    def code_disarm_required(self):
        return self.__code_disarm_required

    @property
    def code_trigger_required(self):
        return self.__code_trigger_required

    @property
    def code(self):
        return self.__code

    ######################################
    def handle_mqtt_alarm_state(self, debug, log, mqttTxQueue, rtekTxQueue, payload):
    ######################################
        if (debug > 0):
            log.info (f'========> SWITCH {payload}: {self.name}')

        alarm = self

        # Update state
        match payload:
            case 'DISARM':
                # disarm timer?
                #mqttTxQueue.put_nowait([self.topic + '/state', 'disarming', 0, True])
                #alarm.state = AlarmF.DISARMING
                #await asyncio.sleep( )
                mqttTxQueue.put_nowait([self.topic + '/state', 'disarmed', 0, True])
                alarm.state = AlarmF.DISARM
            case 'ARM_HOME':
                # arm timer???
                #mqttTxQueue.put_nowait([self.topic + '/state', 'arming', 0, True])
                #alarm.state = AlarmF.ARMING
                #await asyncio.sleep( )
                mqttTxQueue.put_nowait([self.topic + '/state', 'armed_home', 0, True])
                alarm.state = AlarmF.ARM_HOME
            case 'ARM_AWAY':
                # arm timer???
                #mqttTxQueue.put_nowait([self.topic + '/state', 'arming', 0, True])
                #alarm.state = AlarmF.ARMING
                #await asyncio.sleep( )
                mqttTxQueue.put_nowait([self.topic + '/state', 'armed_away', 0, True])
                alarm.state = AlarmF.ARM_AWAY
            case 'TRIGGER':
                mqttTxQueue.put_nowait([self.topic + '/state', 'triggered', 0, True])
                alarm.state = AlarmF.TRIGGER

##########################################################
class Camera(Device):
##########################################################
    def __init__(self, key, device, topic, doorbell = None):
        super().__init__(key, device, topic)
        self.__doorbell = doorbell

    @property
    def doorbell(self):
        return self.__doorbell

##########################################################
class Button(Device):
##########################################################
    def __init__(self, key, device, topic, doorbell = None, function = None):
        super().__init__(key, device, topic)
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
    def __init__(self, key, device, topic, doorbell = None, function = None):
        super().__init__(key, device, topic)
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
    def __init__(self, key, device, topic):
        super().__init__(key, device, topic)
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
    def __init__(self, key, device, topic, state = -1): #, doorbell = None, function = None):
        super().__init__(key, device, topic)
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
    def __init__(self, key, device, topic):
        super().__init__(key, device, topic)
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
class Speaker(Device):
##########################################################
    def __init__(self, key, device, topic):
        super().__init__(key, device, topic)




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
class AlarmF(Enum):
##########################################################
    DISARM = 0
    DISARMING = 1
    ARM_HOME = 2
    ARM_AWAY = 3
    ARMING = 4
    TRIGGER = 5
    ARMED_HOME = 6
    ARMED_AWAY = 7
    TRIGGERED = 8


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
