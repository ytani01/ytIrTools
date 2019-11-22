#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
AutoAircon.py

Class
-----
App
  AutoAircon
    Aircon
      IrSend
    Temp
      Beebotte
        Mqtt

Thread
------
(th) App.main()
  (th) AutoAirconServer.serve_forever()
  (th) cui()

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'


from IrSend import IrSend
from ytBeebotte import Beebotte
import threading
import socketserver
import socket
import json
import time
import os
import configparser

from MyLogger import get_logger


class Temp:
    DEF_TOPIC = 'env1/temp'

    TEMP_END = 99

    def __init__(self, topic=None, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('topic=%s', topic)

        self._topic = self.DEF_TOPIC
        if topic is not None:
            self._topic = topic
        self._logger.debug('_topic=%s', self._topic)

        # self._bbt = Beebotte(self._topic, debug=self._debug)
        self._bbt = Beebotte(self._topic, debug=False)

    def start(self):
        self._logger.debug('')

        self._bbt.start()

        self._bbt.subscribe()

    def end(self):
        self._logger.debug('')
        self._bbt.publish(self._topic, self.TEMP_END)  # for disconnect
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
    DEF_DEV_NAME = 'aircon'
    DEF_BUTTON_HEADER = 'on_hot_auto_'
    DEF_PIN = 22

    def __init__(self, dev=None, button_header=None, pin=None, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev=%s, button_header=%s, pin=%s',
                           dev, button_header, pin)

        self._dev = self.DEF_DEV_NAME
        self._button_header = self.DEF_BUTTON_HEADER
        self._pin = self.DEF_PIN

        if dev is not None:
            self._dev = dev
        if button_header is not None:
            self._button_header = button_header
        if pin is not None:
            self._pin = pin

        self._logger.debug('_dev=%s, _button_header=%s, _pin=%d',
                           self._dev, self._button_header, self._pin)

        # self._irsend = IrSend(self._pin, load_conf=True, debug=self._debug)
        self._irsend = IrSend(self._pin, load_conf=True, debug=False)

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
    DEF_KI = 0.02
    DEF_KD = 100

    DEF_KI_I_MAX = 5.0

    REMOCON_TEMP_MIN = 22
    REMOCON_TEMP_MAX = 29

    def __init__(self, target_temp, temp=None, aircon=None,
                 kp=None, ki=None, kd=None, ki_i_max=None,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('target_temp=%.1f', target_temp)

        self._target_temp = target_temp
        self._temp = temp
        self._aircon = aircon

        self._kp = self.DEF_KP
        if kp is not None:
            self._kp = kp
        self._ki = self.DEF_KI
        if ki is not None:
            self._ki = ki
        self._kd = self.DEF_KD
        if kd is not None:
            self._kd = kd
        self._ki_i_max = self.DEF_KI_I_MAX
        if ki_i_max is not None:
            self._ki_i_max = ki_i_max
        self._logger.debug('_kp=%s, _ki=%s, _kd=%s, _ki_i_max=%s',
                           self._kp, self._ki, self._kd, self._ki_i_max)

        self._i = 0
        self._cmd = {
            'temp': self.cmd_temp,
            'rtemp': self.cmd_remocon_temp,
            'ttemp': self.cmd_target_temp,
            'on':   self.cmd_on,
            'off':  self.cmd_off,
            'kp': self.cmd_kp,
            'ki': self.cmd_ki,
            'kd': self.cmd_kd,
            'ki_i_max': self.cmd_ki_i_max,
            'shutdown': self.cmd_shutdown,
            'help': self.cmd_help,
            '?': self.cmd_help
        }

        self._stat = AutoAirconStat(debug=self._debug)

        self._remocon_temp = round(self._target_temp)

        self._temp_hist = []  # [{'ts':ts1, 'temp':temp1}, ..]
        # self._ir_active = True
        self._ir_active = False
        self._loop = True

        super().__init__(daemon=True)

    def end(self):
        self._logger.debug('')

        self._ir_active = False
        self._stat.publish('active', self._ir_active)

        self._loop = False
        self._stat.end()
        self._temp.end()
        while self.is_alive():
            self._logger.debug('.')
            time.sleep(1)
        self._aircon.end()
        self._logger.debug('done')

    def run(self):
        self._logger.debug('')

        self._stat.publish('kp', self._kp)
        self._stat.publish('ki', self._ki)
        self._stat.publish('kd', self._kd)

        # self.irsend_temp(force=True)

        self._temp.start()

        while self._loop:
            self._stat.publish('active', self._ir_active)

            ts, temp = self._temp.get_temp()
            if ts == 0:
                self._logger.debug('ts=%d', ts)
                break
            if temp == self._temp.TEMP_END:
                self._logger.debug('temp=TEMP_END')
                break
            self._stat.publish('temp', temp)
            self._stat.publish('ttemp', self._target_temp)
            self._stat.publish('rtemp', self._remocon_temp)

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
            self._logger.debug('remocon_temp=%d, _remocon_temp=%d',
                               remocon_temp, self._remocon_temp)

            if remocon_temp != self._remocon_temp:
                self._remocon_temp = remocon_temp
                self._logger.debug('_remocon_temp=%d', remocon_temp)

                self.irsend_temp()

        self._logger.debug('done')

    def exec_cmd(self, cmd, param):
        self._logger.debug('cmd=%s, param=%s', cmd, param)

        try:
            ret = self._cmd[cmd](param)
        except KeyError:
            self._logger.error('%s: no such command', cmd)
            ret = {'rc': 'NG', 'msg': '%s: no such command' % cmd}
        return ret

    def cmd_help(self, param):
        self._logger.debug('param=%s', param)

        cmd_list = []
        for c in self._cmd:
            cmd_list.append(c)

        ret = {'rc': 'OK', 'cmd': cmd_list}
        return ret

    def cmd_kp(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            kp = float(param)
            self._kp = kp
            self._stat.publish('kp', self._kp)
            self._i = 0
        else:
            kp = self._kp

        ret = {'rc': 'OK', 'kp': kp}
        return ret

    def cmd_ki(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            ki = float(param)
            self._ki = ki
            self._stat.publish('ki', self._ki)
            self._i = 0
        else:
            ki = self._ki

        ret = {'rc': 'OK', 'ki': ki}
        return ret

    def cmd_kd(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            kd = float(param)
            self._kd = kd
            self._stat.publish('kd', self._kd)
            self._i = 0
        else:
            kd = self._kd

        ret = {'rc': 'OK', 'kd': kd}
        return ret

    def cmd_ki_i_max(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            ki_i_max = float(param)
            self._ki_i_max = ki_i_max
            self._i = 0
        else:
            ki_i_max = self._ki_i_max

        ret = {'rc': 'OK', 'ki_i_max': ki_i_max}
        return ret

    def cmd_temp(self, param):
        self._logger.debug('param=%s', param)

        if len(self._temp_hist) == 0:
            ret = {'rc': 'NG', 'cur_temp': None}
        else:
            ret = {'rc': 'OK', 'cur_temp': self._temp_hist[-1]['temp']}
        return ret

    def cmd_remocon_temp(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            remocon_temp = int(param)
            self._remocon_temp = remocon_temp
            self.irsend_temp(remocon_temp, force=True)
            self._stat.publish('rtemp', self._remocon_temp)
        else:
            remocon_temp = self._remocon_temp

        ret = {'rc': 'OK', 'remocon_temp': remocon_temp}
        return ret

    def cmd_target_temp(self, param):
        self._logger.debug('param=%s', param)

        if param != '':
            target_temp = float(param)
            self._target_temp = target_temp
            self._stat.publish('ttemp', self._target_temp)

            self._i = 0

            self._remocon_temp = round(target_temp)
            self.irsend_temp(self._remocon_temp, force=True)
        else:
            target_temp = self._target_temp

        ret = {'rc': 'OK', 'target_temp': target_temp}
        return ret

    def cmd_on(self, param):
        self._logger.debug('param=%s', param)

        self._ir_active = True
        self.irsend_temp(force=True)
        self._i = 0

        self._stat.publish('active', self._ir_active)

        ret = {'rc': 'OK', 'msg': 'on'}
        return ret

    def cmd_off(self, param):
        self._logger.debug('param=%s', param)

        self._ir_active = False
        self.irsend_temp(0, force=True)

        self._stat.publish('active', self._ir_active)

        ret = {'rc': 'OK', 'msg': 'off'}
        return ret

    def cmd_shutdown(self, param):
        self._logger.debug('param=%s', param)

        ret = {'rc': 'OK', 'msg': 'shutdown'}
        return ret

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
        kp_p = self._kp * p_

        # I
        d_ts = cur_ts - prev_ts
        i_temp = (cur_temp + prev_temp) * d_ts / 2
        i_temp -= self._target_temp * d_ts
        self._logger.debug('_i=%f, i_temp=%f', self._i, i_temp)
        i_ = self._i + i_temp
        ki_i = self._ki * i_
        if abs(ki_i) <= self._ki_i_max:
            self._i = i_

        # D
        d_ = (cur_temp - first_temp) / (cur_ts - first_ts)
        kd_d = self._kd * d_

        # PID
        pid = kp_p + ki_i + kd_d

        self._logger.debug('( p_, i_, d_)=(%5.2f,%7.2f,%6.3f)', p_, i_, d_)
        self._logger.debug('(kp_p,ki_i,kd_d)=(%5.2f,%7.2f,%6.3f)',
                           kp_p, ki_i, kd_d)
        self._logger.debug('pid=%f', pid)

        self._stat.publish('kpp', kp_p)
        self._stat.publish('kii', ki_i)
        self._stat.publish('kdd', kd_d)
        self._stat.publish('pid', pid)
        return pid

    def ts2datestr(self, ts_msec):
        """
        ts_msec -> ts(sec)

        Parameters
        ----------
        ts_msec: int
        """
        return self._temp._bbt.ts2datestr(ts_msec * 1000)

    def irsend_temp(self, temp=None, force=False):
        """
        Parameters
        ----------
        temp: 0:off, None:_remocon_temp
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


class AutoAirconStat:
    def __init__(self, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('')

        self._ch = 'aircon1'
        self._param = ['temp', 'ttemp', 'rtemp', 'active',
                       'pid', 'kpp', 'kii', 'kdd', 'kp', 'ki', 'kd']

        self._topic = []
        for p in self._param:
            self._topic.append(self._ch + '/' + p)
        self._logger.debug('_topic=%s', self._topic)

        # self._bbt = Beebotte(self._topic, debug=self._debug)
        self._bbt = Beebotte(self._topic)
        self._bbt.start()

    def end(self):
        self._logger.debug('')
        self._bbt.end()
        self._logger.debug('done')

    def publish(self, name, data):
        self._logger.debug('name=%s, data=%s', name, data)

        if name not in self._param:
            return False

        topic = self._ch + '/' + name
        self._bbt.publish(topic, data)
        self._bbt.wait_msg(Beebotte.MSG_OK)
        return True


class AutoAirconHandler(socketserver.StreamRequestHandler):
    DEF_TIMEOUT = 5.0  # sec

    def __init__(self, request, client_address, server):
        self._debug = server._debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('client_address=%s', client_address)

        self._svr = server
        self._active = True

        self.timeout = self.DEF_TIMEOUT  # important !!
        self._logger.debug('timeout=%s sec', self.timeout)

        return super().__init__(request, client_address, server)

    def setup(self):
        self._logger.debug('')
        return super().setup()

    def handle_timeout(self):
        self._logger.debug('')

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
            self._logger.debug('wait net_data')
            try:
                net_data = self.request.recv(512)
            except BaseException as e:
                self._logger.debug('BaseException:%s:%s.', type(e), e)

                self._logger.debug('_svr._active=%s', self._svr._active)
                if self._svr._active:
                    continue
                else:
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
                ret = self._svr._auto_aircon.exec_cmd(cmdline[0], cmdline[1])
                self.net_write(json.dumps(ret) + '\r\n')
            except KeyError:
                ret = {'rc': 'NG', 'msg': '%s: no such command' % cmdline[0]}
                self._logger.error(json.dumps(ret))
                self.net_write(json.dumps(ret) + '\r\n')

        self._logger.debug('done')

    def finish(self):
        self._logger.debug('')
        return super().finish()


class AutoAirconServer(socketserver.ThreadingTCPServer):
    DEF_PORT = 12351

    def __init__(self, auto_aircon, port=None, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s', port)

        self._auto_aircon = auto_aircon
        self._port = port
        if port is None:
            self._port = self.DEF_PORT

        self._active = False
        while not self._active:
            try:
                super().__init__(('', self._port), AutoAirconHandler)
                self._active = True
                self._logger.debug('_active=%s', self._active)
            except PermissionError as e:
                self._logger.error('%s: %s.', type(e), e)
                raise
            except OSError as e:
                self._logger.warning('%s: %s. retry..', type(e), e)
                time.sleep(5)
            except Exception as e:
                self._logger.error('%s: %s.', type(e), e)
                raise

        self._logger.debug('done')

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

    def serve_forever(self):
        self._logger.debug('')
        ret = super().serve_forever()
        self._logger.debug('done')
        return ret

    def end(self):
        self._logger.debug('')
        self._active = False


class App:
    CONF_FILENAME = ['autoaircon', '.autoaircon']
    CONF_PATH = ['.', os.environ['HOME'], 'etc']

    def __init__(self, target_temp, tty=None,
                 dev=None, button_header=None, pin=None,
                 topic=None, svr_port=None,
                 kp=None, ki=None, kd=None, ki_i_max=None,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('target_temp=%s, tty=%s', target_temp, tty)
        self._logger.debug('dev=%s, button_header=%s, pin=%s',
                           dev, button_header, pin)
        self._logger.debug('topic=%s', topic)
        self._logger.debug('svr_port=%s', svr_port)
        self._logger.debug('kp=%s, ki=%s, kd=%s, ki_i_max=%s',
                           kp, ki, kd, ki_i_max)

        self._tty = tty

        # set parameters
        cfg = self.load_conf()
        self._logger.debug('cfg=%s', list(cfg))

        if dev is None:
            dev = cfg.get('aircon', 'dev_name', fallback=None)
        if button_header is None:
            button_header = cfg.get('aircon', 'button_header', fallback=None)
        if pin is None:
            pin = cfg.getint('aircon', 'gpio_pin', fallback=None)
        self._logger.debug('dev=%s, button_header=%s, pin=%s',
                           dev, button_header, pin)

        if topic is None:
            topic = cfg.get('temp', 'topic', fallback=None)
        self._logger.debug('topic=%s', topic)

        if svr_port is None:
            svr_port = cfg.getint('server', 'port', fallback=svr_port)
        self._logger.debug('svr_port=%s', svr_port)

        if kp is None:
            kp = cfg.getfloat('auto_aircon', 'kp', fallback=None)
        if ki is None:
            ki = cfg.getfloat('auto_aircon', 'ki', fallback=None)
        if kd is None:
            kd = cfg.getfloat('auto_aircon', 'kd', fallback=None)
        if ki_i_max is None:
            ki_i_max = cfg.getfloat('auto_aircon', 'ki_i_max', fallback=None)
        self._logger.debug('kp=%s, ki=%s, kd=%s, ki_i_max=%s',
                           kp, ki, kd, ki_i_max)

        #
        self._loop = True

        # objects
        # temp = Temp(topic, debug=self._debug)
        temp = Temp(topic)

        aircon = Aircon(dev, button_header, pin, debug=self._debug)

        self._auto_aircon = AutoAircon(target_temp, temp, aircon,
                                       kp, ki, kd, ki_i_max,
                                       debug=self._debug)

        self._svr = AutoAirconServer(self._auto_aircon, svr_port,
                                     debug=self._debug)

        # threads
        self._svr_th = threading.Thread(target=self._svr.serve_forever,
                                        daemon=True)
        self._logger.debug('_svr_th.daemon:%s', self._svr_th.daemon)

        self._cui_th = threading.Thread(target=self.cui, daemon=True)

    def main(self):
        self._logger.debug('')

        self._auto_aircon.start()
        self._svr_th.start()

        if self._tty:
            self._cui_th.start()

        while self._loop:
            time.sleep(1)

        self._logger.debug('done')

    def end(self):
        self._logger.debug('')
        self._auto_aircon.end()
        self._logger.debug('_svr.shutdown()')
        self._svr.shutdown()
        self._logger.debug('_svr.end()')
        self._svr.end()
        self._logger.debug('done')

    def find_conf(self):
        self._logger.debug('')

        for dir in self.CONF_PATH:
            for fname in self.CONF_FILENAME:
                pathname = dir + '/' + fname
                self._logger.debug('pathname=%s', pathname)
                if self.isreadable(pathname):
                    return pathname
        return None

    def isreadable(self, path):
        self._logger.debug('path=%s', path)

        try:
            f = open(path)
            f.close()
        except FileNotFoundError:
            return False
        except Exception as e:
            self._logger.debug('%s:%s.', type(e), e)
            return False
        return True

    def load_conf(self):
        self._logger.debug('')

        conf_file = self.find_conf()
        self._logger.debug('conf_file=%s', conf_file)
        if conf_file is None:
            conf_file = ''

        cfg = configparser.ConfigParser()
        try:
            cfg.read(conf_file)
        except Exception as e:
            self._logger.warning('%s: %s.', type(e), e)

        for s in cfg:
            for p in cfg[s]:
                self._logger.debug('%s:%s:%s', s, p, cfg[s][p])

        return cfg

    def cui(self):
        self._logger.debug('')

        while self._loop:
            try:
                cmdline = input().split()
            except EOFError:
                print('EOF .. shutdown')
                cmdline = ['shutdown']

            self._logger.debug('cmdline=%s', cmdline)
            if len(cmdline) == 0:
                continue
            if len(cmdline) == 1:
                cmdline.append('')
                self._logger.debug('cmdline=%s', cmdline)

            try:
                ret = self._auto_aircon.exec_cmd(cmdline[0], cmdline[1])
            except KeyError:
                self._logger.error('%s: no such command', cmdline[0])
                continue

            print(json.dumps(ret))

            if cmdline[0] == 'shutdown':
                self._loop = False


import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='AutoAircon')
@click.argument('target_temp', type=float, default=25.5)
@click.option('--tty', 'tty', is_flag=True, default=False,
              help='tty command input')
@click.option('--dev', 'dev', type=str,
              help='device name')
@click.option('--button_header', '-b', 'button_header', type=str,
              help='button_header')
@click.option('--pin', '-p', 'pin', type=int,
              help='GPIO pin number')
@click.option('--topic', '-t', 'topic', type=str,
              help='topic')
@click.option('--svr_port', '--sp', '-s', 'svr_port', type=int,
              help='server port')
@click.option('--kp', 'kp', type=float, help='PID param: kp')
@click.option('--ki', 'ki', type=float, help='PID param: ki')
@click.option('--kd', 'kd', type=float, help='PID param: kd')
@click.option('--ki_i_max', 'ki_i_max', type=float,
              help='PID param: ki_i_max')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(target_temp, tty, dev, button_header, pin, topic, svr_port,
         kp, ki, kd, ki_i_max, debug):
    logger = get_logger(__name__, debug)
    logger.debug('target_temp=%.1f, tty=%s', target_temp, tty)
    logger.debug('dev=%s, button_header=%s, pin=%s', dev, button_header, pin)
    logger.debug('topic=%s', topic)
    logger.debug('svr_port=%s', svr_port)
    logger.debug('kp=%s, ki=%s, kd=%s, ki_i_max=%s', kp, ki, kd, ki_i_max)

    app = App(target_temp, tty, dev, button_header, pin, topic, svr_port,
              kp, ki, kd, ki_i_max,
              debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
