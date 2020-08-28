#!/bin/sh
#
# (c) 2020 Yoichi Tanibayashi
#
MYNAME=`basename $0`

DEV_NAME="lamp"
VAL_COUNT_MAX=7
VAL_COUNT_MIN=0

IR_CMD="$HOME/bin/ir-send"

usage() {
    echo "    usage: ${MYNAME} blightness($VAL_MIN..$VAL_MAX)"
}

if [ -z "$1" ]; then
    usage
    exit 1
fi

echo $1 | grep '^[0-9]*$' > /dev/null
if [ $? != 0 ]; then
    usage
    exit 1
fi
VAL=$1

if [ $VAL -lt $VAL_MIN -o $VAL -gt $VAL_MAX ]; then
    usage
    exit 1
fi

if [ $VAL -eq 100 ]; then
    VAL=99
fi
VAL_COUNT=`expr \( $VAL_COUNT_MAX - $VAL_COUNT_MIN + 1 \) \* $VAL / 100`
echo "VAL_COUNT=$VAL_COUNT"

$IR_CMD $DEV_NAME on down down down down down down down down

COUNT=0
while [ $COUNT -lt $VAL_COUNT ]; do
    $IR_CMD $DEV_NAME up
    COUNT=`expr $COUNT + 1`
done
