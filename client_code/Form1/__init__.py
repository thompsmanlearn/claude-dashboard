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
        self._grader_loaded = False
        self._home_active_agents = 0
        self._home_queue_pending = 0
        self._home_inbox_count = 0
        self._lean_poll_timer = None
        self._research_briefing_full = ''
        self._build_layout()
        self.refresh_data()

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _make_section(self, title, default_open=False, on_expand=None):
        """Return (outer_panel, body_panel, title_label) with collapsible header."""
        outer = ColumnPanel(role='outlined-card')
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        lbl = Label(text=title, role='title', bold=True, font_size=22)
        btn = Button(text=_EXPAND if default_open else _COLLAPSE, role='text-button')
        hdr.add_component(lbl)
        hdr.add_component(btn)
        outer.add_component(hdr)
        body = ColumnPanel()
        body.visible = default_open
        outer.add_component(body)
        _on_expand_called = [False]

        def _toggle(**kw):
            body.visible = not body.visible
            btn.text = _EXPAND if body.visible else _COLLAPSE
            if on_expand and body.visible and not _on_expand_called[0]:
                _on_expand_called[0] = True
                on_expand()

        btn.set_event_handler('click', _toggle)
        return outer, body, lbl

    def _build_layout(self):
        top = FlowPanel(spacing_above='none', spacing_below='small')
        top.add_component(Label(text='AADP', role='headline', bold=True))
        ref_btn = Button(text='Refresh', role='filled-button')
        ref_btn.set_event_handler('click', self._refresh_clicked)
        top.add_component(ref_btn)
        self.content_panel.add_component(top)

        # Tab navigation — four tabs
        tab_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._home_tab_btn = Button(text='Home', role='filled-button')
        self._workpad_tab_btn = Button(text='Workpad', role='tonal-button')
        self._system_tab_btn = Button(text='System', role='tonal-button')
        self._home_tab_btn.set_event_handler('click', self._show_home_tab)
        self._workpad_tab_btn.set_event_handler('click', self._show_workpad_tab)
        self._system_tab_btn.set_event_handler('click', self._show_system_tab)
        tab_row.add_component(self._home_tab_btn)
        tab_row.add_component(self._workpad_tab_btn)
        tab_row.add_component(self._system_tab_btn)
        self.content_panel.add_component(tab_row)

        # Home panel (default visible)
        self._home_panel = ColumnPanel()
        self._build_home_layout()
        self.content_panel.add_component(self._home_panel)

        # Workpad panel (hidden)
        self._workpad_panel = ColumnPanel()
        self._workpad_panel.visible = False
        self._build_workpad_layout()
        self.content_panel.add_component(self._workpad_panel)

        # System panel (hidden) — wraps Fleet, Memory, Lessons, Skills, Artifacts, Research, Grader
        self._system_panel = ColumnPanel()
        self._system_panel.visible = False
        self._build_system_layout()
        self.content_panel.add_component(self._system_panel)

    def _build_controls(self, panel):
        # Row 1: Lean trigger + Autonomous toggle (inline)
        ctrl_row = FlowPanel(spacing_above='none', spacing_below='none')
        self._lean_trigger_btn = Button(text='Trigger Lean Session', role='tonal-button')
        self._lean_trigger_btn.set_event_handler('click', self._trigger_lean_clicked)
        ctrl_row.add_component(self._lean_trigger_btn)
        self._lean_feedback = Label(text='', role='body', font_size=14)
        ctrl_row.add_component(self._lean_feedback)

        self._auto_btn = Button(text='\u23f3 Checking\u2026', role='tonal-button')
        self._auto_btn.set_event_handler('click', self._auto_mode_clicked)
        ctrl_row.add_component(self._auto_btn)
        refresh_auto_btn = Button(text='\u21bb', role='text-button')
        refresh_auto_btn.set_event_handler('click', lambda **kw: self._refresh_auto_status())
        ctrl_row.add_component(refresh_auto_btn)
        self._auto_feedback = Label(text='', role='body', font_size=14)
        ctrl_row.add_component(self._auto_feedback)
        panel.add_component(ctrl_row)

        # Row 2: Directive textarea + button
        dir_row = FlowPanel(spacing_above='none', spacing_below='none')
        dir_row.add_component(Label(text='Directive:', role='body', font_size=14))
        self._directive_input = TextArea(
            placeholder='e.g. "Run: B-032" or free text',
            role='outlined',
            height=60,
            width=480,
        )
        dir_row.add_component(self._directive_input)
        dir_btn = Button(text='Write', role='tonal-button')
        dir_btn.set_event_handler('click', self._write_directive_clicked)
        dir_row.add_component(dir_btn)
        self._directive_feedback = Label(text='', role='body', font_size=14)
        dir_row.add_component(self._directive_feedback)
        panel.add_component(dir_row)

    def _build_home_layout(self):
        # 1. Status strip
        strip = FlowPanel(spacing_above='small', spacing_below='small')
        self._home_health_lbl = Label(text='⏳', font_size=24, bold=True)
        self._home_agents_lbl = Label(text='—', font_size=24)
        self._home_queue_lbl = Label(text='—', font_size=24)
        self._home_inbox_badge = Label(text='—', font_size=24, bold=True)
        strip.add_component(self._home_health_lbl)
        strip.add_component(Label(text='  Agents: ', font_size=18))
        strip.add_component(self._home_agents_lbl)
        strip.add_component(Label(text='  Queue: ', font_size=18))
        strip.add_component(self._home_queue_lbl)
        strip.add_component(Label(text='  Inbox: ', font_size=18))
        strip.add_component(self._home_inbox_badge)
        self._home_panel.add_component(strip)

        # 2. Bill input panel
        self._home_panel.add_component(Label(text='Session Input', bold=True, role='body', font_size=16))
        self._bill_input_mode = ['Question']
        mode_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._bill_mode_q_btn = Button(text='Question', role='filled-button')
        self._bill_mode_c_btn = Button(text='Comment', role='tonal-button')
        self._bill_mode_cmd_btn = Button(text='Command', role='tonal-button')
        self._bill_mode_q_btn.set_event_handler('click', lambda **kw: self._bill_mode_select('Question'))
        self._bill_mode_c_btn.set_event_handler('click', lambda **kw: self._bill_mode_select('Comment'))
        self._bill_mode_cmd_btn.set_event_handler('click', lambda **kw: self._bill_mode_select('Command'))
        for b in [self._bill_mode_q_btn, self._bill_mode_c_btn, self._bill_mode_cmd_btn]:
            mode_row.add_component(b)
        self._home_panel.add_component(mode_row)
        self._bill_input_text = TextArea(placeholder='Type your question, comment, or command…', height=80, width=520)
        self._home_panel.add_component(self._bill_input_text)
        bill_submit_row = FlowPanel(spacing_above='small', spacing_below='none')
        self._bill_submit_btn = Button(text='Submit', role='filled-button')
        self._bill_submit_btn.set_event_handler('click', self._bill_submit_clicked)
        bill_submit_row.add_component(self._bill_submit_btn)
        self._bill_input_fb = Label(text='', role='body', font_size=14)
        bill_submit_row.add_component(self._bill_input_fb)
        self._home_panel.add_component(bill_submit_row)
        self._bill_response_lbl = Label(text='', role='body', font_size=14)
        self._bill_copy_btn = Button(text='Copy', role='outlined-button')
        self._bill_copy_btn.set_event_handler('click', self._bill_copy_response_clicked)
        bill_check_btn = Button(text='Get Output', role='tonal-button')
        bill_check_btn.set_event_handler('click', self._bill_check_response_clicked)
        self._home_panel.add_component(bill_check_btn)
        # Collapsible output panel — collapsed by default
        bill_output_hdr = FlowPanel(spacing_above='small', spacing_below='none')
        self._bill_output_toggle = Button(text='Session Output ▸', role='text-button')
        bill_output_hdr.add_component(self._bill_output_toggle)
        self._home_panel.add_component(bill_output_hdr)
        self._bill_output_body = ColumnPanel()
        self._bill_output_body.visible = False
        bill_copy_row = FlowPanel(spacing_above='none', spacing_below='none')
        bill_copy_row.add_component(self._bill_copy_btn)
        self._bill_output_body.add_component(bill_copy_row)
        self._bill_output_body.add_component(self._bill_response_lbl)
        self._home_panel.add_component(self._bill_output_body)

        def _toggle_bill_output(**kw):
            self._bill_output_body.visible = not self._bill_output_body.visible
            self._bill_output_toggle.text = 'Session Output ▾' if self._bill_output_body.visible else 'Session Output ▸'

        self._bill_output_toggle.set_event_handler('click', _toggle_bill_output)

        # 3. Primary action buttons — single horizontal row
        actions = FlowPanel(spacing_above='none', spacing_below='none')
        _write_dir_btn = Button(text='Write directive', role='tonal-button')
        self._home_export_working_btn = Button(text='⬇ Working', role='tonal-button')
        self._home_export_audit_btn = Button(text='⬇ Audit', role='tonal-button')
        self._home_export_desktop_btn = Button(text='⬇ Desktop', role='tonal-button')
        _write_dir_btn.set_event_handler('click', lambda **kw: setattr(self._directive_feedback, 'text', '↓ below'))
        self._home_export_working_btn.set_event_handler('click', self._home_export_working_clicked)
        self._home_export_audit_btn.set_event_handler('click', self._home_export_audit_clicked)
        self._home_export_desktop_btn.set_event_handler('click', self._home_export_desktop_clicked)
        for b in [_write_dir_btn, self._home_export_working_btn, self._home_export_audit_btn, self._home_export_desktop_btn]:
            actions.add_component(b)
        self._home_panel.add_component(actions)
        self._home_export_fb = Label(text='', role='body', font_size=14)
        self._home_export_fallback = ColumnPanel()
        self._home_export_fallback.visible = False
        self._home_panel.add_component(self._home_export_fb)
        self._home_panel.add_component(self._home_export_fallback)

        # 3. Compact controls: lean trigger + auto toggle + directive
        self._build_controls(self._home_panel)

        # Research Briefing (collapsible)
        rb_hdr = FlowPanel(spacing_above='small', spacing_below='none')
        self._research_toggle_btn = Button(text='▶', role='text-button')
        self._research_briefing_hdr_lbl = Label(text='Research Briefing — loading…', bold=True, role='body', font_size=16)
        self._synthesis_run_btn = Button(text='Run Synthesis', role='tonal-button')
        self._synthesis_run_btn.set_event_handler('click', self._run_synthesis_clicked)
        rb_hdr.add_component(self._research_toggle_btn)
        rb_hdr.add_component(self._research_briefing_hdr_lbl)
        rb_hdr.add_component(self._synthesis_run_btn)
        self._home_panel.add_component(rb_hdr)
        self._research_briefing_body = ColumnPanel()
        self._research_briefing_body.visible = False
        self._research_bullets_panel = ColumnPanel()
        self._rb_copy_btn = Button(text='Copy', role='outlined-button')
        self._rb_copy_btn.set_event_handler('click', self._copy_briefing_clicked)
        rb_copy_row = FlowPanel(spacing_above='none', spacing_below='small')
        rb_copy_row.add_component(self._rb_copy_btn)
        self._research_briefing_body.add_component(rb_copy_row)
        self._research_briefing_body.add_component(self._research_bullets_panel)
        self._home_panel.add_component(self._research_briefing_body)

        def _toggle_rb(**kw):
            self._research_briefing_body.visible = not self._research_briefing_body.visible
            self._research_toggle_btn.text = '▼' if self._research_briefing_body.visible else '▶'
        self._research_toggle_btn.set_event_handler('click', _toggle_rb)

        # 5. Pending inbox
        self._home_inbox_lbl = Label(text='Pending Inbox', bold=True, role='body', font_size=16)
        self._home_panel.add_component(self._home_inbox_lbl)
        self._home_inbox_body = ColumnPanel()
        self._home_panel.add_component(self._home_inbox_body)

    def _build_workpad_layout(self):
        self._wp_dirty = [False]
        self._wp_session_start_idx = 0   # entries before this index are "history"
        self._wp_show_history = False    # whether history panel is expanded

        # Input region
        self._workpad_panel.add_component(Label(text='Input', role='title', font_size=20))
        self._wp_input = TextArea(
            placeholder='Paste content, notes, or questions here…',
            height=180, font_size=16,
        )
        self._wp_input.set_event_handler('change', self._wp_input_changed)
        self._workpad_panel.add_component(self._wp_input)

        url_row = FlowPanel(spacing_above='small', spacing_below='small')
        url_row.add_component(Label(text='URL:', role='body', font_size=16))
        self._wp_url = TextBox(placeholder='https://…', font_size=16)
        self._wp_url.set_event_handler('change', self._wp_input_changed)
        url_row.add_component(self._wp_url)
        self._workpad_panel.add_component(url_row)

        # Actions region
        actions_row = FlowPanel(spacing_above='small', spacing_below='small')
        self._wp_search_btn = Button(text='Search', role='filled-button', enabled=False)
        self._wp_search_btn.set_event_handler('click', self._wp_search)
        self._wp_deep_research_btn = Button(text='Deep Research', role='tonal-button', enabled=False)
        self._wp_deep_research_btn.set_event_handler('click', self._wp_deep_research)
        self._wp_read_btn = Button(text='Read URL', role='filled-button')
        self._wp_read_btn.set_event_handler('click', self._wp_read_url)
        self._wp_copy_btn = Button(text='Copy All', role='tonal-button')
        self._wp_copy_btn.set_event_handler('click', self._wp_copy)
        self._wp_copy_gemini_btn = Button(text='Copy Gemini', role='outlined-button')
        self._wp_copy_gemini_btn.set_event_handler('click', lambda **kw: self._wp_copy(source='gemini'))
        self._wp_copy_tavily_btn = Button(text='Copy Tavily', role='outlined-button')
        self._wp_copy_tavily_btn.set_event_handler('click', lambda **kw: self._wp_copy(source='tavily'))
        self._wp_copy_brave_btn = Button(text='Copy Brave', role='outlined-button')
        self._wp_copy_brave_btn.set_event_handler('click', lambda **kw: self._wp_copy(source='brave'))
        self._wp_copy_github_btn = Button(text='Copy GitHub', role='outlined-button')
        self._wp_copy_github_btn.set_event_handler('click', lambda **kw: self._wp_copy(source='github'))
        self._wp_clear_btn = Button(text='Clear', role='outlined-button')
        self._wp_clear_btn.set_event_handler('click', self._wp_clear)
        for btn in [self._wp_search_btn, self._wp_deep_research_btn, self._wp_read_btn, self._wp_copy_btn,
                    self._wp_copy_gemini_btn, self._wp_copy_tavily_btn, self._wp_copy_brave_btn,
                    self._wp_copy_github_btn, self._wp_clear_btn]:
            actions_row.add_component(btn)
        self._workpad_panel.add_component(actions_row)

        self._wp_fb = Label(text='', role='body', font_size=14)
        self._workpad_panel.add_component(self._wp_fb)

        # Plan review panel — shown between pass 1 and pass 2
        self._wp_plan_card = ColumnPanel(visible=False)
        self._wp_plan_card.add_component(Label(
            text='📋 Pass 1 complete — review the research plan for Pass 2',
            role='title', font_size=16,
        ))
        self._wp_plan_label = Label(text='', role='body', font_size=13)
        self._wp_plan_card.add_component(self._wp_plan_label)
        self._wp_proceed_btn = Button(text='Proceed with Pass 2', role='filled-button')
        self._wp_proceed_btn.set_event_handler('click', self._wp_proceed_pass2)
        self._wp_plan_card.add_component(self._wp_proceed_btn)
        self._workpad_panel.add_component(self._wp_plan_card)
        self._wp_pending_job_id = None

        self._wp_copy_fallback = ColumnPanel()
        self._wp_copy_fallback.visible = False
        self._workpad_panel.add_component(self._wp_copy_fallback)


        # Output region — current session only
        self._workpad_panel.add_component(Label(text='Output', role='title', font_size=20))
        self._wp_output_panel = ColumnPanel()
        self._workpad_panel.add_component(self._wp_output_panel)

        # History toggle — shown only when prior entries exist
        self._wp_history_toggle_row = FlowPanel(spacing_above='small', spacing_below='none')
        self._wp_history_btn = Button(text='Show history', role='text-button', font_size=13)
        self._wp_history_btn.set_event_handler('click', self._wp_toggle_history)
        self._wp_history_toggle_row.add_component(self._wp_history_btn)
        self._wp_history_toggle_row.visible = False
        self._workpad_panel.add_component(self._wp_history_toggle_row)

        # History panel — hidden by default
        self._wp_history_panel = ColumnPanel()
        self._wp_history_panel.visible = False
        self._workpad_panel.add_component(self._wp_history_panel)

        # Auto-save: fires every 2s, saves only when dirty
        self._wp_save_timer = Timer(interval=2)
        self._wp_save_timer.set_event_handler('tick', self._wp_autosave)
        self._workpad_panel.add_component(self._wp_save_timer)

    def _build_fleet_inner(self, panel):
        fleet_hdr = FlowPanel(spacing_above='small', spacing_below='small')
        self._fleet_export_btn = Button(text='⬇ Export fleet', role='tonal-button')
        self._fleet_export_btn.set_event_handler('click', self._fleet_export_clicked)
        fleet_hdr.add_component(self._fleet_export_btn)
        self._cmt_export_btn = Button(text='✏️ Comment work', role='outlined-button')
        self._cmt_export_fb = Label(text='', role='body', font_size=13)
        self._cmt_export_btn.set_event_handler('click', self._export_comment_work_clicked)
        fleet_hdr.add_component(self._cmt_export_btn)
        panel.add_component(fleet_hdr)
        self._cmt_export_panel = ColumnPanel()
        self._cmt_export_panel.visible = False
        panel.add_component(self._cmt_export_panel)
        panel.add_component(self._cmt_export_fb)
        self._fleet_export_fb = Label(text='', role='body', font_size=14)
        panel.add_component(self._fleet_export_fb)
        self._fleet_export_panel = ColumnPanel()
        self._fleet_export_panel.visible = False
        panel.add_component(self._fleet_export_panel)
        sec, self._status_body, _ = self._make_section('System Status', default_open=True)
        panel.add_component(sec)
        sec, self._agents_body, self._agents_lbl = self._make_section('Agent Fleet')
        panel.add_component(sec)
        sec, self._queue_body, self._queue_lbl = self._make_section('Work Queue')
        panel.add_component(sec)

    def _build_system_layout(self):
        # Fleet
        fleet_sec, fleet_body, _ = self._make_section('Fleet')
        self._build_fleet_inner(fleet_body)
        self._system_panel.add_component(fleet_sec)

        # Memory
        self._memory_panel = ColumnPanel()
        self._build_memory_layout()
        mem_sec, mem_body, _ = self._make_section('Memory', on_expand=self._lazy_load_memory)
        mem_body.add_component(self._memory_panel)
        self._system_panel.add_component(mem_sec)

        # Lessons
        self._lessons_panel = ColumnPanel()
        self._build_lessons_layout()
        lessons_sec, lessons_body, _ = self._make_section('Lessons', on_expand=self._lazy_load_lessons)
        lessons_body.add_component(self._lessons_panel)
        self._system_panel.add_component(lessons_sec)

        # Skills
        self._skills_panel = ColumnPanel()
        self._build_skills_layout()
        skills_sec, skills_body, _ = self._make_section('Skills', on_expand=self._lazy_load_skills)
        skills_body.add_component(self._skills_panel)
        self._system_panel.add_component(skills_sec)

        # Artifacts
        self._artifacts_panel = ColumnPanel()
        self._build_artifacts_layout()
        artifacts_sec, artifacts_body, _ = self._make_section('Artifacts', on_expand=self._lazy_load_artifacts)
        artifacts_body.add_component(self._artifacts_panel)
        self._system_panel.add_component(artifacts_sec)

        # Research
        self._research_panel = ColumnPanel()
        self._build_research_layout()
        research_sec, research_body, _ = self._make_section('Research', on_expand=self._lazy_load_research)
        research_body.add_component(self._research_panel)
        self._system_panel.add_component(research_sec)

        # Grader
        self._grader_panel = ColumnPanel()
        self._build_grader_layout()
        grader_sec, grader_body, _ = self._make_section('Grader', on_expand=self._lazy_load_grader)
        grader_body.add_component(self._grader_panel)
        self._system_panel.add_component(grader_sec)

        # Sessions export
        sessions_sec, sessions_body, _ = self._make_section('Sessions')
        sessions_body.add_component(Label(
            text='Export copies recent session artifacts to clipboard for Desktop Claude.',
            role='body', font_size=13,
        ))
        self._sessions_export_btn = Button(text='⬇ Export Sessions', role='tonal-button')
        self._sessions_export_btn.set_event_handler('click', self._sessions_export_clicked)
        sessions_body.add_component(self._sessions_export_btn)
        self._sessions_export_fb = Label(text='', role='body', font_size=14)
        sessions_body.add_component(self._sessions_export_fb)
        self._sessions_export_panel = ColumnPanel()
        self._sessions_export_panel.visible = False
        sessions_body.add_component(self._sessions_export_panel)
        self._system_panel.add_component(sessions_sec)

        # Site regeneration
        site_sec, site_body, _ = self._make_section('Site')
        regen_row = FlowPanel(spacing_above='none', spacing_below='small')
        self._regen_btn = Button(text='Regenerate Site', role='tonal-button')
        self._regen_btn.set_event_handler('click', self._regenerate_site_clicked)
        regen_row.add_component(self._regen_btn)
        site_body.add_component(regen_row)
        self._regen_feedback = Label(text='', role='body', font_size=14)
        site_body.add_component(self._regen_feedback)
        self._system_panel.add_component(site_sec)

    def _lazy_load_memory(self):
        if not self._memory_loaded:
            self._load_memory_collections()
            self._memory_loaded = True

    def _lazy_load_lessons(self):
        if not self._lessons_loaded:
            self._load_lessons('recent')
            self._lessons_loaded = True

    def _lazy_load_skills(self):
        if not self._skills_loaded:
            self._load_skills()
            self._skills_loaded = True

    def _lazy_load_artifacts(self):
        if not self._artifacts_loaded:
            self._load_artifacts()
            self._artifacts_loaded = True

    def _lazy_load_research(self):
        if not self._research_loaded:
            self._load_research_tab()
            self._research_loaded = True

    def _lazy_load_grader(self):
        if not self._grader_loaded:
            self._load_grader_reviews()
            self._grader_loaded = True

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
            'home': self._home_panel,
            'workpad': self._workpad_panel,
            'system': self._system_panel,
        }
        btns = {
            'home': self._home_tab_btn,
            'workpad': self._workpad_tab_btn,
            'system': self._system_tab_btn,
        }
        for name, panel in panels.items():
            panel.visible = (name == active)
        for name, btn in btns.items():
            btn.role = 'filled-button' if name == active else 'tonal-button'

    def _show_home_tab(self, **event_args):
        self._set_tab('home')

    def _show_workpad_tab(self, **event_args):
        self._set_tab('workpad')
        if not getattr(self, '_workpad_loaded', False):
            self._workpad_loaded = True
            self._wp_load_state()

    def _show_system_tab(self, **event_args):
        self._set_tab('system')

    def refresh_data(self):
        self._load_status()
        self._load_agents()
        self._load_queue()
        self._load_inbox()
        self._refresh_lean_status()
        self._refresh_auto_status()
        self._update_home_status_strip()
        self._load_research_briefing()

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
                self._status_body.add_component(Label(text=row, role='body', font_size=18))
        except Exception as e:
            self._status_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=18))

    def _load_agents(self):
        self._agent_card_panels = []
        self._agents_body.clear()

        # Search bar
        search_row = FlowPanel(spacing_above='none', spacing_below='small')
        search_row.add_component(Label(text='\U0001f50d ', role='body', font_size=18))
        self._search_box = TextBox(placeholder='Filter by name\u2026', width=220)
        self._search_box.set_event_handler('change', self._filter_agents)
        search_row.add_component(self._search_box)
        self._agents_body.add_component(search_row)

        try:
            agents = anvil.server.call('get_agent_fleet')
            self._agents_lbl.text = f'Agent Fleet ({len(agents)})'
            self._home_active_agents = sum(1 for a in agents if a.get('status') == 'active')

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
                    Label(text=f'{icon} {status.capitalize()} ({len(group_agents)})', bold=True, role='body', font_size=18)
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
            self._agents_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=18))

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
        compact.add_component(Label(text=f'{icon} {display_name}{prot_mark}', role='body', font_size=18))
        expand_btn = Button(text='+', role='text-button')
        compact.add_component(expand_btn)
        card.add_component(compact)

        # Detail panel (tap to reveal)
        detail = ColumnPanel()
        detail.visible = False
        card.add_component(detail)

        card.add_component(Label(text='\u2500' * 25, role='body', font_size=18))

        # Populate detail
        if description:
            preview = description[:120] + ('\u2026' if len(description) > 120 else '')
            detail.add_component(Label(text=preview, role='body', font_size=18))
        meta = f'Schedule: {schedule}'
        if updated_at:
            meta += f'  |  Updated: {updated_at}'
        detail.add_component(Label(text=meta, role='body', font_size=18))

        # Comment-driven modification indicator (B-114)
        if cmt_activity and agent_name in cmt_activity:
            cmt_info = cmt_activity[agent_name]
            detail.add_component(Label(
                text=f'\u270f\ufe0f Modified {cmt_info.get("date", "?")} from comment \u2192 {cmt_info.get("card_id", "?")}',
                role='body', font_size=13, italic=True,
            ))

        fb_label = Label(text='', role='body', font_size=18)
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
            self._home_queue_pending = pending
            self._queue_lbl.text = f'Work Queue \u2014 {pending} pending, {claimed} claimed'
            if not tasks:
                self._queue_body.add_component(Label(text='Queue is empty', role='body', font_size=18))
                return
            for t in tasks[:20]:
                self._queue_body.add_component(self._build_queue_card(t))
        except Exception as e:
            self._queue_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=18))

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
        compact.add_component(Label(text=f'{icon} {task_type}  (p:{priority})', role='body', font_size=18))
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
        self._home_inbox_body.clear()
        try:
            items = anvil.server.call('get_inbox')
            self._home_inbox_count = len(items)
            self._home_inbox_lbl.text = f'Pending Inbox \u2014 {len(items)} pending'
            if not items:
                self._home_inbox_body.add_component(Label(text='Inbox is clear.', role='body', font_size=18))
                return
            for item in items:
                self._render_inbox_item(item)
        except Exception as e:
            self._home_inbox_body.add_component(Label(text=f'Unavailable: {e}', role='body', font_size=18))

    def _render_inbox_item(self, item):
        item_id = item['id']
        self._home_inbox_body.add_component(Label(text='\u2015' * 20, role='body', font_size=18))
        self._home_inbox_body.add_component(Label(text=item['subject'], bold=True, role='body', font_size=18))
        self._home_inbox_body.add_component(
            Label(text=f"From: {item['from_agent']}  |  Priority: {item.get('priority', 'normal')}", role='body', font_size=18)
        )
        body_text = item.get('body') or ''
        preview = body_text[:200] + ('\u2026' if len(body_text) > 200 else '')
        self._home_inbox_body.add_component(Label(text=preview, role='body', font_size=18))
        fb_label = Label(text='', role='body', font_size=18)
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
        self._home_inbox_body.add_component(btn_row)
        self._home_inbox_body.add_component(fb_label)

    # ── Lessons tab ───────────────────────────────────────────────────────────

    def _build_lessons_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Lessons', role='title', bold=True, font_size=22))
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
        self._lessons_body.add_component(Label(text='Loading\u2026', role='body', font_size=18))
        try:
            if filter == 'search':
                query = (self._lessons_search_box.text or '').strip()
                if not query:
                    self._lessons_body.clear()
                    self._lessons_body.add_component(Label(text='Enter a search query above.', role='body', font_size=18))
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
                self._lessons_body.add_component(Label(text='No lessons found.', role='body', font_size=18))
                return
            self._lessons_body.add_component(Label(text=f'{len(lessons)} lesson(s)', role='body', font_size=14))
            for lesson in lessons:
                self._lessons_body.add_component(self._build_lesson_card(lesson, is_search=(filter == 'search')))
        except Exception as e:
            self._lessons_body.clear()
            self._lessons_body.add_component(Label(text=f'Error: {e}', role='body', font_size=18))

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
        card.add_component(Label(text=title, bold=True, role='body', font_size=18))
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
        hdr.add_component(Label(text='Memory', role='title', bold=True, font_size=22))
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
        self._memory_panel.add_component(Label(text='\u2015' * 20, role='body', font_size=18))
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
        self._mem_colls_body.add_component(Label(text='Loading collections\u2026', role='body', font_size=18))
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
            self._mem_colls_body.add_component(Label(text=f'Error: {e}', role='body', font_size=18))

    def _load_collection_docs(self, offset):
        self._mem_docs_body.clear()
        self._mem_docs_body.add_component(
            Label(text=f'Loading {self._memory_selected_coll}\u2026', role='body', font_size=18)
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
            self._mem_docs_body.add_component(Label(text=f'Error: {e}', role='body', font_size=18))

    def _do_collection_search(self):
        if not self._memory_selected_coll:
            return
        query = (self._mem_search_box.text or '').strip()
        if not query:
            self._load_collection_docs(0)
            return
        self._mem_docs_body.clear()
        self._mem_docs_body.add_component(Label(text='Searching\u2026', role='body', font_size=18))
        try:
            with anvil.server.no_loading_indicator:
                results = anvil.server.call('search_collection', self._memory_selected_coll, query)
            self._mem_docs_body.clear()
            if not results:
                self._mem_docs_body.add_component(Label(text='No results.', role='body', font_size=18))
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
            self._mem_docs_body.add_component(Label(text=f'Error: {e}', role='body', font_size=18))

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
        self._mem_supabase_body.add_component(Label(text=f'Loading {table}\u2026', role='body', font_size=18))
        try:
            with anvil.server.no_loading_indicator:
                rows = anvil.server.call('get_table_rows', table)
            self._mem_supabase_body.clear()
            self._mem_supabase_body.add_component(
                Label(text=f'{table} — {len(rows)} row(s)', bold=True, role='body', font_size=14)
            )
            if not rows:
                self._mem_supabase_body.add_component(Label(text='No rows.', role='body', font_size=18))
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
            self._mem_supabase_body.add_component(Label(text=f'Error: {e}', role='body', font_size=18))

    # ── Research tab ─────────────────────────────────────────────────────────

    def _build_research_layout(self):
        hdr = FlowPanel(spacing_above='small', spacing_below='small')
        hdr.add_component(Label(text='Research', role='title', bold=True, font_size=22))
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

        self._research_panel.add_component(Label(text='―' * 20, role='body', font_size=18))

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

        self._research_panel.add_component(Label(text='―' * 20, role='body', font_size=18))
        fb_hist_hdr = FlowPanel(spacing_above='small', spacing_below='small')
        fb_hist_hdr.add_component(Label(text='Feedback History', bold=True, role='body', font_size=18))
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
            Label(text='Loading articles…', role='body', font_size=18)
        )
        try:
            with anvil.server.no_loading_indicator:
                articles = anvil.server.call('get_research_articles', 50)
            self._research_articles = articles
            self._render_research_articles(articles)
        except Exception as e:
            self._research_articles_body.clear()
            self._research_articles_body.add_component(
                Label(text=f'Error: {e}', role='body', font_size=18)
            )
        self._load_feedback_threads()

    def _render_research_articles(self, articles):
        self._research_articles_body.clear()
        if not articles:
            self._research_articles_body.add_component(
                Label(text='No articles yet. Press "▶ Run research" to fetch some.', role='body', font_size=18)
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
        hdr.add_component(Label(text='Artifacts', role='title', bold=True, font_size=22))
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
        self._artifacts_body.add_component(Label(text='Loading\u2026', role='body', font_size=18))
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
            self._artifacts_body.add_component(Label(text=f'Error: {e}', role='body', font_size=18))

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
        hdr.add_component(Label(text='Grader Reviews', role='title', bold=True, font_size=22))
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
                role='title', bold=True, font_size=18,
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
        hdr.add_component(Label(text='Skills', role='title', bold=True, font_size=22))
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
        self._skills_body.add_component(Label(text='Loading\u2026', role='body', font_size=18))
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
            self._skills_body.add_component(Label(text=f'Error: {e}', role='body', font_size=18))

    def _build_skill_card(self, skill):
        name = skill.get('name', '')
        description = skill.get('description') or '\u2014'
        keywords = skill.get('trigger_keywords') or []
        times_loaded = skill.get('times_loaded') or 0
        last_loaded = (skill.get('last_loaded') or '')[:10] or 'never'

        card = ColumnPanel(role='outlined-card')
        card.add_component(Label(text=name, bold=True, role='body', font_size=18))
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
            hdr.add_component(Label(text=result['name'], bold=True, role='body', font_size=18))
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
        if self._lean_poll_timer is not None:
            self._lean_poll_timer.interval = 0
            self._lean_poll_timer = None
        try:
            result = anvil.server.call('trigger_lean_session')
            self._lean_feedback.text = result.get('message', str(result))
        except Exception as e:
            self._lean_feedback.text = f'\u274c Error: {e}'
            self._refresh_lean_status()
            return
        _tick = [0]
        _terminal = {'complete', 'error', 'timeout'}
        tmr = Timer(interval=10)
        self._lean_poll_timer = tmr

        def _on_lean_tick(**kw):
            _tick[0] += 1
            try:
                with anvil.server.no_loading_indicator:
                    status = anvil.server.call('get_session_status')
                if status is None:
                    if _tick[0] >= 3:
                        tmr.interval = 0
                        self._lean_feedback.text = 'Idle'
                        self._refresh_lean_status()
                    return
                phase = status.get('phase') or 'unknown'
                action = status.get('current_action') or ''
                self._lean_feedback.text = f'{phase.upper()}{" \u2014 " + action if action else ""}'
                if phase in _terminal:
                    tmr.interval = 0
                    self._refresh_lean_status()
            except Exception:
                pass

        tmr.set_event_handler('tick', _on_lean_tick)
        self._home_panel.add_component(tmr)
        self._refresh_lean_status()

    def _load_research_briefing(self):
        try:
            with anvil.server.no_loading_indicator:
                b = anvil.server.call('get_latest_briefing')
            if b is None:
                self._research_briefing_hdr_lbl.text = 'Research Briefing — no briefings yet'
                self._research_bullets_panel.clear()
                self._research_briefing_full = ''
            else:
                ts = (b.get('created_at') or '')[:16].replace('T', ' ')
                count = b.get('paper_count') or 0
                self._research_briefing_hdr_lbl.text = f'Research Briefing — {ts} | {count} papers'
                self._research_briefing_full = b.get('briefing') or ''
                display = b.get('briefing_short') or self._research_briefing_full
                _markers = {'EXECUTIVE_BRIEFING', 'END_EXECUTIVE_BRIEFING'}
                self._research_bullets_panel.clear()
                for line in display.split('\n'):
                    line = line.strip()
                    if line and line not in _markers:
                        self._research_bullets_panel.add_component(
                            Label(text=line, role='body', font_size=14)
                        )
        except Exception as e:
            self._research_briefing_hdr_lbl.text = f'Research Briefing — unavailable: {e}'

    def _run_synthesis_clicked(self, **event_args):
        self._synthesis_run_btn.text = 'Running...'
        self._synthesis_run_btn.enabled = False
        try:
            result = anvil.server.call('run_research_synthesis')
            if result.get('status') == 'no_papers':
                self._synthesis_run_btn.text = '⚠️ No papers'
            else:
                self._synthesis_run_btn.text = '✅ Done'
                self._load_research_briefing()
                self._research_briefing_body.visible = True
                self._research_toggle_btn.text = '▼'
        except Exception:
            self._synthesis_run_btn.text = '❌ Failed'
        tmr = Timer(interval=2)
        _btn = self._synthesis_run_btn
        def _reset(**kw):
            tmr.interval = 0
            _btn.text = 'Run Synthesis'
            _btn.enabled = True
        tmr.set_event_handler('tick', _reset)
        self._home_panel.add_component(tmr)

    def _copy_briefing_clicked(self, **event_args):
        text = self._research_briefing_full or ''
        try:
            anvil.js.window.navigator.clipboard.writeText(text)
            self._rb_copy_btn.text = '✅ Copied'
            tmr = Timer(interval=2)
            def _reset(**kw):
                tmr.interval = 0
                self._rb_copy_btn.text = 'Copy'
            tmr.set_event_handler('tick', _reset)
            self._research_briefing_body.add_component(tmr)
        except Exception:
            pass

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
        except Exception as e:
            self._regen_feedback.text = f'❌ Error: {e}'
        self._regen_btn.enabled = True

    def _refresh_clicked(self, **event_args):
        self.refresh_data()

    # ── Home tab helpers ──────────────────────────────────────────────────────

    def _home_export_working_clicked(self, **event_args):
        self._run_export('get_working_bundle', self._home_export_fb, self._home_export_fallback)

    def _home_export_audit_clicked(self, **event_args):
        self._run_export('get_audit_bundle', self._home_export_fb, self._home_export_fallback)

    def _home_export_desktop_clicked(self, **event_args):
        self._run_export('get_desktop_bundle', self._home_export_fb, self._home_export_fallback)

    def _bill_mode_select(self, mode):
        self._bill_input_mode[0] = mode
        self._bill_mode_q_btn.role = 'filled-button' if mode == 'Question' else 'tonal-button'
        self._bill_mode_c_btn.role = 'filled-button' if mode == 'Comment' else 'tonal-button'
        self._bill_mode_cmd_btn.role = 'filled-button' if mode == 'Command' else 'tonal-button'

    def _bill_submit_clicked(self, **event_args):
        text = (self._bill_input_text.text or '').strip()
        if not text:
            self._bill_input_fb.text = 'Enter text before submitting.'
            return
        mode = self._bill_input_mode[0]
        try:
            anvil.server.call('submit_bill_input', mode, text)
        except Exception as e:
            self._bill_input_fb.text = f'❌ {e}'
            return
        self._bill_input_text.text = ''
        self._bill_input_fb.text = '✅ Submitted. Press Get Output after session runs.'

    def _bill_check_response_clicked(self, **event_args):
        try:
            result = anvil.server.call('get_bill_input_response')
        except Exception as e:
            self._bill_response_lbl.text = f'❌ {e}'
            return
        status = result.get('status', 'none')
        if status == 'none':
            self._bill_response_lbl.text = 'No output on file.'
        elif status == 'pending':
            self._bill_response_lbl.text = '⏳ Still processing…'
        else:
            text = result.get('response') or '(no response written)'
            self._bill_response_lbl.text = text
            self._bill_output_body.visible = True
            self._bill_output_toggle.text = 'Session Output ▾'
            try:
                anvil.js.window.navigator.clipboard.writeText(text)
                self._bill_copy_btn.text = '✅ Copied'
            except Exception:
                self._bill_copy_btn.text = 'Copy'

    def _bill_copy_response_clicked(self, **event_args):
        text = self._bill_response_lbl.text or ''
        if not text:
            return
        try:
            anvil.js.window.navigator.clipboard.writeText(text)
            self._bill_copy_btn.text = '✅ Copied'
        except Exception:
            self._bill_copy_btn.text = 'Copy (failed)'

    def _update_home_status_strip(self):
        n_agents = self._home_active_agents
        n_queue = self._home_queue_pending
        n_inbox = self._home_inbox_count
        self._home_health_lbl.text = '🟢' if n_inbox == 0 else '🟡'
        self._home_agents_lbl.text = str(n_agents)
        self._home_queue_lbl.text = str(n_queue)
        self._home_inbox_badge.text = f'⚠️ {n_inbox}' if n_inbox > 0 else '0'

    # ── Workpad tab ───────────────────────────────────────────────────────────

    def _wp_input_changed(self, **event_args):
        self._wp_dirty[0] = True
        has_input = bool((self._wp_input.text or '').strip())
        self._wp_search_btn.enabled = has_input
        self._wp_deep_research_btn.enabled = has_input

    def _wp_autosave(self, **event_args):
        if self._wp_dirty[0]:
            self._wp_dirty[0] = False
            try:
                with anvil.server.no_loading_indicator:
                    anvil.server.call('save_workpad_input', self._wp_input.text or '', self._wp_url.text or '')
            except Exception:
                pass

    def _wp_do_save(self):
        self._wp_dirty[0] = False
        try:
            with anvil.server.no_loading_indicator:
                anvil.server.call('save_workpad_input', self._wp_input.text or '', self._wp_url.text or '')
        except Exception:
            pass

    def _wp_load_state(self):
        try:
            state = anvil.server.call('get_workpad_state')
            self._wp_input.text = state.get('input_text', '')
            self._wp_url.text = state.get('attach_url', '')
            has_input = bool((self._wp_input.text or '').strip())
            self._wp_search_btn.enabled = has_input
            self._wp_deep_research_btn.enabled = has_input
            entries = state.get('output_entries', [])
            # Everything already in Supabase at load time is "history" for this session
            self._wp_session_start_idx = len(entries)
            self._wp_render_output(entries)
        except Exception as e:
            self._wp_fb.text = f'❌ Load failed: {e}'

    def _wp_render_output(self, entries):
        self._wp_entries = entries  # full list — _wp_copy uses session slice

        session_start = getattr(self, '_wp_session_start_idx', 0)
        history_entries = entries[:session_start]
        current_entries = entries[session_start:]

        # ── Current session output panel ─────────────────────────────────────
        self._wp_output_panel.clear()
        if not current_entries:
            self._wp_output_panel.add_component(
                Label(text='No results this session.', role='body', font_size=14)
            )
        # entries to render in main panel = current session only (reversed = newest first)
        render_entries = current_entries

        # ── History toggle button ─────────────────────────────────────────────
        if history_entries:
            n = len(history_entries)
            if getattr(self, '_wp_show_history', False):
                self._wp_history_btn.text = f'Hide history ({n})'
            else:
                self._wp_history_btn.text = f'Show history ({n} older results)'
            self._wp_history_toggle_row.visible = True
        else:
            self._wp_history_toggle_row.visible = False

        # ── History panel (visible only when toggled) ─────────────────────────
        self._wp_history_panel.clear()
        if getattr(self, '_wp_show_history', False) and history_entries:
            self._wp_history_panel.add_component(
                Label(text='— Earlier results —', role='body', font_size=12, italic=True)
            )
            render_history = history_entries  # will be rendered below after setup

        if not current_entries and not getattr(self, '_wp_show_history', False):
            return  # nothing to render in either panel

        # ── Shared rendering helper (renders entry list into a target panel) ──

        def _make_url_setter(u):
            def _set(**kw):
                self._wp_url.text = u
            return _set

        def _make_expand(e_btn, f_lbl):
            def _toggle(**kw):
                f_lbl.visible = not f_lbl.visible
                e_btn.text = 'Show less' if f_lbl.visible else 'Show more'
            return _toggle

        def _render_result_list(parent, results, source_label):
            """Render a list of {url,title,snippet,source_domain} results under a source header."""
            if not results:
                parent.add_component(Label(text=f'{source_label}: no results.', role='body', font_size=13))
                return
            parent.add_component(Label(text=source_label, role='body', font_size=13, bold=True))
            for res in results:
                title = res.get('title', '') or res.get('url', '')
                url = res.get('url', '')
                domain = res.get('source_domain', '')
                snippet = res.get('snippet', '')
                pub = res.get('published_date', '')
                score = res.get('score')
                row = ColumnPanel()
                title_btn = Button(text=title or url, role='tonal-button', font_size=14)
                title_btn.set_event_handler('click', _make_url_setter(url))
                row.add_component(title_btn)
                meta_parts = []
                if domain:
                    meta_parts.append(domain)
                if pub:
                    meta_parts.append(pub)
                if score is not None:
                    meta_parts.append(f'score {score}')
                if meta_parts:
                    row.add_component(Label(text=' · '.join(meta_parts), role='body', font_size=12))
                if snippet:
                    snip = snippet[:200] + ('…' if len(snippet) > 200 else '')
                    row.add_component(Label(text=snip, role='body', font_size=14))
                parent.add_component(row)

        def _render_entries(target_panel, entry_list):
          for entry in reversed(entry_list):
            action = entry.get('action', '')
            ts = entry.get('timestamp', '')
            card = ColumnPanel()
            if action == 'search_all':
                query_text = entry.get('query', '')
                errors = entry.get('errors', {})
                card.add_component(Label(
                    text=f'🔍 {_rel_time(ts)} — {query_text[:80]}',
                    role='body', font_size=13, bold=True,
                ))
                if errors:
                    card.add_component(Label(
                        text='⚠️ Errors: ' + ', '.join(f'{k}: {v[:60]}' for k, v in errors.items()),
                        role='body', font_size=12,
                    ))
                # Gemini synthesis section
                gemini = entry.get('gemini', {})
                g_answer = gemini.get('answer', '')
                card.add_component(Label(text='🤖 Gemini synthesis', role='body', font_size=13, bold=True))
                if g_answer:
                    trunc = g_answer[:800] + ('…' if len(g_answer) > 800 else '')
                    g_lbl = Label(text=trunc, role='body', font_size=14)
                    card.add_component(g_lbl)
                    if len(g_answer) > 800:
                        g_full = Label(text=g_answer, role='body', font_size=14, visible=False)
                        g_btn = Button(text='Show more', role='tonal-button', font_size=12)
                        card.add_component(g_full)
                        g_btn.set_event_handler('click', _make_expand(g_btn, g_full))
                        card.add_component(g_btn)
                else:
                    reason = gemini.get('error_reason', '') or 'not_called'
                    card.add_component(Label(
                        text=f'Gemini: no synthesis — {reason}',
                        role='body', font_size=13,
                    ))
                # Tavily section
                tavily = entry.get('tavily', {})
                t_answer = tavily.get('answer', '')
                if t_answer:
                    card.add_component(Label(text='🟢 Tavily answer', role='body', font_size=13, bold=True))
                    card.add_component(Label(text=t_answer[:400] + ('…' if len(t_answer) > 400 else ''),
                                             role='body', font_size=14))
                _render_result_list(card, tavily.get('results', []), '🟢 Tavily results')
                # Brave section
                _render_result_list(card, entry.get('brave', []), '🔵 Brave results')
                # GitHub repos section
                github_repos = entry.get('github', [])
                if github_repos:
                    card.add_component(Label(text='⚫ GitHub repos', role='body', font_size=13, bold=True))
                    for repo in github_repos:
                        r_row = ColumnPanel()
                        stars = repo.get('stars', 0)
                        lang = repo.get('language', '')
                        meta = f'⭐{stars}'
                        if lang:
                            meta += f' · {lang}'
                        pushed = repo.get('pushed_at', '')
                        if pushed:
                            meta += f' · pushed {pushed}'
                        repo_btn = Button(
                            text=f"{repo.get('name', '')} ({meta})",
                            role='tonal-button', font_size=14,
                        )
                        repo_btn.set_event_handler('click', _make_url_setter(repo.get('url', '')))
                        r_row.add_component(repo_btn)
                        desc = repo.get('description', '')
                        if desc:
                            r_row.add_component(Label(text=desc[:180], role='body', font_size=13))
                        topics = repo.get('topics', [])
                        if topics:
                            r_row.add_component(Label(text=' '.join(f'#{t}' for t in topics),
                                                       role='body', font_size=12))
                        card.add_component(r_row)
            elif action == 'deep_research':
                query_text = entry.get('query', '')
                artifact = entry.get('artifact_content', '')
                card.add_component(Label(
                    text=f'🔬 Deep Research {_rel_time(ts)} — {query_text[:60]}',
                    role='body', font_size=13, bold=True,
                ))
                if artifact:
                    trunc = artifact[:1000] + ('…' if len(artifact) > 1000 else '')
                    trunc_lbl = Label(text=trunc, role='body', font_size=13)
                    card.add_component(trunc_lbl)
                    if len(artifact) > 1000:
                        full_lbl = Label(text=artifact, role='body', font_size=13, visible=False)
                        exp_btn = Button(text='Show full artifact', role='tonal-button', font_size=12)
                        card.add_component(full_lbl)
                        exp_btn.set_event_handler('click', _make_expand(exp_btn, full_lbl))
                        card.add_component(exp_btn)
                else:
                    card.add_component(Label(text='(no artifact content)', role='body', font_size=13))
            elif action == 'search':
                query_text = entry.get('query', '')
                results = entry.get('results', [])
                card.add_component(Label(
                    text=f'🔍 {_rel_time(ts)} — {query_text[:80]}',
                    role='body', font_size=13, bold=True,
                ))
                _render_result_list(card, results, '🔵 Brave')
            else:
                result = entry.get('result', '')
                card.add_component(Label(
                    text=f'{_rel_time(ts)} — {action}',
                    role='body', font_size=13, bold=True,
                ))
                truncated = result[:600] + ('…' if len(result) > 600 else '')
                body_lbl = Label(text=truncated, role='body', font_size=14)
                card.add_component(body_lbl)
                if len(result) > 600:
                    full_lbl = Label(text=result, role='body', font_size=14, visible=False)
                    expand_btn = Button(text='Show more', role='tonal-button', font_size=12)
                    card.add_component(full_lbl)
                    expand_btn.set_event_handler('click', _make_expand(expand_btn, full_lbl))
                    card.add_component(expand_btn)
            target_panel.add_component(card)

        # Render current session entries into main output panel
        if current_entries:
            _render_entries(self._wp_output_panel, current_entries)

        # Render history entries into history panel (if toggled open)
        if getattr(self, '_wp_show_history', False) and history_entries:
            _render_entries(self._wp_history_panel, history_entries)
            self._wp_history_panel.visible = True
        else:
            self._wp_history_panel.visible = False

    def _wp_toggle_history(self, **event_args):
        self._wp_show_history = not getattr(self, '_wp_show_history', False)
        self._wp_render_output(getattr(self, '_wp_entries', []))

    def _wp_search(self, **event_args):
        self._wp_do_save()
        query = (self._wp_input.text or '').strip()
        if not query:
            self._wp_fb.text = '❌ Nothing to search.'
            return
        self._wp_fb.text = 'Searching Brave, Tavily, GitHub, Gemini…'
        self._wp_search_btn.enabled = False
        try:
            anvil.server.call('search_all', query, 10)
            state = anvil.server.call('get_workpad_state')
            self._wp_render_output(state.get('output_entries', []))
            self._wp_fb.text = '✅ Search complete.'
        except Exception as e:
            self._wp_fb.text = f'❌ {e}'
        finally:
            self._wp_search_btn.enabled = bool(query)

    def _wp_deep_research(self, **event_args):
        import time as _time
        self._wp_do_save()
        query = (self._wp_input.text or '').strip()
        if not query:
            self._wp_fb.text = '❌ Nothing to research.'
            return
        self._wp_fb.text = '🔬 Starting deep research…'
        self._wp_deep_research_btn.enabled = False
        self._wp_search_btn.enabled = False
        try:
            with anvil.server.no_loading_indicator:
                resp = anvil.server.call('run_deep_research', query)
            job_id = resp.get('job_id', '')
            if not job_id:
                raise Exception('No job_id returned')
            # Phase 1: poll until awaiting_review, done, or error
            for attempt in range(36):
                _time.sleep(5)
                self._wp_fb.text = f'🔬 Pass 1 running… ({(attempt + 1) * 5}s)'
                with anvil.server.no_loading_indicator:
                    status = anvil.server.call('get_deep_research_status', job_id)
                s = status.get('status')
                if s == 'awaiting_review':
                    self._wp_show_plan(job_id, status.get('plan', {}))
                    return  # Proceed button resumes from here
                elif s == 'done':
                    self._wp_finish_deep_research(status)
                    return
                elif s == 'error':
                    self._wp_fb.text = f'❌ Deep research failed: {status.get("error", "unknown")}'
                    return
            self._wp_fb.text = '⚠️ Deep research timed out — check server logs.'
        except Exception as e:
            self._wp_fb.text = f'❌ {e}'
        finally:
            has_input = bool((self._wp_input.text or '').strip())
            self._wp_deep_research_btn.enabled = has_input
            self._wp_search_btn.enabled = has_input

    def _wp_show_plan(self, job_id, plan):
        """Display the pass-1 plan for review."""
        self._wp_pending_job_id = job_id
        gaps = plan.get('gaps', [])
        counts = plan.get('pass1_source_counts', {})
        total_p1 = sum(counts.values())
        clusters = plan.get('cluster_count', '?')
        lines = [f'Pass 1: {total_p1} results across {clusters} clusters\n']
        for g in gaps:
            srcs = ', '.join(g.get('sources') or [])
            gap_type = g.get('type', '?')
            priority = g.get('priority', '?')
            lines.append(f'[{gap_type} / {priority}]  {g.get("gap", "")}')
            lines.append(f'    → {srcs}\n')
        self._wp_plan_label.text = '\n'.join(lines)
        self._wp_plan_card.visible = True
        self._wp_fb.text = '⏸ Review the plan below, then click Proceed to run Pass 2.'

    def _wp_proceed_pass2(self, **event_args):
        """User approved the plan — resume pass 2."""
        import time as _time
        job_id = self._wp_pending_job_id
        if not job_id:
            return
        self._wp_plan_card.visible = False
        self._wp_fb.text = '🔬 Pass 2 running…'
        self._wp_deep_research_btn.enabled = False
        self._wp_search_btn.enabled = False
        try:
            with anvil.server.no_loading_indicator:
                anvil.server.call('approve_deep_research_plan', job_id)
            for attempt in range(36):
                _time.sleep(5)
                self._wp_fb.text = f'🔬 Pass 2 running… ({(attempt + 1) * 5}s)'
                with anvil.server.no_loading_indicator:
                    status = anvil.server.call('get_deep_research_status', job_id)
                s = status.get('status')
                if s == 'done':
                    self._wp_finish_deep_research(status)
                    return
                elif s == 'error':
                    self._wp_fb.text = f'❌ Pass 2 failed: {status.get("error", "unknown")}'
                    return
            self._wp_fb.text = '⚠️ Pass 2 timed out — check server logs.'
        except Exception as e:
            self._wp_fb.text = f'❌ {e}'
        finally:
            has_input = bool((self._wp_input.text or '').strip())
            self._wp_deep_research_btn.enabled = has_input
            self._wp_search_btn.enabled = has_input
            self._wp_pending_job_id = None

    def _wp_finish_deep_research(self, status):
        """Reload workpad output and show completion message."""
        with anvil.server.no_loading_indicator:
            state = anvil.server.call('get_workpad_state')
        self._wp_render_output(state.get('output_entries', []))
        runtime = (status.get('result') or {}).get('runtime_s', '?')
        self._wp_fb.text = f'✅ Deep research complete ({runtime}s). Artifact written.'

    def _wp_read_url(self, **event_args):
        self._wp_do_save()
        url = (self._wp_url.text or '').strip()
        if not url:
            self._wp_fb.text = '❌ No URL entered.'
            return
        self._wp_fb.text = 'Fetching…'
        self._wp_read_btn.enabled = False
        try:
            anvil.server.call('fetch_url_content', url)
            state = anvil.server.call('get_workpad_state')
            self._wp_render_output(state.get('output_entries', []))
            self._wp_fb.text = '✅ Fetched.'
        except Exception as e:
            self._wp_fb.text = f'❌ {e}'
        finally:
            self._wp_read_btn.enabled = True

    def _wp_copy(self, source=None, **event_args):
        """Copy workpad content formatted for Desktop Claude AI analysis.
        source=None copies all; source='gemini'/'tavily'/'brave' filters to that engine only.
        """
        self._wp_do_save()
        parts = []
        input_text = (self._wp_input.text or '').strip()
        if input_text and source is None:
            parts.append(input_text)

        # Track seen URLs across entries for deduplication
        seen_urls = set()

        def _age_flag(pub_date):
            """Return [DATED] if pub_date suggests > 12 months old."""
            if not pub_date:
                return ''
            try:
                import re as _re
                year = int(_re.search(r'(20\d\d)', pub_date).group(1))
                import datetime as _dt
                if _dt.date.today().year - year >= 1 and pub_date < str(_dt.date.today().year):
                    return ' [DATED]'
            except Exception:
                pass
            return ''

        def _fmt_source_line(res, already_seen):
            title = (res.get('title', '') or res.get('url', '')).strip()
            url = (res.get('url', '') or '').strip()
            snippet = (res.get('snippet', '') or '').strip()
            pub = res.get('published_date', '')
            flag = _age_flag(pub)
            if url in already_seen:
                return f'• {title} {url} [see above]{flag}'
            already_seen.add(url)
            sentence = (snippet[:200] + '…' if len(snippet) > 200 else snippet)
            return f'• {title} | {url}{flag} — {sentence}'

        def _word_count(text):
            return len(text.split())

        # Copy only current session entries (history excluded unless explicitly shown)
        all_entries = getattr(self, '_wp_entries', [])
        session_start = getattr(self, '_wp_session_start_idx', 0)
        copy_entries = all_entries[session_start:]  # current session only

        for entry in reversed(copy_entries):
            action = entry.get('action', '')
            query = entry.get('query', '')

            if action == 'search_all':
                entry_seen = set(seen_urls)  # per-entry dedup; updates seen_urls at end
                block_lines = [f'QUERY: {query}']
                word_budget = 1500

                if source in (None, 'gemini'):
                    g_answer = (entry.get('gemini', {}).get('answer', '') or '').strip()
                    if g_answer:
                        # Strip markdown: remove **, *, ##, etc.
                        import re as _re2
                        plain = _re2.sub(r'\*+|#+\s?|`+', '', g_answer).strip()
                        # Trim to fit budget
                        words = plain.split()
                        plain = ' '.join(words[:300]) + ('…' if len(words) > 300 else '')
                        block_lines.append(f'GEMINI SYNTHESIS: {plain}')

                if source in (None, 'tavily'):
                    tavily = entry.get('tavily', {})
                    t_answer = (tavily.get('answer', '') or '').strip()
                    t_results = tavily.get('results', [])
                    if t_answer:
                        words = t_answer.split()
                        short = ' '.join(words[:100]) + ('…' if len(words) > 100 else '')
                        block_lines.append(f'TAVILY SUMMARY: {short}')
                    if t_results:
                        src_lines = [_fmt_source_line(r, entry_seen) for r in t_results]
                        block_lines.append('TAVILY SOURCES:\n' + '\n'.join(src_lines))

                if source in (None, 'brave'):
                    brave = entry.get('brave', [])
                    if brave:
                        src_lines = [_fmt_source_line(r, entry_seen) for r in brave]
                        block_lines.append('BRAVE SOURCES:\n' + '\n'.join(src_lines))

                if source in (None, 'github'):
                    github = entry.get('github', [])
                    if github:
                        import re as _re3
                        gh_lines = []
                        for repo in github:
                            name = repo.get('name', '')
                            url = repo.get('url', '')
                            stars = repo.get('stars', 0)
                            lang = repo.get('language', '')
                            pushed = repo.get('pushed_at', '')
                            desc = repo.get('description', '')
                            flag = _age_flag(pushed)
                            meta = f'⭐{stars}'
                            if lang:
                                meta += f', {lang}'
                            if url in entry_seen:
                                gh_lines.append(f'• {name} ({meta}) | {url} [see above]{flag}')
                            else:
                                entry_seen.add(url)
                                snippet = desc[:100] + ('…' if len(desc) > 100 else '')
                                gh_lines.append(f'• {name} ({meta}) | {url}{flag} — {snippet}')
                        block_lines.append('GITHUB REPOS:\n' + '\n'.join(gh_lines))

                seen_urls.update(entry_seen)
                # If filtering by a specific source and nothing was found, skip this entry
                if source is not None and len(block_lines) == 1:
                    continue  # only QUERY: line — no results for this source
                block = '\n\n'.join(block_lines)
                # Hard trim to ~800 words
                words = block.split()
                if len(words) > word_budget:
                    block = ' '.join(words[:word_budget]) + '\n[truncated to 800 words]'
                parts.append(block)

            elif action == 'search' and source in (None, 'brave'):
                # Legacy single-engine entry
                results = entry.get('results', [])
                lines = [f'QUERY: {query}', 'BRAVE SOURCES:']
                for r in results:
                    lines.append(_fmt_source_line(r, seen_urls))
                parts.append('\n'.join(lines))

            elif action == 'deep_research' and source is None:
                artifact = (entry.get('artifact_content', '') or '').strip()
                q_text = entry.get('query', '')
                if artifact:
                    # Strip Query Expansion section — pipeline internals, not useful for Desktop Claude
                    import re as _re_dr
                    stripped = _re_dr.sub(
                        r'## Query Expansion.*?(?=## Pass One Findings)',
                        '',
                        artifact,
                        flags=_re_dr.DOTALL,
                    ).strip()
                    parts.append(f'DEEP RESEARCH: {q_text}\n\n{stripped}')

            elif action not in ('search', 'search_all', 'deep_research') and source is None:
                # URL fetch — already stripped by uplink; trim to 150 words
                result = (entry.get('result', '') or '').strip()
                url = entry.get('url', '') or action
                if result:
                    words = result.split()
                    trimmed = ' '.join(words[:150]) + ('…' if len(words) > 150 else '')
                    parts.append(f'URL FETCHES:\n{url}\n{trimmed}')

        label = {'gemini': 'Gemini', 'tavily': 'Tavily', 'brave': 'Brave', 'github': 'GitHub'}.get(source, 'All')
        text = '\n\n---\n\n'.join(parts) if parts else ''
        self._wp_copy_fallback.visible = False
        if not text:
            self._wp_fb.text = f'ℹ️ No {label} results in this session to copy.'
            return
        copied = False
        try:
            anvil.js.window.navigator.clipboard.writeText(text)
            copied = True
        except Exception:
            pass
        if copied:
            self._wp_fb.text = f'✅ {label} copied to clipboard.'
        else:
            self._wp_fb.text = f'📋 Clipboard unavailable — {label} text below:'
            self._wp_copy_fallback.clear()
            self._wp_copy_fallback.add_component(TextArea(text=text, height=120, enabled=True))
            self._wp_copy_fallback.visible = True

    def _wp_clear(self, **event_args):
        if not anvil.js.window.confirm('Clear all workpad content?'):
            return
        self._wp_fb.text = 'Clearing…'
        try:
            anvil.server.call('clear_workpad')
            self._wp_input.text = ''
            self._wp_url.text = ''
            self._wp_dirty[0] = False
            self._wp_copy_fallback.visible = False
            self._wp_session_start_idx = 0   # nothing left is "history"
            self._wp_show_history = False
            self._wp_render_output([])
            self._wp_fb.text = '✅ Cleared.'
        except Exception as e:
            self._wp_fb.text = f'❌ {e}'

