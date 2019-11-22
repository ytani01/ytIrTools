#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrServer.py

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'


import socketserver
import socket
import threading
import json
import time

from MyLogger import get_logger


DEF_PIN = 22


class IrSendHandler(socketserver.StreamRequestHandler):
    DEF_TIMEOUT = 5  # sec

    def __init__(self, req, c_addr, svr):
        self._debug = svr._debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('c_addr=%s', c_addr)

        self._svr = svr

        self.timeout = self.DEF_TIMEOUT
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

            ret = self._svr.irsend(cmdline[0], cmdline[1])
            self._logger.debug('ret=%s', ret)
            self.net_write(json.dumps(ret) + '\r\n')
            break

        self._logger.debug('done')

    def finish(self):
        self._logger.debug('')
        self._active = False
        self._logger.debug('_active=%s', self._active)
        return super().finish()


class IrSendServer(socketserver.ThreadingTCPServer):
    DEF_PORT = 12352

    def __init__(self, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s', port)

        self._port = port

        self.allow_reuse_address = True  # Important !!

        self._active = False
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
    MSG_LIST        = '__list__'
    MSG_SLEEP       = '__sleep__'
    MSG_END         = '__end__'

    def __init__(self, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%d', port)

        self._port = port

        self._svr = IrSendServer(self._port, self._debug)
        self._svr_th = threading.Thread(target=self._svr.serve_forever,
                                        daemon=True)

    def main(self):
        self._logger.debug('%s', self._svr_th.daemon)

        self._svr_th.start()

        while True:
            time.sleep(1)

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
@click.option('--port', 'port', type=int, default=12352,
              help='port number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%d', port)

    app = App(port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.debug('done')


if __name__ == '__main__':
    main()
