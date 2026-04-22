#Deploy
+run ryu :ryu run ryu_app.py
+ Run mininet : sudo mn --custom topo.py --topo qos_topo --controller=remote --switch ovs,protocols=OpenFlow13
+ Apply QoS RBAC Shapping : ./setup_ovs_qos.sh 


Test : Using Ping or Iperf3 -s , more effect with xterm
