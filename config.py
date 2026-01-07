import yaml
import json

from devices import *

##########################################################
async def load_rtek_config(log, addonConfig, mqttTxQueue, baseTopic):
##########################################################
    rtekConfig = dict()

    # Create rtek devices and queue MQTT discovery messages
    doorbells = dict()
    buttons = dict()
    switches = dict()
    lights = dict()
    sensors = dict()
    blinds = dict()
    cameras = dict()

    try:
        rtekConfigFile = "/homeassistant/rtek/config.yaml"
        with open(rtekConfigFile, "r") as f:
            rtekConfig = yaml.safe_load(f)
    except:
        log.info('ERROR: Could not open RTEK config file!')
        return

    section = None
    try:
        section = rtekConfig['doorbells']
    except:
        log.info('INFO: config section missing - doorbells')

    if isinstance(section, dict):
        for key, entity in section.items():
            name = entity['name']
            label = entity['label']

            # doorbell device
            doorbells[key] = Doorbell(key, entity, '')
            doorbell = doorbells[key]

            # doorbell entities
            doorbell_entity = entity.copy()
            doorbell_entity['name'] = f'Camera {name}'
            key += 1
            topic = f"{baseTopic}-camera/{key}/image"
            #cameraMaxFps = addonConfig["cameraMaxFps"]
            cameraSecondsOn = addonConfig["cameraSecondsOn"]
            #cameras[key] = Camera(key, doorbell_entity, topic, maxfps = cameraMaxFps, maxsecondson = cameraSecondsOn, doorbell = doorbell)
            cameras[key] = Camera(key, doorbell_entity, topic, maxsecondson = cameraSecondsOn, doorbell = doorbell)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'camera', doorbell_entity, device = doorbell))

            doorbell.camera = cameras[key]

            doorbell_entity = entity.copy()
            doorbell_entity['name'] = f'Enable Camera {name}'
            doorbell_entity['label'] = f'{label}_enable'
            key += 1
            topic = mqtt_entity_topic(baseTopic, key, 'switch')
            switches[key] = Switch(key, doorbell_entity, topic, doorbell = doorbell, function = SwitchF.ENABLECAM)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'switch', doorbell_entity, device = doorbell))
            mqttTxQueue.put_nowait([topic + '/set', 'OFF', 0, False])

            doorbell.ison_switch = switches[key]

            doorbell_entity = entity.copy()
            doorbell_entity['name'] = f'Start Call {name}'
            doorbell_entity['label'] = f'{label}_start_call'
            doorbell_entity['icon'] = 'phone'
            key += 1
            topic = mqtt_entity_topic(baseTopic, key, 'button')
            buttons[key] = Button(key, doorbell_entity, topic, doorbell = doorbell, function = ButtonF.STARTCALL)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'button', doorbell_entity, device = doorbell))

            doorbell_entity = entity.copy()
            doorbell_entity['name'] = f'End Call {name}'
            doorbell_entity['label'] = f'{label}_end_call'
            doorbell_entity['icon'] = 'phone-hangup'
            key += 1
            topic = mqtt_entity_topic(baseTopic, key, 'button')
            buttons[key] = Button(key, doorbell_entity, topic, doorbell = doorbell, function = ButtonF.ENDCALL)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'button', doorbell_entity, device = doorbell))

            doorbell_entity = entity.copy()
            doorbell_entity['name'] = f'Open Door {name}'
            doorbell_entity['label'] = f'{label}_open_door'
            doorbell_entity['icon'] = 'door-open'
            key += 1
            topic = mqtt_entity_topic(baseTopic, key, 'switch')
            switches[key] = Switch(key, doorbell_entity, topic, doorbell = doorbell, function = SwitchF.OPENDOOR)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'switch', doorbell_entity, device = doorbell))
            mqttTxQueue.put_nowait([topic + '/set', 'OFF', 0, False])

            doorbell_entity = entity.copy()
            doorbell_entity['name'] = f'Call Incoming {name}'
            doorbell_entity['label'] = f'{label}_call_incoming'
            key += 1
            topic = mqtt_entity_topic(baseTopic, key, 'sensor')
            sensors[key] = Sensor(key, doorbell_entity, topic, state = 0)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'sensor', doorbell_entity, doorbell))
            mqttTxQueue.put_nowait([topic + '/state', 'OFF', 0, True])

            doorbell.incoming = sensors[key]

            doorbell_entity = entity.copy()
            doorbell_entity['name'] = f'Call In Progress {name}'
            doorbell_entity['label'] = f'{label}_call_inprogress'
            key += 1
            topic = mqtt_entity_topic(baseTopic, key, 'sensor')
            sensors[key] = Sensor(key, doorbell_entity, topic, state = 0)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'sensor', doorbell_entity, doorbell))
            mqttTxQueue.put_nowait([topic + '/state', 'OFF', 0, True])

            doorbell.inprogress = sensors[key]
    else:
        log.info('INFO: empty doorbells config section')

    section = None
    try:
        section = rtekConfig['switches']
    except:
        log.info('INFO: config section missing - switches')
    if isinstance(section, dict):
        for key, entity in section.items():
            topic = mqtt_entity_topic(baseTopic, key, 'switch')
            switches[key] = Switch(key, entity, topic)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'switch', entity))
    else:
        log.info('INFO: empty switches config section')

    section = None
    try:
        section = rtekConfig['lights']
    except:
        log.info('INFO: config section missing - lights')
    if isinstance(section, dict):
        for key, entity in section.items():
            topic = mqtt_entity_topic(baseTopic, key, 'light')
            lights[key] = Light(key, entity, topic)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'light', entity))
    else:
        log.info('INFO: empty lights config section')

    section = None
    try:
        section = rtekConfig['sensors']
    except:
        log.info('INFO: config section missing - sensors')
    if isinstance(section, dict):
        for key, entity in section.items():
            topic = mqtt_entity_topic(baseTopic, key, 'sensor')
            sensors[key] = Sensor(key, entity, topic)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'sensor', entity))
    else:
        log.info('INFO: empty sensors config section')

    section = None
    try:
        section = rtekConfig['blinds']
    except:
        log.info('INFO: config section missing - blinds')
    if isinstance(section, dict):
        for key, entity in section.items():
            topic = mqtt_entity_topic(baseTopic, key, 'blind')
            blinds[key] = Blind(key, entity, topic)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'blind', entity))
    else:
        log.info('INFO: empty blinds config section')

    return {'doorbells': doorbells,
            'cameras': cameras,
            'buttons': buttons,
            'sensors': sensors,
            'switches': switches,
            'lights': lights,
            'blinds': blinds
            }

'''
    section = None
    try:
        section = rtekConfig['buttons']
    except:
        log.info('INFO: config section missing - buttons')
    if isinstance(section, dict):
        for key, entity in section.items():
            topic = mqtt_entity_topic(baseTopic, key, 'button')
            buttons[key] = Button(key, entity, topic)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'button', entity))
    else:
        log.info('INFO: empty buttons config section')

    section = None
    try:
        section = rtekConfig['cameras']
    except:
        log.info('INFO: config section missing - cameras')
    if isinstance(section, dict):
        for key, entity in section.items():
            topic = mqtt_entity_topic(baseTopic, key, 'camera')
            cameras[key] = Camera(key, entity, topic)
            mqttTxQueue.put_nowait(
                mqtt_discovery(baseTopic, key, 'camera', entity))
    else:
        log.info('INFO: empty cameras config section')
'''


##########################################################
def mqtt_entity_topic(baseTopic, key, entity_type):
##########################################################
    return f"{baseTopic}/{entity_type}/{key}"

##########################################################
def mqtt_discovery(baseTopic, key, entity_type, entity, device = None):
##########################################################
    name = entity['name']
    label = entity['label']

    # DEVICE
    device_model = entity_type.capitalize()
    device_name = name
    device_label = label
    device_key = key
    if isinstance(device, Device):
        device_model = type(device).__name__
        device_name = device.name
        device_label = device.label
        device_key = device.key

    payload_device = dict()
    payload_device["identifiers"] = [ str(device_key) ]
    payload_device["manufacturer"] = "RTEK"
    payload_device["model"] = device_model
    payload_device["name"] = device_label.upper() + " - " + device_name
    try:
        payload_device["suggested_area"] = entity['area']
    except:
        pass
    #payload_device["hw_version"] = "1"
    #payload_device["model_id"] = f"R{device_model}"
    #payload_device["name"] = "RTEK " + device_model + " " + device_name

    # ORIGIN
    payload_origin = dict()
    payload_origin["name"] = "rtek_addon"
    #payload_origin["sw"] = "1.0"

    # ENTITY
    payload = dict()
    payload['availability_topic'] = baseTopic + "/server/available"
    payload['device'] = payload_device
    payload['origin'] = payload_origin
    payload["unique_id"] = f"rtek_{entity_type}_{key}"

    platform = entity_type             # not for all types
    deviceTopic = mqtt_entity_topic(baseTopic, key, entity_type)
    match entity_type:
        case 'button':
            try:
                payload["icon"] = 'mdi:' + entity['icon']
            except:
                pass
            payload["command_topic"] = deviceTopic + "/set"
            payload_origin["url"] = "https://www.home-assistant.io/integrations/button.mqtt/"
            payload["name"] = name
        case 'switch':
            try:
                payload["icon"] = 'mdi:' + entity['icon']
            except:
                pass
            payload["device_class"] = 'switch'
            payload["state_topic"] = deviceTopic + "/state"
            payload["command_topic"] = deviceTopic + "/set"
            payload_origin["url"] = "https://www.home-assistant.io/integrations/switch.mqtt/"
            payload["name"] = name
        case 'light':
            try:
                payload["icon"] = 'mdi:' + entity['icon']
            except:
                pass
            payload["state_topic"] = deviceTopic + "/state"
            payload["command_topic"] = deviceTopic + "/set"
            payload_origin["url"] = "https://www.home-assistant.io/integrations/light.mqtt/"
            payload["name"] = name
        case 'sensor':
            platform = 'binary_sensor'
            try:
                payload["device_class"] = entity['class']
            except:
                pass
            payload["state_topic"] = deviceTopic + "/state"
            payload_origin["url"] = "https://www.home-assistant.io/integrations/binary_sensor.mqtt/"
            payload["name"] = name
        case 'blind':
            platform = 'cover'
            try:
                payload["position_open"] = entity['position_open']
            except:
                payload["position_open"] = 10000
            try:
                payload["position_closed"] = entity['position_closed']
            except:
                payload["position_closed"] = 0
            #payload["state_topic"] = deviceTopic + '/state'        # A cover entity can be in states (open, opening, closed or closing).
            payload["command_topic"] = deviceTopic + '/set'
            payload["position_topic"] = deviceTopic + '/position'   # If a position_topic is set, the cover’s position will be used to set the state to either open or closed state
            payload["set_position_topic"] = deviceTopic + '/set_position'
            payload_origin["url"] = "https://www.home-assistant.io/integrations/cover.mqtt/"
            payload["name"] = name
        case 'camera':
            platform = 'camera'
            #payload["image_encoding"] = "b64"
            payload["topic"] = f"{baseTopic}-camera/{key}/image"
            payload_origin["url"] = "https://www.home-assistant.io/integrations/camera.mqtt/"
            payload["name"] = name


    discovery_topic = f"homeassistant/{platform}/{key}/rtek/config"
    payload["default_entity_id"] = f"{platform}.rtek_{entity_type}_{label.lower()}"
    discovery_payload = json.dumps(payload)
    return [discovery_topic, discovery_payload, 0, True]


