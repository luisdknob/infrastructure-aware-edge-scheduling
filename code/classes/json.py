import logging as log
import jsonschema
import random
import sys
import json
import bitmath

from uuid import uuid1 as uuid
from datetime import datetime
from collections import namedtuple

import classes.application as ca
import classes.infrastructure as ct

def create_node(template):
    node = template.copy()

    node["id"] = uuid().int
    node["layers"] = [] # cache layers
    node["scheduledApplications"] = [] # scheduled application

    if "position" in template.keys():
        node["position"] = (node["position"][0],node["position"][1])

    if "storageCapacity" in template.keys():
        node["storageCapacity"] = bitmath.parse_string(template["storageCapacity"])
    else:
        node["storageCapacity"] = bitmath.Byte(0)

    if "simultaneousDownload" in template.keys():
        node["simultaneousDownload"] = template["simultaneousDownload"]

    if template["type"] == "chost":

        node["storageUsed"] = 0

        if "memoryCapacity" in template.keys():
            node["memoryCapacity"] = bitmath.parse_string(template["memoryCapacity"])
            node["memoryUsed"] = bitmath.Byte(0)
        else:
            log.warn("Memory capacity has not been set for node. Using default value.")
            node["memoryCapacity"] = bitmath.GB(16)

        if "cpuCapacity" in template.keys():
            node["cpuCapacity"] = template["cpuCapacity"]
            node["cpuUsed"] = 0
        else:
            log.warn("CPU capacity has not been set for node. Using default value.")
            node["cpuCapacity"] = 4000 # considering milicores

    # TODO Could bandwidth be a attribute of node in JSON ?
    if "labels" in template:
        # if "bandwidth" in template['labels'].values():
        if any(label['key'] == 'bandwidth' for label in template['labels']):
            node["bandwidth"] = [label for label in template['labels'] if label['key'] == 'bandwidth'][0]['value']

    node["log"] = {"cache":[0,0]} # [cache hit, cache miss]

    node["rate"] = bitmath.Bit(0)

    return node

def create_edge(edge, nodes):
    edges = []

    try:
        edge["from"] = next(map(lambda x: x["id"], filter(lambda x:x["name"] == edge["from"], nodes)))
        edge["to"] = next(map(lambda x: x["id"], filter(lambda x:x["name"] == edge["to"], nodes)))
    except Exception as e:
        log.error(f"Corrupted JSON - error {e}")
        sys.exit(1)

    if "latency" not in edge.keys():
        edge["latency"] = 1

    edges.append((edge["from"],
                       edge['to'],
                       {"id":uuid().int, "bandwidth":bitmath.parse_string(edge['bandwidth']), "latency":edge["latency"], "activeMessages":[]}))
    if "bidirectional" in edge.keys():
        edges.append((edge['to'],
                           edge["from"],
                           {"id":uuid().int, "bandwidth":bitmath.parse_string(edge['bandwidth']), "latency":edge["latency"], "activeMessages":[]}))
    return edges

def create_message(template):

    message = ct.Message(size=template['size'], name=template['name'])
    if "src" in template:
        message.src = template['src']
    if "dst" in template:
        message.dst = template['dst']
    if "start" in template:
        message.arrival_time = template['start']
    if "dependencies" in template:
        message.dependencies = template['dependencies']
    if "deadline" in template:
        message.deadline_time = template['deadline']
    if "layer" in template:
        message.layer = template['layer']
    if "chain" in template:
        message.chain = template['chain']

    return message

def extract_node_from_JSON(JSONFile):
    nodes = []
    edges = []

    for nodeJSON in JSONFile["nodes"]:
        nodes.append(create_node(nodeJSON))

        # if "networkInterface" in nodeJSON.keys():
        #     if len(nodeJSON["networkInterface"]) == 1:
        #         if nodeJSON["networkInterface"][0]["connectedto"] == "random" :
                    
        #             dst = random.choice(list(filter(lambda x: x['type'] == "netabs", nodes)))["name"]
        #             log.debug("Connect node %s to %s" % (nodeJSON["name"], dst))
        #             nodeJSON["networkInterface"][0]["connectedto"] = dst
        #             nodeJSON["networkInterface"][0]["bidirectional"] = True
            
        #     for interface in nodeJSON["networkInterface"]:
        #         interface["hostId"] = node["id"]
        #         interfaces.append(interface)
            

    for edge in JSONFile["edges"]:
        edges.extend(create_edge(edge, nodes))

    return nodes, edges

def configuration_from_JSON(JSONFile):
    nodes = []
    edges = []
    layers = []
    images = []
    operations = []
    applications = []
    options = []

    #process JSON file

    #first process container layers
    if "layers" in JSONFile:

        # for layer in JSONFile["layers"]:
        for layer in [dict(t) for t in {tuple(d.items()) for d in JSONFile["layers"]}]: # remove duplicates
            layers.append(ca.Layer(**layer))

    # after process images with all layers
    if "images" in JSONFile:
        
        for image in JSONFile["images"]:
            versions = image["versions"]
            versionObjs = list()
            for version in versions:
                version["layers"] = list(filter(lambda x: (x.digest in version["layers"]), layers))
                versionObjs.append(ca.ImageVersion(**version))
            image["versions"] = versionObjs
            images.append(ca.Image(**image))
    
    # at last, process applications
    if "applications" in JSONFile:

        for application in JSONFile["applications"]:
            
            # found image already load on simulation
            tag = application["image"].split(":")[0]
            application["image"] = next(filter(lambda x: (x.name == tag), images))
            
            # TO-DO: Do the same with schedulers and labels

            applications.append(ca.Application(**application))

    if "lifecyleOperations" in JSONFile:

        for operation in JSONFile["lifecyleOperations"]:
            operation["application"] = next(filter(lambda x:x.name == operation["application"], applications))
            operations.append(operation)

    if "nodes" in JSONFile:

        nodes, edges = extract_node_from_JSON(JSONFile)

    if "infrastructure" in JSONFile:

        options = JSONFile["infrastructure"]

    return nodes, edges, images, applications, operations, options

def validate_schema(JSONFile):

    schema = {
        "type": "object",
        "properties": {
            "application": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "image": {"type": "string"},
                    "numReplicas": {"type": "number"},
                    "scheduler": {"type": "string"},
                    "schedulerPolicy": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "value": {"type": ["string", "number"]}
                            }
                        }
                    },
                    "runningActions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string"},
                                "dst": {"type": "string"},
                                "size": {"type": "number"},
                                "interval": {"type": "number"}
                            }
                        }
                    },
                    "labels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"}
                            }
                        }
                    }  
                },
                "required": ["name", "image", "numReplicas"]
            },
            "node": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "storageCapacity": {"type": "string"},
                    "simultaneousDownload": {"type": "number"},
                    "networkInterface": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "bandwidth": {"type": "string"},
                                "connectedto": {"type": "string"},
                                "bidirectional": {"type": "boolean"}
                            }
                        }
                    },
                    "registry": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "position": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "long": {"type": "string"},
                                "lat": {"type": "string"},
                                "region": {"type": "boolean"}
                            }
                        }
                    }
                }
            },
            "image": {
                "name": {"type": "string"},
                "cpu": {"type": "decimal"},
                "memory": {"type": "string"},
                "startDelay": {"type": "decimal"},    
                "versions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tag": {"type": "string"},
                            "digest": {"type": "string"},
                            "layers": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            }
                        }
                    }
                }
            },
            "layer": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "size": {"type": "string"},
                        "digest": {"type": "string"}
                    }
                }
            }
        }
    }

    try:
        # TODO Fix it.
        jsonschema.validate(instance=JSONFile, schema=schema)

    except jsonschema.exceptions.ValidationError as err:
        log.error(err)
        return False
    return True
