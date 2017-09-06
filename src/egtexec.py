#!/usr/bin/env python
import sys
from textwrap import dedent
import ast
import astunparse

def slurp(src):
    with open(src) as x: return x.read()

def if_tmpl(cond, body, orelse):
    tmpl = """
    pid = egt.fork('%s')
    if pid == 0:
        body
    else:
        orelse
    """
    condsrc =  astunparse.unparse(cond).strip()
    myast = ast.parse(dedent(tmpl % condsrc))
    ifbody = myast.body[1]
    ifbody.body[0] = body
    ifbody.orelse[0] = orelse

    return ast.fix_missing_locations(myast)

def assign_tmpl(target, value):
    # TODO: make sure that egt_defined_vars are reinitialized at the start of each block
    # Make sure that the target is suitably renamed.
    tmpl = """
    egt.on_assignment('{target_name}', '{target_value}')
    """.format(target_name=target.id, target_value = astunparse.unparse(value).strip())
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
    return EgtTransformer().visit(tree)

def main():
    tree = ast.parse(slurp(sys.argv[1]))
    tmpl = """
    import os
    import egt
    egt = egt.Egt()
    %s
    egt.epilogue()
    """
    print dedent(tmpl) % astunparse.unparse(transform(tree))

main()
