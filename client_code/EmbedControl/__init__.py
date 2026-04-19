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

        # ── 5. Output display ─────────────────────────────────────────────────
        p.add_component(Label(text='\u2015' * 28, role='body', font_size=14))
        p.add_component(Label(
            text='Last Session', bold=True, role='body', font_size=15,
            spacing_above='small', spacing_below='small',
        ))
        self._output_panel = ColumnPanel()
        self._output_panel.add_component(Label(
            text='No session data yet.', role='body', font_size=13,
        ))
        p.add_component(self._output_panel)

    # ── Data loaders ──────────────────────────────────────────────────────────

    def _refresh_all(self):
        self._check_heartbeat()
        self._check_session_status()
        self._load_last_output()

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

    def _load_last_output(self):
        self._output_panel.clear()
        try:
            with anvil.server.no_loading_indicator:
                artifacts = anvil.server.call('get_session_artifacts', 1)
            if not artifacts:
                self._output_panel.add_component(Label(
                    text='No session artifacts yet.', role='body', font_size=13,
                ))
                return
            a = artifacts[0]
            title = a.get('title') or a.get('filename', '(unknown)')
            date = a.get('date') or ''
            content = a.get('content') or ''

            self._output_panel.add_component(Label(
                text=title[:80], bold=True, role='body', font_size=14,
            ))
            if date:
                self._output_panel.add_component(Label(
                    text=date, role='body', font_size=12,
                ))

            # Show first meaningful section (up to 400 chars)
            preview = content[:400].strip()
            if len(content) > 400:
                preview += '\u2026'
            self._output_panel.add_component(Label(
                text=preview, role='body', font_size=13,
            ))
        except Exception as e:
            self._output_panel.add_component(Label(
                text=f'Error loading output: {e}', role='body', font_size=13,
            ))

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
        self._start_feedback.text = 'Starting\u2026'
        self._start_btn.enabled = False
        try:
            result = anvil.server.call('trigger_lean_session')
            self._start_feedback.text = result.get('message', '\u2705 Session triggered.')
        except Exception as e:
            self._start_feedback.text = f'\u274c {e}'
            self._start_btn.enabled = True
        self._check_session_status()
