#!/usr/bin/env python3
#
# (c) 2019 Yoichi Tanibayashi
#
"""
IrConfig.py
"""
__author__ = 'Yoichi Tanibayashi'
__date__   = '2019'

import json
from pathlib import Path
import MyLogger


#####
class IrConfig:
    """
    設定情報関連

    読み込んだデータは、ファイル名情報を付加して、
    下記 ``data``の形式で保持する。

    irconfファイルの書式: JSON
    --------------------------
    下記 ``conf_data`` 一つ、または、``conf_data``のリスト。

    データ構造
    ----------
    data      := [data_ent1, data_ent2, .. ]
    data_ent  := {'file': 'file_name1', 'data': conf_data1}
    conf_data := {
      "comment": "comment text",
      "dev_name": ["dev_name1", "dev_name2"],
      "format:": "{AEHA|NEC|AEHA|DYSON}"      # optional
      "T": t,        # us
      "sym_tbl": {
        "-": [n, n], # leader
        "=": [n, n], # leader?
        "0": [n, n], # 0
        "1": [n, n], # 1
        "/": [n, n], # trailer
        "*": [n, n], # repeat
        "?": [n, n]  # ???
      },
      "macro": {
        "[prefix]": "- {hex|(0b)bin} ",
        "[suffix]": "{hex|bin} /",
        "[repeat]": "*/"
      }
      "buttons": {
        "button1": "[prefix] {hex|bin} [suffix] [repeat] [repeat]",
        "button2": ["[prefix] {hex|bin} [suffix] [repeat] [repeat]", n]
      }
    }
    """
    HEADER_BIN   = '(0b)'
    CONF_SUFFIX  = '.irconf'
    DEF_CONF_DIR = ['.',
                    str(Path.home()) + '/.irconf.d',
                    '/etc/irconf.d']

    def __init__(self, conf_dir=None, load_all=False, debug=False):
        self.debug = debug
        self.logger = MyLogger.get_logger(__class__.__name__, self.debug)
        self.logger.debug('conf_dir=%s', conf_dir)

        if conf_dir is None:
            self.conf_dir = self.DEF_CONF_DIR
        else:
            if type(conf_dir) == list:
                self.conf_dir = conf_dir
            else:
                self.conf_dir = [conf_dir]
        self.logger.debug('conf_dir=%s', self.conf_dir)

        self.data = []

        if load_all:
            self.load_all()

    def get_raw_data(self, dev_name, button_name):
        """
        デバイス情報を取得して、[pulse, space] のリストを返す。

        Parameters
        ----------
        dev_name: str
        button_name: str

        Returns
        -------
        raw_data: list
          [[p1, s1], [p2, s2], .. ]

        """
        self.logger.debug('dev_name=%s, button_name=%s', dev_name, button_name)

        dev = self.get_dev(dev_name)
        if dev is None:
            self.logger.error('%s: no such device', dev_name)
            return[]
        dev_data = dev['data']
        try:
            button_data = dev_data['buttons'][button_name]
        except KeyError:
            self.logger.warning('no such button: %s,%s', dev_name, button_name)
            return ['no such button']
        self.logger.debug('button_data=%s', button_data)

        sig_str = ''
        #
        # 繰り返し回数展開
        #
        if type(button_data) == str:
            sig_str = button_data
        elif type(button_data) == list:
            if len(button_data) == 2:
                (s, n) = button_data
                for i in range(n):
                    sig_str += s
        self.logger.debug('sig_str=%s', sig_str)
        if sig_str == '':
            self.logger.error('invalid button_data:%s', button_data)
            return ['invalid button data']

        #
        # マクロ(prefix, suffix etc.)展開
        #
        for m in dev_data['macro']:
            sig_str = sig_str.replace(m, dev_data['macro'][m])
        self.logger.debug('sig_str=%s', sig_str)
        if '[' in sig_str or ']' in sig_str:
            msg = 'invalid macro: sig_str=\'%s\'' % sig_str
            self.logger.error(msg)
            return [msg]
        #
        # スペース削除
        #
        sig_str = sig_str.replace(' ', '')
        self.logger.debug('sig_str=%s', sig_str)

        #
        # バイナリコードの途中の HEADR_BIN を削除
        #   '(0b)01(0b)10' -> '(0b)0110'
        #
        sig_str = sig_str.replace('0' + self.HEADER_BIN, '0')
        sig_str = sig_str.replace('1' + self.HEADER_BIN, '1')

        #
        # 記号、数値部の分割
        #
        for ch in dev_data['sym_tbl']:
            if ch in '01':
                continue
            sig_str = sig_str.replace(ch, ' ' + ch + ' ')
        self.logger.debug('sig_str=%s', sig_str)
        sig_list1 = sig_str.split()
        self.logger.debug('sig_list1=%s', sig_list1)

        #
        # hex -> bin
        #
        sig_list2 = []
        for sig in sig_list1:
            if sig in dev_data['sym_tbl']:
                if sig not in '01':
                    sig_list2.append(sig)
                    continue

            if sig.startswith(self.HEADER_BIN):
                # '(0b)0101' -> '0101'
                sig_list2.append(sig[len(self.HEADER_BIN):])
                continue

            # hex -> bin
            bin_str = ''
            for ch in sig:
                if ch in '0123456789ABCDEFabcdef':
                    bin_str += format(int(ch, 16), '04b')
                else:
                    bin_str += ch
            sig_list2.append(bin_str)
        self.logger.debug('sig_list2=%s', sig_list2)

        #
        # 一つの文字列に再結合
        #
        sig_str2 = ''.join(sig_list2)
        self.logger.debug('sig_str2=%s', sig_str2)

        #
        # make pulse,space list (raw_data)
        #
        raw_data = []
        t = dev_data['T']
        for ch in sig_str2:
            if ch not in dev_data['sym_tbl']:
                self.logger.warning('ch=%s !? .. ignored', ch)
                continue
            (pulse, space) = dev_data['sym_tbl'][ch][0]
            raw_data.append([pulse * t, space * t])
        self.logger.debug('raw_data=%s', raw_data)

        return raw_data

    def get_dev(self, dev_name):
        """
        デバイス情報取得

        Parameters
        ----------
        dev_name: str2

        Returns
        d_ent: dict
          {'file': file_name, 'data': conf_data}
        """
        self.logger.debug('dev_name=%s', dev_name)

        for d_ent in self.data:
            try:
                d_nlist = d_ent['data']['dev_name']
                self.logger.debug('d_nlist=%s', d_nlist)
            except KeyError:
                self.logger.warning('KeyError .. ignored: %s', d_ent)
                continue

            if type(d_nlist) != list:
                d_nlist = [d_nlist]
                self.logger.debug('d_nlist=%s', d_nlist)
            for d_name in d_nlist:
                self.logger.debug('d_name=%s', d_name)

                if d_name == dev_name:
                    self.logger.debug('%s: found', dev_name)
                    return d_ent

        self.logger.debug('%s: not found', dev_name)
        return None

    def load_all(self):
        """
        全てのirconfファイルを読み込む

        Returns
        -------
        result: bool

        """
        self.logger.debug('')

        files = []
        for d in self.conf_dir:
            self.logger.debug('d=%s', d)
            for f in list(Path(d).glob('*' + self.CONF_SUFFIX)):
                files.append(str(f))
        self.logger.debug('files=%s', files)

        for f in files:
            if self.load(f) is None:
                return False
        return True

    def load_json_dump(self, file_name):
        """ [現在は不要 ?]
        ``file_name``から読み込んだ不完全な JSONリストを修正して、
        JSONパーサーが読めるようにする。

        "{data1}, {data2}," -> "[ {data1}, {data2} ]"

        Parameters
        ----------
        file_name: str

        """
        self.logger.debug('file_name=%s', file_name)

        with open(file_name, 'r') as f:
            line = f.readlines()

        if line[0].split()[0] != '{' or line[-1].split()[0] != ',':
            self.logger.debug('invalid json.dump file: %s', file_name)
            return None

        line.pop(-1)
        line.insert(0, '[')
        line.append(']')
        s = ''.join(line)
        self.logger.debug(s)
        data = json.loads(s)
        return data

    def load(self, file_name):
        """
        irconfファイル ``file_name``を読み込む

        Returns
        -------
        self.data: dict

        """
        self.logger.debug('file_name=%s', file_name)

        try:
            with open(file_name, 'r') as f:
                data = json.load(f)
                self.logger.debug('data=%s', json.dumps(data))
        except json.JSONDecodeError as e:
            data = self.load_json_dump(file_name)
            if data is None:
                self.logger.error('%s: %s, %s', file_name, type(e), e)
                return None
        except Exception as e:
            self.logger.error('%s, %s', type(e), e)
            return None

        if type(data) == list:
            for d in data:
                data_ent = {'file': file_name, 'data': d}
                self.data.append(data_ent)
        else:
            data_ent = {'file': file_name, 'data': data}
            self.data.append(data_ent)
        self.logger.debug('data=%s', self.data)

        return self.data

    def save(self, file_name=None):
        self.logger.debug('file_name=%s', file_name)


#####
class App:
    """
    """
    def __init__(self, debug=False):
        self.debug = debug
        self.logger = MyLogger.get_logger(__class__.__name__, debug)
        self.logger.debug('')

    def main(self, dev_name, button, conf_file):
        self.logger.debug('dev_name=%s, button=%s, conf_file=%s',
                          dev_name, button, conf_file)

        irconf = IrConfig(debug=self.debug)
        self.logger.debug('irconf=%s', irconf)

        if len(conf_file) == 0:
            irconf.load_all()
        else:
            irconf.load(conf_file)

        conf_data_ent = irconf.get_dev(dev_name)
        self.logger.debug('conf_data_ent=%s', conf_data_ent)

        if conf_data_ent is not None:
            print('<%s>' % (dev_name))

            conf_data = conf_data_ent['data']
            self.logger.debug('conf_data=%s', conf_data)

            if len(button) != 0:
                if ''.join(conf_data['macro'].values()) != '':
                    print('  [macro]')
                    for m in conf_data['macro']:
                        if conf_data['macro'][m] != '':
                            print('    \'%s\': %s' % (m,
                                                      conf_data['macro'][m]))

            buttons = conf_data['buttons']
            if len(button) == 0:
                print('  [buttons]: %s' % list(buttons.keys()))
            else:
                for b in button:
                    button_data = buttons[b]
                    print('  <%s>: %s' % (b, button_data))

                    raw_data = irconf.get_pulse_space(dev_name, b)
                    self.logger.debug('raw_data=%s', raw_data)

    def end(self):
        self.logger.debug('')


#### main
import click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS,
               help='IR config')
@click.argument('dev_name', type=str)
@click.argument('button', type=str, nargs=-1)
@click.option('--conf_file', '-c', '-f', 'conf_file', type=str, default='',
              help='config file')
@click.option('--debug', '-d', 'debug', is_flag=True, default=False,
              help='debug flag')
def main(dev_name, button, conf_file, debug):
    logger = MyLogger.get_logger(__name__, debug)
    logger.debug('dev_name=%s, button=%s, file=%s',
                 dev_name, button, conf_file)

    app = App(debug=debug)
    try:
        app.main(dev_name, button, conf_file)
    finally:
        logger.debug('finally')
        app.end()


if __name__ == '__main__':
    main()
