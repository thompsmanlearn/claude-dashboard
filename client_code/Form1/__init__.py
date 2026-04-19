from ._anvil_designer import Form1Template
from anvil import *
import anvil.server


_STATUS_ICONS = {
    'active': '\u2705', 'paused': '\u23f8', 'sandbox': '\U0001f9ea',
    'building': '\U0001f6e0', 'broken': '\u274c', 'retired': '\U0001f4e6',
}
_STATUS_ORDER = ['active', 'paused', 'sandbox', 'building', 'broken', 'retired']
_EXPAND = '\u25bc'   # ▼
_COLLAPSE = '\u25b6'  # ▶


class Form1(Form1Template):
    def __init__(self, **properties):
        self.init_components(**properties)
        self._agent_card_panels = []  # [(name_lower, card_panel)]
        self._search_box = None
        self._lessons_current_filter = 'recent'
        self._lessons_loaded = False
        self._memory_selected_coll = None
        self._memory_offset = 0
        self._mem_page_size = 15
        self._memory_loaded = False
        self._skills_loaded = False
        self._build_layout()
        self.refresh_data()

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _make_section(self, title, default_open=False):
        """Return (outer_panel, body_panel, title_label) with collapsible header."""
        outer = ColumnPanel(role='outlined-card')
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        lbl = Label(text=title, role='title', bold=True, font_size=20)
        btn = Button(text=_EXPAND if default_open else _COLLAPSE, role='text-button')
        hdr.add_component(lbl)
        hdr.add_component(btn)
        outer.add_component(hdr)
        body = ColumnPanel()
        body.visible = default_open
        outer.add_component(body)

        def _toggle(**kw):
            body.visible = not body.visible
            btn.text = _EXPAND if body.visible else _COLLAPSE

        btn.set_event_handler('click', _toggle)
        return outer, body, lbl

    def _build_layout(self):
        top = FlowPanel(spacing_above='none', spacing_below='small')
        top.add_component(Label(text='AADP', role='headline', bold=True))
        ref_btn = Button(text='Refresh', role='filled-button')
        ref_btn.set_event_handler('click', self._refresh_clicked)
        top.add_component(ref_btn)
        self.content_panel.add_component(top)

        # Tab navigation
        tab_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._fleet_tab_btn = Button(text='Fleet', role='filled-button')
        self._sessions_tab_btn = Button(text='Sessions', role='tonal-button')
        self._lessons_tab_btn = Button(text='Lessons', role='tonal-button')
        self._memory_tab_btn = Button(text='Memory', role='tonal-button')
        self._skills_tab_btn = Button(text='Skills', role='tonal-button')
        self._fleet_tab_btn.set_event_handler('click', self._show_fleet_tab)
        self._sessions_tab_btn.set_event_handler('click', self._show_sessions_tab)
        self._lessons_tab_btn.set_event_handler('click', self._show_lessons_tab)
        self._memory_tab_btn.set_event_handler('click', self._show_memory_tab)
        self._skills_tab_btn.set_event_handler('click', self._show_skills_tab)
        tab_row.add_component(self._fleet_tab_btn)
        tab_row.add_component(self._sessions_tab_btn)
        tab_row.add_component(self._lessons_tab_btn)
        tab_row.add_component(self._memory_tab_btn)
        tab_row.add_component(self._skills_tab_btn)
        self.content_panel.add_component(tab_row)

        # Fleet panel (default visible)
        self._fleet_panel = ColumnPanel()
        sec, self._status_body, _ = self._make_section('System Status', default_open=True)
        self._fleet_panel.add_component(sec)
        sec, self._agents_body, self._agents_lbl = self._make_section('Agent Fleet')
        self._fleet_panel.add_component(sec)
        sec, self._queue_body, self._queue_lbl = self._make_section('Work Queue')
        self._fleet_panel.add_component(sec)
        sec, self._inbox_body, self._inbox_lbl = self._make_section('Inbox')
        self._fleet_panel.add_component(sec)
        sec, controls_body, _ = self._make_section('Controls')
        self._build_controls(controls_body)
        self._fleet_panel.add_component(sec)
        self.content_panel.add_component(self._fleet_panel)

        # Sessions panel (hidden by default)
        self._sessions_panel = ColumnPanel()
        self._sessions_panel.visible = False
        self._build_sessions_layout()
        self.content_panel.add_component(self._sessions_panel)

        # Lessons panel (hidden by default)
        self._lessons_panel = ColumnPanel()
        self._lessons_panel.visible = False
        self._build_lessons_layout()
        self.content_panel.add_component(self._lessons_panel)

        # Memory panel (hidden by default)
        self._memory_panel = ColumnPanel()
        self._memory_panel.visible = False
        self._build_memory_layout()
        self.content_panel.add_component(self._memory_panel)

        # Skills panel (hidden by default)
        self._skills_panel = ColumnPanel()
        self._skills_panel.visible = False
        self._build_skills_layout()
        self.content_panel.add_component(self._skills_panel)

    def _build_controls(self, panel):
        panel.add_component(Label(text='Lean Session', bold=True, role='body', font_size=16))

        status_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._lean_status_label = Label(text='\u23f3 Checking\u2026', role='body', font_size=16)
        status_row.add_component(self._lean_status_label)
        refresh_status_btn = Button(text='\u21bb', role='text-button')
        refresh_status_btn.set_event_handler('click', lambda **kw: self._refresh_lean_status())
        status_row.add_component(refresh_status_btn)
        panel.add_component(status_row)

        self._lean_trigger_btn = Button(text='Trigger Lean Session', role='tonal-button')
        self._lean_trigger_btn.set_event_handler('click', self._trigger_lean_clicked)
        panel.add_component(self._lean_trigger_btn)
        self._lean_feedback = Label(text='', role='body', font_size=16)
        panel.add_component(self._lean_feedback)

        panel.add_component(Label(text='\u2015' * 20, role='body', font_size=16))

        panel.add_component(Label(text='Write Directive', bold=True, role='body', font_size=16))
        panel.add_component(Label(text='Overwrites DIRECTIVES.md and pushes to claudis.', role='body', font_size=16))
        self._directive_input = TextArea(
            placeholder='e.g. "Run: B-032" or free text',
            role='outlined',
            height=80,
        )
        panel.add_component(self._directive_input)
        dir_btn = Button(text='Write Directive', role='tonal-button')
        dir_btn.set_event_handler('click', self._write_directive_clicked)
        panel.add_component(dir_btn)
        self._directive_feedback = Label(text='', role='body', font_size=16)
        panel.add_component(self._directive_feedback)

    # ── Data loaders ──────────────────────────────────────────────────────────

    def _refresh_lean_status(self):
        try:
            with anvil.server.no_loading_indicator:
                s = anvil.server.call('get_lean_status')
            if s['running']:
                self._lean_status_label.text = f"\U0001f7e1 Running (PID: {s['pid']})"
                self._lean_trigger_btn.enabled = False
            else:
                self._lean_status_label.text = '\U0001f7e2 Idle'
                self._lean_trigger_btn.enabled = True
        except Exception as e:
            self._lean_status_label.text = f'Status unknown: {e}'
            self._lean_trigger_btn.enabled = True

    def _show_fleet_tab(self, **event_args):
        self._fleet_panel.visible = True
        self._sessions_panel.visible = False
        self._lessons_panel.visible = False
        self._memory_panel.visible = False
        self._skills_panel.visible = False
        self._fleet_tab_btn.role = 'filled-button'
        self._sessions_tab_btn.role = 'tonal-button'
        self._lessons_tab_btn.role = 'tonal-button'
        self._memory_tab_btn.role = 'tonal-button'
        self._skills_tab_btn.role = 'tonal-button'

    def _show_sessions_tab(self, **event_args):
        self._fleet_panel.visible = False
        self._sessions_panel.visible = True
        self._lessons_panel.visible = False
        self._memory_panel.visible = False
        self._skills_panel.visible = False
        self._fleet_tab_btn.role = 'tonal-button'
        self._sessions_tab_btn.role = 'filled-button'
        self._lessons_tab_btn.role = 'tonal-button'
        self._memory_tab_btn.role = 'tonal-button'
        self._skills_tab_btn.role = 'tonal-button'
        self._load_sessions()

    def _show_lessons_tab(self, **event_args):
        self._fleet_panel.visible = False
        self._sessions_panel.visible = False
        self._lessons_panel.visible = True
        self._memory_panel.visible = False
        self._skills_panel.visible = False
        self._fleet_tab_btn.role = 'tonal-button'
        self._sessions_tab_btn.role = 'tonal-button'
        self._lessons_tab_btn.role = 'filled-button'
        self._memory_tab_btn.role = 'tonal-button'
        self._skills_tab_btn.role = 'tonal-button'
        if not self._lessons_loaded:
            self._load_lessons('recent')
            self._lessons_loaded = True

    def _show_memory_tab(self, **event_args):
        self._fleet_panel.visible = False
        self._sessions_panel.visible = False
        self._lessons_panel.visible = False
        self._memory_panel.visible = True
        self._skills_panel.visible = False
        self._fleet_tab_btn.role = 'tonal-button'
        self._sessions_tab_btn.role = 'tonal-button'
        self._lessons_tab_btn.role = 'tonal-button'
        self._memory_tab_btn.role = 'filled-button'
        self._skills_tab_btn.role = 'tonal-button'
        if not self._memory_loaded:
            self._load_memory_collections()
            self._memory_loaded = True

    def _show_skills_tab(self, **event_args):
        self._fleet_panel.visible = False
        self._sessions_panel.visible = False
        self._lessons_panel.visible = False
        self._memory_panel.visible = False
        self._skills_panel.visible = True
        self._fleet_tab_btn.role = 'tonal-button'
        self._sessions_tab_btn.role = 'tonal-button'
        self._lessons_tab_btn.role = 'tonal-button'
        self._memory_tab_btn.role = 'tonal-button'
        self._skills_tab_btn.role = 'filled-button'
        if not self._skills_loaded:
            self._load_skills()
            self._skills_loaded = True

    def refresh_data(self):
        self._load_status()
        self._load_agents()
        self._load_queue()
        self._load_inbox()
        self._refresh_lean_status()
        if not self._fleet_panel.visible:
            self._load_lessons(self._lessons_current_filter)
            self._lessons_loaded = True

    def _load_status(self):
        self._status_body.clear()
        try:
            s = anvil.server.call('get_system_status')
            for row in [
                f"CPU: {s['cpu_percent']}%",
                f"RAM: {s['memory_percent']}%  ({s['memory_used_gb']:.1f} / {s['memory_total_gb']:.0f} GB)",
                f"Disk: {s['disk_percent']}%  ({s['disk_used_gb']:.0f} / {s['disk_total_gb']:.0f} GB)",
                f"Temp: {s['temperature_c']:.1f}\u00b0C",
                f"Uptime: {s['uptime_human']}",
            ]:
                self._status_body.add_component(Label(text=row, role='body', font_size=16))
        except Exception as e:
            self._status_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=16))

    def _load_agents(self):
        self._agent_card_panels = []
        self._agents_body.clear()

        # Search bar
        search_row = FlowPanel(spacing_above='none', spacing_below='small')
        search_row.add_component(Label(text='\U0001f50d ', role='body', font_size=16))
        self._search_box = TextBox(placeholder='Filter by name\u2026', width=220)
        self._search_box.set_event_handler('change', self._filter_agents)
        search_row.add_component(self._search_box)
        self._agents_body.add_component(search_row)

        try:
            agents = anvil.server.call('get_agent_fleet')
            self._agents_lbl.text = f'Agent Fleet ({len(agents)})'

            groups = {}
            for a in agents:
                groups.setdefault(a.get('status', 'retired'), []).append(a)

            for status in _STATUS_ORDER:
                if status not in groups:
                    continue
                group_agents = sorted(groups[status], key=lambda a: a.get('agent_name', ''))
                icon = _STATUS_ICONS.get(status, '\u2753')

                grp_outer = ColumnPanel()
                grp_hdr = FlowPanel(spacing_above='small', spacing_below='none')
                grp_hdr.add_component(
                    Label(text=f'{icon} {status.capitalize()} ({len(group_agents)})', bold=True, role='body', font_size=16)
                )
                grp_btn = Button(text=_EXPAND, role='text-button')
                grp_hdr.add_component(grp_btn)
                grp_outer.add_component(grp_hdr)
                grp_body = ColumnPanel()
                grp_outer.add_component(grp_body)
                self._agents_body.add_component(grp_outer)

                def _make_grp_toggle(body, btn):
                    def _t(**kw):
                        body.visible = not body.visible
                        btn.text = _EXPAND if body.visible else _COLLAPSE
                    return _t

                grp_btn.set_event_handler('click', _make_grp_toggle(grp_body, grp_btn))

                for agent in group_agents:
                    grp_body.add_component(self._build_agent_card(agent))

        except Exception as e:
            self._agents_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=16))

    def _build_agent_card(self, agent):
        agent_name = agent.get('agent_name', '')
        display_name = agent.get('display_name') or agent_name
        description = agent.get('description') or ''
        status = agent.get('status', '?')
        schedule = agent.get('schedule') or '\u2014'
        protected = agent.get('protected', False)
        updated_at = (agent.get('updated_at') or '')[:10]
        icon = _STATUS_ICONS.get(status, '\u2753')
        prot_mark = '  \u26a0\ufe0f' if protected else ''

        card = ColumnPanel()

        # Compact header (always visible)
        compact = FlowPanel(spacing_above='none', spacing_below='none')
        compact.add_component(Label(text=f'{icon} {display_name}{prot_mark}', role='body', font_size=16))
        expand_btn = Button(text='+', role='text-button')
        compact.add_component(expand_btn)
        card.add_component(compact)

        # Detail panel (tap to reveal)
        detail = ColumnPanel()
        detail.visible = False
        card.add_component(detail)

        card.add_component(Label(text='\u2500' * 25, role='body', font_size=16))

        # Populate detail
        if description:
            preview = description[:120] + ('\u2026' if len(description) > 120 else '')
            detail.add_component(Label(text=preview, role='body', font_size=16))
        meta = f'Schedule: {schedule}'
        if updated_at:
            meta += f'  |  Updated: {updated_at}'
        detail.add_component(Label(text=meta, role='body', font_size=16))

        fb_label = Label(text='', role='body', font_size=16)
        action_row = FlowPanel(spacing_above='none', spacing_below='none')

        if status in ('active', 'paused'):
            new_status = 'paused' if status == 'active' else 'active'
            tog_btn = Button(text='Pause' if status == 'active' else 'Activate', role='tonal-button')

            def _make_toggle(a_name, ns, b, lbl):
                def _t(**kw):
                    try:
                        anvil.server.call('set_agent_status', a_name, ns)
                        lbl.text = f'\u2705 Set to {ns}'
                        b.enabled = False
                    except Exception as ex:
                        lbl.text = f'\u274c {ex}'
                return _t

            tog_btn.set_event_handler('click', _make_toggle(agent_name, new_status, tog_btn, fb_label))
            action_row.add_component(tog_btn)

        thumb_up = Button(text='\U0001f44d', role='outlined-button')
        thumb_down = Button(text='\U0001f44e', role='outlined-button')
        comment_box = TextBox(placeholder='Comment', width=160)

        def _make_feedback(a_name, rating, lbl):
            def _f(**kw):
                try:
                    anvil.server.call('submit_agent_feedback', a_name, rating, comment_box.text or None)
                    lbl.text = '\u2705 Thanks!'
                    comment_box.text = ''
                except Exception as ex:
                    lbl.text = f'\u274c {ex}'
            return _f

        thumb_up.set_event_handler('click', _make_feedback(agent_name, 1, fb_label))
        thumb_down.set_event_handler('click', _make_feedback(agent_name, -1, fb_label))
        action_row.add_component(thumb_up)
        action_row.add_component(thumb_down)
        action_row.add_component(comment_box)
        detail.add_component(action_row)
        detail.add_component(fb_label)

        def _make_expand(det, btn):
            def _e(**kw):
                det.visible = not det.visible
                btn.text = '\u2212' if det.visible else '+'
            return _e

        expand_btn.set_event_handler('click', _make_expand(detail, expand_btn))

        self._agent_card_panels.append((agent_name.lower(), card))
        return card

    def _filter_agents(self, **event_args):
        query = (self._search_box.text or '').lower().strip()
        for name_lower, card in self._agent_card_panels:
            card.visible = (not query) or (query in name_lower)

    def _load_queue(self):
        self._queue_body.clear()
        try:
            tasks = anvil.server.call('get_work_queue')
            pending = sum(1 for t in tasks if t['status'] == 'pending')
            claimed = sum(1 for t in tasks if t['status'] == 'claimed')
            self._queue_lbl.text = f'Work Queue \u2014 {pending} pending, {claimed} claimed'
            if not tasks:
                self._queue_body.add_component(Label(text='Queue is empty', role='body', font_size=16))
                return
            for t in tasks[:15]:
                self._queue_body.add_component(
                    Label(text=f"[{t['status']}] {t['task_type']} (p:{t.get('priority', '?')})", role='body', font_size=16)
                )
        except Exception as e:
            self._queue_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=16))

    def _load_inbox(self):
        self._inbox_body.clear()
        try:
            items = anvil.server.call('get_inbox')
            self._inbox_lbl.text = f'Inbox \u2014 {len(items)} pending'
            if not items:
                self._inbox_body.add_component(Label(text='Inbox is clear.', role='body', font_size=16))
                return
            for item in items:
                self._render_inbox_item(item)
        except Exception as e:
            self._inbox_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=16))

    def _render_inbox_item(self, item):
        item_id = item['id']
        self._inbox_body.add_component(Label(text='\u2015' * 20, role='body', font_size=16))
        self._inbox_body.add_component(Label(text=item['subject'], bold=True, role='body', font_size=16))
        self._inbox_body.add_component(
            Label(text=f"From: {item['from_agent']}  |  Priority: {item.get('priority', 'normal')}", role='body', font_size=16)
        )
        body_text = item.get('body') or ''
        preview = body_text[:200] + ('\u2026' if len(body_text) > 200 else '')
        self._inbox_body.add_component(Label(text=preview, role='body', font_size=16))
        fb_label = Label(text='', role='body', font_size=16)
        btn_row = FlowPanel(spacing_above='none', spacing_below='none')
        approve_btn = Button(text='Approve', role='filled-button')
        deny_btn = Button(text='Deny', role='outlined-button')

        def on_approve(**kw):
            try:
                anvil.server.call('approve_inbox_item', item_id)
                fb_label.text = '\u2705 Approved'
                approve_btn.enabled = False
                deny_btn.enabled = False
            except Exception as ex:
                fb_label.text = f'\u274c Error: {ex}'

        def on_deny(**kw):
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
        self._inbox_body.add_component(btn_row)
        self._inbox_body.add_component(fb_label)

    # ── Sessions tab ─────────────────────────────────────────────────────────

    def _build_sessions_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Sessions', role='title', bold=True, font_size=20))
        ref_btn = Button(text='\u21bb', role='text-button')
        ref_btn.set_event_handler('click', lambda **kw: self._load_sessions())
        hdr.add_component(ref_btn)
        self._sessions_panel.add_component(hdr)

        self._sessions_status_card = ColumnPanel(role='outlined-card')
        self._sessions_panel.add_component(self._sessions_status_card)

        self._sessions_panel.add_component(
            Label(text='Recent Session Artifacts', bold=True, role='body', font_size=16)
        )
        self._sessions_artifacts_body = ColumnPanel()
        self._sessions_panel.add_component(self._sessions_artifacts_body)

    def _load_sessions(self):
        # Live status
        self._sessions_status_card.clear()
        try:
            with anvil.server.no_loading_indicator:
                status = anvil.server.call('get_session_status')
            if status is None:
                self._sessions_status_card.add_component(
                    Label(text='\U0001f7e2 No session data yet', role='body', font_size=16)
                )
            else:
                phase = status.get('phase') or 'unknown'
                card_id = status.get('card_id') or '\u2014'
                action = status.get('current_action') or ''
                updated = (status.get('updated_at') or '')[:16].replace('T', ' ')
                _phase_icons = {
                    'started': '\U0001f7e1', 'executing': '\U0001f7e0',
                    'complete': '\U0001f7e2', 'error': '\U0001f534', 'timeout': '\U0001f534',
                }
                icon = _phase_icons.get(phase, '\u26aa')
                is_active = phase in ('started', 'executing')
                status_text = f'{icon} {phase.upper()}'
                if is_active:
                    status_text += f' \u2014 {card_id}'
                self._sessions_status_card.add_component(
                    Label(text=status_text, bold=True, role='body', font_size=18)
                )
                if action:
                    self._sessions_status_card.add_component(
                        Label(text=action, role='body', font_size=16)
                    )
                self._sessions_status_card.add_component(
                    Label(text=f'Updated: {updated}', role='body', font_size=14)
                )
        except Exception as e:
            self._sessions_status_card.add_component(
                Label(text=f'Status unavailable: {e}', role='body', font_size=16)
            )

        # Artifact history
        self._sessions_artifacts_body.clear()
        try:
            with anvil.server.no_loading_indicator:
                artifacts = anvil.server.call('get_session_artifacts', 15)
            if not artifacts:
                self._sessions_artifacts_body.add_component(
                    Label(text='No session artifacts found.', role='body', font_size=16)
                )
                return
            for artifact in artifacts:
                self._sessions_artifacts_body.add_component(
                    self._build_artifact_card(artifact)
                )
        except Exception as e:
            self._sessions_artifacts_body.add_component(
                Label(text=f'Error loading artifacts: {e}', role='body', font_size=16)
            )

    def _build_artifact_card(self, artifact):
        title = artifact.get('title') or artifact.get('filename', '(unknown)')
        date = artifact.get('date') or ''
        content = artifact.get('content') or ''

        card = ColumnPanel(role='outlined-card')

        hdr = FlowPanel(spacing_above='none', spacing_below='none')
        hdr.add_component(Label(text=title[:80], bold=True, role='body', font_size=16))
        expand_btn = Button(text='+', role='text-button')
        hdr.add_component(expand_btn)
        card.add_component(hdr)

        if date:
            card.add_component(Label(text=date, role='body', font_size=14))

        detail = ColumnPanel()
        detail.visible = False
        detail.add_component(Label(text=content, role='body', font_size=14))
        card.add_component(detail)

        def _make_expand(det, btn):
            def _e(**kw):
                det.visible = not det.visible
                btn.text = '\u2212' if det.visible else '+'
            return _e

        expand_btn.set_event_handler('click', _make_expand(detail, expand_btn))
        return card

    # ── Lessons tab ───────────────────────────────────────────────────────────

    def _build_lessons_layout(self):
        view_row = FlowPanel(spacing_above='small', spacing_below='small')
        self._lesson_view_btns = {}
        for label, filt in [
            ('Recent', 'recent'), ('Top Used', 'most_applied'),
            ('Never Applied', 'never_applied'), ('Broken', 'broken'), ('Search', 'search'),
        ]:
            btn = Button(text=label, role='filled-button' if filt == 'recent' else 'tonal-button')
            def _make_view_click(f):
                def _h(**kw):
                    self._set_lesson_view(f)
                return _h
            btn.set_event_handler('click', _make_view_click(filt))
            view_row.add_component(btn)
            self._lesson_view_btns[filt] = btn
        self._lessons_panel.add_component(view_row)

        self._lessons_search_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._lessons_search_box = TextBox(placeholder='Search lessons\u2026', width=200)
        search_go = Button(text='Go', role='tonal-button')
        search_go.set_event_handler('click', lambda **kw: self._load_lessons('search'))
        self._lessons_search_row.add_component(self._lessons_search_box)
        self._lessons_search_row.add_component(search_go)
        self._lessons_search_row.visible = False
        self._lessons_panel.add_component(self._lessons_search_row)

        self._lessons_body = ColumnPanel()
        self._lessons_panel.add_component(self._lessons_body)

    def _set_lesson_view(self, filter):
        self._lessons_current_filter = filter
        for f, btn in self._lesson_view_btns.items():
            btn.role = 'filled-button' if f == filter else 'tonal-button'
        self._lessons_search_row.visible = (filter == 'search')
        if filter != 'search':
            self._load_lessons(filter)

    def _load_lessons(self, filter):
        self._lessons_body.clear()
        self._lessons_body.add_component(Label(text='Loading\u2026', role='body', font_size=16))
        try:
            if filter == 'search':
                query = (self._lessons_search_box.text or '').strip()
                if not query:
                    self._lessons_body.clear()
                    self._lessons_body.add_component(Label(text='Enter a search query above.', role='body', font_size=16))
                    return
                lessons = anvil.server.call('search_lessons', query)
            else:
                lessons = anvil.server.call('get_lessons', filter)
            self._lessons_body.clear()
            if not lessons:
                self._lessons_body.add_component(Label(text='No lessons found.', role='body', font_size=16))
                return
            self._lessons_body.add_component(Label(text=f'{len(lessons)} lesson(s)', role='body', font_size=14))
            for lesson in lessons:
                self._lessons_body.add_component(self._build_lesson_card(lesson, is_search=(filter == 'search')))
        except Exception as e:
            self._lessons_body.clear()
            self._lessons_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    def _build_lesson_card(self, lesson, is_search=False):
        lesson_id = lesson.get('id')
        chromadb_id = lesson.get('chromadb_id')
        title = (lesson.get('title') or '(untitled)')[:100]
        category = lesson.get('category') or '\u2014'
        times_applied = lesson.get('times_applied') or 0
        confidence = lesson.get('confidence')
        conf_str = f'{float(confidence):.2f}' if confidence is not None else '\u2014'
        created = (lesson.get('created_at') or '')[:10]

        card = ColumnPanel(role='outlined-card')
        card.add_component(Label(text=title, bold=True, role='body', font_size=16))
        meta = f'cat: {category}  |  applied: {times_applied}  |  conf: {conf_str}'
        if created:
            meta += f'  |  {created}'
        if is_search and lesson.get('distance') is not None:
            meta += f'  |  dist: {lesson["distance"]:.3f}'
        card.add_component(Label(text=meta, role='body', font_size=14))

        fb_label = Label(text='', role='body', font_size=14)
        action_row = FlowPanel(spacing_above='none', spacing_below='none')

        up_btn = Button(text='\U0001f44d', role='outlined-button')
        down_btn = Button(text='\U0001f44e', role='outlined-button')
        del_btn = Button(text='\U0001f5d1', role='outlined-button')

        def _make_thumb(lid, delta, lbl):
            def _h(**kw):
                try:
                    result = anvil.server.call('update_lesson', lid, delta)
                    sign = '+' if delta > 0 else ''
                    lbl.text = f'\u2705 conf {sign}{delta:.1f} \u2192 {result["confidence"]:.2f}'
                except Exception as ex:
                    lbl.text = f'\u274c {ex}'
            return _h

        def _make_delete(lid, cid, c, lbl):
            def _h(**kw):
                try:
                    anvil.server.call('delete_lesson', lid, cid)
                    c.visible = False
                except Exception as ex:
                    lbl.text = f'\u274c {ex}'
            return _h

        up_btn.set_event_handler('click', _make_thumb(lesson_id, 0.1, fb_label))
        down_btn.set_event_handler('click', _make_thumb(lesson_id, -0.1, fb_label))
        del_btn.set_event_handler('click', _make_delete(lesson_id, chromadb_id, card, fb_label))

        action_row.add_component(up_btn)
        action_row.add_component(down_btn)
        action_row.add_component(del_btn)
        card.add_component(action_row)
        card.add_component(fb_label)
        return card

    # ── Memory tab ────────────────────────────────────────────────────────────

    def _build_memory_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Memory', role='title', bold=True, font_size=20))
        ref_btn = Button(text='\u21bb', role='text-button')
        ref_btn.set_event_handler('click', lambda **kw: self._refresh_memory())
        hdr.add_component(ref_btn)
        self._memory_panel.add_component(hdr)

        # ChromaDB section
        self._memory_panel.add_component(Label(text='ChromaDB', bold=True, role='body', font_size=18))
        self._mem_colls_body = ColumnPanel()
        self._memory_panel.add_component(self._mem_colls_body)

        # Search row (hidden until a collection is selected)
        self._mem_search_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._mem_search_box = TextBox(placeholder='Semantic search\u2026', width=200)
        go_btn = Button(text='Search', role='tonal-button')
        go_btn.set_event_handler('click', lambda **kw: self._do_collection_search())
        self._mem_search_row.add_component(self._mem_search_box)
        self._mem_search_row.add_component(go_btn)
        self._mem_search_row.visible = False
        self._memory_panel.add_component(self._mem_search_row)

        # Document list area
        self._mem_docs_body = ColumnPanel()
        self._memory_panel.add_component(self._mem_docs_body)

        # Supabase section
        self._memory_panel.add_component(Label(text='\u2015' * 20, role='body', font_size=16))
        self._memory_panel.add_component(Label(text='Supabase', bold=True, role='body', font_size=18))

        sb_row = FlowPanel(spacing_above='none', spacing_below='small')
        rp_btn = Button(text='Research Papers', role='tonal-button')
        el_btn = Button(text='Error Log', role='tonal-button')
        rp_btn.set_event_handler('click', lambda **kw: self._load_supabase_table('research_papers'))
        el_btn.set_event_handler('click', lambda **kw: self._load_supabase_table('error_logs'))
        sb_row.add_component(rp_btn)
        sb_row.add_component(el_btn)
        self._memory_panel.add_component(sb_row)

        self._mem_supabase_body = ColumnPanel()
        self._memory_panel.add_component(self._mem_supabase_body)

    def _refresh_memory(self):
        self._memory_loaded = False
        self._memory_selected_coll = None
        self._memory_offset = 0
        self._mem_search_row.visible = False
        self._mem_docs_body.clear()
        self._mem_supabase_body.clear()
        self._load_memory_collections()
        self._memory_loaded = True

    def _load_memory_collections(self):
        self._mem_colls_body.clear()
        self._mem_colls_body.add_component(Label(text='Loading collections\u2026', role='body', font_size=16))
        try:
            with anvil.server.no_loading_indicator:
                stats = anvil.server.call('get_collection_stats')
            self._mem_colls_body.clear()
            row = FlowPanel(spacing_above='none', spacing_below='small')
            for coll in stats:
                btn = Button(text=f"{coll['name']} ({coll['count']})", role='tonal-button')
                def _make_select(name):
                    def _h(**kw):
                        self._memory_selected_coll = name
                        self._memory_offset = 0
                        self._mem_search_box.text = ''
                        self._mem_search_row.visible = True
                        self._load_collection_docs(0)
                    return _h
                btn.set_event_handler('click', _make_select(coll['name']))
                row.add_component(btn)
            self._mem_colls_body.add_component(row)
        except Exception as e:
            self._mem_colls_body.clear()
            self._mem_colls_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    def _load_collection_docs(self, offset):
        self._mem_docs_body.clear()
        self._mem_docs_body.add_component(
            Label(text=f'Loading {self._memory_selected_coll}\u2026', role='body', font_size=16)
        )
        try:
            with anvil.server.no_loading_indicator:
                result = anvil.server.call('browse_collection', self._memory_selected_coll, self._mem_page_size, offset)
            self._mem_docs_body.clear()
            total = result['total']
            docs = result['docs']
            self._memory_offset = offset

            info = Label(
                text=f'{self._memory_selected_coll} — {total} docs (showing {offset+1}–{min(offset+len(docs), total)})',
                role='body', font_size=14,
            )
            self._mem_docs_body.add_component(info)

            for doc in docs:
                self._mem_docs_body.add_component(self._build_doc_card(doc, self._memory_selected_coll))

            # Pagination
            nav = FlowPanel(spacing_above='small', spacing_below='none')
            if offset > 0:
                prev_btn = Button(text='\u25c0 Prev', role='tonal-button')
                prev_btn.set_event_handler('click', lambda **kw: self._load_collection_docs(self._memory_offset - self._mem_page_size))
                nav.add_component(prev_btn)
            if offset + self._mem_page_size < total:
                next_btn = Button(text='Next \u25b6', role='tonal-button')
                next_btn.set_event_handler('click', lambda **kw: self._load_collection_docs(self._memory_offset + self._mem_page_size))
                nav.add_component(next_btn)
            if nav.get_components():
                self._mem_docs_body.add_component(nav)
        except Exception as e:
            self._mem_docs_body.clear()
            self._mem_docs_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    def _do_collection_search(self):
        if not self._memory_selected_coll:
            return
        query = (self._mem_search_box.text or '').strip()
        if not query:
            self._load_collection_docs(0)
            return
        self._mem_docs_body.clear()
        self._mem_docs_body.add_component(Label(text='Searching\u2026', role='body', font_size=16))
        try:
            with anvil.server.no_loading_indicator:
                results = anvil.server.call('search_collection', self._memory_selected_coll, query)
            self._mem_docs_body.clear()
            if not results:
                self._mem_docs_body.add_component(Label(text='No results.', role='body', font_size=16))
                return
            self._mem_docs_body.add_component(
                Label(text=f'{len(results)} result(s) for "{query}"', role='body', font_size=14)
            )
            for doc in results:
                card = self._build_doc_card(doc, self._memory_selected_coll)
                if doc.get('distance') is not None:
                    card.add_component(
                        Label(text=f'dist: {doc["distance"]:.3f}', role='body', font_size=12)
                    )
                self._mem_docs_body.add_component(card)
        except Exception as e:
            self._mem_docs_body.clear()
            self._mem_docs_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    def _build_doc_card(self, doc, collection):
        doc_id = doc['id']
        text = (doc.get('document') or '(empty)')
        meta = doc.get('metadata') or {}
        title = meta.get('title') or meta.get('lesson_title') or doc_id[:24]

        card = ColumnPanel(role='outlined-card')
        card.add_component(Label(text=str(title)[:80], bold=True, role='body', font_size=14))

        expand_btn = Button(text='+', role='text-button')
        hdr = FlowPanel(spacing_above='none', spacing_below='none')
        hdr.add_component(Label(text=doc_id[:24] + '\u2026', role='body', font_size=12))
        hdr.add_component(expand_btn)
        card.add_component(hdr)

        detail = ColumnPanel()
        detail.visible = False
        detail.add_component(Label(text=text, role='body', font_size=13))
        card.add_component(detail)

        fb_lbl = Label(text='', role='body', font_size=13)
        del_btn = Button(text='\U0001f5d1 Delete', role='outlined-button')

        def _make_delete(cid, c, lbl, coll_name):
            def _h(**kw):
                try:
                    anvil.server.call('delete_document', coll_name, cid)
                    c.visible = False
                except Exception as ex:
                    lbl.text = f'\u274c {ex}'
            return _h

        del_btn.set_event_handler('click', _make_delete(doc_id, card, fb_lbl, collection))

        def _make_expand(det, btn):
            def _e(**kw):
                det.visible = not det.visible
                btn.text = '\u2212' if det.visible else '+'
            return _e

        expand_btn.set_event_handler('click', _make_expand(detail, expand_btn))
        card.add_component(del_btn)
        card.add_component(fb_lbl)
        return card

    def _load_supabase_table(self, table):
        self._mem_supabase_body.clear()
        self._mem_supabase_body.add_component(Label(text=f'Loading {table}\u2026', role='body', font_size=16))
        try:
            with anvil.server.no_loading_indicator:
                rows = anvil.server.call('get_table_rows', table)
            self._mem_supabase_body.clear()
            self._mem_supabase_body.add_component(
                Label(text=f'{table} — {len(rows)} row(s)', bold=True, role='body', font_size=14)
            )
            if not rows:
                self._mem_supabase_body.add_component(Label(text='No rows.', role='body', font_size=16))
                return
            for row in rows:
                card = ColumnPanel(role='outlined-card')
                if table == 'research_papers':
                    title = (row.get('title') or '(no title)')[:80]
                    score = row.get('relevance_score')
                    status = row.get('status') or '\u2014'
                    date = (row.get('discovered_at') or '')[:10]
                    card.add_component(Label(text=title, bold=True, role='body', font_size=14))
                    meta = f'score: {score}  |  status: {status}  |  {date}'
                    card.add_component(Label(text=meta, role='body', font_size=12))
                elif table == 'error_logs':
                    wf = row.get('workflow_name') or '(unknown)'
                    msg = (row.get('error_message') or '')[:120]
                    date = (row.get('created_at') or '')[:16].replace('T', ' ')
                    card.add_component(Label(text=wf, bold=True, role='body', font_size=14))
                    card.add_component(Label(text=msg, role='body', font_size=13))
                    card.add_component(Label(text=date, role='body', font_size=12))
                self._mem_supabase_body.add_component(card)
        except Exception as e:
            self._mem_supabase_body.clear()
            self._mem_supabase_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    # ── Skills tab ───────────────────────────────────────────────────────────

    def _build_skills_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Skills', role='title', bold=True, font_size=20))
        ref_btn = Button(text='\u21bb', role='text-button')
        ref_btn.set_event_handler('click', lambda **kw: self._reload_skills())
        hdr.add_component(ref_btn)
        self._skills_panel.add_component(hdr)

        self._skills_body = ColumnPanel()
        self._skills_panel.add_component(self._skills_body)

        self._skill_detail_panel = ColumnPanel()
        self._skills_panel.add_component(self._skill_detail_panel)

    def _reload_skills(self):
        self._skills_loaded = False
        self._skill_detail_panel.clear()
        self._load_skills()
        self._skills_loaded = True

    def _load_skills(self):
        self._skills_body.clear()
        self._skills_body.add_component(Label(text='Loading\u2026', role='body', font_size=16))
        try:
            with anvil.server.no_loading_indicator:
                skills = anvil.server.call('get_skills')
            self._skills_body.clear()
            self._skills_body.add_component(
                Label(text=f'{len(skills)} skill(s)', role='body', font_size=14)
            )
            for skill in skills:
                self._skills_body.add_component(self._build_skill_card(skill))
        except Exception as e:
            self._skills_body.clear()
            self._skills_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    def _build_skill_card(self, skill):
        name = skill.get('name', '')
        description = skill.get('description') or '\u2014'
        keywords = skill.get('trigger_keywords') or []
        times_loaded = skill.get('times_loaded') or 0
        last_loaded = (skill.get('last_loaded') or '')[:10] or 'never'

        card = ColumnPanel(role='outlined-card')
        card.add_component(Label(text=name, bold=True, role='body', font_size=16))
        meta = f'loaded: {times_loaded}  |  last: {last_loaded}'
        card.add_component(Label(text=meta, role='body', font_size=13))

        desc_preview = description[:100] + ('\u2026' if len(description) > 100 else '')
        card.add_component(Label(text=desc_preview, role='body', font_size=14))

        if keywords:
            card.add_component(Label(text='Keywords: ' + ', '.join(keywords[:6]), role='body', font_size=12))

        view_btn = Button(text='View Content', role='tonal-button')

        def _make_view(n):
            def _h(**kw):
                self._load_skill_content(n)
            return _h

        view_btn.set_event_handler('click', _make_view(name))
        card.add_component(view_btn)
        return card

    def _load_skill_content(self, name):
        self._skill_detail_panel.clear()
        self._skill_detail_panel.add_component(
            Label(text=f'Loading {name}\u2026', role='body', font_size=14)
        )
        try:
            with anvil.server.no_loading_indicator:
                result = anvil.server.call('get_skill', name)
            self._skill_detail_panel.clear()
            hdr = FlowPanel(spacing_above='small', spacing_below='none')
            hdr.add_component(Label(text=result['name'], bold=True, role='body', font_size=16))
            close_btn = Button(text='\u00d7', role='text-button')
            close_btn.set_event_handler('click', lambda **kw: self._skill_detail_panel.clear())
            hdr.add_component(close_btn)
            self._skill_detail_panel.add_component(hdr)
            self._skill_detail_panel.add_component(
                Label(text=result['file_path'], role='body', font_size=12)
            )
            content_card = ColumnPanel(role='outlined-card')
            content_card.add_component(Label(text=result['content'], role='body', font_size=13))
            self._skill_detail_panel.add_component(content_card)
        except Exception as e:
            self._skill_detail_panel.clear()
            self._skill_detail_panel.add_component(
                Label(text=f'Error: {e}', role='body', font_size=14)
            )

    # ── Event handlers ────────────────────────────────────────────────────────

    def _trigger_lean_clicked(self, **event_args):
        self._lean_feedback.text = 'Starting...'
        self._lean_trigger_btn.enabled = False
        try:
            result = anvil.server.call('trigger_lean_session')
            self._lean_feedback.text = result.get('message', str(result))
        except Exception as e:
            self._lean_feedback.text = f'\u274c Error: {e}'
        self._refresh_lean_status()

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
