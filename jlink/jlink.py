import logging
import os
import platform
import re
import sys
import subprocess
import threading
import time
import tempfile

# Setup local logger
logger = logging.getLogger(__name__)


class JLink:
    def __init__(self, connected, device, interface, speed, jlink_exe=None, jlink_path=""):
        """
        JLink interface class.

        Class for interfacing with Segger JLink USB interface.

        Keyword arguments:
        connected -- target specific messages returned when target has been successfully detected
        device -- target device name
        speed -- speed of connection in kHz
        jlink_exe -- name of JLink executable (deafult None = determined by OS)
        jlink_path -- path to JLink executable (default blank = assumes exe is in system path)

        Example usage:

        from jlink import JLink
        interface = JLink("Cortex-M3 r2p0, Little endian", "LPC1343", "swd", "1000", jlink_path="/home/pi/jlink/jlink_linux")
        if interface.is_connected():
            interface.program(["dummy.hex"])
        """
        self._connected = connected

        # Get JLink executable name
        if jlink_exe is None:
            system = platform.system()
            if system == "Linux":
                jlink_exe = "JLinkExe"
            elif system == "Windows":
                jlink_exe = "JLink.exe"
            else:
                raise JLinkError("Unsupported system: {0}".format(system))
        
        # Construct full path to JLinkExe tool
        self._jlink_path = os.path.join(jlink_path, jlink_exe)
        logger.info("Using path to JLinkExe: {0}".format(self._jlink_path))

        # Construct command line parameters
        temp_params = "-device {0} -if {1} -speed {2}".format(device, interface, speed)
        self._jlink_params = []
        self._jlink_params.extend(temp_params.split())
        logger.info("JLinkExe parameters: {0}".format(temp_params))

        # Check that specified executable exists
        self._test_jlinkexe()

    def _test_jlinkexe(self):
        """Check if JLinkExe is found at the specified path"""

        # Spawn JLinkExe process and raise an exception if not found
        args = [self._jlink_path]
        args.append("?")
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            process.wait()
            logger.info("Success")
        except OSError:
            raise JLinkError("'{0}' missing. Ensure J-Link folder is in your system path.".format(self._jlink_path))

    def run_script(self, filename, timeout=60):
        """Run specified JLink script. Returns output of the JLinkExe process. If execution takes longer than specified amount of seconds, process is killed and an exception is thrown. Setting timeout to None disables the timeout check."""

        # Spawn JLinkExe process and capture its output
        args = [self._jlink_path]
        args.extend(self._jlink_params)
        args.append(filename)
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if timeout is not None:
                def timeout_exceeded(p):
                    # Stop JLinkExe process
                    p.kill()
                    raise JLinkError("JLink process exceeded timeout!")

                timer = threading.Timer(timeout, timeout_exceeded, [process])
                timer.start()
            # Capture output from the process
            output, err = process.communicate()
            if timeout is not None:
                # Stop timeout timer since communicate call returned
                timer.cancel()

            return output
        except:
            logger.debug("JLink response: {0}".format(output))
            raise JLinkError("Something went wrong when trying to execute the provided JLink script")

    def run_commands(self, commands, timeout=60):
        """Run the provided list of commands. The provided commands should be a list of strings, which can be executed by JLink. If execution takes longer than specified amount of seconds, process is killed and an exception is thrown. Setting timeout to None disables the timeout check."""

        # Create temporary file for the run_script method
        temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
        commands = "\n".join(commands)
        temp_file.write(commands)
        temp_file.close()
        logger.debug("Temporary script file name: {0}".format(temp_file.name))
        logger.debug("Running JLink commands: {0}".format(commands))
        return self.run_script(temp_file.name, timeout)

    def is_connected(self):
        """Returns true if the specified device is connected to the programmer. Device needs to be a string recognised by JLink, interface can be either S for SWD or J for JTAG."""

        output = self.run_commands(["connect", "q"], timeout=5)
        return self._connected.encode() in output

    def erase(self):
        """Erase entire flash of the target."""

        commands = ["r", "erase", "r", "q"]
        self.run_commands(commands)

    def program(self, hex_files=[], bin_files=[]):
        """Program target with specified list of hex and/or bin files.
        hex_files is a list of paths to .hex files.
        bin_files is a list of tuples with the first value being the path to the .bin file and the second value being the integer starting address for the bin files"""

        # Construct a list of commands
        commands = ["r"]

        # Add each hex file
        for f in hex_files:
            f = os.path.abspath(f)
            commands.append('loadfile "{0}"'.format(f))

        # Add each bin file
        for f, addr in bin_files:
            f = os.path.abspath(f)
            commands.append('loadbin "{0}" 0x{1:08X}'.format(f, addr))

        # Add post programming commands
        commands.extend(["r", "g", "q"])

        # Run commands
        output = self.run_commands(commands)
        # Check if programming succeeded
        pass_messages = ["J-Link: Flash download: Total time needed:", "O.K."]
        write_failed = "Writing target memory failed.".encode()
        flash_match = "J-Link: Flash download: Flash download skipped. Flash contents already match".encode()

        if write_failed in output:
            logger.info("Writing flash failed")
            return -1
        elif flash_match in output:
            logger.info("Target already programmed")
            return 0
        elif all(message.encode() in output for message in pass_messages):
            logger.info("Target programmed")
            return 0
        else:
            logger.info("Programming target failed")
            return -1
