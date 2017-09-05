#!/usr/bin/env python
import sys
from textwrap import dedent
import os
from ast import *
import astunparse

def slurp(src):
    with open(src) as x:
        f = x.read()
        return f

def parse_source(source):
    src = slurp(source) 
    return parse(src)

def prologue_tmpl():
    tmpl = """
    import os
    import signal
    import Pyro4

    egt_uri = ""
    with open(".uri", "r") as x: egt_uri = x.read()
    print egt_uri

    egt_constraints = Pyro4.Proxy(egt_uri)

    egt_defined_vars = {}
    egt_pids = []
    egt_children = []
    egt_path = ''

    def on_child(ppid, pid, cond):
        global egt_constraints
        global egt_pids
        egt_constraints.append(ppid, pid, cond)
        del egt_children[:]

    def on_parent(ppid, pid, cond):
        global egt_constraints
        global egt_children
        egt_constraints.append(ppid, pid, cond)
        egt_children.append(pid)

    """
    return dedent(tmpl)

def epilogue_tmpl():
    tmpl = """
    for i in egt_children:
        if i != os.getpid():
          print "wait child %i" % i
          os.waitpid(i, 0)
    """
    return dedent(tmpl)


def if_tmpl(cond, body, orelse):
    tmpl = """
    pid = os.fork()
    # get all variables in egt_constraints and make sure that the labels are correct
    # from egt_defined_vars
    if pid == 0:
        on_child(os.getpid(), pid, "cond")
        body
    else:
        on_parent(os.getpid(), pid, "cond")
        orelse
    """
    myast = parse(dedent(tmpl))
    myast.body[1].body[1] = body
    myast.body[1].body[0].value.args[2].s = astunparse.unparse(cond).strip()
    myast.body[1].orelse[1] = orelse
    myast.body[1].orelse[0].value.args[2].s =  "not " + astunparse.unparse(cond).strip()
    return fix_missing_locations(myast)


def assign_tmpl(target, value):
    # Make sure that the target is suitably renamed.
    # make sure that egt_defined_vars are reinitialized at the start of each block
    """
    newvar = 1
    if (target in keys(egt_defined_vars)):
       newvar = egt_defined_vars[target] + 1
    egt_defined_vars[target] = newvar
    target_label = target + ':' + newvar
    egt_constraints.append("target_label == v")
    """

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

class RewriteName(NodeTransformer):
    def visit_Name(self, node):
        return copy_location(Subscript(
            value=Name(id='data', ctx=Load()),
            slice=Index(value=Str(s=node.id)),
            ctx=node.ctx
        ), node)

def transform(tree):
    return EgtTransformer().visit(tree)

def main():
    tree = parse_source(sys.argv[1])
    #print astunparse.dump(tree)
    print prologue_tmpl() + astunparse.unparse(transform(tree)) + epilogue_tmpl()
    #print dump(transform(tree))

main()
