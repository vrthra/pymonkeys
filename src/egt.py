import os
import ast
import astunparse
import signal
import collections
from astmonkey import transformers

from z3 import *
Maxiter = 10

class UpdateName(ast.NodeTransformer):
    def __init__(self, egt):
        self.egt = egt

    def visit_Name(self, node):
        self.generic_visit(node)
        if isinstance(node.parent, ast.Call):
            return node
        tmpl = "v['x:1']"
        srcast = ast.parse(tmpl).body[0].value
        label = node.id
        if label in self.egt.defined_vars:
            srcast.slice.value.s = "%s:%d" % (label, self.egt.defined_vars[label])
        return srcast


class Egt():
    def __init__(self):
        self.constraints = []
        self.waitfor = []
        self.mypid = os.getpid()
        self.defined_vars = collections.defaultdict(int)
        self.name_trans = UpdateName(self)
        self.solver = Solver()

    def fork(self):
        pid = os.fork()
        if pid == 0:
            # chid -- update our pid, and reset
            # children to wait for termination
            self.mypid = os.getpid()
            del self.waitfor[:]
        else:
            self.waitfor.append(pid)
        return pid

    def epilogue(self):
        with open(".pids/%d" % self.mypid, "w+") as f:
            f.write(str(self.sat()))
        for pid in self.waitfor:
            os.waitpid(pid, 0)


    def new_label(self, name):
        self.defined_vars[name] += 1
        return "%s:%d" % (name, self.defined_vars[name])

    def symbolic(self, name):
        return Int(name)

    def labelize(self, src):
        """
        replace x + 1
        with    v['x:1'] + 1
        """
        node = ast.parse(src)
        value = transformers.ParentChildNodeTransformer().visit(node)
        return astunparse.unparse(self.name_trans.visit(value)).strip()

    def sat(self):
        if self.solver.check() == sat:
            return self.solver.model()
        else:
            return None

    def on_assign(self, name, value, g_state, l_state):
        newvalue = None
        if value != 'input()':
           newvalue = eval(self.labelize(value), g_state, l_state)
        name = self.new_label(name)
        if not newvalue: newvalue = self.symbolic(name)
        return (name, newvalue)

    def on_print(self, values, g_state, l_state):
        newvalues = [eval(self.labelize(v), g_state, l_state) for v in values]
        return newvalues
