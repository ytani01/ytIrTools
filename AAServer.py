#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from TcpCmdServer import Cmd, CmdServerApp

from ytBeebotte import Beebotte
from IrSendCmdClient import IrSendCmdClient

import os
import configparser

from MyLogger import get_logger


class Aircon:
    DEF_DEV_NAME = 'aircon'
    DEF_BUTTON_HEADER = 'on_hot_auto_'
    DEF_IR_HOST = 'localhost'

    def __init__(self, dev=DEF_DEV_NAME, button_header=DEF_BUTTON_HEADER,
                 ir_host=DEF_IR_HOST,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev=%s, button_header=%s, ir_host=%s',
                           dev, button_header, ir_host)

        self._dev = dev
        self._button_header = button_header
        self._rtemp = 0

        self._irsend = IrSendCmdClient(ir_host, debug=self._debug)

    def set_temp(self, rtemp, force=False):
        self._logger.debug('rtemp=%s', rtemp)

        if not force:
            if rtemp == self._rtemp:
                self._logger.debug('rtemp==_rtemp=%s', self._rtemp)
                return

        button = self._button_header + '%02d' % rtemp
        if rtemp == 0:
            button = 'off'
        self._logger.debug('button=%s', button)

        args = [self._dev, button]

        try:
            ret = self._irsend.send_recv(args)
        except Exception as e:
            self._logger.error('%s:%s', type(e), e)
        else:
            self._logger.info('%s:%s', args, self._irsend.reply2str(ret))


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
        self.i_ = 0

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
    CONF_FILENAME = ['autoaircon', '.autoaircon']
    CONF_PATH = ['.', os.environ['HOME'], '/etc']

    DEF_PORT = 12359

    DEF_TTEMP = 26

    TEMP_END = 0

    def __init__(self, init_param=None, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('init_param=%s', init_param)

        # コマンド追加
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
        aircon_button_header = cfg.get('aircon', 'button_header')
        self._temp_topic = cfg.get('temp', 'topic')
        self._kp = cfg.getfloat('auto_aircon', 'kp')
        self._ki = cfg.getfloat('auto_aircon', 'ki')
        self._kd = cfg.getfloat('auto_aircon', 'kd')
        self._ki_i_max = cfg.getfloat('auto_aircon', 'ki_i_max')

        self.i_ = 0

        self._ttemp = self.DEF_TTEMP
        self._rtemp = round(self._ttemp)

        self._bbt = Beebotte(self._temp_topic, debug=False)
        self._aircon = Aircon(aircon_dev, aircon_button_header, ir_host,
                              debug=self._debug)
        self._temp_hist = TempHist(debug=self._debug)

        # 最後に super()__init__()
        super().__init__(debug=self._debug)

    def main(self):
        self._logger.debug('')

        self._bbt.start()
        self._bbt.subscribe()

        while self._active:
            msg_type, msg_data = self._bbt.wait_msg(self._bbt.MSG_DATA)
            self._logger.debug('%s, %s', msg_type, msg_data)

            if msg_type != self._bbt.MSG_DATA:
                continue

            payload = msg_data['payload']
            ts = payload['ts'] / 1000  # msec -> sec
            temp = float(payload['data'])
            self._logger.debug('ts=%s, temp=%s', ts, temp)
            if temp == self.TEMP_END:
                self._logger.info('temp=%s .. shutdown', temp)
                break

            self._temp_hist.add(temp, ts)
            pid = self.pid()
            self._logger.debug('pid=%s', pid)

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
        self._bbt.publish(self._temp_topic, self.TEMP_END)
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
        self.i_ += d_i
        self._logger.debug('self.i_=%s', self.i_)
        return self.i_

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
               help='TCP Server Template')
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
