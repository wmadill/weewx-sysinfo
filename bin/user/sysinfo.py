#
# Copyright 2013-2013 Matthew Wall
# Further copyright 2024 Bill Madill

"""weewx module that records computer and WeeWX information.

Installation

Put this file in the bin/user directory.

Prerequisites
On a Raspberry Pi, the CPU temperature is retrieved using the
"vcgencmd" program installed with the Raspberry Pi OS. In order to
use the program, the user running weewxd has to be in the video 
group.

Check to see if the user is already in the video group by
entering at the command line:
  groups

If not, add the user by entering:
  sudo usermod -aG video <username>

If the program cannot be found or weewx is running on different
hardware, CPU temp and perhaps other information will not be
available.

Configuration

Add the following to weewx.conf:

[SystemInfo]
    data_binding = sysinfo_binding

[DataBindings]
    [[sysinfo_binding]]
        database = sysinfo_sqlite
        manager = weewx.manager.DaySummaryManager
        table_name = archive
        schema = user.sysinfo.schema

[Databases]
    [[sysinfo_sqlite]]
        database_name = sysinfo.sdb
        database_type = SQLite

[Engine]
    [[Services]]
        archive_services = ..., user.sysinfo.SystemInfo
"""
# import sys
import shutil
import subprocess

import logging
import os
import time
import resource

import weedb
import weewx.manager
from weeutil.weeutil import to_int
from weewx.engine import StdService
from weewx.cheetahgenerator import SearchList

import datetime
from weewx.tags import TimespanBinder
from weeutil.weeutil import TimeSpan

VERSION = "1.0"

log = logging.getLogger(__name__)

schema = [
    ('dateTime', 'INTEGER NOT NULL PRIMARY KEY'),
    ('usUnits', 'INTEGER NOT NULL'),
    ('interval', 'INTEGER NOT NULL'),
    ('mem_size', 'INTEGER'),
    ('mem_rss', 'INTEGER'),
    ('mem_share', 'INTEGER'),
]

class SystemInfo(StdService):

    def __init__(self, engine, config_dict):
        super(SystemInfo, self).__init__(engine, config_dict)

        d = config_dict.get('SystemInfo', {})
        self.max_age = to_int(d.get('max_age', 2592000))
        self.page_size = resource.getpagesize()

        # get the database parameters we need to function
        binding = d.get('data_binding', 'sysinfo_binding')
        self.dbm = self.engine.db_binder.get_manager(data_binding=binding,
                                                     initialize=True)

        # be sure database matches the schema we have
        dbcol = self.dbm.connection.columnsOf(self.dbm.table_name)
        dbm_dict = weewx.manager.get_manager_dict_from_config(config_dict, binding)
        memcol = [x[0] for x in dbm_dict['schema']]
        if dbcol != memcol:
            raise Exception('sysinfo schema mismatch: %s != %s' % (dbcol, memcol))

        ##FIXME##
        # Check is /usr/bin/vcgeninfo is executable and if not, log
        # a debug message and set something to ensure it's values are
        #run
        self.last_ts = None
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def shutDown(self):
        try:
            self.dbm.close()
        except weedb.DatabaseError:
            pass

    def new_archive_record(self, event):
        """save data to database then prune old records as needed"""
        now = int(time.time() + 0.5)
        delta = now - event.record['dateTime']
        if delta > event.record['interval'] * 60:
            log.debug("Skipping record: time difference %s too big" % delta)
            return
        if self.last_ts is not None:
            self.save_data(self.get_data(now, self.last_ts))
        self.last_ts = now
        if self.max_age is not None:
            self.prune_data(now - self.max_age)

    def save_data(self, record):
        """save data to database"""
        self.dbm.addRecord(record)

    def prune_data(self, ts):
        """delete records with dateTime older than ts"""
        sql = "delete from %s where dateTime < %d" % (self.dbm.table_name, ts)
        self.dbm.getSql(sql)
        try:
            self.dbm.getSql('vacuum')
        except weedb.DatabaseError:
            pass

    def get_data(self, now_ts, last_ts):
        record = {
            'dateTime' : now_ts,
            'usUnits' : weewx.US,
            'interval' : int((now_ts - last_ts) / 60.0)
        }
        try:
            pid = os.getpid()
            procfile = "/proc/%s/statm" % pid
            try:
                mem_tuple = open(procfile).read().split()
            except (IOError, ):
                return

            # Unpack the tuple:
            (size, resident, share, text, lib, data, dt) = mem_tuple

        except (ValueError, IOError, KeyError) as e:
            log.error('memory_info failed: %s' % e)

        mb = 1024 * 1024
        record['mem_size']  = float(size)     * self.page_size / mb 
        record['mem_rss']   = float(resident) * self.page_size / mb
        record['mem_share'] = float(share)    * self.page_size / mb

        ##FIXME##
        # If vcgeninfo available:
        # vcgencmd  get_config total_mem     (total memory)
        # vcgencmd  get_mem arm     (arm-addressable memory)
        # vcgencmd  get_mem gpu     (gpu-addressable  memory)
        # vcgencmd throttling status (log if not zero)
        # vcgencmd measure_temp      (current CPU temp)
        # vcgencmd measure_volts core/sdram_c/sdram_i/sdram_p (?)

        return record

# Gather OS information
class OSInfo:
    def __init__(self):
        # Validate OS
        # Note: this only supports Debian so this code is overly picky but
        # it would be convenient place to support other OSes

        self.os_name = None
        self.os_version = None
        self.os_codename = None

        ###FIXME###
        # This is pretty primitive--later lines with same keyword will overwrite
        # the earlier ones. I need to decide if this is a real problem.
        #
        # Also need to test the file not found error and make sure it gets
        # handled so running on a non-Linux system will know what happened.
        # Maybe stuff an error in to the os_* variables.
        #
        # One more thing: want to display the specific dotted release number which is
        # in /etc/debian_version
        try:
            with open('/etc/os-release', 'r') as fp:
                lines = fp.readlines()
                for line in lines:
                    [key, val] = line.split('=', 1)
                    val = val.strip()
                    if key == 'NAME':
                        self.os_name = val.strip('"')
                    elif key == 'VERSION_CODENAME':
                        self.os_codename = val

        except FileNotFoundError:
            print('os-release fail')
            sys.exit()

        try:
            with open('/etc/debian_version', 'r') as fp:
                self.os_version = fp.read().strip()
        except FileNotFoundError:
            print('os_version fail')
            sys.exit()

# Gather CPU information
class CPUInfo:
    def __init__(self):
        self.cpu_type = None

        cmd = ['/usr/bin/grep', 'Model', '/proc/cpuinfo']
        vcmd = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output = vcmd.stdout.decode()
        # output is something like
        # "Model\t\t: Raspberry Pi 4 Model 0 Rev 1.5"
        splits = output.split(':')
        # print(splits)
        # CPU info in right-hand split
        cpu_info = splits[1].strip()

        # Confirm it is Raspberry Pi
        if not cpu_info.startswith('Raspberry Pi'):
            print("not an rPi")
            sys.exit()

        cpu_parts = cpu_info.partition('Model')
        if cpu_parts[1] == '':
            # log some error
            self.cpu_type = cpu_info
            self.cpu_model = ''
        else:
            self.cpu_type = cpu_parts[0]
            self.cpu_model = cpu_parts[1] + cpu_parts[2]

        # Total memory
        # SD card size

class SystemInfoTags(SearchList):
    """Bind memory varialbes to database records"""

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        self.formatter = generator.formatter
        self.converter = generator.converter
        self.skin_dict = generator.skin_dict
        sd = generator.config_dict.get('SystemInfo', {})
        ##FIXME## check if binding defined!
        self.binding = sd.get('data_binding', '')

    def osinfo(self):
        return OSInfo()

    def cpuinfo(self):
        return CPUInfo()

    def prevday(self):
        return self.getvals(1)

    def prevweek(self):
        return self.getvals(7)
    
    def prevmonth(self):
        return self.getvals(30)
    
    def prevyear(self):
        return self.getvals(365)
    
    def getvals(self, numdays):
        # Create a TimespanBinder object for the last seven days. First,
        # calculate the time at midnight, seven days ago. The variable week_dt 
        # will be an instance of datetime.date.
        days_dt = datetime.date.fromtimestamp(self.timespan.stop) \
                  - datetime.timedelta(days = numdays)
        # Convert it to unix epoch time:
        days_ts = time.mktime(days_dt.timetuple())
        # Form a TimespanBinder object, using the time span we just
        # calculated:
        return TimespanBinder(TimeSpan(days_ts, self.timespan.stop),
                                         self.db_lookup,
                                         context='week',
                                         data_binding=self.binding,
                                         formatter=self.formatter,
                                         converter=self.converter,
                                         skin_dict=self.skin_dict)

    def get_extension_list(self, timespan, db_lookup):
        self.timespan = timespan
        self.db_lookup = db_lookup


        # Gather data

        # Set static values
        self.version = VERSION
        self.cpu_type = "CPU type goes here"
        self.cpu_model = "CPU model goes here"

        # Set rPi values

        #### TEST ####
        self.cpu_type_test = "cpu_type_test value"

        search_list_extension = {'sysinfo': self}
        return [search_list_extension]

# what follows is a basic unit test of this module.  to run the test:
#
# cd ~/weewx-data
# PYTHONPATH=bin python bin/user/sysinfo.py
#
if __name__ == "__main__":
    from weewx.engine import StdEngine
    import weeutil.logger
    import weewx

    weewx.debug = 1
    weeutil.logger.setup('sysinfo')

    config = {
        'Station': {
            'station_type': 'Simulator',
            'altitude': [0, 'foot'],
            'latitude': 0,
            'longitude': 0},
        'Simulator': {
            'driver': 'weewx.drivers.simulator',
            'mode': 'simulator'},
        'SystemInfo': {
            'data_binding': 'sysinfo_binding',
            'process': 'sysinfo'},
        'DataBindings': {
            'sysinfo_binding': {
                'database': 'sysinfo_sqlite',
                'manager': 'weewx.manager.DaySummaryManager',
                'table_name': 'archive',
                'schema': 'user.sysinfo.schema'}},
        'Databases': {
            'sysinfo_sqlite': {
                'database_name': 'sysinfo.sdb',
                'database_type': 'SQLite'}},
        'DatabaseTypes': {
            'SQLite': {
                'driver': 'weedb.sqlite',
                'SQLITE_ROOT': 'archive'}},
        'Engine': {
            'Services': {
                'archive_services': 'user.sysinfo.SystemInfo'}},
    }

    # Logged entries are in syslog. View with journalctl --grep=sysinfo

    eng = StdEngine(config)
    svc = SystemInfo(eng, config)

    nowts = lastts = int(time.time())

    loop = 0
    try:
        while True:
            rec = svc.get_data(nowts, lastts)
            print(rec)
            svc.save_data(rec)
            loop += 1
            if loop >= 3:
                break
            time.sleep(5)
            lastts = nowts
            nowts = int(time.time()+0.5)
    except:
        pass
