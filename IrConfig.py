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
from MyLogger import get_logger


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
      "def_repeat": n,
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

    SYM_TBL      = {'-': 'leader',
                    '=': 'leader2',
                    '0': 'zero',
                    '1': 'one',
                    '/': 'trailer',
                    '*': 'repeat',
                    '?': 'unknonw'}

    CONF_SUFFIX  = '.irconf'
    DEF_CONF_DIR = ['.',
                    str(Path.home()) + '/.irconf.d',
                    '/etc/irconf.d']

    MSG_OK = 'OK'

    def __init__(self, conf_dir=DEF_CONF_DIR, load_all=False, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, self._dbg)
        self._log.debug('conf_dir=%s', conf_dir)

        self.conf_dir = conf_dir
        if type(self.conf_dir) != list:
            self.conf_dir = [self.conf_dir]
        self._log.debug('conf_dir=%s', self.conf_dir)

        self.data = []

        if load_all:
            self.load_all()

    def expand_button_macro(self, macro_data, button_str):
        """
        ボタンのマクロ展開


        Parameters
        ----------
        macro_data: dict
        button_str: str


        Returns
        -------
        button_str: str
        '': error

        """
        self._log.debug('macro_data=%s', json.dumps(macro_data, indent=2))
        self._log.debug('button_str=%s', button_str)

        for m in macro_data:
            self._log.debug('m=%s', m)
            button_str = button_str.replace(m, macro_data[m])
            self._log.debug('button_str=%s', button_str)

        if '[' in button_str or ']' in button_str:
            self._log.error('invalid macro: button_str=%s', button_str)
            return ''

        return button_str

    def button2syms(self, dev_data, button_name):
        """
        ボタン情報 ``button_name`` を信号シンボル文字列 ``syms`` に変換。

        Parameters
        ----------
        dev_data: dict
        button_name: str

        Returns
        -------
        syms: str
          ex. '-0101..0101/*/'

        button_rep: int

        None, None: error

        """
        self._log.debug('dev_data=%s, button_name=%s',
                           dev_data, button_name)

        try:
            button_data = dev_data['buttons'][button_name]
        except KeyError:
            self._log.error('\'%s\': no such button', button_name)
            return ''

        if type(button_data) == str:
            button_str = button_data
            try:
                button_rep = dev_data['def_repeat']
                self._log.debug('button_rep=dev_data[\'def_repeat\']=%d',
                                   button_rep)
            except KeyError:
                button_rep = 1
        elif type(button_data) == list and len(button_data) == 2:
            (button_str, button_rep) = button_data
        else:
            self._log.error('invalid button_data: %s', button_data)
            return ''
        self._log.debug('button_str=%s', button_str)
        self._log.debug('button_rep=%d', button_rep)

        # マクロ展開
        try:
            button_str = self.expand_button_macro(dev_data['macro'],
                                                  button_str)
            self._log.debug('button_str=%s', button_str)
        except KeyError:
            self._log.warning('no macro')

        """
        # 繰り返し回数展開
        button_str = button_str * button_rep
        self._log.debug('button_str=%s', button_str)
        """

        # スペース削除
        button_str = button_str.replace(' ', '')
        self._log.debug('button_str=%s', button_str)

        # '(0b)01(0b)10' -> '(0b)0110'
        for bit in '01':
            button_str = button_str.replace(bit + self.HEADER_BIN, bit)

        # 記号、数値部の分割
        for ch in self.SYM_TBL:
            if ch in '01':
                continue
            button_str = button_str.replace(ch, ' ' + ch + ' ')
        s_list1 = button_str.split()
        self._log.debug('button_str=%s', button_str)

        # hex -> bin, '(0b)0101' -> '0101'
        s_list2 = []
        for sig in s_list1:
            if sig in self.SYM_TBL and sig not in '01':
                s_list2.append(sig)
                continue

            if sig.startswith(self.HEADER_BIN):
                # '(0b)0101' -> '0101'
                s_list2.append(sig[len(self.HEADER_BIN):])
                continue

            # hex -> bin
            bin_str = ''
            for ch in sig:
                bin_str += format(int(ch, 16), '04b')
            s_list2.append(bin_str)

        #
        # 一つの文字列に再結合
        #
        syms = ''.join(s_list2)
        self._log.debug('syms=%s', syms)

        return syms, button_rep

    def get_raw_data(self, dev_name, button_name):
        """
        デバイス情報を取得して、
        指定されたボタンの[pulse, space] のリストと
        繰り返し回数を返す。

        Parameters
        ----------
        dev_name: str
        button_name: str

        Returns
        -------
        raw_data: list
          [[p1, s1], [p2, s2], .. ]

        repeat: int

        None, None: error

        """
        self._log.debug('dev_name=%s, button_name=%s',
                           dev_name, button_name)

        #
        # デバイス情報取得
        #
        dev = self.get_dev(dev_name)
        if dev is None:
            self._log.error('\'%s\': no such device', dev_name)
            return None, None
        dev_data = dev['data']
        self._log.debug('dev_data=%s', dev_data)

        #
        # ボタンデータをシンボル文字列に変換
        #
        syms, repeat = self.button2syms(dev_data, button_name)
        self._log.debug('syms=%s, repeat=%s', syms, repeat)
        if syms is None:
            return None, None

        #
        # make pulse,space list (raw_data)
        #  [[pulse1, space1], [pulse2, space2], .. ]
        #
        raw_data = []
        t = dev_data['T']
        for ch in syms:
            if ch not in dev_data['sym_tbl']:
                self._log.warning('ch=%s !? .. ignored', ch)
                continue
            (pulse, space) = dev_data['sym_tbl'][ch][0]
            raw_data.append([pulse * t, space * t])
        self._log.debug('raw_data=%s', raw_data)

        return raw_data, repeat

    def get_dev(self, dev_name):
        """
        デバイス情報取得

        Parameters
        ----------
        dev_name: str2

        Returns
        -------
        d_ent: {'file': conf_file_name, 'data': conf_data}

        """
        self._log.debug('dev_name=%s', dev_name)

        for d_ent in self.data:
            try:
                d_nlist = d_ent['data']['dev_name']
                self._log.debug('d_nlist=%s', d_nlist)
            except KeyError:
                self._log.warning('KeyError .. ignored: %s', d_ent)
                continue

            if type(d_nlist) != list:
                d_nlist = [d_nlist]
                self._log.debug('d_nlist=%s', d_nlist)
            for d_name in d_nlist:
                self._log.debug('d_name=%s', d_name)

                if d_name == dev_name:
                    self._log.debug('%s: found', dev_name)
                    return d_ent

        self._log.debug('%s: not found', dev_name)
        return None

    def reload_all(self):
        """
        全てのirconfファイルを再読み込みする。
        既存のデータは消去される。

        Returns
        -------
        msg: str
          error message
          MSG_OK: success
        """
        self._log.debug('')
        self.data = []
        msg = self.load_all()
        return msg

    def load_all(self):
        """
        全てのirconfファイルを読み込む

        Returns
        -------
        msg: str
          error message
          MSG_OK: success
        """
        self._log.debug('')

        rep_msg = self.MSG_OK

        files = []
        for d in self.conf_dir:
            self._log.debug('d=%s', d)
            for f in list(Path(d).glob('*' + self.CONF_SUFFIX)):
                files.append(str(f))
        self._log.debug('files=%s', files)

        for f in files:
            msg = self.load(f)
            if msg != self.MSG_OK:
                rep_msg = msg
                self._log.error(msg)

        return rep_msg

    def load(self, file_name):
        """
        irconfファイル ``file_name``を読み込む

        Returns
        -------
        msg: str
          error message
          MSG_OK: success

        """
        self._log.debug('file_name=%s', file_name)

        msg = self.MSG_OK

        try:
            with open(file_name, 'r') as f:
                data = json.load(f)
                self._log.debug('data=%s', json.dumps(data))
        except json.JSONDecodeError as e:
            msg = '%s: %s, %s' % (file_name, type(e), e)
            self._log.error(msg)
            return msg
        except Exception as e:
            msg = '%s, %s' % (type(e), e)
            self._log.error(msg)
            return msg

        if type(data) == list:
            for d in data:
                data_ent = {'file': file_name, 'data': d}
                self.data.append(data_ent)
        else:
            data_ent = {'file': file_name, 'data': data}
            self.data.append(data_ent)
        self._log.debug('data=%s', self.data)

        return msg

    def save(self, file_name=None):
        self._log.debug('file_name=%s', file_name)
        # TBD


#####
class App:
    """
    """
    def __init__(self, debug=False):
        self._dbg = debug
        self._log = get_logger(__class__.__name__, debug)
        self._log.debug('')

    def main(self, dev_name, button, conf_file):
        self._log.debug('dev_name=%s, button=%s, conf_file=%s',
                           dev_name, button, conf_file)

        irconf = IrConfig(debug=self._dbg)
        self._log.debug('irconf=%s', irconf)

        if len(conf_file) == 0:
            msg = irconf.load_all()
            if msg != IrConfig.MSG_OK:
                self._log.error(msg)
                return
        else:
            msg = irconf.load(conf_file)
            if msg != IrConfig.MSG_OK:
                self._log.error(msg)
                return

        conf_data_ent = irconf.get_dev(dev_name)
        self._log.debug('conf_data_ent=%s', conf_data_ent)

        if conf_data_ent is not None:
            print('<%s>' % (dev_name))

            conf_data = conf_data_ent['data']
            self._log.debug('conf_data=%s', conf_data)

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
                    self._log.debug('raw_data=%s', raw_data)

    def end(self):
        self._log.debug('')


#
# main
#
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
    logger = get_logger(__name__, debug)
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
