# Installer for sysinfo
# Copyright 2024 Bill Madill

from weecfg.extension import ExtensionInstaller

def loader():
    return SystemInfoInstaller()

class SystemInfoInstaller(ExtensionInstaller):
    def __init__(self):
        super(SystemInfoInstaller, self).__init__(
            version="0.2",
            name='sysinfo',
            description='Collect and display system information.',
            author="Bill Madill",
            author_email="wm@wmadill.com",
            archive_services='user.sysinfo.SystemInfo',
            config={
                'SystemInfo': {
                    'data_binding': 'sysinfo_binding'},
                'DataBindings': {
                    'sysinfo_binding': {
                        'database': 'sysinfo_sqlite',
                        'table_name': 'archive',
                        'manager': 'weewx.manager.DaySummaryManager',
                        'schema': 'user.sysinfo.schema'}},
                'Databases': {
                    'sysinfo_sqlite': {
                        'database_name': 'sysinfo.sdb',
                        'driver': 'weedb.sqlite'}},
                'StdReport': {
                    'sysinfo': {
                        'skin': 'sysinfo',
                        'HTML_ROOT': 'sysinfo'}}},
            files=[('bin/user', ['bin/user/sysinfo.py']),
                   ('skins/sysinfo', ['skins/sysinfo/skin.conf',
                                   'skins/sysinfo/index.html.tmpl'])]
        )
