#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrSendServer.py

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'


from IrSend import IrSend
import socketserver
import socket
import threading
import queue
import json
import time

from MyLogger import get_logger


class IrSendHandler(socketserver.StreamRequestHandler):
    DEF_HANDLE_TIMEOUT = 5  # sec

    def __init__(self, req, c_addr, svr):
        self._debug = svr._debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('c_addr=%s', c_addr)

        self._svr = svr

        self.timeout = self.DEF_HANDLE_TIMEOUT
        self._logger.debug('timeout=%s sec', self.timeout)

        return super().__init__(req, c_addr, svr)

    def setup(self):
        self._active = True
        self._logger.debug('_active=%s', self._active)
        return super().setup()

    def net_write(self, msg, enc='utf-8'):
        self._logger.debug('msg=%a, enc=%s', msg, enc)

        if enc != '':
            msg = msg.encode(enc)
            self._logger.debug('msg=%a', msg)
        try:
            self.wfile.write(msg)
        except Exception as e:
            self._logger.warning('%s:%s.', type(e), e)

    def handle(self):
        self._logger.debug('')

        while self._active:
            self._logger.debug('wait net_data')
            try:
                # in_data = self.rfile.readline().strip()
                # ↓
                # rfile の場合、一度タイムアウトすると、
                # 二度と読めない。
                # ↓
                in_data = self.request.recv(512).strip()
            except socket.timeout as e:
                self._logger.debug('%s:%s.', type(e), e)

                self._logger.debug('_svr._active=%s', self._svr._active)
                if self._svr._active:
                    # サーバーが生きている場合は、継続
                    continue
                else:
                    break
            except Exception as e:
                self._logger.warning('%s:%s.', type(e), e)
                break
            else:
                self._logger.debug('in_data=%a', in_data)

            if len(in_data) == 0:
                break

            # decode
            try:
                decoded_data = in_data.decode('utf-8')
            except UnicodeDecodeError as e:
                self._logging.error('%s:%s .. ignored', type(e), e)
                break
            else:
                self._logger.debug('decoded_data=%a', decoded_data)

            # get cmdline
            cmdline = decoded_data.split()
            self._logger.debug('cmdline=%s', cmdline)
            if len(cmdline) == 0:
                break
            if len(cmdline) == 1:
                cmdline.append('')
                self._logger.debug('cmdline=%s', cmdline)

            p1, p2 = cmdline[:2]
            self._logger.info('pi1,p2=%a,%a', p1, p2)

            if p1 == self._svr.CMD['LIST']:
                ret = self.cmd_devlist()

            elif p1 == self._svr.CMD['SLEEP']:
                try:
                    sec = float(p2)
                except ValueError:
                    msg = '%a: invalid sleep sec .. ignored' % p2
                    ret = {'rc': 'NG', 'data': msg}
                    self._logger.warning(msg)
                else:
                    self._svr._cmdq.put([p1, p2])
                    ret = {'rc': 'OK'}

            elif p1 == self._svr.CMD['LOAD']:
                self._svr._cmdq.put([p1, p2])
                ret = {'rc': 'OK'}

            elif p2 == self._svr.CMD['LIST'] or p2 == '':
                ret = self.cmd_buttonlist(p1)

            else:  # [dev, button]
                self._svr._cmdq.put([p1, p2])
                ret = {'rc': 'OK'}

            self.net_write(json.dumps(ret) + '\r\n')

        self._logger.debug('done')

    def finish(self):
        self._logger.debug('')
        self._active = False
        self._logger.debug('_active=%s', self._active)
        return super().finish()

    def cmd_devlist(self):
        self._logger.debug('')

        devlist = self._svr._irsend.get_dev_list()
        ret = {'rc': 'OK', 'data': devlist}
        return ret

    def cmd_buttonlist(self, dev_name):
        self._logger.debug('dev_name=%s', dev_name)

        buttonlist = self._svr._irsend.get_macro_and_button(dev_name)
        self._logger.debug('buttonlist=%s', buttonlist)
        if buttonlist is None:
            ret = {'rc': 'NG', 'data': '%s: no such device' % dev_name}
        else:
            ret = {'rc': 'OK', 'data': buttonlist}
        return ret

    def cmd_help(self):
        self._logger.debug('')


class IrSendServer(socketserver.ThreadingTCPServer):
    DEF_PORT = 12352

    CMD = {'LIST': '@list',
           'SLEEP': '@sleep',
           'LOAD': '@load',
           'END': '@end'}

    def __init__(self, cmdq, irsend, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s', port)

        self._cmdq = cmdq
        self._irsend = irsend
        self._port = port

        self._active = False
        self.allow_reuse_address = True  # Important !!
        while not self._active:
            try:
                super().__init__(('', self._port), IrSendHandler)
                self._active = True
                self._logger.debug('_active=%s', self._active)
            except PermissionError as e:
                self._logger.error('%s:%s.', type(e), e)
                raise
            except OSError as e:
                self._logger.error('%s:%s.', type(e), e)
                time.sleep(5)
            except Exception as e:
                self._logger.error('%s:%s.', type(e), e)
                raise

        self._logger.debug('done')

    """
    # self.allow_reuse_address = True としてるため、以下は不要
    def server_bind(self):
        self._logger.debug('')
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
    """

    def serve_forever(self):
        self._logger.debug('start')
        super().serve_forever()
        self._logger.debug('done')

    """
    def service_actions(self):
        self._logger.debug('')
        super().service_actions()
        self._logger.debug('done')
    """

    def end(self):
        self._logger.debug('')
        self.shutdown()  # serve_forever() を終了させる
        self._active = False  # handle()を終了させる
        self._logger.debug('done')

    def irsend(self, dev, btn):
        self._logger.debug('dev=%s, btn=%s', dev, btn)

        ret = {'rc': 'OK', 'dev': dev, 'btn': btn}
        return ret


class App:
    """
    cmdline :=
      [dev_name, button_name] ... 赤外線信号送信
      [CMD['SLEEP'], sec]     ... スリープ
      [CMD['LIST'], '']       ... デバイス名リスト
      [dev_name, CMD['LIST']] ... ボタン名リスト
      [CMD['END'], '']        ... 終了(無視)
    """
    def __init__(self, port, pin, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s, pin=%s', port, pin)

        self._port = port or IrSendServer.DEF_PORT
        self._pin = pin or IrSend.DEF_PIN
        self._logger.debug('port=%d, pin=%d', self._port, self._pin)

        self._cmdq = queue.Queue()

        self._irsend = IrSend(self._pin, load_conf=True, debug=self._debug)
        self._svr = IrSendServer(self._cmdq, self._irsend, self._port,
                                 self._debug)
        self._svr_th = threading.Thread(target=self._svr.serve_forever,
                                        daemon=True)

    def main(self):
        self._logger.debug('%s', self._svr_th.daemon)

        self._svr_th.start()

        while True:
            cmdline = self._cmdq.get()
            self._logger.debug('cmdline=%s', cmdline)

            if cmdline[0] == self._svr.CMD['END']:
                msg = 'cmd:END .. ignored'
                self._logger.info(msg)
                continue

            if cmdline[0] == self._svr.CMD['SLEEP']:
                sleep_sec = float(cmdline[1])
                msg = 'cmd:SLEEP %ssec' % sleep_sec
                self._logger.info(msg)
                time.sleep(sleep_sec)
                continue

            if cmdline[0] == self._svr.CMD['LOAD']:
                self._svr._irsend.reload_conf()
                self._logger.debug('%s', self._svr._irsend.irconf.data)
                continue

            # send IR signal
            dev_name, button_name = cmdline
            msg = 'send IR: %s %s' % (dev_name, button_name)
            self._logger.info(msg)
            self._irsend.send(dev_name, button_name)
            time.sleep(0.1)

    def end(self):
        self._logger.debug('')
        self._svr.end()
        self._logger.debug('done')


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='IR signal send server')
@click.option('--port', 'port', type=int,
              help='port number')
@click.option('--pin', 'pin', type=int,
              help='GPIO pin number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, pin, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s, pin=%s', port, pin)

    logger.info('start')

    app = App(port, pin, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.info('end')


if __name__ == '__main__':
    main()
