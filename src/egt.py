import os
import ast
import astunparse
import signal
import collections
class Constraints:
    def __init__(self):
        self.constraints = []

    def append(self, cond):
        self.constraints.append(cond)

    def show(self):
        return " & ".join(self.constraints)

class UpdateName(ast.NodeTransformer):
    def __init__(self, egt):
        self.egt = egt

    def visit_Name(self, node):
        if node.id in self.egt.defined_vars:
            node.id = "%s:%d" % (node.id, self.egt.defined_vars[node.id])
        return node


class Egt():
    def __init__(self):
        self.constraints = Constraints()
        self.children = []
        self.mypid = os.getpid()
        self.defined_vars = collections.defaultdict(int)
        self.name_trans = UpdateName(self)

    def on_child(self, cond):
        self.mypid = os.getpid()
        self.constraints.append(self.update_vars(cond))
        del self.children[:]

    def on_parent(self, pid, cond):
        self.constraints.append(self.update_vars(cond))
        self.children.append(pid)

    def update_vars(self, src):
        value = ast.parse(src)
        return astunparse.unparse(self.name_trans.visit(value)).strip()

    def on_assignment(self, target, target_value):
        # walk the value first to ensure that all variable references are
        # correctly converted to variable:label references.
        target_value = self.update_vars(target_value)

        # now update the reference. If you do this before the previous walk, you
        # will find that the target_value contains referenes to current label
        self.defined_vars[target] += 1

        target_var = "%s:%d" % (target, self.defined_vars[target])
        self.constraints.append(target_var + " == " + target_value)

    def epilogue(self):
        with open(".pids/%d" % self.mypid, "w+") as f:
	    f.write(self.constraints.show())
        for pid in self.children:
	    os.waitpid(pid, 0)

