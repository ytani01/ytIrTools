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
    DEF_TIMEOUT = 2.5  # sec

    EOF = b'\04'

    def __init__(self, host, port, timeout=DEF_TIMEOUT, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('host=%s, port=%s, timeout=%.1f',
                           host, port, timeout)

        self._svr_host = host
        self._svr_port = port
        self._timeout = timeout

    def end(self):
        self._logger.debug('')

    def send_recv(self, cmd_text, timeout=None):
        self._logger.debug('cmd_text=%a, timeout=%s', cmd_text, timeout)

        if timeout is None:
            timeout = self._timeout
            self._logger.debug('timeout=%s', timeout)

        with telnetlib.Telnet(self._svr_host, self._svr_port) as tn:
            try:
                out_data = cmd_text.encode('utf-8')
            except UnicodeDecodeError as e:
                rep_str = '%s, %s' % (type(e), e)
                self._logger.error(rep_str)
                return rep_str
            else:
                self._logger.debug('out_data=%a', out_data)

            tn.write(out_data)

            rep = b''
            while True:
                in_data = b''
                try:
                    in_data = tn.read_until(self.EOF, timeout=timeout)
                    self._logger.debug('in_data=%a', in_data)
                except Exception as e:
                    self._logger.warning('%s: %s.', type(e), e)
                    break

                if in_data == b'':
                    break

                rep += in_data
                self._logger.debug('rep=%a', rep)
                if self.EOF in rep:
                    self._logger.debug('EOF')
                    rep = rep[:-1]
                    break

        rep_str = rep.decode('utf-8').strip()
        self._logger.debug('rep_str=%a', rep_str)
        return rep_str


class App:
    def __init__(self, cmd_text, host, port, timeout, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('cmd_text=%s, host=%s, port=%d',
                           cmd_text, host, port)

        self._cmd_text = cmd_text

        self._cl = TcpCmdClient(host, port, timeout, debug=self._debug)

    def main(self):
        self._logger.debug('')

        rep_str = self._cl.send_recv(self._cmd_text)
        self._logger.debug('rep_str=%a', rep_str)
        rep = rep_str.split('\r\n')
        self._logger.debug('rep=%a', rep)

        try:
            for r in rep:
                json_data = json.loads(r)
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
@click.argument('arg', type=str, nargs=-1)
@click.option('--svrhost', '-s', 'svrhost', type=str, default=DEF_HOST,
              help='server hostname')
@click.option('--port', '-p', 'port', type=int, default=DEF_PORT,
              help='server port nubmer')
@click.option('--timeout', '-t', 'timeout', type=float, default=2,
              help='timeout sec(float)')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(arg, svrhost, port, timeout, debug):
    logger = get_logger(__name__, debug)
    logger.debug('arg=%s, svrhost=%s, port=%d, timeout=%.1f',
                 arg, svrhost, port, timeout)

    arg_str = ' '.join(list(arg))
    logger.debug('arg_str=%s', arg_str)

    app = App(arg_str, svrhost, port, timeout, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
