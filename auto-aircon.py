#!/usr/bin/env python3
#
# (c) Yoichi Tanibayashi
#
"""
auto-aircon.py
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from IrSend import IrSend
from BbtTempSubscriber import BbtTempSubscriber

from MyLogger import get_logger

DEF_BUTTON_HEADER = 'on_hot_auto_'
DEF_TOPIC = 'env1/temp'
DEF_PIN = 22


class AutoAirconHeater:
    D_SEC_MAX = 3600  # 1 hour

    DEF_KP = 0.2
    DEF_KI = 0.0001
    DEF_KD = 50

    REMOCON_TEMP_INIT = 25

    def __init__(self, dev_name, button_header, target_temp, token, topic, pin,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev_name=%s, button_header=%s, target_temp=%f',
                           dev_name, button_header, target_temp)
        self._logger.debug('token=%s, topic=%s', token, topic)
        self._logger.debug('pin=%d', pin)

        self._dev_name = dev_name
        self._button_header = button_header
        self._target_temp = target_temp
        self._token = token
        self._topic = topic
        self._pin = pin

        self._prev_temp = 0
        self._prev_ts_msec = 0
        self._i_temp = 0

        self._kp = self.DEF_KP
        self._ki = self.DEF_KI
        self._kd = self.DEF_KD

        self._remocon_temp = self.REMOCON_TEMP_INIT

        self._temp_subscriber = BbtTempSubscriber(self._token, self._topic,
                                                  debug=False)

        self._aircon = Aircon(self._dev_name, self._pin, debug=self._debug)

    def run(self):
        self._logger.debug('')

        if not self._temp_subscriber.start():
            self._logger.error('_temp_subscriber.start(): failed')
            return

        self._logger.info('start \'%s\' ..', self._dev_name)
        button_name = self._button_header + str(self._remocon_temp)
        if not self._aircon.send(button_name):
            self._logger.error('%s: sending failed', button_name)
            return

        while True:
            ts_msec, cur_temp = self._temp_subscriber.get_temp()
            self._logger.debug('ts_msec=%d, cur_temp=%f', ts_msec, cur_temp)
            if ts_msec == 0:
                self._logger.warning('ignore')
                continue

            date_str = self._temp_subscriber.ts2datestr(ts_msec)
            self._logger.debug('date_str=%s', date_str)

            remocon_temp = self.calc_remocon_temp(ts_msec, cur_temp)
            self._logger.debug('remocon_temp=%d', remocon_temp)
            if remocon_temp < 0:
                self._logger.warning('ignored')
                continue

            if remocon_temp == 0:
                self._logger.debug('ignored')
                continue

            button_name = self._button_header + str(remocon_temp)
            self._logger.debug('button_name=%s', button_name)

            if not self._aircon.send(button_name):
                self._logger.error('%s: sending failed', button_name)

    def end(self):
        self._logger.debug('')
        self._aircon.send('off')
        self._aircon.end()
        self._temp_subscriber.end()

    def calc_remocon_temp(self, ts_msec, cur_temp):
        self._logger.debug('ts_msec=%d, cur_temp=%f', ts_msec, cur_temp)

        if self._prev_ts_msec == 0:
            self._logger.debug('_prev_ts_msec=%d: ignored', self._prev_ts_msec)
            self._prev_temp = cur_temp
            self._prev_ts_msec = ts_msec
            self._i_temp = 0
            return -1

        d_sec = (ts_msec - self._prev_ts_msec) / 1000  # sec
        self._logger.debug('d_sec=%d', d_sec)

        if d_sec > self.D_SEC_MAX:
            self._logger.warning('d_sec > %d', self.D_SEC_MAX)
            self._prev_temp = cur_temp
            self._prev_ts_msec = ts_msec
            self._i_temp = 0
            return -1

        #
        # calc PID
        #
        p_temp = cur_temp - self._target_temp
        self._logger.debug('p_temp=%f', p_temp)

        i_temp = self._i_temp + (p_temp * d_sec)
        self._logger.debug('i_temp=%f (_i_temp=%f)', i_temp, self._i_temp)

        d_temp = (cur_temp - self._prev_temp) / d_sec
        self._logger.debug('d_temp=%f', d_temp)

        self._prev_temp = cur_temp
        self._prev_ts_msec = ts_msec
        self._i_temp = i_temp

        work_p = self._kp * p_temp
        work_i = self._ki * i_temp
        work_d = self._kd * d_temp
        self._logger.debug('work_p=%f, work_i=%f, work_d=%f',
                           work_p, work_i, work_d)

        pid = work_p + work_i + work_d
        self._logger.debug('pid=%f', pid)

        #
        # calc remocon_temp
        #
        remocon_temp = round(self._remocon_temp - pid)
        self._logger.debug('remocon_temp=%d', remocon_temp)

        if remocon_temp == self._remocon_temp:
            return 0

        self._remocon_temp = remocon_temp
        return self._remocon_temp


class Aircon:
    def __init__(self, dev_name, pin, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev_name=%s, pin=%d', dev_name, pin)

        self._pin      = pin
        self._dev_name = dev_name

        # self._irsend = IrSend(self._pin, load_conf=True, debug=self._debug)
        self._irsend = IrSend(self._pin, load_conf=True, debug=False)

    def send(self, button):
        self._logger.debug('button=%s', button)
        return self._irsend.send(self._dev_name, button)

    def end(self):
        self._logger.debug('')
        self._irsend.end()
        self._logger.debug('done')


class App:
    def __init__(self, dev_name, button_header, target_temp, token, topic, pin,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev_name=%s, button_header=%s, target_temp=%f',
                           dev_name, button_header, target_temp)
        self._logger.debug('token=%s, topic=%s', token, topic)
        self._logger.debug('pin=%d', pin)

        self._dev_name = dev_name
        self._button_header = button_header
        self._target_temp = target_temp
        self._token = token
        self._topic = topic
        self._pin = pin

        self._auto_remocon = AutoAirconHeater(self._dev_name,
                                              self._button_header,
                                              self._target_temp,
                                              self._token, self._topic,
                                              self._pin,
                                              debug=self._debug)

    def main(self):
        self._logger.debug('')
        self._auto_remocon.run()

    def end(self):
        self._logger.debug('')
        self._auto_remocon.end()


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='''
aircon heater controler

DEV_NAME(str): device name of aircon

TEMP(float): target temperature in Celsius

TOKEN(str): token strings for beebottle channel (ex. token_...)
''')
@click.argument('dev_name')
@click.argument('temp', type=float)
@click.argument('token')
@click.option('--button_header', '-b', 'button_header',
              default=DEF_BUTTON_HEADER,
              help='button name header (ex. \'on_hot_auto_\')')
@click.option('--topic', '-t', 'topic', type=str, default=DEF_TOPIC,
              help='topic of temperature on beebottle (ex.\'env/temp\')')
@click.option('--pin', '-p', 'pin', type=int, default=DEF_PIN,
              help='GPIO pin')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug option')
def main(dev_name, button_header, temp, token, topic, pin, debug):
    logger = get_logger(__name__, debug)
    logger.debug('dev_name=%s, button_header=%s, temp=%f',
                 dev_name, button_header, temp)
    logger.debug('token=%s, topic=%s', token, topic)
    logger.debug('pin=%d', pin)

    app = App(dev_name, button_header, temp, token, topic, pin, debug=debug)
    try:
        app.main()
    finally:
        logger.info('finally')
        app.end()


if __name__ == '__main__':
    main()
