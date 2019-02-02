import argparse
from bluepy.btle import Scanner, DefaultDelegate

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--scan", help="Scans for Bluetooth low energy devices", action="store_true")
  args = parser.parse_args()

  if args.scan:
    scanner = Scanner()
    devices = scanner.scan(10.0)
  
    for dev in devices:
      print("Device %s (%s), RSSI=%d dB" % (dev.addr, dev.addrType, dev.rssi))
      for (adtype, desc, value) in dev.getScanData():
        print("  %s = %s" % (desc, value))
  

if __name__ == "__main__":
  main()
