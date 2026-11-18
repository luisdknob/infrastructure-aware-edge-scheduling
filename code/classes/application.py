import bitmath
from uuid import uuid1 as uuid

DOWNLOADING = 0
RUNNING = 0
WAITING = 1
TERMINATED = 2

class Application:
    def __init__(self, name=None, arrivalTime=None, numReplicas=None, scheduler=None, schedulerPolicy=None, cpuRequired=None, memoryRequired=None, image=None, tag=None, lifeTime=None, labels=None):
        """
        """
        self.id = uuid().int
        self.name = name
        self.arrivalTime = arrivalTime
        self.lifeTime = lifeTime
        self.scheduler = scheduler
        self.schedulerPolicy = schedulerPolicy
        self.cpuRequired = cpuRequired
        self.memoryRequired = bitmath.parse_string(memoryRequired)
        self.image = image
        self.tag = tag
        self.numReplicas = numReplicas
        self.replicas = []
        self.labels = labels

    def create_message(self):
        print(self.scheduler)

class Replica:
    def __init__(self, **attr):
        self.id = uuid().int
        self.node = None
        self.messages = []
        self.version = None
        self.status = DOWNLOADING # TODO
        self.log = [] # dict('event'='time')

        for var, value in attr.items():
            if var in self.__dict__:
                self.__setattr__(var, value)

    def add_log(self, event, time):
        self.log.append(dict(event=event, time=time))

class Layer:

    def __init__(self, size, digest=uuid().int):
        self.digest = digest
        self.size = bitmath.parse_string(size)
    
    def sizeInBits(self):
        return self.size.to_Bit()

class Image:

    def __init__(self, **attr):
        self.digest = uuid().int
        self.name = ""
        self.versions = []
        self.startDelay = 0
        self.stopDelay = 0
        for var, value in attr.items():
            if var in self.__dict__:
                if var == "memory":
                    bitmath.parse_string(value)
                self.__setattr__(var, value)

class ImageVersion:

    def __init__(self, tag, layers, digest=uuid().int):
        self.digest = digest
        self.tag = tag
        self.layers = layers