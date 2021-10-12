from pyModelChecking import CTL, language
# see https://pymodelchecking.readthedocs.io/en/latest/ and https://github.com/albertocasagrande/pyModelChecking


def new_hash(self):
    return id(self).__hash__()


language.Formula.__hash__ = new_hash


def parse_ctl(path_to_file):
    with open(path_to_file) as f:
        for line in f:
            # remove double spaces
            while "  " in line:
                line = line.replace("  ", " ")
            line = line.replace("\n", "")
            # skip comments and empty lines
            if line.startswith("#") or len(line) == 0 or line == " ":
                continue
            parser = CTL.parser.Parser()
            formula = parser(line)
            formula = formula.get_equivalent_restricted_formula()
            join_same_subformulas(formula)
            yield formula


def join_same_subformulas(ctl):
    str_mapping = dict()
    subformulas = get_subformulas(ctl, include_path_formulas=True)
    for depth in range(max(subformulas.keys()) + 1):
        for f in subformulas[depth]:
            if str(f) in str_mapping:
                continue
            for i in range(len(f.subformulas())):
                f._subformula[i] = str_mapping[str(f.subformula(i))]
            str_mapping[str(f)] = f


def get_subformulas(ctl: CTL, include_path_formulas=False):
    """
    Get all subformulas (recursively) of a CTL, ordered by quantifier depth of remaining subformula in a dictionary.
    Atoms have depth 0, all other formulas have depth of their max depth subformula + 1.
    Only return state formulas, no path formulas.
    Ordering by depth makes it easier to check CTL from inside to outside.

    :param ctl: CTL to get subformulas from
    :param include_path_formulas: whether to include path formulas without quantifier
    :return: dictionary of subformulas ordered by quantifier depth
    """

    # base case
    if isinstance(ctl, CTL.AtomicProposition) or isinstance(ctl, CTL.Bool):
        return {0: [ctl]}

    modified_ctl = ctl
    if not include_path_formulas and (isinstance(ctl, CTL.E) or isinstance(ctl, CTL.A)):
        # strip off quantifier such that iterating over subformulas only results in state formulas
        modified_ctl = ctl.subformula(0)

    subs = {}
    max_depth = -float("inf")
    for sub in modified_ctl.subformulas():
        partial_subs = get_subformulas(sub, include_path_formulas=include_path_formulas)
        for depth in partial_subs:
            max_depth = max(max_depth, depth)
            if depth not in subs:
                subs[depth] = []
            subs[depth] += partial_subs[depth]
    subs[max_depth + 1] = [ctl]
    return subs
