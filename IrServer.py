#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrServer.py

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'


from IrConfig import IrConfig
import pigpio
import threading
import queue
import time

from MyLogger import get_logger


DEF_PIN = 22


class IrSendServer(socketserver.ThreadingTCPServer):
    def __init__(self, pin, load_conf=False, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('pin=%d', pin)

    def server_bind(self):
        self._logger.debug('')


class App:
    MSG_LIST        = '__list__'
    MSG_SLEEP       = '__sleep__'
    MSG_END         = '__end__'

    def __init__(self, pin, port, debug=False):
        self.debug = debug
        self.logger = get_logger(__class__.__name__, self.debug)
        self.logger.debug('pin=%d, port=%d', pin, port)

        self._pin = pin
        self._port = port

        self._irsend = IrSend(self._pin, load_conf=True, debug=self.debug)

    def main(self):
        self.logger.debug('')

    def end(self):
        """
        終了処理
        """
        self.logger.debug('')


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='IR signal server')
@click.option('--pin', 'pin', type=int, default=DEF_PIN,
              help='GPIO pin number')
@click.option('--port', 'port', type=int, default=DEF_PORT,
              help='port number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(pin, port, debug):
    logger = get_logger(__name__, debug)
    logger.debug('pin=%d, port=%d', pin, port)

    app = App(pin, port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.debug('done')


if __name__ == '__main__':
    main()
