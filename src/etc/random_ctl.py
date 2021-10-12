"""
script to create a random CTL formula
usage e.g. like this:
python3 random_ctl.py 3 4 2 a b --exclude_x -out ../../models/random.ctl
for meaning of the numbers use
python3 etc/random_ctl.py -h
"""

import argparse
import pyModelChecking.CTL as CTL
from random import random, randint, choice, sample

parser = argparse.ArgumentParser(description="Create a random CTL formula")
parser.add_argument("min_quantifier_depth", help="number of maximum quantifier nesting", type=int)
parser.add_argument("max_quantifier_depth", help="number of maximum quantifier nesting", type=int)
parser.add_argument("max_width", help="maximum number of successive propositional connectives", type=int)
parser.add_argument("ap", help="list of atomic propositions to be used",
                    nargs='+',
                    type=str)
parser.add_argument("--exclude_x",
                    action="store_true",
                    help="do not use exists next quantifier")
parser.add_argument("-out", help="output location of the CTL", default="random.ctl")

args = parser.parse_args()
quantifier_depth = randint(args.min_quantifier_depth, args.max_quantifier_depth)
max_width = args.max_width
aps = args.ap
exclude_x = args.exclude_x
out = args.out

quantifiers = [CTL.EG, CTL.EU] if exclude_x else [CTL.EG, CTL.EU, CTL.EX]


def get_random_formula(quant_depth, width=None):

    if width is None:
        width = randint(1, max_width)

    subformulas = []

    if quant_depth == 0:
        for ap in random_subset(aps):
            f = CTL.AtomicProposition(ap)
            if random() < 0.5:
                f = CTL.Not(f)
            subformulas.append(f)
        return combine_formulas(subformulas)

    for i in range(width):
        next_depth = quant_depth-1 if i == 0 else randint(0, quant_depth-1)
        quantifier = choice(quantifiers)
        if quantifier == CTL.EG or quantifier == CTL.EX:
            f = quantifier(get_random_formula(next_depth))
            if random() < 0.5:
                f = CTL.Not(f)
            subformulas.append(f)
        elif quantifier == CTL.EU:
            f1 = get_random_formula(next_depth)
            f2 = get_random_formula(randint(0, quant_depth - 1))
            if random() < 0.5:
                f = quantifier(f1, f2)
            else:
                f = quantifier(f2, f1)
            if random() < 0.5:
                f = CTL.Not(f)
            subformulas.append(f)
    return combine_formulas(subformulas)


def combine_formulas(formulas):
    """combine a list of formulas using propositional connectives"""
    f = formulas[0]
    for next_f in formulas[1:]:
        connective = CTL.And if random() < 0.5 else CTL.Or
        f = connective(f, next_f)
    return f


def random_subset(l):
    size = randint(1, len(l))
    return sample(l, size)


with open(out, 'w') as f:
    f.write(str(get_random_formula(quantifier_depth, 1))
            .replace("not ", "~").replace(" or ", "|").replace(" and ", "&").replace("EX", "E X").replace("EG", "E G"))
