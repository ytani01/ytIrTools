#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
Dyson.py

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from IrSend import App
from pathlib import Path
import MyLogger

#####
DEF_PIN = 22


class Dyson:
    SERIAL_NUM_FILE = str(Path.home()) + '/.dyson.serial'
    SERIAL_MAX      = 2
    DEV_NAME        = 'dyson_am05'

    def __init__(self, dev_name=DEV_NAME, serial_max=SERIAL_MAX, debug=False):
        self.debug = debug
        self.logger = MyLogger.get_logger(__class__.__name__, self.debug)
        self.logger.debug('')

        self.dev_name   = dev_name
        self.serial_max = serial_max
        self.logger.debug('dev_name=%s, serial_max=%d', dev_name, serial_max)

    def get_serial_num(self):
        self.logger.debug('')

        with open(self.SERIAL_NUM_FILE, 'r') as f:
            line = f.readline()
            self.logger.debug('line=%s', line)

        serial_num = int(line) + 1
        if serial_num > self.SERIAL_MAX:
            serial_num = 0
        self.logger.debug('serial_num=%d', serial_num)

        with open(self.SERIAL_NUM_FILE, 'w') as f:
            f.write(str(serial_num))

        return serial_num


#####
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS,
               help='IR signal transmitter')
@click.argument('args', type=str, nargs=-1)
@click.option('--pin', '-p', 'pin', type=int, default=DEF_PIN,
              help='pin number')
@click.option('-n', 'n', type=int, default=1)
@click.option('--interval', '-i', 'interval', type=float, default=0.0)
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(args, pin, interval, n, debug):
    logger = MyLogger.get_logger(__name__, debug)
    logger.debug('args=%s, n=%d, interval=%f, pin=%d',
                 args, n, interval, pin)

    dyson = Dyson(debug=debug)

    args2 = []
    for i in range(n):
        for a in args:
            serial_num = dyson.get_serial_num()
            args2.append(a + str(serial_num))

    args2.insert(0, Dyson.DEV_NAME)
    logger.debug('args2=%s', args2)

    app = App(args2, 1, interval, pin, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()
        logger.debug('done')


if __name__ == '__main__':
    main()
