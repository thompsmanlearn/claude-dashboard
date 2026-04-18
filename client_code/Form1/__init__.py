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
        btn = Button(text='Refresh', role='filled-button')
        btn.set_event_handler('click', self._refresh_clicked)
        header.add_component(btn)
        self.content_panel.add_component(header)

        self._status_card = ColumnPanel(role='outlined-card')
        self.content_panel.add_component(self._status_card)

        self._agents_card = ColumnPanel(role='outlined-card')
        self.content_panel.add_component(self._agents_card)

        self._queue_card = ColumnPanel(role='outlined-card')
        self.content_panel.add_component(self._queue_card)

    def refresh_data(self):
        self._load_status()
        self._load_agents()
        self._load_queue()

    def _load_status(self):
        self._status_card.clear()
        self._status_card.add_component(Label(text='System Status', role='title', bold=True))
        try:
            s = anvil.server.call('get_system_status')
            rows = [
                f"CPU: {s['cpu_percent']}%",
                f"RAM: {s['memory_percent']}%  ({s['memory_used_gb']:.1f} / {s['memory_total_gb']:.0f} GB)",
                f"Disk: {s['disk_percent']}%  ({s['disk_used_gb']:.0f} / {s['disk_total_gb']:.0f} GB)",
                f"Temp: {s['temperature_c']:.1f}\u00b0C",
                f"Uptime: {s['uptime_human']}",
            ]
            for row in rows:
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
            active = [a for a in agents if a['status'] == 'active']
            sandbox = [a for a in agents if a['status'] == 'sandbox']
            other = [a for a in agents if a['status'] not in ('active', 'sandbox')]
            for group, label in ((active, 'Active'), (sandbox, 'Sandbox'), (other, 'Other')):
                if not group:
                    continue
                self._agents_card.add_component(Label(text=label, bold=True, role='body'))
                for a in group:
                    self._agents_card.add_component(
                        Label(text=f"  \u2022 {a['name']}", role='body')
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
                desc = t.get('description') or ''
                summary = f"[{t['status']}] {t['task_type']}"
                if desc:
                    summary += f' \u2014 {desc[:60]}'
                self._queue_card.add_component(Label(text=summary, role='body'))
        except Exception as e:
            self._queue_card.add_component(Label(text=f'Unavailable: {e}', role='body'))

    def _refresh_clicked(self, **event_args):
        self.refresh_data()
