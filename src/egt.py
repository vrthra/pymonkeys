# Author: Rahul Gopinath <rahul.gopinath@cispa.saarland>
# License: GPLv3
import os
import ast
import astunparse
import signal
import collections
from astmonkey import transformers

import z3
Maxiter = 10

class NameTrans(ast.NodeTransformer):
    """
    Renamer the last label used for any given variable, so that if
    the variable b is used -- say `fn(b)` -- then it can be translated
    to `fn(egt_v['b:n'])` where n is the variable label that was assigned
    last
    """
    def __init__(self, egt):
        self.egt = egt

    def visit_Name(self, node):
        """
        Called from labelize. Checks if the given variable is already assigned.
        If it is assigned, then get the last assignment name.
        """
        self.generic_visit(node)
        if isinstance(node.parent, ast.Call) and node.parent.func == node:
            return node
        tmpl = "egt_v['x:1']"
        srcast = ast.parse(tmpl).body[0].value
        label = node.id
        if label in self.egt.defined_vars:
            srcast.slice.value.s = "%s:%d" % (label, self.egt.defined_vars[label])
        return srcast


class Egt():
    """
    Then main object that does the concolic execution.
    """
    def __init__(self):
        self.constraints = []
        self.waitfor = []
        self.mypid = os.getpid()
        self.defined_vars = collections.defaultdict(int)
        self.name_trans = NameTrans(self)
        self.solver = z3.Solver()

    def tmpeval(self, cond, g_state, l_state):
        """
        Evaluate cond temporarily using the sat solver.
        """
        self.solver.push() # commit point
        self.solver.add(eval(cond, g_state, l_state))
        condres = self.sat()
        self.solver.pop()
        return condres

    def fork(self, cond, g_state, l_state):
        """
        We *fork for evaluating conditions anywhere. This is a wrapper call over
        fork to ensure that we keep track of our children.

        *The fork is only performed if we can show that both `cond` and `not cond`
        are satisfiable using current information.
        """
        ifcond = self.tmpeval(self.labelize(cond), g_state, l_state)
        # The condition option is unsatisfiable. No point in forking a child.
        if ifcond == None: return -1

        ifnotcond = self.tmpeval('z3.Not%s' % self.labelize(cond), g_state, l_state)
        # The not condition option is unsatisfiable. No point in forking a child.
        if ifnotcond == None: return 0

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
        """
        Write our satisfiability results, and  wait for any children to exit
        """
        with open(".pids/%d" % self.mypid, "w+") as f:
            f.write(str(self.sat()))
        for pid in self.waitfor:
            os.waitpid(pid, 0)

    def symbolic(self, name):
        """
        Return a symbolic variable. As of now, only integers are handled.
        """
        return z3.Int(name)

    def labelize(self, src):
        """
        replace x + 1
        with    egt_v['x:1'] + 1
        """
        node = ast.parse(src)
        value = transformers.ParentChildNodeTransformer().visit(node)
        return astunparse.unparse(self.name_trans.visit(value)).strip()

    def sat(self):
        """
        Check for satisfiability. If satisfiable, return the satisfying model.
        """
        if self.solver.check() == z3.sat:
            return self.solver.model()
        else:
            return None


    def new_label(self, name):
        """ Produce a new label """
        self.defined_vars[name] += 1
        return "%s:%d" % (name, self.defined_vars[name])

    def on_assign(self, name, value, g_state, l_state):
        """
        Handle assignemnt. We need to append a label to LHS indicating its use
        status. That is, a new variable `a` is assigned a value `egt_v['a:0']`,
        while a reassigned variable `a`, which was already assigned egt_v['a:n']
        is assigned `egt_v['a:n+1']`
        For RHS, we simply labelize the existing variables to their latest
        label.
        """
        newvalue = None
        if value != 'input()':
            newvalue = eval(self.labelize(value), g_state, l_state)
        name = self.new_label(name)
        if newvalue is None: newvalue = self.symbolic(name)
        return (name, newvalue)

    def on_print(self, values, g_state, l_state):
        return [eval(self.labelize(v), g_state, l_state) for v in values]
