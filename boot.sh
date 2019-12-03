#!/bin/sh
#
# (c) 2019 Yoichi Tanibayashi
#
MYNAME=`basename $0`

DATE_FMT="%Y/%m/%d %H:%M:%S"

ts_echo () {
    echo `date +"${DATE_FMT}"` $*
}

ts_echo "> ${MYNAME}: start"

NAME_PIGPIOD="pigpiod"
NAME_IRSENDSERVER="IrSendCmdServer"
NAME_AUTOAIRCON="AutoAirconServer"

LOGDIR=${HOME}/tmp
LOG_IRSENDSERVER=${LOGDIR}/${NAME_IRSENDSERVER}.log
LOG_AUTOAIRCON=${LOGDIR}/${NAME_AUTOAIRCON}.log

PID_PIGPIOD=`pgrep ${NAME_PIGPIOD}`
PID_IRSENDSERVER=`pgrep -f python.\*${NAME_IRSENDSERVER}.py`
PID_AUTOAIRCON=`pgrep -f python.\*${NAME_AUTOAIRCON}.py`

if [ X$PID_PIGPIOD = X ]; then
    ts_echo "start pigpiod"
    sudo pigpiod -t 0
    sleep 3
fi

while [ `/sbin/ifconfig -a | grep inet | grep -v inet6 | grep -v 127.0.0 | wc -l` -eq 0 ]; do
    ts_echo ".."
    sleep 1
done

if [ X$PID_IRSENDSERVER = X ]; then
    mv -f ${LOG_IRSENDSERVER} ${LOG_IRSENDSERVER}.1
    ts_echo "start ${NAME_IRSENDSERVER}"
    ${HOME}/bin/${NAME_IRSENDSERVER}.py > ${LOG_IRSENDSERVER} 2>&1 &
fi

if [ X$PID_AUTOAIRCON = X ]; then
    mv -f ${LOG_AUTOAIRCON} ${LOG_AUTOAIRCON}.1
    ts_echo "start ${NAME_AUTOAIRCON}"
    ${HOME}/bin/${NAME_AUTOAIRCON}.py > ${LOG_AUTOAIRCON} 2>&1 &
fi

ts_echo "< ${MYNAME}: end"
