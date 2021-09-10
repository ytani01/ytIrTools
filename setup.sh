#!/bin/sh
#
# (c) 2020 Yoichi Tanibayashi
#
GITS="ytMQTT common_python"
CMDS="IrAnalyze.py IrSendCmdServer.py IrSendCmdClient.py AutoAirconServer.py"
BINCMDS="boot-ir.sh ir-analyze ir-send dyson.sh dyson-temp.sh tv-light-level.sh"

echo "GITS=${GITS}"
echo "CMDS=${CMDS}"
echo "BINCMDS=${BINCMDS}"

MYNAME=`basename $0`
echo "MYNAME=${MYNAME}"

cd `dirname $0`
MYDIR=`pwd`
echo "MYDIR=${MYDIR}"

GITNAME=`basename ${MYDIR}`
echo "GITNAME=$GITNAME"

VENV_DIR=`dirname ${MYDIR}`
echo "VENV_DIR=${VENV_DIR}"

BINDIR="${VENV_DIR}/bin"
echo "BINDIR=${BINDIR}"
if [ ! -d ${BINDIR} ]; then
    echo "${BINDIR}: no such directory" >&2
fi

HOMEBIN="${HOME}/bin"
echo "HOMEBIN=${HOMEBIN}"
if [ ! -d ${HOMEBIN} ]; then
    mkdir -pv ${HOMEBIN}
fi

LOGDIR="${HOME}/tmp"
echo "LOGDIR=${LOGDIR}"
if [ ! -d ${LOGDIR} ]; then
    mkdir -pv ${LOGDIR}
fi

IRCONF_D="${HOME}/.irconf.d"
echo "IRCONF_D=${IRCONF_D}"
if [ ! -d ${IRCONF_D} ]; then
    mkdir -pv ${IRCON_D}
fi
ln -sfv ${MYDIR}/irconf.d/* ${IRCONF_D}

CRONTAB_FILE="crontab.sample"
echo "CRONTAB_FILE=${CRONTAB_FILE}"

##### main
if [ ! -f ${BINDIR}/activate ]; then
    echo "${BINDIR}/activate: no such file" >&2
    exit 1
fi
. ${BINDIR}/activate

echo "VIRTUAL_ENV=${VIRTUAL_ENV}"
ln -s ${BINDIR}/activate ${HOMEBIN}/activate-${GITNAME}

cd ${VIRTUAL_ENV}
echo "[" `pwd` "]"

for g in ${GITS}; do
    git clone git@github.com:ytani01/${g}
done

cd ${MYDIR}
echo "[" `pwd` "]"

# Python3 packages
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt 
fi

# install Node-RED
### T.B.D ###

# AutoAircon configuration files
cp -v dot.autoaircon ${HOME}/.autoaircon 
cp -v dot.autoaircon-param ${HOME}/.autoaircon-param

# copy Command files
for c in ${CMDS}; do
    ln -sfv ${MYDIR}/$c ${BINDIR}/$c
done

for c in ${BINCMDS}; do
    ln -sfv ${MYDIR}/$c ${HOMEBIN}/$c
done

# activate-exec.sh
ln -sv ${VIRTUAL_ENV}/common_python/activate-exec.sh ${HOMEBIN}

# crontab (auto boot)
#cd ${MYDIR}
#crontab -l ${HOME}/tmp/crontab.bak
#crontab ${CRONTAB_FILE}
