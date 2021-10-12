""" CLI script converting .pds into .rsm files
rather hacky atm, requires very strict input, as in 500 PuMoC examples.
Each line has to be in exactly one of the following formats:
* state + tape represented as 'state < >' , 'state <tape>' or 'state <tape1 tape2>'
* init state must be state + exactly one tape symbol
* transition as '[state + tape] --> [state + tape]'
* labeling as 'ATOMS [atom] [states]' where states are separated by comma (and possibly white space)
* comment line, startig with #
* empty line (skipped)
leading white spaces are allowed
"""

# TODO wait for python to finally handle relative imports in __main__ module properly
import sys
import argparse
import json
sys.path.append("..")
try:
    from src.model import rsm
except ImportError:
    print("This script has to be run from the src folder, e.g. like this:\n"
          "python3 etc/pds_to_rsm.py ../models/10.pds")
    exit()


def read_pds(path_to_file):
    with open(path_to_file) as f:
        init_state = None
        states = []
        boxes = {}
        entry_states = []
        exit_states = []
        labels = {}
        transitions = {}

        for line in f:
            if line[0] == "#" or len(line) < 2:
                continue
            while line[0] == " ":
                line = line[1:]
            # strip new line symbol
            line = line[:-1]

            # check if init
            if line[0] == "(" and line[-1] == ")":
                if init_state:
                    raise RuntimeError("two initial states specified")
                init_state = line[1:-1].replace(" ", "")
                if init_state not in states:
                    states.append(init_state)

            # check if label
            elif line[:5].upper() == "ATOMS":
                line = line.split(" ")
                atom = line[1].replace(" ", "")
                labeled_states = "".join(line[2:])
                labeled_states = labeled_states.replace(" ", "")
                labeled_states = labeled_states.split(",")
                for s in labeled_states:
                    if s not in labels:
                        labels[s] = []
                    labels[s].append(atom)

            # check if transition
            elif " --> " in line:
                trans = line.split(" --> ")
                trans_src = trans[0].replace(" ", "")
                trans_tar = trans[1]
                if trans_src not in states:
                    states.append(trans_src)
                # figure out target case
                x = trans_tar.split("<")
                tar_state = x[0].replace(" ", "")
                tar_tape = x[1][:x[1].find(">")]
                if " " not in tar_tape:
                    tar_rsm_state = tar_state + "<" + tar_tape + ">"
                    if tar_rsm_state not in states:
                        states.append(tar_rsm_state)
                    if trans_src not in transitions:
                        transitions[trans_src] = []
                    transitions[trans_src].append(tar_rsm_state)
                elif tar_tape == " ":
                    tar_rsm_state = tar_state
                    if tar_rsm_state not in states:
                        states.append(tar_rsm_state)
                    if tar_rsm_state not in exit_states:
                        exit_states.append(tar_rsm_state)
                    if trans_src not in transitions:
                        transitions[trans_src] = []
                    transitions[trans_src].append(tar_rsm_state)
                else:
                    tapes = tar_tape.split(" ")
                    if len(tapes) > 2:
                        raise RuntimeError("at following line: " + line)
                    t1 = tapes[0]
                    t2 = tapes[1]
                    if t2 not in boxes:
                        # set of entry/exit nodes
                        boxes[t2] = ([], [])
                    tar_rsm_state = "[" + tar_state + "<" + t1 + ">]"
                    if tar_rsm_state not in boxes[t2][0]:
                        boxes[t2][0].append(tar_rsm_state)
                    if tar_state + "<" + t1 + ">" not in states:
                        states.append(tar_state + "<" + t1 + ">")
                    if tar_rsm_state not in states:
                        entry_states.append(tar_rsm_state)
                        states.append(tar_rsm_state)
                        transitions[tar_rsm_state] = [tar_rsm_state[1:-1]]
                    if trans_src not in transitions:
                        transitions[trans_src] = []
                    transitions[trans_src].append((t2, tar_rsm_state))

            else:
                raise RuntimeError("at line: " + line)

        for ex in exit_states:
            for b in boxes:
                target = ex + "<" + b + ">"
                if target not in states:
                    states.append(target)
                transitions[(b, ex)] = [target]
                boxes[b][1].append(ex)

        # Construct RSM #

        component = rsm.Component("main")

        for s in states:
            n = rsm.Node(s)
            component.add_node(n)
            for labeled_state in labels:
                if labeled_state in s:
                    for lbl in labels[labeled_state]:
                        component.add_label(n, lbl)
        for ex in exit_states:
            exit_node = component.get_node_by_name(ex)
            component.make_exit_node(exit_node)
        for en in entry_states:
            entry_node = component.get_node_by_name(en)
            component.make_entry_node(entry_node)

        for b in boxes:
            entries = [component.get_node_by_name(en) for en in boxes[b][0]]
            exits = [component.get_node_by_name(ex) for ex in boxes[b][1]]
            box = rsm.Box(component, b, entries, exits)
            component.add_box(box)

        for source in transitions:
            for target in transitions[source]:
                if isinstance(target, tuple):
                    target = component.get_call_node_by_name(target[0], target[1])
                elif isinstance(target, str):
                    target = component.get_node_by_name(target)
                if isinstance(source, tuple):
                    source = component.get_return_node_by_name(source[0], source[1])
                elif isinstance(source, str):
                    source = component.get_node_by_name(source)
                component.add_transition(source, target)

        res = rsm.RSM()
        res.components = [component]
        res.initial_component = component
        res.initial_node = component.get_node_by_name(init_state)

        return res


def write_rsm(path_to_file, machine, pretty=False):
    machine_dict = {
        "initial_component": machine.initial_component.name,
        "initial_node": machine.initial_node.name,
        "components": []
    }
    for component in machine.components:
        component_dict = {
            "name": component.name,
            "nodes": [],
            "boxes": [],
            "transitions": []
        }

        for n in component.nodes:
            if isinstance(n, rsm.Node):
                node_dict = component.nodes[n]
                node_dict["name"] = n.name
                node_dict["labels"] = list(node_dict["labels"])
                component_dict["nodes"].append(node_dict)

        for b in component.boxes:
            box_dict = {
                "name": b.name,
                "component": b.component.name,
                "call_nodes": [n.name for n in b.call_nodes],
                "return_nodes": [n.name for n in b.return_nodes]
            }
            component_dict["boxes"].append(box_dict)

        for source in component.transitions:
            trans_dict = {}
            source_dict = {}
            if isinstance(source, rsm.Node):
                source_dict["name"] = source.name
                source_dict["type"] = "node"
            if isinstance(source, rsm.BoxNode):
                source_dict["box_name"] = source.box.name
                source_dict["node_name"] = source.node.name
                source_dict["type"] = "box_node"
            trans_dict["source"] = source_dict

            trans_dict["targets"] = []
            for target in component.transitions[source]:
                target_dict = {}
                if isinstance(target, rsm.Node):
                    target_dict["name"] = target.name
                    target_dict["type"] = "node"
                if isinstance(target, rsm.BoxNode):
                    target_dict["box_name"] = target.box.name
                    target_dict["node_name"] = target.node.name
                    target_dict["type"] = "box_node"
                trans_dict["targets"].append(target_dict)
            component_dict["transitions"].append(trans_dict)

        machine_dict["components"].append(component_dict)

    with open(path_to_file, 'w') as f:
        if pretty:
            f.write(json.dumps(machine_dict, indent=4, separators=(',', ': ')))
        else:
            f.write(json.dumps(machine_dict))


def main():
    parser = argparse.ArgumentParser(description="Convert a .pds file into an .rsm file")
    parser.add_argument("path_to_pds", help="path to .pds file")
    parser.add_argument("-pretty",
                        action="store_true",
                        help="add proper indentation the output file for readability at the cost of space")
    parser.add_argument("--out",
                        metavar="path_to_rsm",
                        help="path to desired .rsm file, defaults to same as source with .rsm file ending")

    args = parser.parse_args()
    source_file = args.path_to_pds
    dot_index = source_file.find(".pds")
    auto_target_file = source_file + ".rsm" if dot_index == -1 else source_file[:dot_index] + ".rsm"
    target_file = args.out or auto_target_file

    m = read_pds(source_file)
    write_rsm(target_file, m, args.pretty)


if __name__ == "__main__":
    main()
