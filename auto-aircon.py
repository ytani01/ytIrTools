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
import time

from MyLogger import get_logger

DEF_BUTTON_HEADER = 'on_hot_auto_'
DEF_TOPIC = 'env1/temp'
DEF_PIN = 22


class AutoAircon:
    D_SEC_MAX = 3600  # 1 hour

    DEF_KP = 1.5
    DEF_KI = 0.003
    DEF_KD = 50

    REMOCON_TEMP_INIT = 25

    HIST_MAX_SEC = 60

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

        self._temp_hist = []  # history [[ts1, temp1], [ts2, temp2], ..]

        self._kp = self.DEF_KP
        self._ki = self.DEF_KI
        self._kd = self.DEF_KD

        self._remocon_temp = round(self._target_temp)

        self._temp_subscriber = BbtTempSubscriber(self._token, self._topic,
                                                  debug=False)

        self._aircon = Aircon(self._dev_name, self._pin, debug=self._debug)

    def add_hist(self, ts, temp):
        self._logger.debug('ts=%d sec, temp=%f', ts, temp)

        self._temp_hist.append({'ts': ts, 'temp': temp})
        d_sec = ts - self._temp_hist[0]['ts']
        self._logger.debug('d_sec=%.2f, temp_hist=%s', d_sec, self._temp_hist)
        if d_sec < 0:
            self._logger.warning('invalid d_sec=%.2f: ignored', d_sec)
            self._temp_hist.pop()
            return self._temp_hist
        while d_sec > self.HIST_MAX_SEC:
            self._temp_hist.pop(0)
            d_sec = ts - self._temp_hist[0]['ts']
            self._logger.debug('d_sec=%.2f, temp_hist=%s',
                               d_sec, self._temp_hist)

        return self._temp_hist

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
            ts = ts_msec / 1000
            self._logger.debug('ts=%f, cur_temp=%f', ts_msec, cur_temp)

            if ts_msec == 0:
                self._logger.warning('ts_msec=%d .. ignored', ts_msec)
                continue

            year = time.localtime(ts_msec/1000).tm_year
            if year > 2100 or year < 2000:
                self._logger.warning('year=%d: invalid year .. ignored', year)
                continue

            if len(self._temp_hist) > 0:
                if ts_msec < self._temp_hist[-1]['ts']:
                    self._logger.warning('ts_msec=%d < %d .. ignored',
                                         ts_msec, self._temp_hist[-1]['ts'])
                    continue

            self.add_hist(ts, cur_temp)

            date_str = self._temp_subscriber.ts2datestr(ts_msec)
            self._logger.debug('date_str=%s', date_str)

            self._logger.info('%s: %.2f', date_str, cur_temp)

            remocon_temp = self.calc_remocon_temp(self._temp_hist)
            self._logger.debug('remocon_temp=%d', remocon_temp)
            if remocon_temp < 0:
                self._logger.warning('remocon_temp=%d: ignored',
                                     remocon_temp)
                continue

            if remocon_temp == 0:
                self._logger.warning('remocon_temp=%d: ignored',
                                     remocon_temp)
                continue

            button_name = self._button_header + str(remocon_temp)
            self._logger.debug('button_name=%s', button_name)

            if not self._aircon.send(button_name):
                self._logger.error('%s: sending failed', button_name)

    def end(self):
        self._logger.debug('')
        # self._aircon.send('off')
        self._aircon.end()
        self._temp_subscriber.end()

    def calc_remocon_temp(self, temp_hist):
        self._logger.debug('temp_hist=%s', temp_hist)

        if len(temp_hist) < 2:
            return -1

        cur_ts     = temp_hist[-1]['ts']
        cur_temp   = temp_hist[-1]['temp']
        prev_ts    = temp_hist[-2]['ts']
        prev_temp  = temp_hist[-2]['temp']
        first_ts   = temp_hist[0]['ts']
        first_temp = temp_hist[0]['temp']

        #
        # calc PID
        #
        sum_temp = 0
        for h in temp_hist:
            sum_temp += h['temp']
        ave_temp = sum_temp / len(temp_hist)
        self._logger.debug('ave_temp=%f', ave_temp)

        p_temp = ave_temp - self._target_temp
        i_temp = self._i_temp \
            + ((cur_temp + prev_temp) * (cur_ts - prev_ts) / 2) \
            - self._target_temp * (cur_ts - prev_ts)
        d_temp = (cur_temp - first_temp) / (cur_ts - first_ts)
        self._logger.debug('(p,i,d)_temp=(%f, %f, %f)', p_temp, i_temp, d_temp)

        self._i_temp = i_temp

        p_work = self._kp * p_temp
        i_work = self._ki * i_temp
        d_work = self._kd * d_temp
        self._logger.debug('(p,i,d)_work=(%f, %f, %f)', p_work, i_work, d_work)

        pid = p_work + i_work + d_work
        self._logger.debug('pid=%f', pid)

        #
        # calc remocon_temp
        #
        # remocon_temp = round(self._remocon_temp - pid)
        remocon_temp = round(self._target_temp - pid)
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

        self._logger.info('%s: %s', self._dev_name, button)
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

        self._auto_remocon = AutoAircon(self._dev_name,
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
