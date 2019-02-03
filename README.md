# BLE OTA application for ST BlueNRG-1/2 OTA protocol

This application handles OTA firmware upgrade following ST's proposed OTA protocol implemented in the BlueNRG example libraries.

It is written in python and uses the `bluepy` bluetooth low energy lib.

## Installation

```
virtualenv --no-site-packages venv
. ./venv/bin/activate
pip install -r requirements.txt
sudo setcap 'cap_net_raw,cap_net_admin+eip' ./venv/lib/python3.7/site-packages/bluepy/bluepy-helper
```

## Execution
  * Turn bluetooth on
  * If you get permission denied errors on BLE operations, make sure you executed the setcap command above or run the python script with sudo

```
. ./venv/bin/activate
sudo python ota.py -h
```

### Scan
```
python ota.py --scan
```
displays a list of bluetooth LE devices

### Device Info
```
python ota.py --device 00:11:22:33:44:55
```
displays information about flash memory on device

### Program device
```
python ota.py --device 00:11:22:33:44:55 --program path/to/hexfile.hex
```
programs the device
