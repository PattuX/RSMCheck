"""
Collection of functions to determine the truth value of a CTL in a node
"""
import random
from utils import *
from ctl_parser import get_subformulas
import logging
from collections import defaultdict
from enum import Enum

num_contexts_built = 0
num_contexts_relabeled = 0
# track which components we tried to unpack in last exhaustive iteration so we detect fixed points
last_boxes_to_unpack = set()
# keep track of which CTL have been requested in which nodes for lazy unpacking
requested_nodes = defaultdict(set)
# keep track of which CTL have been requested in which nodes for lazy unpacking in the current call stack
requested_node_chain = defaultdict(list)
# keep track of boxes entered while searching for box to unpack
box_stack = []
# keep track of component entered
component_stack = []
# save which node/ctl pair was requested twice so we can continue when we implicitly detect a cycle while unpacking
double_requests = set()
# keep track of formulas which are fully known in the whole RSM
known_formulas = set()


class ExpansionHeuristics(Enum):
    GETNEXT = 1
    RANDOM = 2
    ALL = 3


def check_exhaustive(machine, ctl):
    """
    Simple script doing exhaustive checking for comparison mainly.
    Whenever a new box with unknown context (i.e. value of CTL in return nodes) is encountered, it is fully unpacked
    to determine the truth value of CTL in call nodes, regardless of whether that's actually required.
    The result will be an RSM in which all formulas are known in all (reachable) possible states, so no target node
    needs to be specified. Also no return is necessary since the whole machine (i.e. all its nodes) will be annotated.

    :param machine: the RSM to check against
    :param ctl: the ctl to check
    """

    # initial_machine = deepcopy(machine)

    global num_contexts_built
    global num_contexts_relabeled
    num_contexts_built = 0
    init_contexts_built = 0

    subformulas = get_subformulas(ctl)

    top_level_existential_formulas = []
    top_level_formulas = [ctl]
    while top_level_formulas:
        next_top_level_formulas = []
        for f in top_level_formulas:
            if isinstance(f, CTL.E):
                top_level_existential_formulas.append(f)
            else:
                next_top_level_formulas += f.subformulas()
        top_level_formulas = next_top_level_formulas

    # iterate via range to guarantee correct order of depths
    for depth in range(max(subformulas.keys()) + 1):
        for f in subformulas[depth]:
            if not isinstance(f, CTL.E):
                for comp in machine.contextualized_components:
                    for node in comp.base_component.nodes:
                        check_locally(node, comp, f)
            else:
                name_appendix = "_init" + str(init_contexts_built)
                init_contexts_built += 1
                machine.initialize_single(f, name_appendix)
                machine.remove_unreachable_components()
                # TODO: restore finish early functionality
                finish_early = f in top_level_existential_formulas
                # uncomment for full exhaustive run
                # finish_early = False

                while check_existential_formula_exhaustive(machine, f, finish_early):
                    pass

    num_contexts_built += init_contexts_built

    logging.debug("Built a total of " + str(num_contexts_built) + " contexts (plus " + str(num_contexts_relabeled) +
                  " context relabels)")


def check_existential_formula_exhaustive(machine, f, finish_early=False):
    """
    Find value for f in all nodes of machine. Build context if necessary. Return whether another step is necessary.
    """
    global num_contexts_built
    global num_contexts_relabeled

    if finish_early:
        found_target = check_existential_formula(machine, f)
        if found_target:
            logging.debug("Determined CTL (" + str(f) + ") in initial node")
            return False
    else:
        check_existential_formula(machine, f)

    machine.remove_unreachable_components()

    # collect boxes which have information that their referenced component does not have
    boxes_to_unpack = set()
    for c in machine.contextualized_components:
        for box in c.base_component.boxes:
            ref_component = c.box_mapping[box]
            for rn in box.return_nodes:
                if f not in ref_component.interpretation[rn.node]:
                    boxes_to_unpack.add((c, box))
                    continue

    if all(f in i for c in machine.contextualized_components for n, i in c.interpretation.items()):
        logging.debug("Determined CTL (" + str(f) + ") in all nodes")
        return False

    for c, box in boxes_to_unpack:
        #print("unpacking ", box, c.context)
        context_existed = c.contextualize_box(box)
        if context_existed:
            num_contexts_relabeled += 1
        else:
            num_contexts_built += 1

    global last_boxes_to_unpack
    if last_boxes_to_unpack == boxes_to_unpack:
        assert isinstance(f.subformula(0), CTL.G) or isinstance(f.subformula(0), CTL.U)
        for c in machine.contextualized_components:
            for n, i in c.interpretation.items():
                if f not in i:
                    i[f] = True if isinstance(f.subformula(0), CTL.G) else False
    last_boxes_to_unpack = boxes_to_unpack

    return True


def check_lazy(machine, ctl, expansion_heuristic, randomize_nondeterminism=False):
    """
    Function doing lazy checking.
    At first, only the initial context is built and all formulas are deduced as far as possible. If the CTL is not known
    in the initial node, then we figure out which context to build next and again deduce all formulas.
    We continue like this until CTL is known in initial node.

    :param machine: the RSM to check against
    :param ctl: the ctl to check
    :param expansion_heuristic: expansion heuristic to use when choosing boxes to unpack
    :param randomize_nondeterminism: whether to randomize nondeterministic choices in GetNextExpansion
    """

    global requested_nodes
    global requested_node_chain
    global box_stack
    global component_stack
    global double_requests
    global num_contexts_built
    global num_contexts_relabeled

    # initialization in exit nodes is not necessary for local properties
    if "E" in str(ctl):
        machine.initialize(ctl)
    num_contexts_built = 1
    machine.remove_unreachable_components()

    complete_machine_for_all_subformulas(machine, ctl)

    # do lazy unpacking
    while ctl not in machine.initial_component.interpretation[machine.initial_node]:
        to_contextualize = []
        # find box(ex) to unpack
        if expansion_heuristic == ExpansionHeuristics.GETNEXT:
            # full lazy, one heuristically chosen box
            requested_nodes = defaultdict(set)
            requested_node_chain = defaultdict(list)
            box_stack = []
            component_stack = [machine.initial_component]
            double_requests = set()

            result = find_next_necessary_context(machine, machine.initial_node, ctl, randomize_nondeterminism)
            to_contextualize = [result] if result is not None else []
        else:
            contextualizable_boxes = []
            for c in machine.contextualized_components:
                for box in c.base_component.boxes:
                    ref_component = c.box_mapping[box]
                    for rn in box.return_nodes:
                        for f in ctl.subformulas():
                            if f not in ref_component.interpretation[rn.node] \
                                    and f in c.interpretation[rn]:
                                contextualizable_boxes.append((box, c))
            if expansion_heuristic == ExpansionHeuristics.RANDOM:
                # random lazy, one randomly chosen box
                to_contextualize = [random.choice(contextualizable_boxes)] if contextualizable_boxes else []
            elif expansion_heuristic == ExpansionHeuristics.ALL:
                # exhaustive contextualization but ternary checking
                to_contextualize = contextualizable_boxes

        if to_contextualize:
            # unpack box(es)
            for last_box, last_component in to_contextualize:
                context_existed = last_component.contextualize_box(last_box)
                if context_existed:
                    num_contexts_relabeled += 1
                else:
                    num_contexts_built += 1
        else:
            if expansion_heuristic == ExpansionHeuristics.GETNEXT:
                # could not properly determine next box to determine by standard decision tree
                if not double_requests:
                    # if no double request happened something went horribly wrong
                    raise ValueError("Something went wrong while computing the next box to unpack")
                else:
                    # otherwise we detected a cycle
                    for (component, node), f in double_requests:
                        path_formula = f.subformula(0)
                        if isinstance(path_formula, CTL.G):
                            # if we found a phi-cycle for EG phi, the CTL is true by definition
                            component.interpretation[node][f] = True
                        if isinstance(path_formula, CTL.U):
                            # here we found an phi1-and-not-phi2-cycle for E phi1 U phi 2
                            # further we checked all branches while searching the next box toi unpack through backtracking
                            # this means no phi2 is reachable and thus the CTL is false
                            component.interpretation[node][f] = False
            else:
                # if GetNext was not used as expansion heuristic we can only safely do global cycle resolution
                # for a formula if all its subformulas are known everywhere, so here we find such formulas
                subformulas = get_subformulas(ctl)
                # iterate via range to guarantee correct order of depths
                found_unknown = False
                for depth in range(max(subformulas.keys()) + 1):
                    for f in subformulas[depth]:
                        for c in machine.contextualized_components:
                            for n in c.base_component.nodes:
                                if f not in c.interpretation[n]:
                                    path_formula = f.subformula(0)
                                    if isinstance(path_formula, CTL.G):
                                        found_unknown = True
                                        c.interpretation[n][f] = True
                                    if isinstance(path_formula, CTL.U):
                                        found_unknown = True
                                        c.interpretation[n][f] = False
                    if found_unknown:
                        break

        machine.remove_unreachable_components()
        # update machine
        complete_machine_for_all_subformulas(machine, ctl)

    logging.debug("Built a total of " + str(num_contexts_built) + " contexts (plus " + str(num_contexts_relabeled) +
                  " context relabels)")


def find_next_necessary_context(machine, node, ctl, randomize_nondeterminism):
    """
    For a machine in which CTL is not known in node, figure out which context to build next to deduce CTL in node
    by the following rules:
    * if CTL is local (not, and, or), we request the next necessary expansion for some unknown subformula
    * if the node is an exit node, we check if the CTL is known in the corresponding return node
        if it is, we can unpack the box
        if it is not, we request it in that return node
    * if the node is a call node we propagate the request into the box
    * if CTL is EG phi we first request the necessary expansion to know phi in node (if it isn't known already).
        Then we request knowing EG phi for some successor in which it is unknown
    * if CTL is EX phi we request knowing phi for some successor in which it is unknown
    * if CTL is E (phi_1 U phi_2) we request in the following order, if the respective fact is unknown:
        - phi_2 is known in node
        - phi_1 is known in node
        - E (phi_1 U phi_2) is known in successors
    if the node is an exit node and the CTL is existential, the only way to determine the CTL is through context,
    so we keep track of the last box we entered and request context unpacking wrt that box

    if the subsequent call wasn't successful (i..e, returned None), we simply try the next option

    :return: the box which needs context unpacking with respect to which CTL
    """
    global requested_nodes
    global requested_node_chain
    global box_stack
    global component_stack
    global double_requests

    current_component = component_stack[-1]
    cn_pair = (current_component, node)

    # track for which nodes the current formula has already been requested
    requested_nodes[ctl].add(cn_pair)
    requested_node_chain[ctl].append(cn_pair)

    if ctl in current_component.interpretation[node]:
        raise ValueError("Requesting a CTL in a node despite the formula being known in the node\n"
                         "CTL: " + str(ctl) + "\nNode: " + str(node))

    if isinstance(ctl, CTL.Not) or isinstance(ctl, CTL.Or) or isinstance(ctl, CTL.And):
        subformulas = ctl.subformulas()
        if randomize_nondeterminism:
            random.shuffle(subformulas)
        for sub in subformulas:
            if sub not in current_component.interpretation[node]:
                if cn_pair not in requested_nodes[sub]:
                    # reset double requested nodes since cycle detection only works if all subformulas are known
                    res = find_next_necessary_context(machine, node, sub, randomize_nondeterminism)
                    if res is not None:
                        requested_node_chain[ctl].pop()
                        return res
        return None

    if node.parent_component.is_exit(node):
        last_component = component_stack[-2]
        last_box = box_stack[-1]
        return_node = None
        # search for corresponding return node
        for bn in last_box.return_nodes:
            if bn.node == node:
                return_node = bn
                break
        if return_node is None:
            raise ValueError("Could not match " + str(node) + " to any return node of " + str(last_box))
        # check if CTL is known in return node
        if ctl in last_component.interpretation[return_node]:
            # if yes, unpack
            requested_node_chain[ctl].pop()
            return last_box, last_component
        else:
            # if not, go to return node, deleting the last stack element, and continue searching
            last_box_elem = box_stack.pop()
            last_comp_elem = component_stack.pop()
            res = find_next_necessary_context(machine, return_node, ctl, randomize_nondeterminism)
            if res is not None:
                requested_node_chain[ctl].pop()
                return res
            # if backtracking is necessary, restore stack elements
            box_stack.append(last_box_elem)
            component_stack.append(last_comp_elem)

    # for call nodes, go into the box and put box on stack
    # for the special case where the box node is both call and return node, we do not go into the box
    if isinstance(node, rsm.BoxNode) and node.is_call_node and not node.is_return_node:
        ref_component = current_component.box_mapping[node.box]
        if (ref_component, node.node) not in requested_nodes[ctl]:
            box_stack.append(node.box)
            component_stack.append(ref_component)
            res = find_next_necessary_context(machine, node.node, ctl, randomize_nondeterminism)
            if res is not None:
                requested_node_chain[ctl].pop()
                return res
            # if backtracking is necessary, restore original stacks
            box_stack.pop()
            component_stack.pop()

    if isinstance(ctl, CTL.E):
        path_formula = ctl.subformula(0)

        if isinstance(path_formula, CTL.G):
            sub = path_formula.subformula(0)
            if sub not in current_component.interpretation[node]:
                # reset double requested nodes since cycle detection only works if all subformulas are known
                if cn_pair not in requested_nodes[sub]:
                    res = find_next_necessary_context(machine, node, sub, randomize_nondeterminism)
                    if res is not None:
                        requested_node_chain[ctl].pop()
                        return res
            successors = node.parent_component.transitions[node]
            if randomize_nondeterminism:
                random.shuffle(successors)
            for succ in successors:
                if ctl not in current_component.interpretation[succ]:
                    if (current_component, succ) not in requested_nodes[ctl]:
                        res = find_next_necessary_context(machine, succ, ctl, randomize_nondeterminism)
                        if res is not None:
                            requested_node_chain[ctl].pop()
                            return res
                    elif cn_pair in requested_node_chain[ctl]:
                        idx = requested_node_chain[ctl].index(cn_pair)
                        for cnp in requested_node_chain[ctl][idx:]:
                            double_requests.add((cnp, ctl))

        elif isinstance(path_formula, CTL.U):
            sub1 = path_formula.subformula(0)
            sub2 = path_formula.subformula(1)
            if sub2 not in current_component.interpretation[node]:
                # reset double requested nodes since cycle detection only works if all subformulas are known
                if cn_pair not in requested_nodes[sub2]:
                    res = find_next_necessary_context(machine, node, sub2, randomize_nondeterminism)
                    if res is not None:
                        requested_node_chain[ctl].pop()
                        return res
            if sub1 not in current_component.interpretation[node]:
                # reset double requested nodes since cycle detection only works if all subformulas are known
                if cn_pair not in requested_nodes[sub1]:
                    res = find_next_necessary_context(machine, node, sub1, randomize_nondeterminism)
                    if res is not None:
                        requested_node_chain[ctl].pop()
                        return res
            successors = node.parent_component.transitions[node]
            if randomize_nondeterminism:
                random.shuffle(successors)
            for succ in successors:
                if ctl not in current_component.interpretation[succ]:
                    if (current_component, succ) not in requested_nodes[ctl]:
                        res = find_next_necessary_context(machine, succ, ctl, randomize_nondeterminism)
                        if res is not None:
                            requested_node_chain[ctl].pop()
                            return res
                    elif cn_pair in requested_node_chain[ctl]:
                        idx = requested_node_chain[ctl].index(cn_pair)
                        for cnp in requested_node_chain[ctl][idx:]:
                            double_requests.add((cnp, ctl))

        if isinstance(path_formula, CTL.X):
            sub = path_formula.subformula(0)
            successors = node.parent_component.transitions[node]
            if randomize_nondeterminism:
                random.shuffle(successors)
            for succ in successors:
                if sub not in current_component.interpretation[succ]:
                    # reset double requested nodes since cycle detection only works if all subformulas are known
                    if (current_component, succ) not in requested_nodes[ctl]:
                        res = find_next_necessary_context(machine, succ, sub, randomize_nondeterminism)
                        if res is not None:
                            requested_node_chain[ctl].pop()
                            return res
    requested_node_chain[ctl].pop()
    return None


def complete_machine_for_all_subformulas(machine, ctl):
    """
    Deduce all subformulas in all nodes of machine as far as possible.
    """
    global known_formulas
    subformulas = get_subformulas(ctl)
    # formulas already checked in this run (in case a formula appears multiple times as a sb
    checked_formulas = set()

    # iterate via range to guarantee correct order of depths
    for depth in range(max(subformulas.keys()) + 1):
        for f in subformulas[depth]:
            if f in checked_formulas or f in known_formulas:
                continue
            if not isinstance(f, CTL.E):
                f_known_in_all_nodes = True
                for comp in machine.contextualized_components:
                    for node in comp.base_component.nodes:
                        determined_f_in_node = check_locally(node, comp, f)
                        f_known_in_all_nodes = f_known_in_all_nodes and determined_f_in_node
                        checked_formulas.add(f)
                if f_known_in_all_nodes:
                    known_formulas.add(f)
            else:
                check_existential_formula(machine, f)
                checked_formulas.add(f)
                if all(f in i for c in machine.contextualized_components for n, i in c.interpretation.items()):
                    known_formulas.add(f)
