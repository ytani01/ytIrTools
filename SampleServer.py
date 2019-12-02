#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from TcpCmdServer import Cmd, CmdServerApp
import time

from MyLogger import get_logger


class SampleCmd(Cmd):
    """
    """
    DEF_PORT = 12399

    CMD_NAME = ['aaa', 'bbb']

    def __init__(self, init_param=(0,), debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('init_param=%s', init_param)

        # コマンド追加
        self.add_cmd(self.CMD_NAME[0], None, self.cmd_q_aaa, 'aaa')
        self.add_cmd(self.CMD_NAME[1], None, self.cmd_q_bbb, 'aaa')

        # サーバー独自の設定
        self._count = init_param[0]

        # 最後に super()__init__()
        super().__init__(debug=self._debug)

    def cmd_q_aaa(self, args):
        self._logger.debug('args=%a', args)

        return self.RC_OK, self._count

    def cmd_q_bbb(self, args):
        self._logger.debug('args=%a', args)

        if len(args) < 2:
            return self.RC_NG, "error"
        
        ret = self._count * float(args[1])
        
        return self.RC_OK, ret

    def main(self):
        self._logger.debug('')

        while self._active:
            print(self._count)
            self._count += 1
            time.sleep(1)

        self._logger.debug('done')


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='TCP Server Template')
@click.option('--port', '-p', 'port', type=int,
              default=SampleCmd.DEF_PORT,
              help='port number')
@click.option('--count', '-c', 'count', type=int, default=0,
              help='count')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, count, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s, count=%s', port, count)

    logger.info('start')

    app = CmdServerApp(SampleCmd, init_param=(count,), port=port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.info('end')


if __name__ == '__main__':
    main()
