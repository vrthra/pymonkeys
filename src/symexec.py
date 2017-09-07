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
    (name, value) = egt.on_assign('{name}', '{value}', globals(), locals())
    v[name] = value
    egt.solver.add(v[name] == value)
    """.format(name=target.id, value = astunparse.unparse(value).strip())
    myast = ast.parse(dedent(tmpl))
    return ast.fix_missing_locations(myast)

def while_tmpl(cond, body, orelse):
    if orelse != []: raise Exception("Cant handle while:else")
    tmpl = """
    # Translate each loop to a while sat loop
    while egt.sat():
        if egt.maxiter(): break
        pid = egt.fork()
        if pid == 0:
            egt.solver.add(eval(egt.labelize('{cond}')))
            body
        else:
            egt.solver.add(eval('z3.Not%s' % egt.labelize('{cond}')))
            orelse
            break
    """
    condsrc =  astunparse.unparse(cond).strip()
    myast = ast.parse(dedent(tmpl.format(cond=condsrc)))
    whilebody = myast.body[0]
    ifbody = whilebody.body[2]
    ifbody.body[1] = body
    ifbody.orelse[1] = orelse

    return ast.fix_missing_locations(whilebody)


class EgtTransformer(ast.NodeTransformer):
    def visit_If(self, node):
        self.generic_visit(node)
        return if_tmpl(node.test, node.body, node.orelse)

    def visit_Assign(self, node):
        self.generic_visit(node)
        return assign_tmpl(node.targets[0], node.value)

    def visit_While(self, node):
        self.generic_visit(node)
        cond = node.test
        whilebody = node.body
        return while_tmpl(node.test, node.body, node.orelse)

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
