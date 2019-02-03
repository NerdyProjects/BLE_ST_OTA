import sys
import argparse
from intelhex import IntelHex
from bluepy.btle import Scanner, DefaultDelegate, Peripheral, ADDR_TYPE_RANDOM
from struct import pack, unpack
from enum import Enum


class NotificationDelegate(DefaultDelegate):
    def __init__(self, ota):
        DefaultDelegate.__init__(self)
        self.ota = ota

    def handleNotification(self, cHandle, data):
        self.ota.notification(cHandle, data)

class OtaError(Enum):
    OTA_SUCCESS = 0
    OTA_FLASH_VERIFY_ERROR = 0x3c
    OTA_FLASH_WRITE_ERROR = 0xff
    OTA_SEQUENCE_ERROR = 0xf0
    OTA_CHECKSUM_ERROR = 0x0f


class Ota():
    OTA_SERVICE_UUID = "8a97f7c0-8506-11e3-baa7-0800200c9a66"
    IMAGE_CHARACTERISTIC_UUID = "122e8cc0-8508-11e3-baa7-0800200c9a66"
    NEW_IMAGE_CHARACTERISTIC_UUID = "210f99f0-8508-11e3-baa7-0800200c9a66"
    NEW_IMAGE_TRANSFER_UNIT_CONTENT_CHARACTERISTIC_UUID = "2691aa80-8508-11e3-baa7-0800200c9a66"
    NEW_IMAGE_EXPECTED_TRANSFER_UNIT_CHARACTERISTIC_UUID = "2bdc5760-8508-11e3-baa7-0800200c9a66"
    notification_interval = 8
    peripheral = None
    service = None
    image_char = None
    new_image_char = None
    new_image_tu_char = None
    new_image_expected_tu_char = None
    delegate = None
    data = None
    upload_in_progress = False
    sequence = 0
    last_sequence = 0

    def __init__(self, peripheral):
        self.peripheral = peripheral
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
        self.delegate = NotificationDelegate(self)
        self.peripheral.withDelegate(self.delegate)

    def read_free_space_info(self):
        response = self.image_char.read()
        # while being little endian everywhere, the free space addresses are explicitly reversed in firmware
        self.free_space_start, self.free_space_end = unpack(">II", response)

    """
    Writes to the new image characteristic of the OTA service: Prepare firmware update

    :param base_addr start address of firmware image
    :param size size in bytes of firmware image
    :param notification_interval changes the number of BLE GATT blocks before an ACK/ERROR cycle with the device is
    done. Implementation in OTA service hasn't been studied enough, for now use with 1 only
    """
    def write_new_image_characteristic(self, base_addr, size, notification_interval = 8):
        if (base_addr < self.free_space_start or
            base_addr > self.free_space_end or
            base_addr + size > self.free_space_end):
            # Careful! while the OTA library application (as of v2.1.0) does not come with any range checks,
            # the flash erase is actually implemented only in the reset or ota service managers, not in the OTA
            # application. Writing outside of the allowed range would work but transform the flash contents
            # into garbage!
            # Also, writing the same device range (with a different image) a second time would work but misses the
            # erase cycle except a reset occured!
            raise Exception("program image out of allowed range (image: 0x%x-0x%x, device: 0x%x-0x%x)" %
                    (base_addr, base_addr + size, self.free_space_start, self.free_space_end))

        data = pack("<BII", self.notification_interval, size, base_addr)
        self.new_image_char.write(data)
        res_ni, res_size, res_base = self.read_new_image_characteristic()
        if (res_ni != notification_interval or res_size != size or res_base != base_addr):
            raise Exception("writing new image characteristic verify failed!")

        print("wrote new image characteristic: Programming %x (len: %d)" % (base_addr, size))

    """
    Reads new image characteristic of OTA service.

    :return tuple of notification_interval, size, base_addr
    """
    def read_new_image_characteristic(self):
        response = self.new_image_char.read()
        return unpack("<BII", response)

    def register_notification(self, valHandle, enabled):
        data = pack("<H", 1 if enabled else 0)
        self.peripheral.writeCharacteristic(valHandle + 1, data)

    def program(self, data):
        min_addr = data.minaddr()
        max_addr = data.maxaddr()
        self.write_new_image_characteristic(min_addr, max_addr - min_addr, self.notification_interval)
        self.register_notification(self.new_image_expected_tu_char.getHandle(), True)
        #self.write_image_block(0, data.tobinarray(min_addr, min_addr + 15))
        self.data = data
        self.sequence = 0
        self.last_sequence = (max_addr - min_addr + 15) >> 4
        print("Starting upload, last sequence: %d" % (self.last_sequence))
        self.upload_in_progress = True
        while self.upload_in_progress:
            if self.peripheral.waitForNotifications(10) == False:
                raise Exception("Upload failed with timeout")

    def write_image_block(self, sequence, request_ack):
        image = self.data.tobinarray(self.data.minaddr() + sequence * 16, self.data.minaddr() + sequence * 16 + 15)
        needs_ack = 1 if request_ack else 0
        checksum = needs_ack ^ (sequence % 256) ^ (sequence >> 8)
        for b in image:
            checksum ^= b
        data = pack("<B16sBH", checksum, bytes(image), needs_ack, sequence)
        self.new_image_tu_char.write(data)

    def notification(self, handle, data):
        if handle == self.new_image_expected_tu_char.getHandle():
            next_sequence, error = unpack("<HH", data)
            status = OtaError(error)
            print("Received notification for expected tu, seq: %d, status: %s" % (next_sequence, status))
            if error != 0:
                print("Received error, retrying...")
            sys.stdout.flush()
            if next_sequence <= self.last_sequence:
                for i in range(next_sequence, next_sequence + self.notification_interval):
                    request_ack = i == next_sequence + self.notification_interval - 1
                    print("write image seq %d with ack %r" % (i, request_ack))
                    self.write_image_block(i, request_ack)
            else:
                print("Upload finished")

        else:
            print("Received notification for %d with %s" % (handle, data.hex()))


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
