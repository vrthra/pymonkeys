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


def if_tmpl(cond, body, orelse):
    tmpl = """
    pid = os.fork()
    # get all variables in constraints and make sure that the labels are correct
    # from defined_vars
    if pid == 0:
        constraints.add("cond")
        body
    else:
        constraints.add("notcond")
        orelse
    """
    ast = parse(dedent(tmpl))
    ast.body[1].body[1] = body
    ast.body[1].body[0].value.args[0].s = astunparse.unparse(cond).strip()
    ast.body[1].orelse[1] = orelse
    ast.body[1].orelse[0].value.args[0].s = astunparse.unparse(cond).strip()
    return ast


def assign_tmpl(target, value):
    # Make sure that the target is suitably renamed.
    # make sure that defined_vars are reinitialized at the start of each block
    """
    newvar = 1
    if (target in keys(defined_vars)):
       newvar = defined_vars[target] + 1
    defined_vars[target] = newvar
    target_label = target + ':' + newvar
    constraints.add("target_label == v")
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
    print "-------"
    print astunparse.unparse(transform(tree))
    #print dump(transform(tree))

main()
