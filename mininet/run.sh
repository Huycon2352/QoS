#!/bin/bash

sudo mn --custom topo.py --topo simpletopo \
  --controller=remote,ip=127.0.0.1,port=6653 \
  --switch ovsk,protocols=OpenFlow13
