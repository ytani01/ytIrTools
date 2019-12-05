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
import time

from MyLogger import get_logger


class ParamClient(TcpCmdClient):
    DEF_SVR_HOST = 'localhost'
    DEF_SVR_PORT = 51888

    DEF_TIMEOUT = 2  # sec

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

    RTEMP_MIN = 20
    RTEMP_MAX = 30

    INTERVAL_MIN = 30  # set_temp interval sec

    BUTTON_OFF = 'off'

    def __init__(self, dev=DEF_DEV, bhdr=DEF_BHDR, ir_host=DEF_IR_HOST,
                 interval_min=INTERVAL_MIN, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev=%s, bhdr=%s, ir_host=%s, interval_min=%s',
                           dev, bhdr, ir_host, interval_min)

        self._dev = dev
        self._bhdr = bhdr
        self._rtemp = self.RTEMP_MIN
        self._ts_set_temp = 0
        self._interval_min = interval_min
        self._on = False

        super().__init__(ir_host, debug=self._debug)

    def on(self):
        self._logger.debug('')
        self.set_temp(self._rtemp, force=True)

    def off(self):
        self._logger.debug('')
        args = [self._dev, self.BUTTON_OFF]
        try:
            ret = self.send_recv(args)
        except Exception as e:
            self._logger.error('%s:%s', type(e), e)
            return False
        else:
            self._logger.info('%s: %s', args, self.reply2str(ret))

        self._on = False
        return True

    def is_on(self):
        return self._on

    def set_temp(self, rtemp, force=False):
        self._logger.info('rtemp=%s', rtemp)

        if rtemp > self.RTEMP_MAX:
            rtemp = self.RTEMP_MAX
            self._logger.info('fix: rtemp=%d', rtemp)
        if rtemp < self.RTEMP_MIN:
            rtemp = self.RTEMP_MIN
            self._logger.info('fix: rtemp=%d', rtemp)

        if not force and rtemp == self._rtemp:
            self._logger.info('rtemp==_rtemp=%s .. ignored', self._rtemp)
            return None

        ts_now = time.time()
        interval = ts_now - self._ts_set_temp
        if not force and interval < self._interval_min:
            self._logger.info('rtemp=%s, interval=%.1f < %s .. ignored',
                              rtemp, interval, self._interval_min)
            return None

        button = self._bhdr + '%02d' % rtemp
        args = [self._dev, button]
        self._logger.debug('args=%s', args)

        try:
            ret = self.send_recv(args)
        except Exception as e:
            self._logger.error('%s:%s', type(e), e)
            return None
        else:
            self._logger.info('%s: %s', args, self.reply2str(ret))

        self._on = True
        self._ts_set_temp = ts_now
        self._rtemp = rtemp

        return self._rtemp


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

    DEF_PORT = 51002

    DEF_TTEMP = 26

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
        if cfg is None:
            raise RuntimeError('load_conf(): failed')

        ir_host = cfg.get('ir', 'host')
        aircon_dev = cfg.get('aircon', 'dev_name')
        aircon_bhdr = cfg.get('aircon', 'button_header')
        aircon_interval_min = cfg.getfloat('aircon', 'interval_min')
        param_host = cfg.get('param', 'host')
        param_port = cfg.getint('param', 'port')

        self._temp_topic = cfg.get('temp', 'topic')
        self._kp = cfg.getfloat('auto_aircon', 'kp')
        self._ki = cfg.getfloat('auto_aircon', 'ki')
        self._kd = cfg.getfloat('auto_aircon', 'kd')
        self._ki_i_max = cfg.getfloat('auto_aircon', 'ki_i_max')

        self._i = 0
        self._prev_i = 0

        self._ttemp = self.DEF_TTEMP
        self._rtemp = round(self._ttemp)
        self._temp = self._ttemp

        self._bbt = Beebotte(self._temp_topic, debug=False)
        self._aircon = Aircon(aircon_dev, aircon_bhdr,
                              ir_host, aircon_interval_min,
                              debug=self._debug)
        self._temp_hist = TempHist(debug=self._debug)
        self._param_cl = ParamClient(param_host, param_port, debug=self._debug)

        # 最後に super()__init__()
        super().__init__(debug=self._debug)

    def main(self):
        self._logger.debug('')

        self._bbt.start()
        self._bbt.subscribe()

        self._aircon.on()

        while self._active:
            # BeebotteからMQTTで温度を取得
            msg_type, msg_data = self._bbt.wait_msg(self._bbt.MSG_DATA)
            self._logger.debug('%s, %s', msg_type, msg_data)

            # シャットダウン チェック
            if not self._active:
                self._logger.info('_active=%s .. shutdown', self._active)
                break

            if msg_type != self._bbt.MSG_DATA:
                continue

            # メッセージのpayloadから、タイムスタンプと温度を抽出
            payload = msg_data['payload']
            ts_str = self._bbt.ts2datestr(payload['ts'])
            self._logger.debug('ts_str=%s', ts_str)

            ts = payload['ts'] / 1000  # msec -> sec

            self._temp = float(payload['data'])
            self._logger.info('_temp,_ttemp=%.2f, %.1f',
                              self._temp, self._ttemp)

            # 温度履歴に追加
            self._temp_hist.add(self._temp, ts)

            # パラメータの値を Node-RED に通知
            self._param_cl.send_param({
                'active': self._aircon.is_on(),
                'ttemp': self._ttemp,
                'rtemp': self._rtemp,
                'temp': self._temp,
            })

            # エアコンのON/OFFチェック
            if not self._aircon.is_on():
                self._logger.info('_aircon is off .. do nothing')
                continue

            # PID制御の計算
            pid = self.pid()
            if type(pid) == float:
                pid = round(pid, 2)
            self._logger.info('pid=%s', pid)
            if pid is None:
                continue

            # エアコンの温度設定
            #   温度設定に関する制限事項(最大値、最低値、頻度など)に
            #   関する処理は、_airconオブジェクト内で判断・処理され、
            #   実際に設定された温度が返される。
            rtemp = round(self._ttemp + pid)
            self._logger.debug('rtemp=%d', rtemp)

            rtemp = self._aircon.set_temp(rtemp)
            self._logger.debug('rtemp=%s', rtemp)
            if rtemp is not None:
                self._rtemp = rtemp
                self._param_cl.send_param({'rtemp': self._rtemp})

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
    def find_conf(self, fname=CONF_FILENAME, path=CONF_PATH):
        self._logger.debug('fname=%s, path=%s', fname, path)

        for d in path:
            for f in fname:
                pathname = d + '/' + f
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

    def load_conf(self, fname=CONF_FILENAME, path=CONF_PATH):
        self._logger.debug('fname=%s, path=%s', fname, path)

        conf_file = self.find_conf(fname, path)
        self._logger.debug('conf_file=%s', conf_file)
        if conf_file is None:
            return None

        cfg = configparser.ConfigParser()
        try:
            cfg.read(conf_file)
        except Exception as e:
            self._logger.error('%s:%s', type(e), e)
            return None

        for s in cfg:
            for p in cfg[s]:
                self._logger.debug('  %s: %s: %s', s, p, cfg[s][p])

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
        if abs(ki_i) > self._ki_i_max:
            self._logger.warning('abs(ki_i)=%.1f > %.1f',
                                 abs(ki_i), self._ki_i_max)
            ki_i = ki_i / abs(ki_i) * self._ki_i_max
            self._i = self._prev_i
            self._logger.warning('ki_i=%.1f, self._i=%.1f ', ki_i, self._i)
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
            self._logger.debug('None')
            return None

        v_cur = self._temp_hist.get(-1)
        v_prev = self._temp_hist.get(-2)

        d_ts = v_cur['ts'] - v_prev['ts']
        d_i = (v_cur['temp'] + v_prev['temp']) * d_ts / 2 - self._ttemp * d_ts
        self._prev_i = self._i
        self._i += d_i
        self._logger.debug('_i=%s, _prev_i=%s', self._i, self._prev_i)
        return self._i

    def d(self):
        if self._temp_hist.len() < 2:
            self._logger.debug('None')
            return None

        v_cur = self._temp_hist.get(-1)
        v0 = self._temp_hist.get(0)

        d_temp = v_cur['temp'] - v0['temp']
        d_ts = v_cur['ts'] - v0['ts']
        if d_ts == 0.0:
            self._logger.debug('None')
            return None
        d_ = d_temp / d_ts
        self._logger.debug('d_=%.4f', d_)
        return d_

    #
    # cmd funcs
    #
    def cmd_q_on(self, args):
        self._logger.debug('args=%a', args)

        self._rtemp = round(self._ttemp)
        self._i = 0

        self._param_cl.send_param({
            'active': self._aircon.is_on(),
            'rtemp': self._rtemp
        })

        rtemp = self._aircon.set_temp(self._rtemp, force=True)
        if rtemp is not None:
            self._rtemp = rtemp

        self._param_cl.send_param({
            'active': self._aircon.is_on(),
            'rtemp': self._rtemp
        })
        return self.RC_OK, None

    def cmd_q_off(self, args):
        self._logger.debug('args=%a', args)
        self._aircon.off()
        self._param_cl.send_param({'active': self._aircon.is_on()})
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

        self._i = 0
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

        msg = 'temp=%s' % self._temp_hist.get(-1)['temp']
        return self.RC_OK, msg

    def cmd_q_ttemp(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            msg = 'ttemp=%s' % self._ttemp
            return self.RC_OK, msg

        self._i = 0
        try:
            self._ttemp = float(args[1])
            self._param_cl.send_param({'ttemp': self._ttemp})
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        msg = 'ttemp=%s' % self._ttemp
        return self.RC_OK, msg

    def cmd_q_rtemp(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            msg = 'rtemp=%s' % self._rtemp
            return self.RC_OK, msg

        try:
            rtemp = round(float(args[1]))
            rtemp = self._aircon.set_temp(rtemp, force=True)
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        if rtemp is None:
            msg = '_aircon.set_temp(): failed'
            return self.RC_NG, msg

        self._rtemp = rtemp
        self._param_cl.send_param({'rtemp': self._rtemp})
        msg = 'rtemp=%s' % self._rtemp
        return self.RC_OK, msg


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
