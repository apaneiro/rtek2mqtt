import os
import json
import asyncio
import aiomqtt


##########################################################
def mqtt_device_topic(baseTopic, type, key):
##########################################################
    return f"{baseTopic}/{type}/{key}"

##########################################################
def mqtt_discovery(baseTopic, type, key, config_entry):
##########################################################
    position_closed = 0
    position_open = 100
    platform = ''

    name = config_entry['name']
    label = config_entry['label']

    payload = dict()
    payload_device = dict()
    payload_origin = dict()

#    payload_device["hw_version"] = "1"
    payload_device["identifiers"] = [ str(key) ]
    payload_device["manufacturer"] = "RTEK"
    payload_device["model"] = type.capitalize()
#    payload_device["model_id"] = f"R{type}"
#    payload_device["name"] = "RTEK " + type.capitalize() + " " + name
    payload_device["name"] = label.upper() + " - " + name
    try:
        payload_device["suggested_area"] = config_entry['area']
    except:
        pass
#    payload_device["suggested_label"] = f"RTEK {type}"

    payload_origin["name"] = "rtek_addon"
#    payload_origin["sw"] = "1.0"

    payload["object_id"] = f"rtek_{type}_{label}"

    payload['availability_topic'] = baseTopic + "/server/available"
    payload['device'] = payload_device
    payload['origin'] = payload_origin
    payload["unique_id"] = f"rtek_{type}_{label}"

    deviceTopic = mqtt_device_topic(baseTopic, type, key)
    match type:
        case 'light':
            platform = 'light'
            try:
                payload["icon"] = 'mdi:' + config_entry['icon']
            except:
                pass
            payload["state_topic"] = deviceTopic + "/state"
            payload["command_topic"] = deviceTopic + "/set"
            payload_origin["url"] = "https://www.home-assistant.io/integrations/light.mqtt/"
            payload["name"] = 'Light'
        case 'sensor':
            platform = 'binary_sensor'
            try:
                payload["device_class"] = config_entry['class']
            except:
                pass
            payload["state_topic"] = deviceTopic + "/state"
            payload_origin["url"] = "https://www.home-assistant.io/integrations/binary_sensor.mqtt/"
        case 'blind':
            platform = 'cover'
            try:
                payload["position_open"] = config_entry['position_open']
            except:
                payload["position_open"] = 10000
            try:
                payload["position_closed"] = config_entry['position_closed']
            except:
                payload["position_closed"] = 0
#            payload["state_topic"] = deviceTopic + '/state'        # A cover entity can be in states (open, opening, closed or closing).
            payload["command_topic"] = deviceTopic + '/set'
            payload["position_topic"] = deviceTopic + '/position'   # If a position_topic is set, the cover’s position will be used to set the state to either open or closed state
            payload["set_position_topic"] = deviceTopic + '/set_position'
            payload_origin["url"] = "https://www.home-assistant.io/integrations/cover.mqtt/"
            payload["name"] = 'Blind'
        case 'speaker':
            platform = 'device_automation'
            payload["automation_type"] = 'trigger'
            payload["type"] = 'button_short_press'
            payload["subtype"] = config_entry['subtype']
            payload["topic"] = deviceTopic + "/state"
            payload["payload"] = 'ON'
            payload_origin["url"] = "https://www.home-assistant.io/integrations/device_trigger.mqtt/"

    discovery_payload = json.dumps(payload)
    discovery_topic = f"homeassistant/{platform}/{key}/rtek/config"

    return [discovery_topic, discovery_payload, 0, True]

##########################################################
async def mqtt_listen(debug, client, rtekTxQueue):
##########################################################
    try:
        async for message in client.messages:
            array = str(message.topic).split('/')
            type = array[1]
            key = int(array[2])
            state = array[3]
            value = str(message.payload.decode())

            if (debug > 0):
                print (f'---> MQTT received: type: {type}, key: {key}, state: {state}, value: {value}')
            match type:
                case 'light':
                    if state == 'set':
                        hex_key = "%0.4x" % key
                        hex_value = '01' if value == 'ON' else '00'
                        packet = f'fa 02 00 48 00 00 00 09 00 00 {hex_key} 00 00 00 {hex_value} ab'

                        rtekTxQueue.put_nowait(packet)
                    else:
                        pass
                case 'blind':
                    if state == 'set':
                        hex_value = '00'    # STOP
                        hex_key = "%0.4x" % key
                        match value:
                            case 'OPEN':
                                hex_value = '01'
                            case 'CLOSE':
                                hex_value = '02'
                        packet = f'fa 02 00 48 00 00 00 09 00 00 {hex_key} 00 00 00 {hex_value} ab'

                        print (value, '    ', packet)

                        rtekTxQueue.put_nowait(packet)

                    elif state == 'set_position':
                        hex_key = "%0.4x" % (key + 2)
                        position = int(value)
                        hex_position = "%0.4x" % position
                        packet = f'fa 02 00 48 00 00 00 09 00 00 {hex_key} 00 00 {hex_position} ab'

                        print (position, '    ', packet)

                        rtekTxQueue.put_nowait(packet)

    except asyncio.CancelledError:
        pass
    except aiomqtt.MqttError:
        pass

##########################################################
async def mqtt_publish(debug, client, mqttTxQueue):
##########################################################
    try:
        while True:
            msg = await mqttTxQueue.get()
            await client.publish(msg[0], payload=msg[1], qos=msg[2], retain=msg[3])
            if (debug > 1):
                print(f'---> MQTT published: topic = {msg[0]}  payload = {msg[1]}')

    except asyncio.CancelledError:
        pass
    except aiomqtt.MqttError:
        pass

##########################################################
async def start_mqtt(config, rtekTxQueue, mqttTxQueue):
##########################################################
    reconnect_interval = 10

    subscribeTopic = config['mqttBaseTopic'] + "/+/+/+"
    availableTopic = config['mqttBaseTopic'] + "/server/available"
    debug = config['debug']
    # mqttHost = config['mqttHost']
    # mqttPort = config['mqttPort']
    # mqttUser = config['mqttUser']
    # mqttPassword =config['mqttPassword']
    mqttHost = os.environ["MQTTHOST"]
    mqttPort = int(os.environ["MQTTPORT"])
    mqttUser = os.environ["MQTTUSER"]
    mqttPassword = os.environ["MQTTPASSWORD"]

    while True:
        tasks = set()
        try:
            will = aiomqtt.Will(availableTopic, "offline", 2, True)
            async with aiomqtt.Client(mqttHost, mqttPort,
                    username = mqttUser, password = mqttPassword, will = will) as client:
                mqttTxQueue.put_nowait([availableTopic, "online", 2, True])
                await client.subscribe(subscribeTopic)
                print('---> Connected to MQTT server')

                async with asyncio.TaskGroup() as tg:
                    tasks.add(tg.create_task(mqtt_listen(debug, client, rtekTxQueue)))
                    tasks.add(tg.create_task(mqtt_publish(debug, client, mqttTxQueue)))

        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            break
        except aiomqtt.MqttError as error:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks)
            print(f'---> ERROR {error}: Reconnecting to MQTT in {reconnect_interval} seconds.')

            await asyncio.sleep(reconnect_interval)

