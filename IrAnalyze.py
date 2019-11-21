#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrAnalyze.py
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

from IrConfig import IrConfig
import json
from MyLogger import get_logger


class IrAnalyze:
    """
    raw_data = [[pulse1, space1], [pulse2, space2], ... ]
    """
    RAW_DATA_LEN_MIN = 6

    SIG_LONG = 99999   # usec
    SIG_END  = 999999  # usec

    SIG_SYM = {
        'leader':  '-',
        'leader?': '=',
        'zero':    '0',
        'one':     '1',
        'trailer': '/',
        'repeat':  '*',
        'unknown': '?'
    }
    SIG_STR_01 = SIG_SYM['zero'] + SIG_SYM['one']

    def __init__(self, raw_data=[], debug=False):
        """
        Parameters
        ----------
        raw_data: list
          [[pulse1, space1], [pulse2, space2], ..]

        """
        self.debug = debug
        self.logger = get_logger(__class__.__name__, self.debug)
        self.logger.debug('raw_data=%s', raw_data)

        self.result   = None
        self.raw_data = raw_data

    def fq_dist(self, data, step=0.2):
        """
        度数分布作成

        Parameters
        ----------
        data: list
        step: float

        """
        self.logger.debug('data=%s, step=%.1f', data, step)

        fq_list = [[]]
        for val in sorted(data):
            if len(fq_list[-1]) > 0:
                if step < 1:
                    # 比率
                    next_step = fq_list[-1][-1] * (1 + step)
                else:
                    # 差
                    next_step = fq_list[-1][-1] + step
                if val >= next_step:
                    fq_list.append([])
            fq_list[-1].append(val)
        return fq_list

    def analyze(self, raw_data=[]):
        """
        pulse, sleepには、誤差があるが、
        一組の (pulse + sleep) は、ほぼ正確と仮定。

        真のパルス, スリープ時間を t_p, t_s、誤差 tdとしたとき、
          pulse + sleep = t_p + t_s
          pulse = t_p + td
          sleep = t_s - td

        Parameters
        ----------
        raw_data: list
          [[pulse1, space1], [pulse1, space1], .. ]

        Returns
        -------
        self.result: dict
        {
          'comment': 'generated by ..',
          'dev_name: 'dev1',
          'T': self.T,
          'sym_tbl': {
            '-': [[p_l1, s_l1]],
            :
          },
          'macro': {
            '[prefix]': '',
            '[suffix]': ''
          },
          'buttons': {
            'button1': self.sig_str2
          }
        }
        """
        self.logger.debug('raw_data=%s', raw_data)

        if raw_data != []:
            self.raw_data = raw_data
            self.logger.debug('raw_data=%s', self.raw_data)

        if len(raw_data) < self.RAW_DATA_LEN_MIN:
            self.logger.warning('too short:%s .. ignored',
                                raw_data)
            return None

        # pulse + sleep の値のリスト
        self.sum_list = [(d1 + d2) for d1, d2 in self.raw_data]
        self.logger.debug('sum_list=%s', self.sum_list)

        # self.sum_listの度数分布
        self.fq_list = self.fq_dist(self.sum_list, 0.2)
        self.logger.debug('fq_list=%s', self.fq_list)

        # 単位時間<T> = 度数分布で一番小さいグループの平均の半分
        self.T = (sum(self.fq_list[0]) / len(self.fq_list[0])) / 2
        self.logger.debug('T=%.2f[us]', self.T)

        # 誤差 td を求める
        self.T1 = {'pulse': [], 'space': []}
        for i, s in enumerate(self.sum_list):
            if self.sum_list[i] in self.fq_list[0]:
                self.T1['pulse'].append(self.raw_data[i][0])
                self.T1['space'].append(self.raw_data[i][1])
        self.T1_ave = {'pulse': [], 'space': []}
        # (pulse,spaceのTdの平均値を求めているが、pulseだけでも十分?)
        for key in ['pulse', 'space']:
            self.T1_ave[key] = sum(self.T1[key]) / len(self.T1[key])
        self.Td_p = abs(self.T1_ave['pulse'] - self.T)
        self.Td_s = abs(self.T1_ave['space'] - self.T)
        self.Td = (self.Td_p + self.Td_s) / 2
        self.logger.debug('Td=%.2f, Td_p=%.2f, Td_s=%.2f',
                          self.Td, self.Td_p, self.Td_s)

        # self.raw_dataのそれぞれの値(Tdで補正)が、self.Tの何倍か求める
        self.n_list_float = []  # for debug
        self.n_list = []
        for p, s in self.raw_data:
            n_p = (p - self.Td) / self.T
            n_s = (s + self.Td) / self.T
            self.n_list_float.append([n_p, n_s])
            n_p = round(n_p)
            n_s = round(n_s)
            self.n_list.append([n_p, n_s])
        self.logger.debug('n_list_float=%s', self.n_list_float)
        self.logger.debug('n_list=%s', self.n_list)

        # 信号パターン抽出
        self.n_pattern = sorted(list(map(list, set(map(tuple, self.n_list)))))
        self.logger.debug('n_pattern=%s', self.n_pattern)

        # 信号パターンの解析
        # 信号フォーマットの特定
        self.sig_format  = []   # 確定
        self.sig_format2 = []   # 未確定(推定)
        self.sig2n = {'leader':  [],
                      'leader?': [],
                      'zero':    [],
                      'one':     [],
                      'trailer': [],
                      'repeat':  [],
                      'unknown': []}
        for i, [n1, n2] in enumerate(self.n_pattern):
            p = [n1, n2]
            # zero
            if p == [1, 1]:
                self.sig2n['zero'].append(p)
                continue
            # one
            if p == [2, 1]:
                self.sig2n['one'].append(p)
                self.sig_format.append('SONY')
                continue
            if p in [[1, 3], [1, 4]]:
                self.sig2n['one'].append(p)
                self.sig_format2.append('NEC?')
                self.sig_format2.append('AEHA?')
                self.sig_format2.append('BOSE?')
                continue
            # leader
            if p == [4, 1]:
                self.sig2n['leader'].append(p)
                self.sig_format.append('SONY')
                continue
            if n1 in [7, 8, 9] and n2 in [3, 4, 5]:
                self.sig2n['leader'].append(p)
                self.sig_format.append('AEHA')
                continue
            if n1 in [15, 16, 17] and n2 in [7, 8, 9]:
                self.sig2n['leader'].append(p)
                self.sig_format.append('NEC')
                continue
            if p == [3, 1]:
                self.sig2n['leader?'].append(p)
                self.sig_format.append('DYSON')
                continue
            if p == [2, 3]:
                self.sig2n['leader?'].append(p)
                self.sig_format.append('BOSE')
                continue
            # repeat
            if n1 in [15, 16, 17] and n2 in [3, 4, 5]:
                self.sig2n['repeat'].append(p)
                self.sig_format.append('NEC')
                continue
            if n1 in [7, 8, 9] and n2 in [7, 8, 9]:
                self.sig2n['repeat'].append(p)
                self.sig_format.append('AEHA')
                continue
            # trailer
            if n1 in [1, 2] and n2 > 10:
                self.sig2n['trailer'].append(p)
                if n1 == 2:
                    self.sig_format2.append('SONY?')
                continue
            # ???
            if len(self.sig2n['one']) == 0 and \
               ((n1 == 1 and n2 > 1) or (n1 > 1 and n2 == 1)):
                self.sig2n['one'].append(p)
                continue
            if n1 == self.n_list[0][0] and n2 == self.n_list[0][1]:
                self.sig2n['leader?'].append(p)
                continue
            # 判断できない
            self.sig2n['unknown'].append(p)

        # self.sig2nの['key']と['key?']の整理
        for key in self.sig2n.keys():
            if key[-1] == '?':
                continue
            if key + '?' in self.sig2n.keys():
                if len(self.sig2n[key]) == 0:
                    self.sig2n[key] = self.sig2n[key + '?'][:]
                for sig in self.sig2n[key]:
                    if sig in self.sig2n[key + '?']:
                        self.sig2n[key + '?'].remove(sig)
        self.logger.debug('sig2n=%s', self.sig2n)

        self.ch2sig = {}
        for key in self.SIG_SYM.keys():
            self.ch2sig[self.SIG_SYM[key]] = self.sig2n[key]
        self.logger.debug('ch2sig=%s', self.ch2sig)

        # 信号フォーマットのリスト<sig_format>から、
        # 文字列<sig_format_str>を生成
        self.sig_format_str = ''
        if len(self.sig_format) > 0:
            self.sig_format = list(set(self.sig_format))
            for f in self.sig_format:
                self.sig_format_str += f + ' '
        elif len(self.sig_format2) > 0:
            self.sig_format2 = list(set(self.sig_format2))
            for f in self.sig_format2:
                self.sig_format_str += f + ' '
        else:
            self.sig_format_str = '??? '
        self.sig_format_str = self.sig_format_str.strip()

        self.logger.debug('sig_format=%s', self.sig_format)
        self.logger.debug('sig_format2=%s', self.sig_format2)

        # 信号リストを生成
        self.sig_list = []
        for n1, n2 in self.n_list:
            for key in self.sig2n.keys():
                if [n1, n2] in self.sig2n[key]:
                    self.sig_list.append(key)
        self.logger.debug('sig_list=%s', self.sig_list)

        # 信号リストを文字列に変換
        self.sig_str = ''
        for i, sig in enumerate(self.sig_list):
            ch = self.SIG_SYM[sig]
            self.sig_str += ch
        self.logger.debug('sig_str=\'%s\'', self.sig_str)

        # 信号文字列の中をさらに分割(' 'を挿入)
        # 0,1の部分は分割しない
        self.sig_line = []
        for key in self.SIG_SYM.keys():
            if self.SIG_SYM[key] in self.SIG_STR_01:
                continue
            self.sig_str = self.sig_str.replace(self.SIG_SYM[key],
                                                ' ' + self.SIG_SYM[key] + ' ')
        self.sig_line = self.sig_str.split()
        self.logger.debug('sig_line=%s', self.sig_line)

        # 2進数の桁数が偶数場合は16進数に変換
        # 2進数のままの場合は、先頭に IrConfix.HEADER_BIN を付加する
        self.sig_line1 = []
        for sig in self.sig_line:
            if sig[0] in self.SIG_STR_01:
                if len(sig) % 2 == 0:
                    # bin_str -> hex_str
                    fmt = '0' + str(int(len(sig) / 4)) + 'X'
                    sig = format(int(sig, 2), fmt)

                    self.sig_line1.append(sig)
                else:
                    self.sig_line1.append(IrConfig.HEADER_BIN + sig)
            else:
                self.sig_line1.append(sig)
        self.logger.debug('sig_line1=%s', self.sig_line1)

        # 再び一つの文字列として連結
        self.sig_str2 = ''
        for s in self.sig_line1:
            self.sig_str2 += s
        self.logger.debug('sig_str2=%s', self.sig_str2)

        # 同じ信号が繰り返されている場合は、下記のようなリストを作成
        #   [ '信号文字列', n ]
        sig_repeat = []
        s_list = self.sig_str2.split('-')
        s_list.pop(0)
        repeat_n = 0
        for s in s_list:
            if s == s_list[0]:
                repeat_n += 1
        if repeat_n > 1 and repeat_n == len(s_list):
            # 繰り返し
            sig_repeat = ['-' + s_list[0], repeat_n]
            self.logger.debug('sig_repeat=%s', sig_repeat)

        # T.B.D.
        # エラーチェックなど

        # 結果のまとめ
        self.sig_format_result = ''
        if len(self.sig_format) == 0:
            if len(self.sig_format2) == 0:
                self.sig_format_result = '?'

            elif len(self.sig_format2) == 1:
                self.sig_format_result = self.sig_format2[0]

            else:
                self.sig_format_result = self.sig_format2

        elif len(self.sig_format) == 1:
            self.sig_format_result = self.sig_format[0]

        else:
            self.sig_format_result = self.sig_format

        self.result = {
            'comment': 'generated by ' + __class__.__name__,
            'dev_name': ['dev1'],
            'format':   self.sig_format_result,
            'T':        self.T,       # us
            'sym_tbl':  self.ch2sig,
            'macro': {
                '[prefix]': '',
                '[suffix]': ''
            },
            'buttons': {
                'button1': self.sig_str2
            }
        }
        if len(sig_repeat) == 2:
            self.result['buttons']['button1'] = sig_repeat

        return self.result

    def json_dumps(self, dev_list=None):
        """
        デバイスデータ(JSON形式、リスト)を見やすく整形し、文字列を返す
        (全体を json.dumps() すると見にくい)

        ``dev_list``が省略された場合は、
        最後に解析した結果 ``self.result``を整形する。

        Parameters
        ----------
        dev_list: json list

        Returns
        -------
        json_str: str

        """
        self.logger.debug('dev_list=%s', dev_list)

        if dev_list is None:
            if self.result is None:
                self.logger.waring('no result')
                return ''

            dev_list = [self.result]
            self.logger.debug('dev_list=%s', dev_list)

        if type(dev_list) != list:
            dev_list = [dev_list]

        if dev_list == []:
            self.logger.waring('no data')
            return ''

        json_str = '[\n'
        for dev_data in dev_list:
            json_str += '''{
  "comment": %s,
  "dev_name": %s,
  "format":   %s,
  "T":        %f,
  "sym_tbl": {
    "-":      %s,
    "=":      %s,
    "0":      %s,
    "1":      %s,
    "/":      %s,
    "*":      %s,
    "?":      %s
  },
  "macro": {
    "[prefix]": "",
    "[suffix]": "",
    "[end of macro]": ""
  },
  "buttons": {
    "button1": %s,
    "end of buttons": ""
  }
}
,
''' % (json.dumps(dev_data['comment']),
       json.dumps(dev_data['dev_name']),
       json.dumps(dev_data['format']),
       dev_data['T'],
       dev_data['sym_tbl']['-'],
       dev_data['sym_tbl']['='],
       dev_data['sym_tbl']['0'],
       dev_data['sym_tbl']['1'],
       dev_data['sym_tbl']['/'],
       dev_data['sym_tbl']['*'],
       dev_data['sym_tbl']['?'],
       json.dumps(dev_data['buttons']['button1']))

        json_str = json_str[:-2] + ']\n'

        self.logger.debug('json_str=\'%s\'', json_str)
        return json_str


#####
import threading
import queue
import os


class App:
    """
    IrAnalyzeクラスを使った実例
    """
    PULSE_SPACE_FILE = '/tmp/pulse_space.txt'
    JSON_DUMP_FILE   = '/tmp/ir_dump.irconf'

    MSG_END = ''

    def __init__(self, pin, n=0, verbose=False, debug=False):
        self.debug = debug
        self.logger = get_logger(__class__.__name__, debug)
        self.logger.debug('pin=%d, n=%d, verbose=%s', pin, n, verbose)

        self.pin     = pin
        self.n       = n
        self.verbose = verbose

        self.analyzer = IrAnalyze(debug=self.debug)
        self.receiver = IrRecv(self.pin, verbose=self.verbose,
                               debug=self.debug)

        self.msgq      = queue.Queue()
        self.th_worker = threading.Thread(target=self.worker)
        self.th_worker.start()

        self.serial_num = 0

    def worker(self):
        """
        サブスレッド

        メッセージキューから``raw_data``を取出し、
        信号解析する。

        raw_data: [[pulse1, space1], [pulse2, space2], ..]
        """
        self.logger.debug('')

        while True:
            raw_data = self.msgq.get()
            self.logger.debug('raw_data=%s', raw_data)
            if raw_data == self.MSG_END:
                break

            with open(self.PULSE_SPACE_FILE, 'w') as f:
                f.write('# generated by %s\n' % os.path.basename(__file__))
                for [p, s] in raw_data:
                    f.write('pulse %d\n' % p)
                    f.write('space %d\n' % s)

            result = self.analyzer.analyze(raw_data)
            self.logger.debug('result=%s', result)
            if result is None:
                print('invalid signal .. ignored')
            else:
                self.serial_num += 1
                dev_name1 = 'dev_' + str(self.serial_num)
                dev_name2 = 'dev_' + ('%06d' % self.serial_num)
                result['dev_name'] = [dev_name1, dev_name2]
                json_str = json.dumps(result['buttons']['button1'])
                if self.n > 1:
                    print('[%d/%d],' % (self.serial_num, self.n), end='')
                print('%s,%s,T=%d,%s' % (dev_name1, result['format'],
                                         round(result['T']), json_str))

                if self.serial_num == 1:
                    dump_data = [result]
                else:
                    with open(self.JSON_DUMP_FILE, 'r') as f:
                        dump_data = json.load(f)
                    dump_data.append(result)

                json_str = self.analyzer.json_dumps(dump_data)
                self.logger.debug('json_str=%s', json_str)

                with open(self.JSON_DUMP_FILE, 'w') as f:
                    f.write(json_str)

                if len(result['sym_tbl']['?']) > 0:
                    print('\'?\': %s .. try again' %
                          result['sym_tbl']['?'])
                    continue
                if len(result['sym_tbl']['=']) > 0:
                    print('\'=\' in \'%s\' .. try again' %
                          result['sym_tbl']['='])
                    continue

                if self.n > 0 and self.serial_num == self.n:
                    self.logger.debug('serial_num=%d', self.serial_num)
                    break

        self.logger.debug('done')

    def main(self):
        """
        メインスレッド

        赤外線信号を受信し、
        メッセージをキューに格納すると、
        ただちに次の信号を受信する。

        実際の解析は <worker>スレッドに任せる。
        """
        self.logger.debug('')

        count = 0
        while True:
            raw_data = self.receiver.recv()
            self.logger.debug('raw_data=%s', raw_data)
            self.msgq.put(raw_data)

            count += 1
            if self.n > 0 and count == self.n:
                self.logger.debug('count=%d/%d', count, self.n)
                break

    def end(self):
        self.logger.debug('')

        if self.th_worker.is_alive():
            self.msgq.put(self.MSG_END)
            self.logger.debug('join()')
            self.th_worker.join()

        self.receiver.end()
        self.logger.debug('done')


#
# main
#
from IrRecv import IrRecv
DEF_PIN = 27

import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS,
               help='IR signal analyzer')
@click.argument('pin', type=int, default=DEF_PIN)
@click.option('-n', 'n', type=int, default=0,
              help='number of signal to anlyze')
@click.option('--verbose', '-v', 'verbose', is_flag=True, default=False,
              help='verbose mode')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(pin, n, verbose, debug):
    logger = get_logger(__name__, debug)
    logger.debug('pin=%d, n=%d', pin, n)

    app = App(pin, n, verbose, debug=debug)
    try:
        app.main()
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
