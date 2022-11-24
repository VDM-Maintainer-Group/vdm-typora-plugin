#!/usr/bin/env python3
import os, re, time, psutil
import json
import subprocess as sp
from pathlib import Path
from pyvdm.interface import CapabilityLibrary, SRC_API

DBG = 0
SLOT = 0.40
PROG_NAME = 'Typora'
WINDOW_TITLE = '%s.? - Typora'

from pyvdm.core.ApplicationManager import ApplicationManager as AM
TARGET = 'io.typora'
APP = AM.get_application(TARGET)
PROG_EXEC = APP['exec'].split()[0]

class TyporaPlugin(SRC_API):
    @staticmethod
    def _gather_records(raw_results) -> list:
        records = list()

        ## collect and filter the raw data
        _processes = dict()
        for item in raw_results:
            pid, path = item.split(',', maxsplit=1)
            pid  = int(pid)
            path = path.rstrip('\u0000')
            #
            if pid not in _processes.keys():
                _processes[pid] = [path]
            else:
                _processes[pid].append(path)
            pass
        # if DBG: print( json.dumps(_processes, indent=4) )

        ## gather records
        for pid, items in _processes.items():
            if len(items) == 1:
                _path = items[0]
                records.append( (pid,_path) )
                if DBG: print(f'file [{pid}]: {_path}')
            elif len( psutil.Process(pid).cmdline() ) == 1:
                _path = ''
            else:
                _path = os.path.commonpath(items)
                records.append( (pid,_path) )
                if DBG: print(f'folder [{pid}]: {_path}')
            pass

        return records

    def _associate_with_window(self, records) -> list:
        results = list()

        windows = self.xm.get_windows_by_name(PROG_NAME)
        windows.sort(key=lambda x:x['xid'])
        if windows:
            _pid = windows[0]['pid']
            records = filter(lambda x:x[0]!=_pid, records)

        for (_pid,_path),w in zip(records, windows):
            results.append({
                'name': Path(_path).name,
                'path': _path,
                'window': {
                    'desktop':w['desktop'],
                    'states':w['states'],
                    'xyhw':w['xyhw']
                }
            })

        return results

    def _rearrange_window(self, records: list):
        _time = time.time()
        _limit= len(records) * 2*SLOT

        windows = self.xm.get_windows_by_name(PROG_NAME)
        while len(windows)!=records and time.time()-_time<_limit:
            time.sleep(SLOT)
            windows = self.xm.get_windows_by_name(PROG_NAME)
        windows.sort(key=lambda x:x['xid'])

        for stat,w in zip(records, windows):
            s = stat['window']
            self.xm.set_window_by_xid( w['xid'], s['desktop'], s['states'], s['xyhw'] )

        pass

    def onStart(self):
        self.xm = CapabilityLibrary.CapabilityHandleLocal('x11-manager')
        self.il = CapabilityLibrary.CapabilityHandleLocal('inotify-lookup')
        self.il.register( PROG_NAME )
        return 0

    def onStop(self):
        self.il.unregister( PROG_NAME )
        return 0

    def onSave(self, stat_file):
        ## dump raw_results via il
        raw_results = self.il.dump( PROG_NAME )
        ## gathering records from raw_result
        records = self._gather_records(raw_results)
        ##
        records = self._associate_with_window(records)
        ## write to file
        with open(stat_file, 'w') as f:
            json.dump(records, f)
            pass
        return 0

    def onResume(self, stat_file, new):
        ## load stat file with failure check
        with open(stat_file, 'r') as f:
            _file = f.read().strip()
        if len(_file)==0:
            return 0
        else:
            try:
                records = json.loads(_file)
            except:
                return -1
        ## open windows
        for item in records:
            sp.Popen([ PROG_EXEC, item['path'] ], start_new_session=True)
        ## rearrange windows by title
        self._rearrange_window(records)
        return 0

    def onClose(self):
        ## force close all
        os.system( f'killall {PROG_NAME}' )
        return 0
    pass

if __name__ == '__main__':
    _plugin = TyporaPlugin()
    _plugin.onStart()

    raw_results = _plugin.il.dump( PROG_NAME )
    ## gathering records from raw_results
    records = _plugin._gather_records(raw_results)
    ## associate with X window
    records = _plugin._associate_with_window(records)
    print( json.dumps(records, indent=4) )
    pass
