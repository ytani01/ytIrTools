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
import json
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

        self._topic = topic

        # self._bbt = Beebotte(topic, debug=self._debug)
        self._bbt = Beebotte(topic, debug=False)

    def start(self):
        self._logger.debug('')

        self._bbt.start()

        self._bbt.subscribe()

    def end(self):
        self._logger.debug('')
        self._bbt.publish(self._topic, 0)  # dummy before disconnect
        time.sleep(2)
        self._bbt.end()
        self._logger.debug('done')

    def get_temp(self, block=True):
        self._logger.debug('block=%s', block)

        msg_type, msg_data = self._bbt.wait_msg(self._bbt.MSG_DATA)
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

    DEF_KP = 2.5
    DEF_KI = 0.03
    DEF_KD = 100

    K_I_MAX = 5.0

    REMOCON_TEMP_MIN = 21
    REMOCON_TEMP_MAX = 29

    def __init__(self, target_temp, dev, button_header, topic, pin,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('target_temp=%.1f', target_temp)
        self._logger.debug('dev=%s, button_header=%s', dev, button_header)
        self._logger.debug('topic=%s', topic)
        self._logger.debug('pin=%d', pin)

        self._aircon = Aircon(dev, button_header, pin, debug=self._debug)

        self._temp = Temp(topic, debug=self._debug)
        # self._temp = Temp(topic)

        self._target_temp = target_temp
        self._remocon_temp = round(self._target_temp)

        self._temp_hist = []  # [{'ts':ts1, 'temp':temp1}, ..]

        self._ir_active = True

        self._kp = self.DEF_KP
        self._ki = self.DEF_KI
        self._kd = self.DEF_KD
        self._i = 0

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

        # self.net_write('Ready\r\n')

        while self._active:
            # receive net_data
            try:
                net_data = self.request.recv(512)
            except BaseException as e:
                self._logger.info('BaseException:%s:%s.', type(e), e)
                return
            else:
                self._logger.debug('net_data=%a', net_data)
            if net_data == b'' or net_data == b'\x04':
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

            # self.net_write('ACK\r\n')

            # cmdline
            cmdline = decoded_data.split()
            self._logger.debug('cmdline=%s', cmdline)
            if len(cmdline) == 0:
                break
            if len(cmdline) == 1:
                cmdline.append('')
                self._logger.debug('cmdline=%s', cmdline)

            try:
                ret = self._server._cmd[cmdline[0]](cmdline[1])
                self.net_write(json.dumps(ret) + '\r\n')
            except KeyError:
                ret = {'rc': 'NG', 'msg': '%s: no such command' % cmdline[0]}
                self._logger.error(json.dumps(ret))
                self.net_write(json.dumps(ret) + '\r\n')

        self._logger.debug('done')

    def finish(self):
        self._logger.debug('')
        return super().finish()


class AutoAirconServer(socketserver.TCPServer):
    DEF_PORT = 12351

    def __init__(self, cmd, port=DEF_PORT, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('cmd=')
        for c in cmd:
            self._logger.debug('  %s', c)
        self._logger.debug('port=%d', port)

        self._cmd = cmd
        self._port = port

        flag_ok = False
        while not flag_ok:
            try:
                super().__init__(('', self._port), AutoAirconHandler)
                flag_ok = True
                self._logger.debug('flag_ok=%s', flag_ok)
            except OSError as e:
                self._logger.warning('%s:%s. retry..', type(e), e)
                time.sleep(5)
            except Exception as e:
                self._logger.error('%s:%s.', type(e), e)
                return None

    def serve_forever(self):
        self._logger.debug('')
        return super().serve_forever()

    def end(self):
        self._logger.debug('')


class App:
    def __init__(self, target_temp, dev, button_header, topic, pin, tty,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('target_temp=%.1f', target_temp)
        self._logger.debug('dev=%s, button_header=%s', dev, button_header)
        self._logger.debug('topic=%s', topic)
        self._logger.debug('tty=%s', tty)
        self._logger.debug('pin=%d', pin)

        self._tty = tty

        self._loop = True

        self._cmd = {
            'kp': self.cmd_kp,
            'ki': self.cmd_ki,
            'kd': self.cmd_kd,
            'temp': self.cmd_temp,
            'rtemp': self.cmd_remocon_temp,
            'ttemp': self.cmd_target_temp,
            'on':   self.cmd_on,
            'off':  self.cmd_off,
            'shutdown': self.cmd_shutdown
        }

        self._aircon = AutoAircon(target_temp, dev, button_header, topic, pin,
                                  debug=self._debug)

        self._server = AutoAirconServer(self._cmd, debug=self._debug)

        self._server_th = threading.Thread(target=self._server.serve_forever,
                                           daemon=True)

        self._cmd_th = threading.Thread(target=self.cmd, daemon=True)

    def main(self):
        self._logger.debug('')

        self._aircon.start()

        self._server_th.start()

        if self._tty:
            self._cmd_th.start()

        while self._loop:
            time.sleep(1)

    def end(self):
        self._logger.debug('')
        self._aircon.end()
        self._server.end()
        self._logger.debug('done')

    def cmd(self):
        self._logger.debug('')

        while self._loop:
            try:
                cmdline = input().split()
            except EOFError:
                cmdline = ''

            self._logger.debug('cmdline=%s', cmdline)
            if len(cmdline) == 0:
                continue
            if len(cmdline) == 1:
                cmdline.append('')
                self._logger.debug('cmdline=%s', cmdline)

            try:
                ret = self._cmd[cmdline[0]](cmdline[1])
            except KeyError:
                self._logger.error('%s: no such command', cmdline[0])
                continue

            print(json.dumps(ret))

    def cmd_kp(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            kp = float(param)
            self._aircon._kp = kp
            self._aircon._i = 0
        else:
            kp = self._aircon._kp

        ret = {'rc': 'OK', 'kp': kp}
        return ret

    def cmd_ki(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            ki = float(param)
            self._aircon._ki = ki
            self._aircon._i = 0
        else:
            ki = self._aircon._ki

        ret = {'rc': 'OK', 'ki': ki}
        return ret

    def cmd_kd(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            kd = float(param)
            self._aircon._kd = kd
            self._aircon._i = 0
        else:
            kd = self._aircon._kd

        ret = {'rc': 'OK', 'kd': kd}
        return ret

    def cmd_temp(self, param):
        self._logger.debug('param=%s', param)

        if len(self._aircon._temp_hist) == 0:
            ret = {'rc': 'NG', 'cur_temp': None}
        else:
            ret = {'rc': 'OK', 'cur_temp': self._aircon._temp_hist[-1]['temp']}
        return ret

    def cmd_remocon_temp(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            remocon_temp = int(param)
            self._aircon._remocon_temp = remocon_temp
            self._aircon.irsend_temp(remocon_temp, force=True)
        else:
            remocon_temp = self._aircon._remocon_temp

        ret = {'rc': 'OK', 'remocon_temp': remocon_temp}
        return ret

    def cmd_target_temp(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            target_temp = float(param)
            self._aircon._target_temp = target_temp
            self._aircon._remocon_temp = round(target_temp)
            self._aircon._i = 0
            self._aircon.irsend_temp(target_temp, force=True)
        else:
            target_temp = self._aircon._target_temp

        ret = {'rc': 'OK', 'target_temp': target_temp}
        return ret

    def cmd_on(self, param):
        self._logger.debug('param=%s', param)

        self._aircon._ir_active = True
        self._aircon.irsend_temp()
        self._i = 0

        ret = {'rc': 'OK', 'msg': 'on'}
        return ret

    def cmd_off(self, param):
        self._logger.debug('param=%s', param)

        self._aircon._ir_active = False
        self._aircon.irsend_temp(0, force=True)

        ret = {'rc': 'OK', 'msg': 'off'}
        return ret

    def cmd_shutdown(self, param):
        self._logger.debug('param=%s', param)

        self._loop = False

        ret = {'rc': 'OK', 'msg': 'shutdown'}
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
@click.option('--tty', 'tty', is_flag=True, default=False,
              help='tty command input')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(target_temp, dev, button_header, topic, pin, tty, debug):
    logger = get_logger(__name__, debug)
    logger.debug('target_temp=%.1f', target_temp)
    logger.debug('dev=%s, button_header=%s', dev, button_header)
    logger.debug('topic=%s', topic)
    logger.debug('pin=%d', pin)
    logger.debug('tty=%s', tty)

    app = App(target_temp, dev, button_header, topic, pin, tty, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
