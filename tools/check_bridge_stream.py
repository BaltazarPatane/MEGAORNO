"""Exercise the real Python bridge + C# gate over pipes, without MadgeTech.

First compile PollGate.cs + PollGateTests.cs. On Windows pass that executable;
on Linux pass a Mono runner followed by the executable, e.g.:
python tools/check_bridge_stream.py mono /tmp/PollGateTests.exe
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acquisition import AcquisitionController, ConnectionSettings
from models import Sesion


def main(command):
    if not command:raise ValueError('Provide the command that runs PollGateTests.exe.')
    spawn=subprocess.Popen
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);compiler=root/'Windows/Microsoft.NET/Framework/v4.0.30319/csc.exe'
        compiler.parent.mkdir(parents=True);compiler.touch()
        def compiled_fixture(args,**kwargs):
            # WCF sources are compiled separately; this integration uses the
            # deterministic C# fixture and the production Python subprocess code.
            target=next(arg[5:] for arg in args if arg.startswith('/out:'))
            shutil.copyfile(command[-1],target)
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        def launch(args,**kwargs):
            kwargs.pop('creationflags',None)
            return spawn(command+['--stream'],**kwargs)
        process_api=SimpleNamespace(Popen=launch,run=compiled_fixture,PIPE=subprocess.PIPE,
            STDOUT=subprocess.STDOUT,CREATE_NO_WINDOW=0,TimeoutExpired=subprocess.TimeoutExpired)
        platform=SimpleNamespace(name='nt',environ=dict(os.environ,WINDIR=str(root/'Windows')))
        with patch('live.os',platform),patch('live.subprocess',process_api):
            c=AcquisitionController(root/'state');path=root/'real-pipes.horno.json'
            c.connect(ConnectionSettings(vendor_dir=str(root)),path)
            def until(predicate,seconds=3):
                end=time.monotonic()+seconds
                while time.monotonic()<end:
                    c.drain()
                    if c.state=='error':raise AssertionError('Bridge error')
                    if predicate():return
                    time.sleep(.01)
                raise AssertionError('Timed out waiting for acquisition')
            try:
                until(lambda:len(c.session.registro.muestras)>=3)
                process=c.bridge.process;session=c.session;before=deepcopy(session.registro.muestras)
                c.pause();c.drain();saved=path.read_bytes();time.sleep(.35);c.drain()
                assert c.paused and process.poll() is None
                assert session.registro.muestras==before and path.read_bytes()==saved
                c.resume();until(lambda:len(session.registro.muestras)>=len(before)+2)
                assert c.session is session and c.bridge.process is process
                assert session.registro.muestras[:len(before)]==before
                channel=session.registro.canales[0]
                assert session.registro.gradientes[len(before)][channel] is None
                assert session.registro.gradientes[len(before)+1][channel]==2
                c.pause();c.drain();c.disconnect();c.bridge.thread.join(3)
                assert not c.bridge.running
                assert Sesion.abrir(path).registro==session.registro
                print('OK: Python + C# pipes; pause freezes data, resume keeps process/session/history, gaps persist, shutdown completes.')
            finally:
                c.disconnect()
                if c.bridge.thread:c.bridge.thread.join(3)


if __name__=='__main__':main(sys.argv[1:])
