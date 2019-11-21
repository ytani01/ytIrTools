#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
TcpCmdClient.py

TCP client that send one string and get json string
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

import telnetlib
import json

from MyLogger import get_logger


DEF_HOST = 'localhost'
DEF_PORT = 12351


class App:
    def __init__(self, cmd_text, host, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('cmd_text=%s, host=%s, port=%d',
                           cmd_text, host, port)

        self._cmd_text = cmd_text
        self._logger.debug('_cmd_text=\'%s\'', self._cmd_text)

        self._tn = telnetlib.Telnet(host, port)

    def main(self):
        self._logger.debug('')

        if self._cmd_text == '':
            self._logger.error('no command')
            return

        self._tn.write(self._cmd_text.encode('utf-8'))

        rep = b''
        while True:
            in_data = self._tn.read_until(b'\r\n')
            self._logger.debug('in_data=%a', in_data)

            rep += in_data
            if b'\r\n' in in_data:
                break

        self._logger.debug('rep=%a', rep)

        rep_str = rep.decode('utf-8')
        json_data = json.loads(rep_str)
        json_str = json.dumps(json_data)
        self._logger.debug('json_str=%s', json_str)

        for k in json_data:
            if k == 'rc':
                continue
            print('%s: %s' % (k, json_data[k]))

    def end(self):
        self._logger.debug('')
        self._tn.close()


import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='TcpCmdClient')
@click.argument('cmd_text1', type=str)
@click.argument('cmd_text2', type=str, nargs=-1)
@click.option('--svrhost', '-s', 'svrhost', type=str, default=DEF_HOST,
              help='server hostname')
@click.option('--port', '-p', 'port', type=int, default=DEF_PORT,
              help='server port nubmer')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(cmd_text1, cmd_text2, svrhost, port, debug):
    logger = get_logger(__name__, debug)
    logger.debug('cmd_text1=%s, cmd_text2=%s, svrhost=%s, port=%d',
                 cmd_text1, cmd_text2, svrhost, port)

    cmd_text = ' '.join([cmd_text1] + list(cmd_text2))
    logger.debug('cmd_text=%s', cmd_text)

    app = App(cmd_text, svrhost, port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
