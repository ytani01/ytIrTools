# ytIrTools for Raspberry Pi
### pigpio + python3 による、赤外線リモコン制御・解析ツール

## 概要

* LIRCなどは使わず、pigpioのPythonライブラリで作成 -- 高性能で高い柔軟性
* 正確な信号解析。
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
オプション「-t 0」は必須です。

自動起動する場合は、crontabを設定。(crontab.sample参照)

### IrAnalyze.py -- 赤外線信号受信・解析

赤外線信号を受信して解析結果を表示する。
詳細な情報を /tmp/ir_json.dump に保存(追記)する。

```
Usage: IrAnalyze.py [OPTIONS] [PIN]

  IR signal analyzer

Options:
  -d, --debug  debug flag
  -h, --help   Show this message and exit.
```

### 1.2 IrSend.py -- 赤外線信号送信

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

### 書式 -- JSON

下記の例のような書式の JSONフォーマット・ファイルを作成する。

ファイル名は任意(検索パスの全ファイルを読み込み、"dev_name"で検索される)。

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

### 拡張子

「.irconf」

これ以外の拡張子だと無視される。


### 検索パス

1. カレントディレクトリ
2. ${HOME}/.irconf.d
3. /etc/irconf.d


## References

* [pigpio](http://abyz.me.uk/rpi/pigpio/)
* [ESP-WROOM-02で赤外線学習リモコン](https://github.com/Goji2100/IRServer)
* [irdb](http://irdb.tk/)
* [Codes for IR Remotes (for YTF IR Bridge)](https://github.com/arendst/Tasmota/wiki/Codes-for-IR-Remotes-(for-YTF-IR-Bridge))
