# jlink-python
Simple python module that can interface with Segger JLink using their official JLink executable on Windows and Linux.

To try it out:

```python
import jlink
interface = JLink("Cortex-M3 r2p0, Little endian", "LPC1343", "swd", "1000", jlink_path="/home/pi/jlink/jlink_linux")
if interface.is_connected():
    interface.program(["dummy.hex"])
```

JLink tool needs to be installed on your machine. Either provide a full path (without the executable bit), or leave it blank if it is setup in your OS's PATH.

The default names for executables are as follows:

```
Linux: JLinkExe
Windows: JLink.exe
 