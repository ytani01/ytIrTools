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
import time

from MyLogger import get_logger


class IrSendCmd(Cmd):
    """
    赤外線リモコン信号送信コマンドの定義
    """
    DEF_PORT = 51001

    CMD_NAME = 'irsend'

    SUBCMD = {'LOAD': '@load'}

    def __init__(self, init_param=(IrSend.DEF_PIN,), port=DEF_PORT,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('init_param=%s, port=%s', init_param, port)

        # コマンド追加
        self.add_cmd(self.CMD_NAME, None, self.cmd_q_irsend, 'send IR signal')

        # サーバー独自の設定
        gpio = init_param[0]
        self._irsend = IrSend(gpio, load_conf=True, debug=False)

        # 最後に super()__init__()
        super().__init__(port=port, debug=self._debug)

    def cmd_q_irsend(self, args):
        """
        args[0]: self.CMD_NAME

        引数無し: デバイス一覧

        引数1個
          "@load":    設定ファイル再読込
          デバイス名: ボタン一覧

        引数2個: 赤外線リモコン信号送信

        """
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            ret = self._irsend.get_dev_list()
            return self.RC_OK, ret

        #
        # len(args) >= 2
        #
        if args[1].startswith('@'):
            if args[1] == self.SUBCMD['LOAD']:
                msg = self._irsend.reload_conf()
                if msg != self._irsend.MSG_OK:
                    self._logger.error(msg)
                    return self.RC_NG, msg
                return self.RC_OK, 'reload config data'
            else:
                return self.RC_NG, '%s: no such command' % args[1]

        m_and_b = self._irsend.get_macro_and_button(args[1])
        if m_and_b is None:
            msg = '%s: no such device' % args[1]
            self._logger.error(msg)
            return self.RC_NG, msg

        if len(args) == 2:
            return self.RC_OK, m_and_b

        #
        # len(args) >= 3
        #
        if args[2].startswith('@'):
            # interval
            try:
                interval = float(args[2][1:])
            except Exception as e:
                msg = '%s:%s' % (type(e), e)
                self._logger.error(msg)
                return self.RC_NG, msg
            self._logger.debug('interval=%s', interval)
            time.sleep(interval)
            return self.RC_OK, 'sleep %s sec' % interval

        if args[2] not in m_and_b['buttons']:
            msg = '%s:%s: no such button' % (args[1], args[2])
            self._logger.error(msg)
            return self.RC_NG, msg

        try:
            ret = self._irsend.send(args[1], args[2])
        except Exception as e:
            msg = '%s %s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        if not ret:
            return self.RC_NG, None
        return self.RC_OK, None


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='TCP Server Template')
@click.option('--port', '-p', 'port', type=int,
              default=IrSendCmd.DEF_PORT,
              help='port number')
@click.option('--gpio', '-g', 'gpio', type=int, default=IrSend.DEF_PIN,
              help='GPIO pin number')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, gpio, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s, gpio=%s', port, gpio)

    logger.info('start')

    app = CmdServerApp(IrSendCmd, init_param=(gpio,), port=port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.info('end')


if __name__ == '__main__':
    main()
