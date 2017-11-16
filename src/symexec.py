#!/usr/bin/env python3
# Author: Rahul Gopinath <rahul.gopinath@cispa.saarland>
# License: GPLv3

import sys
from textwrap import dedent
import ast
import astunparse
from astmonkey import transformers

def slurp(src):
    with open(src) as x: return x.read()

class EgtTransformer(ast.NodeTransformer):
    """
    Transform the given sourcefile to concolic execution source
    The source file generated can be executed by passing it to python3
    """

    def visit_If(self, node):
        """
        Transforms the if condition such that we fork, and pass the
        condtion=True to child, and condition=False keeps executing in the
        parent.
        If the condition=True is not satisfiable, we do not create the child
        Similarly, if condition=False is not satisfiable, we do not create the
        child, but execute the condtion=True in the parent.
        """
        # Note that the template (tmpl) is taken apart, and put back together.
        # Hence, comments within do not translate to the transformed source.
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
        """
        Transforms any assignments to the concolic execution source.
        To make our life easier, we use a single dict -- egt_v -- for all our
        variables. We query the egt_v when an assignment happens. If the
        variable was not assigned before, we assign variable:0 to it. If
        it was assigned before, we increment the count -- variable:n+1
        This transforms the code into a single assignment form within the
        non-looped portions.
        Keeping the variable names within the dict allows us to increment
        the variable names dynamically within loops, and hence use single
        assignment form even in loops -- which makes it easy to generate
        formulas for satisfiability.

        Using a single dict means tha scope resolution rules are yet to be done,
        and can be accomplished by making egt_v a scope aware object.
        """
        # TODO: make sure that egt_defined_vars are reinitialized at the start
        # of each block
        tmpl = """
        (name, value) = myegt.on_assign('{name}', '{value}', globals(), locals())
        egt_v[name] = value
        myegt.solver.add(egt_v[name] == value)
        """.format(name=node.targets[0].id,
                   value = astunparse.unparse(node.value).strip())
        return ast.fix_missing_locations(ast.copy_location(ast.parse(dedent(tmpl)), node))

    def visit_Call(self, node):
        """
        For now, we only transform the print statements. They have to be handled
        separately because it is a library call that occurs frequently.
        """
        def process_arg(n):
            if type(n) is ast.Str:
                return "''%s''" % astunparse.unparse(n).strip()
            else:
                return astunparse.unparse(n)

        # self.generic_visit(node)
        if type(node.func) is not ast.Name: return node
        if node.func.id != 'print': return node
        tmpl = """
        print(myegt.on_print({args}, globals(), locals()), {kwords})
        """.format(args=[process_arg(na) for na in node.args], kwords=astunparse.unparse(node.keywords).strip())
        return ast.fix_missing_locations(ast.copy_location(ast.parse(dedent(tmpl)), node))

    def visit_While(self, node):
        """
        Transforms any while conditions to a loop of fixed depth (egt.Maxiter),
        with loop check being done by an if condition. Only While loops are
        complete. The For/AsyncFor constructs (generators) are still to be done.
        """
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

def main(args):
    tmpl = """
    import os
    import egt
    import z3
    myegt = egt.Egt()
    egt_v = {}
    %s
    myegt.epilogue()
    """
    print(dedent(tmpl) % symbolic_transform(slurp(args[1])))

if __name__ == '__main__': main(sys.argv)
