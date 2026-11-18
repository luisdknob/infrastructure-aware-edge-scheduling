from uuid import uuid1 as uuid

import networkx as nx
import logging as log
import json
import time
import sys
import random
import bitmath

import classes.application as ca

def map_hosts(x):
    x[1]["id"] = x[0]
    return x[1]

class Node:

    @staticmethod
    def get_all_chosts(topology):
        return list(map(map_hosts, filter(lambda x: x[1]['type'] == 'chost', topology.nodes(data=True))))

    @staticmethod
    def update_rate_nodes(chosts, messages, rates):
        messages = [message for message in messages["active"] if message.id in rates]
        for chost in chosts:
            chost['rate'] = bitmath.Bit(0)
            for message in messages:
                if message.dst == chost['id']:
                    chost['rate'] += bitmath.Bit(rates[message.id])

    # TODO: Implement layer control on registry
    @staticmethod
    def get_registry(node, topo):
        chose_registry = (None, sys.maxsize)
        for registry in topo.nodes[node]["registry"]:
            registry = next(filter(lambda d: d[1]['name'] == registry, topo.nodes(data=True)))
            cost = nx.shortest_path_length(topo, registry[0], node, lambda v,u,e: 1/e["bandwidth"].to_Bit())
            if chose_registry[1] > cost:
                chose_registry = (registry[0], cost)

        return chose_registry[0]

    @staticmethod
    def control_cache(node, topology, layer, size, time):
        node = topology.nodes[node]

        if node["storageCapacity"] == 0.0:
            node["log"]["cache"][1] += 1
            return
        
        if bitmath.Mb(sum([layer[1] for layer in node["layers"]])+size) > node["storageCapacity"] or any(layer == i[0] for i in node["layers"]):
            old = ("", bitmath.Byte(0), time)
            for cont in node["layers"]:
                if cont[0] == layer:
                    cont = (layer, size, time)
                    node["log"]["cache"][0] += 1
                    return
                if old[2] > cont[2]:
                    old = (cont[0], cont[1], cont[2])
            
            log.debug("ST: %02.2f - Remove layer %s from node %s because the cache is full" % (time, old[0], node["name"]))
            try:
                node["layers"].remove(old)
            except:
                print(node["layers"], old, any(layer in i for i in node["layers"]), sum([layer[1] for layer in node["layers"]])+size, node["storageCapacity"])
        
        log.debug("ST: %02.2f - Add layer %s on node %s cache" % (time, layer, node["name"]))
        node["layers"].append((layer, size, time))
        node["log"]["cache"][1] += 1

class LCOperationsSchedule:

    @staticmethod
    def max_bandwidth_schedule(messages, topo):
        ordered_messages = messages.copy()
        for message in ordered_messages:
            path_max_bandwidth = 0
            for num, node in enumerate(message.path[:-1]):
                path_max_bandwidth = max(path_max_bandwidth, topo[node][message.path[num+1]]["bandwidth"])
            message.max_bandwidth = path_max_bandwidth
        return sorted(ordered_messages, key=lambda item: item.max_bandwidth, reverse=True)

    @staticmethod
    def common_path_schedule(messages):
        nodes = {}
        ordered_messages = messages.copy()

        for message in ordered_messages:
            for node in message.path:
                if node in nodes.keys():
                    for dep in nodes[node]:
                        if dep not in message.dependencies:
                            message.dependencies.append(dep)
                    nodes[node].append(message.name+"-"+str(message.id))
                else:
                    nodes[node] = []
            print(message.name,message.dependencies)
                    
        return ordered_messages

class Message:

    def __init__(self, **attr):
        self.id = uuid().int
        self.src = None
        self.dst = None
        self.name = ""
        self.arrival_time = 0
        self.deadline_time = sys.maxsize
        self.size = bitmath.Byte(0)
        self.layer = ""
        self.transmitted = bitmath.Bit(0)
        self.dependencies = []
        
        """ 
        message status

        0 - schedule message
        1 - cached message
        2 - error message
        3 - active message
        4 - contained message
        5 - downloaded message 
        """

        self.status = 0
        self.type = "host"
        for var, value in attr.items():
            if var in self.__dict__:
                self.__setattr__(var, value)
        if attr.get("topo"):
            self.calculate_path(attr.get("topo"))

    def data_to_transmit(self):
        return self.size - self.transmitted

    def transfer_data(self, value):
        if self.transmitted + value > self.size:
            self.transmitted = self.size
        else:
            self.transmitted += value

    def calculate_path(self, infra):
        self.path = infra.connection_path(self.src,self.dst)
        if not self.path:
            return False
        return True
class Infrastructure:

    def __init__(self, nodes, edges):
        self.topology = nx.DiGraph()

        self.messages = {
                            "schedule":[],
                            "active":[],
                            "retained":[],
                            "installed":[],
                            "error":[]
                        }

        self.log =  {
                        "netstat":[]
                    }

        self.recalculate_network = False

        for node in nodes:
            id = node["id"]
            node.pop("id")
            self.topology.add_node(id,**node)
        
        for src,dst,data in edges:
            self.topology.add_edge(src,dst,**data)

    def update_nodes(self):
        pass

    def run_network_simulation(self, sec, time_limit):

        while len(self.messages["schedule"]):
            self.running_messages(sec)

            sec += self.calculate_network_traffic(sec, time_limit)

            self.finish_messages(sec)

            # self.update_nodes()

            if time_limit:        
                if sec == time_limit:
                    break

        if time_limit:
            return time_limit
        else:
            return sec

    def connection_path(self, src, dst):
        return nx.shortest_path(self.topology,src,dst,weight="bandwidth")

    def add_messages(self, messages):
        self.messages["schedule"].extend(messages)
        self.messages["schedule"] = sorted(self.messages["schedule"], key=lambda x: x.arrival_time)

        for message in self.messages["schedule"]:
            message.calculate_path(self)

    def scheduling_messages(self, policy):
        if policy == "smallfirst":
            self.messages["schedule"] = sorted(self.messages["schedule"], key=lambda item: item.size)
        elif policy == "largefirst":
            self.messages["schedule"] = sorted(self.messages["schedule"], key=lambda item: item.size, reverse=True)
        elif policy == "largebandwidth":
            self.messages["schedule"] = LCOperationsSchedule.max_bandwidth_schedule(self.messages["schedule"], self.topology)
        elif policy == "commonpath":
            self.messages["schedule"] = LCOperationsSchedule.common_path_schedule(self.messages["schedule"])
        
    def running_messages(self, sec):

        # for each new sim time, run on each message that not be installed or failed

        for message in self.messages["schedule"]:
    

            # if message arrival time bigger than the actual sim time, break the loop

            if message.arrival_time <= sec:

            
                #if message deadline smaller than the sim time, message failed and removed from the schedule list

                if message.deadline_time <= sec:
                    message.status = 2
                    message.start_time = sec
                    message.finish_time = sec
                    self.messages["error"].append(message)
                    self.messages["schedule"].remove(message)
                    log.info("ST: %.2f - Message %s-%d can't be installed because the deadline is smaller than the current time"% (sec, message.name, message.id%100000000))
                    continue

                    # TODO Remove node resource utilization

                # if the same image to the same host are already active put the message on retained and continue

                if any(message.layer == i.layer and message.dst == i.dst for i in self.messages["active"]):
                    if not message in self.messages["retained"]:
                        self.messages["retained"].append(message)
                    continue

                # if message is already installed on the node, set as installed

                if any(message.layer == i[0] for i in self.topology.nodes[message.dst]["layers"]):
                    message.start_time = sec                    
                    message.finish_time = sec
                    self.messages["installed"].append(message)
                    self.messages["schedule"].remove(message)
                    Node.control_cache(message.dst, self.topology, message.layer, message.size, sec)
                    message.status = 1
                    log.debug("ST: %.2f - Message %s-%d download already made, so auto-start"% (sec, message.name, message.id%100000000))
                    if message in self.messages["retained"]:
                        self.messages["retained"].remove(message)
                    continue

                # calculate the number of active messages to a given host

                retained_simultaneous_download = len([True for m in self.messages["active"] if m.dst == message.dst])

                # if number of active messages on node less than the simultaneousDownload test if message has dependencies, if not, start
                # TO-DO Improve dependencies implementation

                if retained_simultaneous_download < self.topology.nodes(data="simultaneousDownload", default=1)[message.dst]:
                    if len(message.dependencies) > 0:
                        if not all([True if m.name == dep or m.name+"-"+str(m.id) == dep else False for m in self.messages["schedule"] for dep in message.dependencies]):
                            if not message in self.messages["retained"]:
                                self.messages["retained"].append(message)
                            continue
                    self.recalculate_network = True
                    if message in self.messages["retained"]:
                        self.messages["retained"].remove(message)
                    log.info("ST: %.2f - Message %s-%d started transfer from %s to %s (schedule waiting time - %.2f)" % (sec, message.name, message.id%100000000, self.topology.nodes[message.src]["name"], self.topology.nodes[message.dst]["name"], sec-message.arrival_time))
                    message.start_time = sec
                    self.messages["active"].append(message)
                else:
                    if not message in self.messages["retained"]:
                        self.messages["retained"].append(message)
            else:
                break    

    def calculate_network_traffic(self, sec, time_limit):

        # calculate minimal arrival time from schedule messages.

        min_arrival_time_waiting = next(iter(sorted(list(set(self.messages["schedule"])-set(self.messages["retained"])-set(self.messages["active"])), key=lambda x: x.arrival_time)), None)

        # if no active messages, add minimal arrival time or 0.0 to time

        if len(self.messages["active"]) == 0:
            return min_arrival_time_waiting.arrival_time-sec if min_arrival_time_waiting else 0.0

        # if necessary recalculate Maxmin Fairness

        if self.recalculate_network:

            sA = []
            C = {}
            sP = []
            links = []

            for message in self.messages["active"]:
                for index, node in enumerate(message.path[:-1]):
                        arc = self.topology[node][message.path[index+1]]
                        links.append((message.id, arc["id"]))
                        if arc["id"] not in sA:
                            sA.append(arc["id"])
                            C[arc["id"]] = float(arc["bandwidth"].to_Bit())
                sP.append(message.id)

            self.rates = self.__maxmin_fairness(sP, sA, C, links)

            self.recalculate_network = False
            self.log["netstat"].append({"sec":sec, "rates":self.rates, "messages":[ { "id":m.id, "name":m.name, "path":m.path } for m in self.messages["active"] ]})

            chosts = Node().get_all_chosts(self.topology)
            Node().update_rate_nodes(chosts, self.messages, self.rates)

        # set min_arrival_time for next message

        min_arrival_time_waiting = min_arrival_time_waiting.arrival_time-sec if min_arrival_time_waiting else sys.maxsize

        # calculate who is the first flow will finish the transmition with a given rates

        next_finish_message = min([ message.data_to_transmit()/bitmath.Bit(self.rates[message.id]) for message in self.messages["active"] ], default=sys.maxsize)

        # set the minimum deadline time to active messages

        min_deadline_time = next(iter(sorted(self.messages["active"], key=lambda x: x.deadline_time)), None)
        min_deadline_time = min_deadline_time.deadline_time-sec if min_deadline_time else sys.maxsize

        time_limit = time_limit-sec if time_limit else None

        # discover which value is small between minimum deadline, minimal arrival time and finish flow
        time_spend_cycle = min(filter(None.__ne__, [next_finish_message, min_arrival_time_waiting, min_deadline_time, time_limit]))
        # after discover the minimum time spend on cycle, update all flows with the data transmitted

        for id, value in self.rates.items():
            for message in self.messages["active"]:
                if message.id == id:
                    message.transfer_data(bitmath.Bit(value)*time_spend_cycle)
                    break
        
        return time_spend_cycle

    def finish_messages(self, sec):
        new_active = []
        for message in self.messages["active"]:     
            if message.transmitted >= message.size:
                Node.control_cache(message.dst, self.topology, message.layer, message.size, sec)
                self.recalculate_network = True
                message.finish_time = sec
                log.info("ST: %02.2f - Message %s-%d transfer %.2f Mbytes from %s to %s and last %.2f seconds" 
                        % (sec, message.name, message.id%100000000, message.size.to_MB(), self.topology.nodes[message.src]["name"], self.topology.nodes[message.dst]["name"], sec-message.start_time))
                
                message.status = 5 # downloaded image
                self.messages["installed"].append(message)
                self.messages["schedule"].remove(message)

            elif message.deadline_time <= sec:
                self.recalculate_network = True
                message.finish_time = sec
                log.info("ST: %02.2f - Message %s-%d transfer %.2f Mbytes from %s to %s and last %.2f seconds but don't finish the installation because deadline was smaller than simulation time" 
                        % (sec, message.name, message.id%100000000, message.transmitted.to_MB(), self.topology.nodes[message.src]["name"], self.topology.nodes[message.dst]["name"], sec-message.start_time))
                
                message.status = 2
                self.messages["error"].append(message)
                self.messages["schedule"].remove(message)

                # TODO Remove node resource utilization
      
            else:
                new_active.append(message)
        self.messages["active"] = new_active             

    def __maxmin_fairness(self, sP, sA, C, links):
        # sP - list of transfers
        # sA - list of arcs
        # C - dictionary with capacities of each arc
        # links - list of tuples, each tuple (i,j) indicates that transfer i uses arc j

        # k -> step
        k = 1 # initiated at 1

        # A[k] -> set of non saturated arcs at the beginning of step k
        A = dict([(k,sA)])

        # P[k] -> set of sessions not passing through any saturated arc at the beginning of step k
        P = dict([(k,sP)])

        # n[k][a] -> number of sessions using arc a that are in P[k]
        n = dict()

        # rt[k] -> increment of rate added to all session in P[k]
        rt = dict()

        # r[k][p] -> allocated rate on session p at step k
        r = dict([ ((0,p),0) for p in sP])

        # F[k][a] = allocated flow on arc a at step k
        F = dict([ ((0,a),0) for a in sA])

        # delta[p][a] = matrix where [p][a] = 1 if arc is in path p, 0 otherwise
        delta = dict([ ((p,a),0) for p in sP for a in sA ])
        delta.update( dict([ (l,1) for l in links ]) )

        while(len(P[k]) != 0) :

            # 1. n[k][a] := number of paths p in P[k] with delta[p][a] = 1
            n.update( dict([ ((k,a),len([ p for p in P[k] if delta[p,a] == 1 ])) for a in sA ]) )

            # 2. rt[k] := min( (C[a]-F[k-1][a])/n[k][a] forall a in A[k] and n[k][a] > 0)
            rt[k] = min([ float(C[a]-F[k-1,a])/n[k,a] for a in A[k] if n[k,a] > 0 ])

            # 3. r[k][p] := if p in P[k], then r[k-1][p] + rt[k] else r[k-1][p]
            r.update( dict([ ((k,p), r[k-1,p]+(lambda x: (x in P[k] and rt[k]) or 0)(p)) for p in sP]))

            # 4. F[k][a] := sum{p in P} delta[p][a] * r[k][p]
            F.update( dict([ ((k,a),sum([ delta[p,a]*r[k,p] for p in sP ])) for a in sA ]) )
            
            # 5. A[k+1] := {a|C[a]-F[k][a] > 0}
            A[k+1] = [ a for a in sA if C[a]-F[k,a] > 0 ]

            # 6. P[k+1] := {p|delta[p][a] = 0, forall a notin A[k+1]}
            saturated_links = [ (p,all( [delta[p,a] == 0 for a in sA if a not in A[k+1]] )) for p in sP]
            P[k+1] = [ p for (p,cond) in saturated_links if cond ]

            # 7. k := k+1
            k = k+1

            # 8. if P[k] is empty, then stop, else goto 1
        
        return dict([ (p,r[k-1,p]) for p in sP ])
