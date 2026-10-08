"""Adquisición MadgeTech independiente de Qt y de la presentación.

El consumidor debe llamar ``drain`` periódicamente. Cada muestra se valida,
conserva en memoria y guarda antes de notificarla a la interfaz. Abrir una
tubería o encontrar un dispositivo no equivale a recibir temperaturas válidas.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
from urllib.parse import urlsplit

from live import WcfBridge, carpeta_madgetech, decodificar_madgetech
from models import Perfil, Registro, Sesion, fecha_local


@dataclass(frozen=True)
class ConnectionSettings:
    endpoint: str = 'net.pipe://localhost/MT4Data'
    poll_seconds: int = 5
    vendor_dir: str = field(default_factory=carpeta_madgetech)
    authenticate: bool = False
    username: str = field(default='', repr=False)
    password: str = field(default='', repr=False)
    serial: str = ''
    unit: str = 'Auto'
    valid_status: str = 'Auto'

    def bridge_config(self, mode):
        endpoint = self.endpoint.strip()
        uri = urlsplit(endpoint)
        if (uri.scheme != 'net.pipe' or uri.hostname not in ('localhost', '127.0.0.1', '::1')
                or uri.username is not None or uri.password is not None or uri.query or uri.fragment):
            raise ValueError('La dirección WCF debe ser una tubería net.pipe local, por ejemplo net.pipe://localhost/MT4Data.')
        if isinstance(self.poll_seconds, bool) or not isinstance(self.poll_seconds, int) or not 1 <= self.poll_seconds <= 3600:
            raise ValueError('El sondeo debe ser un número entero entre 1 y 3600 segundos.')
        if not self.vendor_dir.strip():
            raise ValueError('Elegí la carpeta de instalación de MadgeTech 4.')
        if self.unit not in ('Auto', '°C', '°F', 'K') or not self.valid_status:
            raise ValueError('Revisá la unidad y el estado válido de las lecturas.')
        if self.authenticate and (not self.username.strip() or not self.password):
            raise ValueError('La autenticación WCF requiere usuario y contraseña.')
        return dict(mode=mode, endpoint=endpoint, poll_seconds=self.poll_seconds,
                    vendor_dir=self.vendor_dir.strip(), serial=self.serial.strip(),
                    authenticate='true' if self.authenticate else 'false',
                    username=self.username if self.authenticate else '',
                    password=self.password if self.authenticate else '', security='transport')


class _OperationQueue:
    """Distingue solicitudes de puentes distintos aunque ambos usen request_id=1."""
    def __init__(self, target, generation):
        self.target, self.generation = target, generation

    def put(self, event):
        self.target.put(dict(event, _generation=self.generation))


class AcquisitionController:
    """Un único flujo WCF, con captura durable y eventos de UI sin credenciales.

    Eventos: state(str), devices(list[str]), selection_required(list[str]),
    contract(dict), ready(Sesion), sample(dict), warning/error/log(str).
    ``sample`` contiene changed, valid, total, timestamp y errors. La sesión
    permanece accesible después de disconnect o de un error de adquisición.
    """
    def __init__(self, state_dir, bridge_factory=WcfBridge):
        self.state_dir = Path(state_dir)
        self.bridge_factory = bridge_factory
        self.events = queue.Queue()
        self.bridge = None
        self.session = None
        self.session_path = None
        self.state = 'disconnected'
        self._notifications = []
        self._generation = 0
        self._request_id = None
        self._mode = ''
        self._serial = ''
        self._unit = self._valid_status = 'Auto'
        self._ready = False
        self._raw_hash = ''
        self._secrets = ()
        self._last_warning = None
        self._last_waiting = None
        self._channel_issues = {}
        self._ever_valid = set()
        self._no_valid_reported = False
        self._stream_epoch = 0
        self._resume_after = None
        self._pause_cut_pending = False

    @property
    def running(self):
        # A paused session still owns its bridge and capture file.
        return self.state in ('searching', 'connecting', 'waiting', 'receiving', 'paused')

    @property
    def paused(self):
        return self.state == 'paused'

    @property
    def can_pause(self):
        return self._ready and self._mode == 'mt_poll' and self.state in ('waiting', 'receiving', 'paused')

    def pause(self):
        if self.paused:return
        if not self.can_pause:raise ValueError('No hay una adquisición activa para pausar.')
        self._stream_epoch += 1
        self._state('paused')
        self._resume_after = self.session.registro.muestras[-1][0]
        self._pause_cut_pending = True
        try:self.bridge.set_paused(True, self._stream_epoch)
        except Exception as error:
            self._fail(error)
            return
        self._emit('log', 'Adquisición pausada. La sesión y las muestras acumuladas se conservan.')

    def resume(self):
        if not self.paused:raise ValueError('La adquisición no está pausada.')
        self._stream_epoch += 1
        try:self.bridge.set_paused(False, self._stream_epoch)
        except Exception as error:
            self._fail(error)
            return
        self._state('waiting')
        self._emit('log', 'Adquisición reanudada. Esperando una lectura nueva; no se recuperan las muestras del intervalo pausado.')

    def _redact(self, message):
        text = str(message)
        for secret in self._secrets:
            if secret:
                text = text.replace(secret, '[oculto]')
        return text

    def _emit(self, kind, data):
        if kind in ('log', 'warning', 'error'):
            data = self._redact(data)
        self._notifications.append(dict(type=kind, data=data))

    def _state(self, state):
        if self.state != state:
            self.state = state
            self._emit('state', state)

    def _stop(self):
        self._request_id = None
        self._generation += 1
        if self.bridge is not None:
            self.bridge.stop()
        self._mode = ''

    def disconnect(self):
        """Detiene el puente; no descarta ni reemplaza los datos adquiridos."""
        self._stop()
        self._state('disconnected')

    def _begin(self, settings, config):
        self._generation += 1
        self._secrets = tuple(sorted((settings.password, settings.username), key=len, reverse=True))
        self._mode = config['mode']
        self._serial = settings.serial.strip()
        self._unit, self._valid_status = settings.unit, settings.valid_status
        self._last_warning = None
        self._last_waiting = None
        self._channel_issues.clear()
        self._ever_valid.clear()
        self._no_valid_reported = False
        self._stream_epoch = 0
        self._resume_after = None
        self._pause_cut_pending = False
        self.bridge = self.bridge_factory(_OperationQueue(self.events, self._generation))
        self._state('searching' if self._mode == 'mt_list' else 'connecting')
        try:
            self.bridge.start(config, self.state_dir)
            self._request_id = self.bridge.request_id
        except Exception as error:
            self._fail(error)

    def search(self, settings):
        if self.running:
            raise ValueError('Esperá o desconectá la operación WCF actual.')
        config = settings.bridge_config('mt_list')
        self._begin(settings, config)

    def connect(self, settings, session_path, profile=None):
        """Crea la captura antes de abrir WCF y recibe sin consultas preliminares."""
        if self.running:
            raise ValueError('Esperá o desconectá la operación WCF actual.')
        config = settings.bridge_config('mt_poll')
        path = Path(session_path)
        if not path.name.endswith('.horno.json'):
            raise ValueError('La captura debe guardarse con extensión .horno.json.')
        # Un segundo intento de selección puede reutilizar nuestra captura vacía.
        own_empty = path == self.session_path and self.session is not None and not self.session.registro.muestras
        if path.exists() and not own_empty:
            raise FileExistsError('Ya existe esa captura. Elegí otro nombre para conservar los datos anteriores.')
        selected_profile = deepcopy(profile if profile is not None else Perfil())
        selected_profile.validar()
        session = Sesion(registro=Registro(origen='MadgeTech 4 · ' + config['endpoint'],
                                          serie=config['serial'], notas=[
            'Los canales se identifican por posición WCF; verificar su correspondencia física en MadgeTech.',
            'Interpretación WCF: unidad=' + settings.unit + '; estado válido=' + settings.valid_status + '.',
            'El sondeo consulta la última lectura; no modifica la frecuencia de muestreo del equipo.',
        ]), perfil=selected_profile, modo='Recepción MadgeTech WCF')
        path.parent.mkdir(parents=True, exist_ok=True)
        session.guardar(path)
        # Comprobar también el destino del respaldo original antes de adquirir.
        with open(str(path) + '.wcf.jsonl', 'a', encoding='utf-8') as stream:
            stream.flush()
            os.fsync(stream.fileno())
        self.session, self.session_path = session, path
        self._ready = False
        self._raw_hash = ''
        self._begin(settings, config)

    def _fail(self, error):
        self._stop()
        self._state('error')
        self._emit('error', str(error))

    def _capture_raw(self, payload):
        # Sólo campos de medición: nunca persistir configuraciones o eventos de log.
        raw = dict(serial=payload['serial'], timestamp=payload['timestamp'], channels=[
            {key: channel.get(key) for key in ('position', 'unit', 'status', 'value')}
            for channel in payload['channels']])
        serialized = json.dumps(raw, ensure_ascii=False, sort_keys=True, allow_nan=False)
        digest = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        if digest == self._raw_hash:
            return
        record = dict(recibida=datetime.now().astimezone().isoformat(), madgetech=raw)
        with open(str(self.session_path) + '.wcf.jsonl', 'a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        self._raw_hash = digest

    def _reading(self, payload):
        if self.paused or self._mode != 'mt_poll' or self.session is None:
            return
        if not isinstance(payload, dict) or not self._serial or payload.get('serial') != self._serial:
            raise ValueError('La lectura no coincide con el equipo seleccionado. Recepción detenida.')
        diagnostics=[]
        rows, errors = decodificar_madgetech(payload, self._unit, self._valid_status,diagnostics=diagnostics)
        timestamp=fecha_local(payload['timestamp'])
        if self._resume_after is not None and timestamp<=self._resume_after:
            return
        if self._pause_cut_pending and rows:
            self.session.registro.cortes.append(timestamp)
            self._pause_cut_pending = False
        count = self.session.registro.agregar(rows, self.session.perfil.hueco_max)
        if self._resume_after is not None and rows:self._resume_after=timestamp
        valid = sum(value is not None for _, _, value in rows)
        # Si falla la escritura, los datos nuevos siguen en memoria y se detiene WCF.
        try:
            self._capture_raw(payload)
            if count or not self._ready:
                self.session.guardar(self.session_path)
        except (OSError, ValueError, TypeError) as error:
            raise OSError('No se pudo guardar la captura; la recepción se detuvo. Los datos siguen en memoria. ' + str(error)) from error
        self._report_channel_changes(rows,diagnostics)
        self._last_waiting = None
        if valid and not self._ready:
            self._ready = True
            self._state('receiving')
            self._emit('ready', self.session)
        elif valid:
            self._state('receiving')
        else:
            self._state('waiting')
            if not self._no_valid_reported:
                self._emit('warning', 'MadgeTech todavía no devolvió canales con temperaturas válidas.')
        self._no_valid_reported = not bool(valid)
        self._emit('sample', dict(changed=count, valid=valid, total=len(rows),
                                  timestamp=payload['timestamp'], errors=[self._redact(e) for e in errors]))

    def _report_channel_changes(self,rows,diagnostics):
        """Aggregate transitions; empty unused inputs do not flood diagnostics.

        Raw responses and explicit None samples remain untouched. A sensor that
        used to work still reports its loss once and starts a new gradiente baseline
        on recovery. Unknown units/values are reported once per channel/reason.
        """
        changed=[]
        for issue in diagnostics:
            channel,key=issue['channel'],issue['key']
            previous=self._channel_issues.get(channel)
            if key!=previous and (channel in self._ever_valid or not issue['quiet']):
                changed.append(issue['message'])
            self._channel_issues[channel]=key
        recovered=[]
        for _,channel,value in rows:
            if value is not None:
                if channel in self._channel_issues and channel in self._ever_valid:recovered.append(channel)
                self._channel_issues.pop(channel,None)
                self._ever_valid.add(channel)
        if changed:
            details='\n'.join(changed[:4])
            if len(changed)>4:details+=f'\nY {len(changed)-4} canales adicionales. Estados originales conservados en el respaldo WCF.'
            self._emit('warning',details)
        if recovered:
            self._emit('log',f'Lectura recuperada en {len(recovered)} canal(es). El gradiente vuelve a calcularse desde una nueva pareja de muestras válidas.')

    def _handle(self, event):
        kind, data = event.get('type'), event.get('data')
        if kind == 'mt_devices':
            if not isinstance(data, list) or any(not isinstance(serial, str) or not serial.strip() for serial in data):
                raise ValueError('La lista de equipos WCF no es válida.')
            devices = list(dict.fromkeys(data))
            self._emit('devices', devices)
            if self._mode == 'mt_poll':
                if not devices:
                    raise ValueError('MadgeTech no informa equipos conectados. Revisá la conexión y la adquisición en MadgeTech 4.')
                if self._serial and self._serial not in devices:
                    raise ValueError('El equipo seleccionado ya no está conectado.')
                if not self._serial and len(devices) > 1:
                    self._stop()
                    self._state('selection_required')
                    self._emit('selection_required', devices)
                else:
                    self._serial = self._serial or devices[0]
                    self.session.registro.serie = self._serial
        elif kind == 'mt_select':
            self._stop()
            self._state('selection_required')
            self._emit('selection_required', data)
        elif kind == 'mt_reading':
            self._reading(data)
        elif kind == 'mt_contract':
            self._emit('contract', data)
        elif kind in ('transport_open', 'mt_waiting'):
            if self._mode == 'mt_poll':
                self._state('waiting')
            message='Tubería abierta; esperando una temperatura válida.' if kind == 'transport_open' else data
            if message != self._last_waiting:self._emit('log', message)
            self._last_waiting = message
        elif kind in ('error', 'fault'):
            self._fail(data)
        elif kind == 'log':
            self._emit('log', data)
        elif kind == 'finished':
            if self._mode == 'mt_poll':
                self._fail('El puente WCF terminó. La captura se conserva; revisá MadgeTech antes de reconectar.')
            elif self._mode == 'mt_list':
                self._stop()
                self._state('disconnected')

    def drain(self):
        """Procesa eventos pendientes; descarta resultados de operaciones canceladas."""
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event.get('_generation') != self._generation or self._request_id is None:
                continue
            if event.get('request_id') != self._request_id:
                continue
            if event.get('type') in ('mt_reading','mt_waiting'):
                # Discard queued/in-flight results from before any pause or
                # resume, even if they arrive after a rapid pause/resume cycle.
                if self.paused or event.get('epoch',0)!=self._stream_epoch:continue
            try:
                self._handle(event)
            except Exception as error:
                self._fail(error)
        notifications, self._notifications = self._notifications, []
        return notifications
