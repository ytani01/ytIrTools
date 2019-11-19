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
import socketserver
import socket
import time

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

        self._active = True

        self._bbt = Beebotte(topic, debug=self._debug)

    def start(self):
        self._logger.debug('')

        self._bbt.start()
        msg_type, msg_data = self.wait_msg(self._bbt.MSG_OK)
        if msg_type != self._bbt.MSG_OK:
            return

        self._bbt.subscribe()

    def end(self):
        self._logger.debug('')
        self._active = False
        self._bbt.end()
        self._logger.debug('done')

    def wait_msg(self, wait_msg_type):
        self._logger.debug('wait_msg_type=%s', wait_msg_type)

        (msg_type, msg_data) = (self._bbt.MSG_NONE, None)

        while self._active:
            msg_type, msg_data = self._bbt.get_msg(block=True, timeout=1)
            if msg_type == wait_msg_type:
                break

        self._logger.debug('msg_type=%s, msg_data=%s', msg_type, msg_data)
        return msg_type, msg_data

    def get_temp(self, block=True):
        self._logger.debug('block=%s', block)

        msg_type, msg_data = self.wait_msg(self._bbt.MSG_DATA)
        if msg_type != self._bbt.MSG_DATA:
            return 0, 0

        payload = msg_data['payload']
        ts = payload['ts'] / 1000  # msec -> sec
        temp = float(payload['data'])

        return ts, temp


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

    def irsend(self, button):
        self._logger.debug('button=%s', button)

        self._irsend.send(self._dev, button)

    def irsend_temp(self, temp):
        self._logger.debug('temp=%d', temp)

        button = self._button_header + str(temp)
        if temp == 0:
            button = 'off'
        self._logger.debug('button=%s', button)

        self.irsend(button)

    def end(self):
        self._logger.debug('')
        self._irsend.end()
        self._logger.debug('done')


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

        # self._temp = Temp(topic, debug=self._debug)
        self._temp = Temp(topic)

        self._target_temp = target_temp
        self._remocon_temp = round(self._target_temp) - 1

        self._temp_hist = []  # [{'ts':ts1, 'temp':temp1}, ..]

        self._kp = self.DEF_KP
        self._ki = self.DEF_KI
        self._kd = self.DEF_KD
        self._i = 0

        self._ir_active = True

        self._loop = True
        super().__init__(daemon=True)

    def end(self):
        self._logger.debug('')
        self._loop = False
        self._temp.end()
        while self.is_alive():
            self._logger.debug('.')
            time.sleep(1)
        self._aircon.end()
        self._logger.debug('done')

    def run(self):
        self._logger.debug('')

        self.irsend_temp()

        self._temp.start()

        while self._loop:
            ts, temp = self._temp.get_temp()
            if ts == 0:
                self._logger.debug('ts=%d', ts)
                break

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

                self.irsend_temp()

        self._logger.debug('done')

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
        k_p = self._kp * p_

        # I
        d_ts = cur_ts - prev_ts
        i_temp = (cur_temp + prev_temp) * d_ts / 2
        i_temp -= self._target_temp * d_ts
        self._logger.debug('_i=%f, i_temp=%f', self._i, i_temp)
        i_ = self._i + i_temp
        k_i = self._ki * i_
        if abs(k_i) <= self.K_I_MAX:
            self._i = i_

        # D
        d_ = (cur_temp - first_temp) / (cur_ts - first_ts)
        k_d = self._kd * d_

        # PID
        pid = k_p + k_i + k_d

        self._logger.debug('(p_ ,i_ ,d_ )=(%8.4f,%8.4f,%8.4f)', p_, i_, d_)
        self._logger.debug('(k_p,k_i,k_d)=(%8.4f,%8.4f,%8.4f)', k_p, k_i, k_d)
        self._logger.debug('pid=%f', pid)
        return pid

    def ts2datestr(self, ts):
        return self._temp._bbt.ts2datestr(ts * 1000)

    def irsend_temp(self, temp=None, force=False):
        """
        Parameters
        ----------
        temp: 0=off
        force: bool
        """
        self._logger.debug('temp=%s, force=%s', temp, force)

        if temp is None:
            temp = self._remocon_temp

        temp = int(temp)
        self._logger.debug('temp=%d', temp)

        self._logger.debug('_ir_active=%s', self._ir_active)
        if self._ir_active or force:
            self._aircon.irsend_temp(temp)

    def get_cur_temp(self):
        self._logger.debug('')
        if len(self._temp_hist) == 0:
            return 99.99
        return self._temp_hist[-1]['temp']

    def get_remocon_temp(self):
        self._logger.debug('')
        return self._remocon_temp

    def get_target_temp(self):
        self._logger.debug('')
        return self._target_temp

    def set_target_temp(self, temp):
        self._logger.debug('temp=%.1f', temp)

        self._target_temp = temp
        self._remocon_temp = round(self._target_temp) - 1
        self.irsend_temp()
        self._i = 0

    def on(self):
        self._logger.debug('')
        self._ir_active = True
        self.irsend_temp()
        self._logger.debug('_ir_active=%s', self._ir_active)

    def off(self):
        self._logger.debug('')
        self._ir_active = False
        self.irsend_temp(0, force=True)
        self._logger.debug('_ir_active=%s', self._ir_active)


class AutoAirconHandler(socketserver.StreamRequestHandler):
    def __init__(self, request, client_address, server):
        self._debug = server._debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('client_address=%s', client_address)

        self._server = server
        self._active = True

        return super().__init__(request, client_address, server)

    def setup(self):
        self._logger.debug('')
        return super().setup()

    def net_write(self, msg, enc='utf-8'):
        self._logger.debug('msg=%a, enc=%s', msg, enc)

        if enc != '':
            msg = msg.encode(enc)
            self._logger.debug('msg=%a', msg)
        try:
            self.wfile.write(msg)
        except Exception as e:
            self._logger.debug('%s:%s.', type(e), e)

    def handle(self):
        self._logger.debug('')

        self.net_write('Ready\r\n')

        while self._active:
            # receive net_data
            try:
                net_data = self.request.recv(512)
            except BaseException as e:
                self._logger.info('BaseException:%s:%s.', type(e), e)
                return
            else:
                self._logger.debug('net_data=%a', net_data)
            if net_data == b'':
                self._active = False
                break

            # decode
            try:
                decoded_data = net_data.decode('utf-8')
            except UnicodeDecodeError as e:
                self._logger.debug('%s:%s .. ignored', type(e), e)
                continue
            else:
                self._logger.debug('decoded_data:%a', decoded_data)

            self.net_write('ACK\r\n')

            # cmdline
            cmdline = decoded_data.split()
            self._logger.debug('cmdline=%s', cmdline)
            if len(cmdline) == 0:
                continue
            if len(cmdline) == 1:
                cmdline.append('')
                self._logger.debug('cmdline=%s', cmdline)

            try:
                ret = self._server._cmd[cmdline[0]](cmdline[1])
                self.net_write('OK: ' + ret + '\r\n')
            except KeyError:
                ret = '%s: no such command' % cmdline[0]
                self._logger.error(ret)
                self.net_write('NG: ' + ret + '\r\n')

        self._logger.debug('done')

    def finish(self):
        self._logger.debug('')
        return super().finish()


class AutoAirconServer(socketserver.TCPServer):
    DEF_PORT = 12351

    def __init__(self, cmd, port=DEF_PORT, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('cmd=%s, port=%d', cmd, port)

        self._cmd = cmd
        self._port = port

        while self.is_port_in_use(self._port):
            self._logger.warning('port:%d in use .. waiting',
                                 self._port)
            time.sleep(1)
        self._logger.debug('port:%d is free', self._port)

        try:
            super().__init__(('', self._port), AutoAirconHandler)
        except Exception as e:
            self._logger.debug('%s:%s.', type(e), e)
            return None

    def serve_forever(self):
        self._logger.debug('')
        return super().serve_forever()

    def end(self):
        self._logger.debug('')

    def is_port_in_use(self, port):
        self._logger.debug('port=%d', port)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0


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
            'curtemp': self.cmd_get_cur_temp,
            'rtemp': self.cmd_get_remocon_temp,
            'ttemp': self.cmd_get_target_temp,
            'temp': self.cmd_target_temp,
            'on':   self.cmd_on,
            'off':  self.cmd_off,
            'stop': self.cmd_stop
        }

        self._aircon = AutoAircon(target_temp, dev, button_header, topic, pin,
                                  debug=self._debug)

        self._server = AutoAirconServer(self._cmd, debug=self._debug)

        self._server_th = threading.Thread(target=self._server.serve_forever,
                                           daemon=True)

    def main(self):
        self._logger.debug('')

        self._aircon.start()

        self._server_th.start()

        while self._loop:
            cmdline = input().split()
            self._logger.debug('cmdline=%s', cmdline)
            if len(cmdline) == 0:
                continue
            if len(cmdline) == 1:
                cmdline.append('')
                self._logger.debug('cmdline=%s', cmdline)

            try:
                ret = self._cmd[cmdline[0]](cmdline[1])
                print(ret)
            except KeyError:
                self._logger.error('%s: no such command', cmdline[0])

    def end(self):
        self._logger.debug('')
        self._aircon.end()
        self._server.end()
        self._logger.debug('done')

    def cmd_get_cur_temp(self, param):
        self._logger.debug('param=%s', param)

        cur_temp = self._aircon.get_cur_temp()

        ret = 'cur_temp=%.2f' % cur_temp
        return ret

    def cmd_get_remocon_temp(self, param):
        self._logger.debug('param=%s', param)

        remocon_temp = self._aircon.get_remocon_temp()

        ret = 'remocon_temp=%d' % remocon_temp
        return ret

    def cmd_get_target_temp(self, param):
        self._logger.debug('param=%s', param)

        target_temp = self._aircon.get_target_temp()

        ret = 'target_temp=%.1f' % target_temp
        return ret

    def cmd_target_temp(self, param):
        self._logger.debug('param=%s', param)

        if param == '':
            ret = 'NG: no target temp'
            return ret

        target_temp = float(param)
        self._aircon.set_target_temp(target_temp)

        ret = 'OK'
        return ret

    def cmd_on(self, param):
        self._logger.debug('param=%s', param)

        self._aircon.on()

        ret = 'OK'
        return ret

    def cmd_off(self, param):
        self._logger.debug('param=%s', param)

        self._aircon.off()

        ret = 'OK'
        return ret

    def cmd_stop(self, param):
        self._logger.debug('param=%s', param)

        self._loop = False

        ret = 'OK'
        return ret


import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='AutoAircon')
@click.argument('target_temp', type=float, default=25.5)
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
