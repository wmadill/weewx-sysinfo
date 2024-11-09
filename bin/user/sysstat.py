# Copyright 2013-2013 Matthew Wall
#### THIS IS BEING WRITTEN AND EVERYTHING IN IT IS
#### NOT TO BE RELIED ON!
"""weewx module that records process information.

Installation

Put this file in the bin/user directory.


Configuration

Add the following to weewx.conf:

[ProcessMonitor]
    data_binding = pmon_binding

[DataBindings]
    [[pmon_binding]]
        database = pmon_sqlite
        manager = weewx.manager.Manager
        table_name = archive
        schema = user.pmon.schema

[Databases]
    [[pmon_sqlite]]
        database_name = archive/pmon.sdb
        database_type = SQLite

[Engine]
    [[Services]]
        archive_services = ..., user.pmon.ProcessMonitor
"""

import logging
import os
import re
import time
from subprocess import Popen, PIPE

import weedb
import weewx.manager
from weeutil.weeutil import to_int
from weewx.engine import StdService

VERSION = "0.7"

log = logging.getLogger(__name__)

schema = [
    ('dateTime', 'INTEGER NOT NULL PRIMARY KEY'),
    ('usUnits', 'INTEGER NOT NULL'),
    ('interval', 'INTEGER NOT NULL'),
    ('mem_vsz', 'INTEGER'),
    ('mem_rss', 'INTEGER'),
]


class SystemStatistics(StdService):

    def __init__(self, engine, config_dict):
        super(ProcessMonitor, self).__init__(engine, config_dict)

        # To make what follows simpler, isolate the "pmon" part of the configuration file
        pmon_dict = config_dict.get('ProcessMonitor', {})
        self.process = pmon_dict.get('process', 'weewxd')
        self.max_age = to_int(pmon_dict.get('max_age', 2592000))

        # get the database parameters we need to function
        binding = pmon_dict.get('data_binding', 'pmon_binding')
        self.dbm = self.engine.db_binder.get_manager(data_binding=binding,
                                                     initialize=True)

        # be sure database matches the schema we have
        dbcol = self.dbm.connection.columnsOf(self.dbm.table_name)
        dbm_dict = weewx.manager.get_manager_dict_from_config(config_dict, binding)
        memcol = [x[0] for x in dbm_dict['schema']]
        if dbcol != memcol:
            raise Exception('pmon schema mismatch: %s != %s' % (dbcol, memcol))

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
            # sqlite databases need some help to stay small
            self.dbm.getSql('vacuum')
        except weedb.DatabaseError:
            pass

    COLUMNS = re.compile(r'\S+\s+\d+\s+[\d.]+\s+[\d.]+\s+(\d+)\s+(\d+)')

    def get_data(self, now_ts, last_ts):
        record = {
            'dateTime' : now_ts,
            'usUnits' : weewx.METRIC,
            'interval' : int((now_ts - last_ts) / 60.0)
        }
        try:
            cmd = 'ps aux'
            p = Popen(cmd, shell=True, stdout=PIPE)
            o = p.communicate()[0].decode('ascii')
            for line in o.split('\n'):
                if line.find(self.process) >= 0:
                    m = self.COLUMNS.search(line)
                    if m:
                        record['mem_vsz'] = int(m.group(1))
                        record['mem_rss'] = int(m.group(2))
        except (ValueError, IOError, KeyError) as e:
            log.error('apcups_info failed: %s' % e)
        return record


# what follows is a basic unit test of this module.  to run the test:
#
# cd ~/weewx-data
# PYTHONPATH=bin python bin/user/pmon.py
#
if __name__ == "__main__":
    from weewx.engine import StdEngine
    import weeutil.logger
    import weewx

    weewx.debug = 1
    weeutil.logger.setup('pmon')

    config = {
        'Station': {
            'station_type': 'Simulator',
            'altitude': [0, 'foot'],
            'latitude': 0,
            'longitude': 0},
        'Simulator': {
            'driver': 'weewx.drivers.simulator',
            'mode': 'simulator'},
        'ProcessMonitor': {
            'data_binding': 'pmon_binding',
            'process': 'pmon'},
        'DataBindings': {
            'pmon_binding': {
                'database': 'pmon_sqlite',
                'manager': 'weewx.manager.DaySummaryManager',
                'table_name': 'archive',
                'schema': 'user.pmon.schema'}},
        'Databases': {
            'pmon_sqlite': {
                'database_name': 'pmon.sdb',
                'database_type': 'SQLite'}},
        'DatabaseTypes': {
            'SQLite': {
                'driver': 'weedb.sqlite',
                'SQLITE_ROOT': '/var/tmp'}},
        'Engine': {
            'Services': {
                'process_services': 'user.pmon.ProcessMonitor'}}
    }
    eng = StdEngine(config)
    svc = ProcessMonitor(eng, config)

    nowts = lastts = int(time.time())

    loop = 0
    try:
        while True:
            rec = svc.get_data(nowts, lastts)
            print(rec)
            loop += 1
            if loop >= 3:
                break
            time.sleep(5)
            lastts = nowts
            nowts = int(time.time()+0.5)
    finally:
        try:
            os.remove('/var/tmp/pmon.sdb')
        except FileNotFoundError:
            pass
