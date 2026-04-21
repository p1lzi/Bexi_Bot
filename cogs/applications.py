import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
from utils import (
    t, td, tp, load_config, save_config, now_timestamp,
    make_dm_embed, send_dm, _load_default_application,
    _make_role_select_view, _make_channel_select_view,
    save_open_app, delete_open_app
)
from state import (
    _setup_wizard_state, _wizard_interactions, pending_applications,
    QUESTIONS_PER_STEP, QUESTION_SECTIONS, DEFAULT_APPLICATION_QUESTIONS
)

def get_application_steps(questions: list) -> list:
    steps = []
    for i in range(0, len(questions), QUESTIONS_PER_STEP):
        steps.append(questions[i:i + QUESTIONS_PER_STEP])
    return steps

def _section_for_index(idx: int) -> str:
    result = "📋  Application"
    for sec_idx in sorted(QUESTION_SECTIONS.keys()):
        if idx >= sec_idx:
            result = QUESTION_SECTIONS[sec_idx]
    return result

def build_review_embeds(guild, applicant, answers, panel_title, questions) -> list:
    BLURPLE = discord.Color.from_rgb(88, 101, 242)
    header = discord.Embed(color=BLURPLE, timestamp=now_timestamp())
    header.set_author(name=t("embeds", "application", "review_author", title=panel_title), icon_url=applicant.display_avatar.url)
    joined_str = discord.utils.format_dt(applicant.joined_at, style="R") if applicant.joined_at else "—"
    header.description = "\n".join([
        t("embeds", "application", "review_applicant") + f" {applicant.mention}  `{applicant.id}`",
        t("embeds", "application", "review_account")   + f" {discord.utils.format_dt(applicant.created_at, style='R')}",
        t("embeds", "application", "review_joined")    + " " + joined_str,
        t("embeds", "application", "review_submitted") + f" {discord.utils.format_dt(now_timestamp(), style='f')}",
    ])
    header.set_thumbnail(url=applicant.display_avatar.url)
    footer_text = guild.name + "  •  " + t("embeds", "application", "footer")
    if guild.icon: header.set_footer(text=footer_text, icon_url=guild.icon.url)
    else: header.set_footer(text=footer_text)
    embeds = [header]
    current_section, current_embed, field_count = None, None, 0
    for i, (label, value) in enumerate(answers):
        matched_q = next((q for q in questions if q["label"] == label), None)
        global_idx = questions.index(matched_q) if matched_q else i
        sec_raw = matched_q.get("section") if matched_q else None
        if sec_raw:
            sec_name = sec_raw.get("name", "") if isinstance(sec_raw, dict) else str(sec_raw)
            sec_desc = sec_raw.get("desc", "") if isinstance(sec_raw, dict) else ""
            section  = sec_name or _section_for_index(global_idx)
        else:
            section  = _section_for_index(global_idx)
            sec_desc = ""
        if section != current_section or current_embed is None or field_count >= 5:
            sec_title = section if section != current_section else None
            new_emb = discord.Embed(title=sec_title, color=BLURPLE)
            if sec_title and sec_desc: new_emb.description = "*" + sec_desc + "*"
            embeds.append(new_emb)
            current_embed, current_section, field_count = new_emb, section, 0
        display_value = ("```" + value[:950] + "```") if len(value) > 80 else (value[:1024] or "*— —*")
        current_embed.add_field(name=label, value=display_value, inline=False)
        field_count += 1
    return embeds

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

class ApplicationDecisionModal(discord.ui.Modal):
    def __init__(self, applicant_id: int, decision: str, reviewer, guild, thread_id: int = None):
        title_keys = {"accept": "app_accept_title", "decline": "app_decline_title", "question": "app_question_title"}
        super().__init__(title=t("modals", title_keys.get(decision, "app_decline_title")))
        self.applicant_id, self.decision, self.reviewer, self.guild, self.thread_id = applicant_id, decision, reviewer, guild, thread_id
        self.note = discord.ui.TextInput(label=t("modals", "app_decision_label"), placeholder=t("modals", "app_decision_placeholder"), style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        colors = {"accept": discord.Color.green(), "decline": discord.Color.red(), "question": discord.Color.blurple()}
        emojis = {"accept": "✅", "decline": "❌", "question": "❓"}
        color = colors[self.decision]
        success_key = "application_accepted" if self.decision == "accept" else ("application_declined" if self.decision == "decline" else "application_questioned")
        await interaction.response.send_message(t("success", success_key, mention="<@" + str(self.applicant_id) + ">"), ephemeral=True)
        thread = None
        if self.thread_id:
            try: thread = self.guild.get_channel(self.thread_id) or await self.guild.fetch_channel(self.thread_id)
            except Exception: pass
        applicant = self.guild.get_member(self.applicant_id)
        if self.decision == "question":
            if thread:
                try: await thread.add_user(self.reviewer)
                except Exception: pass
                if applicant:
                    try: await thread.add_user(applicant)
                    except Exception: pass
                q_embed = discord.Embed(title=t("embeds", "application", "dm_question_title"), description=t("embeds", "application", "question_thread_desc", mention="<@" + str(self.applicant_id) + ">", reviewer=self.reviewer.mention), color=discord.Color.blurple(), timestamp=now_timestamp())
                q_embed.add_field(name=t("embeds", "application", "review_note"), value=self.note.value, inline=False)
                if self.guild.icon: q_embed.set_footer(text=self.guild.name + " • " + t("embeds", "application", "footer"), icon_url=self.guild.icon.url)
                await thread.send(content="<@" + str(self.applicant_id) + ">", embed=q_embed)
                if applicant:
                    dm_q_embed = make_dm_embed(title=t("embeds", "application", "dm_question_title"), description=t("embeds", "application", "dm_question_desc"), color=discord.Color.blurple(), guild=self.guild, fields=[(t("embeds", "application", "review_reviewer"), self.reviewer.mention, True), (t("embeds", "application", "review_note"), self.note.value, False)], jump_url=thread.jump_url, footer_system=t("embeds", "application", "footer"))
                    await send_dm(applicant, embed=dm_q_embed)
        else:
            if applicant:
                dm_keys = {"accept": ("dm_accepted_title", "dm_accepted_desc"), "decline": ("dm_declined_title", "dm_declined_desc")}
                title_key, desc_key = dm_keys[self.decision]
                dm_embed = make_dm_embed(title=t("embeds", "application", title_key), description=t("embeds", "application", desc_key), color=color, guild=self.guild, fields=[(t("embeds", "application", "review_reviewer"), self.reviewer.mention, True), (t("embeds", "application", "review_note"), self.note.value, False)], footer_system=t("embeds", "application", "footer"))
                await send_dm(applicant, embed=dm_embed)
            if thread:
                status_embed = discord.Embed(title=emojis[self.decision] + "  " + t("embeds", "application", "status_handled"), description=(t("embeds", "application", "review_reviewer") + " " + self.reviewer.mention + "\n" + t("embeds", "application", "review_note") + "\n" + self.note.value), color=color, timestamp=now_timestamp())
                done_view = discord.ui.View()
                btn_label = (t("buttons", "app_" + self.decision) + "  (" + self.reviewer.display_name + ")")[:80]
                done_view.add_item(discord.ui.Button(label=btn_label, style=discord.ButtonStyle.secondary, disabled=True))
                try:
                    await thread.send(embed=status_embed)
                    await interaction.message.edit(view=done_view)
                    await thread.edit(locked=True, archived=True)
                    delete_open_app(thread.id)
                except Exception: pass

class ApplicationReviewView(discord.ui.View):
    def __init__(self, applicant_id: int, thread_id: int = None, review_channel_id: int = None):
        super().__init__(timeout=None)
        self.applicant_id, self.thread_id, self.review_channel_id = applicant_id, thread_id, review_channel_id
        self.accept_btn.label, self.decline_btn.label, self.question_btn.label = t("buttons", "app_accept"), t("buttons", "app_decline"), t("buttons", "app_question")

    def _check_perm(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅", custom_id="app_review_accept")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction): return await interaction.response.send_message(t("errors", "no_permission_review"), ephemeral=True)
        await interaction.response.send_modal(ApplicationDecisionModal(self.applicant_id, "accept", interaction.user, interaction.guild, self.thread_id))

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌", custom_id="app_review_decline")
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction): return await interaction.response.send_message(t("errors", "no_permission_review"), ephemeral=True)
        await interaction.response.send_modal(ApplicationDecisionModal(self.applicant_id, "decline", interaction.user, interaction.guild, self.thread_id))

    @discord.ui.button(label="Question", style=discord.ButtonStyle.blurple, emoji="❓", custom_id="app_review_question")
    async def question_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction): return await interaction.response.send_message(t("errors", "no_permission_review"), ephemeral=True)
        await interaction.response.send_modal(ApplicationDecisionModal(self.applicant_id, "question", interaction.user, interaction.guild, self.thread_id))

class ApplicationModal(discord.ui.Modal):
    def __init__(self, user_id, guild_id, step, steps, review_channel_id, panel_title, questions):
        total = len(steps)
        super().__init__(title=(panel_title[:40] + " (" + str(step + 1) + "/" + str(total) + ")"))
        self.user_id, self.guild_id, self.step, self.steps, self.review_channel_id, self.panel_title, self.questions = user_id, guild_id, step, steps, review_channel_id, panel_title, questions
        self.inputs, self.input_labels = [], []
        if not steps or step >= len(steps) or not steps[step]: raise ValueError("ApplicationModal: no questions")
        for q in steps[step]:
            label_str = q["label"][:45]
            min_len = max(0, min(int(q.get("min_length") or 0), 1023))
            ti = discord.ui.TextInput(label=label_str, placeholder=q.get("placeholder", "")[:100], style=discord.TextStyle.paragraph if q.get("style") == "paragraph" else discord.TextStyle.short, required=q.get("required", True), min_length=min_len if min_len > 0 else None, max_length=1024)
            self.add_item(ti); self.inputs.append(ti); self.input_labels.append(label_str)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in pending_applications: pending_applications[uid] = {"answers": [], "guild_id": self.guild_id}
        for i, ti in enumerate(self.inputs): pending_applications[uid]["answers"].append((self.input_labels[i], ti.value))
        next_step = self.step + 1
        if next_step < len(self.steps):
            view = ApplicationContinueView(uid, self.guild_id, next_step, self.steps, self.review_channel_id, self.panel_title, self.questions)
            total = len(self.steps)
            bar = "█" * next_step + "░" * (total - next_step)
            await interaction.response.send_message(t("success", "application_step_done", current=next_step, total=total, bar=bar), view=view, ephemeral=True)
        else: await self._submit_application(interaction)

    async def _submit_application(self, interaction: discord.Interaction):
        uid = self.user_id
        data = pending_applications.pop(uid, {"answers": [], "guild_id": self.guild_id})
        guild, applicant = interaction.guild, interaction.user
        await interaction.response.send_message(t("success", "application_submitted"), ephemeral=True)
        review_channel = guild.get_channel(self.review_channel_id)
        if not review_channel: return
        config, guild_id = load_config(), str(guild.id)
        panels = config.get(guild_id, {}).get("application_panels", [])
        reviewer_role_ids_set = set()
        for p in panels:
            if p.get("review_channel_id") in (self.review_channel_id, str(self.review_channel_id)):
                for rid in p.get("reviewer_role_ids") or []: reviewer_role_ids_set.add(int(rid))
        reviewer_role_ids = list(reviewer_role_ids_set)
        thread_name = (self.panel_title[:20] + " — " + applicant.display_name[:20])
        try: thread = await review_channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread, reason="Application: " + applicant.display_name)
        except Exception:
            try: thread = await review_channel.create_thread(name=thread_name, type=discord.ChannelType.public_thread)
            except Exception: return
        for rid in reviewer_role_ids:
            role = guild.get_role(rid)
            if role:
                for member in guild.members:
                    if not member.bot and role in member.roles:
                        try: await thread.add_user(member)
                        except Exception: pass
        embeds = build_review_embeds(guild=guild, applicant=applicant, answers=data["answers"], panel_title=self.panel_title, questions=self.questions)
        try:
            rv = ApplicationReviewView(applicant_id=applicant.id, thread_id=thread.id, review_channel_id=self.review_channel_id)
            for i, e in enumerate(embeds):
                if i == len(embeds) - 1: await thread.send(embed=e, view=rv)
                else: await thread.send(embed=e)
            save_open_app(thread.id, applicant.id, self.review_channel_id)
        except discord.Forbidden: pass
        dm_embed = make_dm_embed(title=t("embeds", "application", "dm_title"), description=t("embeds", "application", "dm_desc"), color=discord.Color.green(), guild=guild, footer_system=t("embeds", "application", "footer"))
        await send_dm(applicant, embed=dm_embed)

class ApplicationContinueView(discord.ui.View):
    def __init__(self, user_id, guild_id, step, steps, review_channel_id, panel_title, questions):
        super().__init__(timeout=300); self.user_id, self.guild_id, self.step, self.steps, self.review_channel_id, self.panel_title, self.questions = user_id, guild_id, step, steps, review_channel_id, panel_title, questions
        self.continue_btn.label, self.cancel_btn.label = t("buttons", "app_continue"), t("buttons", "app_cancel")

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.blurple, emoji="📝")
    async def continue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(ApplicationModal(self.user_id, self.guild_id, self.step, self.steps, self.review_channel_id, self.panel_title, self.questions))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        pending_applications.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), view=None)

class ApplicationPanelView(discord.ui.View):
    def __init__(self, panel_index: int):
        super().__init__(timeout=None); self.panel_index = panel_index
        self.apply_btn.label = t("buttons", "apply_now")

    @discord.ui.button(label="Apply Now", style=discord.ButtonStyle.green, emoji="📋", custom_id="application_panel_btn")
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id, config = str(interaction.guild_id), load_config()
        panels = config.get(guild_id, {}).get("application_panels", [])
        panel = next((p for p in panels if p.get("message_id") == interaction.message.id), None)
        if not panel and panels: panel = panels[self.panel_index] if self.panel_index < len(panels) else panels[0]
        if not panel or not panel.get("review_channel_id"): return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        if interaction.user.id in pending_applications: return await interaction.response.send_message(t("errors", "application_already_open"), ephemeral=True)
        questions = panel.get("questions")
        if questions is None: questions = DEFAULT_APPLICATION_QUESTIONS
        if not questions: questions = _load_default_application()
        if not questions: return await interaction.response.send_message("Keine Fragen konfiguriert.", ephemeral=True)
        steps = get_application_steps(questions)
        if not steps: return await interaction.response.send_message("Fehler beim Laden der Fragen.", ephemeral=True)
        await interaction.response.send_modal(ApplicationModal(interaction.user.id, interaction.guild_id, 0, steps, panel["review_channel_id"], panel.get("title", "Application"), questions))

# --- APPLICATION WIZARD ---

def _build_wizard_embed(state: dict, guild) -> discord.Embed:
    BLURPLE = discord.Color.from_rgb(88, 101, 242)
    embed = discord.Embed(title=t("embeds", "wizard", "title"), color=BLURPLE)
    title_val, channel_id = state.get("title") or t("embeds", "wizard", "not_set"), state.get("review_channel_id")
    channel_val = ("<#" + str(channel_id) + ">") if channel_id else t("embeds", "wizard", "not_set")
    role_ids = state.get("reviewer_role_ids", [])
    roles_val = (" ".join("<@&" + str(r) + ">" for r in role_ids) if role_ids else t("embeds", "wizard", "not_set"))
    embed.add_field(name=t("embeds", "wizard", "f_step1"), value=(t("embeds", "wizard", "f_title") + " " + title_val + "\n" + t("embeds", "wizard", "f_channel") + " " + channel_val + "\n" + t("embeds", "wizard", "f_roles") + " " + roles_val), inline=False)
    questions, current_section = state.get("questions"), state.get("current_section")
    if questions is None: embed.add_field(name=t("embeds", "wizard", "f_step2") + " (—)", value=t("embeds", "wizard", "q_default"), inline=False)
    elif len(questions) == 0: embed.add_field(name=t("embeds", "wizard", "f_step2") + " (0)", value=t("embeds", "wizard", "q_none"), inline=False)
    else:
        shown, last_section, field_lines = 0, None, []
        for i, q in enumerate(questions):
            if shown >= 15: field_lines.append(t("embeds", "wizard", "q_more", n=len(questions) - shown)); break
            sec_raw = q.get("section")
            sec_name = sec_raw.get("name", "") if isinstance(sec_raw, dict) else (sec_raw or "")
            if sec_name and sec_name != last_section: field_lines.append("__**" + sec_name + "**__"); last_section = sec_name
            meta_parts = []
            if q.get("style") == "short": meta_parts.append(t("embeds", "wizard", "q_meta_short"))
            if q.get("min_length"): meta_parts.append(t("embeds", "wizard", "q_meta_minlen", n=q["min_length"]))
            meta = ("  `" + " · ".join(meta_parts) + "`") if meta_parts else ""
            field_lines.append("**" + str(i + 1) + ".** " + q["label"] + meta); shown += 1
        embed.add_field(name=t("embeds", "wizard", "f_step2") + " (" + str(len(questions)) + ")", value="\n".join(field_lines) or "—", inline=False)
    if current_section:
        sec_name = current_section.get("name", "") if isinstance(current_section, dict) else str(current_section)
        embed.add_field(name=t("embeds", "wizard", "f_current_section"), value="`" + sec_name + "`", inline=False)
    if guild and guild.icon: embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed

class AppSetupSectionModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "app_setup_section_title")); self.user_id = user_id
        cur = _setup_wizard_state.get(user_id, {}).get("current_section") or {}
        self.f_name = discord.ui.TextInput(label=t("modals", "app_setup_section_label"), placeholder=t("modals", "app_setup_section_ph"), default=cur.get("name", "") if isinstance(cur, dict) else str(cur), style=discord.TextStyle.short, required=False, max_length=60)
        self.f_desc = discord.ui.TextInput(label=t("modals", "app_setup_section_desc_label"), placeholder=t("modals", "app_setup_section_desc_ph"), default=cur.get("desc", "") if isinstance(cur, dict) else "", style=discord.TextStyle.short, required=False, max_length=100)
        self.add_item(self.f_name); self.add_item(self.f_desc)
    async def on_submit(self, interaction: discord.Interaction):
        name, desc = self.f_name.value.strip(), self.f_desc.value.strip()
        _setup_wizard_state[self.user_id]["current_section"] = {"name": name, "desc": desc} if name else None
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try: await _orig.edit_original_response(embed=_build_wizard_embed(_setup_wizard_state[self.user_id], interaction.guild), view=AppSetupMainView(self.user_id))
            except Exception: pass

class AppSetupMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600); self.user_id = user_id
        state = _setup_wizard_state.get(user_id, {})
        has_title, has_channel = bool(state.get("title")), bool(state.get("review_channel_id"))
        self.edit_info_btn.label, self.edit_info_btn.style = t("buttons", "wizard_edit_info"), (discord.ButtonStyle.secondary if has_title else discord.ButtonStyle.danger)
        self.pick_channel_btn.label, self.pick_channel_btn.style = t("buttons", "wizard_pick_channel"), (discord.ButtonStyle.secondary if has_channel else discord.ButtonStyle.danger)
        self.pick_reviewer_btn.label, self.add_q_btn.label, self.add_section_btn.label, self.default_q_btn.label, self.clear_q_btn.label, self.remove_last_btn.label, self.preview_btn.label, self.finish_btn.label, self.cancel_btn.label = t("buttons", "wizard_pick_reviewer"), t("buttons", "wizard_add_q"), t("buttons", "wizard_add_section"), t("buttons", "wizard_default_q"), t("buttons", "wizard_clear_q"), t("buttons", "wizard_remove_last"), t("buttons", "wizard_preview"), t("buttons", "wizard_finish"), t("buttons", "wizard_cancel")
    def _check(self, interaction: discord.Interaction) -> bool: return interaction.user.id == self.user_id
    async def _refresh(self, interaction: discord.Interaction):
        if self.user_id in _setup_wizard_state: await interaction.response.edit_message(embed=_build_wizard_embed(_setup_wizard_state[self.user_id], interaction.guild), view=AppSetupMainView(self.user_id))
    @discord.ui.button(label="✏️ Info", style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction): await interaction.response.send_modal(AppSetupEditInfoModal(self.user_id))
    @discord.ui.button(label="📢 Channel", style=discord.ButtonStyle.secondary, row=0)
    async def pick_channel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction): await interaction.response.send_message(content=t("success", "wizard_pick_channel_hint"), view=_make_channel_select_view(self.user_id, "review_channel_id", _setup_wizard_state, t("selects", "wizard_pick_channel"), refresh_fn=lambda uid, guild: (_build_wizard_embed(_setup_wizard_state[uid], guild), AppSetupMainView(uid))), ephemeral=True)
    @discord.ui.button(label="👥 Roles", style=discord.ButtonStyle.secondary, row=0)
    async def pick_reviewer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction): await interaction.response.send_message(content=t("success", "wizard_pick_roles_hint"), view=_make_role_select_view(self.user_id, "reviewer_role_ids", _setup_wizard_state, t("selects", "wizard_pick_roles"), multi=True, refresh_fn=lambda uid, guild: (_build_wizard_embed(_setup_wizard_state[uid], guild), AppSetupMainView(uid))), ephemeral=True)
    @discord.ui.button(label="➕ Q", style=discord.ButtonStyle.blurple, row=0)
    async def add_q_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction):
            if _setup_wizard_state[self.user_id].get("questions") is None: _setup_wizard_state[self.user_id]["questions"] = []
            await interaction.response.send_modal(AppSetupQuestionsModal(self.user_id))
    @discord.ui.button(label="📂 Sec", style=discord.ButtonStyle.secondary, row=0)
    async def add_section_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction):
            if _setup_wizard_state[self.user_id].get("questions") is None: _setup_wizard_state[self.user_id]["questions"] = []
            await interaction.response.send_modal(AppSetupSectionModal(self.user_id))
    @discord.ui.button(label="✅ Def", style=discord.ButtonStyle.green, row=1)
    async def default_q_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction): _setup_wizard_state[self.user_id]["questions"] = None; await self._refresh(interaction)
    @discord.ui.button(label="🗑️ Clr", style=discord.ButtonStyle.danger, row=1)
    async def clear_q_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction): _setup_wizard_state[self.user_id]["questions"], _setup_wizard_state[self.user_id]["current_section"] = [], None; await self._refresh(interaction)
    @discord.ui.button(label="↩️ Rem", style=discord.ButtonStyle.secondary, row=1)
    async def remove_last_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction):
            qs = _setup_wizard_state[self.user_id].get("questions")
            if qs: qs.pop(); await self._refresh(interaction)
    @discord.ui.button(label="👁️ Pre", style=discord.ButtonStyle.secondary, row=2)
    async def preview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction): return
        state = _setup_wizard_state[self.user_id]
        questions = state.get("questions") or DEFAULT_APPLICATION_QUESTIONS
        emb = discord.Embed(title=state.get("title") or "Preview", description=state.get("desc") or "Desc", color=discord.Color.blurple())
        for q in questions[:10]: emb.add_field(name=q["label"], value="> Answer", inline=False)
        await interaction.response.send_message(content="Preview", embed=emb, ephemeral=True)
    @discord.ui.button(label="🚀 Fin", style=discord.ButtonStyle.green, row=2)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction):
            state = _setup_wizard_state[self.user_id]
            if not state.get("title") or not state.get("review_channel_id"): return await interaction.response.send_message("Fehlende Info.", ephemeral=True)
            await self._finalize(interaction)
    @discord.ui.button(label="✖️ Can", style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction): _setup_wizard_state.pop(self.user_id, None); await interaction.response.edit_message(content="Abgebrochen.", embed=None, view=None)

    async def _finalize(self, interaction: discord.Interaction):
        state = _setup_wizard_state.pop(self.user_id, None)
        if not state: return
        guild_id, config = str(interaction.guild_id), load_config()
        if guild_id not in config: config[guild_id] = {}
        panel_title, panel_desc = state["title"], state["desc"] or "Application"
        questions = state.get("questions")
        emb = discord.Embed(title=panel_title, description=panel_desc, color=discord.Color.blurple(), timestamp=now_timestamp())
        view = ApplicationPanelView(panel_index=len(config[guild_id].get("application_panels", [])))
        msg = await interaction.channel.send(embed=emb, view=view)
        config[guild_id].setdefault("application_panels", []).append({"message_id": msg.id, "channel_id": interaction.channel_id, "review_channel_id": state["review_channel_id"], "reviewer_role_ids": state.get("reviewer_role_ids", []), "title": panel_title, "questions": questions})
        save_config(config)
        await interaction.response.edit_message(embed=discord.Embed(title="Erledigt", description=f"Panel erstellt: {msg.id}", color=discord.Color.green()), view=None)

class AppSetupEditInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title="Edit Info"); self.user_id = user_id
        state = _setup_wizard_state.get(user_id, {})
        self.f_title = discord.ui.TextInput(label="Title", default=state.get("title", ""), required=True)
        self.f_desc = discord.ui.TextInput(label="Desc", default=state.get("desc", ""), style=discord.TextStyle.paragraph, required=False)
        self.add_item(self.f_title); self.add_item(self.f_desc)
    async def on_submit(self, interaction: discord.Interaction):
        _setup_wizard_state[self.user_id].update({"title": self.f_title.value, "desc": self.f_desc.value or ""})
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try: await _orig.edit_original_response(embed=_build_wizard_embed(_setup_wizard_state[self.user_id], interaction.guild), view=AppSetupMainView(self.user_id))
            except Exception: pass

class AppSetupQuestionsModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title="Add Q"); self.user_id = user_id
        self.f_label = discord.ui.TextInput(label="Label", required=True)
        self.f_ph = discord.ui.TextInput(label="Placeholder", required=False)
        self.f_min = discord.ui.TextInput(label="Min Len", required=False)
        self.f_style = discord.ui.TextInput(label="Style (s/p)", required=False)
        self.add_item(self.f_label); self.add_item(self.f_ph); self.add_item(self.f_min); self.add_item(self.f_style)
    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        try: min_len = int(self.f_min.value.strip())
        except: min_len = 0
        style = "short" if (self.f_style.value or "").lower().startswith("s") else "paragraph"
        _setup_wizard_state[uid].setdefault("questions", []).append({"label": self.f_label.value.strip(), "placeholder": self.f_ph.value.strip(), "style": style, "required": True, "min_length": min_len, "section": _setup_wizard_state[uid].get("current_section")})
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try: await _orig.edit_original_response(embed=_build_wizard_embed(_setup_wizard_state[uid], interaction.guild), view=AppSetupMainView(uid))
            except Exception: pass

async def setup(bot):
    await bot.add_cog(Applications(bot))
