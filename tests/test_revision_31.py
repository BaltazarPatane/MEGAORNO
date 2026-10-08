"""Regressions for the operator's v3.1 feedback, including invalid-sample continuity."""
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from acquisition import AcquisitionController,ConnectionSettings
from gui import App
from models import Registro,Sesion,cargar_xlsx
from live import decodificar_madgetech
from ui.chart_widget import ChartWidget
from tools.export_session import export_snapshot
from test_acquisition import FakeBridge
from test_gui_workflow import WorkflowController

ROOT=Path(__file__).resolve().parents[1]


def packet(index=0, value='25', status='Valid', missing_status='SensorError'):
    return dict(serial='R59022',timestamp=(datetime(2026,10,6,9)+timedelta(seconds=index*15)).isoformat(),channels=[
        dict(position=i,unit='Celsius',status=status if i==2 else missing_status,
             value=value if i==2 else '') for i in range(1,25)])


class ChannelRevision(unittest.TestCase):
    def test_names_preserve_original_positions_historical_numbers_and_custom_aliases(self):
        session=Sesion()
        self.assertEqual(session.nombre('Madge'),'Temperatura Ambiente')
        for position in range(1,25):
            channel=f'R59022 / Posición WCF {position}'
            expected=('Temperatura Ambiente' if position%2 else 'Termocuplas')+f' · {(position+1)//2}'
            self.assertEqual(session.nombre(channel),expected)
        channel='Canal 6 · Termopar 3'
        self.assertEqual(session.nombre(channel),'Termocuplas · 3')
        self.assertEqual(session.nombre('Canal 1 · Ambiente 1'),'Temperatura Ambiente · 1')
        session.alias[channel]='Centro del horno'
        self.assertEqual(session.nombre(channel),'Centro del horno')
        session.alias[channel]='Madge'
        self.assertEqual(session.nombre(channel),'Temperatura Ambiente')
        self.assertEqual(session.nombre('Canal desconocido'),'Canal desconocido')

    def test_empty_inputs_are_quiet_but_preserve_none_and_original_identity(self):
        data=packet();rows,errors=decodificar_madgetech(data)
        self.assertEqual(len(rows),24);self.assertEqual(errors,[])
        self.assertEqual(rows[1][1:],('R59022 / Posición WCF 2',25.))
        self.assertEqual(sum(value is None for _,_,value in rows),23)

    def test_unused_channels_do_not_flood_notifications_or_erase_raw_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'capture.horno.json';controller=AcquisitionController(temp,FakeBridge)
            controller.connect(ConnectionSettings(vendor_dir=temp),path);bridge=controller.bridge
            bridge.emit('mt_devices',['R59022']);notifications=[]
            for i in range(75):
                # Alternate missing, explicit error and saturation states on
                # inputs which have never produced any valid temperature.
                data=packet(i)
                for channel in data['channels']:
                    if channel['position']!=2:
                        channel.update(status=['SensorError','OverRange','NoSensor'][i%3],value='' if i%3==0 else '1370')
                bridge.emit('mt_reading',data);notifications.extend(controller.drain())
            self.assertFalse([e for e in notifications if e['type'] in ('warning','error')])
            self.assertEqual(controller.state,'receiving')
            self.assertEqual(len(controller.session.registro.muestras),75)
            self.assertEqual(len(Path(str(path)+'.wcf.jsonl').read_text().splitlines()),75)
            restored=Sesion.abrir(path)
            self.assertIsNone(restored.registro.muestras[-1][1]['R59022 / Posición WCF 3'])
            controller.disconnect()

    def test_sensor_loss_warns_once_and_recovery_does_not_bridge_invalid_interval(self):
        with tempfile.TemporaryDirectory() as temp:
            controller=AcquisitionController(temp,FakeBridge)
            controller.connect(ConnectionSettings(vendor_dir=temp),Path(temp)/'capture.horno.json');b=controller.bridge
            b.emit('mt_devices',['R59022']);b.emit('mt_reading',packet(0));controller.drain()
            b.emit('mt_reading',packet(1,value='26'));controller.drain()
            b.emit('mt_reading',packet(2,value=None));first=controller.drain()
            self.assertTrue(any('sin lectura' in e['data'] for e in first if e['type']=='warning'))
            for i in range(3,10):
                b.emit('mt_reading',packet(i,value=None));events=controller.drain()
                self.assertFalse([e for e in events if e['type']=='warning'])
            b.emit('mt_reading',packet(10,value='50'));events=controller.drain()
            channel='R59022 / Posición WCF 2'
            self.assertIsNone(controller.session.registro.gradientes[-1][channel])
            self.assertTrue(any('recuperada' in e['data'] for e in events if e['type']=='log'))
            b.emit('mt_reading',packet(11,value='51'));controller.drain()
            self.assertEqual(controller.session.registro.gradientes[-1][channel],4.)
            controller.disconnect()

    def test_unknown_units_still_report_once_without_becoming_a_temperature(self):
        with tempfile.TemporaryDirectory() as temp:
            controller=AcquisitionController(temp,FakeBridge)
            controller.connect(ConnectionSettings(vendor_dir=temp),Path(temp)/'capture.horno.json');b=controller.bridge;b.emit('mt_devices',['R59022'])
            warnings=[]
            for i in range(12):
                data=packet(i);data['channels'][1].update(unit='mV',value=str(i))
                b.emit('mt_reading',data);warnings.extend(e['data'] for e in controller.drain() if e['type']=='warning')
            self.assertEqual(sum('unidad' in warning for warning in warnings),1)
            self.assertEqual(sum('todavía' in warning for warning in warnings),1)
            self.assertFalse(controller._ready)
            self.assertTrue(all(vals['R59022 / Posición WCF 2'] is None for _,vals in controller.session.registro.muestras))
            controller.disconnect()


class UiRevision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.qt=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.controller=WorkflowController(self.temp.name)
        self.w=App(self.temp.name,self.controller);self.w.timer.stop();self.w.refresh_timer.stop()
    def tearDown(self):
        self.w.close();self.w.deleteLater();self.qt.processEvents();self.temp.cleanup()

    def test_home_contains_only_requested_hero_text_and_two_summary_cards(self):
        hero=self.w.login.findChild(QWidget,'hero')
        text='\n'.join(label.text() for label in hero.findChildren(QLabel))
        for expected in ['CONTROL DE TRATAMIENTO','MADGETECH 4','INTEROPERABILIDAD','Baltazar Patané','Juan Marcos Macagno']:self.assertIn(expected,text)
        for removed in ['Cada grado','Cada instante','Datos originales','precisión']:self.assertNotIn(removed,text)
        self.w.open_example()
        self.assertEqual(len(self.w.curves.metric_values),2)
        text='\n'.join(label.text() for label in self.w.curves.findChildren(QLabel))
        self.assertNotIn('CANALES CON DATOS',text);self.assertNotIn('AVISOS DEL PROCESO',text)

    def test_notices_render_after_many_warnings_without_growing_the_main_window(self):
        self.w.resize(1366,738);self.w.show();self.qt.processEvents();self.w.open_example();self.qt.processEvents()
        notice=self.w.notice.text()
        self.controller._emit('warning','\n'.join(f'Sensor {i}: lectura inválida' for i in range(100)))
        self.w.consume();self.qt.processEvents()
        self.assertEqual(self.w.notice.text(),notice)
        self.assertIs(self.w.tabs.currentWidget(),self.w.curves)
        self.assertEqual(self.w.height(),738)
        self.w.tabs.setCurrentWidget(self.w.alerts);self.qt.processEvents();self.qt.processEvents()
        self.assertTrue(self.w.alerts.isVisible());self.assertTrue(self.w.alerts.table.isVisible())
        self.assertGreater(self.w.alerts.table.height(),100)
        self.assertTrue(all(s>0 for s in self.w.alerts.splitter.sizes()))
        self.assertGreater(self.w.alerts.model.rowCount(),0)
        self.assertIn('Sensor 99',self.w.alerts.log_text.toPlainText())
        self.w.alerts.splitter.setSizes([0,800]);self.qt.processEvents()
        self.assertGreater(self.w.alerts.table.height(),100)

    def test_ctrl_wheel_only_changes_y_in_each_plot_mode(self):
        self.w.open_example();chart=self.w.curves.chart
        for mode in ['Temperatura','Ambas','Gradiente']:
            chart.set_options(mode=mode);chart.fit_view();chart.canvas.draw()
            ax=chart.ax_g if mode=='Gradiente' else chart.ax_t
            oldx=ax.get_xlim();oldy=ax.get_ylim();x=sum(oldx)/2;y=sum(oldy)/2
            for key in ['control','ctrl']:
                event=SimpleNamespace(inaxes=ax,xdata=x,ydata=y,step=1,key=key)
                before=ax.get_ylim();chart._on_scroll(event)
                self.assertEqual(chart.ax_t.get_xlim(),oldx);self.assertEqual(chart.ax_g.get_xlim(),oldx)
                self.assertLess(ax.get_ylim()[1]-ax.get_ylim()[0],before[1]-before[0])
                self.assertFalse(chart.follow)

    def test_pdf_export_freezes_channel_identity_without_altering_session_or_selection(self):
        self.w.open_example();self.w.curves.channels.item(1).setCheckState(Qt.CheckState.Unchecked)
        selected=self.w.curves.selected_channels()
        with patch('gui.QProcess.start'):
            self.w.export_to(Path(self.temp.name)/'selected.pdf','PDF')
        try:
            arguments=self.w.export_process.arguments()
            self.assertEqual(json.loads(arguments[-1]),selected)
            self.w.curves.check_all(True)
            self.assertEqual(json.loads(self.w.export_process.arguments()[-1]),selected)
            self.assertEqual(len(Sesion.abrir(self.w.export_snapshot).registro.canales),2)
        finally:self.w.cleanup_export()

    def test_pdf_with_no_selected_channels_is_rejected_without_creating_an_export(self):
        self.w.open_example();self.w.curves.check_all(False)
        with self.assertRaisesRegex(ValueError,'al menos un canal'):
            self.w.export_to(Path(self.temp.name)/'empty.pdf','PDF')
        self.assertIsNone(self.w.export_process)


class PdfSelectionRevision(unittest.TestCase):
    def test_pdf_figure_contains_only_selected_channels_but_report_keeps_complete_data(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);session=Sesion(registro=cargar_xlsx(ROOT/'ejemplos'/'R59022 MultiChannel.xlsx'))
            session.guardar(folder/'snapshot.horno.json');selected=session.registro.canales[1]
            observed={}
            def inspect_pdf(snapshot,figure,target):
                observed['labels']=[line.get_label() for ax in figure.axes for line in ax.lines]
                observed['channels']=list(snapshot.registro.canales)
                Path(target).write_bytes(b'%PDF-test')
            with patch('tools.export_session.exportar_pdf',side_effect=inspect_pdf):
                export_snapshot(folder/'snapshot.horno.json',folder/'selected.pdf','PDF',json.dumps([selected]))
            self.assertIn(session.nombre(selected),observed['labels'])
            self.assertNotIn(session.nombre(session.registro.canales[0]),observed['labels'])
            self.assertEqual(observed['channels'],session.registro.canales)
            self.assertEqual((folder/'selected.pdf').read_bytes(),b'%PDF-test')

    def test_invalid_selection_does_not_replace_an_existing_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);source=folder/'snapshot.horno.json';Sesion().guardar(source)
            destination=folder/'existing.pdf';destination.write_bytes(b'previous')
            for selected in [[],['missing']]:
                with self.assertRaises(ValueError):export_snapshot(source,destination,'PDF',json.dumps(selected))
                self.assertEqual(destination.read_bytes(),b'previous')
                self.assertFalse(list(folder.glob('.megaorno-export-*')))


if __name__=='__main__':unittest.main()
