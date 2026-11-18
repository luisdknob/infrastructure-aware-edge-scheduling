#import simpy as sim
import time
import sys
import json
import logging as log
import pathlib
import argparse
import time
import random

import classes.infrastructure as ct
import classes.application as ca
import classes.json as js
import classes.draw as dr
import classes.report as rp
import classes.simulation as cs

def parse_args(parser):
    parser.epilog = "ContainerSim v0.01"
    parser.add_argument("--debug", help="enable DEBUG log", action="store_true")
    parser.add_argument("--seed", type=int, default=None, help="set the random seed")
    parser.add_argument("--netLimit", type=float, default=1.0, help="set the limit to network bandwidth")
    parser.add_argument("--topo", help="import a topology file")
    parser.add_argument("--options", type=json.loads, default={}, help="Complimentary options to deploy the topology")
    parser.add_argument("--file", help="import a configuration file")
    parser.add_argument("--draws", nargs="+", help="list of graphics that want to be generate after the simulation")
    parser.add_argument("--reports", nargs="+", help="list of logs that want to be generate after the simulation")
    parser.add_argument("--psch", help="list of logs that want to be generate after the simulation")

    return parser.parse_args()

def main():

    start_time = time.time()

    log.basicConfig(filename="logs/log_"+str(int(time.time()))+".log",
                            filemode='a', format='%(levelname)s - %(message)s', level=log.INFO)
    
    args = parse_args(argparse.ArgumentParser())
    
    if args.seed is not None:
        random.seed(int(args.seed))

    if args.file:
        filename = pathlib.Path(args.file)
        with open(filename, "r") as file:
            json_file = json.load(file)
            if js.validate_schema(json_file):
                nodes, edges, images, applications, operations, options = js.configuration_from_JSON(json_file)
            else:   
                log.info("Não deu")

    # Create infrastructure graph
    infra = ct.Infrastructure(nodes, edges)

    simulation = cs.Simulation(**options)

    simulation.add_infrastructure(infra)
    simulation.add_applications(applications, operations)
    simulation.add_images(images)

    # Start simulation time

    log.info("Start Simulation")

    sec = simulation.run_simulation()

    log.info("Finish Simulation")
    log.info("Total Time: %.2f" % sec)

    if args.draws:
        if "map" in args.draws:
            dr.map(infra.topology, filename.stem)
        if "containerInstTime" in args.draws:
            dr.container_instantiantion_time(infra.messages["installed"], filename.stem)
        if "containerMaxMinInstTime" in args.draws:
            dr.container_instantiantion_maxmin_time(infra.messages["installed"], filename.stem)
    
    if args.reports:
        rp.generate_reports(args.reports, infra, filename)

    log.info("Simulation Time: %.2f" % (time.time()-start_time))

if __name__ == "__main__":
    main() 
