# ytIrTools for Raspberry Pi

Raspberry Pi + pigpio + python3 による、赤外線リモコン制御・解析ツール


## 概要

* LIRCなどは使わず、pigpioのPythonライブラリで作成 -- 高性能で高い柔軟性
* 正確な信号解析(IrAnalyze.py)
* 信号フォーマットは、AEHA,SONY,NEC以外に、DYSON,BOSEほか、あらゆる機器に対応
* 送受信を同時に行える
* 赤外線送受信につかうGPIOピンを(PWM用の12, 13, 18, 19以外で)自由に選べる

ちなみに…
GPIO の ON/OFF で信号を出しているのではなく、
pigpioの wave関数を使って、高品質な赤外線信号を作成してます。


## 注意

PWM用のピン(GPIO 12,13,18,19)は、使用しないで下さい。

* pigpiodをデフォルト(クロック=PCM)で立ち上げると不安定になる??


## インストール

### ytIrTools

```bash
# cd ~
$ python3 -m venv env-ir
$ cd env-ir
$ git clone https://www.github.com/ytani01/ytIrTools.git
$ cd ytIrTools
$ ./setup.sh
```

#### crontab の設定 (自動起動、自動再起動)
このとき、crontabの設定が上書きされます。
直前の設定内容は、``crontab.bak``に保存されます。
必要に応じて、``crontab -e``コマンドなどで、設定を調整して下さい。

```bash
$ crontab -l > crontab.bak
$ crontab crontab.sample
```

### Node-RED

Node-REDのインストール
```bash
bash < \(curl -sL https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered\)
```

追加フロー
* node-red-dashbaord
* alexa-home-skil


## ハードウェア

下記のページの回路を使うと、強力な赤外線信号を広範囲に送信できます。

* [IRRC32(IRServer32) - ESP32で赤外線学習リモコン](https://github.com/Goji2100/IRRC32)


## Comands

### [pigpiod](http://abyz.me.uk/rpi/pigpio/)

事前に pigpiod を起動する必要があります。
上記設定を行えば、自動的に起動するので、下記を行う必要はありません。

```bash
$ sudo pigpiod -t 0
```
* オプション「-t 0」がないと、不安定になる(?)

自動起動する場合は、crontabを設定。(crontab.sample 参照)

(注意) コマンドラインで "$ crontab crontab.sample" を実行すると、
今までの crontabが全て消去されます！


### ir-send (IrSendCmdClient.py) -- 赤外線信号コマンド

実体は、``IrSendCmdClient.py``です。
(python venvを``activate``してから、このスクリプトを呼び出します。)

デバイス名とボタン名を指定して、赤外線信号を送信する。
デバイス名・ボタンの設定は後述。

引数がない場合は、デバイス一覧、
デバイス名だけを指定した場合は、ボタン一覧
を表示。
```
$ ir-send -h

Usage: IrSendCmdClient.py [OPTIONS] [ARG]...

  IrSendCmdClient

Options:
  -s, --svrhost TEXT  server hostname
  -p, --port INTEGER  server port nubmer
  -d, --debug         debug flag
  -h, --help          Show this message and exit.

$ ir-send.py dev1 button1 button2
デバイス「dev1」のボタン「button1」と「button2」を連続して送信

$ ir-send.py
設定されているデバイス一覧

$ ir-send.py dev1
デバイス「dev1」に設定されているボタン一覧

$ ir-send.py @load
設定ファイルの再読み込み

```

### ir-analyze (IrAnalyze.py) -- 赤外線信号受信・解析

実体は、``IrAnalyze.py``です。
(python venvを``activate``してから、このスクリプトを呼び出します。)

赤外線信号を受信して解析結果を表示する。

詳細な解析結果情報を
/tmp/ir_dump.irconf
に保存(追記)する。
(このファイルは設定ファイルとして利用可)

最新の受信データ(補正しない生のパルス情報)を
/tmp/pulse_space.txt
に保存する。

```
Usage: IrAnalyze.py [OPTIONS] [PIN]

  IR signal analyzer
  
Options:
  -n INTEGER     number of signal to anlyze
  -v, --verbose  verbose mode
  -d, --debug    debug flag
  -h, --help     Show this message and exit.
```


## 設定ファイル(*.irconf)

* JSON形式で記述します。
* 一つのファイルに複数のデバイス設定を記述することができます。
* ``ir-analyze`` の出力(``/tmp/ir_dump.irconf``)を元に、
デバイス名、ボタン名などを設定できます。
* マクロ文字列を使えば、効率良く、わかりやすい記述が可能。


### ファイル名

* 拡張子は「.irconf」。これ以外のファイルは無視されます。


### 検索パス

下記のパスに存在する全ての``*.irconf''ファイルを読み込みます。

1. カレントディレクトリ
2. ${HOME}/.irconf.d
3. /etc/irconf.d


### 書式 -- JSON

下記の書式で、JSONフォーマット・ファイルを作成する。

* example 1
```
{
  "comment": "example 1",
  "header": {
    "dev_name": ["lamp", "ball_lamp"],
    "format":   "NEC",
    "T":        557.735294,
    "sym_tbl": {
      "-":      [[16, 8]],
      "=":      [],
      "0":      [[1, 1]],
      "1":      [[1, 3]],
      "/":      [[1, 71], [1, 73], [1, 108], [1, 1875]],
      "*":      [[16, 4]],
      "?":      []
    },
    "macro": {
      "[prefix]": "00F7",
      "[suffix]": "F /*/"
    }
  },
  "buttons": {
    "on":  ["- [prefix] C03 [suffix]", 2],
    "off": ["- [prefix] 40B [suffix]", 2]
  }
}
```

* example 2
```
{
  "comment": "example 2",
  "header": {
    "dev_name": ["sony_bl", "bl"],
    "format":   "SONY",
    "T":        598.750000,
    "sym_tbl": {
      "-":      [[4, 1]],
      "=":      [],
      "0":      [[1, 1]],
      "1":      [[2, 1]],
      "/":      [[2, 20], [2, 1966]],
      "*":      [],
      "?":      []
    },
    "macro": {
      "[prefix]": "-(0b)",
      "[suffix]": "0101 1010 0111/"
    }
  },
  "buttons": {
    "ch_01":   ["[prefix] 000 0000 [suffix]", 3],
    "ch_02":   ["[prefix] 100 0000 [suffix]", 3],
    "ch_03":   ["[prefix] 010 0000 [suffix]", 3],
    "ch_04":   ["[prefix] 110 0000 [suffix]", 3],
  }
}
```


## ポート番号

* 51001: IrSendCmdServer
* 51002: AutoAirconServer


## References

* [pigpio](http://abyz.me.uk/rpi/pigpio/)
* [IRRC32(IRServer32) - ESP32で赤外線学習リモコン](https://github.com/Goji2100/IRRC32)
* [irdb](http://irdb.tk/)
* [Codes for IR Remotes (for YTF IR Bridge)](https://github.com/arendst/Tasmota/wiki/Codes-for-IR-Remotes-(for-YTF-IR-Bridge))
