"""
script to create a random RSM
must be used from the src folder, e.g. like this:
python3 etc/random_rsm.py 3 20 15 15 5 20 -label a 30 -label b 60 -out ../models/random.rsm
for meaning of the numbers use
python3 etc/random_rsm.py -h
"""

import argparse
import sys
from random import random, randint
from pds_to_rsm import write_rsm
sys.path.append("..")
try:
    from src.model import rsm
except ImportError:
    print("This script has to be run from the src folder, e.g. like this:\n"
          "python3 etc/random_rsm.py 3 20 15 15 5 20 -label a 30 -label b 60 -out ../models/random.rsm")
    exit()

parser = argparse.ArgumentParser(description="Create a random RSM")
parser.add_argument("nr_components", help="number of components in the RSM")
parser.add_argument("nr_nodes", help="number of nodes in each component (not including box nodes)")
parser.add_argument("entry_pct", help="percentage of nodes that shall be entry nodes")
parser.add_argument("exit_pct", help="percentage of non-entry nodes that shall be exit nodes")
parser.add_argument("nr_boxes", help="number of boxes per component")
parser.add_argument("transition_pct", help="percentage of possible outgoing transitions existing per node")
parser.add_argument("-label", help="add a label to a certain percentage of nodes in each component."
                                   "first argument is label name, second is percentage.",
                    action="append",
                    nargs=2)
parser.add_argument("-out", help="output location of the RSM", default="random.rsm")

args = parser.parse_args()
nr_components = int(args.nr_components)
nr_nodes = int(args.nr_nodes)
entry_pct = int(args.entry_pct)
exit_pct = int(args.exit_pct)
nr_boxes = int(args.nr_boxes)
transition_pct = int(args.transition_pct)
labels = args.label
out = args.out

machine = rsm.RSM()

components = [rsm.Component("c"+str(i)) for i in range(nr_components)]
machine.components = components
machine.initial_component = components[0]

for i, c in enumerate(components):
    for j in range(nr_nodes):
        node = rsm.Node("n" + str(i) + "_" + str(j))
        c.add_node(node)
        if j == 0:
            c.make_entry_node(node)
        elif j == 1:
            c.make_exit_node(node)
        elif random() < entry_pct / 100:
            c.make_entry_node(node)
        elif random() < entry_pct / 100:
            c.make_exit_node(node)
        for lbl, pct in labels:
            if random() < float(pct) / 100:
                c.add_label(node, lbl)

for i, c in enumerate(components):
    for j in range(nr_boxes):
        ref_index = randint(0, nr_components-1)
        ref_component = machine.components[ref_index]
        box = rsm.Box(ref_component, "b" + str(i) + "_" + str(j))
        c.add_box(box)

for c in components:

    # we sort nodes to form a total order
    # the box-nodes for each box will be adjacent in the order, i.e., act as one node
    # transitions will only be allowed to go forward according to this order
    sorted_nodes = []

    for n in c.nodes:
        # don't add box nodes for now
        if isinstance(n, rsm.BoxNode):
            continue
        # don't add entry/exit nodes as they have to be first/last in ordering
        if c.is_entry(n) or c.is_exit(n):
            continue
        # insert node at random spot
        sorted_nodes.insert(randint(0, len(sorted_nodes)), n)

    bn_insertions = []
    for box in c.boxes:
        bns = box.call_nodes + box.return_nodes
        insertion_index = randint(0, len(sorted_nodes))
        bn_insertions.append((insertion_index, bns))
    # sort the insertion list by indices, s.t. we insert the box-node furthest back first to not mess up other indices
    bn_insertions.sort(reverse=True, key=lambda x: x[0])
    for index, box_nodes in bn_insertions:
        for bn in box_nodes:
            sorted_nodes.insert(index, bn)

    # insert entry and exit nodes at the front/back
    for n in c.nodes:
        # don't add entry/exit nodes as they have to be first/last in ordering
        if c.is_entry(n):
            sorted_nodes.insert(0, n)
        elif c.is_exit(n):
            sorted_nodes.append(n)

    for i, source in enumerate(sorted_nodes):
        if c.is_exit(source) or (isinstance(source, rsm.BoxNode) and source.is_call_node):
            continue
        # only select targets from behind the source in the ordering
        for target in sorted_nodes:  # [(i+1):]:
            if not(c.is_entry(target) or isinstance(target, rsm.BoxNode) and target.is_return_node) \
                    and random() < float(transition_pct / 100):
                c.add_transition(source, target)

machine.initial_node = machine.initial_component.get_entry_nodes()[0]

write_rsm(out, machine)
