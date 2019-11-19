#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
AutoAircon.py
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'


from IrSend import IrSend
from ytBeebotte import Beebotte
import threading

from MyLogger import get_logger

DEF_DEV_NAME = 'aircon'
DEF_BUTTON_HEADER = 'on_hot_auto_'
DEF_TOPIC = 'env1/temp'
DEF_PIN = 22


class Temp:
    def __init__(self, topic, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('topic=%s', topic)

        self._bbt = Beebotte(topic, debug=self._debug)

    def start(self):
        self._logger.debug('')

        self._bbt.start()
        while True:
            msg_type, msg_data = self._bbt.get_msg(block=True)
            self._logger.debug('msg_type=%s, msg_data=%s', msg_type, msg_data)
            if msg_type == self._bbt.MSG_OK:
                break

        self._bbt.subscribe()

    def get_temp(self, block=True):
        self._logger.debug('block=%s', block)

        while True:
            msg_type, msg_data = self._bbt.get_msg(block=block)
            if msg_type == self._bbt.MSG_DATA:
                break

        payload = msg_data['payload']
        ts = payload['ts'] / 1000  # msec -> sec
        temp = float(payload['data'])

        return ts, temp

    def end(self):
        self._logger.debug('')
        self._bbt.end()


class Aircon:
    def __init__(self, dev, button_header, pin, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev=%s, button_header=%s, pin=%d',
                           dev, button_header, pin)

        self._dev = dev
        self._button_header = button_header

        # self._irsend = IrSend(pin, load_conf=True, debug=self._debug)
        self._irsend = IrSend(pin, load_conf=True, debug=False)

    def send(self, button):
        self._logger.debug('button=%s', button)

        self._irsend.send(self._dev, button)

    def send_temp(self, temp):
        self._logger.debug('temp=%d', temp)

        button = self._button_header + str(temp)
        self._logger.debug('button=%s', button)

        self.send(button)

    def end(self):
        self._logger.debug('')
        self._irsend.end()


class AutoAircon(threading.Thread):
    DSEC_MAX = 60  # sec

    DEF_KP = 1.6
    DEF_KI = 0.002
    DEF_KD = 60

    K_I_MAX = 3.0

    REMOCON_TEMP_MIN = 20
    REMOCON_TEMP_MAX = 30

    def __init__(self, target_temp, dev, button_header, topic, pin,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('target_temp=%.1f', target_temp)
        self._logger.debug('dev=%s, button_header=%s', dev, button_header)
        self._logger.debug('topic=%s', topic)
        self._logger.debug('pin=%d', pin)

        self._aircon = Aircon(dev, button_header, pin, debug=self._debug)
        self._temp = Temp(topic)

        self._target_temp = target_temp
        self._remocon_temp = round(self._target_temp) - 1

        self._temp_hist = []  # [{'ts':ts1, 'temp':temp1}, ..]

        self._kp = self.DEF_KP
        self._ki = self.DEF_KI
        self._kd = self.DEF_KD
        self._i = 0

        self._pause = False

        self._loop = True
        super().__init__(daemon=True)

    def add_temp_hist(self, ts, temp):
        self._logger.debug('ts=%.3f sec, temp=%.2f', ts, temp)

        self._temp_hist.append({'ts': ts, 'temp': temp})

        if len(self._temp_hist) < 2:
            return self._temp_hist

        while True:
            d_sec = ts - self._temp_hist[0]['ts']
            self._logger.debug('d_sec=%.2f', d_sec)

            if d_sec < 0:
                self._logger.warning('invalid d_sec=%.2f: ignored', d_sec)
                self._temp_hist.pop()
                break

            if d_sec <= self.DSEC_MAX:
                break

            self._temp_hist.pop(0)
            if len(self._temp_hist) < 2:
                break

        return self._temp_hist

    def ave_temp_hist(self):
        self._logger.debug('')

        sum = 0.0
        for h in self._temp_hist:
            sum += h['temp']
        ave = sum / len(self._temp_hist)
        return ave

    def calc_pid(self):
        self._logger.debug('')

        if len(self._temp_hist) < 2:
            self._logger.debug('return None')
            return None

        ave_temp  = self.ave_temp_hist()
        self._logger.debug('ave_temp=%.2f, _target_temp=%.1f',
                           ave_temp, self._target_temp)

        cur_ts     = self._temp_hist[-1]['ts']
        cur_temp   = self._temp_hist[-1]['temp']
        prev_ts    = self._temp_hist[-2]['ts']
        prev_temp  = self._temp_hist[-2]['temp']
        first_ts   = self._temp_hist[0]['ts']
        first_temp = self._temp_hist[0]['temp']

        # P
        p_ = ave_temp - self._target_temp

        # I
        d_ts = cur_ts - prev_ts
        i_temp = (cur_temp + prev_temp) * d_ts / 2
        i_temp -= self._target_temp * d_ts
        self._logger.debug('_i=%f, i_temp=%f', self._i, i_temp)
        i_ = self._i + i_temp

        # D
        d_ = (cur_temp - first_temp) / (cur_ts - first_ts)

        self._logger.debug('(p_, i_, d_ )=(%f, %f, %f)', p_, i_, d_)

        k_p = self._kp * p_
        k_i = self._ki * i_
        k_d = self._kd * d_
        self._logger.debug('(k_p,k_i,k_d)=(%f, %f, %f)', k_p, k_i, k_d)

        if abs(k_i) <= self.K_I_MAX:
            self._i = i_

        # PID
        pid = k_p + k_i + k_d
        self._logger.debug('pid=%f', pid)
        return pid

    def ts2datestr(self, ts):
        return self._temp._bbt.ts2datestr(ts * 1000)

    def run(self):
        self._logger.debug('')

        self._aircon.send_temp(self._remocon_temp)

        self._temp.start()

        while self._loop:
            ts, temp = self._temp.get_temp()
            datestr = self.ts2datestr(ts)
            self._logger.debug('%s: %.2f', datestr, temp)

            self.add_temp_hist(ts, temp)
            self._logger.debug('_temp_hist=')
            for h in self._temp_hist:
                self._logger.debug('  {%s, %.2f}',
                                   self.ts2datestr(h['ts']), h['temp'])

            pid = self.calc_pid()
            if pid is None:
                continue

            if self._pause:
                continue

            remocon_temp = self._target_temp - pid
            self._logger.debug('remocon_temp=%.2f', remocon_temp)
            remocon_temp = round(remocon_temp)
            if remocon_temp < self.REMOCON_TEMP_MIN:
                remocon_temp = self.REMOCON_TEMP_MIN
            if remocon_temp > self.REMOCON_TEMP_MAX:
                remocon_temp = self.REMOCON_TEMP_MAX

            if remocon_temp != self._remocon_temp:
                self._remocon_temp = remocon_temp
                self._logger.debug('_remocon_temp=%d', remocon_temp)

                self._aircon.send_temp(self._remocon_temp)

    def set_target_temp(self, temp):
        self._logger.debug('temp=%.1f', temp)

        self._target_temp = temp
        self._remocon_temp = round(self._target_temp) - 1
        self._aircon.send_temp(self._remocon_temp)
        self._i = 0

    def on(self):
        self._logger.debug('')
        self._aircon.send_temp(self._remocon_temp)
        self._pause = False
        self._logger.debug('_pause=%s', self._pause)
        
    def off(self):
        self._logger.debug('')
        self._aircon.send('off')
        self._pause = True
        self._logger.debug('_pause=%s', self._pause)

    def end(self):
        self._logger.debug('')
        self._temp.end()
        self._aircon.end()


class App:
    def __init__(self, target_temp, dev, button_header, topic, pin,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('target_temp=%.1f', target_temp)
        self._logger.debug('dev=%s, button_header=%s', dev, button_header)
        self._logger.debug('topic=%s', topic)
        self._logger.debug('pin=%d', pin)

        self._loop = True

        self._cmd = {
            'temp': self.cmd_target_temp,
            'on':   self.cmd_on,
            'off':  self.cmd_off,
            'stop': self.cmd_stop
        }

        self._aircon = AutoAircon(target_temp, dev, button_header, topic, pin,
                                  debug=self._debug)

    def cmd_target_temp(self, param):
        self._logger.debug('param=%s', param)

        target_temp = float(param)
        self._aircon.set_target_temp(target_temp)

    def cmd_on(self, param):
        self._logger.debug('param=%s', param)
        self._aircon.on()

    def cmd_off(self, param):
        self._logger.debug('param=%s', param)
        self._aircon.off()

    def cmd_stop(self, param):
        self._logger.debug('param=%s', param)
        self._loop = False

    def main(self):
        self._logger.debug('')
        self._aircon.start()

        while self._loop:
            cmdline = input().split()
            self._logger.debug('cmdline=%s', cmdline)
            if len(cmdline) == 0:
                continue
            if len(cmdline) == 1:
                cmdline.append('')
                self._logger.debug('cmdline=%s', cmdline)

            try:
                self._cmd[cmdline[0]](cmdline[1])
            except KeyError:
                self._logger.debug('%s: no such command', cmdline[0])

    def end(self):
        self._logger.debug('')
        self._aircon.end()


import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='AutoAircon')
@click.argument('target_temp', type=float)
@click.option('--dev', 'dev', type=str, default=DEF_DEV_NAME,
              help='device name')
@click.option('--button_header', '-b', 'button_header', type=str,
              default=DEF_BUTTON_HEADER,
              help='button_header')
@click.option('--topic', '-t', 'topic', type=str, default=DEF_TOPIC,
              help='topic')
@click.option('--pin', '-p', 'pin', type=int, default=DEF_PIN,
              help='pin number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(target_temp, dev, button_header, topic, pin, debug):
    logger = get_logger(__name__, debug)
    logger.debug('target_temp=%.1f', target_temp)
    logger.debug('dev=%s, button_header=%s', dev, button_header)
    logger.debug('topic=%s', topic)
    logger.debug('pin=%d', pin)

    app = App(target_temp, dev, button_header, topic, pin, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
