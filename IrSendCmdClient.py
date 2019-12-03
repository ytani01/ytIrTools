#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrSendCmdClient
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from TcpCmdClient import TcpCmdClient, TcpCmdClientApp
from IrSendCmdServer import IrSendCmd
import json

from MyLogger import get_logger


class IrSendCmdClient(TcpCmdClient):
    DEF_SVR_HOST = 'localhost'
    DEF_SVR_PORT = IrSendCmd.DEF_PORT

    CMD_NAME = IrSendCmd.CMD_NAME

    DEF_TIMEOUT = 3  # sec
    
    def __init__(self, host=DEF_SVR_HOST, port=DEF_SVR_PORT, debug=False):
        """
        サーバーホスト、サーバーポートのデフォルト値を変えるためだけの定義
        """
        super().__init__(host, port, debug=debug)

    def send_recv(self, args,
                  timeout=DEF_TIMEOUT, newline=False):
        """
        args := [dev, button1, button2, ..]

        ボタンを複数指定可能: どれかが NG だと、最後の NGを返す。
        """
        self._logger.debug('args=%a', args)

        args = [self.CMD_NAME] + list(args)

        if len(args) <= 2:
            # [CMD_NAME] or [CMD_NAME, dev]
            return super().send_recv(args, timeout=timeout, newline=newline)

        #
        # len(args) > 2: [CMD_NAME, dev, btn1, .. ]
        #
        ret = json.dumps({'rc': IrSendCmd.RC_OK})
        for b in args[2:]:
            ret1 = super().send_recv(args[:2] + [b],
                                     timeout=timeout, newline=newline)
            self._logger.debug('ret1=%a', ret1)
            try:
                if json.loads(ret1)['rc'] != IrSendCmd.RC_OK:
                    ret = ret1
                    self._logger.debug('ret1=%s', ret1)
            except Exception as e:
                self._logger.warning('ret1=%a, %s: %s', ret1, type(e), e)

        return ret

    def reply2str(self, rep_str):
        self._logger.debug('rep_str=%a', rep_str)

        rep = rep_str.split('\r\n')
        self._logger.debug('rep=%a', rep)

        ret = json.loads(rep[0])
        self._logger.debug('ret=%a', ret)

        if type(ret) != dict:
            self._logger.warning('invalid reply foramt')
            return ret

        if 'rc' not in ret:
            self._logger.warning('invalid reply foramt')
            ret_str = json.dumps(ret, indent=2, ensure_ascii=False)
            return ret_str

        rc = ret['rc']

        if 'msg' not in ret:
            # only rc
            return rc

        msg = ret['msg']

        if type(msg) == str:
            return '%s: %s' % (rc, msg)

        if type(msg) == list:
            # device list
            out_str = ''
            for d in msg:
                out_str += str(d) + '\n'
            return out_str.strip()

        # button list
        out_str = ''
        if 'macro' in msg:
            out_str += '* macro\n'
            for m in msg['macro']:
                out_str += '%s: %s\n' % (m, msg['macro'][m])

        if 'buttons' in msg:
            out_str += '* button\n'
            for b in msg['buttons']:
                out_str += '%s: %s\n' % (b, msg['buttons'][b])

        return out_str.strip()


import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='IrSendCmdClient')
@click.argument('args', type=str, nargs=-1)
@click.option('--svrhost', '-s', 'svrhost', type=str,
              default=IrSendCmdClient.DEF_SVR_HOST,
              help='server hostname')
@click.option('--svrport', '--port', '-p', 'svrport', type=int,
              default=IrSendCmdClient.DEF_SVR_PORT,
              help='server port nubmer')
@click.option('--timeout', '-t', 'timeout', type=float,
              default=TcpCmdClient.DEF_TIMEOUT,
              help='timeout sec(float)')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(args, svrhost, svrport, timeout, debug):
    logger = get_logger(__name__, debug)
    logger.debug('args=%s, svrhost=%s, svrport=%d, timeout=%s',
                 args, svrhost, svrport, timeout)

    app = TcpCmdClientApp(IrSendCmdClient, args, svrhost, svrport, timeout,
                          debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
