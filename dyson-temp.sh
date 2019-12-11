#!/bin/sh
#
# (c) 2019 Yoichi Tanibayashi
#
MYNAME=`basename $0`

SEND_CMD="${HOME}/bin/dyson.sh"

usage () {
    echo "usage: ${MYNAME} temp"
}
	   
if [ X$1 = X ]; then
    usage
    exit 1
fi

TEMP=$1

TEMP10=`expr $TEMP / 10`
TEMP1=`expr $TEMP % 10`

${SEND_CMD} temp_down_40-

while [ ${TEMP10} -gt 0 ]; do
    ${SEND_CMD} temp_up_10-
    TEMP10=`expr $TEMP10 - 1`
done

while [ ${TEMP1} -gt 0 ]; do
    ${SEND_CMD} temp_up
    TEMP1=`expr $TEMP1 - 1`
done
