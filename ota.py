import argparse
from intelhex import IntelHex
from bluepy.btle import Scanner, DefaultDelegate, Peripheral, ADDR_TYPE_RANDOM
from struct import unpack


class Ota():
    OTA_SERVICE_UUID = "8a97f7c0-8506-11e3-baa7-0800200c9a66"
    IMAGE_CHARACTERISTIC_UUID = "122e8cc0-8508-11e3-baa7-0800200c9a66"
    NEW_IMAGE_CHARACTERISTIC_UUID = "210f99f0-8508-11e3-baa7-0800200c9a66"
    NEW_IMAGE_TRANSFER_UNIT_CONTENT_CHARACTERISTIC_UUID = "2691aa80-8508-11e3-baa7-0800200c9a66"
    NEW_IMAGE_EXPECTED_TRANSFER_UNIT_CHARACTERISTIC_UUID = "2bdc5760-8508-11e3-baa7-0800200c9a66"
    service = None
    image_char = None
    new_image_char = None
    new_image_tu_char = None
    new_image_expected_tu_char = None

    def __init__(self, peripheral):
        self.service = peripheral.getServiceByUUID(self.OTA_SERVICE_UUID)
        characteristics = self.service.getCharacteristics()
        for c in characteristics:
            if c.uuid == self.IMAGE_CHARACTERISTIC_UUID:
                self.image_char = c
            elif c.uuid == self.NEW_IMAGE_CHARACTERISTIC_UUID:
                self.new_image_char = c
            elif c.uuid == self.NEW_IMAGE_TRANSFER_UNIT_CONTENT_CHARACTERISTIC_UUID:
                self.new_image_tu_char = c
            elif c.uuid == self.NEW_IMAGE_EXPECTED_TRANSFER_UNIT_CHARACTERISTIC_UUID:
                self.new_image_expected_tu_char = c
        if (self.image_char is None or
            self.new_image_char is None or
            self.new_image_tu_char is None or
            self.new_image_expected_tu_char is None):
                raise Exception("Could not find all characteristics in OTA service on %s" % (peripheral))

        self.read_free_space_info()
        print("Initialized OTA application, application space 0x%x-0x%x (%d bytes)" % (self.free_space_start,
            self.free_space_end, self.free_space_end - self.free_space_start))

    def read_free_space_info(self):
        response = self.image_char.read()
        self.free_space_start, self.free_space_end = unpack(">II", response)

    def program(self, data):
        min_addr = data.minaddr()
        max_addr = data.maxaddr()
        if (min_addr < self.free_space_start or
            min_addr > self.free_space_end or
            max_addr < self.free_space_start or
            max_addr > self.free_space_end):
            raise Exception("program image out of allowed range (image: 0x%x-0x%x, device: 0x%x-0x%x)" %
                    (min_addr, max_addr, self.free_space_start, self.free_space_end))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", help="Scans for Bluetooth low energy devices", action="store_true")
    parser.add_argument("--device", help="Connects to given bluetooth device and give OTA information")
    parser.add_argument("--program", help="Writes firmware image onto device")
    args = parser.parse_args()
    ota_service = None

    if args.scan:
        scanner = Scanner()
        devices = scanner.scan(5.0)

        for dev in devices:
            print("Device %s (%s), RSSI=%d dB, connectable=%r" % (dev.addr, dev.addrType, dev.rssi, dev.connectable))
        for (adtype, desc, value) in dev.getScanData():
            print("  %s = %s" % (desc, value))

    if args.device:
        peripheral = Peripheral(args.device, ADDR_TYPE_RANDOM)
        ota_service = Ota(peripheral)

    if args.device and args.program:
        ih = IntelHex()
        ih.fromfile(args.program, format='hex')
        ota_service.program(ih)


if __name__ == "__main__":
    main()
