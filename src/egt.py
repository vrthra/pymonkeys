import os
import ast
import astunparse
import signal
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
        self.defined_vars = {}
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

    def theend(self):
        with open(".pids/%d" % self.mypid, "w+") as f:
	    f.write(self.constraints.show())
        for pid in self.children:
	    os.waitpid(pid, 0)

