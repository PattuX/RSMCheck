""" Collection of useful functions
"""

from pyModelChecking import CTL
from model import rsm


# Exception class for nested break statements
class Found(Exception):
    pass


def check_locally(node, component, ctl):
    """
    Simple procedure to deduce local properties, i.e. AP, Not, And, Or formulas by looking at formulas
    which are already known to (not) hold in that state or its successors.

    :param node: RSM node
    :param component: the component the node is in
    :param ctl: CTL formula to check against
    :return: bool whether finding the truth value of the CTL was successful.
             Note that this is also True if the formula was found to be False!
    """

    node_interpretation = component.interpretation[node]

    if isinstance(ctl, CTL.Bool):
        if str(ctl) == "true":
            node_interpretation[ctl] = True
        else:
            node_interpretation[ctl] = False
        return True

    if isinstance(ctl, CTL.AtomicProposition):
        ap = str(ctl)
        node_interpretation[ctl] = component.base_component.has_label(node, ap)
        return True

    if isinstance(ctl, CTL.E) or isinstance(ctl, CTL.A):
        raise ValueError("Can't check temporal operators locally")

    if isinstance(ctl, CTL.Not):
        if ctl.subformula(0) not in node_interpretation:
            return False
        node_interpretation[ctl] = not node_interpretation[ctl.subformula(0)]
        return True

    if isinstance(ctl, CTL.And):
        has_unknown = False
        for sub in ctl.subformulas():
            if sub not in node_interpretation:
                has_unknown = True
                continue
            if not node_interpretation[sub]:
                node_interpretation[ctl] = False
                return True
        if not has_unknown:
            node_interpretation[ctl] = True
            return True
        return False

    if isinstance(ctl, CTL.Or):
        has_unknown = False
        for sub in ctl.subformulas():
            if sub not in node_interpretation:
                has_unknown = True
                continue
            if node_interpretation[sub]:
                node_interpretation[ctl] = True
                return True
        if not has_unknown:
            node_interpretation[ctl] = False
            return True
        return False


def check_next(machine, ctl):
    """
    For an EX type CTL, figure out its value in the machine's nodes

    :param machine: The machine to check
    :param ctl: The CTL to check against
    :raises: ValueError: if wrong CTL type is given
    :return: True iff a target node was successfully computed
    """

    path_formula = ctl.subformula(0)
    sub = path_formula.subformula(0)

    if not isinstance(ctl, CTL.E) and not isinstance(path_formula, CTL.X):
        raise ValueError("CTL for context completion must be of form EX")

    for c in machine.contextualized_components:
        for node in c.base_component.nodes:
            # for exit node it can only be deduced via context
            if c.base_component.is_exit(node):
                if ctl in c.context[node]:
                    c.interpretation[node][ctl] = c.context[node][ctl]
                continue

            has_unknown = False
            try:
                successors = c.base_component.transitions[node]
                for s in successors:
                    if sub not in c.interpretation[s]:
                        has_unknown = True
                        continue
                    if c.interpretation[s][sub]:
                        c.interpretation[node][ctl] = True
                        raise Found

                if isinstance(node, rsm.BoxNode) and node.is_call_node:
                    ref_component = c.box_mapping[node.box]
                    box_successors = ref_component.base_component.transitions[node.node]
                    for s in box_successors:
                        if sub not in ref_component.interpretation[s]:
                            has_unknown = True
                            continue
                        if ref_component.interpretation[s][sub]:
                            c.interpretation[node][ctl] = True
                            raise Found

            except Found:
                continue
            # if no successor was found and no unknown successors are present the CTL is False
            if not has_unknown:
                c.interpretation[node][ctl] = False

    return False


def check_until(machine, ctl):

    path_formula = ctl.subformula(0)
    sub1 = path_formula.subformula(0)
    sub2 = path_formula.subformula(1)

    ###################
    # pessimistic run #
    ###################

    sat = set()
    to_determine = set()

    # obvious deductions
    for contextualized_component in machine.contextualized_components:
        for node, node_interpretation in contextualized_component.interpretation.items():
            # don't search for truth value if it's already known
            if ctl in node_interpretation:
                if node_interpretation[ctl] is True:
                    sat.add((contextualized_component, node))
                continue
            else:
                # if exit node has ctl as true in context (i.e. outside path exists), then ctl is true
                if contextualized_component.base_component.is_exit(node) and \
                        ctl in contextualized_component.context[node]:
                    if contextualized_component.context[node][ctl] is True:
                        sat.add((contextualized_component, node))
                    continue
                # if phi_2 is true, then ctl is true
                if sub2 in node_interpretation and node_interpretation[sub2] is True:
                    sat.add((contextualized_component, node))
                    continue
                # if phi_1 is pessimistically false, we do not add it to search space
                if sub1 not in node_interpretation or node_interpretation[sub1] is False:
                    continue

            # if value still not known, add it to search space
            to_determine.add((contextualized_component, node))

    # here we know all nodes in to_determine pessimistically satisfy phi_1 and all nodes in sat satisfy ctl
    # so we add nodes from to_determine to sat if they have a sat successor until we reach a fixed point

    while True:
        next_to_determine = set()
        for contextualized_component, node in to_determine:
            base_component = contextualized_component.base_component

            successors = [(contextualized_component, s) for s in base_component.transitions[node]]
            box_successors = []
            if isinstance(node, rsm.BoxNode) and node.is_call_node:
                ref_component = contextualized_component.box_mapping[node.box]
                box_successors = [(ref_component, s) for s in ref_component.base_component.transitions[node.node]]

            for successor in successors + box_successors:
                if successor in sat:
                    sat.add((contextualized_component, node))
                    break
            else:
                next_to_determine.add((contextualized_component, node))

        if len(to_determine) == len(next_to_determine):
            break

        to_determine = next_to_determine

    # what is true pessimistically is definitely true
    for contextualized_component, node in sat:
        contextualized_component.interpretation[node][ctl] = True

    ##################
    # optimistic run #
    ##################

    sat = set()
    to_determine = set()

    # obvious deductions
    for contextualized_component in machine.contextualized_components:
        for node, node_interpretation in contextualized_component.interpretation.items():
            # don't search for truth value if it's already known
            if ctl in node_interpretation:
                if node_interpretation[ctl] is True:
                    sat.add((contextualized_component, node))
                continue
            else:
                # if exit node does not have ctl in context, or it's true in context (i.e. outside path exists),
                # then ctl is optimistically true in exit node
                # otherwise it's definitely false and we do not add it to search space
                if contextualized_component.base_component.is_exit(node):
                    if ctl not in contextualized_component.context[node] or \
                            contextualized_component.context[node][ctl] is True:
                        sat.add((contextualized_component, node))
                    continue
                # if phi_2 is true or unknown, ctl is optimistically satisfied
                if sub2 not in node_interpretation or node_interpretation[sub2] is True:
                    sat.add((contextualized_component, node))
                    continue
                # only if we know for sure phi_1 does not hold, we exclude node from search space
                if sub1 in node_interpretation and node_interpretation[sub1] is False:
                    continue

            # if value still not known and node wasn't excluded, add it to search space
            to_determine.add((contextualized_component, node))

    # here we know all nodes in to_determine optimistically satisfy phi_1 and all nodes in sat satisfy ctl
    # so we add nodes from to_determine to sat if they have a sat successor until we reach a fixed point

    while to_determine:
        next_to_determine = set()
        for contextualized_component, node in to_determine:
            base_component = contextualized_component.base_component

            successors = [(contextualized_component, s) for s in base_component.transitions[node]]
            box_successors = []
            if isinstance(node, rsm.BoxNode) and node.is_call_node:
                ref_component = contextualized_component.box_mapping[node.box]
                box_successors = [(ref_component, s) for s in ref_component.base_component.transitions[node.node]]

            for successor in successors + box_successors:
                if successor in sat:
                    sat.add((contextualized_component, node))
                    break
            else:
                next_to_determine.add((contextualized_component, node))

        if len(to_determine) == len(next_to_determine):
            break

        to_determine = next_to_determine

    ###############
    # end of runs #
    ###############

    # what is false optimistically, is definitely false

    for contextualized_component in machine.contextualized_components:
        for node, node_interpretation in contextualized_component.interpretation.items():
            if ctl not in node_interpretation and (contextualized_component, node) not in sat:
                node_interpretation[ctl] = False


def check_always(machine, ctl):
    sub = ctl.subformula(0).subformula(0)

    sat = set()

    ###################
    # pessimistic run #
    ###################

    # initialization
    for contextualized_component in machine.contextualized_components:
        for node, node_interpretation in contextualized_component.interpretation.items():
            # don't search for truth value if it's already known
            if ctl in node_interpretation:
                if node_interpretation[ctl] is True:
                    sat.add((contextualized_component, node))
                continue
            else:
                # in exit nodes the ctl is only true if it is in context, otherwise it's pessimistically false
                if contextualized_component.base_component.is_exit(node):
                    if ctl in contextualized_component.context[node] and \
                            contextualized_component.context[node][ctl] is True:
                        sat.add((contextualized_component, node))
                # all nodes with phi_1 true may pessimistically satisfy ctl
                elif sub in node_interpretation and node_interpretation[sub] is True:
                    sat.add((contextualized_component, node))

    # here we know all nodes in sat pessimistically satisfy phi_1
    # we now throw out all nodes w/o a sat-successor until we reach a fixed point

    while True:
        new_sat = sat.copy()

        for contextualized_component, node in sat:
            base_component = contextualized_component.base_component

            # dont remove context
            if base_component.is_exit(node) and ctl in contextualized_component.context[node] and \
                    contextualized_component.context[node][ctl] is True:
                continue

            # dont remove nodes where we know the truth value (e.g. by cycle detection)
            if ctl in contextualized_component.interpretation[node]:
                continue

            successors = [(contextualized_component, s) for s in base_component.transitions[node]]
            box_successors = []
            if isinstance(node, rsm.BoxNode) and node.is_call_node:
                ref_component = contextualized_component.box_mapping[node.box]
                box_successors = [(ref_component, s) for s in ref_component.base_component.transitions[node.node]]

            # dont remove nodes with implicit self loops
            if len(successors + box_successors) == 0:
                continue

            # if we dont find a successor in the pessimistically satisfying set, remove node from sat
            for successor in successors + box_successors:
                if successor in sat:
                    break
            else:
                new_sat.remove((contextualized_component, node))

        if len(new_sat) == len(sat):
            break

        sat = new_sat

    # what is true pessimistically, is definitely true

    for contextualized_component, node in sat:
        contextualized_component.interpretation[node][ctl] = True

    ##################
    # optimistic run #
    ##################

    sat = set()

    # initialization
    for contextualized_component in machine.contextualized_components:
        for node, node_interpretation in contextualized_component.interpretation.items():
            # don't search for truth value if it's already known
            if ctl in node_interpretation:
                if node_interpretation[ctl] is True:
                    sat.add((contextualized_component, node))
                continue
            else:
                # if exit node has ctl in context then we know CTL truth value
                if contextualized_component.base_component.is_exit(node) and \
                        ctl in contextualized_component.context[node]:
                    if contextualized_component.context[node][ctl] is True:
                        sat.add((contextualized_component, node))
                    continue
                # for non-exit nodes and when ctl is not in context for exit nodes, we optimistically assume
                # satisfaction if the subformula is true or unknown
                if sub not in node_interpretation or node_interpretation[sub] is True:
                    sat.add((contextualized_component, node))
                    continue

    # here we know all nodes in sat optimistically satisfy phi_1
    # we now throw out all nodes w/o a sat-successor until we reach a fixed point

    while True:
        new_sat = sat.copy()

        for contextualized_component, node in sat:
            base_component = contextualized_component.base_component

            # dont remove context
            if base_component.is_exit(node) and ctl in contextualized_component.context[node] \
                    and contextualized_component.context[node][ctl] is True:
                continue

            successors = [(contextualized_component, s) for s in base_component.transitions[node]]
            box_successors = []
            if isinstance(node, rsm.BoxNode) and node.is_call_node:
                ref_component = contextualized_component.box_mapping[node.box]
                box_successors = [(ref_component, s) for s in ref_component.base_component.transitions[node.node]]

            # dont remove nodes with implicit self loops
            if len(successors + box_successors) == 0:
                continue

            # if we dont find a successor in the optimistically satisfying set, remove node from sat
            for successor in successors + box_successors:
                if successor in sat:
                    break
            else:
                new_sat.remove((contextualized_component, node))

        if len(new_sat) == len(sat):
            break

        sat = new_sat

    ###############
    # end of runs #
    ###############

    # what is false optimistically, is definitely false

    for contextualized_component in machine.contextualized_components:
        for node, node_interpretation in contextualized_component.interpretation.items():
            if ctl not in node_interpretation and (contextualized_component, node) not in sat:
                node_interpretation[ctl] = False


def check_existential_formula(machine, ctl):
    """
    For a CTL-formula of form EX, EG or EU calculate the value of the  CTL-formula in all nodes of the contextualized
    component as far as possible

    :param machine: RSM  for whose nodes satisfaction is to be determined
    :param ctl: EX-, EU- or EG-form CTL-formula to check against
    :raises:
        ValueError: if ctl is not of EX-, EG- or EU-form
    """

    path_formula = ctl.subformula(0)

    if not isinstance(ctl, CTL.E):
        raise ValueError("CTL for context completion must be of form EU, EG or EX")
    if not isinstance(path_formula, CTL.G) and not isinstance(path_formula, CTL.U) \
            and not isinstance(path_formula, CTL.X):
        raise ValueError("CTL for context completion must be of form EU, EG or EX")

    # handle EX formulas separately
    if isinstance(path_formula, CTL.X):
        return check_next(machine, ctl)
    # handle U/G via optimistic/pessimistic runs (see Godefroid)
    if isinstance(path_formula, CTL.U):
        return check_until(machine, ctl)
    if isinstance(path_formula, CTL.G):
        return check_always(machine, ctl)


def get_context_encoding(formulas, context, base_component):
    """
    Get the encoding of a component's context wrt a ctl as a ternary string (using 0, 1 and ?)
    """

    ctl_str = ""
    tmp_ctl_str = ""
    enc = ""

    sorted_exit_nodes = list(base_component.get_exit_nodes())
    sorted_exit_nodes.sort(key=lambda x: x.name)

    for node in sorted_exit_nodes:
        for ctl in formulas:
            if not ctl_str:
                tmp_ctl_str += str(ctl).replace(" ", "") + "/"
            if ctl not in context[node]:
                enc += "?"
            elif context[node][ctl] is True:
                enc += "1"
            else:
                enc += "0"
        if not ctl_str:
            ctl_str = tmp_ctl_str
        enc += "/"
    return "_" + ctl_str + enc[:-1]


def box_stack_to_context(machine, box_stack, component=None):
    """
    :param machine: the RSM on which the box stack is defined
    :param box_stack: a list of boxes, the first box being
    :param component: the component from which the box stack is executed. default: initial component of the RSM
    :return: contextualized component in which execution ends up in if boxes are entered in the specified order
    """

    if component is None:
        component = machine.initial_component

    if len(box_stack) == 0:
        return component

    next_box = box_stack[0]
    next_component = component.box_mapping[next_box]
    return box_stack_to_context(rsm, box_stack[1:], next_component)
