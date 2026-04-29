from ._anvil_designer import Form1Template
from anvil import *
import anvil.server
import anvil.js


_STATUS_ICONS = {
    'active': '\u2705', 'paused': '\u23f8', 'sandbox': '\U0001f9ea',
    'building': '\U0001f6e0', 'broken': '\u274c', 'retired': '\U0001f4e6',
}
_STATUS_ORDER = ['active', 'paused', 'sandbox', 'building', 'broken', 'retired']
_EXPAND = '\u25bc'   # ▼
_COLLAPSE = '\u25b6'  # ▶


_ENTRY_ICONS = {
    'gather': '\U0001f50d',
    'annotation': '\u270f\ufe0f',
    'analysis': '\U0001f52c',
    'conclusion': '\u2705',
    'state_change': '\U0001f501',
}
_STATE_BADGE = {
    'active': '\U0001f7e2 active',
    'dormant': '\u26aa dormant',
    'closed': '\u26ab closed',
}


def _rel_time(iso_str):
    if not iso_str:
        return ''
    try:
        from datetime import datetime, timezone
        ts = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        secs = int((now - ts).total_seconds())
        if secs < 60:
            return 'just now'
        if secs < 3600:
            return f'{secs // 60}m ago'
        if secs < 86400:
            return f'{secs // 3600}h ago'
        days = secs // 86400
        if days == 1:
            return 'yesterday'
        if days < 30:
            return f'{days} days ago'
        return f'{ts.strftime("%B")} {ts.day}'
    except Exception:
        return iso_str[:10]

class Form1(Form1Template):
    def __init__(self, **properties):
        # Hash routing — must run before init_components
        try:
            raw_hash = str(anvil.js.window.location.hash)
            if 'EmbedControl' in raw_hash:
                open_form('EmbedControl')
                return
        except Exception:
            pass

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
        self._artifacts_loaded = False
        self._artifacts_agent_filter = None
        self._artifacts_type_filter = None
        self._research_loaded = False
        self._research_articles = []
        self._threads_loaded = False
        self._threads_state_filter = 'active'
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
        self._research_tab_btn = Button(text='Research', role='tonal-button')
        self._threads_tab_btn = Button(text='Threads', role='tonal-button')
        self._skills_tab_btn = Button(text='Skills', role='tonal-button')
        self._artifacts_tab_btn = Button(text='Artifacts', role='tonal-button')
        self._fleet_tab_btn.set_event_handler('click', self._show_fleet_tab)
        self._sessions_tab_btn.set_event_handler('click', self._show_sessions_tab)
        self._lessons_tab_btn.set_event_handler('click', self._show_lessons_tab)
        self._memory_tab_btn.set_event_handler('click', self._show_memory_tab)
        self._research_tab_btn.set_event_handler('click', self._show_research_tab)
        self._threads_tab_btn.set_event_handler('click', self._show_threads_tab)
        self._skills_tab_btn.set_event_handler('click', self._show_skills_tab)
        self._artifacts_tab_btn.set_event_handler('click', self._show_artifacts_tab)
        tab_row.add_component(self._fleet_tab_btn)
        tab_row.add_component(self._sessions_tab_btn)
        tab_row.add_component(self._lessons_tab_btn)
        tab_row.add_component(self._memory_tab_btn)
        tab_row.add_component(self._research_tab_btn)
        tab_row.add_component(self._threads_tab_btn)
        tab_row.add_component(self._skills_tab_btn)
        tab_row.add_component(self._artifacts_tab_btn)
        self.content_panel.add_component(tab_row)

        # Fleet panel (default visible)
        self._fleet_panel = ColumnPanel()
        _fleet_hdr = FlowPanel(spacing_above='small', spacing_below='small')
        _fleet_hdr.add_component(Label(text='Fleet', role='title', bold=True, font_size=20))
        self._fleet_export_btn = Button(text='⬇ Export', role='tonal-button')
        self._fleet_export_btn.set_event_handler('click', self._fleet_export_clicked)
        _fleet_hdr.add_component(self._fleet_export_btn)
        self._fleet_panel.add_component(_fleet_hdr)
        self._fleet_export_fb = Label(text='', role='body', font_size=14)
        self._fleet_panel.add_component(self._fleet_export_fb)
        self._fleet_export_panel = ColumnPanel()
        self._fleet_export_panel.visible = False
        self._fleet_panel.add_component(self._fleet_export_panel)
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

        # Artifacts panel (hidden by default)
        self._artifacts_panel = ColumnPanel()
        self._artifacts_panel.visible = False
        self._build_artifacts_layout()
        self.content_panel.add_component(self._artifacts_panel)

        # Research panel (hidden by default)
        self._research_panel = ColumnPanel()
        self._research_panel.visible = False
        self._build_research_layout()
        self.content_panel.add_component(self._research_panel)

        # Threads panel (hidden by default)
        self._threads_panel = ColumnPanel()
        self._threads_panel.visible = False
        self._build_threads_layout()
        self.content_panel.add_component(self._threads_panel)

    def _build_controls(self, panel):
        panel.add_component(Label(text='Lean Session', bold=True, role='body', font_size=16))

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

        panel.add_component(Label(text='\u2015' * 20, role='body', font_size=16))

        panel.add_component(Label(text='Autonomous Mode', bold=True, role='body', font_size=16))
        panel.add_component(Label(text='Toggles growth scheduler + lean auto-cycle.', role='body', font_size=16))

        auto_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._auto_btn = Button(text='\u23f3 Checking\u2026', role='tonal-button')
        self._auto_btn.set_event_handler('click', self._auto_mode_clicked)
        auto_row.add_component(self._auto_btn)
        refresh_auto_btn = Button(text='\u21bb', role='text-button')
        refresh_auto_btn.set_event_handler('click', lambda **kw: self._refresh_auto_status())
        auto_row.add_component(refresh_auto_btn)
        panel.add_component(auto_row)

        self._auto_feedback = Label(text='', role='body', font_size=16)
        panel.add_component(self._auto_feedback)

    # ── Data loaders ──────────────────────────────────────────────────────────

    def _refresh_lean_status(self):
        try:
            with anvil.server.no_loading_indicator:
                s = anvil.server.call('get_lean_status')
            self._lean_trigger_btn.enabled = not s['running']
        except Exception:
            self._lean_trigger_btn.enabled = True

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
            if errors:
                self._auto_feedback.text = 'Partial: ' + '; '.join(errors)
            else:
                self._auto_feedback.text = 'Enabled' if new_state else 'Disabled'
        except Exception as e:
            self._auto_feedback.text = f'\u274c Error: {e}'

    def _set_tab(self, active):
        panels = {
            'fleet': self._fleet_panel,
            'sessions': self._sessions_panel,
            'lessons': self._lessons_panel,
            'memory': self._memory_panel,
            'research': self._research_panel,
            'threads': self._threads_panel,
            'skills': self._skills_panel,
            'artifacts': self._artifacts_panel,
        }
        btns = {
            'fleet': self._fleet_tab_btn,
            'sessions': self._sessions_tab_btn,
            'lessons': self._lessons_tab_btn,
            'memory': self._memory_tab_btn,
            'research': self._research_tab_btn,
            'threads': self._threads_tab_btn,
            'skills': self._skills_tab_btn,
            'artifacts': self._artifacts_tab_btn,
        }
        for name, panel in panels.items():
            panel.visible = (name == active)
        for name, btn in btns.items():
            btn.role = 'filled-button' if name == active else 'tonal-button'

    def _show_fleet_tab(self, **event_args):
        self._set_tab('fleet')

    def _show_sessions_tab(self, **event_args):
        self._set_tab('sessions')
        self._load_sessions()

    def _show_lessons_tab(self, **event_args):
        self._set_tab('lessons')
        if not self._lessons_loaded:
            self._load_lessons('recent')
            self._lessons_loaded = True

    def _show_memory_tab(self, **event_args):
        self._set_tab('memory')
        if not self._memory_loaded:
            self._load_memory_collections()
            self._memory_loaded = True

    def _show_skills_tab(self, **event_args):
        self._set_tab('skills')
        if not self._skills_loaded:
            self._load_skills()
            self._skills_loaded = True

    def _show_artifacts_tab(self, **event_args):
        self._set_tab('artifacts')
        if not self._artifacts_loaded:
            self._load_artifacts()
            self._artifacts_loaded = True

    def _show_research_tab(self, **event_args):
        self._set_tab('research')
        if not self._research_loaded:
            self._load_research_tab()
            self._research_loaded = True

    def _show_threads_tab(self, **event_args):
        self._set_tab('threads')
        if not self._threads_loaded:
            self._load_threads()
            self._threads_loaded = True

    # ── Threads tab ───────────────────────────────────────────────────────────

    def _build_threads_layout(self):
        # Create-thread affordance
        create_row = FlowPanel(spacing_above='small', spacing_below='none')
        self._threads_title_input = TextBox(placeholder='Title', width=200)
        self._threads_question_input = TextBox(placeholder='Question', width=300)
        create_btn = Button(text='Create thread', role='tonal-button')
        self._threads_create_fb = Label(text='', role='body', font_size=12)
        create_row.add_component(self._threads_title_input)
        create_row.add_component(self._threads_question_input)
        create_row.add_component(create_btn)
        create_row.add_component(self._threads_create_fb)
        create_btn.set_event_handler('click', self._create_thread_clicked)
        self._threads_panel.add_component(create_row)

        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Threads', role='title', bold=True, font_size=20))
        self._threads_state_dd = DropDown(
            items=['active', 'dormant', 'closed', 'all'],
            selected_value='active',
        )
        self._threads_state_dd.set_event_handler('change', self._threads_filter_changed)
        hdr.add_component(self._threads_state_dd)
        ref_btn = Button(text='\u21bb', role='text-button')
        ref_btn.set_event_handler('click', lambda **kw: self._reload_threads())
        hdr.add_component(ref_btn)
        self._threads_panel.add_component(hdr)

        self._threads_counter_lbl = Label(text='', role='body', font_size=14)
        self._threads_panel.add_component(self._threads_counter_lbl)

        self._threads_body = ColumnPanel()
        self._threads_panel.add_component(self._threads_body)

    def _create_thread_clicked(self, **event_args):
        title = (self._threads_title_input.text or '').strip()
        question = (self._threads_question_input.text or '').strip()
        if not title or not question:
            self._threads_create_fb.text = '⚠️ Title and question required'
            return
        self._threads_create_fb.text = 'Creating…'
        try:
            with anvil.server.no_loading_indicator:
                anvil.server.call('create_thread', title, question)
            self._threads_title_input.text = ''
            self._threads_question_input.text = ''
            self._threads_create_fb.text = '✅ Thread created'
            self._threads_state_filter = 'active'
            self._threads_state_dd.selected_value = 'active'
            self._load_threads()
        except Exception as e:
            self._threads_create_fb.text = f'❌ {e}'

    def _threads_filter_changed(self, **event_args):
        self._threads_state_filter = self._threads_state_dd.selected_value
        self._load_threads()

    def _reload_threads(self):
        self._threads_loaded = False
        self._load_threads()
        self._threads_loaded = True

    def _load_threads(self):
        self._threads_body.clear()
        self._threads_body.add_component(Label(text='Loading\u2026', role='body', font_size=16))
        state = self._threads_state_filter
        try:
            with anvil.server.no_loading_indicator:
                threads = anvil.server.call('get_threads', state=None if state == 'all' else state)
            self._threads_body.clear()
            n = len(threads)
            label_state = state if state != 'all' else ''
            self._threads_counter_lbl.text = (
                f'{n} {label_state} thread(s)' if label_state else f'{n} thread(s)'
            )
            if not threads:
                self._threads_body.add_component(
                    Label(text=f'No {state} threads.', role='body', font_size=16)
                )
                return
            for t in threads:
                self._threads_body.add_component(self._build_thread_card(t))
        except Exception as e:
            self._threads_body.clear()
            self._threads_counter_lbl.text = ''
            self._threads_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    def _build_thread_card(self, t):
        thread_id = t.get('id', '')
        t_state = [dict(t)]
        title = t.get('title') or '(untitled)'
        question = t.get('question') or ''

        card = ColumnPanel(role='outlined-card')

        # Collapsed header (always visible)
        hdr_panel = ColumnPanel()
        title_row = FlowPanel(spacing_above='none', spacing_below='none')
        toggle_btn = Button(text=_COLLAPSE, role='text-button')
        title_row.add_component(toggle_btn)
        title_row.add_component(Label(text=title, bold=True, role='body', font_size=16))
        badge_lbl = Label(text=f'  {_STATE_BADGE.get(t_state[0].get("state","active"), t_state[0].get("state","active"))}', role='body', font_size=13)
        title_row.add_component(badge_lbl)
        hdr_panel.add_component(title_row)

        if question:
            q_preview = question[:80] + ('\u2026' if len(question) > 80 else '')
            hdr_panel.add_component(Label(text=q_preview, role='body', font_size=13))

        last_activity = t.get('last_activity_at') or t.get('updated_at') or ''
        agent_text = t.get('bound_agent') or 'no agent wired'
        meta_lbl = Label(text=f'{agent_text}  \u00b7  last active {_rel_time(last_activity)}', role='body', font_size=12)
        hdr_panel.add_component(meta_lbl)
        card.add_component(hdr_panel)

        # Content panel: entries + actions (hidden until expanded)
        content_panel = ColumnPanel()
        content_panel.visible = False

        entries_panel = ColumnPanel()
        content_panel.add_component(entries_panel)

        actions_panel = ColumnPanel()
        content_panel.add_component(actions_panel)

        card.add_component(content_panel)

        loaded = [False]

        def _toggle(**kw):
            if not loaded[0]:
                self._load_thread_entries(thread_id, entries_panel)
                self._build_thread_actions(thread_id, t_state, entries_panel, actions_panel, badge_lbl, meta_lbl)
                loaded[0] = True
                content_panel.visible = True
            else:
                content_panel.visible = not content_panel.visible
            toggle_btn.text = _EXPAND if content_panel.visible else _COLLAPSE

        toggle_btn.set_event_handler('click', _toggle)
        return card

    def _load_thread_entries(self, thread_id, entries_panel):
        entries_panel.clear()
        entries_panel.add_component(Label(text='Loading entries\u2026', role='body', font_size=13))
        try:
            with anvil.server.no_loading_indicator:
                entries = anvil.server.call('get_thread_entries', thread_id)
            entries_panel.clear()
            if not entries:
                entries_panel.add_component(
                    Label(text='No entries yet.', role='body', font_size=13)
                )
                return
            for e in entries:
                entry_type = e.get('entry_type') or 'annotation'
                icon = _ENTRY_ICONS.get(entry_type, '\u2022')
                content = e.get('content') or ''
                if len(content) > 600:
                    content = content[:600] + ' [truncated]'
                source = e.get('source') or ''
                created = e.get('created_at') or ''

                row = FlowPanel(spacing_above='none', spacing_below='none')
                row.add_component(Label(text=icon, role='body', font_size=13))
                row.add_component(Label(text=f'  {entry_type}', role='body', font_size=12))
                row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                entries_panel.add_component(row)
                entries_panel.add_component(Label(text=content, role='body', font_size=13))
                if source:
                    entries_panel.add_component(Label(text=source, role='body', font_size=12))
                entries_panel.add_component(Label(text='\u2015' * 15, role='body', font_size=11))
        except Exception as e:
            entries_panel.clear()
            entries_panel.add_component(Label(text=f'Error: {e}', role='body', font_size=13))

    def _build_thread_actions(self, thread_id, t_state, entries_panel, actions_panel, badge_lbl, meta_lbl):
        actions_panel.clear()
        try:
            with anvil.server.no_loading_indicator:
                fleet = anvil.server.call('get_agent_fleet')
        except Exception as e:
            actions_panel.add_component(Label(text=f'⚠️ Could not load agents: {e}', role='body', font_size=12))
            fleet = []

        wireable = [a for a in fleet if a.get('status') == 'active' and a.get('webhook_url')]
        bound_agent = t_state[0].get('bound_agent')
        bound_has_webhook = any(
            a['agent_name'] == bound_agent and a.get('webhook_url') for a in fleet
        ) if bound_agent else False

        actions_panel.add_component(Label(text='─' * 20, role='body', font_size=11))

        # ── Annotate ──────────────────────────────────────────────────────────
        actions_panel.add_component(Label(text='Add annotation', role='body', font_size=13, bold=True))
        ann_ta = TextArea(placeholder='Annotation content…', height=80)
        actions_panel.add_component(ann_ta)
        ann_row = FlowPanel(spacing_above='none', spacing_below='none')
        ann_btn = Button(text='Add annotation', role='tonal-button')
        ann_fb = Label(text='', role='body', font_size=12)
        ann_row.add_component(ann_btn)
        ann_row.add_component(ann_fb)
        actions_panel.add_component(ann_row)

        def _annotate(**kw):
            content = (ann_ta.text or '').strip()
            if not content:
                ann_fb.text = '⚠️ Empty'
                return
            ann_fb.text = 'Saving…'
            try:
                with anvil.server.no_loading_indicator:
                    anvil.server.call('add_thread_entry', thread_id, 'annotation', content,
                                      source='bill', embed=True)
                ann_ta.text = ''
                ann_fb.text = '✅ Added'
                self._load_thread_entries(thread_id, entries_panel)
            except Exception as e:
                ann_fb.text = f'❌ {e}'
        ann_btn.set_event_handler('click', _annotate)

        # ── State change ──────────────────────────────────────────────────────
        actions_panel.add_component(Label(text='State', role='body', font_size=13, bold=True))
        state_row = FlowPanel(spacing_above='none', spacing_below='none')
        state_dd = DropDown(items=['active', 'dormant', 'closed'],
                            selected_value=t_state[0].get('state', 'active'))
        close_tb = TextBox(placeholder='Close reason (optional)')
        close_tb.visible = (t_state[0].get('state') == 'closed')
        state_upd_btn = Button(text='Update state', role='tonal-button')
        state_fb = Label(text='', role='body', font_size=12)
        state_row.add_component(state_dd)
        state_row.add_component(close_tb)
        state_row.add_component(state_upd_btn)
        state_row.add_component(state_fb)
        actions_panel.add_component(state_row)

        def _state_dd_changed(**kw):
            close_tb.visible = (state_dd.selected_value == 'closed')
        state_dd.set_event_handler('change', _state_dd_changed)

        def _update_state(**kw):
            new_state = state_dd.selected_value
            close_reason = (close_tb.text or '').strip() if new_state == 'closed' else None
            state_fb.text = 'Updating…'
            try:
                with anvil.server.no_loading_indicator:
                    thread = anvil.server.call('update_thread_state', thread_id, new_state, close_reason)
                t_state[0] = thread
                badge_lbl.text = f'  {_STATE_BADGE.get(new_state, new_state)}'
                state_fb.text = '✅ Updated'
                self._load_thread_entries(thread_id, entries_panel)
            except Exception as e:
                state_fb.text = f'❌ {e}'
        state_upd_btn.set_event_handler('click', _update_state)

        # ── Wire agent ────────────────────────────────────────────────────────
        actions_panel.add_component(Label(text='Wire agent', role='body', font_size=13, bold=True))
        wire_row = FlowPanel(spacing_above='none', spacing_below='none')
        wire_fb = Label(text='', role='body', font_size=12)

        if wireable:
            agent_names = [a['agent_name'] for a in wireable]
            wire_dd = DropDown(
                items=agent_names,
                selected_value=bound_agent if bound_agent in agent_names else agent_names[0],
            )
            wire_btn = Button(text='Wire agent', role='tonal-button')
            wire_row.add_component(wire_dd)
            wire_row.add_component(wire_btn)

            if bound_agent:
                unwire_btn = Button(text='Unwire', role='text-button')
                wire_row.add_component(unwire_btn)

                def _unwire(**kw):
                    wire_fb.text = 'Unwiring…'
                    try:
                        with anvil.server.no_loading_indicator:
                            thread = anvil.server.call('wire_thread_agent', thread_id, None)
                        t_state[0] = thread
                        meta_lbl.text = f'no agent wired  ·  last active {_rel_time(t_state[0].get("last_activity_at",""))}'
                        self._load_thread_entries(thread_id, entries_panel)
                        self._build_thread_actions(thread_id, t_state, entries_panel, actions_panel, badge_lbl, meta_lbl)
                    except Exception as e:
                        wire_fb.text = f'❌ {e}'
                unwire_btn.set_event_handler('click', _unwire)

            def _wire_agent(**kw):
                agent_name = wire_dd.selected_value
                wire_fb.text = 'Wiring…'
                try:
                    with anvil.server.no_loading_indicator:
                        thread = anvil.server.call('wire_thread_agent', thread_id, agent_name)
                    t_state[0] = thread
                    meta_lbl.text = f'{agent_name}  ·  last active {_rel_time(t_state[0].get("last_activity_at",""))}'
                    self._load_thread_entries(thread_id, entries_panel)
                    self._build_thread_actions(thread_id, t_state, entries_panel, actions_panel, badge_lbl, meta_lbl)
                except Exception as e:
                    wire_fb.text = f'❌ {e}'
            wire_btn.set_event_handler('click', _wire_agent)
        else:
            wire_row.add_component(Label(
                text='No agents available — none have webhook URLs configured.',
                role='body', font_size=12,
            ))

        wire_row.add_component(wire_fb)
        actions_panel.add_component(wire_row)

        # ── Gather (only when bound_agent with webhook) ───────────────────────
        if bound_agent and bound_has_webhook:
            gather_row = FlowPanel(spacing_above='none', spacing_below='none')
            gather_btn = Button(text='▶ Gather', role='tonal-button')
            gather_fb = Label(text='', role='body', font_size=12)
            gather_row.add_component(gather_btn)
            gather_row.add_component(gather_fb)
            actions_panel.add_component(gather_row)

            def _gather(**kw):
                gather_fb.text = 'Triggering…'
                gather_btn.enabled = False
                try:
                    with anvil.server.no_loading_indicator:
                        anvil.server.call('trigger_thread_gather', thread_id)
                    gather_fb.text = '✅ Triggered'
                    self._load_thread_entries(thread_id, entries_panel)
                except Exception as e:
                    gather_fb.text = f'❌ {e}'
                finally:
                    gather_btn.enabled = True
            gather_btn.set_event_handler('click', _gather)

        # ── Export ────────────────────────────────────────────────────────────
        export_row = FlowPanel(spacing_above='none', spacing_below='none')
        export_btn = Button(text='⬇ Export thread', role='tonal-button')
        export_fb = Label(text='', role='body', font_size=12)
        export_row.add_component(export_btn)
        export_row.add_component(export_fb)
        actions_panel.add_component(export_row)
        export_fp = ColumnPanel()
        export_fp.visible = False
        actions_panel.add_component(export_fp)

        def _export_thread(**kw):
            export_fb.text = 'Exporting…'
            export_fp.visible = False
            try:
                with anvil.server.no_loading_indicator:
                    bundle = anvil.server.call('get_thread_bundle', thread_id)
            except Exception as e:
                export_fb.text = f'❌ {e}'
                return
            copied = False
            try:
                anvil.js.window.navigator.clipboard.writeText(bundle)
                copied = True
            except Exception:
                pass
            if copied:
                export_fb.text = '✅ Copied'
            else:
                export_fb.text = '📋 Ready to copy below'
                export_fp.clear()
                export_fp.add_component(TextArea(text=bundle, height=300, enabled=True))
                export_fp.visible = True
        export_btn.set_event_handler('click', _export_thread)

    def refresh_data(self):
        self._load_status()
        self._load_agents()
        self._load_queue()
        self._load_inbox()
        self._refresh_lean_status()
        self._refresh_auto_status()
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
        webhook_url = agent.get('webhook_url')
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

        if webhook_url and status == 'active':
            run_row = FlowPanel(spacing_above='none', spacing_below='none')
            run_btn = Button(text='▶ Run', role='tonal-button')
            run_fb = Label(text='', role='body', font_size=14)
            def _make_invoke(a_name, btn, lbl):
                def _h(**kw):
                    btn.enabled = False
                    lbl.text = 'Triggering…'
                    try:
                        anvil.server.call('invoke_agent', a_name)
                        lbl.text = '✅ Triggered'
                    except Exception as ex:
                        lbl.text = f'❌ {ex}'
                        btn.enabled = True
                return _h
            run_btn.set_event_handler('click', _make_invoke(agent_name, run_btn, run_fb))
            run_row.add_component(run_btn)
            run_row.add_component(run_fb)
            detail.add_component(run_row)

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
            for t in tasks[:20]:
                self._queue_body.add_component(self._build_queue_card(t))
        except Exception as e:
            self._queue_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=16))

    def _build_queue_card(self, task):
        status = task.get('status', '?')
        task_type = task.get('task_type', '?')
        priority = task.get('priority', '?')
        created_at = (task.get('created_at') or '')[:16].replace('T', ' ')
        created_by = task.get('created_by') or '\u2014'
        assigned = task.get('assigned_agent') or '\u2014'
        input_data = task.get('input_data') or {}

        _status_icons = {'pending': '\u23f3', 'claimed': '\u26a1', 'failed': '\u274c'}
        icon = _status_icons.get(status, '\u25aa')

        card = ColumnPanel(role='outlined-card')
        compact = FlowPanel(spacing_above='none', spacing_below='none')
        compact.add_component(Label(text=f'{icon} {task_type}  (p:{priority})', role='body', font_size=16))
        expand_btn = Button(text='+', role='text-button')
        compact.add_component(expand_btn)
        card.add_component(compact)

        detail = ColumnPanel()
        detail.visible = False
        meta = f'status: {status}  |  by: {created_by}  |  agent: {assigned}  |  {created_at}'
        detail.add_component(Label(text=meta, role='body', font_size=13))
        if input_data:
            preview = str(input_data)[:300]
            detail.add_component(Label(text=preview, role='body', font_size=12))
        card.add_component(detail)

        def _toggle(det, btn):
            def _h(**kw):
                det.visible = not det.visible
                btn.text = '\u2212' if det.visible else '+'
            return _h

        expand_btn.set_event_handler('click', _toggle(detail, expand_btn))
        return card

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
        self._sessions_export_btn = Button(text='\u2b07 Export', role='tonal-button')
        self._sessions_export_btn.set_event_handler('click', self._sessions_export_clicked)
        hdr.add_component(self._sessions_export_btn)
        self._sessions_panel.add_component(hdr)
        self._sessions_export_fb = Label(text='', role='body', font_size=14)
        self._sessions_panel.add_component(self._sessions_export_fb)
        self._sessions_export_panel = ColumnPanel()
        self._sessions_export_panel.visible = False
        self._sessions_panel.add_component(self._sessions_export_panel)

        # Boot Briefings section
        self._briefings_lbl = Label(text='Boot Briefings', bold=True, role='body', font_size=16)
        self._sessions_panel.add_component(self._briefings_lbl)
        self._briefings_body = ColumnPanel()
        self._sessions_panel.add_component(self._briefings_body)
        self._sessions_panel.add_component(Label(text='\u2015' * 20, role='body', font_size=16))

        self._sessions_status_card = ColumnPanel(role='outlined-card')
        self._sessions_panel.add_component(self._sessions_status_card)

        self._sessions_panel.add_component(Label(text='―' * 20, role='body', font_size=16))
        site_hdr = FlowPanel(spacing_above='none', spacing_below='small')
        site_hdr.add_component(Label(text='Site Status', bold=True, role='body', font_size=16))
        self._regen_btn = Button(text='Regenerate Site', role='tonal-button')
        self._regen_btn.set_event_handler('click', self._regenerate_site_clicked)
        site_hdr.add_component(self._regen_btn)
        self._sessions_panel.add_component(site_hdr)
        self._regen_feedback = Label(text='', role='body', font_size=14)
        self._sessions_panel.add_component(self._regen_feedback)
        self._site_status_card = ColumnPanel(role='outlined-card')
        self._sessions_panel.add_component(self._site_status_card)

        self._sessions_panel.add_component(Label(text='―' * 20, role='body', font_size=16))
        self._sessions_panel.add_component(
            Label(text='Recent Session Artifacts', bold=True, role='body', font_size=16)
        )
        self._sessions_artifacts_body = ColumnPanel()
        self._sessions_panel.add_component(self._sessions_artifacts_body)

    def _load_sessions(self):
        # Boot briefings
        self._briefings_body.clear()
        try:
            with anvil.server.no_loading_indicator:
                briefings = anvil.server.call('get_boot_briefings', 5)
            unacked = [b for b in briefings if not b.get('acknowledged')]
            self._briefings_lbl.text = f'Boot Briefings ({len(unacked)} unread)' if unacked else 'Boot Briefings'
            if not briefings:
                self._briefings_body.add_component(Label(text='No briefings yet.', role='body', font_size=14))
            else:
                for b in briefings:
                    self._briefings_body.add_component(self._build_briefing_card(b))
        except Exception as e:
            self._briefings_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=13))

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

        # Site status
        self._site_status_card.clear()
        try:
            with anvil.server.no_loading_indicator:
                site = anvil.server.call('get_site_status')
            generated = (site.get('generated_at') or '')[:16].replace('T', ' ')
            agents = site.get('agent_count', '?')
            mode = site.get('mode') or '?'
            directive = (site.get('current_directive') or '').strip()[:80]
            self._site_status_card.add_component(
                Label(text=f'mode: {mode}  |  agents: {agents}  |  as of: {generated} UTC', role='body', font_size=14)
            )
            if directive:
                self._site_status_card.add_component(
                    Label(text=f'Directive: {directive}', role='body', font_size=13)
                )
            for s in site.get('last_sessions', []):
                line = f"{s.get('date','')}  {s.get('descriptor','')}  —  {s.get('outcome','')}"
                self._site_status_card.add_component(
                    Label(text=line[:120], role='body', font_size=13)
                )
        except Exception as e:
            self._site_status_card.add_component(
                Label(text=f'Site status unavailable: {e}', role='body', font_size=14)
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

    def _build_briefing_card(self, briefing):
        briefing_id = briefing.get('id')
        created = (briefing.get('created_at') or '')[:16].replace('T', ' ')
        directive = briefing.get('directive_seen') or '—'
        content = briefing.get('content') or ''
        acked = briefing.get('acknowledged', False)

        card = ColumnPanel(role='outlined-card')
        icon = '✅ ' if acked else '🔔 '
        meta = f'{icon}{created}  |  directive: {directive}'
        card.add_component(Label(text=meta, bold=True, role='body', font_size=14))

        expand_btn = Button(text='+', role='text-button')
        hdr = FlowPanel(spacing_above='none', spacing_below='none')
        hdr.add_component(expand_btn)
        card.add_component(hdr)

        detail = ColumnPanel()
        detail.visible = False
        detail.add_component(Label(text=content, role='body', font_size=13))

        if not acked:
            ack_fb = Label(text='', role='body', font_size=13)
            ack_btn = Button(text='Acknowledge', role='tonal-button')
            def _make_ack(bid, btn, fb, c):
                def _h(**kw):
                    try:
                        anvil.server.call('acknowledge_boot_briefing', bid)
                        fb.text = '✅ Acknowledged'
                        btn.enabled = False
                        c.role = None
                    except Exception as ex:
                        fb.text = f'❌ {ex}'
                return _h
            ack_btn.set_event_handler('click', _make_ack(briefing_id, ack_btn, ack_fb, card))
            detail.add_component(ack_btn)
            detail.add_component(ack_fb)

        card.add_component(detail)

        def _make_expand(det, btn):
            def _e(**kw):
                det.visible = not det.visible
                btn.text = '−' if det.visible else '+'
            return _e

        expand_btn.set_event_handler('click', _make_expand(detail, expand_btn))
        return card

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
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Lessons', role='title', bold=True, font_size=20))
        self._lessons_export_btn = Button(text='⬇ Export', role='tonal-button')
        self._lessons_export_btn.set_event_handler('click', self._lessons_export_clicked)
        hdr.add_component(self._lessons_export_btn)
        self._lessons_panel.add_component(hdr)
        self._lessons_export_fb = Label(text='', role='body', font_size=14)
        self._lessons_panel.add_component(self._lessons_export_fb)
        self._lessons_export_panel = ColumnPanel()
        self._lessons_export_panel.visible = False
        self._lessons_panel.add_component(self._lessons_export_panel)

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
            if filter == 'never_applied':
                self._lessons_body.add_component(Label(
                    text='Lessons created 7+ days ago that have never been applied',
                    role='body', font_size=13, italic=True,
                ))
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
        self._memory_export_btn = Button(text='\u2b07 Export All', role='tonal-button')
        self._memory_export_btn.set_event_handler('click', self._memory_export_clicked)
        hdr.add_component(self._memory_export_btn)
        self._memory_panel.add_component(hdr)
        self._memory_export_fb = Label(text='', role='body', font_size=14)
        self._memory_panel.add_component(self._memory_export_fb)
        self._memory_export_panel = ColumnPanel()
        self._memory_export_panel.visible = False
        self._memory_panel.add_component(self._memory_export_panel)

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
        self._errors_export_btn = Button(text='⬇ Export Errors', role='tonal-button')
        self._errors_export_btn.set_event_handler('click', self._errors_export_clicked)
        sb_row.add_component(rp_btn)
        sb_row.add_component(el_btn)
        sb_row.add_component(self._errors_export_btn)
        self._memory_panel.add_component(sb_row)
        self._errors_export_fb = Label(text='', role='body', font_size=14)
        self._memory_panel.add_component(self._errors_export_fb)
        self._errors_export_panel = ColumnPanel()
        self._errors_export_panel.visible = False
        self._memory_panel.add_component(self._errors_export_panel)

        self._mem_supabase_body = ColumnPanel()
        self._memory_panel.add_component(self._mem_supabase_body)

    def _refresh_memory(self):
        self._memory_loaded = False
        self._memory_selected_coll = None
        self._memory_export_btn.text = '⬇ Export All'
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
                        self._memory_export_btn.text = f'⬇ Export {name}'
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
                    error_id = row.get('id')
                    wf = row.get('workflow_name') or '(unknown)'
                    msg = (row.get('error_message') or '')[:120]
                    date = (row.get('timestamp') or '')[:16].replace('T', ' ')
                    card.add_component(Label(text=wf, bold=True, role='body', font_size=14))
                    card.add_component(Label(text=msg, role='body', font_size=13))
                    card.add_component(Label(text=date, role='body', font_size=12))
                    notes_box = TextBox(placeholder='Resolution notes…', width=200)
                    card.add_component(notes_box)
                    resolve_fb = Label(text='', role='body', font_size=12)
                    resolve_btn = Button(text='Resolve', role='tonal-button')
                    def _make_resolve(eid, nb, fb, btn, c):
                        def _h(**kw):
                            try:
                                anvil.server.call('resolve_error_log', eid, nb.text or None)
                                fb.text = '✅ Resolved'
                                btn.enabled = False
                                nb.enabled = False
                                c.role = None
                            except Exception as ex:
                                fb.text = f'❌ {ex}'
                        return _h
                    resolve_btn.set_event_handler('click', _make_resolve(error_id, notes_box, resolve_fb, resolve_btn, card))
                    card.add_component(resolve_btn)
                    card.add_component(resolve_fb)
                self._mem_supabase_body.add_component(card)
        except Exception as e:
            self._mem_supabase_body.clear()
            self._mem_supabase_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    # ── Research tab ─────────────────────────────────────────────────────────

    def _build_research_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Research', role='title', bold=True, font_size=20))
        self._research_run_btn = Button(text='▶ Run research', role='tonal-button')
        self._research_run_btn.set_event_handler('click', self._research_run_clicked)
        hdr.add_component(self._research_run_btn)
        self._research_export_btn = Button(text='⬇ Export', role='tonal-button')
        self._research_export_btn.set_event_handler('click', self._research_export_clicked)
        hdr.add_component(self._research_export_btn)
        self._research_panel.add_component(hdr)

        self._research_run_fb = Label(text='', role='body', font_size=14)
        self._research_panel.add_component(self._research_run_fb)

        self._research_export_fb = Label(text='', role='body', font_size=14)
        self._research_panel.add_component(self._research_export_fb)
        self._research_export_panel = ColumnPanel()
        self._research_export_panel.visible = False
        self._research_panel.add_component(self._research_export_panel)

        self._research_status_lbl = Label(text='', role='body', font_size=14)
        self._research_panel.add_component(self._research_status_lbl)

        self._research_articles_body = ColumnPanel()
        self._research_panel.add_component(self._research_articles_body)

        self._research_panel.add_component(Label(text='―' * 20, role='body', font_size=16))

        fb_row = FlowPanel(spacing_above='small', spacing_below='small')

        agent_fb_col = ColumnPanel()
        agent_fb_col.add_component(Label(text='Feedback for the agent', bold=True, role='body', font_size=15))
        self._research_agent_fb_box = TextArea(
            placeholder='What should the agent research differently?',
            role='outlined',
            height=60,
        )
        agent_fb_col.add_component(self._research_agent_fb_box)
        agent_submit = Button(text='Submit', role='tonal-button')
        self._research_agent_fb_status = Label(text='', role='body', font_size=13)
        agent_submit.set_event_handler(
            'click',
            lambda **kw: self._submit_research_feedback(
                'agent', 'context_engineering_research',
                self._research_agent_fb_box, self._research_agent_fb_status,
            ),
        )
        agent_fb_col.add_component(agent_submit)
        agent_fb_col.add_component(self._research_agent_fb_status)
        fb_row.add_component(agent_fb_col)

        ui_fb_col = ColumnPanel()
        ui_fb_col.add_component(Label(text='Feedback for this UI', bold=True, role='body', font_size=15))
        self._research_ui_fb_box = TextArea(
            placeholder='What should this view show differently?',
            role='outlined',
            height=60,
        )
        ui_fb_col.add_component(self._research_ui_fb_box)
        ui_submit = Button(text='Submit', role='tonal-button')
        self._research_ui_fb_status = Label(text='', role='body', font_size=13)
        ui_submit.set_event_handler(
            'click',
            lambda **kw: self._submit_research_feedback(
                'anvil_view', 'research_tab',
                self._research_ui_fb_box, self._research_ui_fb_status,
            ),
        )
        ui_fb_col.add_component(ui_submit)
        ui_fb_col.add_component(self._research_ui_fb_status)
        fb_row.add_component(ui_fb_col)

        self._research_panel.add_component(fb_row)

        self._research_panel.add_component(Label(text='―' * 20, role='body', font_size=16))
        fb_hist_hdr = FlowPanel(spacing_above='small', spacing_below='small')
        fb_hist_hdr.add_component(Label(text='Feedback History', bold=True, role='body', font_size=16))
        fb_hist_refresh = Button(text='↻', role='text-button')
        fb_hist_refresh.set_event_handler('click', lambda **kw: self._load_feedback_threads())
        fb_hist_hdr.add_component(fb_hist_refresh)
        self._research_panel.add_component(fb_hist_hdr)
        self._feedback_threads_body = ColumnPanel()
        self._research_panel.add_component(self._feedback_threads_body)

    def _load_research_tab(self):
        self._research_status_lbl.text = 'Loading…'
        try:
            with anvil.server.no_loading_indicator:
                summary = anvil.server.call('get_research_run_summary')
                counters = anvil.server.call('get_research_counters')
            total = counters.get('total', '?')
            unreviewed = counters.get('unreviewed', '?')
            last_24h = counters.get('last_24h', '?')
            counter_str = f'{total} total · {unreviewed} unreviewed · {last_24h} new (24h)'
            if summary.get('retrieved_at'):
                ts = (summary['retrieved_at'] or '')[:16].replace('T', ' ')
                self._research_status_lbl.text = (
                    f"Last run: {ts} UTC — {summary['count']} article(s)  |  {counter_str}"
                )
            else:
                self._research_status_lbl.text = f'No runs yet  |  {counter_str}'
        except Exception as e:
            self._research_status_lbl.text = f'Status unavailable: {e}'

        self._research_articles_body.clear()
        self._research_articles_body.add_component(
            Label(text='Loading articles…', role='body', font_size=16)
        )
        try:
            with anvil.server.no_loading_indicator:
                articles = anvil.server.call('get_research_articles', 50)
            self._research_articles = articles
            self._render_research_articles(articles)
        except Exception as e:
            self._research_articles_body.clear()
            self._research_articles_body.add_component(
                Label(text=f'Error: {e}', role='body', font_size=16)
            )
        self._load_feedback_threads()

    def _render_research_articles(self, articles):
        self._research_articles_body.clear()
        if not articles:
            self._research_articles_body.add_component(
                Label(text='No articles yet. Press "▶ Run research" to fetch some.', role='body', font_size=16)
            )
            return

        runs = {}
        run_order = []
        for a in articles:
            run_id = a.get('agent_run_id') or 'unknown'
            if run_id not in runs:
                runs[run_id] = []
                run_order.append(run_id)
            runs[run_id].append(a)

        for i, run_id in enumerate(run_order):
            run_articles = runs[run_id]
            run_ts = (run_articles[0].get('retrieved_at') or '')[:16].replace('T', ' ')

            run_outer = ColumnPanel(role='outlined-card')
            run_hdr = FlowPanel(spacing_above='small', spacing_below='none')
            run_hdr.add_component(
                Label(
                    text=f'Run {run_ts} UTC — {len(run_articles)} article(s)',
                    bold=True, role='body', font_size=15,
                )
            )
            run_toggle_btn = Button(text=_EXPAND if i == 0 else _COLLAPSE, role='text-button')
            run_hdr.add_component(run_toggle_btn)
            run_outer.add_component(run_hdr)

            run_body = ColumnPanel()
            run_body.visible = (i == 0)
            run_outer.add_component(run_body)

            def _make_run_toggle(body, btn):
                def _t(**kw):
                    body.visible = not body.visible
                    btn.text = _EXPAND if body.visible else _COLLAPSE
                return _t

            run_toggle_btn.set_event_handler('click', _make_run_toggle(run_body, run_toggle_btn))

            for article in run_articles:
                run_body.add_component(self._build_research_article_card(article))

            self._research_articles_body.add_component(run_outer)

    def _build_research_article_card(self, article):
        article_id = article.get('id')
        title = (article.get('title') or '(no title)')[:120]
        url = article.get('url') or ''
        source = article.get('source') or ''
        query_used = article.get('query_used') or ''
        summary = (article.get('summary') or '')
        current_rating = article.get('rating') or 0
        current_comment = article.get('comment') or ''
        current_status = article.get('status') or 'new'

        card = ColumnPanel(role='outlined-card')

        title_link = Link(text=title, url=url)
        card.add_component(title_link)

        meta_row = FlowPanel(spacing_above='none', spacing_below='none')
        if source:
            meta_row.add_component(Label(text=source, role='body', font_size=13))
        if query_used:
            meta_row.add_component(Label(text=f'[{query_used[:60]}]', role='body', font_size=12))
        card.add_component(meta_row)

        if summary:
            card.add_component(Label(text=summary[:300], role='body', font_size=14))

        action_row = FlowPanel(spacing_above='none', spacing_below='none')
        fb_label = Label(text='', role='body', font_size=13)

        rating_state = [current_rating]
        up_btn = Button(
            text='\U0001f44d' + (' ✓' if current_rating == 1 else ''),
            role='outlined-button',
        )
        down_btn = Button(
            text='\U0001f44e' + (' ✓' if current_rating == -1 else ''),
            role='outlined-button',
        )

        def _make_rate(aid, new_r, up, down, state, lbl):
            def _h(**kw):
                actual = 0 if state[0] == new_r else new_r
                try:
                    with anvil.server.no_loading_indicator:
                        anvil.server.call('rate_research_article', aid, actual)
                    state[0] = actual
                    up.text = '\U0001f44d' + (' ✓' if state[0] == 1 else '')
                    down.text = '\U0001f44e' + (' ✓' if state[0] == -1 else '')
                    lbl.text = ''
                except Exception as ex:
                    lbl.text = f'❌ {ex}'
            return _h

        up_btn.set_event_handler('click', _make_rate(article_id, 1, up_btn, down_btn, rating_state, fb_label))
        down_btn.set_event_handler('click', _make_rate(article_id, -1, up_btn, down_btn, rating_state, fb_label))
        action_row.add_component(up_btn)
        action_row.add_component(down_btn)

        comment_box = TextBox(placeholder='Comment', text=current_comment, width=200)

        def _make_save_comment(aid, cbox, lbl):
            def _h(**kw):
                try:
                    with anvil.server.no_loading_indicator:
                        anvil.server.call('comment_research_article', aid, cbox.text or '')
                    lbl.text = '✅'
                except Exception as ex:
                    lbl.text = f'❌ {ex}'
            return _h

        comment_box.set_event_handler('lost_focus', _make_save_comment(article_id, comment_box, fb_label))
        action_row.add_component(comment_box)

        status_dd = DropDown(items=['new', 'reviewed', 'archived'], selected_value=current_status)

        def _make_status(aid, dd, lbl):
            def _h(**kw):
                try:
                    with anvil.server.no_loading_indicator:
                        anvil.server.call('set_research_article_status', aid, dd.selected_value)
                    lbl.text = f'✅ {dd.selected_value}'
                except Exception as ex:
                    lbl.text = f'❌ {ex}'
            return _h

        status_dd.set_event_handler('change', _make_status(article_id, status_dd, fb_label))
        action_row.add_component(status_dd)

        card.add_component(action_row)
        card.add_component(fb_label)
        return card

    def _load_feedback_threads(self):
        self._feedback_threads_body.clear()
        try:
            with anvil.server.no_loading_indicator:
                data = anvil.server.call('get_feedback_threads')
        except Exception as e:
            self._feedback_threads_body.add_component(
                Label(text=f'Error: {e}', role='body', font_size=14)
            )
            return

        pending = data.get('pending') or []
        resolved = data.get('resolved') or []

        if not pending and not resolved:
            self._feedback_threads_body.add_component(
                Label(text='No feedback yet.', role='body', font_size=14)
            )
            return

        if pending:
            self._feedback_threads_body.add_component(
                Label(text=f'Pending ({len(pending)})', bold=True, role='body', font_size=15)
            )
            for item in pending:
                self._feedback_threads_body.add_component(self._build_feedback_thread_card(item))

        if resolved:
            self._feedback_threads_body.add_component(
                Label(text=f'Recently Resolved ({len(resolved)})', bold=True, role='body', font_size=15)
            )
            for item in resolved:
                self._feedback_threads_body.add_component(self._build_feedback_thread_card(item))

    def _build_feedback_thread_card(self, item):
        target_type = item.get('target_type') or ''
        target_id = item.get('target_id') or ''
        content = item.get('content') or ''
        created_at = (item.get('created_at') or '')[:16].replace('T', ' ')
        action_summary = item.get('action_summary')
        action_session = item.get('action_session')
        action_result_url = item.get('action_result_url')

        card = ColumnPanel(role='outlined-card')
        card.add_component(Label(
            text=f'{target_type}: {target_id}  |  {created_at}',
            role='body', font_size=13,
        ))
        card.add_component(Label(text=content, role='body', font_size=14))

        if action_summary is not None:
            is_deferred = action_summary.startswith('Deferred:')
            icon = '⏸ ' if is_deferred else '✅ '
            resp_size = 13 if is_deferred else 14
            card.add_component(Label(text=icon + action_summary, role='body', font_size=resp_size))
            if action_session:
                card.add_component(Label(
                    text=f'Session: {action_session}',
                    role='body', font_size=12,
                ))
            if action_result_url:
                card.add_component(Link(text='View result →', url=action_result_url))

        return card

    def _research_run_clicked(self, **event_args):
        import time
        self._research_run_btn.enabled = False
        self._research_run_fb.text = 'Triggering…'
        try:
            with anvil.server.no_loading_indicator:
                anvil.server.call('invoke_agent', 'context_engineering_research')
            self._research_run_fb.text = '✅ Triggered — articles arriving'
            prev_count = len(self._research_articles)
            found = False
            for _ in range(12):
                time.sleep(5)
                with anvil.server.no_loading_indicator:
                    articles = anvil.server.call('get_research_articles', 50)
                if len(articles) > prev_count:
                    self._research_articles = articles
                    self._render_research_articles(articles)
                    self._research_run_fb.text = '✅ New articles loaded'
                    with anvil.server.no_loading_indicator:
                        summary = anvil.server.call('get_research_run_summary')
                    if summary.get('retrieved_at'):
                        ts = (summary['retrieved_at'] or '')[:16].replace('T', ' ')
                        self._research_status_lbl.text = (
                            f"Last run: {ts} UTC — {summary['count']} article(s)"
                        )
                    found = True
                    break
            if not found:
                self._research_run_fb.text = 'No new articles yet — refresh manually'
        except Exception as e:
            self._research_run_fb.text = f'❌ {e}'
        self._research_run_btn.enabled = True

    def _research_export_clicked(self, **event_args):
        self._research_export_fb.text = 'Exporting…'
        self._research_export_panel.visible = False
        try:
            with anvil.server.no_loading_indicator:
                bundle = anvil.server.call('get_research_bundle')
        except Exception as e:
            self._research_export_fb.text = f'❌ {e}'
            return

        # Try clipboard; fall back to TextArea
        copied = False
        try:
            anvil.js.window.navigator.clipboard.writeText(bundle)
            copied = True
        except Exception:
            pass

        if copied:
            self._research_export_fb.text = '✅ Copied'
        else:
            self._research_export_fb.text = '📋 Ready to copy below'
            self._research_export_panel.clear()
            self._research_export_panel.add_component(
                TextArea(text=bundle, height=300, enabled=True)
            )
            self._research_export_panel.visible = True

    def _submit_research_feedback(self, target_type, target_id, textbox, status_lbl):
        import time
        content = (textbox.text or '').strip()
        if not content:
            status_lbl.text = '⚠️ Empty'
            return
        try:
            with anvil.server.no_loading_indicator:
                anvil.server.call('submit_agent_feedback_v2', target_type, target_id, content)
            textbox.text = ''
            status_lbl.text = '✅ Saved'
            time.sleep(3)
            status_lbl.text = ''
        except Exception as ex:
            status_lbl.text = f'❌ {ex}'

    # ── Artifacts tab ────────────────────────────────────────────────────────

    def _build_artifacts_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Artifacts', role='title', bold=True, font_size=20))
        ref_btn = Button(text='\u21bb', role='text-button')
        ref_btn.set_event_handler('click', lambda **kw: self._reload_artifacts())
        hdr.add_component(ref_btn)
        self._artifacts_export_btn = Button(text='\u2b07 Export', role='tonal-button')
        self._artifacts_export_btn.set_event_handler('click', self._artifacts_export_clicked)
        hdr.add_component(self._artifacts_export_btn)
        self._artifacts_panel.add_component(hdr)
        self._artifacts_export_fb = Label(text='', role='body', font_size=14)
        self._artifacts_panel.add_component(self._artifacts_export_fb)
        self._artifacts_export_panel = ColumnPanel()
        self._artifacts_export_panel.visible = False
        self._artifacts_panel.add_component(self._artifacts_export_panel)

        self._artifacts_filter_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._artifacts_panel.add_component(self._artifacts_filter_row)

        self._artifacts_body = ColumnPanel()
        self._artifacts_panel.add_component(self._artifacts_body)

    def _reload_artifacts(self):
        self._artifacts_loaded = False
        self._artifacts_agent_filter = None
        self._artifacts_type_filter = None
        self._load_artifacts()
        self._artifacts_loaded = True

    def _load_artifacts(self):
        self._artifacts_body.clear()
        self._artifacts_body.add_component(Label(text='Loading\u2026', role='body', font_size=16))
        try:
            with anvil.server.no_loading_indicator:
                meta = anvil.server.call('get_artifact_agents')
                artifacts = anvil.server.call(
                    'get_artifacts',
                    self._artifacts_agent_filter,
                    self._artifacts_type_filter,
                )
            self._build_artifact_filters(meta)
            self._artifacts_body.clear()
            self._artifacts_body.add_component(
                Label(text=f'{len(artifacts)} artifact(s)', role='body', font_size=14)
            )
            for artifact in artifacts:
                self._artifacts_body.add_component(self._build_artifact_row(artifact))
        except Exception as e:
            self._artifacts_body.clear()
            self._artifacts_body.add_component(Label(text=f'Error: {e}', role='body', font_size=16))

    def _build_artifact_filters(self, meta):
        self._artifacts_filter_row.clear()
        all_btn = Button(text='All', role='filled-button' if not self._artifacts_agent_filter and not self._artifacts_type_filter else 'tonal-button')

        def _clear_filters(**kw):
            self._artifacts_agent_filter = None
            self._artifacts_type_filter = None
            self._artifacts_loaded = False
            self._load_artifacts()
            self._artifacts_loaded = True

        all_btn.set_event_handler('click', _clear_filters)
        self._artifacts_filter_row.add_component(all_btn)

        for agent in meta.get('agents', []):
            btn = Button(
                text=agent[:20],
                role='filled-button' if self._artifacts_agent_filter == agent else 'tonal-button',
            )
            def _make_agent_filter(a):
                def _h(**kw):
                    self._artifacts_agent_filter = a
                    self._artifacts_type_filter = None
                    self._artifacts_loaded = False
                    self._load_artifacts()
                    self._artifacts_loaded = True
                return _h
            btn.set_event_handler('click', _make_agent_filter(agent))
            self._artifacts_filter_row.add_component(btn)

        for atype in meta.get('types', []):
            btn = Button(
                text=atype[:20],
                role='filled-button' if self._artifacts_type_filter == atype else 'tonal-button',
            )
            def _make_type_filter(t):
                def _h(**kw):
                    self._artifacts_type_filter = t
                    self._artifacts_agent_filter = None
                    self._artifacts_loaded = False
                    self._load_artifacts()
                    self._artifacts_loaded = True
                return _h
            btn.set_event_handler('click', _make_type_filter(atype))
            self._artifacts_filter_row.add_component(btn)

    def _build_artifact_row(self, artifact):
        artifact_id = artifact.get('id')
        agent = artifact.get('agent_name', '')
        atype = artifact.get('artifact_type', '')
        summary = (artifact.get('summary') or '(no summary)')[:120]
        confidence = artifact.get('confidence')
        conf_str = f'{float(confidence):.2f}' if confidence is not None else '\u2014'
        created = (artifact.get('created_at') or '')[:10]
        rating = artifact.get('bill_rating')
        reviewed = artifact.get('reviewed_by_bill', False)

        card = ColumnPanel(role='outlined-card')

        hdr = FlowPanel(spacing_above='none', spacing_below='none')
        hdr.add_component(Label(text=f'{agent}', bold=True, role='body', font_size=15))
        expand_btn = Button(text='+', role='text-button')
        hdr.add_component(expand_btn)
        card.add_component(hdr)

        type_row = f'{atype}  |  conf: {conf_str}  |  {created}'
        if reviewed:
            type_row += f'  |  \U0001f44d' if rating == 1 else (f'  |  \U0001f44e' if rating == -1 else '  |  reviewed')
        card.add_component(Label(text=type_row, role='body', font_size=13))
        card.add_component(Label(text=summary, role='body', font_size=14))

        detail = ColumnPanel()
        detail.visible = False
        card.add_component(detail)

        fb_label = Label(text='', role='body', font_size=13)

        def _make_load_detail(aid, det):
            def _h(**kw):
                if det.get_components():
                    det.visible = not det.visible
                    expand_btn.text = '\u2212' if det.visible else '+'
                    return
                det.add_component(Label(text='Loading\u2026', role='body', font_size=13))
                try:
                    with anvil.server.no_loading_indicator:
                        full = anvil.server.call('get_artifact', aid)
                    det.clear()
                    content = full.get('content')
                    if isinstance(content, dict):
                        for k, v in content.items():
                            det.add_component(Label(text=f'{k}: {str(v)[:200]}', role='body', font_size=13))
                    else:
                        det.add_component(Label(text=str(content)[:800], role='body', font_size=13))
                    if full.get('bill_comment'):
                        det.add_component(Label(text=f'Comment: {full["bill_comment"]}', role='body', font_size=13))
                    # Rating row
                    comment_box = TextBox(placeholder='Comment\u2026', width=200)
                    det.add_component(comment_box)
                    rate_row = FlowPanel(spacing_above='none', spacing_below='none')
                    up = Button(text='\U0001f44d', role='outlined-button')
                    dn = Button(text='\U0001f44e', role='outlined-button')
                    def _make_rate(aid2, r, lbl, cbox):
                        def _h2(**kw):
                            try:
                                anvil.server.call('rate_artifact', aid2, r, cbox.text or None)
                                lbl.text = '\u2705 Rated'
                                up.enabled = False
                                dn.enabled = False
                                cbox.enabled = False
                            except Exception as ex:
                                lbl.text = f'\u274c {ex}'
                        return _h2
                    up.set_event_handler('click', _make_rate(aid, 1, fb_label, comment_box))
                    dn.set_event_handler('click', _make_rate(aid, -1, fb_label, comment_box))
                    rate_row.add_component(up)
                    rate_row.add_component(dn)
                    det.add_component(rate_row)
                    det.visible = True
                    expand_btn.text = '\u2212'
                except Exception as ex:
                    det.clear()
                    det.add_component(Label(text=f'Error: {ex}', role='body', font_size=13))
                    det.visible = True
            return _h

        expand_btn.set_event_handler('click', _make_load_detail(artifact_id, detail))
        card.add_component(fb_label)
        return card

    # ── Skills tab ───────────────────────────────────────────────────────────

    def _build_skills_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Skills', role='title', bold=True, font_size=20))
        ref_btn = Button(text='\u21bb', role='text-button')
        ref_btn.set_event_handler('click', lambda **kw: self._reload_skills())
        hdr.add_component(ref_btn)
        self._skills_export_btn = Button(text='\u2b07 Export', role='tonal-button')
        self._skills_export_btn.set_event_handler('click', self._skills_export_clicked)
        hdr.add_component(self._skills_export_btn)
        self._skills_panel.add_component(hdr)
        self._skills_export_fb = Label(text='', role='body', font_size=14)
        self._skills_panel.add_component(self._skills_export_fb)
        self._skills_export_panel = ColumnPanel()
        self._skills_export_panel.visible = False
        self._skills_panel.add_component(self._skills_export_panel)

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

    def _run_export(self, callable_name, fb_lbl, fallback_panel, **kwargs):
        fb_lbl.text = 'Exporting…'
        fallback_panel.visible = False
        try:
            with anvil.server.no_loading_indicator:
                bundle = anvil.server.call(callable_name, **kwargs)
        except Exception as e:
            fb_lbl.text = f'❌ {e}'
            return
        copied = False
        try:
            anvil.js.window.navigator.clipboard.writeText(bundle)
            copied = True
        except Exception:
            pass
        if copied:
            fb_lbl.text = '✅ Copied'
        else:
            fb_lbl.text = '📋 Ready to copy below'
            fallback_panel.clear()
            fallback_panel.add_component(TextArea(text=bundle, height=300, enabled=True))
            fallback_panel.visible = True

    def _fleet_export_clicked(self, **event_args):
        self._run_export('get_fleet_bundle', self._fleet_export_fb, self._fleet_export_panel)

    def _sessions_export_clicked(self, **event_args):
        self._run_export('get_sessions_bundle', self._sessions_export_fb, self._sessions_export_panel)

    def _lessons_export_clicked(self, **event_args):
        self._run_export('get_lessons_bundle', self._lessons_export_fb, self._lessons_export_panel,
                         filter=self._lessons_current_filter)

    def _memory_export_clicked(self, **event_args):
        self._run_export('get_memory_bundle', self._memory_export_fb, self._memory_export_panel,
                         collection=self._memory_selected_coll)

    def _errors_export_clicked(self, **event_args):
        self._run_export('get_errors_bundle', self._errors_export_fb, self._errors_export_panel)

    def _skills_export_clicked(self, **event_args):
        self._run_export('get_skills_bundle', self._skills_export_fb, self._skills_export_panel)

    def _artifacts_export_clicked(self, **event_args):
        self._run_export('get_artifacts_bundle', self._artifacts_export_fb, self._artifacts_export_panel,
                         agent_name=self._artifacts_agent_filter, artifact_type=self._artifacts_type_filter)

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

    def _regenerate_site_clicked(self, **event_args):
        self._regen_feedback.text = 'Regenerating...'
        self._regen_btn.enabled = False
        try:
            result = anvil.server.call('update_site')
            ts = (result.get('generated_at') or '')[:16].replace('T', ' ')
            self._regen_feedback.text = f'✅ Site updated at {ts} UTC'
            self._site_status_card.clear()
            with anvil.server.no_loading_indicator:
                site = anvil.server.call('get_site_status')
            generated = (site.get('generated_at') or '')[:16].replace('T', ' ')
            self._site_status_card.add_component(
                Label(text=f"mode: {site.get('mode','?')}  |  agents: {site.get('agent_count','?')}  |  as of: {generated} UTC", role='body', font_size=14)
            )
        except Exception as e:
            self._regen_feedback.text = f'❌ Error: {e}'
        self._regen_btn.enabled = True

    def _refresh_clicked(self, **event_args):
        self.refresh_data()
