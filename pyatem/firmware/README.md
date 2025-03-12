# Firmware update utility

This utility can push firmware update to networked ATEM devices that have the new REST api. 

The firmware files can be extracted by unpacking the "ATEM Switchers" update files from blackmagic design and searching
for the `data-*.bin` files. The update utility can figure out the right filename by specifying only an IP address or hostname:

```shell-session
$ python3 -m pyatem.firmware 192.168.2.1
Device:   ATEM Mini Extreme
Name:     OpenSwitcher :)
Firmware: 9.5.1
Hardware: 0x0100
Software: 0x08132CCA
Filename: data-be7c.bin
```

Here the ATEM Mini Extreme is connected and the utility reports the filename is data-be7c.bin. The firmware update
support is extremely basic for now and the utility does a series of sanity checks on the firmware file to make sure
it matches expectations. You can use the inspect command to run those checks without being connected to hardware:

```shell-session
$ python3 -m pyatem.firmware inspect /tmp/data-be7c.bin
Firmware is for device BE7C
```

Here the values for the header of the firmware are checked and the firmware product ID is loaded as extra sanity check.
So far the utility can parse the firmware files for ATEM Mini devices but it looks like other series of devices have
slightly different formats, the flashing utility will abort any operation when this is encountered.

The firmware can be flashed by specifying both the ip/hostname and the firmware file:

```shell-session
$ python3 -m pyatem.firmware 192.198.2.1 /tmp/data-be7c.bin
Device:   ATEM Mini Extreme
Name:     OpenSwitcher :)
Firmware: 9.5.1
Hardware: 0x0100
Software: 0x08132CCA
Filename: data-be7c.bin

Everything seems to be ready to go, press enter to continue or ctrl+c to abort
[pressed enter]

Upload filename is update-somerandomstring.bin
Uploading firmware to device...
Finalizing firmware update...
Firmware update completed
```

After the firmware update is completed the device should restart and it will be running the new firmware.

## Tested upgrades

* ATEM Mini Extreme
  * 9.5 -> 9.5.1

### Notes

```
#pragma endian big

struct FWHeader {
    char hash[32];
    
    u16 magic;    // always 0xBDBD
    u16 unknown1; // Possibly HW version
    u32 unknown2;
    u32 length;
    
    u16 headersize;
    u16 unknown3;
    u32 fwlength;
    
    u32 unknown4; // Firmware ID?
    u16 unknown5; // Possibly HW version
    u16 unknown6;
    
    u32 unknown7;
    u16 unknown8; // Always 0 for firmware I can parse, sometimes 3
    u16 unknown9; // Possibly HW version
    
    u16 vendor_id;
    u16 product_id;
    
    u64 unknown10;
};

FWHeader firmware @0x00;
```