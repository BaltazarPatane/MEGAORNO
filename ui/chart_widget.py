"""Qt chart interaction; the measurement and gradient calculations stay in models.

The wheel zooms time around the pointer; Ctrl/Shift+wheel zooms only vertically.
Left-drag pans time and Ctrl+drag also pans the vertical scale. Manual navigation pauses
following so incoming measurements never take the operator away from a detail.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import asdict, dataclass, replace
from math import isfinite

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.dates import num2date
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from charts import COLORS, render_chart
from models import Sesion


CHANNEL_COLORS = (
    "#167aa5", "#41a17c", "#d68a39", "#8064ad", "#cf6265", "#3d9fa3",
    "#818d3f", "#4d729d", "#a37638", "#b3638a", "#6c69a6", "#637e78",
)


@dataclass(frozen=True)
class ChartOptions:
    mode: str = "Temperatura"
    unit: str = "°C/h"
    show_ideal: bool = False
    show_band: bool = False
    full_program: bool = False
    window_minutes: float = 0


class ChartWidget(QWidget):
    """Reusable chart; session contents are read only from this widget.

    ``view_changed`` carries whether automatic following is enabled, while
    ``cursor_text`` carries an actual recorded sample, never an interpolation.
    Methods must be called on the Qt GUI thread.
    """

    view_changed = Signal(bool)
    cursor_text = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.session = Sesion()
        self.follow = True
        self._options = ChartOptions()
        self._channels = []
        self._series = {}
        self._backgrounds = {}
        self._overlays = {}
        self._drag = None
        self._cursor_label = ""
        self._has_rendered = False
        self.figure = Figure(figsize=(9, 5), layout="constrained", facecolor="#ffffff")
        self.ax_t, self.ax_g = self.figure.subplots(2, 1, sharex=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.canvas.setMouseTracking(True)
        self.canvas.setMinimumSize(280, 240)
        self.canvas.setToolTip(
            "Rueda: acercar o alejar en el tiempo · Arrastrar: desplazar\n"
            "Ctrl/Mayús + rueda: sólo eje vertical · Ctrl + arrastrar: ambos ejes\n"
            "Doble clic: ajustar y volver a seguir las muestras\n"
            "El cursor muestra la lectura registrada más cercana, sin interpolar."
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self._connection_ids = [
            self.canvas.mpl_connect(name, handler)
            for name, handler in (
                ("scroll_event", self._on_scroll),
                ("button_press_event", self._on_press),
                ("button_release_event", self._on_release),
                ("motion_notify_event", self._on_motion),
                ("figure_leave_event", self._on_leave),
                ("draw_event", self._on_draw),
                ("resize_event", self._on_resize),
            )
        ]
        self.refresh(preserve_view=False)

    @property
    def options(self):
        return asdict(self._options)

    @property
    def channels(self):
        return list(self._channels)

    def set_session(self, session):
        self.session = session
        self._channels = list(range(len(session.registro.canales)))
        self._set_follow_state(True)
        self.refresh(preserve_view=False)

    def set_channels(self, indices):
        self._channels = list(dict.fromkeys(
            int(i) for i in indices if 0 <= int(i) < len(self.session.registro.canales)
        ))
        self.refresh()

    def set_options(self, *, mode=None, unit=None, show_ideal=None, show_band=None,
                    full_program=None, window_minutes=None):
        changes = {k: v for k, v in locals().items() if k != "self" and v is not None}
        candidate = replace(self._options, **changes)
        if candidate.mode not in ("Temperatura", "Gradiente", "Ambas"):
            raise ValueError("Modo de gráfico no reconocido.")
        if candidate.unit not in ("°C/h", "°C/min"):
            raise ValueError("Unidad de gradiente no reconocida.")
        if not isfinite(candidate.window_minutes) or candidate.window_minutes < 0:
            raise ValueError("La ventana de tiempo debe ser finita y no negativa.")
        previous = self._options
        self._options = candidate
        # A new time-window is an explicit request to frame that interval.
        if (candidate.window_minutes, candidate.full_program) != (previous.window_minutes, previous.full_program):
            self.fit_view()
            return
        # Manual time navigation survives changing units or switching plots;
        # vertical limits are recalculated because the scale may have changed.
        old_x = self.ax_t.get_xlim()
        reset_y = candidate.unit != previous.unit or candidate.mode != previous.mode
        self.refresh(preserve_view=not reset_y)
        if reset_y and not self.follow:
            self.ax_t.set_xlim(old_x)
            self.canvas.draw_idle()

    def refresh(self, preserve_view=True):
        keep_limits = preserve_view and not self.follow and self._has_rendered
        limits = [(ax.get_xlim(), ax.get_ylim()) for ax in (self.ax_t, self.ax_g)]
        self._backgrounds.clear()
        self._drag = None
        self._set_cursor_text("")
        self._series = render_chart(
            self.figure, self.ax_t, self.ax_g, self.session, self._channels,
            **asdict(self._options),
        )
        self._style_chart()
        if keep_limits:
            for ax, (xlim, ylim) in zip((self.ax_t, self.ax_g), limits):
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
        self._create_cursor()
        self._has_rendered = True
        self.canvas.draw_idle()

    def fit_view(self):
        self._set_follow_state(True)
        self.refresh(preserve_view=False)

    def set_follow(self, follow):
        self._set_follow_state(bool(follow))
        if self.follow:
            self.refresh(preserve_view=False)

    def _set_follow_state(self, follow):
        if self.follow != follow:
            self.follow = follow
            self.view_changed.emit(follow)

    def _style_chart(self):
        valid = [i for i in self._channels if 0 <= i < len(self.session.registro.canales)]
        mapping = {COLORS[i % len(COLORS)]: CHANNEL_COLORS[i % len(CHANNEL_COLORS)] for i in valid}
        if len(valid) == 1:
            mapping["#ff4040"] = CHANNEL_COLORS[valid[0] % len(CHANNEL_COLORS)]
        for ax in (self.ax_t, self.ax_g):
            ax.set_facecolor("#ffffff")
            ax.grid(which="major", color="#e1e7eb", linewidth=.7)
            ax.grid(which="minor", color="#f1f4f6", linewidth=.4)
            ax.tick_params(colors="#637581", labelsize=9, length=3)
            for name, spine in ax.spines.items():
                spine.set_color("#dce3e7")
                spine.set_visible(name in ("left", "bottom"))
            ax.xaxis.label.set_color("#647783")
            ax.yaxis.label.set_color("#647783")
            ax.xaxis.label.set_size(9)
            ax.yaxis.label.set_size(9)
            for line, series in zip(ax.lines, self._series.get(ax, [])):
                color = mapping.get(series["color"], series["color"])
                line.set_color(color)
                line.set_linewidth(1.5)
                series["color"] = color
            legend = ax.get_legend()
            if legend is not None:
                # Rebuild after recolouring so keys and measurements agree.
                ax.legend(loc="upper left", fontsize=8,
                          ncol=min(3, len(ax.get_legend_handles_labels()[0])),
                          facecolor="white", edgecolor="#e3e9ec", framealpha=.93)
            if ax is self.ax_t:
                ax.set_ylabel("Temperatura (°C)")

    def _create_cursor(self):
        self._overlays = {}
        for ax in (self.ax_t, self.ax_g):
            vertical = ax.axvline(0, color="#7d929e", linewidth=.75,
                                  linestyle=(0, (3, 3)), animated=True, visible=False)
            marker, = ax.plot([], [], "o", markersize=5, markeredgecolor="white",
                              markeredgewidth=1, animated=True, visible=False, zorder=10)
            label = ax.annotate(
                "", xy=(.99, .98), xycoords="axes fraction", ha="right", va="top",
                fontsize=12, linespacing=1.5, color="#17394c", animated=True, visible=False, zorder=11,
                bbox=dict(boxstyle="round,pad=.65", fc="#f5fafc", ec="#97b7c8", alpha=.98),
            )
            label.set_in_layout(False)
            self._overlays[ax] = (vertical, marker, label)

    @staticmethod
    def _modifiers(event):
        # Qt's wheel event is authoritative: Matplotlib's cached key can be
        # stale when focus changes or Ctrl is pressed outside the canvas.
        gui_event=getattr(event,'guiEvent',None)
        if gui_event is not None and hasattr(gui_event,'modifiers'):
            modifiers=gui_event.modifiers()
            return (bool(modifiers & Qt.KeyboardModifier.ControlModifier),
                    bool(modifiers & Qt.KeyboardModifier.ShiftModifier))
        modifiers=getattr(event,'modifiers',None)
        if modifiers is not None:
            return ('ctrl' in modifiers or 'control' in modifiers,'shift' in modifiers)
        key = (getattr(event, "key", None) or "").lower()
        return "ctrl" in key or "control" in key, "shift" in key

    def _is_active_axis(self, ax):
        return ax in (self.ax_t, self.ax_g) and ax.get_visible()

    def _on_scroll(self, event):
        if not self._is_active_axis(event.inaxes) or event.xdata is None:
            return
        step = float(getattr(event, "step", 0))
        if not step:
            return
        ctrl, shift = self._modifiers(event)
        factor = 1.25 ** -max(-8., min(8., step))
        ax = event.inaxes
        if not (ctrl or shift):
            low, high = ax.get_xlim()
            span = (high - low) * factor
            data = self.session.registro.muestras
            data_days = (data[-1][0] - data[0][0]).total_seconds() / 86400 if len(data) > 1 else 0
            span = min(max(span, .1 / 86400), max(1., data_days * 8))
            ratio = (event.xdata - low) / (high - low)
            ax.set_xlim(event.xdata - ratio * span, event.xdata + (1 - ratio) * span)
        if (ctrl or shift) and event.ydata is not None:
            low, high = ax.get_ylim()
            span = max((high - low) * factor, 1e-6)
            ratio = (event.ydata - low) / (high - low)
            ax.set_ylim(event.ydata - ratio * span, event.ydata + (1 - ratio) * span)
        self._set_follow_state(False)
        self._hide_cursor()
        self._backgrounds.clear()
        self.canvas.draw_idle()

    def _on_press(self, event):
        if event.button != 1 or not self._is_active_axis(event.inaxes):
            return
        if event.dblclick:
            self.fit_view()
            return
        self.canvas.setFocus()
        self._drag = dict(axis=event.inaxes, x=event.x, y=event.y,
                          xlim=event.inaxes.get_xlim(), ylim=event.inaxes.get_ylim(),
                          modifiers=self._modifiers(event), moved=False)

    def _on_motion(self, event):
        if self._drag is not None:
            self._pan_to(event)
            return
        self._show_cursor(event)

    def _show_cursor(self, event):
        if not self._is_active_axis(event.inaxes) or event.xdata is None:
            self._hide_cursor()
            return
        point = self._nearest_sample(event)
        if point is None:
            self._hide_cursor()
            return
        series, x, y = point
        unit = "°C" if event.inaxes is self.ax_t else self._options.unit
        timestamp = num2date(x).strftime("%d/%m/%Y %H:%M:%S")
        label_text = f"{series['name']} · {timestamp} · {y:.10g} {unit}"
        self._set_cursor_text(label_text)
        for ax, (vertical, marker, label) in self._overlays.items():
            vertical.set_xdata([x, x])
            vertical.set_visible(ax.get_visible())
            active = ax is event.inaxes
            marker.set_visible(active)
            label.set_visible(active)
            if active:
                marker.set_data([x], [y])
                marker.set_color(series["color"])
                from textwrap import wrap
                name='\n'.join(wrap(series['name'],width=max(18,int(ax.bbox.width/10)),break_long_words=True))
                measure='Temperatura' if ax is self.ax_t else 'Gradiente'
                label.set_text(f"{name}\n{measure}: {y:.10g} {unit}\n{timestamp}")
        self._draw_cursor()

    def _nearest_sample(self, event):
        """Find a real sample using pixel distance; no point is interpolated."""
        nearest = None
        distance = float("inf")
        ax = event.inaxes
        xlow, xhigh = sorted(ax.get_xlim())
        ylow, yhigh = sorted(ax.get_ylim())
        for series in self._series.get(ax, []):
            xs = series["x"]
            index = bisect_left(xs, event.xdata)
            for i in (index - 1, index):
                if not 0 <= i < len(xs):
                    continue
                x, y = xs[i], series["y"][i]
                if not (xlow <= x <= xhigh and ylow <= y <= yhigh):
                    continue
                px, py = ax.transData.transform((x, y))
                candidate = (px - event.x) ** 2 + (py - event.y) ** 2
                if candidate < distance:
                    distance, nearest = candidate, (series, x, y)
        return nearest

    def _pan_to(self, event):
        drag = self._drag
        dx, dy = event.x - drag["x"], event.y - drag["y"]
        if not drag["moved"] and abs(dx) + abs(dy) < 3:
            return
        drag["moved"] = True
        ax = drag["axis"]
        ctrl, shift = drag["modifiers"]
        if not shift:
            low, high = drag["xlim"]
            delta = -dx * (high - low) / max(ax.bbox.width, 1)
            ax.set_xlim(low + delta, high + delta)
        if ctrl or shift:
            low, high = drag["ylim"]
            delta = -dy * (high - low) / max(ax.bbox.height, 1)
            ax.set_ylim(low + delta, high + delta)
        self._set_follow_state(False)
        self.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._hide_cursor()
        self._backgrounds.clear()
        self.canvas.draw_idle()

    def _on_release(self, event):
        clicked=self._drag is not None and not self._drag['moved']
        self._drag = None
        self.canvas.unsetCursor()
        if clicked:self._show_cursor(event)

    def _on_leave(self, event):
        self._hide_cursor()
        # Qt can deliver a release outside the plot; leave cancels stale drags.
        self._drag = None
        self.canvas.unsetCursor()

    def _on_resize(self, event):
        self._backgrounds.clear()

    def _on_draw(self, event):
        # Large tooltips can extend beyond a short subplot. Capture the whole
        # canvas so hiding one also restores the margins, without ghost text.
        self._backgrounds = {'figure': self.canvas.copy_from_bbox(self.figure.bbox)}
        # draw_event runs inside Qt's paint cycle. Draw into Agg here and let
        # the ongoing paint finish; blit/repaint here would recurse into Qt.
        for ax in (self.ax_t,self.ax_g):
            if not ax.get_visible():continue
            for artist in self._overlays.get(ax, ()):
                if artist.get_visible():ax.draw_artist(artist)

    def _draw_cursor(self):
        background=self._backgrounds.get('figure')
        if background is None:return
        self.canvas.restore_region(background)
        for ax in (self.ax_t,self.ax_g):
            if not ax.get_visible():
                continue
            for artist in self._overlays.get(ax, ()):
                if artist.get_visible():
                    ax.draw_artist(artist)
        self.canvas.blit(self.figure.bbox)

    def _set_cursor_text(self, text):
        if text != self._cursor_label:
            self._cursor_label = text
            self.cursor_text.emit(text)

    def _hide_cursor(self):
        for artists in self._overlays.values():
            for artist in artists:
                artist.set_visible(False)
        self._set_cursor_text("")
        self._draw_cursor()
