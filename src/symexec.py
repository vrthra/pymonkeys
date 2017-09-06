#!/usr/bin/env python
import sys
from textwrap import dedent
import ast
import astunparse
from astmonkey import transformers

def slurp(src):
    with open(src) as x: return x.read()

def if_tmpl(cond, body, orelse):
    tmpl = """
    pid = egt.fork()
    if pid == 0:
        egt.solver.add(eval(egt.labelize('{cond}')))
        body
    else:
        egt.solver.add(eval('z3.Not%s' % egt.labelize('{cond}')))
        orelse
    """
    condsrc =  astunparse.unparse(cond).strip()
    myast = ast.parse(dedent(tmpl.format(cond=condsrc)))
    ifbody = myast.body[1]
    ifbody.body[1] = body
    ifbody.orelse[1] = orelse

    return ast.fix_missing_locations(myast)

def assign_tmpl(target, value):
    # TODO: make sure that egt_defined_vars are reinitialized at the start of each block
    # Make sure that the target is suitably renamed.
    tmpl = """
    value = None
    if '{value}' != 'input()':
        value = eval(egt.labelize('{value}'))
    name = egt.new_label('{name}')
    if not value: value = egt.symbolic(name)
    v[name] = value
    egt.solver.add(v[name] == value)
    """.format(name=target.id, value = astunparse.unparse(value).strip())
    myast = ast.parse(dedent(tmpl))
    return ast.fix_missing_locations(myast)

def loop_tmpl(cond, body, orelse):
    """
    # Translate each loop to a while True loop
    while True:
        if cond: break
        body
    else:
        orelse
    """

class EgtTransformer(ast.NodeTransformer):
    def visit_If(self, node):
        self.generic_visit(node)
        return if_tmpl(node.test, node.body, node.orelse)

    def visit_Assign(self, node):
        self.generic_visit(node)
        return assign_tmpl(node.targets[0], node.value)

def transform(tree):
    newtree = transformers.ParentChildNodeTransformer().visit(tree)
    return EgtTransformer().visit(newtree)

def main(src):
    tree = ast.parse(slurp(src))
    tmpl = """
    import os
    import egt
    import z3
    egt = egt.Egt()
    v = {}
    %s
    egt.epilogue()
    """
    print dedent(tmpl) % astunparse.unparse(transform(tree))

main(sys.argv[1])
