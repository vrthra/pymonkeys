#!/usr/bin/env python
import sys
from textwrap import dedent
import os
from ast import *
import astunparse

def slurp(src):
    with open(src) as x: return x.read()

def prologue_tmpl():
    tmpl = """
    import os
    import ast
    import astunparse
    import signal
    class EgtConstraints:
        def __init__(self):
            self.constraints = []

        def append(self, cond):
            self.constraints.append(cond)

        def show(self):
            return " & ".join(self.constraints)

    class UpdateNameTransformer(ast.NodeTransformer):
        def visit_Name(self, node):
            #print astunparse.unparse(node)
            #print "------"
            if node.id in egt_defined_vars:
                node.id = "%s:%d" % (node.id, egt_defined_vars[node.id])
            return node

    egt_constraints = EgtConstraints()

    egt_defined_vars = {}
    egt_children = []
    egt_mypid = os.getpid()

    def on_child(cond):
        global egt_constraints
        global egt_children
        global egt_mypid
        egt_mypid = os.getpid()
        egt_constraints.append(cond)
        del egt_children[:]

    def on_parent(pid, cond):
        global egt_constraints
        global egt_children
        egt_constraints.append(cond)
        egt_children.append(pid)


    def egt_update_vars(src):
        value = ast.parse(src)
        return astunparse.unparse(UpdateNameTransformer().visit(value)).strip()
    """
    return dedent(tmpl)

def epilogue_tmpl():
    tmpl = """
    with open(".pids/%d" % egt_mypid, "w+") as f: f.write(egt_constraints.show())
    for pid in egt_children: os.waitpid(pid, 0)
    """
    return dedent(tmpl)


def if_tmpl(cond, body, orelse):
    tmpl = """
    parentpid = egt_mypid
    pid = os.fork()
    # get all variables in egt_constraints and make sure that the labels are correct
    # from egt_defined_vars
    if pid == 0:
        on_child("cond")
        body
    else:
        on_parent(pid, "cond")
        orelse
    """
    myast = parse(dedent(tmpl))
    myast.body[2].body[1] = body
    myast.body[2].body[0].value.args[0].s = astunparse.unparse(cond).strip()
    myast.body[2].orelse[1] = orelse
    myast.body[2].orelse[0].value.args[1].s =  "not " + astunparse.unparse(cond).strip()
    return fix_missing_locations(myast)

def assign_tmpl(target, value):
    # Make sure that the target is suitably renamed.
    # make sure that egt_defined_vars are reinitialized at the start of each block
    target_name = target.id

    tmpl = """
    newvar = 1
    egt_target = '{target_name}'
    if (egt_target in egt_defined_vars.keys()): newvar = egt_defined_vars[egt_target] + 1
    egt_target_value = egt_update_vars('{target_value}')
    egt_defined_vars[egt_target] = newvar
    egt_target_label = egt_target + ':' + str(newvar)
    egt_constraints.append(egt_target_label + " == " + egt_target_value)
    """.format(target_name=target_name,
         target_value = astunparse.unparse(value).strip())
    myast = parse(dedent(tmpl))
    return fix_missing_locations(myast)

def loop_tmpl(cond, body, orelse):
    """
    # Translate each loop to a while True loop
    while True:
        if cond: break
        body
    else:
        orelse
    """


class EgtTransformer(NodeTransformer):
    def visit_If(self, node):
        self.generic_visit(node)
        ifcond = node.test
        ifbody = node.body
        elbody = node.orelse
        # first we fork, and check the pid
        newnode = if_tmpl(ifcond, ifbody, elbody)
        return newnode

    def visit_Assign(self, node):
        self.generic_visit(node)
        newnode = assign_tmpl(node.targets[0], node.value)
        return newnode

def transform(tree):
    return EgtTransformer().visit(tree)

def main():
    tree = parse(slurp(sys.argv[1]))
    #print astunparse.dump(tree)
    print prologue_tmpl() + astunparse.unparse(transform(tree)) + epilogue_tmpl()
    #print dump(transform(tree))

main()
