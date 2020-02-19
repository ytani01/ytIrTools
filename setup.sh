#!/bin/sh
#
# (c) 2020 Yoichi Tanibayashi
#
MYNAME=`basename $0`
MYDIR=`pwd`
GITNAME=`basename $MYDIR`
echo "MYNAME=$MYNAME"
echo "MYDIR=$MYDIR"
echo "GITNAME=$GITNAME"

BINDIR="${HOME}/bin"
if [ ! -d ${BINDIR} ]; then
    mkdir -pv ${BINDIR}
fi

LOGDIR="${HOME}/tmp"

IRCONF_D=${HOME}/.irconf.d

MQTT_DIR="ytMQTT"

echo 
##### main
if [ X${VIRTUAL_ENV} = X ]; then
    echo "You must use venv."
    exit 1
fi
VENV_NAME=`basename ${VIRTUAL_ENV}`
echo "VENV_NAME=$VENV_NAME"

if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt 
fi


ln -sfv ${VIRTUAL_ENV}/bin/activate ${BINDIR}/activate-${GITNAME}


cp -v dot.autoaircon ${HOME}/.autoaircon 
cp -v dot.autoaircon-param ${HOME}/.autoaircon-param


echo "${MQTT_DIR} .."
if [ -d ../${MQTT_DIR} ]; then
    echo "found."
else
    cd ..
    pwd
    git clone git@github.com:ytani01/${MQTT_DIR}.git
fi

cd ${BINDIR}
echo "[" `pwd` "]"

for f in ir-analyze ir-send IrAnalyze.py IrSendCmdServer.py IrSendCmdClient.py AutoAirconServer.py boot.sh dyson.sh dyson-temp.sh tv-light-level.sh ; do
    ln -sfv ${MYDIR}/$f ${BINDIR}/$f
done
