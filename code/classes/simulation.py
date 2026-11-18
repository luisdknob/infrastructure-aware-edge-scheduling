import sys
import logging as log

import classes.infrastructure as ct
import classes.application as ca
import classes.scheduler as sch

class Simulation:

    def __init__(self, **options):
        self.infrastructure = None
        self.images = None
        self.cachedStartOperations = []
        self.scheduler = None
        for var, value in options.items():
            if var == "logLevel":
                    log.getLogger().setLevel(value)
            elif var == "scheduler":
                if "config" in value:
                    exec(f'self.scheduler = sch.{value["name"]}(config={value["config"]})')
                else:
                    exec(f'self.scheduler = sch.{value["name"]}()')
            elif var in self.__dict__:
                self.__setattr__(var, value)     

    def add_infrastructure(self, infrastructure):
        self.infrastructure = infrastructure

    def add_applications(self, applications, operations):
        self.applications = applications
        for operation in operations:
            if operation["type"] == "creation":
                self.cachedStartOperations.append((operation["time"],operation))
        self.cachedStartOperations = sorted(self.cachedStartOperations, key=lambda x: x[0])

    def add_images(self, images):
        self.images = images
        
    def run_simulation(self):

        sec = 0

        while True:
            self.infrastructure.add_messages(self.create_messages_from_applications(sec))

            next_lifecycle_time = min(self.cachedStartOperations, key=lambda x: x[0], default=None)
            next_lifecycle_time = next_lifecycle_time[1]["time"] if next_lifecycle_time else None

            #print(sec, next_lifecycle_time)
            sec = self.infrastructure.run_network_simulation(sec, next_lifecycle_time)

            if len(self.cachedStartOperations) == 0:
                break

        return sec

    def create_messages_from_applications(self, sec):    
        
        messages = []
        remove_from_cache = []
        for operation in filter(lambda x: x[0] == sec, self.cachedStartOperations):
            time, op = operation

            if op["name"] == "deployment":
            
                for x in range(op['numReplicas']):
                    
                    replicaMessages = []
                    
                    # select the configured scheduler for the application
                    src, dst = self.scheduler \
                        .place(application_to_schedule=op["application"], images=self.images, topology=self.infrastructure.topology)

                    for layer in op["application"].image.versions[0].layers:
                        replicaMessages.append(ct.Message(src=src, dst=dst, name=op["application"].name+"-"+str(x)+"-"+op["application"].image.name+"-"+op["application"].image.versions[0].tag+"-"+layer.digest, arrival_time = time, size = layer.size, layer=layer.digest))

                    replica_name = op["application"].name+"-"+str(x)+"-"+op["application"].image.name+"-"+op["application"].image.versions[0].tag                   
                    log.debug(f"Scheduling replica {replica_name} to the node {dst} using {type(self.scheduler).__name__}")

                    replica = ca.Replica(name=replica_name, node=dst, messages=replicaMessages, version=op["application"].image.versions[0]) # TODO get correct version
                    op["application"].replicas.append(replica)
                    messages.extend(replicaMessages)

                    # TODO Set node cpu and memory utilization
                    self.update_node_resource_utilization(dst, op["application"])
            
                remove_from_cache.append(operation)

            # TODO
            # if op["name"] == "destroy":
            #    Remove application from nodes
        
        for i in remove_from_cache:
            self.cachedStartOperations.remove(i)

        return messages

    def update_node_resource_utilization(self, node_id, application):
        
        if self.infrastructure.topology.nodes[node_id]["cpuUsed"] + application.cpuRequired and \
            self.infrastructure.topology.nodes[node_id]["memoryUsed"] + application.memoryRequired:
            
            self.infrastructure.topology.nodes[node_id]["cpuUsed"] += application.cpuRequired
            self.infrastructure.topology.nodes[node_id]["memoryUsed"] += application.memoryRequired
            # self.infrastructure.topology.nodes[node_id]["storageUsed"] += application.storageRequired TODO

            self.infrastructure.topology.nodes[node_id]["scheduledApplications"] += [application]
        
        else:
            raise Exception(f"Node {node_id} has not enough resources!")