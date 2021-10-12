""" Module containing definition of existential CTL formulas
currently not used since outside package seems to save some work for now
"""


class CTLFormula:
    """
    a base class to represent CTL formulas
    """


class CTLCompoundFormula(CTLFormula):
    """
    a class to represent CTL formulas including an operator

    Attributes
    ----------
    operator : any of "EX", "EU", "EG", "&&", "||", "!", "ATOMIC"
        specifies outermost operation
        ATOMIC implies subformula1 is a CTLLabel
    subformula1 : CTLFormula
        first subformula used for operators
    subformula2 : CTLFormula
        second subformula used for some operators
        None if operator is anything but "AND", "EU" or "OR"
    """

    def __init__(self, operator: str, subformula1: CTLFormula, subformula2: CTLFormula = None):
        self.operator = operator
        self.subformula1 = subformula1
        self.subformula2 = subformula2


class CTLLabel(CTLFormula):
    """
    a class to represent atomic CTL formulas
    """

    def __init__(self, label: str):
        self.label = label
