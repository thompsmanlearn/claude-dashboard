from ._anvil_designer import Form1Template
from anvil import *
import anvil.server


class Form1(Form1Template):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._build_layout()
        self.refresh_data()

    def _build_layout(self):
        header = FlowPanel(spacing_above='none', spacing_below='small')
        header.add_component(Label(text='AADP Dashboard', role='headline', bold=True))
        btn = Button(text='Refresh All', role='filled-button')
        btn.set_event_handler('click', self._refresh_clicked)
        header.add_component(btn)
        self.content_panel.add_component(header)

        self._status_card = ColumnPanel(role='outlined-card')
        self.content_panel.add_component(self._status_card)

        self._agents_card = ColumnPanel(role='outlined-card')
        self.content_panel.add_component(self._agents_card)

        self._queue_card = ColumnPanel(role='outlined-card')
        self.content_panel.add_component(self._queue_card)

        self._inbox_card = ColumnPanel(role='outlined-card')
        self.content_panel.add_component(self._inbox_card)

        self._controls_card = ColumnPanel(role='outlined-card')
        self._build_controls()
        self.content_panel.add_component(self._controls_card)

    def _build_controls(self):
        self._controls_card.add_component(
            Label(text='Controls', role='title', bold=True)
        )

        # Lean session
        self._controls_card.add_component(Label(text='Lean Session', bold=True, role='body'))
        lean_row = FlowPanel(spacing_above='none', spacing_below='none')
        lean_btn = Button(text='Trigger Lean Session', role='tonal-button')
        lean_btn.set_event_handler('click', self._trigger_lean_clicked)
        lean_row.add_component(lean_btn)
        self._controls_card.add_component(lean_row)
        self._lean_feedback = Label(text='', role='body')
        self._controls_card.add_component(self._lean_feedback)

        self._controls_card.add_component(Label(text='\u2015' * 30, role='body'))

        # Write directive
        self._controls_card.add_component(Label(text='Write Directive', bold=True, role='body'))
        self._controls_card.add_component(
            Label(text='Overwrites DIRECTIVES.md and pushes to claudis.', role='body')
        )
        self._directive_input = TextArea(
            placeholder='Enter directive text (e.g. "Run: B-030" or free text)',
            role='outlined',
            height=80,
        )
        self._controls_card.add_component(self._directive_input)
        directive_btn = Button(text='Write Directive', role='tonal-button')
        directive_btn.set_event_handler('click', self._write_directive_clicked)
        self._controls_card.add_component(directive_btn)
        self._directive_feedback = Label(text='', role='body')
        self._controls_card.add_component(self._directive_feedback)

    def refresh_data(self):
        self._load_status()
        self._load_agents()
        self._load_queue()
        self._load_inbox()

    def _load_status(self):
        self._status_card.clear()
        self._status_card.add_component(Label(text='System Status', role='title', bold=True))
        try:
            s = anvil.server.call('get_system_status')
            for row in [
                f"CPU: {s['cpu_percent']}%",
                f"RAM: {s['memory_percent']}%  ({s['memory_used_gb']:.1f} / {s['memory_total_gb']:.0f} GB)",
                f"Disk: {s['disk_percent']}%  ({s['disk_used_gb']:.0f} / {s['disk_total_gb']:.0f} GB)",
                f"Temp: {s['temperature_c']:.1f}\u00b0C",
                f"Uptime: {s['uptime_human']}",
            ]:
                self._status_card.add_component(Label(text=row, role='body'))
        except Exception as e:
            self._status_card.add_component(Label(text=f'Unavailable: {e}', role='body'))

    def _load_agents(self):
        self._agents_card.clear()
        try:
            agents = anvil.server.call('get_agent_fleet')
            self._agents_card.add_component(
                Label(text=f'Agent Fleet ({len(agents)})', role='title', bold=True)
            )
            for group_status, label in (('active', 'Active'), ('sandbox', 'Sandbox')):
                group = [a for a in agents if a['status'] == group_status]
                if not group:
                    continue
                self._agents_card.add_component(Label(text=label, bold=True, role='body'))
                for a in group:
                    self._agents_card.add_component(
                        Label(text=f"  \u2022 {a['agent_name']}", role='body')
                    )
            other = [a for a in agents if a['status'] not in ('active', 'sandbox')]
            if other:
                self._agents_card.add_component(Label(text='Other', bold=True, role='body'))
                for a in other:
                    self._agents_card.add_component(
                        Label(text=f"  \u2022 {a['agent_name']} [{a['status']}]", role='body')
                    )
        except Exception as e:
            self._agents_card.add_component(Label(text=f'Unavailable: {e}', role='body'))

    def _load_queue(self):
        self._queue_card.clear()
        try:
            tasks = anvil.server.call('get_work_queue')
            pending = sum(1 for t in tasks if t['status'] == 'pending')
            claimed = sum(1 for t in tasks if t['status'] == 'claimed')
            self._queue_card.add_component(
                Label(text=f'Work Queue \u2014 {pending} pending, {claimed} claimed', role='title', bold=True)
            )
            if not tasks:
                self._queue_card.add_component(Label(text='Queue is empty', role='body'))
                return
            for t in tasks[:15]:
                self._queue_card.add_component(
                    Label(text=f"[{t['status']}] {t['task_type']} (p:{t.get('priority', '?')})", role='body')
                )
        except Exception as e:
            self._queue_card.add_component(Label(text=f'Unavailable: {e}', role='body'))

    def _load_inbox(self):
        self._inbox_card.clear()
        try:
            items = anvil.server.call('get_inbox')
            self._inbox_card.add_component(
                Label(text=f'Inbox \u2014 {len(items)} pending', role='title', bold=True)
            )
            if not items:
                self._inbox_card.add_component(Label(text='Inbox is clear.', role='body'))
                return
            for item in items:
                self._render_inbox_item(item)
        except Exception as e:
            self._inbox_card.add_component(Label(text=f'Unavailable: {e}', role='body'))

    def _render_inbox_item(self, item):
        item_id = item['id']

        self._inbox_card.add_component(Label(text='\u2015' * 30, role='body'))
        self._inbox_card.add_component(
            Label(text=item['subject'], bold=True, role='body')
        )
        self._inbox_card.add_component(
            Label(text=f"From: {item['from_agent']}  |  Priority: {item.get('priority', 'normal')}", role='body')
        )

        body_preview = (item.get('body') or '')[:200]
        if len(item.get('body') or '') > 200:
            body_preview += '...'
        self._inbox_card.add_component(Label(text=body_preview, role='body'))

        fb_label = Label(text='', role='body')

        btn_row = FlowPanel(spacing_above='none', spacing_below='none')
        approve_btn = Button(text='Approve', role='filled-button')
        deny_btn = Button(text='Deny', role='outlined-button')

        def on_approve(**event_args):
            try:
                anvil.server.call('approve_inbox_item', item_id)
                fb_label.text = '\u2705 Approved'
                approve_btn.enabled = False
                deny_btn.enabled = False
            except Exception as ex:
                fb_label.text = f'\u274c Error: {ex}'

        def on_deny(**event_args):
            try:
                anvil.server.call('deny_inbox_item', item_id)
                fb_label.text = '\u274c Denied'
                approve_btn.enabled = False
                deny_btn.enabled = False
            except Exception as ex:
                fb_label.text = f'\u274c Error: {ex}'

        approve_btn.set_event_handler('click', on_approve)
        deny_btn.set_event_handler('click', on_deny)
        btn_row.add_component(approve_btn)
        btn_row.add_component(deny_btn)
        self._inbox_card.add_component(btn_row)
        self._inbox_card.add_component(fb_label)

    def _trigger_lean_clicked(self, **event_args):
        self._lean_feedback.text = 'Starting...'
        try:
            result = anvil.server.call('trigger_lean_session')
            self._lean_feedback.text = result.get('message', str(result))
        except Exception as e:
            self._lean_feedback.text = f'\u274c Error: {e}'

    def _write_directive_clicked(self, **event_args):
        text = self._directive_input.text or ''
        if not text.strip():
            self._directive_feedback.text = '\u274c Directive text is empty.'
            return
        self._directive_feedback.text = 'Writing...'
        try:
            result = anvil.server.call('write_directive', text)
            self._directive_feedback.text = f"\u2705 {result.get('message', 'Done.')}"
            self._directive_input.text = ''
        except Exception as e:
            self._directive_feedback.text = f'\u274c Error: {e}'

    def _refresh_clicked(self, **event_args):
        self.refresh_data()
