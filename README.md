# QoS

# How to deploy

+ Git clone : git clone https://github.com/Huycon2352/QoS
+ Run Ryu COntroller : ryu-manager dynamic_access_controller.py
+ Run mininet : mn --custom topology.py --topo dynamicaccesstopo --controller=remote --switch ovsk,protocols=OpenFlow13 --mac
+ Run apply queue setup shapping : ./setup_qos.sh s1-eth4
