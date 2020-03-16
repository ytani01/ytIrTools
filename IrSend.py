#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrSend.py

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'


from IrConfig import IrConfig
import pigpio
import time
from MyLogger import get_logger


class WaveForm:
    OFF       = 0
    ON        = 1
    ONOFF     = [OFF, ON]
    ONOFF_STR = ['OFF', 'ON']

    def __init__(self, pin, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, debug)
        self._log.debug('pin=%d', pin)

        self.pin = pin
        self.waveform = []

    def clear(self):
        self._log.debug('')
        self.waveform = []

    def append_null(self, usec):
        self.waveform.append(pigpio.pulse(0, 0, usec))

    def append_pulse(self, onoff, usec):
        if onoff not in self.ONOFF:
            msg = 'onoff[%s] must be WaveForm.ON or WaveForm.OFF' % str(onoff)
            raise ValueError(msg)
        if usec <= 0:
            raise ValueError('usec[' + str(usec) + '] must be > 0')
        self._log.debug('onoff:%-3s, usec=%s', self.ONOFF_STR[onoff], usec)

        if onoff == self.ON:
            self.waveform.append(pigpio.pulse(1 << self.pin, 0, usec))
        else:
            self.waveform.append(pigpio.pulse(0, 1 << self.pin, usec))

    def append_pulse_list1(self, onoff_list):
        """
        onoff_list:
          [on_usec1, off_usec1, on_usec2, off_usec2, ...]
        """
        verr_msg = 'onoff_list:' + str(onoff_list) + ' must be int list'
        if type(onoff_list) != list:
            raise ValueError(verr_msg)
        if type(onoff_list[0]) != int:
            raise ValueError(verr_msg)
        self._log.debug('onoff_list=%s', onoff_list)

        for i, usec in enumerate(onoff_list):
            if i % 2 == 0:
                self.append_pulse(self.ON, usec)
            else:
                self.append_pulse(self.OFF, usec)

    def append_pulse_list(self, onoff_list, n=1):
        verr_msg = 'n:' + str(n) + ' must be > 1'
        if n < 1:
            raise ValueError(verr_msg)
        self._log.debug('onoff_list=%s, n=%d', onoff_list, n)

        for i in range(n):
            self.append_pulse_list1(onoff_list)

    def append_carrier(self, freq_KHz, duty, len_us):
        """
        append carrier wave.

        <len_us> を0.071*1000*1000より大きくすると crate_wave() できない？
        """
        self._log.debug('freq_KHz:%d, len_us:%d', freq_KHz, len_us)

        wave_len_us = 1000000.0 / freq_KHz      # = 1/(Hz) * 1000 * 1000
        wave_n      = int(round(len_us / wave_len_us))
        on_usec     = int(round(wave_len_us * duty))
        self._log.debug('wave_len_usec: %d, wave_n: %d, on_usec: %d',
                          wave_len_us, wave_n, on_usec)

        cur_usec = 0
        for i in range(wave_n):
            target_usec = int(round((i + 1) * wave_len_us))
            cur_usec += on_usec
            off_usec = target_usec - cur_usec
            cur_usec += off_usec
            self.append_pulse_list1([on_usec, off_usec])


class Wave(WaveForm):
    PIN_PWM = [12, 13, 18]

    def __init__(self, pi, pin, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, debug)
        self._log.debug('pin: %d', pin)

        self.pi  = pi
        self.pin = pin

        if pin in self.PIN_PWM:
            msg = 'pin:%d is one of PWM pins:%s' % (pin, self.PIN_PWM)
            raise ValueError(msg)

        super().__init__(self.pin, debug=self._dbg)
        self.wave = None

        # self.pi.wave_add_new()

    def create_wave(self):
        self._log.debug('len(waveform): %d', len(self.waveform))

        self.pi.wave_add_generic(self.waveform)
        self.wave = self.pi.wave_create()
        return self.wave

    def delete(self):
        self._logger.debug('')

        if self.wave is not None:
            self.pi.wave_delete(self.wave)


class IrSend:
    DEF_PIN = 22

    DEF_FREQ = 38000      # 38KHz
    DEF_DUTY = (1 / 3.0)  # 1/3

    SIG_BITS_MIN = 5

    MSG_OK = IrConfig.MSG_OK

    def __init__(self, pin=DEF_PIN, load_conf=False, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, debug)
        self._log.debug('pin: %d', pin)

        self.pin = pin
        self.tick = 0

        self.pi = pigpio.pi()
        self.pi.set_mode(self.pin, pigpio.OUTPUT)

        self.pulse_wave_hash = {}
        self.space_wave_hash = {}

        self.irconf = None
        if load_conf:
            self.irconf = IrConfig(load_all=True, debug=self._dbg)
            self._log.debug('data=%s', self.irconf.data)
            if self.irconf.data is None:
                self._log.error('no config data')

    def reload_conf(self):
        self._log.debug('')
        msg = self.irconf.reload_all()
        return msg

    def clean_wave(self):
        self._log.debug('')
        self.clear_wave_hash()
        self.pi.wave_clear()

    def end(self):
        self._log.debug('')
        self.clean_wave()
        self.pi.stop()
        self._log.debug('done')

    def print_signal(self, signal):
        self._log.debug('signal:%s', signal)

        for i, interval in enumerate(self.signal):
            print('%s %d' % (self.VAL_STR[i % 2], interval))

    def clear_wave_hash(self):
        self._log.debug('')
        self.clear_pulse_wave_hash()
        self.clear_space_wave_hash()

    def create_pulse_wave1(self, usec, freq=DEF_FREQ, duty=DEF_DUTY):
        self._log.debug('usec: %d, freq=%d', usec, freq)
        wave = Wave(self.pi, self.pin, debug=self._dbg)
        wave.append_carrier(freq, duty, usec)
        return wave.create_wave()

    def clear_pulse_wave_hash(self):
        self._log.debug('')

        for usec in self.pulse_wave_hash:
            self.pi.wave_delete(self.pulse_wave_hash[usec])

        self.pulse_wave_hash = {}

    def create_pulse_wave(self, usec):
        self._log.debug('usec: %d', usec)

        if usec not in self.pulse_wave_hash:
            self.pulse_wave_hash[usec] = self.create_pulse_wave1(usec)
            self._log.debug('pulse_wave_hash: %s', self.pulse_wave_hash)

        return self.pulse_wave_hash[usec]

    def clear_space_wave_hash(self):
        self._log.debug('')

        for usec in self.space_wave_hash:
            self.pi.wave_delete(self.space_wave_hash[usec])

        self.space_wave_hash = {}

    def create_space_wave1(self, usec):
        self._log.debug('usec: %d', usec)
        wave = Wave(self.pi, self.pin, debug=self._dbg)
        wave.append_null(int(round(usec)))
        return wave.create_wave()

    def create_space_wave(self, usec):
        self._log.debug('usec: %d', usec)

        if usec not in self.space_wave_hash:
            self.space_wave_hash[usec] = self.create_space_wave1(usec)
            self._log.debug('space_wave_hash: %s', self.space_wave_hash)

        return self.space_wave_hash[usec]

    def send_raw_data(self, raw_data, repeat=1):
        """
        Parameters
        ----------
        raw_data: list
          [[pulse1, space1], [pulse2, space2], .. ]

        repeat: int
        """
        self._log.debug('raw_data=%s, repeat=%s', raw_data, repeat)

        if len(raw_data) <= self.SIG_BITS_MIN:
            if len(raw_data) == 0:
                self._log.debug('%s: no signal', raw_data)
            self._log.warning('sig is too short: %s .. ignored', raw_data)
            return False

        self.clear_wave_hash()
        w = []

        total_us = 0
        for pulse, space in raw_data:
            total_us += pulse + space

            w.append(self.create_pulse_wave(pulse))
            w.append(self.create_space_wave(space))
        self._log.debug('total_us: %d', total_us)

        for i in range(repeat):
            self.pi.wave_chain(w)

            while self.pi.wave_tx_busy():
                time.sleep(0.01)
            time.sleep(0.005)

        self.clean_wave()

        return True

    def send(self, dev_name, button_name):
        self._log.debug('dev_name=%s, button_name=%s', dev_name, button_name)

        if self.irconf is None:
            self.irconf = IrConfig(load_all=True, debug=self._dbg)
            if self.irconf.data is None:
                self._log.error('loading config files: failed')
                return False

        raw_data, repeat = self.irconf.get_raw_data(dev_name, button_name)
        if raw_data is None:
            return False
        return self.send_raw_data(raw_data, repeat)

    def get_dev_list(self):
        self._log.debug('')

        dev_list = []
        for d in self.irconf.data:
            dev_list.append(d['data']['dev_name'])

        return dev_list

    def get_macro_and_button(self, dev_name):
        """
        Returns
        -------
        ret: {'macro': {'[m1]': 'mdata1', '[m2]': 'mdata2'},
              'buttons': {'b1': 'bdata1', 'b2': 'bdata2'}}
        """
        self._log.debug('dev_name=%s', dev_name)

        dev = self.irconf.get_dev(dev_name)
        if dev is None:
            self._log.warning('%s: no such device', dev_name)
            return None

        ret = {'macro': dev['data']['macro'],
               'buttons': dev['data']['buttons']}
        return ret


#####
import threading
import queue


class App:
    MSG_LIST        = '__list__'
    MSG_SLEEP       = '__sleep__'
    MSG_END         = '__end__'

    def __init__(self, args, n, interval, pin, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, self._dbg)
        self._log.debug('args=%s, n=%d, interval=%d, pin=%d',
                          args, n, interval, pin)

        if len(args) == 0:
            self.dev_name = ''
            self.buttons  = []
        else:
            self.dev_name = args[0]
            self.buttons  = args[1:]
        self.n        = n
        self.interval = interval
        self.pin      = pin

        self.irsend = IrSend(self.pin, load_conf=True, debug=self._dbg)

        self.msgq = queue.Queue()
        self.th_worker = threading.Thread(target=self.worker)
        self.th_worker.start()

    def main(self):
        self._log.debug('')

        if self.dev_name == '':
            msg = [self.MSG_LIST, '']
            self._log.debug('msg=%s', msg)
            self.msgq.put(msg)
            self.end_main()
            return

        print('dev: %s' % self.dev_name)

        if len(self.buttons) == 0:
            msg = [self.dev_name, self.MSG_LIST]
            self._log.debug('msg=%s', msg)
            self.msgq.put(msg)
            self.end_main()
            return

        for i in range(self.n):
            if self.n > 1:
                print('[%d]' % (i + 1))

            for b in self.buttons:
                print('  button: %s' % b)
                msg = [self.dev_name, b]
                self._log.debug('msg=%s', msg)
                self.msgq.put([self.dev_name, b])
                if self.interval > 0:
                    print('   sleep: %.1f sec' % self.interval)
                    self.msgq.put([self.MSG_SLEEP, self.interval])

        self.end_main()

    def end_main(self):
        self._log.debug('')

        self.msgq.put([self.MSG_END, ''])
        self._log.debug('join()')
        self.th_worker.join()

    def worker(self):
        """
        サブスレッド

        メッセージキューからメッセージ ``msg``を受け取って処理する

        メッセージフォーマット
        ----------------------
          [dev_name, button_name]: 赤外線信号送信
          [MSG_SLEEP, sleep_sec]:  スリープ
          [MSG_LIST, '']:          デバイス名リスト
          [dev_name, MSG_LIST]:    ボタン名リスト
          [MSG_END, '']:           終了

        """
        self._log.debug('')

        while True:
            msg = self.msgq.get()
            self._log.debug('msg=%s', msg)

            (dev_name, button_name) = msg

            if dev_name == self.MSG_END:
                self._log.debug('msg:MSG_END')
                break

            if dev_name == self.MSG_SLEEP:
                self._log.debug('msg:[MSG_SLEEP, %s]', button_name)
                time.sleep(int(button_name))
                continue

            if dev_name == self.MSG_LIST:
                self._log.debug('msg:MSG_LIST')
                # show device list
                self.show_dev_list()
                break

            if button_name == self.MSG_LIST:
                self._log.debug('msg:[%s, MSG_LIST]', dev_name)
                # show button list
                self.show_button_list(dev_name)
                break

            if not self.irsend.send(dev_name, button_name):
                self._log.error('%s,%s: sending failed',
                                  dev_name, button_name)
            time.sleep(0.1)

        self._log.debug('done')

    def end(self):
        """
        終了処理(強制終了)

        メッセージキューに残っている場合は、全て捨ててから、
        ``MSG_END``を格納して、``th_worker``スレッドが終了するの待つ。

        """
        self._log.debug('')

        if self.th_worker.is_alive():
            count = 0
            while not self.msgq.empty():
                count += 1
                self._log.debug('msgq.get()[%d]', count)
                self.msgq.get()
            self.msgq.put([self.MSG_END, ''])
            self._log.debug('join()')
            self.th_worker.join()

        self.irsend.end()
        print('done')
        self._log.debug('done')

    def show_dev_list(self):
        self._log.debug('')

        for d in self.irsend.get_dev_list():
            print('%s' % d)

    def show_button_list(self, dev_name):
        self._log.debug('dev_name=%s', dev_name)

        ret = self.irsend.get_macro_and_button(dev_name)
        if ret is None:
            print('%s: no such device' % dev_name)
            return
        self._log.debug('ret=%s', ret)

        macro = ret['macro']
        for m in macro:
            if macro[m] != '':
                print(' %-17s : %s' % (m, macro[m]))
        print()

        buttons = ret['buttons']
        for b in buttons:
            if buttons[b] != '':
                print(' %-17s : %s' % (b, buttons[b]))
        print()


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='IR signal transmitter')
@click.argument('args', type=str, nargs=-1)
@click.option('--pin', '-p', 'pin', type=int, default=IrSend.DEF_PIN,
              help='pin number')
@click.option('-n', 'n', type=int, default=1)
@click.option('--interval', '-i', 'interval', type=float, default=0.0)
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(args, pin, interval, n, debug):
    logger = get_logger(__name__, debug)
    logger.debug('args=%s, n=%d, interval=%f, pin=%d',
                 args, n, interval, pin)

    app = App(args, n, interval, pin, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.debug('done')


if __name__ == '__main__':
    main()
