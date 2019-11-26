#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
TcpCmdServer

要求(コマンド文字列)を受け取り、
対応するコマンド(関数)をサーバー側で実行する。

要求は、内部でキューイングされて、順番に実行される。
クライアントには、キューイングと同時に受理した旨返信し、
通信を終了する。

クライアントは、コメントが受理されたことがわかり、
コマンド実行の成否はわからない。

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'


import socketserver
import socket
import threading
import queue
import json
import time

from MyLogger import get_logger


class CmdServerHandler(socketserver.StreamRequestHandler):
    DEF_HANDLE_TIMEOUT = 3  # sec

    RC_ACCEPT = 'ACCEPT'
    RC_NG = 'NG'

    def __init__(self, req, c_addr, svr):
        self._debug = svr._debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('c_addr=%s', c_addr)

        self._svr = svr

        # 変数名は固定: self.request.recv() のタイムアウト
        self.timeout = self.DEF_HANDLE_TIMEOUT
        self._logger.debug('timeout=%s sec', self.timeout)

        return super().__init__(req, c_addr, svr)

    def setup(self):
        self._logger.debug('timeout=%s', self.timeout)
        self._active = True
        self._logger.debug('_active=%s', self._active)
        return super().setup()

    def finish(self):
        self._logger.debug('')
        self._active = False
        self._logger.debug('_active=%s', self._active)
        return super().finish()

    def set_timeout(self, timeout=DEF_HANDLE_TIMEOUT):
        self._debug('timeout=%s', timeout)
        self.timeout = timeout

    def net_write(self, msg, enc='utf-8'):
        self._logger.debug('msg=%a, enc=%s', msg, enc)

        if enc != '':
            msg = msg.encode(enc)
            self._logger.debug('msg=%a', msg)
        try:
            self.wfile.write(msg)
        except Exception as e:
            self._logger.warning('%s:%s.', type(e), e)

    def send_reply(self, rc, msg=None):
        self._logger.debug('rc=%a, msg=%a', rc, msg)

        if msg is None:
            rep = {'rc': rc}
        else:
            rep = {'rc': rc, 'msg': msg}
        rep_str = json.dumps(rep)
        self._logger.debug('rep_str=%a', rep_str)
        self.net_write(rep_str + '\r\n')

    def handle(self):
        self._logger.debug('')

        while self._active:
            self._logger.debug('wait net_data')
            try:
                # in_data = self.rfile.readline().strip()
                # ↓
                # rfile の場合、一度タイムアウトすると、
                # 二度と読めない!?
                # ↓
                in_data = self.request.recv(512).strip()

            except socket.timeout as e:
                self._logger.warning('%s:%s.', type(e), e)
                self._logger.warning('_svr._active=%s', self._svr._active)
                if self._svr._active:
                    # サーバーが生きている場合は、継続
                    continue
                else:
                    self.send_reply(self.RC_NG, 'server is inactive.')
                    break
            except Exception as e:
                self._logger.warning('%s:%s.', type(e), e)
                msg = 'error %s:%s' % (type(e), e)
                self.send_reply(self.RC_NG, msg)
                break
            else:
                self._logger.debug('in_data=%a', in_data)

            if len(in_data) == 0 or in_data == b'\x04':
                self._logger.debug('disconnected')
                break

            # decode
            try:
                decoded_data = in_data.decode('utf-8')
            except UnicodeDecodeError as e:
                msg = '%s:%s .. ignored' % (type(e), e)
                self._logging.error(msg)
                self.send_reply(self.RC_NG, msg)
                break
            else:
                self._logger.debug('decoded_data=%a', decoded_data)

            # get cmdline
            args = decoded_data.split()
            self._logger.debug('args=%s', args)
            if len(args) == 0:
                msg = 'no command'
                self._logger.warning(msg)
                self.send_reply(self.RC_NG, msg)
                break

            self._logger.info('qsize=%d', self._svr._cmdq.qsize())
            try:
                self._svr._cmdq.put(args, block=False)
            except Exception as e:
                msg = '%s:%s' % (type(e), e)
                self._logger.error(msg)
            else:
                self.send_reply(self.RC_ACCEPT)

        self._logger.debug('done')

    def cmd_devlist(self):
        self._logger.debug('')

        devlist = self._svr._irsend.get_dev_list()
        ret = {'rc': 'OK', 'data': devlist}
        return ret

    def cmd_help(self):
        self._logger.debug('')


class CmdServer(socketserver.ThreadingTCPServer):
    DEF_PORT = 12399

    def __init__(self, cmdq, port=DEF_PORT, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s', port)

        self._cmdq = cmdq
        self._port = port or self.DEF_PORT

        self._active = False
        self.allow_reuse_address = True  # Important !!

        while not self._active:
            try:
                super().__init__(('', self._port), CmdServerHandler)
                self._active = True
                self._logger.debug('_active=%s', self._active)
            except PermissionError as e:
                self._logger.error('%s:%s.', type(e), e)
                raise
            except OSError as e:
                self._logger.error('%s:%s .. retry', type(e), e)
                time.sleep(5)
            except Exception as e:
                self._logger.error('%s:%s.', type(e), e)
                raise

        self._logger.debug('done')

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


class CmdServerApp:
    """
    """
    CMD = {'ECHO': '@echo',
           'SLEEP': '@sleep',
           'LOAD': '@load',
           'END': '@end'}

    def __init__(self, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s', port)

        self._port = port

        self._cmdq = queue.Queue()

        self._svr = CmdServer(self._cmdq, self._port, self._debug)
        self._svr_th = threading.Thread(target=self._svr.serve_forever,
                                        daemon=True)

    def main(self):
        self._logger.debug('%s', self._svr_th.daemon)

        self._svr_th.start()

        while True:
            cmdline = self._cmdq.get()
            self._logger.info('cmdline=%s', cmdline)

            # exec cmd

            time.sleep(0.1)

    def end(self):
        self._logger.debug('')
        self._svr.end()
        self._logger.debug('done')


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='TCP Server Template')
@click.option('--port', 'port', type=int,
              help='port number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s', port)

    logger.info('start')

    app = CmdServerApp(port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.info('end')


if __name__ == '__main__':
    main()
