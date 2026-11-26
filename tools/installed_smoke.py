"""Acceptance check executed by the installed launcher and its private Python.

The check creates its own test capture and does not connect to MadgeTech.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    runtime=(ROOT/'runtime').resolve()
    assert Path(sys.executable).resolve().is_relative_to(runtime),'No se está usando el Python incluido.'
    assert sys.flags.isolated and sys.flags.ignore_environment,'El Python debe estar aislado.'
    import PySide6,matplotlib,numpy,openpyxl,reportlab
    for module in [PySide6,matplotlib,numpy,openpyxl,reportlab]:
        assert Path(module.__file__).resolve().is_relative_to(runtime),module.__file__
    from PySide6.QtWidgets import QApplication
    from gui import App
    from live import install_bundled_bridge
    from models import Sesion
    app=QApplication.instance() or QApplication([])
    window=App(state_dir=output/'estado');window.show();app.processEvents()
    assert not window.active and window.tabs.count()==5
    assert not window.windowIcon().isNull(),'No se cargó el icono del horno.'
    window.open_example();app.processEvents()
    assert len(window.session.registro.muestras)==93
    for i in range(5):window.tabs.setCurrentIndex(i);app.processEvents()
    window.tabs.setCurrentIndex(0)
    for kind,ext in [('PDF','pdf'),('EXCEL','xlsx'),('CSV','csv')]:
        destination=output/('prueba.'+ext)
        window.export_to(destination,kind);deadline=time.monotonic()+90
        while window.export_process is not None and time.monotonic()<deadline:
            app.processEvents();time.sleep(.02)
        assert window.last_export==destination,window.alerts.log_text.toPlainText()
        assert destination.stat().st_size>100
    with (output/'prueba.csv').open(encoding='utf-8-sig',newline='') as stream:
        assert len(list(csv.reader(stream,delimiter=';')))==94
    workbook=openpyxl.load_workbook(output/'prueba.xlsx',read_only=True,data_only=True)
    assert workbook['Datos'].max_row==94;assert 'Controladores' in workbook.sheetnames;workbook.close()
    assert (output/'prueba.pdf').read_bytes().startswith(b'%PDF-')
    stored=window.session_path;window.logout()
    assert len(Sesion.abrir(stored).registro.muestras)==93
    base=ROOT/'wcf'
    fingerprint=hashlib.sha256(b'v2.1-x86'+b''.join((base/name).read_bytes() for name in ['Bridge.cs','MadgeTechClient.cs','PollGate.cs'])).hexdigest()
    bridge_dir=output/'puente';bridge_dir.mkdir(exist_ok=True)
    assert install_bundled_bridge(base,bridge_dir,fingerprint),'Falta el puente precompilado.'
    assert (bridge_dir/'HornoWcfBridge.exe').read_bytes().startswith(b'MZ')
    window.close();app.processEvents()
    result=dict(resultado='OK',python=sys.version,ejecutable=sys.executable,muestras=93,
                comprobaciones=['inicio','cinco pestañas','icono','sesión','PDF','EXCEL','CSV','puente WCF precompilado'],
                paquetes={dist.metadata['Name']:dist.version for dist in importlib.metadata.distributions()})
    (output/'resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('OK: instalación aislada, 93 muestras, cinco pestañas, icono, PDF, Excel, CSV, guardado y puente precompilado.')


if __name__=='__main__':main()
