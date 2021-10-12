"""
Representation of witnesses, giving reason for why a formula holds
"""

from utils import *


class Witness:
    """
    a reason why ctl holds or does not hold in node with a given box stack
    """

    def __init__(self, machine, box_stack, node, ctl, expected_value):
        self.machine = machine
        self.box_stack = box_stack
        self.component = box_stack_to_context(machine, box_stack)
        self.node = node
        self.ctl = ctl
        self.expected_value = expected_value
        self.reasons = []


class LocalWitness(Witness):

    def __init__(self, machine, box_stack, node, ctl, expected_value):
        super().__init__(machine, box_stack, node, ctl, expected_value)

    def __str__(self):
        if self.expected_value:
            return str(self.ctl) + " locally holds in " + self.node.name
        else:
            return str(self.ctl) + " locally does not hold in " + self.node.name


class NegationWitness(Witness):

    def __init__(self, machine, box_stack, node, ctl, expected_value):
        super().__init__(machine, box_stack, node, ctl, expected_value)
        self.reasons = self.find_reasons()

    def find_reasons(self):
        sub = self.ctl.subformula(0)
        return [generate_witness(self.machine, self.box_stack, self.node, sub, not self.expected_value)]

    def __str__(self):
        sub = self.ctl.subformula(0)
        if self.expected_value:
            return str(self.ctl) + " holds in " + state_str(self.box_stack, self.node) + " because " + \
                str(sub) + " does not hold"
        else:
            return str(self.ctl) + " does not hold in " + state_str(self.box_stack, self.node) + " because " + \
                str(sub) + " holds"


class DisjunctionWitness(Witness):

    def __init__(self, machine, box_stack, node, ctl, expected_value):
        super().__init__(machine, box_stack, node, ctl, expected_value)
        self.reasons = self.find_reasons()

    def find_reasons(self):
        if self.expected_value:
            for sub in self.ctl.subformulas():
                if sub not in self.component.interpretation[self.node] or \
                        self.component.interpretation[self.node] is False:
                    continue
                return [generate_witness(self.machine, self.box_stack, self.node, sub, self.expected_value)]
        else:
            reasons = []
            for sub in self.ctl.subformulas():
                reasons.append(generate_witness(self.machine, self.box_stack, self.node, sub, self.expected_value))
            return reasons

    def __str__(self):
        if self.expected_value:
            for sub in self.ctl.subformulas():
                if sub not in self.component.interpretation[self.node] or \
                        self.component.interpretation[self.node] is False:
                    continue
                return str(self.ctl) + " holds in " + state_str(self.box_stack, self.node) + " because " + \
                    str(sub) + " holds"
        else:
            return str(self.ctl) + " does not hold in " + state_str(self.box_stack, self.node) + \
                " because none of the disjuncts hold"


class NextWitness(Witness):

    def __init__(self, machine, box_stack, node, ctl, expected_value):
        super().__init__(machine, box_stack, node, ctl, expected_value)
        self.reasons = self.find_reasons()

    def find_reasons(self):
        sub = self.ctl.subformula(0).subformula(0)
        successors = self.component.base_component.transitions[self.node]
        if self.expected_value:
            for s in successors:
                if sub not in self.component.interpretation[s] or self.component.interpretation[s][sub] is False:
                    continue
                return [generate_witness(self.machine, self.box_stack, s, sub, self.expected_value)]
            if isinstance(self.node, rsm.BoxNode):
                next_box_stack = self.box_stack + self.node.box
                next_component = self.component.box_mapping[self.node.box]
                successors = next_component.base_component.transitions[self.node.node]
                for s in successors:
                    if sub not in self.component.interpretation[s] or self.component.interpretation[s][sub] is False:
                        continue
                    return [generate_witness(self.machine, next_box_stack, s, sub, self.expected_value)]
        else:
            reasons = []
            for s in successors:
                reasons.append(generate_witness(self.machine, self.box_stack, s, sub, self.expected_value))
            if isinstance(self.node, rsm.BoxNode):
                next_box_stack = self.box_stack + self.node.box
                next_component = self.component.box_mapping[self.node.box]
                successors = next_component.base_component.transitions[self.node.node]
                for s in successors:
                    reasons.append(generate_witness(self.machine, next_box_stack, s, sub, not self.expected_value))

    def __str__(self):
        sub = self.ctl.subformula(0).subformula(0)
        successors = self.component.base_component.transitions[self.node]
        if self.expected_value:
            for s in successors:
                if sub not in self.component.interpretation[s] or self.component.interpretation[s][sub] is False:
                    continue
                return str(self.ctl) + " holds in " + state_str(self.box_stack, self.node) + " because " + \
                    str(sub) + " holds in " + state_str(self.box_stack, s)
            if isinstance(self.node, rsm.BoxNode):
                next_box_stack = self.box_stack + self.node.box
                next_component = self.component.box_mapping[self.node.box]
                successors = next_component.base_component.transitions[self.node.node]
                for s in successors:
                    if sub not in self.component.interpretation[s] or self.component.interpretation[s][sub] is False:
                        continue
                    return str(self.ctl) + " holds in " + state_str(self.box_stack, self.node) + " because " + \
                        str(sub) + " holds in " + state_str(s, next_box_stack)
        else:
            return str(self.ctl) + " does not hold in " + state_str(self.box_stack, self.node) + " because " + \
                str(sub) + " does not hold in any successor"


class UntilWitness(Witness):

    def __init__(self, machine, box_stack, node, ctl, expected_value):
        super().__init__(machine, box_stack, node, ctl, expected_value)
        self.path = self.find_path([(self.box_stack, self.node)], self.component)
        self.reasons = self.find_reasons()

    def find_reasons(self):
        if self.expected_value:
            sub1 = self.ctl.subformula(0).subformula(0)
            sub2 = self.ctl.subformula(0).subformula(1)
            sub1_path = self.path[:-1]
            sub2_box_stack, sub2_node = self.path[-1]
            reasons = [generate_witness(self.machine, box_stack, node, sub1, True) for (box_stack, node) in sub1_path]
            reasons.append(generate_witness(self.machine, sub2_box_stack, sub2_node, sub2, True))
            return reasons
        else:
            return []

    def find_path(self, path, component, visited=None):
        if self.expected_value is False:
            return None
        if visited is None:
            visited = set()
        sub2 = self.ctl.subformula(0).subformula(1)
        box_stack, node = path[-1]
        visited.add((component, node))
        # if phi_2 holds, we have found the complete witness path
        if sub2 in component.interpretation[node] and component.interpretation[node][sub2] is True:
            return path
        # otherwise, phi_1 must hold, and the until formula must hold in some successor
        successors = component.base_component.transitions[node]
        for s in successors:
            # ignore successors in which the until formula is unknown or false
            if self.ctl not in component.interpretation[s] or component.interpretation[s][self.ctl] is False:
                continue
            if (component, s) not in visited:
                path.append((box_stack, s))
                full_path = self.find_path(path, component, visited)
                if full_path is not None:
                    return full_path
                path.pop()
        # entering a box
        if isinstance(node, rsm.BoxNode) and node.is_call_node:
            component = component.box_mapping[node.box]
            successors = component.base_component.transitions[node.node]
            for s in successors:
                # ignore successors in which ctl is unknown or false
                if self.ctl not in component.interpretation[s] or component.interpretation[s][self.ctl] is False:
                    continue
                if (component, s) not in visited:
                    path.append((box_stack + [node.box], s))
                    full_path = self.find_path(path, component, visited)
                    if full_path is not None:
                        return full_path
                    path.pop()
        # leaving a box
        elif isinstance(node, rsm.Node) and component.base_component.is_exit(node):
            # for the case where we reach an exit node in the initial component in which sub2 does not hold
            if not box_stack:
                return None
            last_box = box_stack[-1]
            component = box_stack_to_context(self.machine, box_stack[:-1])
            node = component.base_component.get_return_node(last_box, node)
            successors = component.base_component.transitions[node]
            for s in successors:
                # ignore successors in which ctl is unknown or false
                if self.ctl not in component.interpretation[s] or component.interpretation[s][self.ctl] is False:
                    continue
                if (component, s) not in visited:
                    path.append((box_stack[:-1], s))
                    full_path = self.find_path(path, component, visited)
                    if full_path is not None:
                        return full_path
                    path.pop()
        return None

    def __str__(self):
        sub1 = self.ctl.subformula(0).subformula(0)
        sub2 = self.ctl.subformula(0).subformula(1)
        if self.expected_value:
            sub1_path = self.path[:-1]
            sub2_box_stack, sub2_node = self.path[-1]
            return str(self.ctl) + " holds in " + state_str(self.box_stack, self.node) + " because " + str(sub1) + \
                " holds along the path " + " -> ".join(state_str(box_stack, node) for box_stack, node in sub1_path) + \
                " and " + str(sub2) + " holds in " + state_str(sub2_box_stack, sub2_node)
        else:
            return str(self.ctl) + " does not hold in " + state_str(self.box_stack, self.node) + \
                   " but cannot give a witness for the non-existence of a path."


class AlwaysWitness(Witness):

    def __init__(self, machine, box_stack, node, ctl, expected_value):
        super().__init__(machine, box_stack, node, ctl, expected_value)
        self.cycle, self.cycle_index = self.find_cycle([(self.box_stack, self.node)], [(self.component, self.node)])
        self.reasons = self.find_reasons()

    def find_reasons(self):
        if self.expected_value:
            sub = self.ctl.subformula(0).subformula(0)
            return [generate_witness(self.machine, box_stack, node, sub, True) for (box_stack, node) in self.cycle]
        else:
            return []

    def find_cycle(self, bs_path, comp_path):
        if self.expected_value is False:
            return None
        box_stack, node = bs_path[-1]
        component, node = comp_path[-1]
        # if we visited the node already we found a cycle
        if (component, node) in comp_path[:-1]:
            idx = comp_path.index((component, node))
            return bs_path, idx
        # otherwise, the always formula must hold in some successor
        successors = component.base_component.transitions[node]
        for s in successors:
            # ignore successors in which the always formula is unknown or false
            if self.ctl not in component.interpretation[s] or component.interpretation[s][self.ctl] is False:
                continue
            bs_path.append((box_stack, s))
            comp_path.append((component, s))
            full_cycle = self.find_cycle(bs_path, comp_path)
            if full_cycle is not None:
                return full_cycle
            bs_path.pop()
            comp_path.pop()
        # entering a box
        if isinstance(node, rsm.BoxNode) and node.is_call_node:
            component = component.box_mapping[node.box]
            successors = component.base_component.transitions[node.node]
            for s in successors:
                # ignore successors in which the always formula is unknown or false
                if self.ctl not in component.interpretation[s] or component.interpretation[s][self.ctl] is False:
                    continue
                bs_path.append((box_stack + [node.box], s))
                comp_path.append((component, s))
                full_cycle = self.find_cycle(bs_path, comp_path)
                if full_cycle is not None:
                    return full_cycle
                bs_path.pop()
                comp_path.pop()
        # leaving a box
        elif isinstance(node, rsm.Node) and component.base_component.is_exit(node):
            # for the case where we reach an exit node in the initial component in sub holds
            if not box_stack:
                idx = len(bs_path)
                bs_path.append((box_stack, node))
                return bs_path, idx
            last_box = box_stack[-1]
            component = box_stack_to_context(self.machine, box_stack[:-1])
            node = component.base_component.get_return_node(last_box, node)
            successors = component.base_component.transitions[node]
            for s in successors:
                # ignore successors in which ctl is unknown or false
                if self.ctl not in component.interpretation[s] or component.interpretation[s][self.ctl] is False:
                    continue
                bs_path.append((box_stack[:-1], s))
                comp_path.append((component, s))
                full_cycle = self.find_cycle(bs_path, comp_path)
                if full_cycle is not None:
                    return full_cycle
                bs_path.pop()
                comp_path.pop()
        return None

    def __str__(self):
        sub = self.ctl.subformula(0).subformula(0)
        if self.expected_value:
            ctx_note = " (the cyclic node is reached with two different box stacks [" + \
                       state_str(*(self.cycle[self.cycle_index])) + " and " + state_str(*(self.cycle[-1])) + \
                       "], however both box stacks produce the same context, so it is indeed a cycle)"
            return str(self.ctl) + " holds in " + state_str(self.box_stack, self.node) + " because " + str(sub) + \
                " holds along the path " + " -> ".join(("[CYCLE START]" if i == self.cycle_index else "") +
                                                       state_str(box_stack, node)
                                                       for i, (box_stack, node) in enumerate(self.cycle)) + \
                (ctx_note if self.cycle[self.cycle_index][0] != self.cycle[-1][0] else "")
        else:
            return str(self.ctl) + " does not hold in " + state_str(self.box_stack, self.node) + \
                   " but cannot give a witness for the non-existence of a path."


def generate_witness(machine, box_stack, node, ctl, expected_value):
    if is_propositional(ctl):
        return LocalWitness(machine, box_stack, node, ctl, expected_value)
    if isinstance(ctl, CTL.Not):
        return NegationWitness(machine, box_stack, node, ctl, expected_value)
    if isinstance(ctl, CTL.Or):
        return DisjunctionWitness(machine, box_stack, node, ctl, expected_value)
    if isinstance(ctl, CTL.E):
        path_formula = ctl.subformula(0)
        if isinstance(path_formula, CTL.X):
            return NextWitness(machine, box_stack, node, ctl, expected_value)
        if isinstance(path_formula, CTL.U):
            return UntilWitness(machine, box_stack, node, ctl, expected_value)
        if isinstance(path_formula, CTL.G):
            return AlwaysWitness(machine, box_stack, node, ctl, expected_value)


def is_propositional(ctl):
    if isinstance(ctl, CTL.AtomicProposition) or isinstance(ctl, CTL.Bool):
        return True
    if isinstance(ctl, CTL.E) or isinstance(ctl, CTL.A):
        return False
    return all(is_propositional(sub) for sub in ctl.subformulas())


def recursive_str(witness, depth=0, max_depth=float('Inf')):
    if depth > max_depth:
        return ""
    out = ["\t" * depth + str(witness)]
    for reason in witness.reasons:
        out += recursive_str(reason, depth+1)
    return out


def box_stack_str(box_stack):
    return "[" + ", ".join(b.name for b in box_stack) + "]"


def state_str(box_stack, node):
    return "(" + box_stack_str(box_stack) + ", " + node.name + ")"
