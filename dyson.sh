#!/bin/sh
#
# (c) 2019 Yoichi Tanibayashi
#
MYNAME=`basename $0`

SERIAL_NUM_FILE="${HOME}/.dyson.serial"

DEV_NAME="dyson_am05"
SERIAL_MAX=3

SEND_CMD="ir-send"

if [ ! -f ${SERIAL_NUM_FILE} ]; then
    echo 0 > ${SERIAL_NUM_FILE}
fi
SERIAL_NUM=`cat ${SERIAL_NUM_FILE}`

while [ X$1 != X ]; do
    BUTTON_NAME=$1${SERIAL_NUM}

    SERIAL_NUM=`expr \( ${SERIAL_NUM} + 1 \) % ${SERIAL_MAX}`
    echo ${SERIAL_NUM} > ${SERIAL_NUM_FILE}

    ${SEND_CMD} ${DEV_NAME} ${BUTTON_NAME}

    shift
done
