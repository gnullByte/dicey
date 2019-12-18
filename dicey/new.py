import lark
import random
import sys
from queue import LifoQueue

grammar = """
start: expr+ (op expr)* meta* repeat?

expr: tok
     |l tok r
     |l tok expr_tail r

expr_tail: op tok
          |op tok expr_tail
          |op l tok r
          |op l tok expr_tail r

tok: die|num
die: INT "d" INT         -> die
num: INT                 -> num
op: ADDOP|MULOP          -> op
l: LPAREN                -> lparen
r: RPAREN                -> rparen

meta: ADDOP SPEC         -> meta
repeat: "{" INT "}"      -> repeat


LPAREN: "("
RPAREN: ")"
ADDOP: "+"|"-"
MULOP: "*"|"/"
SPEC: "min"|"max"

%import common.INT
%import common.WS
%ignore WS
"""

text = (
    "(1 + (2d4 + (1 + (3d6 + (12d8))))) + (2d4 + 1d6) + (1d8) - 2d4 - min {2}"
)
# text = "1 + (2d4 + 3d6) * 2 - min {2}"
# text = "4d6 - min"
# print(tree.pretty())


class DieTransformer(lark.Transformer):
    def __init__(self):
        self.string = ""
        self.intermediate_expr = ""
        self.value = LifoQueue()
        self.operators = LifoQueue()
        self.max = -(sys.maxsize)
        self.min = sys.maxsize
        self.repeats = 0

    def _precedence(self, op):
        if op == "+" or op == "-":
            return 1
        if op == "*" or op == "/":
            return 2
        return 0

    def _applyOp(self, a, b, op):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b

    def _eval(self):
        while not self.operators.empty():
            op = self.operators.get()
            b = self.value.get()
            a = self.value.get()
            self.value.put(self._applyOp(a, b, op))

    def lparen(self, args):
        self.string += "("
        self.intermediate_expr += "("

        self.operators.put(args[0])

    def rparen(self, args):
        self.string += ")"
        self.intermediate_expr += ")"

        op = self.operators.get()
        while op != "(":
            b = self.value.get()
            a = self.value.get()

            if op == "+":
                self.value.put(a + b)
            elif op == "-":
                self.value.put(a - b)
            elif op == "*":
                self.value.put(a * b)
            elif op == "/":
                self.value.put(a / b)

            op = self.operators.get()

    def num(self, args):
        self.string += "{}".format(args[0])
        self.intermediate_expr += args[0]

        self.value.put(int(args[0]))

    def op(self, args):
        self.string += " {} ".format(args[0])
        self.intermediate_expr += " {} ".format(args[0])

        if not self.operators.empty():
            op = self.operators.queue[-1]
            while not self.operators.empty() and self._precedence(
                op
            ) >= self._precedence(args[0]):
                op = self.operators.get()
                b = self.value.get()
                a = self.value.get()
                self.value.put(self._applyOp(a, b, op))

        self.operators.put(args[0])

    def die(self, args):
        self.string += "{}d{}".format(args[0], args[1])

        n = int(args[0])
        m = int(args[1])
        total = 0
        for die in range(n):
            roll = random.randrange(1, m + 1)
            total += roll

            if roll > self.max:
                self.max = roll

            if roll < self.min:
                self.min = roll

        self.intermediate_expr += " {} ".format(total)
        self.value.put(total)

    def meta(self, args):
        op = args[0]
        t = args[1]

        if t == "min":
            self.op([op])
            self.value.put(self.min)
            self.intermediate_expr += "[{}]".format(self.min)
        elif t == "max":
            self.op([op])
            self.value.put(self.max)
            self.intermediate_expr += "[{}]".format(self.max)

        self.string += "{}".format(args[1])

    def repeat(self, args):
        self.repeats = int(args[0])
        self.string += " {{{0}}}".format(self.repeats)


class DieParser:
    def __init__(self):
        self.last_exp = ""
        self.intermediate_expr = ""
        self.results = []
        self.transformer = DieTransformer()
        self.parser = lark.Lark(
            grammar,
            parser="lalr",
            transformer=self.transformer,
            propagate_positions=False,
        )

    def parse(self, text):
        self.parser.parse(text)
        self.transformer._eval()
        self.last_exp = self.transformer.string
        self.intermediate_expr = self.transformer.intermediate_expr
        self.results.append(self.transformer.value.get())

        for i in range(self.transformer.repeats - 1):
            self.transformer.__init__()
            self.parser.parse(text)
            self.intermediate_expr += "\n{}".format(
                self.transformer.intermediate_expr
            )
            self.results.append(self.transformer.value.get())

    def __str__(self):
        s = ""
        s += "{} = ".format(self.last_exp)
        s += "{} = ".format(self.intermediate_expr)
        s += str(self.results[0])
        return s


d = DieParser()
d.parse(text)
print(d)