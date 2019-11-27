#!/bin/sh

COUNT=$1

while [ $COUNT -gt 0 ]; do
    echo $COUNT
    ./TcpCmdClient.py -s 192.168.0.220 -p 12399 irsend lamp &
#    sleep 1
    ./TcpCmdClient.py -s 192.168.0.220 -p 12399 -t .1 irsend lamp on &
#    sleep 1
    ./TcpCmdClient.py -s 192.168.0.220 -p 12399 -t .1 irsend lamp off &
#    sleep 1
    COUNT=`expr $COUNT - 1`
done
