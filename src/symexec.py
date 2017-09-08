#!/usr/bin/env python
import sys
from textwrap import dedent
import ast
import astunparse
from astmonkey import transformers

def slurp(src):
    with open(src) as x: return x.read()

class EgtTransformer(ast.NodeTransformer):

    def visit_If(self, node):
        tmpl = """
        if myegt.fork('{cond}', globals(), locals()) == 0:
            myegt.solver.add(eval(myegt.labelize('{cond}')))
        else:
            myegt.solver.add(eval('z3.Not%s' % myegt.labelize('{cond}')))
        """
        condsrc =  astunparse.unparse(node.test).strip()
        ifstmt = ast.parse(dedent(tmpl.format(cond=condsrc))).body[0]

        ifstmt.body.extend(node.body)
        ifstmt.orelse.extend(node.orelse)
        ifstmt = ast.fix_missing_locations(ast.copy_location(ifstmt, node))
        return self.generic_visit(ifstmt)

    def visit_Assign(self, node):
        # TODO: make sure that egt_defined_vars are reinitialized at the start of each block
        tmpl = """
        (name, value) = myegt.on_assign('{name}', '{value}', globals(), locals())
        v[name] = value
        myegt.solver.add(v[name] == value)
        """.format(name=node.targets[0].id,
                   value = astunparse.unparse(node.value).strip())
        return ast.fix_missing_locations(ast.copy_location(ast.parse(dedent(tmpl)), node))

    def visit_Print(self, node):
        # self.generic_visit(node)
        if isinstance(node.values[0], ast.Str): return node
        tmpl = """
        print myegt.on_print('{value}', globals(), locals())
        """.format(value = astunparse.unparse(node.values[0]).strip())
        return ast.fix_missing_locations(ast.copy_location(ast.parse(dedent(tmpl)), node))

    def visit_While(self, node):
        if node.orelse != []: raise Exception("Cant handle while:else")
        # Translate each loop to a while sat loop
        tmpl = """
        for i in range(0, egt.Maxiter):
            if {cond}:
                body
            else:
                orelse
                break
        """
        condsrc =  astunparse.unparse(node.test).strip()
        fornode = ast.parse(dedent(tmpl.format(cond=condsrc))).body[0]

        ifnode = fornode.body[0]
        ifnode.body = node.body
        ifnode.orelse = node.orelse
        fornode.body[0] = self.visit(ifnode)
        return ast.fix_missing_locations(ast.copy_location(fornode, node))

def symbolic_transform(src):
    return astunparse.unparse(EgtTransformer().visit(ast.parse(src)))

def main(fname):
    tmpl = """
    import os
    import egt
    import z3
    myegt = egt.Egt()
    v = {}
    %s
    myegt.epilogue()
    """
    print dedent(tmpl) % symbolic_transform(slurp(fname))

main(sys.argv[1])
