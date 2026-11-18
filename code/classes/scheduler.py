from abc import ABC, abstractmethod
import classes.infrastructure as ct

import logging as log
import bitmath
import random
import sys


class Scheduler(ABC):

    @abstractmethod
    def place(self):
        pass


class KubeScheduler(Scheduler):

    def __init__(self, **options):
        super().__init__()

        self.predicates = {
            "PodFitsResources": self._pod_fits_resources,
            "PodAntiAffinity": self._pod_anti_affinity,
            "MatchNodeSelector": self._match_node_selector
            # "PodToleratesNodeTaints": self._pod_tolerates_node_taints
        }

        self.priorities = {
            "InterPodAffinityPriority": self._inter_pod_affinity_priority,
            "LeastRequestedPriority": self._least_requested_priority,
            "LeastCongestedNodePriority": self._least_congested_node_priority,
            "SelectorSpreadPriority": self._selector_spread_priority,
            "ImageLocalityPriority": self._image_locality_priority,
            "LayerLocalityPriority": self._layer_locality_priority,
        }

        self.config = options.get("config")

    def _get_application_layers(self, application):
        # TODO versions[0]
        return [layer.digest for layer in application.image.versions[0].layers]

    def _inter_pod_affinity_priority(self, application, chosts, weight):

        pod_affinity = None

        for label in application.labels:
            if "podAffinity" == label["key"]:
                pod_affinity = [label for label in application.labels if label["key"] == "podAffinity"][0]["value"]

        if (pod_affinity):
            for chost in chosts:
                for app in chost["scheduledApplications"]:
                    if (app.name == pod_affinity):
                        chost["score"] += weight

        return chosts

    def _least_requested_priority(self, application, chosts, weight):
        """
        Favors nodes with fewer requested resources. 
        In other words, the more Pods that are placed on a Node, and the more resources those Pods use, the lower the ranking this policy will give.
        """

        chosts = sorted(chosts, key=lambda chost: (chost['cpuCapacity'] - chost['cpuUsed'], int(chost['memoryCapacity'] - chost['memoryUsed'])), \
            reverse=True) # Free CPU and Memory

        groups = dict()
        for chost in chosts:
            key = (chost['cpuCapacity'] - chost['cpuUsed'], int(chost['memoryCapacity'] - chost['memoryUsed']))
            if (key in groups):
                groups[key] += 1
            else:
                groups[key] = 1

        highiest = weight
        scores = []
        for group in groups.items():
            for _ in range(0, group[1]):
                scores.append(highiest)
            break # prioritizes only the first group
            # highiest -= 1

        for chost, score in zip(chosts, scores):
            if (score):
                chost['score'] += score
                log.debug(f"{self._least_requested_priority.__name__} chost['id']: {chost['id']} score: {score}")
            else:
                break

        return chosts

    def _least_congested_node_priority(self, application, chosts, weight):
        """
        Favorece os nodes menos congestionados
        """

        # 1. provavel tempo de instanciação levando em conta as aplicações em fila 
        application_layers = dict()
        for layer in application.image.versions[0].layers:
            application_layers[layer.digest] = layer.size

        total_time_to_instantiate = dict()
        for chost in chosts:
            messages_layers = dict()
            for application in chost['scheduledApplications']:
                for replica in application.replicas:
                    if (replica.node == chost["id"]):
                        for message in replica.messages:
                            if (message.status == 0 or message.status == 3 or message.status == 4 or message.status == 5):
                                messages_layers[message.layer] = message.data_to_transmit()

            # TODO Remove message.status == 5
            # To verify if the chost has a layer in locally check cache
            # for cache in chost['log']['cache']

            bandwidth = bitmath.parse_string(chost['bandwidth']) if chost['rate'] == bitmath.Bit(0) else chost['rate'].to_Mb()
            total_time_to_instantiate[chost["id"]] = sum((application_layers | messages_layers).values()) / bandwidth

        # sort dict
        total_time_to_instantiate = {k: v for k, v in sorted(total_time_to_instantiate.items(), key=lambda item: item[1])}
        
        # rescale
        total_time_list = [v for k, v in total_time_to_instantiate.items()]
        min_total_time = min(total_time_list)
        max_total_time = max(total_time_list)

        if (min_total_time == max_total_time):
            for chost in chosts:
                if chost['id'] in total_time_to_instantiate:
                    chost['score'] += weight
                    log.debug(f"{self._least_congested_node_priority.__name__} chost['id']: {chost['id']} score: {weight}")

        else:
            for chost in chosts:
                # rescale = lambda max, value: (1 - value / max) * weight
                # score = rescale(max_total_time, total_time_to_instantiate[chost["id"])

                if chost['id'] in total_time_to_instantiate:
                    score = (weight - ((weight - 0) / (max_total_time - min_total_time) * (total_time_to_instantiate[chost["id"]] - min_total_time) + 0))
                    chost['score'] += score
                    log.debug(f"{self._least_congested_node_priority.__name__} chost['id']: {chost['id']} total_time_to_instantiate: {total_time_to_instantiate[chost['id']]} score: {score}")

        return chosts

    def _image_locality_priority(self, application, chosts, weight):

        application_layers = self._get_application_layers(application)

        for chost in chosts:
            if (len(chost["layers"]) > 0):
                chost_layers = [layer[0] for layer in chost["layers"]]

                # The list chost_layers contain all elements of the list application_layers
                if all(layer in chost_layers for layer in application_layers):
                    chost["score"] += weight
                    log.debug(f"{self._image_locality_priority.__name__} chost['id']: {chost['id']} score: {weight}")

        return chosts

    def _layer_locality_priority(self, application, chosts, weight):

        application_layers = {layer.digest:layer.size for layer in application.image.versions[0].layers}

        chost_priority = dict()
        for chost in chosts:

            if (len(chost["layers"]) > 0):
                chost_layers = {layer[0]:layer[1] for layer in chost["layers"]}
                overlap_layers = {app_layer[0]:app_layer[1] for app_layer in application_layers.items() if app_layer[0] in chost_layers}

                if (len(overlap_layers) > 0):
                    size_overlap = sum([layer[1] for layer in overlap_layers.items()])
                    chost_priority[chost['id']] = size_overlap

        if len(chost_priority) > 0:
            # rescale
            chost_priority_list = [v for k, v in chost_priority.items()]
            min_chost_priority = min(chost_priority_list)
            max_chost_priority = max(chost_priority_list)
            
            if (min_chost_priority == max_chost_priority):
                for chost in chosts:
                    if chost['id'] in chost_priority:
                        chost['score'] += weight
                        log.debug(f"{self._layer_locality_priority.__name__} chost['id']: {chost['id']} chost_priority[chost['id']: {chost_priority[chost['id']]} score: {weight}")
            else:
                for chost in chosts:
                    if chost['id'] in chost_priority:
                        score = ((weight - 0) / (max_chost_priority - min_chost_priority) * (chost_priority[chost["id"]] - min_chost_priority) + 0)
                        chost['score'] += score
                        log.debug(f"{self._layer_locality_priority.__name__} chost['id']: {chost['id']} chost_priority[chost['id']: {chost_priority[chost['id']]} score: {score}")

        return chosts

    def _selector_spread_priority(self, application, chosts, weight):

        for chost in chosts:
            # Spreads applications across hosts
            if application in chost["scheduledApplications"]:
                chost["score"] -= weight
                log.debug(f"{self._selector_spread_priority.__name__} chost['id']: {chost['id']} score: {-weight}")

        return chosts
    
    def evaluate_priorities(self, **options):
        """
        It returns the eligle nodes based on predicades.
        https://kubernetes.io/docs/reference/scheduling/policies/#priorities
        """

        chosts = options.get('chosts')
        application_to_schedule = options.get('application_to_schedule')

        chosts = [dict(host, score=10) for host in chosts]

        for priority in self.config["priorities"]:
            chosts = self.priorities[priority["name"]](application_to_schedule, chosts, priority.get("weight", 10)) # 10 as a default value

        # chosts = sorted(chosts, key=lambda chost : chost['score'], reverse=True)

        return chosts

    def _pod_fits_resources(self, application, chosts):

        eligible_node = []
        for chost in chosts:
            # if the node has free cpu and memory           
            if ((chost["cpuCapacity"] - chost["cpuUsed"] >= application.cpuRequired) and \
                (chost["memoryCapacity"] - chost["memoryUsed"]) >= application.memoryRequired):

                # eligible node
                eligible_node.append(chost)

        return eligible_node

    def _pod_anti_affinity(self, application, chosts):
        """
        https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#inter-pod-affinity-and-anti-affinity
        """

        ineligible_nodes = []
        pod_affinity, pod_anti_affinity = None, None

        for label in application.labels:
            # if "podAffinity" == label["key"]:
            #     pod_affinity = [label for label in application.labels if label["key"] == "podAffinity"][0]["value"]
            if "podAntiAffinity" == label["key"]:
                pod_anti_affinity = [label for label in application.labels if label["key"] == "podAntiAffinity"][0]["value"]

        if (pod_anti_affinity):
            for chost in chosts:
                for app in chost["scheduledApplications"]:
                    if (app.name == pod_anti_affinity):
                        # chost["score"] -= 1
                        ineligible_nodes.append(chost["id"])

        # TODO
        # if (pod_affinity):
        #     for chost in chosts:
        #         for app in chost["scheduledApplications"]:
        #             if (app.name == pod_affinity):
        #                 eligible_nodes.append(chost["id"])

        return [chost for chost in chosts if chost["id"] not in ineligible_nodes]

    def _match_node_selector(self, application, chosts):

        eligible_nodes = []
        selector = None

        for label in application.labels:
            if "selector" in label["key"]:
                selector = label

        if (selector):
            for chost in chosts:
                for chost_label in chost['labels']:
                    if (chost_label['key'] == selector['key'].split(':')[-1]):
                        if (chost_label['value'] == selector['value']):
                            eligible_nodes.append(chost["id"])

            chosts = [chost for chost in chosts if chost["id"] in eligible_nodes]
        
        return chosts

    def evaluate_predicates(self, **options):
        """
        It returns the eligle nodes based on predicades.
        https://kubernetes.io/docs/reference/scheduling/policies/#predicates
        """

        chosts = options.get('chosts')
        application_to_schedule = options.get('application_to_schedule')

        for predicate in self.config["predicates"]:
            # TODO Verify if there is nodes to evaluate
            # if (chosts):
            #     TODO
            # else:
            chosts = self.predicates[predicate](application_to_schedule, chosts)

        return chosts

    def place(self, **options):
        """
        It returns a deployment composed by source repository (registry) and destination (container host - chost).
        """

        topology = options.get('topology')
        application_to_schedule = options.get('application_to_schedule')
        chosts = ct.Node().get_all_chosts(topology)

        chosts = self.evaluate_predicates(chosts=chosts, application_to_schedule=application_to_schedule)
        chosts = self.evaluate_priorities(chosts=chosts, application_to_schedule=application_to_schedule)

        scores = [chost['score'] for chost in chosts]

        if len(scores) == 0:
            log.warn(f"No node found for the application {application_to_schedule.name}")
            sys.exit(0)
            # return None, None # TODO suportar continuar a simulação

        log.debug("Scores {}".format({chost['id']: chost['score'] for chost in chosts}))

        # The node with the highest score is chosen
        # If there is more than one node with equal scores, kube-scheduler selects one of these at random
        if (scores.count(max(scores)) > 1):
            chosts_selected = [chost for chost in chosts if chost['score'] == max(scores)]
            node = random.choice(chosts_selected)
        else:
            # select the node with the highest score
            node = sorted(chosts, key=lambda item: item['score'], reverse=True)[0]

        registry = ct.Node.get_registry(node["id"], topology)

        return registry, node["id"]


class RandomScheduler(Scheduler):    # overriding abstract method

    def place(self, **options):
        """
        It returns a deployment composed by source repository (registry) and destination (container host - chost).
        """

        images = options.get('images')
        topology = options.get('topology')
        
        chosts = ct.Node().get_all_chosts(topology)

        # randomly selecting the node where the container will be provisioned
        containerHostSelected = random.choice(chosts)

        # randomly selecting the registry where the image will be downloaded
        registry = next(map(lambda x: x[0], filter(lambda x: x[1]["name"] == random.choice(containerHostSelected["registry"]), topology.nodes(data=True))))

        return registry, containerHostSelected["id"] # deploymentId


class NetworkAwareScheduler(KubeScheduler):

    def __init__(self, **options):
        super().__init__(**options)

    def get_RTT(self, node, target_location):
        rtt = None
        
        try:
            rtt = [label for label in node['labels'] if label['key'] == target_location][0]['value']
            rtt = float(rtt)
        except Exception as error:
            log.error(f'There is no rtt for node {node["id"]}. Error: {error}')
            return sys.float_info.max

        return rtt

    def remove_node(self, nodes, to_remove):

        return [node for node in nodes if node["id"] != to_remove["id"]]

    def get_bandwidth_value(self, node):
        bandwidth = None
        
        try:
            bandwidth = [label for label in node['labels'] if label['key'] == 'bandwidth'][0]['value']
            bandwidth = bitmath.parse_string(bandwidth)
        except Exception as error:
            message = f'There is no bandwidth for node {node["id"]}. Error: {error}'
            log.error(message)
            raise Exception(message)

        return bandwidth

    def place(self, **options):
        """
        This scheduler implements a Network-Aware Scheduler (Santos et al., 2019).
        """

        topology = options.get('topology')
        application_to_schedule = options.get('application_to_schedule')

        # Recursive algorith
        if ('chosts' not in options):
            chosts = ct.Node().get_all_chosts(topology)

            chosts = super().evaluate_predicates(chosts=chosts, topology=topology, application_to_schedule=application_to_schedule)
            # chosts = super().evaluate_priorities(chosts=chosts, application_to_schedule=application_to_schedule)
        else:
            chosts = options.get('chosts')

        # application location and min bandwidth required
        target_location = None
        min_bandwidth = None

        try:
            target_location = [app for app in application_to_schedule.labels if app['key'] == 'targetLocation'][0]['value']
        except Exception as error:
            log.error('There is no target_location founded!')
        
        try:
            min_bandwidth = [app for app in application_to_schedule.labels if app['key'] == 'minBandwidth'][0]['value']
            min_bandwidth = bitmath.parse_string(min_bandwidth)
        except Exception as error:
            log.warn(f'Minimum bandwidth has not been set for the application {application_to_schedule.id}')

            # If the bandwidth request is not specified in the pod configuration file, 
            # a default value of 250 Kbit/s is considered during the scheduling phase.
            min_bandwidth = bitmath.parse_string('250Kb')
    
        minimum = sys.float_info.max
        copy = chosts.copy()

        # find min RTT
        for node in chosts:
            # get RTT between target_location and node location
            rtt = self.get_RTT(node, target_location)
            minimum = min([minimum, rtt])

        # find best Node based on RTT and minBandwidth
        for node in chosts:

            if minimum == self.get_RTT(node, target_location):

                if min_bandwidth <= self.get_bandwidth_value(node):

                    new_bandwidth = self.get_bandwidth_value(node) - min_bandwidth

                    for label in node["labels"]:
                        if (label["key"] == 'bandwidth'):
                            label["value"] = str(new_bandwidth)

                    # self.infrastructure.topology.nodes[node["id"]]["labels"] = node["labels"]

                    registry = ct.Node.get_registry(node["id"], topology)
                    
                    return registry, node["id"]

                else:
                    copy = self.remove_node(copy, node)

        if (copy is None):
            message = 'No suitable nodes found!'
            log.error(message)
            raise Exception(message)

        else:
            return self.place(chosts=copy, application_to_schedule=application_to_schedule, topology=topology)


class DependencyScheduler(Scheduler):
    def __init__(self):
        super().__init__()

    def place(self):
        return 


class WorstFitScheduler(Scheduler):
    """
    It distributes the applications over the cluster.
    """
    
    def place(self, **options):

        topology = options.get('topology')
        application_to_schedule = options.get('application_to_schedule')
        
        chosts = ct.Node().get_all_chosts(topology)

        # keep just eligle hosts.
        chosts = KubeScheduler().evaluate_predicates(chosts=chosts, topology=topology, application_to_schedule=application_to_schedule)

        node = sorted(chosts, key=lambda item: (item['cpuUsed'], item['memoryUsed']), reverse=True)[0]

        registry = ct.Node.get_registry(node["id"], topology)

        return registry, node["id"]


class BestFitScheduler(Scheduler):
    """
    It concentrates applications on the most loaded nodes.
    """
    
    def place(self, **options):

        topology = options.get('topology')        
        chosts = ct.Node().get_all_chosts(topology)

        node = sorted(chosts, key=lambda item: (item['cpuUsed'], item['memoryUsed']), reverse=False)[0]

        registry = ct.Node.get_registry(node["id"], topology)

        return registry, node["id"]