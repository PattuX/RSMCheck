"""" Module to parse .rsm files """

from model import rsm
import json


def parse_rsm(path_to_file):
    with open(path_to_file) as f:
        rsm_dict = json.loads(f.read())

        machine = rsm.RSM()

        # create blank components
        for c in rsm_dict["components"]:
            component = rsm.Component(c["name"])
            machine.add_base_component(component)

        # create nodes and add them to component
        for c in rsm_dict["components"]:
            component = machine.get_base_component_by_name(c["name"])
            for n in c["nodes"]:
                node = rsm.Node(n["name"])
                component.add_node(node)
                for label in n["labels"]:
                    component.add_label(node, label)
                if n["is_entry"]:
                    component.make_entry_node(node)
                if n["is_exit"]:
                    component.make_exit_node(node)

        # set initial component and node
        machine.initial_component = machine.get_base_component_by_name(rsm_dict["initial_component"])
        machine.initial_node = machine.initial_component.get_node_by_name(rsm_dict["initial_node"])

        # create boxes
        for c in rsm_dict["components"]:
            component = machine.get_base_component_by_name(c["name"])
            for b in c["boxes"]:
                name = b["name"]
                ref_comp = machine.get_base_component_by_name(b["component"])
                call_nodes = []
                for n in b["call_nodes"]:
                    to_add = ref_comp.get_node_by_name(n)
                    if to_add is None:
                        raise ValueError("Box " + name + " references invalid node " + n +
                                         " in component " + b["component"])
                    else:
                        call_nodes.append(to_add)
                return_nodes = []
                for n in b["return_nodes"]:
                    to_add = ref_comp.get_node_by_name(n)
                    if to_add is None:
                        raise ValueError("Box " + name + " references invalid node " + n +
                                         " in component " + b["component"])
                    else:
                        return_nodes.append(to_add)
                box = rsm.Box(ref_comp, name, call_nodes, return_nodes)
                component.add_box(box)

        # set transitions
        for c in rsm_dict["components"]:
            component = machine.get_base_component_by_name(c["name"])
            for trans in c["transitions"]:
                source = trans["source"]
                if source["type"] == "node":
                    source = component.get_node_by_name(source["name"])
                elif source["type"] == "box_node":
                    if not trans["targets"]:
                        continue
                    source = component.get_return_node_by_name(source["box_name"], source["node_name"])
                else:
                    raise ValueError("Invalid type for transition source: " + source["type"])
                if source is None:
                    raise ValueError("Source node of transition not found: " + trans["source"]["name"] +
                                     " in component " + c["name"])

                for target in trans["targets"]:
                    if target["type"] == "node":
                        t_name = target["name"]
                        target = component.get_node_by_name(t_name)
                    elif target["type"] == "box_node":
                        t_name = target["box_name"] + "-" + target["node_name"]
                        target = component.get_call_node_by_name(target["box_name"], target["node_name"])
                    else:
                        raise ValueError("Invalid type for transition source: " + target["type"])
                    if target is None:
                        raise ValueError("Target node of transition not found: " + t_name +
                                         " in component " + c["name"])

                    component.add_transition(source, target)

        # add empty context to everything
        for component in machine.base_components:
            contextualized_component =\
                rsm.ContextualizedComponent(machine, component, "", component.generate_empty_context())
            machine.add_contextualized_component(contextualized_component)
            if machine.initial_component == component:
                machine.initial_component = contextualized_component

        for component in machine.contextualized_components:
            for box in component.base_component.boxes:
                ref = box.component
                contextualized_ref = machine.get_contextualized_component(ref, ref.generate_empty_context())
                component.box_mapping[box] = contextualized_ref

        return machine
