#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrSendCmdServer.py

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from TcpCmdServer import Cmd, CmdServerApp
from IrSend import IrSend

from MyLogger import get_logger


class IrSendCmd(Cmd):
    def __init__(self, gpio=IrSend.DEF_PIN, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('gpio=%a', gpio)

        # コマンド追加
        self.add_cmd('irsend', None, self.cmd_q_irsend, 'send IR signal')

        # サーバー独自の設定
        self._irsend = IrSend(gpio, load_conf=True, debug=False)

        # 最後に super()__init__()
        super().__init__(debug=self._debug)

    def cmd_q_irsend(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            ret = self._irsend.get_dev_list()
            return self.RC_OK, ret

        m_and_b = self._irsend.get_macro_and_button(args[1])
        if m_and_b is None:
            msg = '%s: no such device' % args[1]
            self._logger.error(msg)
            return self.RC_NG, msg

        if len(args) == 2:
            return self.RC_OK, m_and_b

        if args[2] not in m_and_b['buttons']:
            msg = '%s:%s: no such button' % (args[1], args[2])
            self._logger.error(msg)
            return self.RC_NG, msg

        if len(args) < 3:
            return self.RC_OK, None

        try:
            ret = self._irsend.send(args[1], args[2])
        except Exception as e:
            msg = '%s %s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg
        if not ret:
            return self.RC_NG, None
        return self.RC_OK, None


class IrSendCmdServerApp(CmdServerApp):
    def __init__(self, port, gpio, debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('port=%s, gpio=%s', port, gpio)

        # 最初に super().__init__()
        super().__init__(port, debug=self._debug)

        # super().__init__()の後
        self._cmd = IrSendCmd(gpio, debug=self._debug)


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='TCP Server Template')
@click.option('--port', '-p', 'port', type=int,
              help='port number')
@click.option('--gpio', '-g', 'gpio', type=int, default=IrSend.DEF_PIN,
              help='GPIO pin number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, gpio, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s, gpio=%s', port, gpio)

    logger.info('start')

    app = IrSendCmdServerApp(port, gpio, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.info('end')


if __name__ == '__main__':
    main()
