# Copyright 2013-2013 Matthew Wall
# Further copyright 2024 Bill Madill

"""weewx module that records computer and WeeWX information.

Installation

Put this file in the bin/user directory.


Configuration

Add the following to weewx.conf:

[SystemStatistics]
    data_binding = sysstat_binding
    ##FIXME## add all the desired filesystems for sizing

[DataBindings]
    [[sysstat_binding]]
        database = sysstat_sqlite
        manager = weewx.manager.DaySummaryManager
        table_name = archive
        schema = user.sysstat.schema

[Databases]
    [[sysstat_sqlite]]
        database_name = sysstat.sdb
        database_type = SQLite

[Engine]
    [[Services]]
        archive_services = ..., user.sysstat.SystemStatistics
"""

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

VERSION = "0.5"

log = logging.getLogger(__name__)

schema = [
    ('dateTime', 'INTEGER NOT NULL PRIMARY KEY'),
    ('usUnits', 'INTEGER NOT NULL'),
    ('interval', 'INTEGER NOT NULL'),
    ('mem_size', 'INTEGER'),
    ('mem_rss', 'INTEGER'),
    ('mem_share', 'INTEGER'),
]

class SystemStatistics(StdService):

    def __init__(self, engine, config_dict):
        super(SystemStatistics, self).__init__(engine, config_dict)

        d = config_dict.get('SystemStatistics', {})
        self.max_age = to_int(d.get('max_age', 2592000))
        self.page_size = resource.getpagesize()

        # get the database parameters we need to function
        binding = d.get('data_binding', 'sysstat_binding')
        self.dbm = self.engine.db_binder.get_manager(data_binding=binding,
                                                     initialize=True)

        # be sure database matches the schema we have
        dbcol = self.dbm.connection.columnsOf(self.dbm.table_name)
        dbm_dict = weewx.manager.get_manager_dict_from_config(config_dict, binding)
        memcol = [x[0] for x in dbm_dict['schema']]
        if dbcol != memcol:
            raise Exception('sysstat schema mismatch: %s != %s' % (dbcol, memcol))

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

        return record

class SystemStatisticsVariables(SearchList):
    """Bind memory varialbes to database records"""

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        self.formatter = generator.formatter
        self.converter = generator.converter
        self.skin_dict = generator.skin_dict
        sd = generator.config_dict.get('SystemStatistics', {})
        ##FIXME## check if binding defined!
        self.binding = sd.get('data_binding', '')

    def version(self):
        return VERSION

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

        return [{'sys_stat': self}]

# what follows is a basic unit test of this module.  to run the test:
#
# cd ~/weewx-data
# PYTHONPATH=bin python bin/user/sysstat.py
#
if __name__ == "__main__":
    from weewx.engine import StdEngine
    import weeutil.logger
    import weewx

    weewx.debug = 1
    weeutil.logger.setup('sysstat')

    config = {
        'Station': {
            'station_type': 'Simulator',
            'altitude': [0, 'foot'],
            'latitude': 0,
            'longitude': 0},
        'Simulator': {
            'driver': 'weewx.drivers.simulator',
            'mode': 'simulator'},
        'SystemStatistics': {
            'data_binding': 'sysstat_binding',
            'process': 'sysstat'},
        'DataBindings': {
            'sysstat_binding': {
                'database': 'sysstat_sqlite',
                'manager': 'weewx.manager.DaySummaryManager',
                'table_name': 'archive',
                'schema': 'user.sysstat.schema'}},
        'Databases': {
            'sysstat_sqlite': {
                'database_name': 'sysstat.sdb',
                'database_type': 'SQLite'}},
        'DatabaseTypes': {
            'SQLite': {
                'driver': 'weedb.sqlite',
                'SQLITE_ROOT': 'archive'}},
        'Engine': {
            'Services': {
                'archive_services': 'user.sysstat.SystemStatistics'}},
    }

    # Logged entries are in syslog. View with journalctl --grep=sysstat

    eng = StdEngine(config)
    svc = SystemStatistics(eng, config)

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
