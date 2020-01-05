#!/bin/sh
#
# (c) 2019 Yoichi Tanibayashi
#
MYNAME=`basename $0`

IRSEND_CMD="$HOME/bin/ir-send"
DEV_NAME="tv-light"
BUTTON_UP="up"
BUTTON_DOWN="down"
LEVEL_MIN=1
LEVEL_MAX=5


### func
usage () {
    echo "usage: ${MYNAME} level (1 .. 5)"
}

irsend_n () {
    button=$1
    count=$2
    while [ $count -gt 0 ]; do
	CMDLINE="$IRSEND_CMD $DEV_NAME $button"
	echo -n "($count) $CMDLINE: "
	eval $CMDLINE
	count=`expr $count - 1`
    done
}


### main
if [ X$1 = X ]; then
    usage
    exit 1
fi

LEVEL=$1

irsend_n $BUTTON_DOWN `expr $LEVEL_MAX - $LEVEL_MIN`
irsend_n $BUTTON_UP   `expr $LEVEL     - $LEVEL_MIN`

exit 0
