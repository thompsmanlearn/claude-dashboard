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
        self._hb_dot = Label(text='\u25cf', font_size=14)  # ●
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

        p.add_component(Label(text='\u2015' * 28, role='body', font_size=14))

        # ── 3. Direction input ────────────────────────────────────────────────
        p.add_component(Label(
            text='Direction', bold=True, role='body', font_size=15,
            spacing_above='small', spacing_below='none',
        ))
        p.add_component(Label(
            text='What should the system work on?',
            role='body', font_size=13,
            spacing_above='none', spacing_below='small',
        ))
        self._direction_box = TextArea(
            placeholder='Enter direction or "Run: B-NNN"\u2026',
            role='outlined', height=72,
        )
        p.add_component(self._direction_box)

        dir_row = FlowPanel(spacing_above='small', spacing_below='small')
        self._dir_btn = Button(text='Write Directive', role='filled-button')
        self._dir_btn.set_event_handler('click', self._write_directive_clicked)
        dir_row.add_component(self._dir_btn)
        self._dir_feedback = Label(text='', role='body', font_size=13)
        dir_row.add_component(self._dir_feedback)
        p.add_component(dir_row)

        # ── 4. Start session button ───────────────────────────────────────────
        p.add_component(Label(text='\u2015' * 28, role='body', font_size=14))
        self._start_btn = Button(
            text='\u25b6 Start Session', role='tonal-button',
            spacing_above='small',
        )
        self._start_btn.set_event_handler('click', self._start_clicked)
        p.add_component(self._start_btn)
        self._start_feedback = Label(text='', role='body', font_size=13)
        p.add_component(self._start_feedback)

        # ── 5. Autonomous mode toggle ─────────────────────────────────────────
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
                self._start_btn.enabled = False
                self._start_btn.text = '\u23f3 Session running'
            else:
                self._session_label.text = '\u25cb Session idle'
                self._start_btn.enabled = True
                self._start_btn.text = '\u25b6 Start Session'
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

    # ── Event handlers ────────────────────────────────────────────────────────

    def _write_directive_clicked(self, **event_args):
        text = (self._direction_box.text or '').strip()
        if not text:
            self._dir_feedback.text = '\u274c Enter a directive first.'
            return
        self._dir_feedback.text = 'Writing\u2026'
        self._dir_btn.enabled = False
        try:
            anvil.server.call('write_directive', text)
            self._dir_feedback.text = '\u2705 Directive written.'
            self._direction_box.text = ''
        except Exception as e:
            self._dir_feedback.text = f'\u274c {e}'
        finally:
            self._dir_btn.enabled = True

    def _start_clicked(self, **event_args):
        self._start_feedback.text = 'Checking\u2026'
        self._start_btn.enabled = False
        try:
            with anvil.server.no_loading_indicator:
                s = anvil.server.call('get_lean_status')
            if s.get('running'):
                self._start_feedback.text = f'\u26a0\ufe0f Claude already running (PID {s["pid"]}) \u2014 close that session first.'
                self._start_btn.enabled = False
                return
            result = anvil.server.call('trigger_lean_session')
            self._start_feedback.text = result.get('message', '\u2705 Session triggered.')
        except Exception as e:
            self._start_feedback.text = f'\u274c {e}'
            self._start_btn.enabled = True
        self._check_session_status()
