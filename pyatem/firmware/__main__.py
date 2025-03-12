import argparse
import struct

import requests
import logging


def get(ip, endpoint):
    base = f'http://{ip}/admin/api/v1'
    return requests.get(f'{base}/{endpoint}').json()


def put(ip, endpoint, payload):
    base = f'http://{ip}/admin/api/v1'
    return requests.put(f'{base}/{endpoint}', data=payload)


def get_device_capability(ip, capability):
    capa = get(ip, 'capabilities')
    if 'response' not in capa:
        logging.fatal("Did not get a valid response to the capabilities request")

    if capability not in capa['response']:
        return 0

    version = capa['response'][capability]['version']
    return version


def get_setup_basic(ip):
    return get(ip, 'setupBasic')


def get_firmware_info(ip):
    return get(ip, 'firmware/info')


def get_device_info(ip):
    setupcap = get_device_capability(ip, 'setupBasic')
    if setupcap != 1:
        logging.fatal("Device does not support the setupBasic capability")
        exit(1)

    basic = get_setup_basic(ip)['response']
    logging.info(f"Device:   {basic['productName']}")
    logging.info(f"Name:     {basic['deviceName']}")
    logging.info(f"Firmware: {basic['software']}")

    fwcap = get_device_capability(ip, 'firmware')
    if fwcap == 0:
        logging.fatal("Device does not support HTTP firmware upgrades")
        exit(1)

    if fwcap != 1:
        logging.fatal(f"Unknown firmware protocol version: {fwcap}")
        exit(1)

    fwinfo = get_firmware_info(ip)['response']
    logging.info(f"Hardware: 0x{fwinfo['hardware version']}")
    logging.info(f"Software: 0x{fwinfo['software version']}")
    logging.info(f"Filename: data-{fwinfo['product id'].lower()}.bin")
    logging.info("")

    return fwinfo['product id']


def load_firmware(file):
    with open(file, 'rb') as handle:
        fwheader = handle.read(80)
        fwdata = handle.read()

    part = struct.unpack_from('>32s HH 4x I H 2x I 4x 2x 2x 4x 4x HH', fwheader)
    checksum = part[0]
    length = part[3]
    headersize = part[4]
    fwlength = part[5]
    vid, pid = part[6], part[7]
    hpid = hex(pid).upper()[2:]
    piep = len(fwdata)
    if (length - headersize) != fwlength:
        logging.fatal("Understanding of header format incomplete, exit for safety")
        exit(1)

    if len(fwdata) != (part[3] - 48):
        logging.fatal("Firmware file length doesn't match header length")
        exit(1)

    return hpid, fwdata


def update_firmware(ip, firmware):
    fpid, fwdata = firmware
    response = put(ip, 'firmware/updateStart', b'').json()
    if 'success' not in response:
        logging.fatal("updateStart did not have a success key")
        exit(1)
    if not response['success']:
        logging.fatal("updateStart did not return a success result")
        exit(1)
    if 'response' not in response:
        logging.fatal("updateStart did not have a response key")
        exit(1)
    if 'upload_name' not in response['response']:
        logging.fatal("updateStart did not return an upload_name")
        exit(1)
    upload_name = response['response']['upload_name']
    logging.info(f"Upload filename is {upload_name}")

    logging.info("Uploading firmware to device...")
    response = put(ip, f'firmware/upload/{upload_name}', fwdata)
    if response.status_code != 200:
        logging.error(f'Update failed, http status {response.status_code}')
        exit(1)
    logging.info("Finalizing firmware update...")
    response = put(ip, 'firmware/updateFinalize', b'').json()
    if 'success' not in response:
        logging.fatal("updateFinalize did not have a success key")
        exit(1)
    if not response['success']:
        logging.fatal("updateFinalize did not return a success result")
        exit(1)
    logging.info("Firmware update completed")


def main():
    parser = argparse.ArgumentParser(description="ATEM firmware tool")
    parser.add_argument('ip', help='IP address of the ATEM device')
    parser.add_argument('file', nargs='?', help='Firmware filename')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.ip == "inspect":
        firmware = load_firmware(args.file)
        print(f"Firmware is for device {firmware[0]}")
        exit(0)

    product = get_device_info(args.ip)

    if args.file:
        firmware = load_firmware(args.file)
        logging.info("Everything seems to be ready to go, press enter to continue or ctrl+c to abort")
        input()
        if product != firmware[0]:
            logging.error(f"Product ID of device [{product}] does not match firmware file [{firmware[0]}]")
        update_firmware(args.ip, firmware)


if __name__ == '__main__':
    main()
