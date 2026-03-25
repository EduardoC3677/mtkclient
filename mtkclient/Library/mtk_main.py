#!/usr/bin/env python3
# MTK Flash Client (c) B.Kerler 2018-2026.
# Licensed under GPLv3 License
import os
import sys
import logging
import time
from binascii import hexlify
from struct import unpack, pack
from mtkclient.Library.mtk_class import Mtk
from mtkclient.config.payloads import PathConfig
from mtkclient.Library.pltools import PLTools
from mtkclient.Library.meta import META
from mtkclient.Library.utils import getint
from mtkclient.Library.gui_utils import LogBase, logsetup, progress
from mtkclient.config.mtk_config import MtkConfig
from mtkclient.Library.error import ErrorHandler
from mtkclient.Library.DA.mtk_da_handler import DaHandler
from mtkclient.Library.Partitions.gpt import GptSettings

metamodes = "[FASTBOOT, FACTFACT, METAMETA, FACTORYM, ADVEMETA, AT+NBOOT]"


class ArgHandler(metaclass=LogBase):
    @staticmethod
    def _safe_get_arg(args, name, default=None):
        """Safely retrieve an argument attribute, returning default if not present."""
        try:
            value = getattr(args, name, default)
            return value if value is not None else default
        except Exception:
            return default

    def __init__(self, args, config):
        self.__logger, self.info, self.debug, self.warning, self.error = logsetup(self, self.__logger,
                                                                                  config.loglevel, config.gui)
        # GPT file
        gpt_file = self._safe_get_arg(args, "gpt_file")
        config.gpt_file = gpt_file if gpt_file and os.path.exists(gpt_file) else None

        # USB identifiers
        vid = self._safe_get_arg(args, "vid")
        if vid is not None:
            config.vid = getint(vid)
        pid = self._safe_get_arg(args, "pid")
        if pid is not None:
            config.pid = getint(pid)

        # Boolean/simple flags with defaults
        config.stock = self._safe_get_arg(args, "stock", False)
        noreconnect = self._safe_get_arg(args, "noreconnect", False)
        config.reconnect = not noreconnect
        config.uartloglevel = self._safe_get_arg(args, "uartloglevel", 2)

        # Optional string/path attributes
        payload = self._safe_get_arg(args, "payload")
        if payload is not None:
            config.payloadfile = payload

        appid = self._safe_get_arg(args, "appid")
        if appid is not None:
            try:
                config.appid = bytes.fromhex(appid)
            except (ValueError, TypeError):
                pass

        loader = self._safe_get_arg(args, "loader")
        if loader is not None:
            config.loader = loader

        # Address overrides with logging
        da_address = self._safe_get_arg(args, "da_address")
        if da_address is not None:
            config.chipconfig.da_payload_addr = getint(da_address)
            self.info("O:DA offset:\t\t\t" + da_address)

        brom_address = self._safe_get_arg(args, "brom_address")
        if brom_address is not None:
            config.chipconfig.brom_payload_addr = getint(brom_address)
            self.info("O:Payload offset:\t\t" + brom_address)

        watchdog_address = self._safe_get_arg(args, "watchdog_address")
        if watchdog_address is not None:
            wdt = self._safe_get_arg(args, "wdt")
            if wdt is not None:
                config.chipconfig.watchdog = getint(wdt)
                self.info("O:Watchdog addr:\t\t" + wdt)

        skipwdt = self._safe_get_arg(args, "skipwdt")
        if skipwdt is not None:
            config.skipwdt = skipwdt

        uart_address = self._safe_get_arg(args, "uart_address")
        if uart_address is not None:
            config.chipconfig.uart = getint(uart_address)
            self.info("O:Uart addr:\t\t" + uart_address)

        # Var1 config
        var1 = self._safe_get_arg(args, "var1")
        if var1 is not None:
            config.chipconfig.var1 = getint(var1)
            self.info("O:Var1:\t\t" + hex(config.chipconfig.var1))

        # Preloader file
        preloader = self._safe_get_arg(args, "preloader")
        if preloader is not None and os.path.exists(preloader):
            config.preloader_filename = preloader
            with open(config.preloader_filename, "rb") as f:
                config.preloader = f.read()

        # Remaining simple attribute mappings
        write_preloader = self._safe_get_arg(args, "write_preloader_to_file")
        if write_preloader is not None:
            config.write_preloader_to_file = write_preloader

        generatekeys = self._safe_get_arg(args, "generatekeys")
        if generatekeys is not None:
            config.generatekeys = generatekeys

        ptype = self._safe_get_arg(args, "ptype")
        if ptype is not None:
            config.ptype = ptype

        socid = self._safe_get_arg(args, "socid")
        if socid is not None:
            config.readsocid = socid

        crash = self._safe_get_arg(args, "crash")
        if crash is not None:
            config.enforcecrash = crash

        # GPT settings
        gpt_num_part_entries = self._safe_get_arg(args, "gpt_num_part_entries", 0)
        gpt_part_entry_size = self._safe_get_arg(args, "gpt_part_entry_size", 0)
        gpt_part_entry_start_lba = self._safe_get_arg(args, "gpt_part_entry_start_lba", 0)
        config.gpt_settings = GptSettings(gpt_num_part_entries, gpt_part_entry_size,
                                          gpt_part_entry_start_lba)


class Main(metaclass=LogBase):
    def __init__(self, args):
        self.__logger, self.info, self.debug, self.warning, self.error = logsetup(self, self.__logger,
                                                                                  args.loglevel, None)
        self.eh = None
        self.args = args
        if args.loglevel == logging.DEBUG:
            if not os.path.exists("logs"):
                os.mkdir("logs")

    @staticmethod
    def close():
        sys.exit(0)

    def cmd_stage(self, mtk, filename, stage2addr, stage2file, verifystage2):
        if filename is None:
            pc = PathConfig()
            stage1file = os.path.join(pc.get_payloads_path(), "generic_stage1_payload.bin")
        else:
            stage1file = filename
        if not os.path.exists(stage1file):
            self.error(f"Error: {stage1file} doesn't exist !")
            return False
        if stage2file is not None:
            if not os.path.exists(stage2file):
                self.error(f"Error: {stage2file} doesn't exist !")
                return False
        else:
            stage2file = os.path.join(mtk.pathconfig.get_payloads_path(), "stage2.bin")
        if mtk.preloader.init():
            mtk = mtk.crasher()
            if mtk.port.cdc.pid == 0x0003:
                plt = PLTools(mtk, self.__logger.level)
                self.info("Uploading stage 1")
                mtk.config.set_gui_status(mtk.config.tr("Uploading stage 1"))
                if plt.runpayload(filename=stage1file):
                    self.info("Successfully uploaded stage 1, sending stage 2")
                    mtk.config.set_gui_status(mtk.config.tr("Successfully uploaded stage 1, sending stage 2"))
                    with open(stage2file, "rb") as rr:
                        stage2data = rr.read()
                        while len(stage2data) % 0x200:
                            stage2data += b"\x00"
                    if stage2addr is None:
                        stage2addr = mtk.config.chipconfig.da_payload_addr
                        if stage2addr is None:
                            stage2addr = 0x201000

                    # ###### Send stage2
                    # magic
                    mtk.port.usbwrite(pack(">I", 0xf00dd00d))
                    # cmd write
                    mtk.port.usbwrite(pack(">I", 0x4000))
                    # address
                    mtk.port.usbwrite(pack(">I", stage2addr))
                    # length
                    mtk.port.usbwrite(pack(">I", len(stage2data)))
                    bytestowrite = len(stage2data)
                    pos = 0
                    while bytestowrite > 0:
                        size = min(bytestowrite, 1)
                        if mtk.port.usbwrite(stage2data[pos:pos + size]):
                            bytestowrite -= size
                            pos += size
                    # mtk.port.usbwrite(b"")
                    time.sleep(0.1)
                    flag = mtk.port.rdword()
                    if flag != 0xD0D0D0D0:
                        self.error(f"Error on sending stage2, size {hex(len(stage2data))}.")
                    self.info(f"Done sending stage2, size {hex(len(stage2data))}.")
                    mtk.config.set_gui_status(mtk.config.tr("Done sending stage 2"))
                    if verifystage2:
                        self.info("Verifying stage2 data")
                        rdata = b""
                        mtk.port.usbwrite(pack(">I", 0xf00dd00d))
                        mtk.port.usbwrite(pack(">I", 0x4002))
                        mtk.port.usbwrite(pack(">I", stage2addr))
                        mtk.port.usbwrite(pack(">I", len(stage2data)))
                        bytestoread = len(stage2data)
                        while bytestoread > 0:
                            size = min(bytestoread, 1)
                            rdata += mtk.port.usbread(size)
                            bytestoread -= size
                        flag = mtk.port.rdword()
                        if flag != 0xD0D0D0D0:
                            self.error("Error on reading stage2 data")
                        if rdata != stage2data:
                            self.error("Stage2 data doesn't match")
                            with open("rdata", "wb") as wf:
                                wf.write(rdata)
                        else:
                            self.info("Stage2 verification passed.")
                            mtk.config.set_gui_status(mtk.config.tr("Stage2 verification passed."))

                    # ####### Kick Watchdog
                    # magic
                    # mtk.port.usbwrite(pack("<I", 0xf00dd00d))
                    # cmd kick_watchdog
                    # mtk.port.usbwrite(pack("<I", 0x3001))

                    # ######### Jump stage1
                    # magic
                    mtk.port.usbwrite(pack(">I", 0xf00dd00d))
                    # cmd jump
                    mtk.port.usbwrite(pack(">I", 0x4001))
                    # address
                    mtk.port.usbwrite(pack(">I", stage2addr))
                    self.info("Done jumping stage2 at %08X" % stage2addr)
                    mtk.config.set_gui_status(mtk.config.tr("Done jumping stage2 at %08X" % stage2addr))
                    ack = unpack(">I", mtk.port.usbread(4))[0]
                    if ack == 0xB1B2B3B4:
                        self.info("Successfully loaded stage2")

    def cmd_peek(self, mtk, addr, length, preloader, filename):
        wwf = None
        if preloader is not None:
            if os.path.exists(preloader):
                daaddr, dadata = mtk.parse_preloader(preloader)
        if mtk.preloader.init():
            if mtk.config.target_config["daa"]:
                mtk = mtk.bypass_security()
        if mtk is not None:
            if preloader is not None:
                if os.path.exists(preloader):
                    daaddr, dadata = mtk.parse_preloader(preloader)
                    if mtk.preloader.send_da(daaddr, len(dadata), 0x100, dadata):
                        self.info(f"Sent preloader to {hex(daaddr)}, length {hex(len(dadata))}")
                        if mtk.preloader.jump_da(daaddr):
                            self.info(f"Jumped to pl {hex(daaddr)}.")
                            time.sleep(2)
                            config = MtkConfig(loglevel=self.__logger.level, gui=mtk.config.gui,
                                               guiprogress=mtk.config.guiprogress)
                            mtk = Mtk(loglevel=self.__logger.level, config=config,
                                      serialportname=mtk.port.serialportname)
                            res = mtk.preloader.init()
                            if not res:
                                self.error("Error on loading preloader")
                                return
                            else:
                                self.info("Successfully connected to pl.")
                                # mtk.preloader.get_hw_sw_ver()
                                # status=mtk.preloader.jump_to_partition(b"") # Do not remove !
                else:
                    self.error("Error on jumping to pl")
                    return
            self.info("Starting to read ...")
            dwords = length // 4
            if length % 4:
                dwords += 1
            if filename is not None:
                wwf = open(filename, "wb")
            sdata = b""
            pg = progress(total=addr + length, prefix='Progress:')
            length = dwords * 4
            pos = 0
            while dwords:
                size = min(512 // 4, dwords)
                if dwords == 1:
                    data = pack("<I", mtk.preloader.read32(addr + pos, size))
                else:
                    data = b"".join(int.to_bytes(val, 4, 'little') for val in mtk.preloader.read32(addr + pos, size))
                pg.update(len(data))
                sdata += data
                if filename is not None:
                    wwf.write(data)
                pos += len(data)
                dwords = (length - pos) // 4
            pg.done()
            if filename is None:
                print(hexlify(sdata).decode('utf-8'))
            else:
                wwf.close()
                self.info(f"Data from {hex(addr)} with size of {hex(length)} was written to " + filename)

    def _init_loglevel(self):
        """Initialize log level from args, defaulting to INFO."""
        try:
            if self.args.debugmode:
                loglevel = logging.DEBUG
                self.__logger.setLevel(logging.DEBUG)
            else:
                loglevel = logging.INFO
                self.__logger.setLevel(logging.INFO)
        except AttributeError:
            loglevel = logging.INFO
            self.__logger.setLevel(logging.INFO)
        return loglevel

    def _init_config(self, loglevel):
        """Create and configure MtkConfig from args."""
        loader = ArgHandler._safe_get_arg(self.args, "loader")
        if loader is not None and not os.path.exists(loader):
            print(f"Couldn't find loader {loader} :(")
            sys.exit(1)

        config = MtkConfig(loglevel=loglevel, gui=None, guiprogress=None)
        ArgHandler(self.args, config)
        self.eh = ErrorHandler()

        serialport = ArgHandler._safe_get_arg(self.args, "serialport")
        disable_internal_flash = ArgHandler._safe_get_arg(self.args, "disable_internal_flash", False)
        config.internal_flash = not disable_internal_flash
        config.auth = ArgHandler._safe_get_arg(self.args, "auth")
        config.cert = ArgHandler._safe_get_arg(self.args, "cert")

        return config, serialport

    def _init_mtk(self, config, loglevel, serialport):
        """Initialize the Mtk device connection and debug logging."""
        mtk = Mtk(config=config, loglevel=loglevel, serialportname=serialport)
        config.set_peek(mtk.daloader.peek)
        if mtk.config.debugmode:
            logfilename = os.path.join("logs", "log.txt")
            if os.path.exists(logfilename):
                os.remove(logfilename)
            fh = logging.FileHandler(logfilename, encoding='utf-8')
            self.__logger.addHandler(fh)
        self.debug(" ".join(sys.argv))
        mtk.config.preloader_filename = ArgHandler._safe_get_arg(self.args, "preloader")
        return mtk

    def _cmd_devices(self):
        """Handle the 'devices' command - list supported devices."""
        dev_filter = self.args.filter
        print("\n")
        from mtkclient.config.devicedb import supported_devices
        for device in supported_devices:
            if dev_filter is not None:
                if dev_filter.lower() not in device.lower():
                    continue
            info = f"{device}:\n" + "-" * len(device) + "\n"
            for infodev in supported_devices[device]:
                sinfo = supported_devices[device][infodev]
                info += f"\t{infodev}: {sinfo}\n"
            print(info)
        exit(0)

    def _cmd_script(self, mtk, loglevel, config, directory, parser):
        """Handle the 'script' command - run commands from a script file."""
        if not os.path.exists(self.args.script):
            self.error("Couldn't find script: " + self.args.script)
            self.close()
            return
        with open(self.args.script, "r") as f:
            commands = f.read().splitlines()
        da_handler = DaHandler(mtk, loglevel)
        mtk = da_handler.connect(mtk, directory)
        if mtk is None:
            return
        mtk = da_handler.configure_da(mtk)
        if mtk is not None:
            for rcmd in commands:
                self.args = parser.parse_args(rcmd.split(" "))
                ArgHandler(self.args, config)
                cmd = self.args.cmd
                da_handler.handle_da_cmds(mtk, cmd, self.args)
                sys.stdout.flush()
                sys.stderr.flush()
        else:
            self.close()

    def _cmd_multi(self, mtk, loglevel, config, directory, parser):
        """Handle the 'multi' command - run multiple semicolon-separated commands."""
        commands = self.args.commands.split(';')
        da_handler = DaHandler(mtk, loglevel)
        mtk = da_handler.connect(mtk, directory)
        if mtk is None:
            self.close()
            return
        mtk = da_handler.configure_da(mtk)
        if mtk is not None:
            for rcmd in commands:
                self.args = parser.parse_args(rcmd.split(" "))
                ArgHandler(self.args, config)
                cmd = self.args.cmd
                da_handler.handle_da_cmds(mtk, cmd, self.args)
                sys.stdout.flush()
                sys.stderr.flush()
        else:
            self.close()

    def _cmd_dumpbrom(self, mtk):
        """Handle the 'dumpbrom' command."""
        if mtk.preloader.init():
            rmtk = mtk.crasher()
            if rmtk is None:
                sys.exit(0)
            if rmtk.port.cdc.vid != 0xE8D and rmtk.port.cdc.pid != 0x0003:
                self.warning("We couldn't enter preloader.")
            filename = self.args.filename
            if filename is None:
                cpu = ""
                if rmtk.config.cpu != "":
                    cpu = "_" + rmtk.config.cpu
                filename = "brom" + cpu + "_" + hex(rmtk.config.hwcode)[2:] + ".bin"
            plt = PLTools(rmtk, self.__logger.level)
            plt.run_dump_brom(filename, self.args.ptype)
            rmtk.port.close()
        self.close()

    def _cmd_dumppreloader(self, mtk):
        """Handle the 'dumppreloader' command."""
        if mtk.preloader.init():
            rmtk = mtk.crasher()
            if rmtk is None:
                sys.exit(0)
            if rmtk.port.cdc.vid != 0xE8D or rmtk.port.cdc.pid != 0x0003:
                self.warning("We couldn't enter preloader.")
            plt = PLTools(rmtk, self.__logger.level)
            data, filename = plt.run_dump_preloader(self.args.ptype)
            if self.args.filename is not None:
                filename = self.args.filename
            if filename is None:
                filename = "preloader.bin"
            if data is not None:
                if filename == "":
                    if self.args.filename is not None:
                        filename = self.args.filename
                    else:
                        filename = "preloader.bin"
                with open(filename, 'wb') as wf:
                    wf.write(data)
                    self.info("Preloader dumped as: " + filename)
            rmtk.port.close()
        self.close()

    def _cmd_dumpsram(self, mtk):
        """Handle the 'dumpsram' command."""
        if mtk.preloader.init():
            rmtk = mtk.crasher()
            if rmtk is None:
                sys.exit(0)
            if rmtk.port.cdc.vid != 0xE8D and rmtk.port.cdc.pid != 0x0003:
                self.warning("We couldn't enter preloader.")
            filename = self.args.filename
            if filename is None:
                cpu = ""
                if rmtk.config.cpu != "":
                    cpu = "_" + rmtk.config.cpu
                filename = "sram" + cpu + "_" + hex(rmtk.config.hwcode)[2:] + ".bin"
            plt = PLTools(rmtk, self.__logger.level)
            plt.run_dump_brom(filename, self.args.ptype, loader="generic_sram_payload.bin")
            rmtk.port.close()
        self.close()

    def _cmd_brute(self, mtk):
        """Handle the 'brute' command."""
        self.info("Kamakiri / DA Bruteforce run")
        rmtk = Mtk(config=mtk.config, loglevel=self.__logger.level, serialportname=mtk.port.serialportname)
        plt = PLTools(rmtk, self.__logger.level)
        plt.runbrute(self.args)
        self.close()

    def _cmd_crash(self, mtk):
        """Handle the 'crash' command."""
        if mtk.preloader.init():
            mtk = mtk.crasher(mode=getint(self.args.mode))
        mtk.port.close()
        self.close()

    def _cmd_plstage(self, mtk, loglevel):
        """Handle the 'plstage' command."""
        if mtk.config.chipconfig.pl_payload_addr is not None:
            plstageaddr = mtk.config.chipconfig.pl_payload_addr
        else:
            plstageaddr = 0x40001000  # 0x40200000  # 0x40001000
        if self.args.pl is None:
            plstage = os.path.join(mtk.pathconfig.get_payloads_path(), "pl.bin")
        else:
            plstage = self.args.pl
        if os.path.exists(plstage):
            with open(plstage, "rb") as rf:
                rf.seek(0)
                if os.path.basename(plstage) != "pl.bin":
                    pldata = mtk.patch_preloader_security_da1(rf.read())
                else:
                    pldata = rf.read()
        if mtk.preloader.init():
            if mtk.config.target_config["daa"]:
                mtk = mtk.bypass_security()
                if mtk is None:
                    self.error("Error on bypassing security, aborting")
                    return
            self.info("Connected to device, loading")
        else:
            self.error("Couldn't connect to device, aborting.")

        if mtk.config.is_brom and mtk.config.preloader is None and os.path.basename(plstage) == "pl.bin":
            self.warning("PL stage needs preloader, please use --preloader option. " +
                         "Trying to dump preloader from ram.")
            plt = PLTools(mtk=mtk, loglevel=self.__logger.level)
            dadata, filename = plt.run_dump_preloader(self.args.ptype)
            mtk.config.preloader = mtk.patch_preloader_security_da1(dadata)

        if mtk.config.preloader_filename is not None:
            self.info("Using custom preloader : " + mtk.config.preloader_filename)
            mtk.preloader.setreg_disablewatchdogtimer(mtk.config.hwcode, mtk.config.hwver)
            daaddr, dadata = mtk.parse_preloader(mtk.config.preloader_filename)
            dadata = mtk.config.preloader = mtk.patch_preloader_security_da1(dadata)
            if mtk.preloader.send_da(daaddr, len(dadata), 0x100, dadata):
                self.info(f"Sent preloader to {hex(daaddr)}, length {hex(len(dadata))}")
                if mtk.preloader.jump_da(daaddr):
                    self.info(f"PL Jumped to daaddr {hex(daaddr)}.")
                    mtk = Mtk(config=mtk.config, loglevel=self.__logger.level)
                    if self.args.metamode is not None:
                        time.sleep(1)
                        meta = META(mtk, loglevel)
                        if meta.init(metamode=self.args.metamode, display=False):
                            self.info(f"Successfully set meta mode : {self.args.metamode}")
                        mtk.port.close()
                        self.close()
                        return
                    if (self.args.startpartition is not None or self.args.offset is not None or
                            self.args.length is not None):
                        time.sleep(1)
                        res = mtk.preloader.init()
                        if not res:
                            self.error("Error on loading preloader")
                            return
                        else:
                            self.info("Successfully connected to pl")
                    else:
                        mtk.port.close()
                        time.sleep(3)
                        self.info("Keep pressed power button to boot.")
                        self.close()
                        return

                    if self.args.startpartition is not None:
                        partition = self.args.startpartition
                        self.info("Booting to : " + partition)
                        # mtk.preloader.send_partition_data(partition, mtk.patch_preloader_security(pldata))
                        status = mtk.preloader.jump_to_partition(partition)  # Do not remove !

                    if self.args.offset is not None and self.args.length is not None:
                        offset = getint(self.args.offset)
                        length = getint(self.args.length)
                        rlen = min(0x200, length)
                        status = 0
                        mtk.preloader.get_hw_sw_ver()
                        if self.args.filename is not None:
                            with open(self.args.filename, "wb") as wf:
                                for pos in range(offset, offset + length, rlen):
                                    print("Reading pos %08X" % pos)
                                    res = mtk.preloader.read32(pos, rlen // 4)
                                    wf.write(b"".join([pack("<I", val) for val in res]))
                        else:
                            for pos in range(offset, offset + length, rlen):
                                print("Reading pos %08X" % pos)
                                res = mtk.preloader.read32(pos, rlen // 4)
                                if not res:
                                    break
                                print(hexlify(b"".join([pack("<I", val) for val in res])).decode('utf-8'))

                        # for val in res:
                        #    print(hex(val))
                        if status != 0x0:
                            self.error("Error on jumping to partition: " + self.eh.status(status))
                        else:
                            self.info("Jumping to partition ....")
                        return
                    mtk.port.close()
                    sys.exit(0)
        if mtk.preloader.send_da(plstageaddr, len(pldata), 0x100, pldata):
            self.info(f"Sent stage2 to {hex(plstageaddr)}, length {hex(len(pldata))}")
            mtk.preloader.get_hw_sw_ver()
            if mtk.preloader.jump_da(plstageaddr):
                self.info(f"Jumped to stage2 at {hex(plstageaddr)}.")
                if os.path.basename(plstage) == "pl.bin":
                    ack = unpack(">I", mtk.port.usbread(4))[0]
                    if ack == 0xB1B2B3B4:
                        self.info("Successfully loaded stage2")
                        return
                else:
                    self.info("Successfully loaded stage2, dis- and reconnect usb cable")
                    time.sleep(2)
                    ack = unpack(">I", mtk.port.usbread(4))[0]
                    mtk.port.close()
                    return
            else:
                self.error("Error on jumping to pl")
                return
        else:
            self.error("Error on sending pl")
            return
        self.close()

    def _cmd_peek_dispatch(self, mtk):
        """Handle the 'peek' command dispatch."""
        addr = getint(self.args.address)
        length = getint(self.args.length)
        preloader = self.args.preloader
        filename = self.args.filename
        self.cmd_peek(mtk=mtk, addr=addr, length=length, preloader=preloader, filename=filename)
        self.close()

    def _cmd_stage_dispatch(self, mtk):
        """Handle the 'stage' command dispatch."""
        filename = self.args.filename
        stage2addr = self.args.stage2addr
        if self.args.stage2addr is not None:
            stage2addr = getint(self.args.stage2addr)
        stage2file = self.args.stage2
        verifystage2 = self.args.verifystage2
        self.cmd_stage(mtk=mtk, filename=filename, stage2addr=stage2addr, stage2file=stage2file,
                       verifystage2=verifystage2)
        self.close()

    def _cmd_gettargetconfig(self, mtk):
        """Handle the 'gettargetconfig' command."""
        if mtk.preloader.init():
            self.info("Getting target info...")
            mtk.preloader.get_target_config()
        mtk.port.close()
        self.close()

    def _cmd_logs(self, mtk):
        """Handle the 'logs' command."""
        filename = self.args.filename if self.args.filename is not None else "log.txt"
        self.cmd_log(mtk=mtk, filename=filename)
        mtk.port.close()
        self.close()

    def _cmd_meta(self, mtk, loglevel):
        """Handle the 'meta' command."""
        meta = META(mtk, loglevel)
        if self.args.metamode is None:
            self.error("You need to give a metamode as argument ex: " + metamodes)
        else:
            if meta.init(metamode=self.args.metamode, display=True):
                self.info(f"Successfully set meta mode : {self.args.metamode}")
        mtk.port.close()
        self.close()

    def _cmd_meta2(self, mtk, loglevel):
        """Handle the 'meta2' command."""
        meta = META(mtk, loglevel)
        if meta.init_wdg(display=True):
            self.info("Successfully set meta mode :)")
        mtk.port.close()
        self.close()

    def _cmd_da_default(self, mtk, cmd, loglevel, directory):
        """Handle DA/Flash commands (default command handler)."""
        da_handler = DaHandler(mtk, loglevel)
        mtk.offset = 0
        offset = ArgHandler._safe_get_arg(self.args, "offset")
        if offset is not None:
            try:
                mtk.offset = int(offset, 16)
            except (ValueError, TypeError):
                pass
        mtk.length = 0x400000
        length = ArgHandler._safe_get_arg(self.args, "length")
        if length is not None:
            try:
                mtk.length = int(length, 16)
            except (ValueError, TypeError):
                pass
        mtk.step = 0x1000
        step = ArgHandler._safe_get_arg(self.args, "step")
        if step is not None:
            try:
                mtk.step = int(step, 16)
            except (ValueError, TypeError):
                pass
        mtk = da_handler.connect(mtk, directory)
        if mtk is not None:
            mtk = da_handler.configure_da(mtk)
            if mtk is not None:
                self.info("Handling da commands ...")
                da_handler.handle_da_cmds(mtk, cmd, self.args)
                mtk.port.close()
        self.close()

    def run(self, parser):
        loglevel = self._init_loglevel()
        config, serialport = self._init_config(loglevel)
        mtk = self._init_mtk(config, loglevel, serialport)
        directory = ArgHandler._safe_get_arg(self.args, "directory", ".")
        cmd = self.args.cmd

        # Command dispatch table for simple commands
        command_handlers = {
            "devices": lambda: self._cmd_devices(),
            "script": lambda: self._cmd_script(mtk, loglevel, config, directory, parser),
            "multi": lambda: self._cmd_multi(mtk, loglevel, config, directory, parser),
            "dumpbrom": lambda: self._cmd_dumpbrom(mtk),
            "dumppreloader": lambda: self._cmd_dumppreloader(mtk),
            "dumpsram": lambda: self._cmd_dumpsram(mtk),
            "brute": lambda: self._cmd_brute(mtk),
            "crash": lambda: self._cmd_crash(mtk),
            "plstage": lambda: self._cmd_plstage(mtk, loglevel),
            "peek": lambda: self._cmd_peek_dispatch(mtk),
            "stage": lambda: self._cmd_stage_dispatch(mtk),
            "payload": lambda: self.cmd_payload(mtk=mtk, payloadfile=ArgHandler._safe_get_arg(self.args, 'payload')),
            "gettargetconfig": lambda: self._cmd_gettargetconfig(mtk),
            "logs": lambda: self._cmd_logs(mtk),
            "meta": lambda: self._cmd_meta(mtk, loglevel),
            "meta2": lambda: self._cmd_meta2(mtk, loglevel),
        }

        handler = command_handlers.get(cmd)
        if handler is not None:
            handler()
        else:
            self._cmd_da_default(mtk, cmd, loglevel, directory)

    def cmd_log(self, mtk, filename):
        if mtk.preloader.init():
            self.info("Getting target logs...")
            try:
                logs = mtk.preloader.get_brom_log_new()
            except Exception:
                logs = mtk.preloader.get_brom_log()
            if logs != b"":
                with open(filename, "wb") as wf:
                    wf.write(logs)
                    self.info(f'Successfully wrote logs to "{filename}"')
            else:
                self.info("No logs found.")

    def cmd_payload(self, mtk, payloadfile):
        if mtk.preloader.init():
            mtk = mtk.crasher()
            plt = PLTools(mtk, self.__logger.level)
            if payloadfile is None:
                if mtk.config.chipconfig.loader is None:
                    payloadfile = os.path.join(mtk.pathconfig.get_payloads_path(), "generic_patcher_payload.bin")
                else:
                    payloadfile = os.path.join(mtk.pathconfig.get_payloads_path(), mtk.config.chipconfig.loader)
            plt.runpayload(filename=payloadfile)
            if self.args.metamode:
                mtk.port.run_handshake()
                mtk.preloader.jump_bl()
                mtk.port.close(reset=True)
                meta = META(mtk, self.__logger.level)
                if meta.init(metamode=self.args.metamode, display=True):
                    self.info(f"Successfully set meta mode : {self.args.metamode}")
        mtk.port.close(reset=True)
