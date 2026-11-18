import json
from networkx.readwrite import json_graph
import sys

def time_per_app(messages, topo, filename):
    if not filename:
        filename="simulation"

    messages_plot = {}

    for message in messages:
        if not message.name in messages_plot.keys():
            messages_plot[message.name] = []

        messages_plot[message.name].append(
            {"downloadTime":round(message.finish_time-message.start_time, 2),
            "waitingTime":round(message.start_time-message.arrival_time, 2), 
            "node":topo.nodes[message.path[-1]]["name"],
            "id":message.id})

    jsonFile = {"apps":[]}

    for id, values in messages_plot.items():
        jsonFile["apps"].append({"name":id, "containers":values})
    
    with open("reports/"+filename+'-time_per_app.json', 'w') as fp:
        json.dump(jsonFile, fp)

def _get_time_per_host(messages, hosts):

    messages_per_host = {}
    for message in messages:
        if message.path[-1] in messages_per_host.keys():
            messages_per_host[message.path[-1]].append(message)
        else:
            messages_per_host[message.path[-1]] = [message]

    times_per_host = []
    for host, messages in messages_per_host.items():
        entry = {"name":hosts.nodes[host]['name'], "id":host, "messages":[]}
        for message in messages:
            if message.transmitted == 0:
                bandwidth = 0.0
            else:
                bandwidth = message.size.to_Mb()/(message.finish_time-message.start_time)
            entry['messages'].append({"name":message.name, "id":message.id, "start_time":message.start_time, "finish_time":message.finish_time, "bandwidth_mean":bandwidth, "size":message.size})
        entry['messages'] = sorted(entry['messages'], key=lambda x: x['start_time'])
        times_per_host.append(entry)

    return times_per_host

def host_occupation(messages, hosts, filename):
    file = open('reports/'+filename+"-host_occupation.csv", 'w')

    times_per_host = _get_time_per_host(messages, hosts)

    file.write("host;name;start_time;finish_time;bw;size\n")
    for host in times_per_host:
        #file.write("Host: "+host['name']+"\n")
        for message in host['messages']:
            file.write("%s;%s;%.2f;%.2f;%.2f;%.2f\n"%(host["name"],message['name'], message['start_time'],message['finish_time'],message['bandwidth_mean'],message["size"]))
        #file.write("-------------------\n")
     
    file.close()

def provision_time(messages, hosts, filename):
    file = open('reports/'+filename+"-provision_time.csv", 'w')

    provision_time_by_application = dict()
    times_per_host = _get_time_per_host(messages, hosts)

    for host in times_per_host:
        for message in host['messages']:
            app_name = message['name'].split('-sha256')[0]
            if (app_name in provision_time_by_application.keys()):
                provision_time_by_application[app_name]['provision_time'] += message['finish_time'] - message['start_time']

            else:
                provision_time_by_application[app_name] = dict(
                    host = host["name"],
                    provision_time = message['finish_time'] - message['start_time'],
                ) 

    file.write("host;name;provision_time\n")
    for app in provision_time_by_application.items():
        file.write("%s;%s;%.2f\n"%(app[1]['host'], app[0], app[1]['provision_time']))
     
    file.close()

def cache_status(topo, filename):

    file = open('reports/'+filename+"-cache_status.csv", 'w')

    file.write("host;hit;miss;total\n")
    for host in topo.nodes(data=True):
        host = host[1]
        if host["type"] == "chost":
            cache = host["log"]["cache"]
            if cache[0] > 0 or cache[1] > 0:
                file.write("%s;%d;%d;%d\n" %(host['name'],cache[0],cache[1],cache[0]+cache[1]))
                #file.write("Host: "+host['name']+"\n")
                #file.write("Cache Hit: %d/%d = %.3f\n" %(host["cache"][0], host["cache"][0]+host["cache"][1], (host["cache"][0]/(host["cache"][0]+host["cache"][1]))*100))
                #file.write("Cache Miss: %d/%d = %.3f\n\n" %(host["cache"][1], host["cache"][0]+host["cache"][1], (host["cache"][1]/(host["cache"][0]+host["cache"][1]))*100))

def container_instantiation_time(messages, topo, filename):
    file = open('reports/'+filename+"-container_time.json", 'w')
    file.write("{\n\"containers\":\n")
    containers = []
    for message in messages:
        downloaded = int(message.transmitted/message.size)
        if message.status == 1:
            downloaded = 2
        containers.append({"name":message.name, "src":topo.nodes[message.src]["name"], "dst":topo.nodes[message.dst]["name"], "downloaded":downloaded, "download_time": message.finish_time-message.arrival_time})
    json.dump(containers, file)
    file.write("}")

def container_all_times(messages, topo, filename):
    file = open('reports/'+filename+"-container_all_times.json", 'w')
    file.write("{\n\"containers\":\n")
    containers = []
    for message in messages:
        downloaded = int(message.transmitted/message.size)
        if message.status == 1:
            downloaded = 2
        containers.append({"name":message.name, "src":topo.nodes[message.src]["name"], "dst":topo.nodes[message.dst]["name"], "downloaded":downloaded, "instantiation_time": message.finish_time-message.arrival_time, "waiting_time":message.start_time-message.arrival_time, "download_time":message.finish_time-message.start_time })
    json.dump(containers, file)
    file.write("}")

def chain_time(messages, filename):

    file = open('reports/'+filename+"-chain_time.json", 'w')
    messages = sorted(messages, key=lambda x: x.chain)

    chains = {} 

    for message in messages:

        downloaded = int(message.transmitted/message.size)
        if message.status == 1:
            downloaded = 2
        appended_message = {"name":message.name, "schedule":message.arrival_time, "deadline":message.deadline_time ,"start":message.start_time ,"finish":message.finish_time, "downloaded":downloaded}

        if message.chain not in chains.keys():
            chains[message.chain] = {"finish_time": message.finish_time, "expected_lifetime": message.deadline_time-message.arrival_time, "real_lifetime":message.deadline_time-message.finish_time, "messages":[appended_message], "status":message.status}
        else:
            if message.finish_time > chains[message.chain]["finish_time"]:
                 chains[message.chain]["finish_time"] = message.finish_time
                 chains[message.chain]["real_lifetime"] = message.deadline_time-message.finish_time
            #print(message.__dict__)
            chains[message.chain]["messages"].append(appended_message)
            if message.status > chains[message.chain]["status"] :
                chains[message.chain]["status"] = message.status

    file.write("{\n\"chains\":\n")
    tmp = []
    for id, chain in chains.items():
         tmp.append({"id":id,"status":chain["status"],"expected":chain["expected_lifetime"],"real":chain["real_lifetime"],"percentage":chain["real_lifetime"]/chain["expected_lifetime"]})
         #tmp = ""
         #for message in chain["messages"]:
         #    tmp += str(message)+", "
         #file.write(json.dumps(chain["messages"]))
    file.write(json.dumps(tmp))
    file.write("}")

class bitmath_json_serializable(json.JSONEncoder):
    def default(self, o):
        #print(type(o))
        if "bitmath" in str(type(o)):
            return "%s"%o.to_Bit()
        else:
            return o.__dict__   

def network_log(logs, topo, filename):

    file = open('reports/'+filename+"-network_log.json", 'w')

    file.write("{\n\"rates\":\n")

    json.dump(logs, file)

    file.write(",\n\"graph\":\n")

    file.write(json.dumps(json_graph.node_link_data(topo), cls=bitmath_json_serializable))

    file.write("}")

def registry_usage(messages, topo, filename):
    file = open('reports/'+filename+"-registry_usage.json", 'w')
    file.write("{\n\"registries\":\n")
    registries = {}
    for message in messages:
        if topo.nodes[message.src]["name"] in registries.keys():
            registries[topo.nodes[message.src]["name"]] += 1
        else:
            registries[topo.nodes[message.src]["name"]] = 0
    jsonRegistry = []
    for name,number in registries.items():
        jsonRegistry.append({"name":name, "numberOfRequests":number})
    
    file.write(json.dumps(jsonRegistry))

    file.write("}")

def generate_reports(reports, infra, filename):
    if "hostOccupation" in reports:
        host_occupation(infra.messages["installed"], infra.topology, filename.stem)
    if "provisionTime" in reports:
        provision_time(infra.messages["installed"], infra.topology, filename.stem)
    if "timePerApp" in reports:
        time_per_app(infra.messages["installed"], infra.topology, filename.stem)
    if "cacheStatus" in reports:
        cache_status(infra.topology, filename.stem)
    if "chainTime" in reports:
        chain_time(infra.messages["installed"]+infra.messages["error"], filename.stem)
    if "networkLog" in reports:
        network_log(infra.log["netstat"], infra.topology, filename.stem)
    if "registryUsage" in reports:
        registry_usage(infra.messages["installed"]+infra.messages["error"], infra.topology, filename.stem)
    if "containerTime" in reports:
        container_instantiation_time(infra.messages["installed"]+infra.messages["error"], infra.topology, filename.stem)
    if "containerAllTimes" in reports:
        container_all_times(infra.messages["installed"]+infra.messages["error"], infra.topology, filename.stem)