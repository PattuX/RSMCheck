""" Main script to check an RSM against a CTL formula
"""

from rsm_parser import *
from ctl_parser import *
from checker import *
from model.witness import *
import argparse
import logging
import time

# imports for memout/timeout
import signal 
try:
    import resource
except ModuleNotFoundError:
    print("The module 'resource' was not found. Either you have not installed it, or you are running a non-UNIX system."
          " In either case the program will be executed, however memory limits will not be available.")


# limits memory consumption to [maxsize] in Bytes
def limit_memory(maxsize):
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (maxsize, maxsize))


# limits memory consumption to [maxtime] in seconds
def time_exceeded(signo, frame):
    logging.info("timeout")
    raise SystemExit(1)


def limit_time(maxtime):
    soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
    resource.setrlimit(resource.RLIMIT_CPU, (maxtime, hard))
    signal.signal(signal.SIGXCPU, time_exceeded)


parser = argparse.ArgumentParser(description="Check an RSM against a CTL")
parser.add_argument("path_to_rsm", help="input .rsm file")
parser.add_argument("path_to_ctl", help="input .ctl file")
parser.add_argument("-log", "--logfile",
                    default="log.log",
                    help="logfile name")
parser.add_argument("-overwrite",
                    action="store_true",
                    help="overwrite the existing logging file")
parser.add_argument("-exhaustive",
                    action="store_true",
                    help="use exhaustive checking approach")
parser.add_argument("-expansion_heuristic",
                    default="getnext",
                    help="Choose an expansion heuristic for lazy checking from the following list\n"
                         "* getnext: as in GetNextExpansion in the paper, search for a box."
                         "\tAlso enables faster cycle detection\n"
                         "* random: choose a random contextualizable box\n"
                         "* all: contextualize all boxes (i.e., exhaustive with ternery checking")
parser.add_argument("-maxmem", 
                    default=0,
                    help="maximal amount of MB before memout (default: 0 = no limit)")
parser.add_argument("-maxtime", 
                    default=0,
                    help="maximal time in minutes before timeout (default: 0 = no limit)")
parser.add_argument("-witness",
                    action="store_true",
                    help="generate witness paths for the computed results")
parser.add_argument("-witness_file",
                    default="witness.log",
                    help="witness file name")
parser.add_argument("-randomize_nondeterminism",
                    action="store_true",
                    help="randomize nondeterministic choices in GetNextExpansion when deciding in which disjunct (for "
                         "local formulas) or successor (for existential formulas) to continue the search")

args = parser.parse_args()
path_to_rsm = args.path_to_rsm
path_to_ctl = args.path_to_ctl
logfile = args.logfile
do_overwrite = args.overwrite
do_exhaustive = args.exhaustive
expansion_heuristic = args.expansion_heuristic
do_witnesses = args.witness
witness_file = args.witness_file
randomize_nondeterminism = args.randomize_nondeterminism
maxmem = int(args.maxmem)
maxtime = int(args.maxtime)

if do_overwrite:
    logging.basicConfig(filename=logfile, level=logging.DEBUG, format='%(asctime)s %(message)s', filemode="w")
else:
    logging.basicConfig(filename=logfile, level=logging.DEBUG, format='%(asctime)s %(message)s')

logging.info("---------------------------------")
logging.info("--- STARTING TO CHECK NEW RSM ---")
logging.info("---------------------------------")
logging.info(path_to_rsm + " " + path_to_ctl)
print("Checking RSM " + path_to_rsm + " against properties " + path_to_ctl)
logging.info("using " + ("exhaustive" if do_exhaustive else "lazy") + " approach")

num_true = 0
num_false = 0

total_start_time = time.process_time()

if maxmem > 0:
    limit_memory(maxmem)
if maxtime > 0:
    limit_time(maxtime * 60)

index = 0

for ctl in parse_ctl(path_to_ctl):
    index += 1
    print("checking CTL", index)
    logging.info("--- STARTING TO CHECK NEW FORMULA ---")

    start_parsing_time = time.process_time()
    machine = parse_rsm(path_to_rsm)

    num_comp = len(machine.contextualized_components)
    machine.remove_unreachable_components()

    logging.debug(f"Uncontextualized RSM has {str(num_comp)} components (of which"
                  f"{str(num_comp-len(machine.contextualized_components))} are unreachable) and"
                  f"{str(sum(len(c.base_component.nodes) for c in machine.contextualized_components))} nodes")

    start_checking_time = time.process_time()

    if do_exhaustive:
        check_exhaustive(machine, ctl)
    else:
        try:
            eh = ExpansionHeuristics[expansion_heuristic.upper()]
        except ValueError:
            raise ValueError(f"Invalid expansion heuristic: {expansion_heuristic}")
        check_lazy(machine, ctl, eh, randomize_nondeterminism)

    result = machine.initial_component.interpretation[machine.initial_node][ctl]

    if result is True:
        num_true += 1
    else:
        num_false += 1

    with open('short_log.log', 'a') as f:
        path_to_rsm = args.path_to_rsm
        slash_index = path_to_rsm.rfind("/")
        point_index = path_to_rsm.rfind(".")
        rsm_name = path_to_rsm[slash_index+1:point_index]
        f.write(rsm_name)
        f.write("\t")
        path_to_ctl = args.path_to_ctl
        slash_index = path_to_ctl.rfind("/")
        point_index = path_to_ctl.rfind(".")
        ctl_name = path_to_ctl[slash_index+1:point_index]
        f.write(ctl_name + "/" + str(index))
        f.write("\t")
        f.write(str(time.process_time() - start_checking_time))
        f.write("\n")

    logging.debug("    Final unpacked RSM has " + str(len(machine.contextualized_components)) + " components " +
                  "with a total of " + str(sum(len(c.base_component.nodes) for c in machine.contextualized_components))
                  + " states")
    logging.info(str(result) + ": " + str(ctl) + " does" +
                 (" not" if result is False else "") + " hold in " +
                 str(machine.initial_node.base_name) + " (component " + str(machine.initial_component.name) + ")")
    print(str(result) + ": " + str(ctl) + " does" +
          (" not" if result is False else "") + " hold in " +
          str(machine.initial_node.base_name) + " (component " + str(machine.initial_component.name) + ")")
    logging.info("    Parsing took " + str(start_checking_time - start_parsing_time) + " seconds")
    logging.info("    Checking took " + str(time.process_time() - start_checking_time) + " seconds")

    if do_witnesses:
        witness = generate_witness(machine, [], machine.initial_node, ctl, result)
        with open(witness_file, 'a') as f:
            for line in recursive_str(witness):
                f.write(line)
                f.write("\n")

logging.info("Took a total of " + str(time.process_time() - total_start_time) + " seconds")
logging.info("Found " + str(num_true) + " true formulas and " + str(num_false) + " false formulas.")
