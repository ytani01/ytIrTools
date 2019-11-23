# ytIrTools for Raspberry Pi
### Raspberry Pi + pigpio + python3 による、赤外線リモコン制御・解析ツール

## 概要

* LIRCなどは使わず、pigpioのPythonライブラリで作成 -- 高性能で高い柔軟性
* 正確な信号解析。(IrAnalyze.py)
* 信号フォーマットは、AEHA,SONY,NEC以外に、DYSON,BOSEなどの一部機器にも対応
* 送受信を同時に行える。
* 赤外線送受信につかうGPIOピンを(PWM用の12, 13, 18以外で)自由に選べる

## 注意

PWM用のピン(GPIO 12,13,18)は、使用できなくなります。
(クロックとして使用しているため)

※ pigpiodをデフォルト(クロック=PCM)で立ち上げると不安定になる??



## Comands

### pigpiod

事前に pigpiod を起動しておいてください。

```bash
$ sudo pigpiod -t 0
```
※オプション「-t 0」がないと、不安定になる(?)

自動起動する場合は、crontabを設定。(crontab.sample参照)

※(注意) コマンド "crontab crontab.sample" を実行すると、
今までの crontabが全て消去されます！

### IrAnalyze.py -- 赤外線信号受信・解析

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
  -d, --debug  debug flag
  -h, --help   Show this message and exit.
```


### IrSendServer.py -- 赤外線信号送信サーバー



### IrSend.py -- 赤外線信号送信

(注意) 複数タスクで同時に起動すると、送信失敗することがあります。
出来る限り、上記 IrSendServer.py を利用してください。

デバイス名とボタン名を指定して、赤外線信号を送信する。
デバイス名・ボタンの設定は後述


```
Usage: IrSend.py [OPTIONS] DEV_NAME [BUTTONS]...

  IR signal transmitter

Options:
  -p, --pin INTEGER     pin number
  -n INTEGER
  -i, --interval FLOAT
  -d, --debug           debug flag
  -h, --help            Show this message and exit.
```


## *.irconf -- 設定ファイル

* 一つのファイルに複数のデバイス設定を記述することができる。


### ファイル名

* 拡張子は「.irconf」。これ以外のファイルは無視される。


### 検索パス

1. カレントディレクトリ
2. ${HOME}/.irconf.d
3. /etc/irconf.d


### 書式 -- JSON

下記の例のような書式の JSONフォーマット・ファイルを作成する。

検索パスの全irconfファイルが読み込まれる。

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



## References

* [pigpio](http://abyz.me.uk/rpi/pigpio/)
* [ESP-WROOM-02で赤外線学習リモコン](https://github.com/Goji2100/IRServer)
* [irdb](http://irdb.tk/)
* [Codes for IR Remotes (for YTF IR Bridge)](https://github.com/arendst/Tasmota/wiki/Codes-for-IR-Remotes-(for-YTF-IR-Bridge))
