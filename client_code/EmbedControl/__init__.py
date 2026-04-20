from ._anvil_designer import EmbedControlTemplate
from anvil import *
import anvil.server
import datetime


class EmbedControl(EmbedControlTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._build_layout()
        self._refresh_all()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        p = self.content_panel
        p.add_component(Label(
            text='AADP Control',
            role='title', bold=True, font_size=20,
            spacing_above='small', spacing_below='small',
        ))

        # ── 1. Heartbeat ──────────────────────────────────────────────────────
        hb_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._hb_dot = Label(text='\u25cf', font_size=14)
        self._hb_label = Label(text='Checking\u2026', role='body', font_size=14)
        hb_row.add_component(self._hb_dot)
        hb_row.add_component(self._hb_label)
        p.add_component(hb_row)

        # ── 2. Session status ─────────────────────────────────────────────────
        self._session_label = Label(
            text='Session: \u2014',
            role='body', font_size=14,
            spacing_above='none', spacing_below='small',
        )
        p.add_component(self._session_label)

        # ── 3. Autonomous mode toggle ─────────────────────────────────────────
        p.add_component(Label(text='\u2015' * 28, role='body', font_size=14))
        auto_row = FlowPanel(spacing_above='small', spacing_below='none')
        self._auto_btn = Button(text='\u23f3 Checking\u2026', role='tonal-button')
        self._auto_btn.set_event_handler('click', self._auto_mode_clicked)
        auto_row.add_component(self._auto_btn)
        p.add_component(auto_row)
        self._auto_feedback = Label(text='', role='body', font_size=13)
        p.add_component(self._auto_feedback)

    # ── Data loaders ──────────────────────────────────────────────────────────

    def _refresh_all(self):
        self._check_heartbeat()
        self._check_session_status()
        self._refresh_auto_status()

    def _check_heartbeat(self):
        try:
            with anvil.server.no_loading_indicator:
                anvil.server.call('ping')
            self._hb_dot.foreground = '#4caf50'
            self._hb_label.text = 'Connected'
        except Exception:
            self._hb_dot.foreground = '#f44336'
            ts = datetime.datetime.now().strftime('%H:%M')
            self._hb_label.text = f'Unreachable \u2014 last checked {ts}'

    def _check_session_status(self):
        try:
            with anvil.server.no_loading_indicator:
                s = anvil.server.call('get_lean_status')
            if s.get('running'):
                self._session_label.text = f"\u23f3 Session running (PID {s['pid']})"
            else:
                self._session_label.text = '\u25cb Session idle'
        except Exception as e:
            self._session_label.text = f'Status unknown: {e}'

    def _refresh_auto_status(self):
        try:
            with anvil.server.no_loading_indicator:
                s = anvil.server.call('get_autonomous_mode')
            active = s.get('scheduler_active')
            if active is True:
                self._auto_btn.text = '\U0001f7e2 Autonomous: ON'
                self._auto_btn.role = 'filled-button'
            elif active is False:
                self._auto_btn.text = '\u26aa Autonomous: OFF'
                self._auto_btn.role = 'tonal-button'
            else:
                self._auto_btn.text = '\u2753 Autonomous: Unknown'
                self._auto_btn.role = 'tonal-button'
        except Exception as e:
            self._auto_btn.text = f'\u274c Error: {e}'

    def _auto_mode_clicked(self, **event_args):
        self._auto_feedback.text = 'Updating\u2026'
        try:
            with anvil.server.no_loading_indicator:
                s = anvil.server.call('get_autonomous_mode')
            new_state = not s.get('scheduler_active', False)
            with anvil.server.no_loading_indicator:
                result = anvil.server.call('set_autonomous_mode', new_state)
            self._refresh_auto_status()
            errors = result.get('errors', [])
            self._auto_feedback.text = ('Enabled' if new_state else 'Disabled') if not errors else 'Partial: ' + '; '.join(errors)
        except Exception as e:
            self._auto_feedback.text = f'\u274c {e}'
