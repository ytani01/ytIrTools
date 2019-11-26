#!/bin/sh

COUNT=$1

while [ $COUNT -gt 0 ]; do
    echo $COUNT
    ./TcpCmdClient.py -s 192.168.0.220 -p 12399 $COUNT &
    COUNT=`expr $COUNT - 1`
done
