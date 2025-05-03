##########################################################
class Device():
##########################################################
    def __init__(self, key, item = dict(), topic=''):
        self.__key = key
        self.__label = item['label']
        self.__name = item['name']
        self.__area = item['area']
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
class Light(Device):
##########################################################
    def __init__(self, key, item = dict(), topic=''):
        super().__init__(key, item, topic)
        self.__state = -1

    @property
    def state(self):
        return self.__state

    @state.setter
    def state(self, value):
        self.__state = value

class Sensor(Device):
    def __init__(self, key, item = dict(), topic=''):
        super().__init__(key, item, topic)
        self.__class = item['class']
        self.__state = -1

    @property
    def state(self):
        return self.__state

    @state.setter
    def state(self, value):
        self.__state = value

    @property
    def device_class(self):
        return self.__device_class

##########################################################
class Blind(Device):
##########################################################
    def __init__(self, key, item = dict(), topic=''):
        super().__init__(key, item, topic)
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
    def __init__(self, key, item = dict(), topic=''):
        super().__init__(key, item, topic)
