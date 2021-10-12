""" CLI script converting a PDS from the JimpleToPDSolver format into PuMoC and RSMCheck format"""

import argparse
import collections
import sys
sys.path.append("..")
try:
    from src.model import rsm
except ImportError:
    print("This script has to be run from the src folder, e.g. like this:\n"
          "python3 etc/jimple_convert.py ../models/j2p.out")
    exit()
from pds_to_rsm import write_rsm


def remove_double_spaces(s):
    if len(s) == 0:
        return s
    while "  " in s:
        s = s.replace("  ", " ")
    if s[0] == " ":
        s = s[1:]
    if s[-1] == " ":
        s = s[:-1]
    return s


def extract_usedef(source, target):

    variables = set()
    mu_vars = set()

    # skip to labels
    with open(source) as f:
        for line in f:
            if "Propositions:" in line:
                break

        for line in f:
            if "Property:" in line:
                break
            line = line.replace("\n", "").replace(";", "")
            line = remove_double_spaces(line)
            if len(line) <= 1:
                continue
            line = line.split(" ")
            labels = line[1:]

            for label in labels:
                if label.startswith("use__") or label.startswith("def__"):
                    var_name = label[5:]
                    variables.add(var_name)
                elif label.startswith("usedef__"):
                    var_name = label[8:]
                    variables.add(var_name)

        for line in f:
            line = line.replace("\n", "").replace(";", "")
            line = line.replace("[", " ").replace("]", " ")\
                .replace("<", " ").replace(">", " ")\
                .replace("@", " ").replace("\\", " ")
            line = remove_double_spaces(line)
            if len(line) <= 1:
                continue
            line = line.split(" ")
            for word in line:
                if word.startswith("use__") or word.startswith("def__"):
                    var_name = word[5:]
                    mu_vars.add(var_name)
                elif word.startswith("usedef__"):
                    var_name = word[8:]
                    mu_vars.add(var_name)

    usedef_ctl_path = target + "_usedef.ctl"

    with open(usedef_ctl_path, 'w') as f:
        f.write("# usedef formulas for each variable occurring in the program\n\n")
        for v in variables:
            if len(v) == 0:
                continue
            use_var = "use__" + v
            def_var = "def__" + v
            usedef_var = "usedef__" + v

            def_or_usedef = "( " + def_var + " | " + usedef_var + " )"
            eventually_use_or_usedef = "E F ( " + use_var + " | " + usedef_var + " )"
            implication = "( " + def_or_usedef + " --> " + eventually_use_or_usedef + " )"
            formula = "A G " + implication

            f.write(formula)
            f.write("\n")

    single_usedef_ctl_path = target + "_single_usedef.ctl"

    with open(single_usedef_ctl_path, 'w') as f:
        f.write("# usedef formulas for each variable occurring in the mu property of the PDMU\n\n")

        for v in mu_vars:
            if len(v) == 0:
                continue
            use_var = "use__" + v
            def_var = "def__" + v
            usedef_var = "usedef__" + v

            def_or_usedef = "( " + def_var + " | " + usedef_var + " )"
            eventually_use_or_usedef = "E F ( " + use_var + " | " + usedef_var + " )"
            implication = "( " + def_or_usedef + " --> " + eventually_use_or_usedef + " )"
            formula = "A G " + implication

            f.write(formula)
            f.write("\n")


"""
PuMoC format.
Each line has to be in exactly one of the following formats:
* [state + tape] represented as 'state < >' , 'state <tape>' or 'state <tape1 tape2>'
* init state must be state + exactly one tape symbol, denoted as '(state <tape>)'
* transition as '[state + tape] --> [state + tape]'
* labeling as 'ATOMS [atom] [states]' where states are separated by comma (and possibly white space)
* comment line, starting with #
* empty line (skipped)
leading white spaces are allowed
"""


def pdsolver_to_pumoc(source, target):
    rules = []
    atoms = []

    # transitions
    with open(source) as f:
        for line in f:
            if "Propositions:" in line:
                break
            line = line.replace("\n", "").replace(";", "")
            if " -> " not in line:
                continue
            line = line.split(" -> ")
            pre = line[0]
            post = line[1]

            # left side
            pre = remove_double_spaces(pre)
            pre = pre.split(" ")
            pre = [" " if e == "_" else e for e in pre]
            left_state = pre[0]
            left_tape = "<" + " ".join(pre[1:]) + ">"
            left = left_state + " " + left_tape

            # right side
            post = remove_double_spaces(post)
            post = post.split(" ")
            post = [" " if e == "_" else e for e in post]
            right_state = post[0]
            right_tape = "<" + " ".join(post[1:]) + ">"
            right = right_state + " " + right_tape

            new_line = left + " --> " + right

            rules.append(new_line)

        # propositions
        state = None
        #atoms.append(" ATOMS csinit csinit")
        #atoms.append(" ATOMS csq csq")
        #atoms.append(" ATOMS csend csend")

        for line in f:
            if "Mu Property" in line:
                break
            line = line.replace("\n", "").replace(";", "")
            line = remove_double_spaces(line)
            if len(line) <= 1:
                continue
            line = line.split(" ")
            this_state = line[0]
            if state is None:
                state = this_state
            elif state != this_state:
                break
            tape = line[1]
            aps = line[2:]
            if state in aps:
                aps.remove(state)
            if len(aps) <= 1:
                continue
            aps = ", ".join(aps)
            new_line = " ATOMS " + tape + " " + aps
            atoms.append(new_line)

        # writing
        with open(target, 'w') as out_file:
            out_file.write("(csinit_0 <blank_0>)\n\n")
            for line in atoms:
                line = line.replace("csq","csq_1")
                line = line.replace("csinit", "csinit_0")
                line = line.replace("csend", "csend_2")
                line = line.replace("#", "blank_0")
                line = line.replace("'", "_")
                out_file.write(line)
                out_file.write("\n")
            out_file.write("\n")
            for line in rules:
                line = line.replace("csq", "csq_1")
                line = line.replace("csinit", "csinit_0")
                line = line.replace("csend", "csend_2")
                line = line.replace("#", "blank_0")
                line = line.replace("'", "_")
                out_file.write(line)
                out_file.write("\n")


def pdsolver_to_rsm(source, target, pretty=False):
    with open(source) as f:
        #############
        # structure #
        #############

        # convert PDS into dict
        transitions = collections.defaultdict(list)
        entry_nodes = []

        for line in f:
            if "Propositions:" in line:
                break
            line = line.replace("\n", "").replace(";", "")
            if " -> " not in line:
                continue
            line = line.split(" -> ")
            pre = line[0]
            post = line[1]

            if "csinit #" in pre:
                initial_state = remove_double_spaces(post).split(" ")[1]
                entry_nodes.append(initial_state)
                continue
            if "csend #" in post:
                continue

            # dismiss csq
            pre = remove_double_spaces(pre)
            pre = pre.split(" ")
            pre = pre[1]

            post = remove_double_spaces(post)
            post = post.split(" ")
            post = post[1:]

            transitions[pre].append(post)
            for n in post:
                if len(post) > 1:
                    entry_nodes.append(post[0])
                if n not in transitions:
                    transitions[n] = []

        # determine which nodes belong in the same component
        components = {}
        index = 0
        for node in entry_nodes:
            reach = component_reach(transitions, node)
            name = "component" + str(index)
            components[name] = reach
            join_components(components, name)
            index += 1

        # dict that holds strings as keys and the corresponding node/component as value to avoid expensive searches
        mapping = {}

        # create RSM
        machine = rsm.RSM()

        # create components and nodes
        for name, component in components.items():
            new_component = rsm.Component(name)
            machine.add_component(new_component)
            mapping[name] = new_component

            for n in component:
                new_node = rsm.Node(n)
                new_component.add_node(new_node)
                mapping[n] = new_node
                # set initial node
                if n == initial_state:
                    machine.initial_node = new_node
                    machine.initial_component = new_component
                if n in entry_nodes:
                    new_component.make_entry_node(new_node)
                if ["_"] in transitions[n]:
                    new_component.make_exit_node(new_node)

        # create boxes and transitions
        box_index = 0
        for n, successors in transitions.items():
            # init/end is handled separately
            if n == "#":
                continue
            # n is unreachable from any entry node
            if n not in mapping:
                continue
            for successor in successors:
                # normal transition
                if len(successor) == 1:
                    if "_" in successor or "#" in successor[0]:
                        continue
                    source_node = mapping[n]
                    target_node_name = successor[0]
                    if target_node_name not in mapping:
                        continue
                    target_node = mapping[target_node_name]
                    component = source_node.parent_component
                    component.add_transition(source_node, target_node)
                # box entry
                elif len(successor) == 2:
                    if "_" in successor or "#" in successor[0]:
                        continue
                    # fetch corresponding RSM objects
                    source_node = mapping[n]
                    component = source_node.parent_component
                    call_node = mapping[successor[0]]
                    box_successor_node = mapping[successor[1]]
                    ref_component = call_node.parent_component

                    # create and add box
                    box_name = "box" + str(box_index)
                    box_index += 1
                    box = rsm.Box(ref_component, box_name, entry_nodes=[call_node])
                    component.add_box(box)

                    # transition to box
                    target_box_node = component.get_call_node(box, call_node)
                    component.add_transition(source_node, target_box_node)

                    # transitions from box
                    for ex in box.return_nodes:
                        source_box_node = component.get_return_node(box, ex)
                        component.add_transition(source_box_node, box_successor_node)
                else:
                    raise ValueError("Found a transition with 3 tape symbols: " + str(successor))

        ##########
        # labels #
        ##########

        state = None

        for line in f:
            if "Mu Property" in line:
                break
            line = line.replace("\n", "").replace(";", "")
            line = remove_double_spaces(line)
            if len(line) <= 1:
                continue
            line = line.split(" ")
            this_state = line[0]
            if state is None:
                state = this_state
            elif state != this_state:
                break
            node_name = line[1]
            if node_name == "#":
                continue
            labels = line[2:]
            for label in labels:
                if label == "csq":
                    continue
                # exclude unreachable nodes
                if node_name not in mapping:
                    continue
                node = mapping[node_name]
                node.parent_component.add_label(node, label)

        ###########
        # writing #
        ###########

        write_rsm(target, machine, pretty)


def join_components(components, new_component):
    """ given candidate boxes, join those who have common nodes """
    to_join = [new_component]
    for name, component in components.items():
        if name == new_component:
            continue
        for component_to_join_name in to_join:
            component_to_join = components[component_to_join_name]
            # check if intersection is non-empty
            if not set(component).isdisjoint(component_to_join):
                to_join.append(name)
                break
    joined_component = []
    for name in to_join:
        joined_component += components[name]
        components.pop(name)
    joined_component = list(set(joined_component))
    components[new_component] = joined_component


def component_reach(transitions, node):
    """ return which nodes are reachable from any given node inside the same component (i.e, not going into boxes) """
    reach = []
    next_reach = [node]

    while next_reach:
        reach += next_reach
        new_reach = []
        for n in next_reach:
            # we don't go into boxes, so in case the PDS writes 2 tape symbols we only care for the latter
            successors = [t[-1] for t in transitions[n]]
            for s in successors:
                # deleting the tape symbol is not a successor
                if s == "_":
                    continue
                if s not in reach and s not in new_reach and s not in next_reach:
                    new_reach.append(s)
        next_reach = new_reach.copy()
    return reach


def main():
    parser = argparse.ArgumentParser(description="Convert a PDSolver PDS into an .rsm file and a PuMoC PDS")
    parser.add_argument("path_to_pdmu", help="path to .pdmu file")
    parser.add_argument("-pretty",
                        action="store_true",
                        help="add proper indentation the RSM output file for readability at the cost of space")
    parser.add_argument("--out",
                        metavar="output_path",
                        help="path to desired output file (without file ending)\n"
                             "defaults to same as source with appropriate file ending")

    args = parser.parse_args()
    source_file = args.path_to_pdmu
    dot_index = source_file.find(".pdmu")
    auto_target_file_rsm = source_file + ".rsm" if dot_index == -1 else source_file[:dot_index] + ".rsm"
    auto_target_file_pds = source_file + ".pds" if dot_index == -1 else source_file[:dot_index] + ".pds"
    auto_target_dir = source_file if dot_index == -1 else source_file[:dot_index]
    target_file_rsm = args.out + ".rsm" if args.out else auto_target_file_rsm
    target_file_pds = args.out + ".pds" if args.out else auto_target_file_pds
    target_dir = args.out or auto_target_dir
    pretty = args.pretty

    extract_usedef(source_file, target_dir)
    pdsolver_to_pumoc(source_file, target_file_pds)
    pdsolver_to_rsm(source_file, target_file_rsm, pretty)


if __name__ == "__main__":
    main()
