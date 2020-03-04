#!/usr/bin/env python3
#
# (c) 2020 Yoichi Tanibayashi
#
"""
WebSocket Server
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2020'

from IrSendCmdClient import IrSendCmdClient
from websocket_server import WebsocketServer
import click
from MyLogger import get_logger


class IrWsServer():
    DEF_PORT = 9001

    def __init__(self, port=DEF_PORT, host="0.0.0.0",
                 svrhost='localhost', svrport=51001,
                 debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, self._dbg)
        self._log.debug('host=%s, port=%s', host, port)
        self._log.debug('svrhost=%s, svrport=%s', svrhost, svrport)

        self.irsvr = IrSendCmdClient(svrhost, svrport, debug=self._dbg)
        self.server = WebsocketServer(port, host=host)

    def new_client(self, client, server):
        self._log.debug('client=%s', client)

    def client_left(self, client, server):
        self._log.debug('client=%s', client)
        self.irsvr.end()

    def message_received(self, client, server, msg):
        self._log.debug('client=%s, msg=%s', client, msg)
        self.msg = msg.encode('utf-8')
        self._log.info('msg=%s.', msg)
        self.irsvr.send_recv(msg.split())

    def run(self):
        self._log.debug('')
        self.server.set_fn_new_client(self.new_client)
        self.server.set_fn_client_left(self.client_left)
        self.server.set_fn_message_received(self.message_received)
        self.server.run_forever()


class App:
    def __init__(self, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, self._dbg)
        self._log.debug('')

        self.ws_svr = IrWsServer(9001, debug=self._dbg)

    def main(self):
        self._log.debug('')
        self.ws_svr.run()

    def end(self):
        self._log.debug('')


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS, help='''
WebSocket Server
''')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(debug):
    _log = get_logger(__name__, debug)
    _log.debug('')

    app = App(debug=debug)
    try:
        app.main()
    finally:
        app.end()


if __name__ == '__main__':
    main()
