#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrSendClient
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from TcpCmdClient import TcpCmdClient
from IrSendServer import IrSendServer
import json

from MyLogger import get_logger


class IrSendClient(TcpCmdClient):
    DEF_SVR_HOST = 'localhost'
    DEF_SVR_PORT = IrSendServer.DEF_PORT
    
    def __init__(self, host=None, port=None, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('host=%s, port=%s', host, port)

        self._svr_host = host
        if self._svr_host is None:
            self._svr_host = self.DEF_SVR_HOST

        self._svr_port = port
        if self._svr_port is None:
            self._svr_port = self.DEF_SVR_PORT

    def send_recv(self, arg_str):
        self._logger.debug

        if arg_str == '':
            arg_str = '@list'

        rep_str = super().send_recv(arg_str)

        try:
            rep_json = json.loads(rep_str)
        except json.decoder.JSONDecodeError:
            self._logger.warning('invalid json format')
            return rep_str

        return rep_json

class App:
    def __init__(self, arg, host, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('arg=%s, host=%s, port=%d', arg, host, port)

        self._arg_str = ' '.join(list(arg))
        self._logger.debug('_arg_str=%a', self._arg_str)

        self._cl = IrSendClient(host, port, debug=self._debug)

    def main(self):
        self._logger.debug('')

        ret = self._cl.send_recv(self._arg_str)
        self._logger.debug('ret=%s', ret)

        if type(ret) != dict:
            self._logger.warning('invalid reply foramt')
            print(ret)
            return
        
        if 'rc' not in ret:
            self._logger.warning('invalid reply foramt')
            ret_str = json.dumps(ret, indent=2, ensure_ascii=False)
            print(ret_str)
            return

        rc = ret['rc']

        if 'data' not in ret:
            # only rc
            print(rc)
            return

        data = ret['data']

        if type(data) == str:
            # error message
            print(data)
            return
        
        if type(data) == list:
            # device list
            for d in data:
                print(d)
            return

        # button list
        if 'macro' in data:
            print('* macro')
            for m in data['macro']:
                print('%s: %s' % (m, data['macro'][m]))

        if 'buttons' in data:
            print('* button')
            for b in data['buttons']:
                print('%s: %s' % (b, data['buttons'][b]))

    def end(self):
        self._logger.debug('')
        self._cl.end()


import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='IrSendClient')
@click.argument('arg', type=str, nargs=-1)
@click.option('--svrhost', '-s', 'svrhost', type=str,
              default=IrSendClient.DEF_SVR_HOST,
              help='server hostname')
@click.option('--port', '-p', 'port', type=int,
              default=IrSendClient.DEF_SVR_PORT,
              help='server port nubmer')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(arg, svrhost, port, debug):
    logger = get_logger(__name__, debug)
    logger.debug('arg=%s, svrhost=%s, port=%d', arg, svrhost, port)

    app = App(arg, svrhost, port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
