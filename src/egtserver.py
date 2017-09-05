#!/usr/bin/env python
import Pyro4

import signal
import sys
import io
import os
import copy

egt_gconstraints = {}
@Pyro4.expose
class Constraints(object):
    def append(self, pid, forkedpid, constraint):
        global egt_gconstraints
        if pid not in egt_gconstraints: egt_gconstraints[pid] = []
        if forkedpid == 0: # child registering new constraint
            myconstraints = copy.copy(egt_gconstraints[pid])
            myconstraints.append(constraint)
            egt_gconstraints[pid] = myconstraints
            print "register child: %s" % constraint
        else: #update parent constraints
            egt_gconstraints[pid].append(constraint)
            print "register parent: %s" % constraint
egt_daemon = Pyro4.Daemon()
egt_uri = egt_daemon.register(Constraints)
print egt_uri

with open('.uri', 'w') as f: f.write(str(egt_uri))

def signal_handler(signal, frame):
    global egt_gconstraints
    print ""
    for k in egt_gconstraints.keys():
        print "%s: %s" % (k, egt_gconstraints[k])
        
    print ""
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
egt_daemon.requestLoop()
