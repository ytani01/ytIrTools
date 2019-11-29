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

    def __init__(self, host=DEF_SVR_HOST, port=DEF_SVR_PORT, debug=False):
        """
        サーバーホスト、サーバーポートのデフォルト値を変えるためだけの定義
        """
        super().__init__(host, port, debug=debug)

    def send_recv(self, args_str, timeout=TcpCmdClient.DEF_TIMEOUT, newline=False):
        self._logger.debug('args_str=%a', args_str)

        args_str = self.CMD_NAME + ' ' + args_str

        return super().send_recv(args_str)

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
               help='IrSendClient')
@click.argument('args', type=str, nargs=-1)
@click.option('--svrhost', '-s', 'svrhost', type=str,
              default=IrSendCmdClient.DEF_SVR_HOST,
              help='server hostname')
@click.option('--svrport', '--port', '-p', 'svrport', type=int,
              default=IrSendCmdClient.DEF_SVR_PORT,
              help='server port nubmer')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(args, svrhost, svrport, debug):
    logger = get_logger(__name__, debug)
    logger.debug('args=%s, svrhost=%s, svrport=%d', args, svrhost, svrport)

    app = TcpCmdClientApp(IrSendCmdClient, args, svrhost, svrport, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()