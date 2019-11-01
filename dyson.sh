#!/bin/sh
#
# (c) 2019 Yoichi Tanibayashi
#
MYNAME=`basename $0`

SERIAL_NUM_FILE="${HOME}/.dyson.serial"

DEV_NAME="dyson_am05"
SERIAL_MAX=3

SEND_CMD="IrSend.py"

if [ ! -f ${SERIAL_NUM_FILE} ]; then
    echo 0 > ${SERIAL_NUM_FILE}
fi
SERIAL_NUM=`cat ${SERIAL_NUM_FILE}`

while true; do
    BUTTON_NAME=$1
    
    if [ X${BUTTON_NAME} != X ]; then
	BUTTON_NAME="${BUTTON_NAME}${SERIAL_NUM}"
	SERIAL_NUM=`expr ${SERIAL_NUM} + 1`
	if [ ${SERIAL_NUM} -eq ${SERIAL_MAX} ]; then
	    SERIAL_NUM="0"
	fi
	echo ${SERIAL_NUM} > ${SERIAL_NUM_FILE}
    fi

    ${SEND_CMD} ${DEV_NAME} ${BUTTON_NAME}

    if [ X$1 != X ]; then
	shift
    fi
    if [ X$1 = X ]; then
	break
    fi
done
