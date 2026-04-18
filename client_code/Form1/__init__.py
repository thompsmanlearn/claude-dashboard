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
            STATUS_ORDER = ['active', 'paused', 'sandbox', 'building', 'broken', 'retired']
            def sort_key(a):
                s = a.get('status', 'retired')
                return (STATUS_ORDER.index(s) if s in STATUS_ORDER else len(STATUS_ORDER), a.get('agent_name', ''))
            for agent in sorted(agents, key=sort_key):
                self._render_agent_row(agent)
        except Exception as e:
            self._agents_card.add_component(Label(text=f'Unavailable: {e}', role='body'))

    def _render_agent_row(self, agent):
        agent_name = agent.get('agent_name', '')
        display_name = agent.get('display_name') or agent_name
        description = agent.get('description') or ''
        status = agent.get('status', '?')
        schedule = agent.get('schedule') or '—'
        updated_at = agent.get('updated_at') or ''
        if updated_at:
            updated_at = updated_at[:10]

        STATUS_ICONS = {
            'active': '\u2705', 'paused': '\u23f8', 'sandbox': '\U0001f9ea',
            'building': '\U0001f6e0', 'broken': '\u274c', 'retired': '\U0001f4e6',
        }
        icon = STATUS_ICONS.get(status, '\u2753')

        self._agents_card.add_component(Label(text='\u2015' * 30, role='body'))

        name_row = FlowPanel(spacing_above='none', spacing_below='none')
        name_row.add_component(Label(text=f'{icon} {display_name}', bold=True, role='body'))
        name_row.add_component(Label(text=f'  [{status}]', role='body'))
        self._agents_card.add_component(name_row)

        if description:
            desc_preview = description[:120] + ('...' if len(description) > 120 else '')
            self._agents_card.add_component(Label(text=desc_preview, role='body'))

        meta = f'Schedule: {schedule}'
        if updated_at:
            meta += f'  |  Updated: {updated_at}'
        self._agents_card.add_component(Label(text=meta, role='body'))

        action_row = FlowPanel(spacing_above='none', spacing_below='none')
        fb_label = Label(text='', role='body')

        # Activate/pause toggle — only for active or paused agents
        if status in ('active', 'paused'):
            new_status = 'paused' if status == 'active' else 'active'
            toggle_text = 'Pause' if status == 'active' else 'Activate'
            toggle_btn = Button(text=toggle_text, role='tonal-button')

            def make_toggle(a_name, ns, btn, lbl):
                def on_toggle(**event_args):
                    try:
                        anvil.server.call('set_agent_status', a_name, ns)
                        lbl.text = f'\u2705 Set to {ns}'
                        btn.enabled = False
                    except Exception as ex:
                        lbl.text = f'\u274c {ex}'
                return on_toggle

            toggle_btn.set_event_handler('click', make_toggle(agent_name, new_status, toggle_btn, fb_label))
            action_row.add_component(toggle_btn)

        # Feedback buttons
        thumb_up = Button(text='\U0001f44d', role='outlined-button')
        thumb_down = Button(text='\U0001f44e', role='outlined-button')
        comment_box = TextBox(placeholder='Comment (optional)', width=180)

        def make_feedback(a_name, rating, lbl):
            def on_feedback(**event_args):
                try:
                    comment = comment_box.text or None
                    anvil.server.call('submit_agent_feedback', a_name, rating, comment)
                    lbl.text = '\u2705 Thanks!'
                    comment_box.text = ''
                except Exception as ex:
                    lbl.text = f'\u274c {ex}'
            return on_feedback

        thumb_up.set_event_handler('click', make_feedback(agent_name, 1, fb_label))
        thumb_down.set_event_handler('click', make_feedback(agent_name, -1, fb_label))
        action_row.add_component(thumb_up)
        action_row.add_component(thumb_down)
        action_row.add_component(comment_box)

        self._agents_card.add_component(action_row)
        self._agents_card.add_component(fb_label)

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
