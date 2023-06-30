#!/bin/sh
#
# (c) 2019 Yoichi Tanibayashi
#
MYNAME=`basename $0`
MYDIR=`dirname $0`

export PATH=${MYDIR}:${PATH}


DATE_FMT="%Y/%m/%d %H:%M:%S"
ts_echo () {
    echo "`date +"${DATE_FMT}"`> $*"
}

ts_echo "${MYNAME}: start"

GITNAME="ytIrTools"
. ${HOME}/bin/activate-${GITNAME}
ts_echo "VIRTUAL_ENV=${VIRTUAL_ENV}"

LOGDIR=${HOME}/tmp
ts_echo "LOGDIR=${LOGDIR}"

NAME_PIGPIOD="pigpiod"
PID_PIGPIOD=`pgrep ${NAME_PIGPIOD}`
ts_echo "PID_PIGPIOD=${PID_PIGPIOD}"

NAME_IRSENDSERVER="IrSendCmdServer"
LOG_IRSENDSERVER=${LOGDIR}/${NAME_IRSENDSERVER}.log
PID_IRSENDSERVER=`pgrep -f python.\*${NAME_IRSENDSERVER}.py`
ts_echo "PID_IRSENDSERVER=${PID_IRSENDSERVER}"

NAME_AUTOAIRCON="AutoAirconServer"
PARAM_AUTOAIRCON="--mqtt_svr mqtt.ytani.net"
LOG_AUTOAIRCON=${LOGDIR}/${NAME_AUTOAIRCON}.log
PID_AUTOAIRCON=`pgrep -f python.\*${NAME_AUTOAIRCON}.py`
ts_echo "PID_AUTOAIRCON=${PID_AUTOAIRCON}"
#TARGET_TEMP=25
TARGET_TEMP=28

if [ X$PID_PIGPIOD = X ]; then
    ts_echo "start pigpiod"
    sudo pigpiod -t 0
fi

while [ `/sbin/ifconfig -a | grep inet | grep -v inet6 | grep -v 127.0.0 | wc -l` -eq 0 ]; do
    ts_echo ".."
    sleep 1
done

if [ X$PID_IRSENDSERVER = X ]; then
    if [ -f ${LOG_IRSENDSERVER} ]; then
	mv -fv ${LOG_IRSENDSERVER} ${LOG_IRSENDSERVER}.1
    fi
    ts_echo "start ${NAME_IRSENDSERVER}"
    ${NAME_IRSENDSERVER}.py > ${LOG_IRSENDSERVER} 2>&1 &
fi

if [ X$PID_AUTOAIRCON = X ]; then
    if [ -f ${LOG_AUTOAIRCON} ]; then
	mv -fv ${LOG_AUTOAIRCON} ${LOG_AUTOAIRCON}.1
    fi
    ts_echo "start ${NAME_AUTOAIRCON}"
    ${NAME_AUTOAIRCON}.py $PARAM_AUTOAIRCON $TARGET_TEMP > $LOG_AUTOAIRCON 2>&1 &
fi

ts_echo "${MYNAME}: end"
