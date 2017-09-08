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
        self.generic_visit(node)
        cond = node.test
        body = node.body
        orelse = node.orelse
        tmpl = """
        pid = myegt.fork('{cond}', globals(), locals())
        if pid == 0:
            myegt.solver.add(eval(myegt.labelize('{cond}')))
            body
        else:
            myegt.solver.add(eval('z3.Not%s' % myegt.labelize('{cond}')))
            orelse
        """
        condsrc =  astunparse.unparse(cond).strip()
        myast = ast.parse(dedent(tmpl.format(cond=condsrc)))
        ifbody = myast.body[1]
        ifbody.body[1] = body
        ifbody.orelse[1] = orelse
        return ast.copy_location(myast, node)

    def visit_Assign(self, node):
        self.generic_visit(node)
        target = node.targets[0]
        value = node.value
        # TODO: make sure that egt_defined_vars are reinitialized at the start of each block
        # Make sure that the target is suitably renamed.
        tmpl = """
        (name, value) = myegt.on_assign('{name}', '{value}', globals(), locals())
        v[name] = value
        myegt.solver.add(v[name] == value)
        """.format(name=target.id, value = astunparse.unparse(value).strip())
        return ast.fix_missing_locations(ast.copy_location(ast.parse(dedent(tmpl)), node))

    def visit_Print(self, node):
        self.generic_visit(node)
        if isinstance(node.values[0], ast.Str): return node
        tmpl = """
        print myegt.on_print('{value}', globals(), locals())
        """.format(value = astunparse.unparse(node.values[0]).strip())
        return ast.fix_missing_locations(ast.copy_location(ast.parse(dedent(tmpl)), node))

class PreLoopTransformer(ast.NodeTransformer):

    def visit_While(self, node):
        self.generic_visit(node)

        cond = node.test
        body = node.body
        orelse = node.orelse
        if orelse != []: raise Exception("Cant handle while:else")
        # Translate each loop to a while sat loop
        tmpl = """
        for i in range(0, egt.Maxiter):
            if {cond}:
                body
            else:
                orelse
                break
        """
        condsrc =  astunparse.unparse(cond).strip()
        myast = ast.parse(dedent(tmpl.format(cond=condsrc)))
        fornode = myast.body[0]
        ifnode = fornode.body[0]
        ifnode.body[0] = body
        ifnode.orelse[0] = orelse

        return ast.fix_missing_locations(ast.copy_location(fornode, node))


def symbolic_transform(src):
    return astunparse.unparse(EgtTransformer().visit(ast.parse(src)))

def loop_preprocess(src):
    return astunparse.unparse(PreLoopTransformer().visit(ast.parse(src)))

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
    # Hack warning: The tree nodes inserted by loop replacement is not
    # visited by the EgtTransformer unless converted back into source and
    # reconverted.
    preprocessed = loop_preprocess(slurp(fname))
    print dedent(tmpl) % symbolic_transform(preprocessed)

main(sys.argv[1])
