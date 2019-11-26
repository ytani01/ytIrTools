#!/bin/sh

COUNT=$1

while [ $COUNT -gt 0 ]; do
    echo $COUNT
    TcpCmdClient.py -p 12399 $COUNT &
    COUNT=`expr $COUNT - 1`
done
