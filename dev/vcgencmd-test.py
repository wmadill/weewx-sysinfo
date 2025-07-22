PROG = "vcgencmd"
TESTED_DATE = "Aug 30 2024 19:17:39"

import sys
import shutil
import subprocess
import datetime
import os
import resource
import re

# Make sure running Linux
path = shutil.which("uname")
if path is None:
  print("log.error: cannot find 'uname'. Not running Linux")
  sys.exit()
print("uname is at %s" % path)

cmd = [path]
cmd.extend(["-s"])
vcmd = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = vcmd.stdout.decode()
print(output)
if output.find("Linux") >= 0:
    print("Running Linux")
else:
    print("not running Linux; skipping")
    sys.exit()

# Make sure running Debia
cmd = [path]
cmd.extend(["-v"])
vcmd = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = vcmd.stdout.decode()
print(output)
if output.find("Debian") >= 0:
    print("Running Debian")
else:
    print("Not running Debian")
    sys.exit()

# on a Raspberry Pi

# cat /proc/cpuinfo | grep "Raspberry Pi" returns something
cmd = ["/usr/bin/grep", "Model", "/proc/cpuinfo"]
vcmd = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = vcmd.stdout.decode()
print("Model: %s" % output)
sys.exit()
cmd = ["cat"]
cmd.extend(["/proc/cpuinfo"])
vcmd = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = vcmd.stdout.decode()
print(output)
re.search

# Look for PROG
# I can't get it to throw an exception but leaving this here
# to be safe
try:
    path = shutil.which(PROG)
except e:
    print("log.error: cannot find %s. %s" % (PROG, e))
    sys.exit()

if path is None:
    print("log.error: No path to %s" % PROG)
    sys.exit()
else:
    print("log.debug: path: %s" % path)

cmd = [path, "commands"]
print (cmd)
vcmd = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = vcmd.stdout.decode()
if output.find("Can't open device file") >= 0:
    # Test result for "Can't open device file:" on line one
    # If so...
    print("log.error: User needs to be in 'video' group")
    sys.exit()

### FIXME need better message
print("log.debug: processing vcgencmds")

# Check verstion
###This may not work as expected since we only check against the
# version date of the vcgencmd executable on my rpi. The version format
# may change in the future, and other versions (past or future) may
# (or may not) work.

###FIXME in weewx extension version of this code, either have a 
# way to set the TESTED_DATE for other versions that work or
# disable the test

# Convert the date-time line of the tested version of vcgencmd to datetime
tested_dt = datetime.datetime.strptime(TESTED_DATE, "%b %d %Y %H:%M:%S")
#print("tested_dt: %s" % tested_dt)

# Get the same from the current version
cmd = [path, "version"]
vcmd = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = vcmd.stdout.decode()
lines = output.splitlines()
first_line = lines[0].strip()
current_version_dt = datetime.datetime.strptime(first_line, "%b %d %Y %H:%M:%S")
#print("current_version_dt: %s" % current_version_dt)

if (current_version_dt < tested_dt):
    print("log.warning: current version vcgencmd is older than tested version")
elif (current_version_dt > tested_dt):
    print("log.debug: current version vcgencmd is newer than tested version")

#sys.exit()

# Create dictionary of desired values

# Get static numbers
# cpu type, memory split, number cores, clock rate
# lscpu
# grep CPU(s) for number of cores
# grep CPU max MHz for clock rate
# grep "Model name" for chip model, "Model" for model version, "Vendor ID" for 
#  chip design
# grep L1d: , L1i, (multiply by 4 or say each core has this), L2

# rpi model
cmd = ["/usr/bin/grep", "Model", "/proc/cpuinfo"]
x = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
output = x.stdout.decode()
print("Model: %s" % output)

# run expeiment with /proc numbers, free -m, and mem_size etc
# grep /proc/meminfo (in 1K)

# from tk
print("Tom version")
pid = os.getpid()
procfile = "/proc/%s/statm" % pid
try:
    mem_tuple = open(procfile).read().split()
except (IOError, ):
    print("procfile error")
    sys.exit()
         
page_size = resource.getpagesize()
# Unpack the tuple:
(size, resident, share, text, lib, data, dt) = mem_tuple

mb = 1024 * 1024
x = int(page_size) / mb
mem_size = float(size) * x
print("Mem size: %s" % mem_size)
mem_resident = float(resident) * x
print("Mem resident: %s" % mem_resident)
mem_share = float(share) * x
print("Mem share: %s" % mem_share)
sys.exit()

# free --kibi




# vcgencmd measure_volts core (or sdram_c,i,p?)
# " measure_temp
# " get_mem arm/gpu
