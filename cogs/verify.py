import discord
from discord import app_commands
from discord.ext import commands
import datetime
from utils import (
    t, td, tp, load_config, save_config, now_timestamp,
    _make_role_select_view
)
from state import _verify_wizard_state, _wizard_interactions

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

class VerifyView(discord.ui.View):
    def __init__(self, role_id: int):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.verify.label = t("buttons", "verify")

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, emoji="✅", custom_id="verify_btn_persistent")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(t("success", "verify_success", role=role.name), ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(t("errors", "verify_no_permission"), ephemeral=True)
        else:
            await interaction.response.send_message(t("errors", "role_not_found"), ephemeral=True)

# --- VERIFY WIZARD ---

def _build_verify_embed_preview(state: dict, guild) -> discord.Embed:
    color_hex = state.get("color_hex")
    try:
        color = discord.Color(int(color_hex, 16)) if color_hex else discord.Color.green()
    except (ValueError, TypeError):
        color = discord.Color.green()
    embed = discord.Embed(
        title=state.get("title") or t("embeds", "verify_panel", "default_title"),
        description=state.get("desc") or t("embeds", "verify_panel", "default_desc"),
        color=color
    )
    if state.get("thumbnail", True) and guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    role_id = state.get("role_id")
    role_name = ""
    if role_id and guild:
        role = guild.get_role(role_id)
        role_name = role.name if role else str(role_id)
    embed.set_footer(text=t("embeds", "verify_panel", "footer", role=role_name))
    return embed

def _build_verify_wizard_embed(state: dict, guild) -> discord.Embed:
    BLURPLE = discord.Color.blurple()
    embed = discord.Embed(title=t("embeds", "verify_wizard", "title"), color=BLURPLE)
    role_id = state.get("role_id")
    role_val = ("<@&" + str(role_id) + ">") if role_id else t("embeds", "wizard", "not_set")
    title_val = state.get("title") or t("embeds", "verify_panel", "default_title")
    desc_val = (state.get("desc") or "")[:50] + ("..." if len(state.get("desc") or "") > 50 else "")
    color_val = ("#" + state["color_hex"]) if state.get("color_hex") else t("embeds", "verify_wizard", "color_default")
    thumb_val = t("embeds", "ticket_wizard", "thumb_on") if state.get("thumbnail", True) else t("embeds", "ticket_wizard", "thumb_off")
    embed.add_field(name=t("embeds", "verify_wizard", "f_settings"), value=(
        t("embeds", "verify_wizard", "f_role")  + " " + role_val  + "\n" +
        t("embeds", "verify_wizard", "f_title") + " " + title_val + "\n" +
        t("embeds", "verify_wizard", "f_desc")  + " " + (desc_val or t("embeds", "wizard", "not_set")) + "\n" +
        t("embeds", "verify_wizard", "f_color") + " " + color_val + "\n" +
        t("embeds", "verify_wizard", "f_thumb") + " " + thumb_val
    ), inline=False)
    if guild and guild.icon: embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed

class VerifySetupInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "verify_setup_info_title"))
        self.user_id = user_id
        state = _verify_wizard_state.get(user_id, {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "verify_setup_title_label"),
            placeholder=t("modals", "verify_setup_title_ph"),
            default=state.get("title", ""),
            style=discord.TextStyle.short, required=False, max_length=80
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "verify_setup_desc_label"),
            placeholder=t("modals", "verify_setup_desc_ph"),
            default=state.get("desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.f_color = discord.ui.TextInput(
            label=t("modals", "verify_setup_color_label"),
            placeholder=t("modals", "verify_setup_color_ph"),
            default=state.get("color_hex", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_thumbnail = discord.ui.TextInput(
            label=t("modals", "verify_setup_thumb_label"),
            placeholder=t("modals", "verify_setup_thumb_ph"),
            default="yes" if state.get("thumbnail", True) else "no",
            style=discord.TextStyle.short, required=False, max_length=5
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)
        self.add_item(self.f_color)
        self.add_item(self.f_thumbnail)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        color_raw = self.f_color.value.strip().lstrip("#")
        if color_raw:
            try: int(color_raw, 16)
            except ValueError: return await interaction.response.send_message(t("errors", "ticket_invalid_color"), ephemeral=True)
        thumb_raw = self.f_thumbnail.value.strip().lower()
        thumbnail = thumb_raw not in ("no", "n", "false", "0", "nein")
        _verify_wizard_state[uid].update({
            "title": self.f_title.value.strip(),
            "desc": self.f_desc.value.strip(),
            "color_hex": color_raw,
            "thumbnail": thumbnail
        })
        embed = _build_verify_wizard_embed(_verify_wizard_state[uid], interaction.guild)
        view = VerifyWizardMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try: await _orig.edit_original_response(embed=embed, view=view)
            except Exception: pass

class VerifyWizardMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        state = _verify_wizard_state.get(user_id, {})
        has_role = bool(state.get("role_id"))
        self.edit_info_btn.label = t("buttons", "wizard_edit_info")
        self.pick_role_btn.label = t("buttons", "verify_wizard_pick_role")
        self.pick_role_btn.style = discord.ButtonStyle.secondary if has_role else discord.ButtonStyle.danger
        self.preview_btn.label = t("buttons", "wizard_preview")
        self.finish_btn.label = t("buttons", "wizard_finish")
        self.cancel_btn.label = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="✏️ Info", style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(VerifySetupInfoModal(self.user_id))

    @discord.ui.button(label="🛡️ Role", style=discord.ButtonStyle.secondary, row=0)
    async def pick_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        view = _make_role_select_view(
            self.user_id, "role_id", _verify_wizard_state, t("selects", "verify_pick_role"),
            refresh_fn=lambda uid, guild: (_build_verify_wizard_embed(_verify_wizard_state[uid], guild), VerifyWizardMainView(uid))
        )
        await interaction.response.send_message(content=t("success", "verify_pick_role_hint"), view=view, ephemeral=True)

    @discord.ui.button(label="👁️ Preview", style=discord.ButtonStyle.secondary, row=0)
    async def preview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _verify_wizard_state.get(self.user_id)
        if not state: return
        embed = _build_verify_embed_preview(state, interaction.guild)
        await interaction.response.send_message(content=t("success", "wizard_preview_note"), embed=embed, ephemeral=True)

    @discord.ui.button(label="🚀 Finish", style=discord.ButtonStyle.green, row=1)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _verify_wizard_state.get(self.user_id)
        if not state or not state.get("role_id"): return await interaction.response.send_message(t("errors", "wizard_missing_roles"), ephemeral=True)
        await self._finalize(interaction)

    @discord.ui.button(label="✖️ Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _verify_wizard_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), embed=None, view=None)

    async def _finalize(self, interaction: discord.Interaction):
        state = _verify_wizard_state.pop(self.user_id, None)
        if not state: return
        guild_id = str(interaction.guild_id)
        config = load_config()
        if guild_id not in config: config[guild_id] = {}
        embed = _build_verify_embed_preview(state, interaction.guild)
        view = VerifyView(state["role_id"])
        message = await interaction.channel.send(embed=embed, view=view)
        config[guild_id].setdefault("verify_panels", []).append({
            "message_id": message.id, "channel_id": interaction.channel_id,
            "role_id": state["role_id"], "title": state.get("title")
        })
        save_config(config)
        done_embed = discord.Embed(title=t("embeds", "wizard", "done_title"), description=t("success", "verify_panel_created", id=message.id), color=discord.Color.green(), timestamp=now_timestamp())
        if interaction.guild.icon: done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=done_embed, view=None)

async def setup(bot):
    await bot.add_cog(Verify(bot))
