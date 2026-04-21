import discord
from discord import app_commands
from discord.ext import commands
import json
import io
from utils import (
    t, td, tp, load_config, save_config, now_timestamp,
    set_language, send_log, load_open_apps
)
from state import _wizard_interactions

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="adminpanel", description=td("adminpanel"))
    @app_commands.default_permissions(administrator=True)
    async def adminpanel_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title=t("embeds","admin_panel","title"), description=t("embeds","admin_panel","desc"), color=discord.Color.blurple(), timestamp=now_timestamp())
        if interaction.guild.icon: embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.send_message(embed=embed, view=AdminStartView(interaction.user.id), ephemeral=True)

    @app_commands.command(name="set_language", description=td("set_language"))
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(sprache=[
        app_commands.Choice(name="🇩🇪 Deutsch", value="de"),
        app_commands.Choice(name="🇬🇧 English", value="en"),
    ])
    async def set_language_cmd(self, interaction: discord.Interaction, sprache: app_commands.Choice[str]):
        ok = set_language(sprache.value, guild_id=str(interaction.guild_id))
        if not ok: return await interaction.response.send_message(t("errors", "unknown_language"), ephemeral=True)
        await interaction.response.send_message(t("success", "language_set"), ephemeral=True)
        lang_names = {"de": "🇩🇪 Deutsch", "en": "🇬🇧 English"}
        await send_log(interaction.guild, t("embeds", "log_language", "title"), t("embeds", "log_language", "desc", lang=lang_names.get(sprache.value, sprache.value)), discord.Color.blurple(), interaction.user, moderator=interaction.user)

    @app_commands.command(name="config_export", description=td("config_export"))
    @app_commands.default_permissions(administrator=True)
    async def config_export(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        config, guild_id = load_config(), str(interaction.guild_id)
        gdata = config.get(guild_id, {})
        if not gdata: return await interaction.followup.send(t("errors","config_export_empty"), ephemeral=True)
        guild_channel_ids = {ch.id for ch in interaction.guild.channels}
        open_apps = load_open_apps()
        guild_open_apps = {tid: entry for tid, entry in open_apps.items() if entry.get("review_channel_id") in guild_channel_ids}
        export = {guild_id: gdata, "open_applications": guild_open_apps}
        buf = io.BytesIO(json.dumps(export, indent=4, ensure_ascii=False).encode("utf-8"))
        buf.seek(0)
        file = discord.File(buf, filename=f"config_{guild_id}.json")
        await interaction.followup.send(t("success","config_export_done"), file=file, ephemeral=True)
        await send_log(interaction.guild, t("embeds", "log_config_export", "title"), t("embeds", "log_config_export", "desc"), discord.Color.blurple(), interaction.user, moderator=interaction.user)

class AdminStartView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600); self.user_id = user_id
    # Placeholder for buttons like Edit, Delete etc.
    @discord.ui.button(label="Setup", style=discord.ButtonStyle.blurple)
    async def setup_btn(self, interaction, btn):
        if interaction.user.id != self.user_id: return
        from cogs.setup import SetupMenuView
        await interaction.response.edit_message(view=SetupMenuView(self.user_id))

async def setup(bot):
    await bot.add_cog(Admin(bot))
