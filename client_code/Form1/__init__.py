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
    'summary': '\U0001f4cb',
    'screening': '\U0001f50e',
    'screening_uncertain': '\u2753',
    'sub_question_candidate': '\U0001f4ac',
    'charter': '\U0001f4dc',
    'cycle_metadata': '\U0001f504',
    'memory_consultation': '\U0001f9e0',
    'finding': '\U0001f4a1',
    'cycle_summary': '\U0001f4ca',
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
        self._grader_loaded = False
        self._workspace_loaded = False
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
        self._grader_tab_btn = Button(text='Grader', role='tonal-button')
        self._workspace_tab_btn = Button(text='Workspace', role='tonal-button')
        self._fleet_tab_btn.set_event_handler('click', self._show_fleet_tab)
        self._sessions_tab_btn.set_event_handler('click', self._show_sessions_tab)
        self._lessons_tab_btn.set_event_handler('click', self._show_lessons_tab)
        self._memory_tab_btn.set_event_handler('click', self._show_memory_tab)
        self._research_tab_btn.set_event_handler('click', self._show_research_tab)
        self._threads_tab_btn.set_event_handler('click', self._show_threads_tab)
        self._skills_tab_btn.set_event_handler('click', self._show_skills_tab)
        self._artifacts_tab_btn.set_event_handler('click', self._show_artifacts_tab)
        self._grader_tab_btn.set_event_handler('click', self._show_grader_tab)
        self._workspace_tab_btn.set_event_handler('click', self._show_workspace_tab)
        tab_row.add_component(self._fleet_tab_btn)
        tab_row.add_component(self._sessions_tab_btn)
        tab_row.add_component(self._lessons_tab_btn)
        tab_row.add_component(self._memory_tab_btn)
        tab_row.add_component(self._research_tab_btn)
        tab_row.add_component(self._threads_tab_btn)
        tab_row.add_component(self._skills_tab_btn)
        tab_row.add_component(self._artifacts_tab_btn)
        tab_row.add_component(self._grader_tab_btn)
        tab_row.add_component(self._workspace_tab_btn)
        self.content_panel.add_component(tab_row)

        # Fleet panel (default visible)
        self._fleet_panel = ColumnPanel()
        _fleet_hdr = FlowPanel(spacing_above='small', spacing_below='small')
        _fleet_hdr.add_component(Label(text='Fleet', role='title', bold=True, font_size=20))
        self._fleet_export_btn = Button(text='⬇ Export', role='tonal-button')
        self._fleet_export_btn.set_event_handler('click', self._fleet_export_clicked)
        _fleet_hdr.add_component(self._fleet_export_btn)
        self._cmt_export_btn = Button(text='✏️ Comment work', role='outlined-button')
        self._cmt_export_fb = Label(text='', role='body', font_size=13)
        self._cmt_export_btn.set_event_handler('click', self._export_comment_work_clicked)
        _fleet_hdr.add_component(self._cmt_export_btn)
        self._fleet_panel.add_component(_fleet_hdr)
        self._cmt_export_panel = ColumnPanel()
        self._cmt_export_panel.visible = False
        self._fleet_panel.add_component(self._cmt_export_panel)
        self._fleet_panel.add_component(self._cmt_export_fb)
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

        # Grader panel (hidden by default)
        self._grader_panel = ColumnPanel()
        self._grader_panel.visible = False
        self._build_grader_layout()
        self.content_panel.add_component(self._grader_panel)

        # Workspace panel (hidden by default)
        self._workspace_panel = ColumnPanel()
        self._workspace_panel.visible = False
        self._build_workspace_layout()
        self.content_panel.add_component(self._workspace_panel)

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
            'grader': self._grader_panel,
            'workspace': self._workspace_panel,
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
            'grader': self._grader_tab_btn,
            'workspace': self._workspace_tab_btn,
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

    def _show_grader_tab(self, **event_args):
        self._set_tab('grader')
        if not self._grader_loaded:
            self._load_grader_reviews()
            self._grader_loaded = True

    def _show_workspace_tab(self, **event_args):
        self._set_tab('workspace')
        if not self._workspace_loaded:
            self._load_workspace_notes()
            self._workspace_loaded = True

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
                self._load_thread_entries(thread_id, entries_panel, t_state)
                self._build_thread_actions(thread_id, t_state, entries_panel, actions_panel, badge_lbl, meta_lbl)
                loaded[0] = True
                content_panel.visible = True
            else:
                content_panel.visible = not content_panel.visible
            toggle_btn.text = _EXPAND if content_panel.visible else _COLLAPSE

        toggle_btn.set_event_handler('click', _toggle)
        return card

    def _load_thread_entries(self, thread_id, entries_panel, t_state=None):
        entries_panel.clear()
        entries_panel.add_component(Label(text='Loading entries\u2026', role='body', font_size=13))
        try:
            with anvil.server.no_loading_indicator:
                entries = anvil.server.call('get_thread_entries', thread_id)
            entries_panel.clear()

            # Header: full question + state badge
            td = t_state[0] if t_state else {}
            question = td.get('question') or ''
            state = td.get('state') or 'active'
            if question:
                entries_panel.add_component(Label(text=question, role='body', font_size=14, bold=True))
            entries_panel.add_component(Label(
                text=_STATE_BADGE.get(state, state), role='body', font_size=13
            ))

            # Charter block \u2014 most recent charter at top
            _charter_entries = sorted(
                [e for e in entries if (e.get('entry_type') or '') == 'charter'],
                key=lambda e: e.get('created_at') or '', reverse=True
            )
            _active_charter = _charter_entries[0] if _charter_entries else None
            if _active_charter:
                charter_card = ColumnPanel(role='outlined-card')
                charter_card.add_component(Label(text='\U0001f4dc Research Charter', role='title', bold=True, font_size=14))
                charter_content = _active_charter.get('content') or ''
                # Render section headers as bold labels
                for line in charter_content.splitlines():
                    line = line.rstrip()
                    if line.startswith('## ') or line.startswith('### '):
                        charter_card.add_component(Label(text=line.lstrip('#').strip(), role='body', font_size=13, bold=True))
                    elif line:
                        charter_card.add_component(Label(text=line, role='body', font_size=13))
                ts = (_active_charter.get('created_at') or '')[:16].replace('T', ' ')
                charter_card.add_component(Label(text=f'Added {ts}', role='body', font_size=12))
                entries_panel.add_component(charter_card)

            # Watch state badge (B-098)
            td_full = t_state[0] if t_state else {}
            if td_full.get('watch_enabled'):
                _wi = td_full.get('watch_interval', 'weekly')
                _nw = (td_full.get('next_watch_due_at') or '')[:16].replace('T', ' ')
                _lw = (td_full.get('last_watch_cycle_at') or '')[:16].replace('T', ' ')
                entries_panel.add_component(Label(
                    text=f'👁 Watch: {_wi}  ·  last {_lw or "never"}  ·  next {_nw or "?"}',
                    role='body', font_size=12
                ))

            # Cycle grader verdict badge (B-097)
            try:
                with anvil.server.no_loading_indicator:
                    cycle_verdict = anvil.server.call('get_latest_cycle_verdict', thread_id)
                if cycle_verdict:
                    _cv = cycle_verdict.get('verdict', '')
                    _cv_icons = {'continue': '🔄', 'complete': '✅', 'pause': '⚠️', 'fail': '❌'}
                    _cv_icon = _cv_icons.get(_cv, '❓')
                    _cv_ts = (cycle_verdict.get('created_at') or '')[:16].replace('T', ' ')
                    _cv_row = FlowPanel(spacing_above='none', spacing_below='none')
                    _cv_row.add_component(Label(
                        text=f'{_cv_icon} Cycle grader: {_cv.upper()}  ·  {_cv_ts}',
                        role='body', font_size=13, bold=True
                    ))
                    entries_panel.add_component(_cv_row)
                    if cycle_verdict.get('rationale'):
                        entries_panel.add_component(Label(
                            text=cycle_verdict['rationale'][:200], role='body', font_size=13
                        ))
            except Exception:
                pass

            _summary_candidates = sorted(
                [e for e in entries if (e.get('entry_type') or '') == 'summary'
                 and (e.get('content') or '').strip()],
                key=lambda e: e.get('created_at') or '', reverse=True
            )
            top_summary = _summary_candidates[0] if _summary_candidates else None
            if top_summary:
                entries_panel.add_component(Label(text='Standing summary', role='title', font_size=13, bold=True))
                entries_panel.add_component(Label(text=top_summary.get('content') or '', role='body', font_size=13))

            entries_panel.add_component(Label(text='\u2015' * 20, role='body', font_size=11))

            # Main content: no state_change, no active charter (shown at top already)
            _top_summary_id = top_summary.get('id') if top_summary else None
            _active_charter_id = _active_charter.get('id') if _active_charter else None
            content_entries = [e for e in entries
                               if (e.get('entry_type') or 'annotation') != 'state_change'
                               and e.get('id') != _top_summary_id
                               and e.get('id') != _active_charter_id]
            def _make_screening_handlers(eid, tid, iid, dec, rea, cbtn, obtn, rbtn, rfb, ep, ts):
                def _confirm(**kw):
                    rfb.text = 'Applying\u2026'
                    cbtn.enabled = obtn.enabled = rbtn.enabled = False
                    try:
                        with anvil.server.no_loading_indicator:
                            anvil.server.call('resolve_screening_uncertain', eid, tid, iid, dec, rea, 'confirm')
                        rfb.text = '\u2705 Confirmed'
                        self._load_thread_entries(tid, ep, ts)
                    except Exception as ex:
                        rfb.text = f'\u274c {ex}'
                        cbtn.enabled = obtn.enabled = rbtn.enabled = True
                def _override(**kw):
                    rfb.text = 'Applying\u2026'
                    cbtn.enabled = obtn.enabled = rbtn.enabled = False
                    try:
                        with anvil.server.no_loading_indicator:
                            anvil.server.call('resolve_screening_uncertain', eid, tid, iid, dec, rea, 'override')
                        rfb.text = '\u2705 Overridden'
                        self._load_thread_entries(tid, ep, ts)
                    except Exception as ex:
                        rfb.text = f'\u274c {ex}'
                        cbtn.enabled = obtn.enabled = rbtn.enabled = True
                def _reject(**kw):
                    rfb.text = 'Applying\u2026'
                    cbtn.enabled = obtn.enabled = rbtn.enabled = False
                    try:
                        with anvil.server.no_loading_indicator:
                            anvil.server.call('resolve_screening_uncertain', eid, tid, iid, dec, rea, 'reject')
                        rfb.text = '\u2705 Rejected'
                        self._load_thread_entries(tid, ep, ts)
                    except Exception as ex:
                        rfb.text = f'\u274c {ex}'
                        cbtn.enabled = obtn.enabled = rbtn.enabled = True
                cbtn.set_event_handler('click', _confirm)
                obtn.set_event_handler('click', _override)
                rbtn.set_event_handler('click', _reject)

            if content_entries:
                for e in content_entries:
                    entry_type = e.get('entry_type') or 'annotation'
                    icon = _ENTRY_ICONS.get(entry_type, '\u2022')
                    content = e.get('content') or ''
                    source = e.get('source') or ''
                    created = e.get('created_at') or ''
                    entry_id = e.get('id') or ''
                    metadata = e.get('metadata') or {}
                    row = FlowPanel(spacing_above='none', spacing_below='none')
                    row.add_component(Label(text=icon, role='body', font_size=13))

                    if entry_type == 'summary':
                        row.add_component(Label(text='  Standing summary', role='body', font_size=12, bold=True))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        entries_panel.add_component(Label(text=content, role='body', font_size=13))

                    elif entry_type == 'screening':
                        row.add_component(Label(text='  screening', role='body', font_size=12))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        entries_panel.add_component(Label(text=content, role='body', font_size=13))

                    elif entry_type == 'screening_uncertain':
                        row.add_component(Label(text='  screening (pending Bill review)', role='body', font_size=12))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        try:
                            import json as _jmod
                            decision_data = _jmod.loads(content)
                            item_id = decision_data.get('item_id', '')
                            decision = decision_data.get('decision', '')
                            reason = decision_data.get('reason', '')
                            entries_panel.add_component(Label(
                                text=f'Decision: {decision} \u2014 {reason}', role='body', font_size=13
                            ))
                        except Exception:
                            decision_data = {}
                            item_id = decision = reason = ''
                            entries_panel.add_component(Label(text=content[:300], role='body', font_size=13))
                        resolved = isinstance(metadata, dict) and metadata.get('resolved', False)
                        if resolved:
                            entries_panel.add_component(Label(
                                text=f'\u2705 Resolved: {metadata.get("resolution", "")}',
                                role='body', font_size=12
                            ))
                        elif item_id:
                            btn_row = FlowPanel(spacing_above='none', spacing_below='none')
                            confirm_btn = Button(text='Confirm', role='tonal-button')
                            override_btn = Button(text='Override', role='outlined-button')
                            reject_btn = Button(text='Reject', role='text-button')
                            res_fb = Label(text='', role='body', font_size=12)
                            btn_row.add_component(confirm_btn)
                            btn_row.add_component(override_btn)
                            btn_row.add_component(reject_btn)
                            btn_row.add_component(res_fb)
                            entries_panel.add_component(btn_row)
                            _make_screening_handlers(
                                entry_id, thread_id, item_id, decision, reason,
                                confirm_btn, override_btn, reject_btn, res_fb,
                                entries_panel, t_state,
                            )

                    elif entry_type == 'sub_question_candidate':
                        spawned = isinstance(metadata, dict) and metadata.get('spawned', False)
                        label = '  sub-question (spawned)' if spawned else '  sub-question candidate'
                        row.add_component(Label(text=label, role='body', font_size=12))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        entries_panel.add_component(Label(text=content, role='body', font_size=13))
                        if not spawned:
                            spawn_btn = Button(text='↗ Spawn as child thread', role='tonal-button', font_size=12)
                            spawn_fb = Label(text='', role='body', font_size=12)
                            spawn_row = FlowPanel(spacing_above='none', spacing_below='none')
                            spawn_row.add_component(spawn_btn)
                            spawn_row.add_component(spawn_fb)
                            entries_panel.add_component(spawn_row)
                            def _make_spawn(eid, tid):
                                def _spawn(**kw):
                                    spawn_fb.text = 'Spawning…'
                                    spawn_btn.enabled = False
                                    try:
                                        with anvil.server.no_loading_indicator:
                                            result = anvil.server.call(
                                                'spawn_thread_from_sub_question', tid, eid,
                                                ['Scope', 'Source Preferences', 'Time Bounds']
                                            )
                                        spawn_fb.text = f'✅ Thread created: {result.get("title","?")[:40]}'
                                        self._load_thread_entries(tid, entries_panel, t_state)
                                    except Exception as ex:
                                        spawn_fb.text = f'❌ {ex}'
                                        spawn_btn.enabled = True
                                return _spawn
                            spawn_btn.set_event_handler('click', _make_spawn(entry_id, thread_id))

                    elif entry_type == 'charter':
                        row.add_component(Label(text='  charter (superseded)', role='body', font_size=12))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        entries_panel.add_component(Label(text=content[:200] + '…', role='body', font_size=13))

                    elif entry_type == 'cycle_metadata':
                        meta_text = ''
                        if isinstance(metadata, dict):
                            verdict = metadata.get('grader_verdict', '')
                            cycle_n = metadata.get('cycle_number', '')
                            outcome = metadata.get('outcome', '')
                            meta_text = f'Cycle {cycle_n} · {outcome or verdict}'
                        row.add_component(Label(text=f'  research cycle  {meta_text}', role='body', font_size=12))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)

                    elif entry_type == 'memory_consultation':
                        row.add_component(Label(text='  🧠 What we already know', role='body', font_size=12, bold=True))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        entries_panel.add_component(Label(text=content[:600], role='body', font_size=13))

                    elif entry_type == 'finding':
                        meta_url = isinstance(metadata, dict) and metadata.get('url', '') or source or ''
                        meta_title = isinstance(metadata, dict) and metadata.get('title', '') or ''
                        relevance = isinstance(metadata, dict) and metadata.get('relevance_note', '') or ''
                        row.add_component(Label(text='  finding', role='body', font_size=12))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        if meta_title:
                            entries_panel.add_component(Label(text=meta_title, role='body', font_size=13, bold=True))
                        entries_panel.add_component(Label(text=content[:500], role='body', font_size=13))
                        if relevance:
                            entries_panel.add_component(Label(text=f'Why relevant: {relevance}', role='body', font_size=12))
                        if meta_url:
                            entries_panel.add_component(Label(text=meta_url, role='body', font_size=12))

                    elif entry_type == 'cycle_summary':
                        row.add_component(Label(text='  research cycle summary', role='body', font_size=12))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        entries_panel.add_component(Label(text=content[:400], role='body', font_size=13))

                    else:
                        display = content if len(content) <= 600 else content[:600] + ' [truncated]'
                        row.add_component(Label(text=f'  {entry_type}', role='body', font_size=12))
                        row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                        entries_panel.add_component(row)
                        entries_panel.add_component(Label(text=display, role='body', font_size=13))
                        if source:
                            entries_panel.add_component(Label(text=source, role='body', font_size=12))

                    entries_panel.add_component(Label(text='\u2015' * 15, role='body', font_size=11))
            else:
                entries_panel.add_component(Label(text='No content entries yet.', role='body', font_size=13))

            # Sub-questions section removed: schema does not yet model sub-questions.
            # Restore when sub_questions schema and spawn-thread button land.
            # See: claudis/anvil-redesign-principles-and-plan.md

            # History log toggle -- collapsed by default, shows state_change entries
            entries_panel.add_component(Label(text='\u2015' * 20, role='body', font_size=11))
            history_entries = [e for e in entries if (e.get('entry_type') or '') == 'state_change']
            hist_count = len(history_entries)
            hist_btn = Button(text=f'\u25b6 History ({hist_count})', role='text-button')
            entries_panel.add_component(hist_btn)

            hist_panel = ColumnPanel()
            hist_panel.visible = False
            for e in history_entries:
                icon = _ENTRY_ICONS.get('state_change', '\u2022')
                content = e.get('content') or ''
                if len(content) > 300:
                    content = content[:300] + ' [truncated]'
                created = e.get('created_at') or ''
                row = FlowPanel(spacing_above='none', spacing_below='none')
                row.add_component(Label(text=icon, role='body', font_size=13))
                row.add_component(Label(text='  state change', role='body', font_size=12))
                row.add_component(Label(text=f'  {_rel_time(created)}', role='body', font_size=12))
                hist_panel.add_component(row)
                hist_panel.add_component(Label(text=content, role='body', font_size=13))
            entries_panel.add_component(hist_panel)

            def _toggle_hist(**kw):
                hist_panel.visible = not hist_panel.visible
                hist_btn.text = (f'\u25bc History ({hist_count})' if hist_panel.visible
                                 else f'\u25b6 History ({hist_count})')
            hist_btn.set_event_handler('click', _toggle_hist)

            # Parent / children section (B-100)
            try:
                with anvil.server.no_loading_indicator:
                    family = anvil.server.call('get_thread_family', thread_id)
                parent_t = family.get('parent')
                children_t = family.get('children', [])
                if parent_t or children_t:
                    entries_panel.add_component(Label(text='\u2015' * 20, role='body', font_size=11))
                if parent_t:
                    entries_panel.add_component(Label(
                        text=f'\u2191 Parent: {parent_t.get("title","?")[:60]} [{parent_t.get("state","?")}]',
                        role='body', font_size=13
                    ))
                if children_t:
                    entries_panel.add_component(Label(text=f'\u2193 Child threads ({len(children_t)}):', role='body', font_size=13, bold=True))
                    for child in children_t:
                        c_row = FlowPanel(spacing_above='none', spacing_below='none')
                        c_row.add_component(Label(
                            text=f'  \u2022 {child.get("title","?")[:60]} [{child.get("state","?")}]',
                            role='body', font_size=13
                        ))
                        if child.get('state') == 'closed':
                            wb_btn = Button(text='\u2191 Write findings to parent', role='text-button', font_size=12)
                            def _make_wb(cid):
                                def _wb(**kw):
                                    try:
                                        with anvil.server.no_loading_indicator:
                                            anvil.server.call('write_child_findings_to_parent', cid)
                                        self._load_thread_entries(thread_id, entries_panel, t_state)
                                    except Exception as ex:
                                        alert(str(ex))
                                return _wb
                            wb_btn.set_event_handler('click', _make_wb(child['id']))
                            c_row.add_component(wb_btn)
                        entries_panel.add_component(c_row)
            except Exception:
                pass

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

        # ── Gather ────────────────────────────────────────────────────────────
        has_charter = bool(t_state[0].get('charter'))
        if has_charter and bound_agent and bound_has_webhook:
            gather_btn = Button(text='▶ Gather', role='filled-button')
            gather_fb = Label(text='', role='body', font_size=12)
            actions_panel.add_component(gather_btn)
            actions_panel.add_component(gather_fb)

            def _gather(**kw):
                gather_fb.text = 'Gathering…'
                gather_btn.enabled = False
                try:
                    with anvil.server.no_loading_indicator:
                        trigger_entry = anvil.server.call('trigger_thread_gather', thread_id)
                    trigger_time = (trigger_entry or {}).get('created_at', '')
                    gather_fb.text = '⏳ Gathering…'
                    self._load_thread_entries(thread_id, entries_panel, t_state)
                    _tick = [0]
                    tmr = Timer(interval=15)

                    def _on_tick(**kw):
                        _tick[0] += 1
                        try:
                            with anvil.server.no_loading_indicator:
                                entries = anvil.server.call('get_thread_entries', thread_id)
                            done = any(
                                e.get('entry_type') == 'cycle_summary'
                                and e.get('created_at', '') > trigger_time
                                for e in entries
                            )
                            if done or _tick[0] >= 8:
                                tmr.interval = 0
                                self._load_thread_entries(thread_id, entries_panel, t_state)
                                gather_fb.text = '✅ Cycle complete' if done else '⚠️ No summary yet — check entries'
                                gather_btn.enabled = True
                            else:
                                gather_fb.text = f'⏳ Gathering… ({_tick[0] * 15}s)'
                        except Exception:
                            tmr.interval = 0
                            gather_btn.enabled = True
                            gather_fb.text = '⚠️ Poll error'

                    tmr.set_event_handler('tick', _on_tick)
                    actions_panel.add_component(tmr)
                except Exception as e:
                    gather_fb.text = f'❌ {e}'
                    gather_btn.enabled = True
            gather_btn.set_event_handler('click', _gather)

        # ── Export ────────────────────────────────────────────────────────────
        export_btn = Button(text='⬇ Export thread', role='filled-button')
        export_fb = Label(text='', role='body', font_size=12)
        actions_panel.add_component(export_btn)
        actions_panel.add_component(export_fb)
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

        # ── Paste analysis ────────────────────────────────────────────────────
        actions_panel.add_component(Label(text='Paste analysis', role='body', font_size=13, bold=True))
        analysis_ta = TextArea(placeholder='Paste analysis from desktop Claude…', height=120)
        actions_panel.add_component(analysis_ta)
        analysis_ctrl_row = FlowPanel(spacing_above='none', spacing_below='none')
        analysis_btn = Button(text='Add as analysis entry', role='filled-button')
        analysis_fb = Label(text='', role='body', font_size=12)
        analysis_ctrl_row.add_component(analysis_btn)
        analysis_ctrl_row.add_component(analysis_fb)
        actions_panel.add_component(analysis_ctrl_row)

        def _add_analysis(**kw):
            import json as _jmod
            content = (analysis_ta.text or '').strip()
            if not content:
                analysis_fb.text = '⚠️ Empty'
                return
            analysis_fb.text = 'Extracting…'
            analysis_btn.enabled = False
            try:
                with anvil.server.no_loading_indicator:
                    result = anvil.server.call('extract_analysis', thread_id, content, 'desktop_claude')

                if result.get('error'):
                    with anvil.server.no_loading_indicator:
                        anvil.server.call('add_thread_entry', thread_id, 'analysis', content,
                                          source='desktop_claude', embed=True)
                    analysis_ta.text = ''
                    analysis_fb.text = f'Extraction failed: {result["error"]}; analysis saved as plain entry'
                    self._load_thread_entries(thread_id, entries_panel, t_state)
                    return

                # Full prose as 'analysis' entry
                with anvil.server.no_loading_indicator:
                    anvil.server.call('add_thread_entry', thread_id, 'analysis', content,
                                      source='desktop_claude', embed=True)

                # Conclusions as 'summary' entry
                conclusions = result.get('conclusions') or []
                if conclusions:
                    with anvil.server.no_loading_indicator:
                        anvil.server.call('add_thread_entry', thread_id, 'summary',
                                          '\n'.join(f'- {c}' for c in conclusions),
                                          source='desktop_claude', embed=True)

                # Screening decisions
                for item in (result.get('screening') or []):
                    item_id = item.get('item_id', '')
                    decision = item.get('decision', '')
                    reason = item.get('reason', '')
                    confidence = item.get('confidence', 'low')
                    if not item_id or not decision:
                        continue
                    if confidence == 'high':
                        rating = 1 if decision == 'kept' else -1
                        try:
                            with anvil.server.no_loading_indicator:
                                anvil.server.call('rate_research_article', item_id, rating)
                                anvil.server.call('set_research_article_status', item_id, 'reviewed')
                        except Exception:
                            pass
                        with anvil.server.no_loading_indicator:
                            anvil.server.call('add_thread_entry', thread_id, 'screening',
                                              f'{decision.title()}: {reason}',
                                              source='desktop_claude', embed=False)
                    else:
                        with anvil.server.no_loading_indicator:
                            anvil.server.call('add_thread_entry', thread_id, 'screening_uncertain',
                                              _jmod.dumps({'item_id': item_id, 'decision': decision,
                                                           'reason': reason}),
                                              source='desktop_claude', embed=False)

                # Sub-question candidates
                for sq in (result.get('sub_questions') or []):
                    question = sq.get('question', '')
                    if not question:
                        continue
                    pb = sq.get('prompted_by', '')
                    sq_text = f'{question}\n(prompted by: {pb})' if pb else question
                    with anvil.server.no_loading_indicator:
                        anvil.server.call('add_thread_entry', thread_id, 'sub_question_candidate',
                                          sq_text, source='desktop_claude', embed=True)

                analysis_ta.text = ''
                n_sc = len(result.get('screening') or [])
                n_sq = len(result.get('sub_questions') or [])
                analysis_fb.text = f'✅ Extracted: {n_sc} screening, {n_sq} questions'
                self._load_thread_entries(thread_id, entries_panel, t_state)
            except Exception as e:
                analysis_fb.text = f'❌ {e}'
            finally:
                analysis_btn.enabled = True
        analysis_btn.set_event_handler('click', _add_analysis)

        # ── Annotate (secondary) ──────────────────────────────────────────────
        actions_panel.add_component(Label(text='─' * 10, role='body', font_size=11))
        actions_panel.add_component(Label(text='Annotate', role='body', font_size=12))
        ann_ta = TextArea(placeholder='Annotation content…', height=80)
        actions_panel.add_component(ann_ta)
        ann_row = FlowPanel(spacing_above='none', spacing_below='none')
        ann_btn = Button(text='Add annotation', role='outlined-button')
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
                self._load_thread_entries(thread_id, entries_panel, t_state)
            except Exception as e:
                ann_fb.text = f'❌ {e}'
        ann_btn.set_event_handler('click', _annotate)

        # ── Watch state toggle (B-098) ────────────────────────────────────────
        actions_panel.add_component(Label(text='─' * 10, role='body', font_size=11))
        _watch_enabled = bool((t_state[0] if t_state else {}).get('watch_enabled', False))
        _watch_btn = Button(
            text='👁 Disable Watch' if _watch_enabled else '👁 Enable Watch',
            role='outlined-button'
        )
        _watch_interval_dd = DropDown(items=['daily', 'weekly', 'monthly'],
                                       selected_value='weekly', enabled=not _watch_enabled)
        _watch_fb = Label(text='', role='body', font_size=12)
        _watch_row = FlowPanel(spacing_above='none', spacing_below='none')
        _watch_row.add_component(_watch_btn)
        _watch_row.add_component(_watch_interval_dd)
        _watch_row.add_component(_watch_fb)
        actions_panel.add_component(_watch_row)

        def _toggle_watch(**kw):
            new_enabled = not _watch_enabled
            interval = _watch_interval_dd.selected_value or 'weekly'
            _watch_fb.text = 'Saving…'
            try:
                with anvil.server.no_loading_indicator:
                    anvil.server.call('set_watch_state', thread_id, new_enabled, interval)
                _watch_fb.text = f'✅ Watch {"enabled" if new_enabled else "disabled"}'
                self._build_thread_actions(thread_id, t_state, entries_panel, actions_panel, badge_lbl, meta_lbl)
            except Exception as e:
                _watch_fb.text = f'❌ {e}'
        _watch_btn.set_event_handler('click', _toggle_watch)

        # ── Charter (B-116) ───────────────────────────────────────────────────
        actions_panel.add_component(Label(text='─' * 10, role='body', font_size=11))
        _has_charter = bool((t_state[0] if t_state else {}).get('charter'))
        if _has_charter:
            actions_panel.add_component(Label(text='📜 Charter saved', role='body', font_size=13))
        else:
            charter_btn = Button(text='📜 Add charter', role='tonal-button')
            charter_fb = Label(text='', role='body', font_size=12)
            charter_hdr = FlowPanel(spacing_above='none', spacing_below='none')
            charter_hdr.add_component(charter_btn)
            charter_hdr.add_component(charter_fb)
            actions_panel.add_component(charter_hdr)

            charter_form = ColumnPanel()
            charter_form.visible = False

            charter_form.add_component(Label(text='Question', role='body', font_size=13, bold=True))
            cq_tb = TextBox(text=(t_state[0] if t_state else {}).get('question', '') or '')
            charter_form.add_component(cq_tb)

            charter_form.add_component(Label(text='Scope', role='body', font_size=13, bold=True))
            scope_ta = TextArea(placeholder='What is in/out of scope…', height=60)
            charter_form.add_component(scope_ta)

            charter_form.add_component(Label(text='Success Criteria', role='body', font_size=13, bold=True))
            sc_ta = TextArea(placeholder='When is this research done?', height=80)
            charter_form.add_component(sc_ta)

            charter_form.add_component(Label(text='Disqualifying Criteria', role='body', font_size=13, bold=True))
            dc_ta = TextArea(placeholder='What disqualifies a source or finding?', height=80)
            charter_form.add_component(dc_ta)

            charter_form.add_component(Label(text='Sub-Questions (one per line)', role='body', font_size=13, bold=True))
            sq_ta = TextArea(placeholder='One sub-question per line…', height=80)
            charter_form.add_component(sq_ta)

            charter_form.add_component(Label(text='Source Preferences', role='body', font_size=13, bold=True))
            sp_tb = TextBox(placeholder='e.g. arXiv, peer-reviewed journals…')
            charter_form.add_component(sp_tb)

            charter_form.add_component(Label(text='Recency Requirement (optional)', role='body', font_size=13, bold=True))
            rr_tb = TextBox(placeholder='e.g. last 2 years, since 2023…')
            charter_form.add_component(rr_tb)

            charter_ctrl = FlowPanel(spacing_above='none', spacing_below='none')
            charter_save_btn = Button(text='Save charter', role='filled-button')
            charter_cancel_btn = Button(text='Cancel', role='text-button')
            charter_ctrl.add_component(charter_save_btn)
            charter_ctrl.add_component(charter_cancel_btn)
            charter_form.add_component(charter_ctrl)

            actions_panel.add_component(charter_form)

            def _toggle_charter(**kw):
                charter_form.visible = not charter_form.visible
                charter_btn.text = '▼ Add charter' if charter_form.visible else '📜 Add charter'
            charter_btn.set_event_handler('click', _toggle_charter)

            def _cancel_charter(**kw):
                charter_form.visible = False
                charter_btn.text = '📜 Add charter'
            charter_cancel_btn.set_event_handler('click', _cancel_charter)

            def _save_charter(**kw):
                q = (cq_tb.text or '').strip()
                sc = (sc_ta.text or '').strip()
                if not q or not sc:
                    charter_fb.text = '⚠️ Question and Success Criteria required'
                    return
                charter_fb.text = 'Saving…'
                charter_save_btn.enabled = False
                try:
                    sq_lines = [ln.strip() for ln in (sq_ta.text or '').splitlines() if ln.strip()]
                    charter_d = {
                        'question': q,
                        'scope': (scope_ta.text or '').strip(),
                        'success_criteria': sc,
                        'disqualifying_criteria': (dc_ta.text or '').strip(),
                        'sub_questions': sq_lines,
                        'source_preferences': (sp_tb.text or '').strip(),
                        'recency_requirement': (rr_tb.text or '').strip(),
                    }
                    with anvil.server.no_loading_indicator:
                        result = anvil.server.call('save_charter', thread_id, charter_d)
                    auto_wire = result.pop('_auto_wire', None) if isinstance(result, dict) else None
                    t_state[0] = result
                    aw_status = (auto_wire or {}).get('status', '')
                    if aw_status == 'wired':
                        aw_agent = auto_wire.get('agent', '')
                        aw_pct = int(round(auto_wire.get('confidence', 0) * 100))
                        t_state[0]['bound_agent'] = aw_agent
                        charter_fb.text = f'✅ Charter saved · 🔗 Auto-wired {aw_agent} ({aw_pct}%)'
                    elif aw_status == 'build_request_queued':
                        charter_fb.text = '✅ Charter saved · No matching agent found — build request queued'
                    elif aw_status == 'already_wired':
                        charter_fb.text = f'✅ Charter saved · Agent already wired'
                    else:
                        charter_fb.text = '✅ Charter saved'
                    self._load_thread_entries(thread_id, entries_panel, t_state)
                    self._build_thread_actions(thread_id, t_state, entries_panel, actions_panel, badge_lbl, meta_lbl)
                except Exception as e:
                    charter_fb.text = f'❌ {e}'
                    charter_save_btn.enabled = True
            charter_save_btn.set_event_handler('click', _save_charter)

        # ── Thread settings drawer (state, agent) ─────────────────────────────
        actions_panel.add_component(Label(text='─' * 10, role='body', font_size=11))
        settings_btn = Button(text='▶ Thread settings (state, agent)', role='text-button')
        actions_panel.add_component(settings_btn)
        settings_panel = ColumnPanel()
        settings_panel.visible = False

        # State change
        settings_panel.add_component(Label(text='State', role='body', font_size=13, bold=True))
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
        settings_panel.add_component(state_row)

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
                self._load_thread_entries(thread_id, entries_panel, t_state)
            except Exception as e:
                state_fb.text = f'❌ {e}'
        state_upd_btn.set_event_handler('click', _update_state)

        # Wire agent
        settings_panel.add_component(Label(text='Wire agent', role='body', font_size=13, bold=True))
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
                        self._load_thread_entries(thread_id, entries_panel, t_state)
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
                    self._load_thread_entries(thread_id, entries_panel, t_state)
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
        settings_panel.add_component(wire_row)
        actions_panel.add_component(settings_panel)

        def _toggle_settings(**kw):
            settings_panel.visible = not settings_panel.visible
            settings_btn.text = (
                '▼ Thread settings (state, agent)' if settings_panel.visible
                else '▶ Thread settings (state, agent)'
            )
        settings_btn.set_event_handler('click', _toggle_settings)

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

            # Load comment-driven activity for indicators (B-114)
            try:
                cmt_activity = anvil.server.call('get_comment_driven_activity')
            except Exception:
                cmt_activity = {}

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
                    grp_body.add_component(self._build_agent_card(agent, cmt_activity))

        except Exception as e:
            self._agents_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=16))

    def _build_agent_card(self, agent, cmt_activity=None):
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

        # Comment-driven modification indicator (B-114)
        if cmt_activity and agent_name in cmt_activity:
            cmt_info = cmt_activity[agent_name]
            detail.add_component(Label(
                text=f'\u270f\ufe0f Modified {cmt_info.get("date", "?")} from comment \u2192 {cmt_info.get("card_id", "?")}',
                role='body', font_size=13, italic=True,
            ))

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

        comment_box = TextBox(placeholder='Comment', width=160)
        comment_btn = Button(text='Comment', role='outlined-button')

        def _submit_comment(a_name, lbl):
            def _f(**kw):
                content = (comment_box.text or '').strip()
                if not content:
                    return
                try:
                    anvil.server.call('submit_agent_feedback_v2', 'agent', a_name, content)
                    lbl.text = '\u2705 Saved'
                    comment_box.text = ''
                except Exception as ex:
                    lbl.text = f'\u274c {ex}'
            return _f

        comment_btn.set_event_handler('click', _submit_comment(agent_name, fb_label))
        action_row.add_component(comment_box)
        action_row.add_component(comment_btn)
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

        thread_btn = Button(text='Add to thread', role='outlined-button')
        action_row.add_component(thread_btn)

        card.add_component(action_row)
        card.add_component(fb_label)

        picker_panel = ColumnPanel()
        picker_panel.visible = False
        card.add_component(picker_panel)

        def _make_add_to_thread(aid, art, p_panel, lbl):
            def _h(**kw):
                if p_panel.visible:
                    p_panel.visible = False
                    return
                p_panel.clear()
                try:
                    with anvil.server.no_loading_indicator:
                        threads = anvil.server.call('get_threads', 'active')
                except Exception as ex:
                    p_panel.add_component(Label(text=f'❌ {ex}', role='body', font_size=12))
                    p_panel.visible = True
                    return
                if not threads:
                    p_panel.add_component(Label(
                        text='No active threads. Create one in the Threads tab first.',
                        role='body', font_size=12,
                    ))
                    p_panel.visible = True
                    return
                thread_titles = [t['title'] for t in threads]
                thread_dd = DropDown(items=thread_titles, selected_value=thread_titles[0])
                pick_btn = Button(text='Add', role='tonal-button')
                pick_row = FlowPanel(spacing_above='none', spacing_below='none')
                pick_row.add_component(thread_dd)
                pick_row.add_component(pick_btn)
                p_panel.add_component(pick_row)
                p_panel.visible = True

                def _make_pick(thr_list, t_dd, a_id, a_art, lbl_ref, pp):
                    def _pick(**kw):
                        chosen = next((t for t in thr_list if t['title'] == t_dd.selected_value), None)
                        if not chosen:
                            return
                        a_title = a_art.get('title') or '(no title)'
                        a_url = a_art.get('url') or ''
                        a_src = a_art.get('source') or ''
                        a_summ = (a_art.get('summary') or '')[:400]
                        a_rating = a_art.get('rating') or 0
                        a_comment = (a_art.get('comment') or '').strip()
                        parts = [a_title, a_url]
                        if a_src:
                            parts.append(f'Source: {a_src}')
                        if a_summ:
                            parts.append(a_summ)
                        if a_rating:
                            parts.append(f'Rating: {"+1" if a_rating == 1 else "-1"}')
                        if a_comment:
                            parts.append(f'Comment: {a_comment}')
                        content = '\n'.join(p for p in parts if p)
                        try:
                            with anvil.server.no_loading_indicator:
                                anvil.server.call('add_thread_entry', chosen['id'], 'gather',
                                                  content,
                                                  source=f'research_articles:{a_id}',
                                                  embed=True)
                            lbl_ref.text = f'✅ Added to {chosen["title"]}'
                            pp.visible = False
                        except Exception as ex:
                            lbl_ref.text = f'❌ {ex}'
                    return _pick

                pick_btn.set_event_handler('click', _make_pick(threads, thread_dd, aid, art, lbl, p_panel))
            return _h

        thread_btn.set_event_handler('click', _make_add_to_thread(article_id, article, picker_panel, fb_label))

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

    # ── Grader tab ────────────────────────────────────────────────────────────

    def _build_grader_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Grader Reviews', role='title', bold=True, font_size=20))
        ref_btn = Button(text='↻', role='text-button')
        ref_btn.set_event_handler('click', lambda **kw: self._reload_grader())
        hdr.add_component(ref_btn)
        # Filter buttons
        _filter_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._grader_filter = 'card'
        def _make_filter(ft):
            def _handler(**kw):
                self._grader_filter = ft
                self._reload_grader()
            return _handler
        for ft, lbl in [('card', 'Cards'), ('research_cycle', 'Research Cycles')]:
            fb = Button(text=lbl, role='tonal-button', font_size=13)
            fb.set_event_handler('click', _make_filter(ft))
            _filter_row.add_component(fb)
        hdr.add_component(_filter_row)
        self._grader_panel.add_component(hdr)
        self._grader_feedback = Label(text='', role='body', font_size=14)
        self._grader_panel.add_component(self._grader_feedback)
        self._grader_body = ColumnPanel()
        self._grader_panel.add_component(self._grader_body)

    def _reload_grader(self):
        self._grader_loaded = False
        self._grader_body.clear()
        self._load_grader_reviews()
        self._grader_loaded = True

    def _load_grader_reviews(self):
        self._grader_feedback.text = 'Loading…'
        review_type = getattr(self, '_grader_filter', 'card')
        try:
            with anvil.server.no_loading_indicator:
                reviews = anvil.server.call('get_grader_reviews_by_type', review_type, 30)
        except Exception as e:
            self._grader_feedback.text = f'❌ Error: {e}'
            return
        self._grader_body.clear()
        if not reviews:
            self._grader_feedback.text = 'No grader reviews yet.'
            return
        self._grader_feedback.text = f'{len(reviews)} reviews'
        verdict_icons = {'pass': '✅', 'pause': '⚠️', 'fail': '❌'}
        for rv in reviews:
            card = ColumnPanel(role='outlined-card')
            icon = verdict_icons.get(rv.get('verdict', ''), '❓')
            override = rv.get('bill_override') or ''
            reviewed = rv.get('reviewed_by_bill', False)
            hdr_row = FlowPanel(spacing_above='none', spacing_below='none')
            hdr_row.add_component(Label(
                text=f"{icon} {rv.get('card_id', '?')} — {rv.get('verdict', '?').upper()}",
                role='title', bold=True, font_size=16,
            ))
            if reviewed:
                hdr_row.add_component(Label(text=' ✓ Bill reviewed', role='body', font_size=13))
            card.add_component(hdr_row)
            ts = (rv.get('created_at') or '')[:16].replace('T', ' ')
            card.add_component(Label(text=f"Graded: {ts}", role='body', font_size=13))
            if rv.get('rationale'):
                card.add_component(Label(text=rv['rationale'], role='body', font_size=14))
            criteria = rv.get('criteria_results') or []
            if criteria:
                for c in criteria:
                    met = c.get('met', False)
                    badge = '✅' if met else '❌'
                    crit_text = f"{badge} {c.get('criterion', '')}"
                    ev = c.get('evidence', '')
                    card.add_component(Label(text=crit_text, role='body', font_size=13, bold=True))
                    if ev:
                        card.add_component(Label(text=f"  {ev}", role='body', font_size=13))
            if override:
                card.add_component(Label(text=f'\U0001f4dd Override: {override}', role='body', font_size=13))
            # Override action
            if not reviewed:
                override_row = FlowPanel(spacing_above='small', spacing_below='none')
                for ov in ('pass', 'pause', 'fail'):
                    btn = Button(text=f'Override → {ov}', role='tonal-button', font_size=12)
                    review_id = rv.get('id', '')
                    card_id_lbl = rv.get('card_id', '')
                    def _make_override_handler(rid, cid, v):
                        def handler(**kw):
                            reason = anvil.js.window.prompt(f'Reason for overriding {cid} to {v}?', '')
                            if reason is None:
                                return
                            try:
                                anvil.server.call('bill_override_grader_review', rid, v, reason)
                                self._reload_grader()
                            except Exception as ex:
                                alert(str(ex))
                        return handler
                    btn.set_event_handler('click', _make_override_handler(review_id, card_id_lbl, ov))
                    override_row.add_component(btn)
                card.add_component(override_row)

            # ── Copy for Opus button (B-102) ──────────────────────────────────
            export_row = FlowPanel(spacing_above='small', spacing_below='none')
            export_btn = Button(text='📋 Copy for Opus', role='text-button', font_size=12)
            export_fb = Label(text='', role='body', font_size=12)
            export_ta = TextArea(height=120, visible=False)
            export_row.add_component(export_btn)
            export_row.add_component(export_fb)
            card.add_component(export_row)
            card.add_component(export_ta)

            def _make_export_handler(rid):
                def _export(**kw):
                    export_fb.text = 'Fetching…'
                    export_btn.enabled = False
                    try:
                        with anvil.server.no_loading_indicator:
                            result = anvil.server.call('export_grader_review', rid)
                        md = result.get('markdown', '')
                        # Try clipboard, fall back to text area
                        try:
                            anvil.js.window.navigator.clipboard.writeText(md)
                            export_fb.text = '✅ Copied to clipboard'
                        except Exception:
                            export_ta.text = md
                            export_ta.visible = True
                            export_fb.text = '📋 Select-all and copy from the text area below'
                    except Exception as ex:
                        export_fb.text = f'❌ {ex}'
                    finally:
                        export_btn.enabled = True
                return _export
            export_btn.set_event_handler('click', _make_export_handler(review_id))

            self._grader_body.add_component(card)

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

    def _export_comment_work_clicked(self, **event_args):
        self._cmt_export_fb.text = 'Loading...'
        self._cmt_export_panel.visible = False
        try:
            result = anvil.server.call('export_comment_driven_results')
            markdown = result.get('markdown', '')
            count = result.get('count', 0)
            self._cmt_export_fb.text = f'{count} item(s) — copy from below'
            self._cmt_export_panel.clear()
            self._cmt_export_panel.add_component(TextArea(text=markdown, height=300, enabled=True))
            self._cmt_export_panel.visible = True
        except Exception as e:
            self._cmt_export_fb.text = f'❌ {e}'

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

    # ── Workspace tab (B-120) ─────────────────────────────────────────────────

    def _build_workspace_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text="Workspace", role='title', bold=True, font_size=20))
        self._workspace_export_btn = Button(text='⬇ Export working bundle', role='tonal-button')
        self._workspace_export_btn.set_event_handler('click', self._workspace_export_clicked)
        hdr.add_component(self._workspace_export_btn)
        self._workspace_audit_export_btn = Button(text='⬇ Export audit bundle', role='tonal-button')
        self._workspace_audit_export_btn.set_event_handler('click', self._workspace_audit_export_clicked)
        hdr.add_component(self._workspace_audit_export_btn)
        self._workspace_panel.add_component(hdr)

        self._workspace_export_fb = Label(text='', role='body', font_size=13)
        self._workspace_panel.add_component(self._workspace_export_fb)
        self._workspace_export_fallback = ColumnPanel()
        self._workspace_export_fallback.visible = False
        self._workspace_panel.add_component(self._workspace_export_fallback)

        self._workspace_audit_export_fb = Label(text='', role='body', font_size=13)
        self._workspace_panel.add_component(self._workspace_audit_export_fb)
        self._workspace_audit_export_fallback = ColumnPanel()
        self._workspace_audit_export_fallback.visible = False
        self._workspace_panel.add_component(self._workspace_audit_export_fallback)

        note_row = FlowPanel(spacing_above='small', spacing_below='none')
        self._workspace_note_input = TextArea(placeholder="What's on your mind?", height=80)
        self._workspace_add_btn = Button(text='Add note', role='filled-button')
        self._workspace_add_fb = Label(text='', role='body', font_size=13)
        self._workspace_add_btn.set_event_handler('click', self._workspace_add_note_clicked)
        note_row.add_component(self._workspace_note_input)
        note_row.add_component(self._workspace_add_btn)
        self._workspace_panel.add_component(note_row)
        self._workspace_panel.add_component(self._workspace_add_fb)

        self._workspace_panel.add_component(Label(text='Unaddressed notes:', role='body', bold=True, font_size=14))
        self._workspace_notes_panel = ColumnPanel()
        self._workspace_panel.add_component(self._workspace_notes_panel)

    def _load_workspace_notes(self):
        self._workspace_notes_panel.clear()
        try:
            with anvil.server.no_loading_indicator:
                notes = anvil.server.call('get_bill_notes')
        except Exception as e:
            self._workspace_notes_panel.add_component(Label(text=f'❌ {e}', role='body', font_size=13))
            return
        if not notes:
            self._workspace_notes_panel.add_component(Label(text='No unaddressed notes.', role='body', font_size=13))
            return
        for note in notes:
            self._workspace_notes_panel.add_component(self._make_note_row(note))

    def _make_note_row(self, note):
        row = FlowPanel(spacing_above='none', spacing_below='none')
        ts = (note.get('created_at') or '')[:10]
        row.add_component(Label(text=f"[{ts}] {note.get('content','')}", role='body', font_size=13))
        btn = Button(text='Mark addressed', role='outlined-button')
        note_id = note.get('id')
        def _mark(note_id=note_id, row=row, **kw):
            try:
                with anvil.server.no_loading_indicator:
                    anvil.server.call('mark_bill_note_addressed', note_id)
                row.visible = False
            except Exception as e:
                self._workspace_add_fb.text = f'❌ {e}'
        btn.set_event_handler('click', _mark)
        row.add_component(btn)
        return row

    def _workspace_add_note_clicked(self, **event_args):
        text = self._workspace_note_input.text or ''
        if not text.strip():
            self._workspace_add_fb.text = '❌ Note is empty.'
            return
        self._workspace_add_fb.text = 'Saving...'
        try:
            anvil.server.call('add_bill_note', text.strip())
            self._workspace_note_input.text = ''
            self._workspace_add_fb.text = '✅ Saved.'
            self._workspace_loaded = False
            self._load_workspace_notes()
            self._workspace_loaded = True
        except Exception as e:
            self._workspace_add_fb.text = f'❌ {e}'

    def _workspace_export_clicked(self, **event_args):
        self._run_export('get_working_bundle', self._workspace_export_fb, self._workspace_export_fallback)

    def _workspace_audit_export_clicked(self, **event_args):
        self._run_export('get_audit_bundle', self._workspace_audit_export_fb, self._workspace_audit_export_fallback)
