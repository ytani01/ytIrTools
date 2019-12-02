#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from TcpCmdServer import Cmd, CmdServerApp

from ytBeebotte import Beebotte
from IrSendCmdClient import IrSendCmdClient

import time

from MyLogger import get_logger


class Aircon:
    DEF_DEV_NAME = 'aircon'
    DEF_BUTTON_HEADER = 'on_hot_auto_'
    DEF_IR_HOST = 'localhost'

    def __init__(self, dev=DEF_DEV_NAME, button_header=DEF_BUTTON_HEADER,
                 ir_host=DEF_IR_HOST,
                 debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('dev=%s, button_header=%s, ir_host=%s',
                           dev, button_header, ir_host)

        self._dev = dev
        self._button_header = button_header
        self._rtemp = 0

        self._irsend = IrSendCmdClient(ir_host, debug=self._debug)

    def set_temp(self, rtemp, force=False):
        self._logger.debug('rtemp=%s', rtemp)

        if not force:
            if rtemp == self._rtemp:
                self._logger.debug('rtemp==_rtemp=%s', self._rtemp)
                return

        button = self._button_header + '%02d' % rtemp
        if rtemp == 0:
            button = 'off'
        self._logger.debug('button=%s', button)

        args = [self._dev, button]

        try:
            ret = self._irsend.send_recv(args)
        except Exception as e:
            self._logger.error('%s:%s', type(e), e)
        else:
            self._logger.info('%s:%s', args, self._irsend.reply2str(ret))


class AutoAirconCmd(Cmd):
    """
    """
    DEF_PORT = 12359
    DEF_TTEMP = 26
    TEMP_TOPIC = 'env1/temp'
    TEMP_END = 0

    def __init__(self, init_param=(TEMP_TOPIC,
                                   Aircon.DEF_DEV_NAME,
                                   Aircon.DEF_BUTTON_HEADER,
                                   Aircon.DEF_IR_HOST), debug=False):
        self._debug = debug
        self._logger = get_logger(__class__.__name__, self._debug)
        self._logger.debug('init_param=%s', init_param)

        # コマンド追加
        self.add_cmd('temp', None, self.cmd_q_temp, 'get current temp')
        self.add_cmd('rtemp', None, self.cmd_q_rtemp,
                     'get and set target temp')
        self.add_cmd('ttemp', None, self.cmd_q_ttemp,
                     'get and set remocon temp')

        # サーバー独自の設定
        self._temp_topic = init_param[0]
        self._bbt = Beebotte(self._temp_topic, debug=False)

        self._aircon = Aircon(init_param[1], init_param[2], init_param[3],
                              debug=self._debug)

        self._ts = None
        self._temp = None

        self._ttemp = self.DEF_TTEMP
        self._rtemp = round(self._ttemp)

        # 最後に super()__init__()
        super().__init__(debug=self._debug)

    def main(self):
        self._logger.debug('')

        self._bbt.start()
        self._bbt.subscribe()

        while self._active:
            msg_type, msg_data = self._bbt.wait_msg(self._bbt.MSG_DATA)
            self._logger.debug('%s, %s', msg_type, msg_data)

            if msg_type != self._bbt.MSG_DATA:
                continue

            payload = msg_data['payload']
            self._ts = payload['ts'] / 1000  # msec -> sec
            self._temp = float(payload['data'])
            self._logger.debug('_ts=%s, _temp=%s', self._ts, self._temp)
            if self._temp == self.TEMP_END:
                self._logger.info('_temp=%s .. shutdown', self._temp)
                break

        self._logger.debug('done')

    def end(self):
        self._logger.debug('')
        self._bbt.end()
        super().end()
        self._logger.debug('done')

    def stop_main(self):
        self._logger.debug('')
        self._bbt.publish(self._temp_topic, self.TEMP_END)
        super().stop_main()
        self._logger.debug('done')

    def cmd_q_temp(self, args):
        self._logger.debug('args=%a', args)

        if self._temp is None:
            return self.RC_NG, 'no temp data'

        return self.RC_OK, self._temp

    def cmd_q_ttemp(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            return self.RC_OK, self._ttemp

        try:
            self._ttemp = float(args[1])
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        return self.RC_OK, self._ttemp

    def cmd_q_rtemp(self, args):
        self._logger.debug('args=%a', args)

        if len(args) == 1:
            return self.RC_OK, self._rtemp

        try:
            self._rtemp = round(float(args[1]))
        except Exception as e:
            msg = '%s:%s' % (type(e), e)
            self._logger.error(msg)
            return self.RC_NG, msg

        self._aircon.set_temp(self._rtemp)

        return self.RC_OK, self._rtemp


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='TCP Server Template')
@click.option('--port', '-p', 'port', type=int,
              default=AutoAirconCmd.DEF_PORT,
              help='port number')
@click.option('--temp_topic', '-t', 'temp_topic', default='env1/temp',
              help='topic name of temperature')
@click.option('--aircon_dev', '-d', 'aircon_dev', default=Aircon.DEF_DEV_NAME,
              help='aircon device name')
@click.option('--aircon_button_header', '-b', 'aircon_button_header',
              default=Aircon.DEF_BUTTON_HEADER,
              help='aircon button header strings')
@click.option('--ir_host', '-h', 'ir_host', default=Aircon.DEF_IR_HOST,
              help='IR send server host name')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(port, temp_topic, aircon_dev, aircon_button_header, ir_host, debug):
    logger = get_logger(__name__, debug)
    logger.debug('port=%s, temp_topic=%s', port, temp_topic)
    logger.debug('aircon_dev=%s, aircon_button_header=%s, ir_host=%s',
                 aircon_dev, aircon_button_header, ir_host)

    logger.info('start')

    app = CmdServerApp(AutoAirconCmd,
                       init_param=(temp_topic,
                                   aircon_dev, aircon_button_header, ir_host),
                       port=port, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.info('end')


if __name__ == '__main__':
    main()
