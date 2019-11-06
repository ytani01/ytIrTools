#!/usr/bin/env python3
#
"""
for irdb raw mode
(http://irdb.tk/codes/)

"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from IrAnalyze import IrAnalyze
from MyLogger import get_logger


#####
class App:
    def __init__(self, file, debug=False):
        self.debug = debug
        self.logger = get_logger(__class__.__name__, self.debug)
        self.logger.debug('file=%s', file)

        self.file = file

        self.an = IrAnalyze(debug=self.debug)

    def main(self):
        self.logger.debug('')

        with open(self.file, 'r') as f:
            line = f.readlines()
        print(line)

        raw_data = []
        i = 0
        for li in line:
            for w in li.split():
                if i % 2 == 0:
                    raw_data.append([int(w)])
                else:
                    raw_data[-1].append(-int(w))
                self.logger.debug('raw_data=%s', raw_data)
                i += 1
        self.logger.debug('raw_data=%s', raw_data)

        result = self.an.analyze(raw_data)
        self.logger.debug('result=%s', result)

        print(self.an.json_dumps(result))

    def end(self):
        self.logger.debug('')


#####
import click


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS,
               help='irdb raw format analyzer')
@click.argument('file')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(file, debug):
    logger = get_logger(__name__, debug)
    logger.debug('file=%s', file)

    app = App(file, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
