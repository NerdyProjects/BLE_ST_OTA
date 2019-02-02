# BLE OTA application for ST BlueNRG-1/2 OTA protocol

This application handles OTA firmware upgrade following ST's proposed OTA protocol implemented in the BlueNRG example libraries.

It is written in python and uses the `bluepy` bluetooth low energy lib.

## Installation

```
virtualenv --no-site-packages venv
. ./venv/bin/activate
pip install -r requirements.txt
```

## Execution

```
. ./venv/bin/activate
python ota.py -h
```

### Scan
```
python ota.py --scan
```
displays a list of bluetooth LE devices
