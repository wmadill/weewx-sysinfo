# installer for sysstat
# Copyright 2014-2024 Matthew Wall and 2024 Bill Madill

from weecfg.extension import ExtensionInstaller

def loader():
    return SystemStatisticsInstaller()


class SystemStatisticsInstaller(ExtensionInstaller):
    def __init__(self):
        super(SystemStatisticsInstaller, self).__init__(
            version="0.1",
            name='sysstat',
            description='Collect and display system statistics.',
            author="Bill Madill",
            author_email="wm@wmadill.com",
            archive_services='user.sysstat.SystemStatistics',
            config={
                'SystemStatistics': {
                    'data_binding': 'sysstat_binding',
                    'process': 'weewxd'},
                'DataBindings': {
                    'sysstat_binding': {
                        'database': 'sysstat_sqlite',
                        'table_name': 'archive',
                        'manager': 'weewx.manager.Manager',
                        'schema': 'user.sysstat.schema'}},
                'Databases': {
                    'sysstat_sqlite': {
                        'database_name': 'sysstat.sdb',
                        'driver': 'weedb.sqlite'}},
                'StdReport': {
                    'sysstat': {
                        'skin': 'sysstat',
                        'HTML_ROOT': 'sysstat'}}},
            files=[('bin/user', ['bin/user/sysstat.py']),
                   ('skins/sysstat', ['skins/sysstat/skin.conf',
                                   'skins/sysstat/index.html.tmpl'])]
        )
