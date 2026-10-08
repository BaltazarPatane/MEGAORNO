"""Flujos completos de interfaz con Qt real y transporte WCF simulado."""
import csv
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication
from acquisition import AcquisitionController
from gui import App
from models import Sesion


class WorkflowBridge:
    def __init__(self, events):
        self.events = events
        self.request_id = 0
        self.running = False
        self.config = None

    def start(self, config, folder):
        self.config = config
        self.request_id += 1
        self.running = True

    def stop(self):
        self.request_id += 1
        self.running = False

    def emit(self, kind, data):
        self.events.put(dict(type=kind, data=data, request_id=self.request_id))


class WorkflowController(AcquisitionController):
    """Inyectar un transporte simulado evita la restricción WCF de Windows."""
    def __init__(self, state_dir):
        super().__init__(state_dir, bridge_factory=WorkflowBridge)


def payload(timestamp='2026-09-29T08:00:00.123456', value='630', serial='R59022', status='Valid'):
    return dict(serial=serial, timestamp=timestamp, channels=[
        dict(position=1, unit='Celsius', status=status, value=value)])


class GuiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name)
        self.controller = WorkflowController(self.state_dir)
        self.window = App(state_dir=self.state_dir, controller=self.controller)
        self.window.timer.stop()
        self.window.refresh_timer.stop()
        self.window.login.vendor_dir.setText(str(self.state_dir))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.qt.processEvents()
        self.tmp.cleanup()

    def connect(self):
        self.window.connect_device()
        return self.controller.bridge

    def receive(self):
        bridge = self.connect()
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', payload())
        self.window.consume()
        return bridge

    def test_starts_with_login_and_workspace_hidden(self):
        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertFalse(self.window.active)
        self.assertTrue(self.window.workspace.isHidden())
        self.assertTrue(self.window.login.demo_button.isEnabled())
        self.assertFalse(self.window.login.auth.isChecked())
        self.assertFalse(self.window.login.username.isEnabled())
        self.assertFalse(self.window.login.password.isEnabled())

    def test_example_opens_all_five_views_and_three_exports_with_93_samples(self):
        self.window.open_example()
        self.assertTrue(self.window.active)
        self.assertEqual(self.window.stack.currentIndex(), 1)
        self.assertEqual(len(self.window.session.registro.muestras), 93)
        self.assertEqual([self.window.tabs.tabText(i) for i in range(self.window.tabs.count())],
                         ['Curvas', 'Perfil ideal', 'Estadísticas', 'Datos', 'Avisos'])
        self.assertEqual([action.text() for action in self.window.export_button.menu().actions()], ['PDF', 'EXCEL', 'CSV'])
        self.assertTrue(self.window.export_button.isEnabled())
        self.assertIn('EJEMPLO', self.window.connection_badge.text())
        self.assertEqual(len(Sesion.abrir(self.window.session_path).registro.muestras), 93)
        for i in range(5):
            self.window.tabs.setCurrentIndex(i)
            self.window.refresh_visible()

    def test_logout_saves_current_changes_clears_credentials_and_returns_to_login(self):
        self.window.open_example()
        path = self.window.session_path
        channel = self.window.session.registro.canales[0]
        self.window.session.alias[channel] = 'Termocupla superior'
        self.window.login.username.setText('operador privado')
        self.window.login.password.setText('clave privada')
        self.window.logout()
        self.assertEqual(Sesion.abrir(path).alias[channel], 'Termocupla superior')
        self.assertFalse(self.window.active)
        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertEqual(self.window.login.username.text(), '')
        self.assertEqual(self.window.login.password.text(), '')

    def test_transport_or_invalid_readings_do_not_unlock_workspace(self):
        bridge = self.connect()
        bridge.emit('transport_open', 'net.pipe://localhost/MT4Data')
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', payload(status='SensorError'))
        self.window.consume()
        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertFalse(self.window.active)
        self.assertEqual(self.controller.state, 'waiting')
        self.assertFalse(self.window.login.connect_button.isEnabled())

    def test_first_valid_reading_unlocks_workspace_and_further_samples_share_session(self):
        bridge = self.receive()
        self.assertTrue(self.window.active)
        self.assertIs(self.window.session, self.controller.session)
        self.assertEqual(self.window.session_path, self.controller.session_path)
        self.assertIn('ACTIVA', self.window.connection_badge.text())
        bridge.emit('mt_reading', payload('2026-09-29T08:05:00', '640'))
        self.window.consume()
        self.window.flush_refresh()
        self.assertEqual(len(self.window.session.registro.muestras), 2)
        self.assertEqual(len(Sesion.abrir(self.window.session_path).registro.muestras), 2)
        self.assertIn('2 muestras', self.window.source.text())

    def test_live_error_preserves_session_and_export_access(self):
        bridge = self.receive()
        session = self.window.session
        bridge.emit('error', 'CommunicationLostException: se desconectó el equipo')
        self.window.consume()
        self.assertIs(self.window.session, session)
        self.assertTrue(self.window.active)
        self.assertEqual(self.window.stack.currentIndex(), 1)
        self.assertIn('DETENIDA', self.window.connection_badge.text())
        self.assertIn('CommunicationLostException', self.window.alerts.log_text.toPlainText())
        self.assertNotIn('CommunicationLostException', self.window.notice.text())
        self.assertTrue(self.window.export_button.isEnabled())
        self.assertFalse(self.controller.running)

    def test_autosave_failure_exposes_unsaved_reading_without_discarding_it(self):
        bridge = self.receive()
        bridge.emit('mt_reading', payload('2026-09-29T08:05:00', '640'))
        with patch.object(self.window.session, 'guardar', side_effect=OSError('Disco lleno')):
            self.window.consume()
        self.assertTrue(self.window.active)
        self.assertFalse(self.controller.running)
        self.assertEqual(len(self.window.session.registro.muestras), 2)
        self.assertEqual(len(Sesion.abrir(self.window.session_path).registro.muestras), 1)
        self.assertIn('memoria', self.window.alerts.log_text.toPlainText())
        self.assertNotIn('memoria', self.window.notice.text())

    def test_first_sample_save_failure_opens_current_capture_for_recovery(self):
        bridge = self.connect()
        path = self.controller.session_path
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', payload())
        with patch.object(self.controller.session, 'guardar', side_effect=OSError('Disco lleno')):
            self.window.consume()
        self.assertTrue(self.window.active)
        self.assertFalse(self.controller.running)
        self.assertIs(self.window.session, self.controller.session)
        self.assertEqual(self.window.session_path, path)
        self.assertEqual(len(self.window.session.registro.muestras), 1)
        self.assertEqual(len(Sesion.abrir(path).registro.muestras), 0)
        self.assertIn('DETENIDA', self.window.connection_badge.text())

    def test_credentials_not_saved_and_password_is_cleared_on_ready(self):
        self.window.login.auth.setChecked(True)
        self.window.login.username.setText('PRIVATE_OPERATOR')
        self.window.login.password.setText('SECRET_PASSWORD')
        bridge = self.receive()
        self.assertEqual(bridge.config['username'], 'PRIVATE_OPERATOR')
        self.assertEqual(bridge.config['password'], 'SECRET_PASSWORD')
        self.assertEqual(self.window.login.password.text(), '')
        for path in self.state_dir.rglob('*'):
            if path.is_file():
                text = path.read_text(encoding='utf-8')
                self.assertNotIn('PRIVATE_OPERATOR', text)
                self.assertNotIn('SECRET_PASSWORD', text)
        bridge.emit('error', 'Falló SECRET_PASSWORD de PRIVATE_OPERATOR')
        self.window.consume()
        self.assertNotIn('PRIVATE_OPERATOR', self.window.notice.text())
        self.assertNotIn('SECRET_PASSWORD', self.window.alerts.log_text.toPlainText())

    def test_multiple_devices_reveals_selection_then_connects_chosen_serial(self):
        first = self.connect()
        first.emit('mt_devices', ['R1', 'R2'])
        self.window.consume()
        self.assertFalse(self.window.active)
        self.assertFalse(self.window.login.advanced.isHidden())
        self.assertTrue(self.window.login.connect_button.isEnabled())
        self.assertIn('más de un equipo', self.window.login.message.text())
        self.window.login.devices.setCurrentIndex(2)
        self.window.connect_device()
        second = self.controller.bridge
        self.assertEqual(second.config['serial'], 'R2')
        second.emit('mt_devices', ['R1', 'R2'])
        second.emit('mt_reading', payload(serial='R2'))
        self.window.consume()
        self.assertTrue(self.window.active)
        self.assertEqual(self.window.session.registro.serie, 'R2')

    def test_search_finishes_on_login_and_allows_example(self):
        self.window.search_devices()
        bridge = self.controller.bridge
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('finished', 'mt_list')
        self.window.consume()
        self.assertFalse(self.window.active)
        self.assertTrue(self.window.login.demo_button.isEnabled())
        self.assertTrue(self.window.login.connect_button.isEnabled())
        self.assertEqual(self.window.login.devices.count(), 2)
        self.window.open_example()
        self.assertTrue(self.window.active)

    def test_failed_search_after_logout_does_not_reopen_previous_capture(self):
        self.receive()
        previous_path = self.window.session_path
        self.window.logout()
        self.window.search_devices()
        self.controller.bridge.emit('error', 'MadgeTech no está abierto.')
        self.window.consume()
        self.assertFalse(self.window.active)
        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertIsNone(self.window.session_path)
        self.assertEqual(len(Sesion.abrir(previous_path).registro.muestras), 1)

    def test_logout_drains_pending_sample_before_stopping_bridge(self):
        bridge = self.receive()
        path = self.window.session_path
        bridge.emit('mt_reading', payload('2026-09-29T08:05:00', '640'))
        self.window.logout()
        self.assertEqual(len(Sesion.abrir(path).registro.muestras), 2)

    def test_logout_save_failure_keeps_view_open_and_indicates_stopped_reception(self):
        self.receive()
        with patch.object(self.window.session, 'guardar', side_effect=OSError('Disco lleno')):
            self.window.logout()
        self.assertTrue(self.window.active)
        self.assertEqual(self.window.stack.currentIndex(), 1)
        self.assertFalse(self.controller.running)
        self.assertIn('DETENIDA', self.window.connection_badge.text())

    def test_close_drains_pending_sample_and_refuses_unsaved_exit(self):
        bridge = self.receive()
        path = self.window.session_path
        bridge.emit('mt_reading', payload('2026-09-29T08:05:00', '640'))
        event = QCloseEvent()
        self.window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(len(Sesion.abrir(path).registro.muestras), 2)
        event = QCloseEvent()
        with patch.object(self.window.session, 'guardar', side_effect=OSError('Disco lleno')):
            self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())

    def test_connection_diagnostics_received_before_ready_remain_in_notices(self):
        bridge = self.connect()
        bridge.emit('log', 'Authenticate aceptado en esta sesión WCF.')
        bridge.emit('mt_contract', dict(version='1.1.0.2', statuses=['Valid']))
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', payload())
        self.window.consume()
        text = self.window.alerts.log_text.toPlainText()
        self.assertIn('Authenticate aceptado', text)
        self.assertIn('1.1.0.2', text)

    def test_duplicate_latest_sample_does_not_request_graph_redraw(self):
        bridge = self.receive()
        self.window.flush_refresh()
        self.assertFalse(self.window.refresh_pending)
        bridge.emit('mt_reading', payload())
        self.window.consume()
        self.assertFalse(self.window.refresh_pending)
        self.assertEqual(len(self.window.session.registro.muestras), 1)

    def test_temporary_unavailability_recovers_without_replacing_session(self):
        bridge = self.receive()
        session = self.window.session
        bridge.emit('mt_waiting', 'MadgeTech todavía no dispone de una lectura.')
        self.window.consume()
        self.assertTrue(self.controller.running)
        self.assertIn('ESPERANDO', self.window.connection_badge.text())
        bridge.emit('mt_reading', payload('2026-09-29T08:05:00', '640'))
        self.window.consume()
        self.assertIs(self.window.session, session)
        self.assertIn('ACTIVA', self.window.connection_badge.text())
        self.assertEqual(len(self.window.session.registro.muestras), 2)

    def test_cancel_connection_clears_password_and_ignores_late_results(self):
        self.window.login.password.setText('secret in memory')
        bridge = self.connect()
        bridge.emit('mt_devices', ['R59022'])
        bridge.emit('mt_reading', payload())
        self.window.cancel_connection()
        self.window.consume()
        self.assertFalse(self.window.active)
        self.assertFalse(self.controller.running)
        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertTrue(self.window.login.demo_button.isEnabled())
        self.assertEqual(self.window.login.password.text(), '')

    def test_replay_preserves_original_timestamps_and_saves_all_samples(self):
        self.window.open_example()
        original = list(self.window.session.registro.muestras)
        original_path = self.window.session_path
        self.window.toggle_replay()
        self.window.replay_timer.stop()
        replay_path = self.window.session_path
        self.assertNotEqual(replay_path, original_path)
        self.assertEqual(len(self.window.session.registro.muestras), 1)
        self.assertIn('SIMULACIÓN', self.window.session.modo)
        while self.window.replay_rows:
            self.window.replay_step()
        self.window.replay_step()
        self.assertEqual(self.window.session.registro.muestras, original)
        self.assertEqual(Sesion.abrir(replay_path).registro.muestras, original)
        self.assertEqual(len(Sesion.abrir(original_path).registro.muestras), 93)
        self.assertFalse(self.window.replay_timer.isActive())
        self.assertIn('COMPLETO', self.window.connection_badge.text())

    def test_replay_write_failure_stops_timer_and_keeps_unsaved_sample(self):
        self.window.open_example()
        self.window.toggle_replay()
        with patch.object(self.window.session, 'guardar', side_effect=OSError('Disco lleno')):
            self.window.replay_step()
        self.assertFalse(self.window.replay_timer.isActive())
        self.assertEqual(len(self.window.session.registro.muestras), 2)
        self.assertEqual(len(Sesion.abrir(self.window.session_path).registro.muestras), 1)
        self.assertIn('memoria', self.window.alerts.log_text.toPlainText())
        self.assertNotIn('memoria', self.window.notice.text())

    def test_export_uses_snapshot_and_allows_reception_to_continue(self):
        bridge = self.receive()
        destination = self.state_dir / 'snapshot.csv'
        self.window.export_to(destination, 'CSV')
        process = self.window.export_process
        try:
            bridge.emit('mt_reading', payload('2026-09-29T08:05:00', '640'))
            self.window.consume()
            self.assertEqual(len(self.window.session.registro.muestras), 2)
            self.assertTrue(self.controller.running)
            self.assertTrue(process.waitForFinished(15000), 'La exportación CSV no finalizó.')
            self.qt.processEvents()
            self.assertEqual(self.window.last_export, destination)
            self.assertIsNone(self.window.export_snapshot)
            with destination.open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.reader(stream, delimiter=';'))
            self.assertEqual(len(rows), 2, 'Debe exportarse la primera muestra de la instantánea, no la segunda posterior.')
            self.assertEqual(len(Sesion.abrir(self.window.session_path).registro.muestras), 2)
        finally:
            if self.window.export_process is not None:
                self.window.export_process.kill()
                self.window.export_process.waitForFinished(3000)


if __name__ == '__main__':
    unittest.main()
