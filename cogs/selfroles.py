import discord
from discord import app_commands
from discord.ext import commands
import datetime
from utils import (
    t, td, tp, load_config, save_config, now_timestamp,
    format_discord_text, _make_role_select_view
)
from state import _selfrole_wizard_state, _wizard_interactions

class SelfRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

class SelfRoleSelect(discord.ui.Select):
    def __init__(self, roles_data: list, panel_id: str, member_role_ids: set):
        self.roles_data = roles_data
        self.panel_id = panel_id
        self.member_role_ids = member_role_ids
        options = []
        for role_data in roles_data[:25]:
            has_role = role_data['role_id'] in member_role_ids
            label = role_data['label'][:100]
            display_label = ("✅ " + label)[:100] if has_role else label
            options.append(discord.SelectOption(
                label=display_label,
                value=str(role_data['role_id']),
                emoji=role_data.get('emoji') or None,
                description=role_data.get('description')[:100] if role_data.get('description') else None,
                default=has_role,
            ))
        super().__init__(
            placeholder=t("selects", "selfrole_pick_role"),
            min_values=0,
            max_values=len(options) if options else 1,
            options=options,
            custom_id="selfrole_select_" + panel_id
        )

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        selected_ids = {int(v) for v in self.values}
        current_ids = {r.id for r in member.roles}
        panel_role_ids = {r['role_id'] for r in self.roles_data}
        
        added, removed, errors = [], [], []
        for role_data in self.roles_data:
            rid = role_data['role_id']
            role = interaction.guild.get_role(rid)
            if not role: continue
            if rid in selected_ids and rid not in current_ids:
                try:
                    await member.add_roles(role)
                    added.append(role.name)
                except: errors.append(role.name)
            elif rid not in selected_ids and rid in current_ids:
                try:
                    await member.remove_roles(role)
                    removed.append(role.name)
                except: errors.append(role.name)

        new_ids = (current_ids - panel_role_ids) | selected_ids
        lines = [f"🟢 **{n}** hinzugefügt" for n in added] + [f"🔴 **{n}** entfernt" for n in removed] + [f"❌ **{n}** — Fehler" for n in errors]
        if not lines: lines.append("ℹ️ Keine Änderungen.")
        
        await interaction.response.edit_message(view=SelfRoleView(self.roles_data, self.panel_id, member_role_ids=new_ids))
        await interaction.followup.send(embed=discord.Embed(description="\n".join(lines), color=discord.Color.blue()), ephemeral=True)

class SelfRoleView(discord.ui.View):
    def __init__(self, roles_data: list, panel_id: str = "default", member: discord.Member = None, member_role_ids: set = None):
        super().__init__(timeout=None)
        if member_role_ids is None:
            member_role_ids = {r.id for r in member.roles} if member else set()
        if roles_data:
            self.add_item(SelfRoleSelect(roles_data, panel_id, member_role_ids))

# --- SELFROLE WIZARD ---

def _build_selfrole_embed(state: dict, guild) -> discord.Embed:
    color_hex = state.get("color_hex", "")
    try: color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.blue()
    except: color = discord.Color.blue()
    embed = discord.Embed(title=t("embeds", "selfrole_wizard", "title"), color=color)
    title_val = state.get("title") or t("embeds", "wizard", "not_set")
    desc_val = (state.get("desc") or "")[:60] + ("..." if len(state.get("desc") or "") > 60 else "")
    color_val = ("#" + state["color_hex"]) if state.get("color_hex") else t("embeds", "selfrole_wizard", "color_default")
    embed.add_field(name=t("embeds", "selfrole_wizard", "f_info"), value=(t("embeds", "selfrole_wizard", "f_title") + " " + title_val + "\n" + t("embeds", "selfrole_wizard", "f_desc")  + " " + (desc_val or t("embeds", "wizard", "not_set")) + "\n" + t("embeds", "selfrole_wizard", "f_color") + " " + color_val), inline=False)
    roles = state.get("roles", [])
    if roles:
        lines = [f"**{i+1}.** " + ((r.get('emoji')+' ') if r.get('emoji') else '') + r['label'] + f" <@&{r['role_id']}>" for i, r in enumerate(roles[:15])]
        if len(roles) > 15: lines.append(t("embeds", "wizard", "q_more", n=len(roles)-15))
        roles_val = "\n".join(lines)
    else: roles_val = t("embeds", "selfrole_wizard", "roles_empty")
    embed.add_field(name=t("embeds", "selfrole_wizard", "f_roles") + " (" + str(len(roles)) + ")", value=roles_val, inline=False)
    if guild and guild.icon: embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed

class SelfRoleSetupMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600); self.user_id = user_id
        state = _selfrole_wizard_state.get(user_id, {})
        has_title, has_roles = bool(state.get("title")), bool(state.get("roles"))
        self.edit_info_btn.label = t("buttons", "wizard_edit_info")
        self.edit_info_btn.style = discord.ButtonStyle.secondary if has_title else discord.ButtonStyle.danger
        self.add_role_btn.label = t("buttons", "selfrole_wizard_add")
        self.add_role_btn.style = discord.ButtonStyle.blurple if has_roles else discord.ButtonStyle.danger
        self.remove_role_btn.label, self.finish_btn.label, self.cancel_btn.label = t("buttons", "selfrole_wizard_remove"), t("buttons", "wizard_finish"), t("buttons", "wizard_cancel")
    def _check(self, interaction: discord.Interaction) -> bool: return interaction.user.id == self.user_id
    @discord.ui.button(label="✏️ Info", style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction): await interaction.response.send_modal(SelfRoleSetupInfoModal(self.user_id))
    @discord.ui.button(label="➕ Add", style=discord.ButtonStyle.blurple, row=0)
    async def add_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction):
            if len(_selfrole_wizard_state.get(self.user_id, {}).get("roles", [])) >= 25: return await interaction.response.send_message(t("errors", "selfrole_max_roles"), ephemeral=True)
            v = discord.ui.View(timeout=120); v.add_item(SelfRoleAddRoleSelect(self.user_id))
            await interaction.response.send_message(content=t("success", "selfrole_pick_role_hint"), view=v, ephemeral=True)
    @discord.ui.button(label="🗑️ Rem", style=discord.ButtonStyle.danger, row=0)
    async def remove_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction):
            roles = _selfrole_wizard_state.get(self.user_id, {}).get("roles", [])
            if not roles: return await interaction.response.send_message(t("errors", "selfrole_no_roles_to_remove"), ephemeral=True)
            v = discord.ui.View(timeout=120); v.add_item(SelfRoleRemoveRoleSelect(self.user_id, roles))
            await interaction.response.send_message(content=t("success", "selfrole_remove_role_hint"), view=v, ephemeral=True)
    @discord.ui.button(label="🚀 Fin", style=discord.ButtonStyle.green, row=1)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction):
            state = _selfrole_wizard_state.get(self.user_id)
            if not state or not state.get("title") or not state.get("roles"): return await interaction.response.send_message("Fehlende Info.", ephemeral=True)
            await self._finalize(interaction)
    @discord.ui.button(label="✖️ Can", style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._check(interaction): _selfrole_wizard_state.pop(self.user_id, None); await interaction.response.edit_message(content="Abgebrochen.", embed=None, view=None)
    async def _finalize(self, interaction: discord.Interaction):
        state = _selfrole_wizard_state.pop(self.user_id, None)
        if not state: return
        guild_id, config = str(interaction.guild_id), load_config()
        if guild_id not in config: config[guild_id] = {}
        color = discord.Color.blue()
        if state.get("color_hex"):
            try: color = discord.Color(int(state["color_hex"].lstrip("#"), 16))
            except: pass
        panel_id, roles = str(interaction.id), state["roles"]
        emb = discord.Embed(title=state["title"], description=format_discord_text(state.get("desc", "")), color=color, timestamp=now_timestamp())
        if interaction.guild.icon: emb.set_thumbnail(url=interaction.guild.icon.url)
        view = SelfRoleView(roles, panel_id)
        msg = await interaction.channel.send(embed=emb, view=view)
        config[guild_id].setdefault("selfrole_panels", []).append({"message_id": msg.id, "channel_id": interaction.channel_id, "panel_id": panel_id, "title": state["title"], "roles": roles})
        save_config(config)
        await interaction.response.edit_message(embed=discord.Embed(title="Panel erstellt", description=f"ID: {msg.id}", color=discord.Color.green()), view=None)

class SelfRoleSetupInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title="Info"); self.user_id = user_id
        state = _selfrole_wizard_state.get(user_id, {})
        self.f_title = discord.ui.TextInput(label="Title", default=state.get("title", ""), required=True)
        self.f_desc = discord.ui.TextInput(label="Desc", default=state.get("desc", ""), style=discord.TextStyle.paragraph, required=False)
        self.f_color = discord.ui.TextInput(label="Color Hex", default=state.get("color_hex", ""), required=False)
        self.add_item(self.f_title); self.add_item(self.f_desc); self.add_item(self.f_color)
    async def on_submit(self, interaction: discord.Interaction):
        _selfrole_wizard_state[self.user_id].update({"title": self.f_title.value, "desc": self.f_desc.value, "color_hex": self.f_color.value.lstrip("#")})
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try: await _orig.edit_original_response(embed=_build_selfrole_embed(_selfrole_wizard_state[self.user_id], interaction.guild), view=SelfRoleSetupMainView(self.user_id))
            except: pass

class SelfRoleAddRoleSelect(discord.ui.RoleSelect):
    def __init__(self, user_id: int): super().__init__(placeholder="Pick role", min_values=1, max_values=1); self.user_id = user_id
    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        await interaction.response.send_modal(SelfRoleSetupRoleDetailsModal(self.user_id, role.id, role.name))

class SelfRoleSetupRoleDetailsModal(discord.ui.Modal):
    def __init__(self, user_id, role_id, role_name):
        super().__init__(title="Role Details"); self.user_id, self.role_id = user_id, role_id
        self.f_name = discord.ui.TextInput(label="Label", default=role_name, required=True)
        self.f_emoji = discord.ui.TextInput(label="Emoji", required=False)
        self.f_desc = discord.ui.TextInput(label="Desc", required=False)
        self.add_item(self.f_name); self.add_item(self.f_emoji); self.add_item(self.f_desc)
    async def on_submit(self, interaction: discord.Interaction):
        _selfrole_wizard_state[self.user_id].setdefault("roles", []).append({"label": self.f_name.value, "role_id": self.role_id, "emoji": self.f_emoji.value, "description": self.f_desc.value})
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try: await _orig.edit_original_response(embed=_build_selfrole_embed(_selfrole_wizard_state[self.user_id], interaction.guild), view=SelfRoleSetupMainView(self.user_id))
            except: pass

class SelfRoleRemoveRoleSelect(discord.ui.Select):
    def __init__(self, user_id, roles):
        options = [discord.SelectOption(label=r["label"], value=str(r["role_id"]), emoji=r.get("emoji")) for r in roles]
        super().__init__(placeholder="Remove role", options=options); self.user_id = user_id
    async def callback(self, interaction: discord.Interaction):
        rid = int(self.values[0])
        _selfrole_wizard_state[self.user_id]["roles"] = [r for r in _selfrole_wizard_state[self.user_id].get("roles", []) if r["role_id"] != rid]
        await interaction.response.edit_message(content="Erledigt", view=None)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try: await _orig.edit_original_response(embed=_build_selfrole_embed(_selfrole_wizard_state[self.user_id], interaction.guild), view=SelfRoleSetupMainView(self.user_id))
            except: pass

async def setup(bot):
    await bot.add_cog(SelfRoles(bot))
