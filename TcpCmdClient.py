#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
TcpCmdClient.py

TCP client that send command strings and get reply string
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

import telnetlib
import json

from MyLogger import get_logger


DEF_HOST = 'localhost'
DEF_PORT = 12351


class TcpCmdClient:
    def __init__(self, host, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('host=%s, port=%s', host, port)

        self._svr_host = host
        self._svr_port = port

    def end(self):
        self._logger.debug('')

    def send_recv(self, cmd_text):
        self._logger.debug('cmd_text=%s', cmd_text)

        with telnetlib.Telnet(self._svr_host, self._svr_port) as tn:
            out_data = cmd_text.encode('utf-8')
            self._logger.debug('out_data=%a', out_data)

            tn.write(out_data)

            rep = b''
            while True:
                in_data = b''
                try:
                    in_data = tn.read_until(b'__dummy__', timeout=0.5)
                    self._logger.debug('in_data=%a', in_data)
                except Exception as e:
                    self._logger.warning('%s: %s.', type(e), e)
                    break

                if in_data == b'':
                    break

                rep += in_data
                self._logger.debug('rep=%a', rep)

        rep_str = rep.decode('utf-8').strip()
        self._logger.debug('rep_str=\'%s\'', rep_str)
        return rep_str


class App:
    def __init__(self, cmd_text, host, port, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('cmd_text=%s, host=%s, port=%d',
                           cmd_text, host, port)

        self._cmd_text = cmd_text

        self._cl = TcpCmdClient(host, port, debug=self._debug)

    def main(self):
        self._logger.debug('')

        if self._cmd_text == '':
            self._logger.error('no command')
            return

        rep_str = self._cl.send_recv(self._cmd_text)

        try:
            json_data = json.loads(rep_str)
            json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
            print(json_str)

        except json.decoder.JSONDecodeError:
            print(rep_str)

    def end(self):
        self._logger.debug('')
        self._cl.end()


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
