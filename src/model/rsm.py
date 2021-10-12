""" Module containing the basic structure to describe recursive state machines#
Due to the recursive nature of RSMs it is best (and often required) to construct RSMs in the following way:
* construct all components as blanks
* define all nodes in each component, set entry/exit nodes
* define all boxes in each component
* define the transition
* define all contextualizations
* define box mappings for contextualized components
"""

from copy import copy
from utils import get_context_encoding
from ctl_parser import get_subformulas
from pyModelChecking import CTL


class RSM:
    """
    a class to represent recursive state machines

     Attributes
    ----------

    base_components : Set[ContextualizedComponent]
        set of base components of the RSM
    base_component_dict : Dict[String -> ContextualizedComponent]
        dictionary from component names to components of the RSM
    contextualized_components : Set[ContextualizedComponent]
        set of contextualized components of the RSM
    initial_component : ContextualizedComponent
        the component containing the node where a path starts
    initial_node : Node
        the node in the initial component where paths start

    Methods
    -------

    initialize_single(ctl, name_appendix)
        builds a component with the initial context for the initial component w.r.t. a single existential CTL formula
        and declares it the new initial component. can be given name appendix to avoid naming all contexts "_init"
    initialize(ctl)
        builds a component with the initial context for the initial component w.r.t. a CTL formula including all its
        subformulas and declare it the new initial component
    get_base_component_by_name(name)
        return Component object from name as string
        only returns first match, None if no box, or no node in box is found
    add_base_component(c):
        add a base component to the RSM
    add_contextualized_component(c):
        add a contextualized component to the RSM
    remove_contextualized_component(c)
        remove a contextualized component from the RSM
    get_contextualized_component(c, context)
        checks whether the RSM has a contextualized component based on c with given context
        the component must be the same object, however for the context its contents are checked
        return None if no such component was found
    remove_unreachable_components()
        remove all contextualized components that are unreachable, i.e., there is no box referencing them
    is_sequential()
        check whether the RSM is sequential
    """

    def __init__(self):
        self.base_components = set()
        self.base_component_dict = {}
        self.contextualized_components = set()
        self.initial_component = None
        self.initial_node = None

    def __str__(self, include_labels=False):
        out = ["\nInitial node: " + str(self.initial_node) + " in " + str(self.initial_component)]
        for bc in self.base_components:
            out.append("")
            out.append(str(bc))
            out.append("Transitions:")
            for s in bc.transitions:
                ts = bc.transitions[s]
                if isinstance(s, BoxNode):
                    lbl_str = " (labels: " + str(s.node.parent_component.get_labels(s.node)) + ")"
                    out.append("    " + str(s.box) + " - " + str(s.node) + (lbl_str if include_labels else "") + " -->")
                else:
                    lbl_str = " (labels: " + str(bc.get_labels(s)) + ")"
                    out.append("    " + str(s) + (lbl_str if include_labels else "") + " -->")
                for t in ts:
                    if isinstance(t, BoxNode):
                        lbl_str = " (labels: " + str(t.node.parent_component.get_labels(t.node)) + ")"
                        out.append("        " + str(t.box) + " - " + str(t.node) + (lbl_str if include_labels else ""))
                    else:
                        lbl_str = " (labels: " + str(bc.get_labels(t)) + ")"
                        out.append("        " + str(t) + (lbl_str if include_labels else ""))
        return "\n".join(out)

    def initialize_single(self, ctl, name_appendix="_init"):
        exit_nodes = self.initial_component.base_component.get_exit_nodes()
        init_context = {ex: {f: val for f, val in ctx.items()} for ex, ctx in self.initial_component.context.items()}
        init_interpretation = {n: {f: val for f, val in i.items()}
                               for n, i in self.initial_component.interpretation.items()}

        # compute initial context
        try:
            if isinstance(ctl, CTL.E):
                for ex in exit_nodes:
                    path_formula = ctl.subformula(0)
                    if isinstance(path_formula, CTL.X) or isinstance(path_formula, CTL.G):
                        init_interpretation[ex][ctl] = init_interpretation[ex][path_formula.subformula(0)]
                    elif isinstance(path_formula, CTL.U):
                        init_interpretation[ex][ctl] = init_interpretation[ex][path_formula.subformula(1)]
                    else:
                        raise ValueError("can only initialize wrt x, g or u path formulas")
                    init_context[ex][ctl] = init_interpretation[ex][ctl]
            else:
                raise ValueError("can only single initialization wrt an existential ctl")
        except KeyError as e:
            raise ValueError("You tried to initialize wrt the CTL formula " + str(ctl) + " but the subformulas " +
                             str(e) + " is not known in all exit nodes of the initial component")

        # create initial context and set it as initial
        new_initial_component = self.initial_component.get_extended_component(name_appendix, init_context)
        self.contextualized_components.add(new_initial_component)
        self.initial_component = new_initial_component

    def initialize(self, ctl):
        subformulas = get_subformulas(ctl)
        exit_nodes = self.initial_component.base_component.get_exit_nodes()
        init_interpretation = {ex: dict() for ex in exit_nodes}
        init_context = {ex: dict() for ex in exit_nodes}

        # compute initial context
        for depth in range(max(subformulas.keys()) + 1):
            for f in subformulas[depth]:
                for ex in exit_nodes:
                    if isinstance(f, CTL.Bool):
                        if str(f) == "true":
                            init_interpretation[ex][f] = True
                        else:
                            init_interpretation[ex][f] = False
                    elif isinstance(f, CTL.AtomicProposition):
                        init_interpretation[ex][f] = self.initial_component.base_component.has_label(ex, str(f))
                    elif isinstance(f, CTL.Not):
                        init_interpretation[ex][f] = not init_interpretation[ex][f.subformula(0)]
                    elif isinstance(f, CTL.Or):
                        init_interpretation[ex][f] = any(init_interpretation[ex][sub] for sub in f.subformulas())
                    elif isinstance(f, CTL.E):
                        path_formula = f.subformula(0)
                        if isinstance(path_formula, CTL.X) or isinstance(path_formula, CTL.G):
                            init_interpretation[ex][f] = init_interpretation[ex][path_formula.subformula(0)]
                        elif isinstance(path_formula, CTL.U):
                            init_interpretation[ex][f] = init_interpretation[ex][path_formula.subformula(1)]
                        else:
                            raise ValueError("Can only initialize wrt X, G or U path formulas")
                        init_context[ex][f] = init_interpretation[ex][f]
                    else:
                        raise ValueError("Can only initialize wrt a CTL in existential normal form (not, or, exists)")

        # create initial context and set it as initial
        new_initial_component = self.initial_component.get_extended_component("_init", init_context)
        self.contextualized_components.add(new_initial_component)
        self.initial_component = new_initial_component

    def add_base_component(self, c):
        self.base_components.add(c)
        self.base_component_dict[c.name] = c

    def get_base_component_by_name(self, name):
        return self.base_component_dict[name]

    def add_contextualized_component(self, c):
        self.contextualized_components.add(c)

    def remove_contextualized_component(self, c):
        self.contextualized_components.remove(c)

    def get_contextualized_component(self, base_component, ctx):
        for c in self.contextualized_components:
            if c.base_component != base_component:
                continue
            if len(c.context) == 0 == len(ctx):
                return c
            context_matches_in_all_nodes = True
            for ex, mapping in c.context.items():
                if len(mapping) != len(ctx[ex]):
                    context_matches_in_all_nodes = False
                    break
                if any(value != ctx[ex][ctl] for ctl, value in mapping.items()):
                    context_matches_in_all_nodes = False
                    break
            if context_matches_in_all_nodes:
                return c
        return None

    def remove_unreachable_components(self):
        # remove unreachable components
        reach = []
        next_reach = [self.initial_component]
        while next_reach:
            for c in next_reach:
                reach.append(c)
            new_reach = []
            for component in next_reach:
                for b, target in component.box_mapping.items():
                    if target not in reach and target not in new_reach:
                        new_reach.append(target)
            next_reach = new_reach

        components = copy(self.contextualized_components)
        for component in components:
            if component not in reach:
                self.remove_contextualized_component(component)

    def is_sequential(self):
        return all(c.component.is_sequential() for c in self.base_components)


class ContextualizedComponent:
    """
    a class to represent a contextualized component of an RSM

    Attributes
    ----------

    base_component : Component
        The structure of this component
    context : Context
        The context of this component
    box_mapping : dict { Box : ContextualizedComponent }
        box reference function
    interpretation : dict { node : dict { CTL : bool } }
        The ternary interpretation of CTL formulas over the component. Unknown is represented by None.

    Methods
    -------

    get_truth_value(node, ctl)
        Return whether CTL holds in node
    get_extended_component(new_name_appendix, new_context)
        create a new component that is structurally identical to this one but has refined context information
        this is preferable over creating the component from scratch since it directly asserts known parts of the
        interpretation and the box mapping
    contextualize_box(box)
        unpack a box. collects the truth values of all formulas in the return nodes of the box and rewires the box to
        refer to a component with refined context (after potentially creating it first)

    """

    def __init__(self, parent_rsm, base_component, name_appendix, context):
        self.parent_rsm = parent_rsm
        self.name = base_component.name + name_appendix
        self.base_component = base_component
        self.context = context
        self.interpretation = {n: dict() for n in base_component.nodes}
        for ex, ctx in context.items():
            self.interpretation[ex] = {ctl: val for ctl, val in ctx.items()}
        self.box_mapping = dict()

    def get_truth_value(self, node, ctl):
        try:
            return self.interpretation[node][ctl]
        except KeyError:
            return None

    def get_extended_component(self, new_name_appendix, new_context):
        # sanity check for extension
        try:
            for n, ctx in self.context.items():
                for ctl, value in ctx.items():
                    if new_context[n][ctl] != value:
                        raise ValueError(str(new_context) + "is not an extension of " + str(self.context))
        except KeyError:
            raise ValueError(str(new_context) + "is not an extension of " + str(self.context))

        # create new component
        extended_component =\
            ContextualizedComponent(self.parent_rsm, self.base_component, new_name_appendix, new_context)

        # copy known stuff
        for n, i in self.interpretation.items():
            for ctl, v in i.items():
                extended_component.interpretation[n][ctl] = v
        for b, c in self.box_mapping.items():
            extended_component.box_mapping[b] = c

        # incorporate context information into interpretation
        for n, i in new_context.items():
            for ctl, v in i.items():
                extended_component.interpretation[n][ctl] = v

        return extended_component

    def contextualize_box(self, box):
        ref_component = self.box_mapping[box]
        formulas = set()

        # build new context
        context = dict()
        for rn in self.base_component.get_return_of_box(box):
            context[rn.node] = dict()
            for ctl, value in self.interpretation[rn].items():
                if not isinstance(ctl, CTL.E):
                    continue
                context[rn.node][ctl] = value
                formulas.add(ctl)

        # search if component exists
        new_component = self.parent_rsm.get_contextualized_component(ref_component.base_component, context)

        context_existed = True

        # create new component if none was found
        if new_component is None:
            context_existed = False
            name_appendix = get_context_encoding(formulas, context, ref_component.base_component)
            new_component = ref_component.get_extended_component(name_appendix, context)
            self.parent_rsm.contextualized_components.add(new_component)

        # update box mapping
        self.box_mapping[box] = new_component

        return context_existed


class Component:
    """
    a class to represent a component of an RSM

    Attributes
    ----------

    name : str
        The name of the component, solely for naming it
    nodes : dict{(Box)Node : {"is_entry" : bool, "is_exit" : bool, "labels" : Set[str]}
        dictionary containing all nodes (incl. BoxNodes) as keys of component and further info on them
    boxes : List[Box]
        list of boxes in component
    box_nodes : dict{BoxNode : {"labels" : Set[str], "formulas" : dict{CTL : bool}}}
        list of box nodes in component
        automatically kept up-to date along with boxes
    node_name_dict : dict { str : Node }
        dict of nodes by name for faster access
    call_node_dict : dict { (Box, Node) : BoxNode }
        dict of BoxNodes that are call nodes for faster access
    return_node_dict : dict { (Box, Node) : BoxNode }
        dict of BoxNodes that are return nodes for faster access
    box_node_name_dict : dict { (str, str) : BoxNode }
        dict of BoxNodes by names of Boxes and Nodes for faster access
    transitions : dict{X : [Y]}
            where X is a non-exit node or a BoxNode
            where Y is a non-entry node or a BoxNode
        dictionary containing all transitions of a component

    Methods
    -------

    is_entry(node)
        return whether node is entry node of component
    is_exit(node)
        return whether node is exit node of component
    get_entry_nodes()
        return all entry nodes of the component
    get_exit_nodes()
        return all entry nodes of the component
    get_return_of_box(box)
        return all call nodes of the specified box
    get_call_of_box(box)
        return all return nodes of the specified box
    make_entry_node(node)
        declare a node as entry node
    makes_exit_node(node)
        declare a node as exit node
    add_node(node)
        adds a Node or BoxNode object to the component
    add_label(node, label)
        adds a label to a node
    add_box(box)
        adds a box object to the component
    add_transition(source, target)
        add a transition from source to target in the RSM
        use this rather than modifying self.transitions directly as this does an integrity check
    get_node_by_name(name)
        return the node object with a given name
        only returns first match, None if no node is found
    get_node_by_base_name
        return the node object with a given base name
        only returns first match, None if no node is found
    get_box_by_name(name)
        return the box object with a given name
        only returns first match, None if no box is found
    get_call_node_by_name(box_name, node_name)
        return a BoxNode object by giving the name of its box and node
    get_return_node_by_name(box_name, node_name)
        return a BoxNode object by giving the name of its box and node
    get_call_node(box, node)
        return a BoxNode object corresponding to a given box and node
    get_return_node(box, node)
        return a BoxNode object corresponding to a given box and node
    get_predecessors(node)
        return the list of nodes that have a transition to the given node
    get_labels(node)
        return the list of labels of a node
    has_label(node, label)
        return whether the node has the label
    is_sequential()
        check whether the component has a sequential ordering w.r.t. the transitions
    """

    def __init__(self, name=""):
        self.name = name
        self.base_name = name
        self.nodes = {}
        self.boxes = []
        self.box_nodes = {}
        self.node_name_dict = {}
        self.call_node_dict = {}
        self.return_node_dict = {}
        self.call_node_name_dict = {}
        self.return_node_name_dict = {}
        self.transitions = {}

    def __str__(self):
        return "component " + str(self.name)

    def is_entry(self, node):
        return self.nodes[node]["is_entry"]

    def is_exit(self, node):
        return self.nodes[node]["is_exit"]

    def get_entry_nodes(self):
        return [n for n in self.nodes if self.is_entry(n)]

    def get_exit_nodes(self):
        return [n for n in self.nodes if self.is_exit(n)]

    def make_entry_node(self, node):
        if len(self.get_predecessors(node)) > 0:
            raise ValueError("Can't declare node " + str(node) + " entry node because it has ingoing transitions")
        self.nodes[node]["is_entry"] = True

    def make_exit_node(self, node):
        if len(self.transitions[node]) > 0:
            raise ValueError("Can't declare node " + str(node) + " entry node because it has outgoing transitions")
        self.nodes[node]["is_exit"] = True

    def get_call_of_box(self, box):
        result = []
        for bn in self.box_nodes:
            if bn.box == box and bn.is_call_node:
                result.append(bn)
        return result

    def get_return_of_box(self, box):
        result = []
        for bn in self.box_nodes:
            if bn.box == box and bn.is_return_node:
                result.append(bn)
        return result

    def add_node(self, node):
        if node.parent_component:
            raise ValueError("Tried adding node that was already contained in component: " + str(node.parent_component))
        node.parent_component = self
        self.nodes[node] = {"is_entry": False, "is_exit": False, "labels": set([]), "formulas": {}}
        self.transitions[node] = []
        self.node_name_dict[node.name] = node

    def add_label(self, node, label):
        self.nodes[node]["labels"].add(label)

    def add_box(self, box):
        if box.parent_component:
            raise ValueError("Tried adding node that was already contained in component: " + str(box.parent_component))
        box.parent_component = self
        self.boxes.append(box)
        for n in box.call_nodes:
            bn = BoxNode(box, n, is_call=True, is_return=False, name=box.name + "-" + n.name)
            self.call_node_dict[(box, n)] = bn
            self.call_node_name_dict[(box.name, n.name)] = bn
            bn.parent_component = self
            self.box_nodes[bn] = {"labels": n.parent_component.nodes[n]["labels"], "formulas": {}}
            self.nodes[bn] = {"is_entry": False, "is_exit": False,
                              "labels": n.parent_component.nodes[n]["labels"], "formulas": {}}
            self.transitions[bn] = []
        for n in box.return_nodes:
            bn = BoxNode(box, n, is_call=False, is_return=True, name=box.name + "-" + n.name)
            self.return_node_dict[(box, n)] = bn
            self.return_node_name_dict[(box.name, n.name)] = bn
            bn.parent_component = self
            self.box_nodes[bn] = {"labels": n.parent_component.nodes[n]["labels"], "formulas": {}}
            self.nodes[bn] = {"is_entry": False, "is_exit": False,
                              "labels": n.parent_component.nodes[n]["labels"], "formulas": {}}
            self.transitions[bn] = []

    def add_transition(self, source, target):
        """Adds a transition from source to target while checking for consistency within RSM

        Parameters
        ----------
        source : Node or BoxNode
            transition source
            must be non-exit node of component of return port of a box
        target : Node or BoxNode
            transition target
            must be non-entry node of component of call port of a box

        Raises
        ------
        ValueError
            If invalid transition nodes are given (i.e. exit/entry nodes or box nodes that aren't return/call ports)
        """

        # sanity checks - commented for now for performance reasons
        """
        if isinstance(source, Node) and self.is_exit(source):
            raise ValueError("Failed adding transition from " + str(source) + " to " + str(target) + "\n" +
                             "Source can't be an exit node of a component")
        if isinstance(target, Node) and self.is_entry(target):
            raise ValueError("Failed adding transition from " + str(source) + " to " + str(target) + "\n" +
                             "Target  can't be an entry node of a component")
        if isinstance(source, BoxNode):
            # Check if node is actually a return port in box
            if not source.is_return_node:
                raise ValueError("Failed adding transition from " + str(source) + " to " + str(target) + "\n" +
                                 "If source of transition is box, it must be a return port of the box")
        if isinstance(target, BoxNode):
            # Check if node is actually a call port in box
            if not target.is_call_node:
                raise ValueError("Failed adding transition from " + str(source) + " to " + str(target) + "\n" +
                                 "If target of transition is box, it must be a call port of the box")
        """

        if source not in self.transitions:
            self.transitions[source] = []
        self.transitions[source].append(target)

    def get_node_by_name(self, name):
        return self.node_name_dict[name]

    def get_node_by_base_name(self, name):
        for n in self.nodes:
            if n.base_name == name:
                return n

    def get_box_by_name(self, name):
        for b in self.boxes:
            if b.name == name:
                return b

    def get_call_node_by_name(self, box_name, node_name):
        return self.call_node_name_dict[(box_name, node_name)]

    def get_return_node_by_name(self, box_name, node_name):
        return self.return_node_name_dict[(box_name, node_name)]

    def get_call_node(self, box, node):
        return self.call_node_dict[(box, node)]

    def get_return_node(self, box, node):
        return self.return_node_dict[(box, node)]

    def get_predecessors(self, node):
        predecessors = []
        for n, successors in self.transitions.items():
            if node in successors:
                predecessors.append(n)
        return predecessors

    def get_labels(self, node):
        return self.nodes[node]["labels"]

    def has_label(self, node, label):
        return label in self.get_labels(node)

    def generate_empty_context(self):
        return {ex: dict() for ex in self.get_exit_nodes()}

    def is_sequential(self):

        def detect_cycle(node, visited, stack):
            # returns True if you can reach a box node in stack from node. ignores visited nodes.

            visited.add(node)
            if isinstance(node, BoxNode):
                stack.add(node)

            successors = node.parent_component.transitions[node]
            box_successors = []
            if isinstance(node, BoxNode) and node.is_call_node:
                box_successors = self.get_return_of_box(node.box)

            for succ in successors + box_successors:
                if succ not in visited:
                    if detect_cycle(succ, visited, stack):
                        return True
                elif succ in stack:
                    return True

            if isinstance(node, BoxNode):
                stack.remove(node)
            return False

        v = set()
        s = set()

        for bn in self.box_nodes:
            if bn not in v:
                if detect_cycle(bn, v, s):
                    return False
            return True


class Box:
    """
    a class to represent boxes used in a recursive state machine
    this should only be used within RSMs, not as a standalone object
    """

    def __init__(self, component, name="", entry_nodes=None, exit_nodes=None):
        """
        Parameters
        ----------
        name : str
            The name of the box, solely for naming it
        component : Component
            the component the box is referencing
        entry_nodes : Optional list[Node]
            subset of entry nodes of referenced component, aka call nodes
            if omitted, all entry nodes of referenced component are declared call nodes
        exit_nodes : Optional list[Node]
            subset of exit nodes of referenced component, aka return nodes
            if omitted, all entry nodes of referenced component are declared return nodes

        Raises
        ------
        ValueError
            If any of the specified call/return nodes are not entry/exit nodes of the component
        """
        self.component = component
        self.name = name
        self.parent_component = None
        if entry_nodes is None:
            self.call_nodes = self.component.get_entry_nodes()
        else:
            for node in entry_nodes:
                if not component.is_entry(node):
                    raise ValueError("Call nodes of box must be entry nodes of component")
            self.call_nodes = entry_nodes
        if exit_nodes is None:
            self.return_nodes = self.component.get_exit_nodes()
        else:
            for node in exit_nodes:
                if not component.is_exit(node):
                    raise ValueError("Return nodes of box must be exit nodes of component")
            self.return_nodes = exit_nodes

    def __str__(self):
        return "box " + str(self.name) + " [ref: " + str(self.component) + "]"


class Node:
    """
    a class to represent nodes used in a recursive state machine
    this should only be used within RSMs, not as a standalone object
    """

    def __init__(self, name="", base_name=None):
        """
        Parameters
        ----------
        name : str
            The name of the box, solely for naming it
        """
        if " " in name:
            raise ValueError(name)
        self.name = name
        self.base_name = name if base_name is None else base_name
        self.parent_component = None

    def is_entry(self):
        return self.parent_component.is_entry(self)

    def is_exit(self):
        return self.parent_component.is_exit(self)

    def __str__(self):
        return "node " + str(self.name) + \
               (" (entry)" if self.is_entry() else "") + (" (exit)" if self.is_exit() else "")


class BoxNode:
    """
    a class to represent nodes that are entry or exit ports of a box
    this should only be used within RSMs, not as a standalone object
    """

    def __init__(self, box: Box, node: Node, is_call: bool, is_return: bool, name=""):
        """
        Parameters
        ----------
        name : str
            The name of the box-node, solely for naming it
        """
        if " " in name:
            raise ValueError(name)
        self.name = name
        self.parent_component = None
        self.box = box
        self.node = node
        self.is_call_node = is_call
        self.is_return_node = is_return
        if not self.is_call_node and not self.is_return_node:
            raise ValueError("Node of BoxNode must be entry or exit node of the BoxNode's Box")

    def __str__(self):
        return "box-node " + str(self.name) + " (" + ("call, " if self.is_call_node else "") + \
               ("return, " if self.is_return_node else "") + str(self.node) + ", " + str(self.box) + ")"
