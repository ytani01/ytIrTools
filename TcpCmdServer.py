#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
TcpCmdServer -- サーバープログラムのベース

クライアントからの要求(コマンド文字列)を受け取り、
対応するコマンド(関数)を実行する。

* コマンド文字列: コマンド名とパラメータ (スペース区切り)

    "コマンド名 param1 param2 .."

* コマンドとパラメータは、関数に渡される前にリストに分解される。

* リプライ: JSON文字列

    '{"rc": Cmd.RC_*, "msg": 任意のメッセージ}'

------------
各コマンドには、
CmdServerHandler で即時に実行される関数(FUNC_I)と、
キューイングされて、CmdServerApp で順に実行される関数(FUNC_Q)を
登録できる。

FAUNC_I: 複数クライアントからの要求が並列実行される(マルチスレッド)。
FAUNC_Q: 並列実行されず、必ず順に一つずつ実行される(シングルスレッド)。


オブジェクト
------------
main()
  |
  +- CmdServerApp
       |
       +- Cmd
       |
       +- CmdServer
            |
            +- CmdServerHandler

スレッド
--------
main() - CmdServerApp:main() - Cmd.main()
           |
           +- CmdServer.serve_forever()
           |   |
           |   +- CmdServerHandler.handle()
           |
           +- CmdServerApp.cmd_worker()

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


class Cmd:
    """
    __init__()を override
      self.add_cmd()でコマンドを登録。
      最後に、super().__init__() を呼び出す。

    コマンドに対応する関数を定義する。
      def cmd_..(self, args):
        :
        return rc, msg

    コマンド実行以外の処理は、main(), end()を override
      self._active をフラグとして利用

    """
    DEF_PORT = 59001

    RC_OK = 'OK'  # OK .. FUNC_I の場合は、キューイング不要
    RC_NG = 'NG'  # NG
    RC_CONT = 'CONTINUE'  # FUNC_I 正常終了 .. キューイングして結果を待つ
    RC_ACCEPT = 'ACCEPT'  # FUNC_I 正常終了 .. キューイングして結果を待たない

    FUNC_I = 'func_i'
    FUNC_Q = 'func_q'
    HELP_STR = 'help'

    CMD_HELP = 'help'
    CMD_EXIT = 'exit'
    CMD_SHUTDOWN = 'shutdown9999'

    def __init__(self, init_param=None, port=DEF_PORT, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('init_param=%s, port=%s', init_param, port)

        if port is None:
            self._port = self.DEF_PORT
        else:
            self._port = port
        self._logger.debug('_port=%d', self._port)

        self._active = True  # main()の終了条件に使用

        self.add_cmd('sleep', self.cmd_i_sleep, self.cmd_q_sleep, 'sleep')
        self.add_cmd(self.CMD_HELP, self.cmd_i_help, None, 'command help')
        self.add_cmd(self.CMD_EXIT, self.cmd_i_exit, None, 'disconnect')
        self.add_cmd(self.CMD_SHUTDOWN,
                     self.cmd_i_shutdown, self.cmd_q_shutdown,
                     'shutdown server')

    def main(self):
        """
        override
        """
        self._logger.debug('')

        while self._active:
            time.sleep(1)

        self._active = False
        self._logger.debug('done')

    def end(self):
        self._logger.debug('')
        self._logger.debug('done')

    def start(self):
        self._logger.debug('')
        self._active = True
        self._logger.debug('done')

    def stop_main(self):
        """
        override:
        main()内の処理を止める。
        その後の終了処理(資源の開放やサブスレッドの終了など)は、
        end() で行う。
        """
        self._logger.debug('')
        self._active = False
        self._logger.debug('done')

    def add_cmd(self, name, func_i, func_q, help_str):
        self._logger.debug('name=%a, func_i=%a, func_q=%a, help_str=%a',
                           name, func_i, func_q, help_str)

        try:
            self._cmd
        except AttributeError:
            self._logger.debug('create: self._cmd')
            self._cmd = {}

        self._cmd[name] = {
            self.FUNC_I: func_i,
            self.FUNC_Q: func_q,
            self.HELP_STR: help_str
        }

    def cmd_i_help(self, args):
        """
        コマンド一覧
        """
        self._logger.debug('args=%a', args)

        if len(args) >= 2:
            if args[1] in self._cmd:
                msg = self._cmd[args[1]]['help']
                rc = self.RC_OK
                return rc, msg
            else:
                msg = '%s: no such command' % args[1]
                rc = self.RC_NG
                return rc, msg

        # command list
        msg = []
        for c in self._cmd:
            msg.append([c, self._cmd[c]['help']])

        rc = self.RC_OK
        return rc, msg

    def cmd_i_sleep(self, args):
        """
        サーバーをスリープさせる。
        クライアントも待たされる。

        ここでは、引数の事前チェックのみ。
        """
        self._logger.debug('args=%a', args)

        try:
            sleep_sec = float(args[1])
        except Exception as e:
            rc = self.RC_NG
            msg = '%s: %s: %s' % (args[0], type(e), e)
        else:
            rc = self.RC_CONT
            msg = 'sleep_sec=%s' % sleep_sec
        self._logger.debug(msg)
        return rc, msg

    def cmd_q_sleep(self, args):
        """
        サーバーをさせる。
        クライアントも待たされる。

        事前チェックされたパラメータ(秒数)受け取り、
        実際にスリープする。
        """
        self._logger.debug('args=%a', args)

        rc = self.RC_OK

        sleep_sec = float(args[1])
        msg = '%s: sleep_sec=%s' % (args[0], sleep_sec)

        time.sleep(sleep_sec)
        self._logger.debug('sleep:done')
        return rc, msg

    def cmd_i_exit(self, args):
        """
        接続を切断する。
        """
        self._logger.debug('args=%a', args)
        return self.RC_OK, None

    def cmd_i_shutdown(self, args):
        """
        指定された秒数後にサーバープロセスをシャットダウン。
        クライアントは、待たずに完了。

        ここでは、パラメータの事前チェックを行い。
        受理 (ACCEPT) する。

        """
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            return self.RC_ACCEPT, 'sleep_sec=0'

        try:
            sleep_sec = float(args[1])
        except Exception as e:
            rc = self.RC_NG
            msg = '%s: %s: %s' % (args[0], type(e), e)
        else:
            rc = self.RC_ACCEPT
            msg = 'sleep_sec=%s' % sleep_sec
        self._logger.debug(msg)
        return rc, msg

    def cmd_q_shutdown(self, args):
        """
        指定された秒数後にサーバープロセスをシャットダウン。
        クライアントは、待たずに完了。

        指定された秒数スリープし、OK を返すだけ。

        メインルーチン (CmdServerApp:main)で、
        コマンド名をキーに判断され、シャットダウン処理が実行される。
        """
        self._logger.debug('args=%a', args)

        rc = self.RC_OK

        if len(args) == 1:
            sleep_sec = 0
        else:
            sleep_sec = float(args[1])

        msg = '%s: sleep_sec=%s' % (args[0], sleep_sec)
        self._logger.debug(msg)

        time.sleep(sleep_sec)
        self._logger.debug('sleep:done')

        return rc, msg


class CmdServerHandler(socketserver.StreamRequestHandler):
    """
    override 不要
    """
    DEF_HANDLE_TIMEOUT = 3  # sec

    EOF = '\x04'

    def __init__(self, req, c_addr, svr):
        self._debug = svr._debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('c_addr=%s', c_addr)

        self._svr = svr

        self._active = False
        self._myq = queue.SimpleQueue()

        # 変数名は固定: self.request.recv() のタイムアウト
        self.timeout = self.DEF_HANDLE_TIMEOUT
        self._logger.debug('timeout=%s sec', self.timeout)

        return super().__init__(req, c_addr, svr)

    def setup(self):
        self._logger.debug('_active=%s', self._active)
        self._active = True
        self._logger.debug('_active=%s', self._active)
        return super().setup()

    def finish(self):
        self._logger.debug('_active=%s', self._active)
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

    def send_reply(self, rc, msg=None, cont=False):
        self._logger.debug('rc=%a, msg=%a, cont=%s', rc, msg, cont)

        if msg is None:
            rep = {'rc': rc}
        else:
            rep = {'rc': rc, 'msg': msg}
        rep_str = json.dumps(rep)
        rep_str += '\r\n'
        if not cont:
            rep_str += self.EOF
        self._logger.debug('rep_str=%a', rep_str)
        self.net_write(rep_str)

    def handle(self):
        self._logger.debug('')

        while self._active:
            self._logger.debug('wait net_data')
            try:
                # in_data = self.rfile.readline().strip()
                #                ↓
                # rfile だと、一度タイムアウトすると、
                # 二度と読めない!?
                #              ↓
                in_data = self.request.recv(512).strip()

            except socket.timeout as e:
                self._logger.debug('%s:%s.', type(e), e)
                self._logger.debug('_svr._active=%s', self._svr._active)
                if self._svr._active:
                    # サーバーが生きている場合は、継続
                    continue
                else:
                    self.send_reply(Cmd.RC_NG, 'server is dead !')
                    break
            except Exception as e:
                self._logger.warning('%s:%s.', type(e), e)
                msg = 'error %s:%s' % (type(e), e)
                self.send_reply(Cmd.RC_NG, msg)
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
                self._logger.error(msg)
                self.send_reply(Cmd.RC_NG, msg)
                break
            else:
                self._logger.debug('decoded_data=%a', decoded_data)

            # get args
            args = decoded_data.split()
            self._logger.debug('args=%s', args)
            if len(args) == 0:
                msg = 'no command'
                self._logger.warning(msg)
                self.send_reply(Cmd.RC_NG, msg)
                break

            # check command
            if args[0] not in self._svr._app._cmd._cmd:
                msg = '%s: no such command .. ignored' % args[0]
                self._logger.error(msg)
                self.send_reply(Cmd.RC_NG, msg)
                continue

            if self._svr._app._cmd._cmd[args[0]][Cmd.FUNC_I] is not None:
                #
                # interactive command
                #
                self._logger.info('call %s: %a', Cmd.FUNC_I, args)
                rc, msg = self._svr._app._cmd._cmd[args[0]][Cmd.FUNC_I](args)
                self._logger.info('rc=%s, msg=%s', rc, msg)

                if args[0] == Cmd.CMD_EXIT:
                    self._active = False
                    self._logger.debug('_active=%s', self._active)

                if rc != Cmd.RC_CONT and rc != Cmd.RC_ACCEPT:
                    self.send_reply(rc, msg)
                    continue

                if rc == Cmd.RC_ACCEPT:
                    self._myq = None

            # check FANC_Q
            if self._svr._app._cmd._cmd[args[0]][Cmd.FUNC_Q] is None:
                msg2 = '%s: %s is None .. ignored' % (args[0], Cmd.FUNC_Q)
                self._logger.warning(msg2)
                if msg is None:
                    self.send_reply(Cmd.RC_OK, msg2)
                else:
                    self.send_reply(Cmd.RC_OK, msg)
                continue

            #
            # queuing
            #

            # check que size
            qsize = self._svr._app._cmdq.qsize()
            if qsize > 100:
                msg = 'qsize=%d: server busy' % qsize
                self._logger.warning(msg)
                self.send_reply(Cmd.RC_NG, msg)
                continue

            # put args to queue
            try:
                self._svr._app._cmdq.put((args, self._myq), block=False)
            except Exception as e:
                msg = '%s:%s' % (type(e), e)
                self._logger.error(msg)
                self.send_reply(Cmd.RC_NG, msg)
                continue

            # if _myq is None (RC_ACCEPT), send reply now
            if self._myq is None:
                self._logger.debug('reply queue is None .. send reply')
                self.send_reply(Cmd.RC_OK, msg)
                continue

            # wait result from _myq
            self._logger.debug('wait result')
            rc, msg = self._myq.get()
            if rc == Cmd.RC_OK:
                self._logger.debug('rc=%s, msg=%s', rc, msg)
            else:
                self._logger.error('rc=%s, msg=%s', rc, msg)

            # send reply
            self.send_reply(rc, msg)

        self._logger.debug('done')


class CmdServer(socketserver.ThreadingTCPServer):
    """
    override 不要
    """
    def __init__(self, app, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s', port)

        self._app = app
        self._port = port

        self._active = False
        self.allow_reuse_address = True  # Important !!

        while not self._active:
            try:
                super().__init__(('', self._port), CmdServerHandler)
                self._active = True
                self._logger.info('_active=%s,_port=%s',
                                  self._active, self._port)
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
    def __init__(self, cmd_class, init_param=None, port=Cmd.DEF_PORT,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('cmd_class=%s, init_param=%s, port=%s',
                           cmd_class, init_param, port)

        self._cmdq = queue.Queue()

        self._cmd = cmd_class(init_param, port, debug=self._debug)
        self._svr = CmdServer(self, self._cmd._port, self._debug)
        self._svr_th = threading.Thread(target=self._svr.serve_forever,
                                        daemon=True)
        self._cmd_worker_th = threading.Thread(target=self.cmd_worker,
                                               daemon=True)

    def cmd_worker(self):
        self._logger.debug('')

        loop = True

        while loop:
            args, repq = self._cmdq.get()
            self._logger.info('args=%a', args)

            # check and call cmd
            if args[0] in self._cmd._cmd:
                if self._cmd._cmd[args[0]][Cmd.FUNC_Q] is not None:

                    # call cmd
                    self._logger.debug('call %s: %a', Cmd.FUNC_Q, args)
                    rc, msg = self._cmd._cmd[args[0]][Cmd.FUNC_Q](args)

                    if rc == Cmd.RC_OK:
                        self._logger.info('rc=%a, msg=%a', rc, msg)
                    else:
                        self._logger.error('rc=%a, msg=%a', rc, msg)
                else:
                    rc = Cmd.RC_NG
                    msg = '%s: no such %s .. ignored' % (args[0], Cmd.FUNC_Q)
                    self._logger.error(msg)
            else:
                rc = Cmd.RC_NG
                msg = '%s: no such command .. ignored' % args[0]
                self._logger.error(msg)

            if repq is not None:
                self._logger.debug('put reply')
                repq.put((rc, msg))

            # shutdown check
            if args[0] == Cmd.CMD_SHUTDOWN:
                self._logger.info('shutdown !!')
                time.sleep(1)
                break

            time.sleep(0.1)

        self._cmd.stop_main()
        self._logger.debug('done')

    def main(self):
        self._svr_th.start()
        self._cmd_worker_th.start()

        self._cmd.main()

        self._logger.debug('done')

    def end(self):
        self._logger.debug('')
        while not self._cmdq.empty():
            args, repq = self._cmdq.get()
            self._logger.debug('args=%s, repq=%s', args, repq)
            if repq is not None:
                repq.put((Cmd.RC_NG, 'terminated'))
        self._svr.end()
        self._cmd.end()
        self._logger.debug('done')


import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='TCP Server base class')
@click.option('--port', 'port', type=int,
              help='port number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s', port)

    logger.info('start')

    app = CmdServerApp(Cmd, init_param=None, port=port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.info('end')


if __name__ == '__main__':
    main()
