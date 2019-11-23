#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrServer.py

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


DEF_PIN = 22


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

            cmdline = cmdline[:2]
            self._svr._cmdq.put(cmdline)
            self.net_write(json.dumps(cmdline) + '\r\n')

        self._logger.debug('done')

    def finish(self):
        self._logger.debug('')
        self._active = False
        self._logger.debug('_active=%s', self._active)
        return super().finish()


class IrSendServer(socketserver.ThreadingTCPServer):
    DEF_PORT = 12352

    def __init__(self, cmdq, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s', port)

        self._cmdq = cmdq
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
    CMD = {'LIST': '@list',
           'SLEEP': '@sleep',
           'END': '@end'}

    def __init__(self, port, pin, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s, pin=%s', port, pin)

        self._port = port
        if port is None:
            self._port = IrSendServer.DEF_PORT
            self._logger.debug('port=%d', self._port)

        self._pin = pin
        if pin is None:
            self._pin = IrSend.DEF_PIN
            self._logger.debug('pin=%d', self._pin)

        self._cmdq = queue.Queue()

        self._irsend = IrSend(self._pin, load_conf=True, debug=self._debug)
        self._svr = IrSendServer(self._cmdq, self._port, self._debug)
        self._svr_th = threading.Thread(target=self._svr.serve_forever,
                                        daemon=True)

    def main(self):
        self._logger.debug('%s', self._svr_th.daemon)

        self._svr_th.start()

        while True:
            cmdline = self._cmdq.get()
            self._logger.debug('cmdline=%s', cmdline)

            if cmdline[0] == self.CMD['END']:
                self._logger.debug('cmd:END .. ignored')
                break

            if cmdline[0] == self.CMD['SLEEP']:
                sleep_sec = float(cmdline[1])
                self._logger.debug('cmd:SLEEP %ssec', sleep_sec)
                time.sleep(sleep_sec)
                continue

            if cmdline[0] == self.CMD['LIST']:
                self._logger.debug('cmd:LIST')
                # dev_list = self.irsend.get_dev_list()
                continue

            if cmdline[1] == self.CMD['LIST'] or cmdline == '':
                dev_name = cmdline[0]
                self._logger.debug('%s cmd:LIST', dev_name)
                # m_b = self.irsend.get_macro_and_button(dev_name)
                continue

            # dev_name button
            dev_name, button_name = cmdline
            self._logger.debug('%s %s', dev_name, button_name)
            # irsend(dev_name, button_name)
            time.sleep(0.1)

    def end(self):
        """
        終了処理
        """
        self._svr.end()
        self._logger.debug('')


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='IR signal server')
@click.option('--port', 'port', type=int,
              help='port number')
@click.option('--pin', 'pin', type=int,
              help='GPIO pin number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, pin, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s, pin=%s', port, pin)

    app = App(port, pin, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.debug('done')


if __name__ == '__main__':
    main()
