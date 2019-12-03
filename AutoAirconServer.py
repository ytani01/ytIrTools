#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
Auto aircon server

  bhdr := button header
  ttemp := target temp
  rtemp := remocon temp
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from TcpCmdServer import Cmd, CmdServerApp
from TcpCmdClient import TcpCmdClient
from ytBeebotte import Beebotte
from IrSendCmdClient import IrSendCmdClient

import json
import os
import configparser

from MyLogger import get_logger


class ParamClient(TcpCmdClient):
    DEF_SVR_HOST = 'localhost'
    DEF_SVR_PORT = 51888

    DEF_TIMEOUT = 2  # sec

    def __init__(self, host=DEF_SVR_HOST, port=DEF_SVR_PORT, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('host=%s, port=%s', host, port)

        super().__init__(host, port, self._debug)

    def send_param(self, param):
        self._logger.debug('param=%s', param)

        param_str = json.dumps(param)
        ret = self.send_recv_str(param_str, timeout=0)
        ret_json = json.loads(ret)
        if ret_json['rc'] == 'OK':
            self._logger.debug('ret=%s', ret)
        else:
            self._logger.error('ret=%s', ret)


class Aircon(IrSendCmdClient):
    DEF_DEV = 'aircon'
    DEF_BHDR = 'on_hot_auto_'
    DEF_IR_HOST = 'localhost'

    TEMP_OFF = 0

    def __init__(self, dev=DEF_DEV, bhdr=DEF_BHDR, ir_host=DEF_IR_HOST,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev=%s, bhdr=%s, ir_host=%s',
                           dev, bhdr, ir_host)

        self._dev = dev
        self._bhdr = bhdr
        self._rtemp = 0

        super().__init__(ir_host, debug=self._debug)

    def set_temp(self, rtemp, force=False):
        self._logger.debug('rtemp=%s', rtemp)

        if not force:
            if rtemp == self._rtemp:
                self._logger.debug('rtemp==_rtemp=%s', self._rtemp)
                return

        self._rtemp = rtemp

        button = self._bhdr + '%02d' % rtemp
        if rtemp == self.TEMP_OFF:
            button = 'off'
        self._logger.debug('button=%s', button)

        args = [self._dev, button]

        try:
            ret = self.send_recv(args)
        except Exception as e:
            self._logger.error('%s:%s', type(e), e)
        else:
            self._logger.info('%s:%s', args, self.reply2str(ret))


class TempHist:
    """
    _val := [{'temp': temp1, 'ts': ts1}, {'temp': temp2, 'ts': ts2}, .. ]
    """
    DEF_HIST_LEN = 60  # sec

    def __init__(self, val=[], debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('val=%s', val)

        self._val = val
        self._i = 0

    def add(self, temp, ts):
        self._logger.debug('val=%s', temp)

        self._val.append({'temp': temp, 'ts': ts})

        while ts - self._val[0]['ts'] > self.DEF_HIST_LEN:
            v = self._val.pop(0)
            self._logger.debug('  remove: %s', v)

        for v in self._val:
            self._logger.debug('  %s', v)
        return self._val

    def len(self):
        return len(self._val)

    def get(self, idx):
        return self._val[idx]

    def ave(self):
        temp_sum = 0.0
        temp_n = 0
        for v in self._val:
            temp_sum += v['temp']
            temp_n += 1
        temp_ave = temp_sum / temp_n
        self._logger.debug('temp_ave=%.2f', temp_ave)
        return temp_ave


class AutoAirconCmd(Cmd):
    """
    """
    CONF_FILENAME = ['autoaircon.conf', '.autoaircon.conf', '.autoaircon']
    CONF_PATH = ['.', os.environ['HOME'], '/etc']

    DEF_PORT = 12359

    DEF_TTEMP = 26

    RTEMP_MIN = 20
    RTEMP_MAX = 30

    TEMP_END = 0

    def __init__(self, init_param=None, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('init_param=%s', init_param)

        # コマンド追加
        self.add_cmd('on', None, self.cmd_q_on, 'Auto control ON')
        self.add_cmd('off', None, self.cmd_q_off, 'Auto control OFF')
        
        self.add_cmd('kp', None, self.cmd_q_kp, 'get and set kp')
        self.add_cmd('ki', None, self.cmd_q_ki, 'get and set ki')
        self.add_cmd('kd', None, self.cmd_q_kd, 'get and set kd')

        self.add_cmd('temp', None, self.cmd_q_temp, 'get current temp')
        self.add_cmd('rtemp', None, self.cmd_q_rtemp,
                     'get and set target temp')
        self.add_cmd('ttemp', None, self.cmd_q_ttemp,
                     'get and set remocon temp')

        # サーバー独自の設定
        cfg = self.load_conf()
        self._logger.debug('cfg=%s', list(cfg))

        ir_host = cfg.get('ir', 'host')
        aircon_dev = cfg.get('aircon', 'dev_name')
        aircon_bhdr = cfg.get('aircon', 'button_header')
        param_host = cfg.get('param', 'host')
        param_port = cfg.getint('param', 'port')

        self._temp_topic = cfg.get('temp', 'topic')
        self._kp = cfg.getfloat('auto_aircon', 'kp')
        self._ki = cfg.getfloat('auto_aircon', 'ki')
        self._kd = cfg.getfloat('auto_aircon', 'kd')
        self._ki_i_max = cfg.getfloat('auto_aircon', 'ki_i_max')

        self._i = 0

        self._temp = 0
        self._ttemp = self.DEF_TTEMP
        self._rtemp = round(self._ttemp)

        self._on = True

        self._bbt = Beebotte(self._temp_topic, debug=False)
        self._aircon = Aircon(aircon_dev, aircon_bhdr, ir_host,
                              debug=self._debug)
        self._temp_hist = TempHist(debug=self._debug)
        self._param_cl = ParamClient(param_host, param_port, debug=self._debug)

        # 最後に super()__init__()
        super().__init__(debug=self._debug)

    def main(self):
        self._logger.debug('')

        self._bbt.start()
        self._bbt.subscribe()

        while self._active:
            msg_type, msg_data = self._bbt.wait_msg(self._bbt.MSG_DATA)
            self._logger.debug('%s, %s', msg_type, msg_data)

            if not self._active:
                self._logger.info('_active=%s .. shutdown', self._active)
                break

            if msg_type != self._bbt.MSG_DATA:
                continue

            payload = msg_data['payload']
            ts_str = self._bbt.ts2datestr(payload['ts'])
            ts = payload['ts'] / 1000  # msec -> sec
            self._temp = float(payload['data'])

            self._temp_hist.add(self._temp, ts)

            pid = self.pid()
            if type(pid) == float:
                pid = round(pid, 2)
            self._logger.info('ts_str,_temp = %s, %s', ts_str, self._temp)
            self._logger.info('_ttemp,pid   = %s, %s', self._ttemp, pid)

            if pid is None:
                continue

            self._rtemp = round(self._ttemp + pid)
            if self._rtemp > self.RTEMP_MAX:
                self._rtemp = self.RTEMP_MAX
            if self._rtemp < self.RTEMP_MIN:
                self._rtemp = self.RTEMP_MIN
            self._logger.debug('self._rtemp=%d', self._rtemp)

            self._param_cl.send_param({
                'active': self._on,
                'rtemp': self._rtemp,
                'ttemp': self._ttemp,
                'temp': self._temp,
            })

            if not self._on:
                self._logger.debug('_on=%s .. not active', self._on)
                continue

            self._aircon.set_temp(self._rtemp)

        self._active = False
        self._logger.debug('done')

    def end(self):
        self._logger.debug('')
        self._bbt.end()
        if self._active:
            self.stop_main()
        super().end()
        self._logger.debug('done')

    def stop_main(self):
        self._logger.debug('')
        self._active = False
        self._bbt.publish(self._temp_topic, self._temp)
        super().stop_main()
        self._logger.debug('done')

    #
    # config file
    #
    def find_conf(self):
        self._logger.debug('')

        for dir in self.CONF_PATH:
            for fname in self.CONF_FILENAME:
                pathname = dir + '/' + fname
                self._logger.debug('pathname=%s', pathname)
                if self.is_readable(pathname):
                    return pathname
        return None

    def is_readable(self, path):
        self._logger.debug('path=%s', path)

        try:
            f = open(path)
            f.close()
        except Exception as e:
            self._logger.debug('%s:%s', type(e), e)
            return False
        return True

    def load_conf(self):
        self._logger.debug('')

        conf_file = self.find_conf()
        self._logger.debug('conf_file=%s', conf_file)
        if conf_file is None:
            return None

        cfg = configparser.ConfigParser()
        try:
            cfg.read(conf_file)
        except Exception as e:
            self._logger.warning('%s:%s', type(e), e)

        for s in cfg:
            for p in cfg[s]:
                self._logger.debug('%s:%s:%s', s, p, cfg[s][p])

        return cfg

    #
    # PID
    #
    def pid(self):
        self._logger.debug('')

        p_ = self.p()
        i_ = self.i()
        d_ = self.d()
        self._logger.debug('(p_, i_, d_)=(%s, %s, %s)', p_, i_, d_)
        if None in (p_, i_, d_):
            return None

        kp_p = -self._kp * p_
        ki_i = -self._ki * i_
        kd_d = -self._kd * d_
        self._logger.debug('(kp_p,ki_i,kd_d)=(%s,%s,%s)', kp_p, ki_i, kd_d)

        pid = kp_p + ki_i + kd_d

        self._param_cl.send_param({
            'pid': pid,
            'kp_p': kp_p, 'ki_i': ki_i, 'kd_d': kd_d,
            'kp': self._kp, 'ki': self._ki, 'kd': self._kd,
        })
        return pid

    def p(self):
        p_ = self._temp_hist.ave() - self._ttemp
        self._logger.debug('p_=%.2f', p_)
        return p_

    def i(self):
        if self._temp_hist.len() < 2:
            return None

        v_cur = self._temp_hist.get(-1)
        v_prev = self._temp_hist.get(-2)

        d_ts = v_cur['ts'] - v_prev['ts']
        d_i = (v_cur['temp'] + v_prev['temp']) * d_ts / 2 - self._ttemp * d_ts
        self._i += d_i
        self._logger.debug('self._i=%s', self._i)
        return self._i

    def d(self):
        if self._temp_hist.len() < 2:
            return None

        v_cur = self._temp_hist.get(-1)
        v0 = self._temp_hist.get(0)

        d_temp = v_cur['temp'] - v0['temp']
        d_ts = v_cur['ts'] - v0['ts']
        if d_ts == 0.0:
            return None
        d_ = d_temp / d_ts
        self._logger.debug('d_=%.4f', d_)
        return d_

    #
    # cmd funcs
    #
    def cmd_q_on(self, args):
        self._logger.debug('args=%a', args)
        self._on = True
        self._rtemp = round(self._ttemp)
        self._param_cl.send_param({'active': self._on, 'rtemp': self._rtemp})
        self._aircon.set_temp(self._rtemp, force=True)
        return self.RC_OK, None

    def cmd_q_off(self, args):
        self._logger.debug('args=%a', args)
        self._on = False
        self._param_cl.send_param({'active': self._on})
        self._aircon.set_temp(Aircon.TEMP_OFF, force=True)
        return self.RC_OK, None

    def cmd_q_kp(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            return self.RC_OK, self._kp

        try:
            self._kp = float(args[1])
            self._param_cl.send_param({'kp': self._kp})
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        return self.RC_OK, self._kp            

    def cmd_q_ki(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            return self.RC_OK, self._ki

        try:
            self._ki = float(args[1])
            self._param_cl.send_param({'ki': self._ki})
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        return self.RC_OK, self._ki

    def cmd_q_kd(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            return self.RC_OK, self._kd

        try:
            self._kd = float(args[1])
            self._param_cl.send_param({'kd': self._kd})
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        return self.RC_OK, self._kd            

    def cmd_q_temp(self, args):
        self._logger.debug('args=%a', args)

        if self._temp_hist.len() == 0:
            return self.RC_NG, 'no temp data'

        return self.RC_OK, self._temp_hist.get(-1)['temp']

    def cmd_q_ttemp(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            return self.RC_OK, self._ttemp

        try:
            self._ttemp = float(args[1])
            self._i = 0
            self._param_cl.send_param({'ttemp': self._ttemp})
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        return self.RC_OK, self._ttemp

    def cmd_q_rtemp(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            return self.RC_OK, self._rtemp

        try:
            self._rtemp = round(float(args[1]))
            self._param_cl.send_param({'rtemp': self._rtemp})
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        self._aircon.set_temp(self._rtemp)

        return self.RC_OK, self._rtemp


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='Auto Aircon Server')
@click.option('--port', '-p', 'port', type=int,
              default=AutoAirconCmd.DEF_PORT,
              help='port number (%s)' % AutoAirconCmd.DEF_PORT)
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s', port)

    logger.info('start')

    app = CmdServerApp(AutoAirconCmd, port=port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.info('end')


if __name__ == '__main__':
    main()