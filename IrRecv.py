#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrRecv.py

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

import pigpio
import time
import queue
import threading
from MyLogger import get_logger


#####
class IrRecv:
    """
    赤外線信号の受信
    """
    GLITCH_USEC     = 250     # usec
    LEADER_MIN_USEC = 1000

    INTERVAL_MAX    = 999999  # usec

    WATCHDOG_MSEC   = INTERVAL_MAX / 1000 / 2    # msec
    WATCHDOG_CANCEL = 0

    VAL_ON          = 0
    VAL_OFF         = 1
    VAL_STR         = ['pulse', 'space', 'timeout']

    MSG_END         = ''

    def __init__(self, pin, glitch_usec=GLITCH_USEC, verbose=False,
                 debug=False):
        """
        Parameters
        ----------
        pin: int
        glitch_usec: int
        verbose: bool
        debug: bool
        """
        self._dbg = debug
        self._log = get_logger(__class__.__name__, self._dbg)
        self._log.debug('pin=%d, glitch_usec=%d', pin, glitch_usec)

        self.pin = pin
        self.tick = 0

        self.pi = pigpio.pi()
        self.pi.set_mode(self.pin, pigpio.INPUT)
        self.pi.set_glitch_filter(self.pin, self.GLITCH_USEC)

        self.receiving = False
        self.raw_data = []
        self.verbose = verbose

        self.msgq = queue.Queue()

    def set_watchdog(self, ms):
        """
        受信タイムアウトの設定

        Parameters
        ----------
        ms: int
          msec
        """
        self._log.debug('ms=%d', ms)
        self.pi.set_watchdog(self.pin, ms)

    def cb_func_recv(self, pin, val, tick):
        """
        信号受信用コールバック関数

        受信用GPIOピン``pin``が変化するか、タイムアウトすると呼び出される。

        変化を検知すると、メッセージキューに格納し、
        最小限の処理にとどめて、ほとんどの処理はサブスレッドに任せる。

        """
        self._log.debug('pin=%d, val=%d, tick=%d', pin, val, tick)

        if not self.receiving:
            self._log.debug('reciving=%s .. ignore', self.receiving)
            return

        self.msgq.put([pin, val, tick])

        if val == pigpio.TIMEOUT:
            # 受信終了処理
            self.set_watchdog(self.WATCHDOG_CANCEL)
            self.cb_recv.cancel()
            self.receiving = False

            self.msgq.put(self.MSG_END)

            self._log.debug('timeout!')
            return

        self.set_watchdog(self.WATCHDOG_MSEC)

    def worker(self):
        """
        サブスレッド

        メッセージキューから``msg``(GPIOピンの変化情報)を取出し、処理する。
        実際の処理は``proc_msg()``で行う。

        """
        self._log.debug('')

        while True:
            msg = self.msgq.get()
            self._log.debug('msg=%s', msg)
            if msg == self.MSG_END:
                break

            self.proc_msg(msg)

        self._log.debug('done')

    def proc_msg(self, msg):
        """
        GPIOの値の変化に応じて、
        赤外線信号のON/OFF時間を``self.raw_data``に記録する。

        self.raw_data: [[pulse1, space1], [pulse2, space2], ..]

        Parameters
        ----------
        msg: [pin, val, tick]
          GPIOピンの状態変化

        """
        self._log.debug('msg=%s', msg)

        if type(msg) != list:
            self._log.waring('invalid msg:%s .. ignored', msg)
            return
        if len(msg) != 3:
            self._log.waring('invalid msg:%s .. ignored', msg)
            return

        [pin, val, tick] = msg

        interval = tick - self.tick
        self._log.debug('interval=%d', interval)
        self.tick = tick

        if val == pigpio.TIMEOUT:
            self._log.debug('timeout!')
            if len(self.raw_data) > 0:
                if len(self.raw_data[-1]) == 1:
                    self.raw_data[-1].append(interval)
            self._log.debug('end')
            return

        if interval > self.INTERVAL_MAX:
            interval = self.INTERVAL_MAX
            self._log.debug('interval=%d', interval)

        if val == IrRecv.VAL_ON:
            # end of space
            if self.raw_data == []:
                self._log.debug('start raw_data')
                return
            else:
                self.raw_data[-1].append(interval)

        else:  # val == IrRecv.VAL_OFF
            # end of pulse
            if self.raw_data == [] and interval < self.LEADER_MIN_USEC:
                self.set_watchdog(self.WATCHDOG_CANCEL)
                self._log.debug('%d: leader is too short .. ignored',
                                   interval)
                return
            else:
                self.raw_data.append([interval])

        self._log.debug('raw_data=%s', self.raw_data)

    def recv(self):
        """
        赤外線信号の受信

        受信処理に必要なコールバックとサブスレッド``th_worker``を生成し、
        サブスレッドが終了するまで待つ。

        """
        self._log.debug('')

        self.raw_data  = []
        self.receiving = True

        self.th_worker = threading.Thread(target=self.worker, daemon=True)
        self.th_worker.start()

        self.cb_recv = self.pi.callback(self.pin, pigpio.EITHER_EDGE,
                                        self.cb_func_recv)

        if self.verbose:
            print('Ready')

        """
        while self.receiving:
            time.sleep(0.1)
        """
        # スレッドが終了するまで待つ
        self.th_worker.join()
        self.cb_recv.cancel()

        if self.verbose:
            print('Done')

        return self.raw_data

    def end(self):
        """
        終了処理

        コールバックをキャンセルし、
        ``worker``スレッドがaliveの場合は、終了メッセージを送り、終了を待つ。
        """
        self._log.debug('')
        self.cb_recv.cancel()
        self.pi.stop()

        if self.th_worker.is_alive():
            self.msgq.put(self.MSG_END)
            self._log.debug('join()')
            self.th_worker.join()

        self._log.debug('done')

    def raw2pulse_space(self, raw_data=None):
        """
        リスト形式のデータをテキストに変換。

        Parameters
        ----------
        raw_data: [[p1, s1], [p2, s2], ..]
          引数で与えられなかった場合は、最後に受信したデータを使用する。

        Returns
        -------
        pulse_space: str
          pulse p1
          space s1
          pulse p2
          space s2
          :
        """
        self._log.debug('row_data=%s', raw_data)

        if raw_data is None:
            raw_data = self.raw_data
            self._log.debug('raw_data=%s', raw_data)

        pulse_space = ''

        for (p, s) in raw_data:
            pulse_space += '%s %d\n' % (self.VAL_STR[0], p)
            pulse_space += '%s %d\n' % (self.VAL_STR[1], s)

        return pulse_space

    def print_pulse_space(self, raw_data=None):
        """
        ``raw_data``の内容を下記の書式でテキスト出力する。

        pulse p1
        space s1
        pulse p2
        space s2
        :

        Parameters
        ----------
        raw_data: list
          [[p1, s1], [p2, s2], .. ]

        """
        self._log.debug('raw_data=%s', raw_data)

        if raw_data is None:
            raw_data = self.raw_data
            self._log.debug('raw_data=%s', raw_data)

        print(self.raw2pulse_space(raw_data), end='')


#####
class App:
    def __init__(self, pin, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, self._dbg)
        self._log.debug('pin=%d', pin)

        self.r = IrRecv(pin, verbose=True, debug=self._dbg)

    def main(self):
        self._log.debug('')

        while True:
            print('# -')
            raw_data = self.r.recv()
            self.r.print_pulse_space(raw_data)
            print('# /')
            time.sleep(.5)

    def end(self):
        self._log.debug('')
        self.r.end()


#####
DEF_PIN = 27

import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='IR signal receiver')
@click.argument('pin', type=int, default=DEF_PIN)
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(pin, debug):
    logger = get_logger(__name__, debug)
    logger.debug('pin: %d', pin)

    app = App(pin, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
