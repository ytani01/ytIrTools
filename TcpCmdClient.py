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

from TcpCmdServer import Cmd
import telnetlib
import json

from MyLogger import get_logger


class TcpCmdClient:
    DEF_SVR_HOST = 'localhost'
    DEF_SVR_PORT = Cmd.DEF_PORT

    DEF_TIMEOUT = 10  # sec

    EOF = b'\x04'
    EOL = b'\r\n'

    def __init__(self, host=DEF_SVR_HOST, port=DEF_SVR_PORT, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, self._dbg)
        self._log.debug('host=%s, port=%s', host, port)

        self._svr_host = host
        self._svr_port = port

    def end(self):
        self._log.debug('')

    def send_recv(self, args, timeout=DEF_TIMEOUT, newline=False):
        """
        override対象

        timeout=0: 返信を受信しない
        """
        self._log.debug('args=%s, timeout=%s, newline=%s',
                           args, timeout, newline)

        args_str = ' '.join(list(args))
        return self.send_recv_str(args_str, timeout=timeout, newline=newline)

    def send_recv_str(self, args_str, timeout=DEF_TIMEOUT, newline=False):
        """
        timeout=0: 送信のみ、返信を受信しない
        """
        self._log.debug('args_str=%a, timeout=%s, newline=%s',
                           args_str, timeout, newline)

        if newline:
            args_str += '\r\n'
            self._log.debug('args_str=%a', args_str)

        try:
            out_data = args_str.encode('utf-8')
        except UnicodeDecodeError as e:
            msg = '%s, %s' % (type(e), e)
            self._log.error(msg)
            return json.dumps({'rc': Cmd.RC_NG, 'msg': msg})
        else:
            self._log.debug('out_data=%a', out_data)

        # Python3.6 以降は下記の記述ができるが、互換性のためあえて使わない。
        #
        #  with telnetlib.Telnet(self._svr_host, self._svr_port) as tn:
        #
        try:
            tn = telnetlib.Telnet(self._svr_host, self._svr_port, timeout=5)
            tn.write(out_data)
        except Exception as e:
            msg = '%s, %s' % (type(e), e)
            self._log.error(msg)
            return json.dumps({'rc': Cmd.RC_NG, 'msg': msg})

        if timeout == 0:
            rep = b'{"rc": "OK", "msg": "send only"}'
        else:
            rep = b''
            while True:
                in_data = b''
                try:
                    in_data = tn.read_until(self.EOF, timeout=timeout)
                except Exception as e:
                    self._log.warning('%s:%s', type(e), e)
                    break
                else:
                    self._log.debug('in_data=%a', in_data)

                if in_data == b'':
                    break

                rep += in_data
                self._log.debug('rep=%a', rep)
                if self.EOF in rep:
                    self._log.debug('EOF')
                    rep = rep[:-1]
                    break
        tn.close()

        if len(rep) == 0:
            msg = 'timeout'
            self._log.error(msg)
            return json.dumps({'rc': Cmd.RC_NG, 'msg': msg})

        rep_str = rep.decode('utf-8').strip()
        self._log.debug('rep_str=%a', rep_str)
        return rep_str

    def reply2str(self, rep_str):
        self._log.debug('rep_str=%a', rep_str)

        rep = rep_str.split('\r\n')
        self._log.debug('rep=%a', rep)

        try:
            for r in rep:
                json_data = json.loads(r)
                json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
                return json_str

        except json.decoder.JSONDecodeError:
            return rep_str


class TcpCmdClientApp:
    def __init__(self, client_class, args, host, port,
                 timeout=TcpCmdClient.DEF_TIMEOUT, newline=False,
                 debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, self._dbg)
        self._log.debug('args=%s, host=%s, port=%d',
                           args, host, port)
        self._log.debug('timeout=%s, newline=%s', timeout, newline)

        self._args = args
        self._cl = client_class(host, port, debug=self._dbg)

        self._timeout = timeout
        self._newline = newline

    def main(self):
        self._log.debug('')

        rep_str = self._cl.send_recv(self._args, self._timeout, self._newline)
        self._log.debug('rep_str=%a', rep_str)

        print(self._cl.reply2str(rep_str))

    def end(self):
        self._log.debug('')
        self._cl.end()
        self._log.debug('done')


import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS, help="""
TcpCmdClient
""")
@click.argument('args', type=str, nargs=-1)
@click.option('--svrhost', '-s', 'svrhost', type=str,
              default=TcpCmdClient.DEF_SVR_HOST,
              help='server hostname')
@click.option('--port', '-p', 'port', type=int,
              default=TcpCmdClient.DEF_SVR_PORT,
              help='server port nubmer')
@click.option('--timeout', '-t', 'timeout', type=float,
              default=TcpCmdClient.DEF_TIMEOUT,
              help='timeout sec(float)')
@click.option('--newline', '--nl', '-n', 'newline',
              is_flag=True, default=False,
              help='append newline')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(args, svrhost, port, timeout, newline, debug):
    logger = get_logger(__name__, debug)
    logger.debug('args=%s, svrhost=%s, port=%d, timeout=%.1f, newline=%s',
                 args, svrhost, port, timeout, newline)

    app = TcpCmdClientApp(TcpCmdClient, args, svrhost, port, timeout, newline,
                          debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.debug('done')


if __name__ == '__main__':
    main()
