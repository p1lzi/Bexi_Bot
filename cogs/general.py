import discord
from discord import app_commands
from discord.ext import commands
import datetime
import os
import shutil
import asyncio
from utils import t, td, tp, load_config, save_config, set_language, now_timestamp, send_log, HAS_STATIC_FFMPEG, ffmpeg_exe
from state import _status_wizard_state, _joinroles_wizard_state, _embed_gen_state, _wizard_interactions, _wizard_messages, _ticket_wizard_state, _verify_wizard_state, _selfrole_wizard_state, _setup_wizard_state

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # This will be called when the cog is ready
        pass

    @app_commands.command(name="ping", description="Zeigt die Latenz des Bots an.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency < 100 else discord.Color.orange() if latency < 200 else discord.Color.red()
        embed = discord.Embed(
            title=t("embeds","ping","title"),
            description=t("embeds","ping","desc", ms=latency),
            color=color
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setup_pioneer_role", description=td("setup_pioneer_role"))
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(rolle=tp("setup_pioneer_role","rolle"))
    async def setup_pioneer_role(self, interaction: discord.Interaction, rolle: discord.Role):
        await interaction.response.defer(ephemeral=True)
        all_members = [m for m in interaction.guild.members if not m.bot]
        all_members.sort(key=lambda m: m.joined_at if m.joined_at else datetime.datetime.now())

        pioneers = all_members[:100]
        assigned_count = 0
        errors = 0

        for member in pioneers:
            if rolle not in member.roles:
                try:
                    await member.add_roles(rolle, reason="Top 100 Pioneer Role Setup")
                    assigned_count += 1
                except Exception:
                    errors += 1

        embed = discord.Embed(
            title=t("embeds","pioneer","title"),
            description=t("success","pioneer_summary"),
            color=discord.Color.gold(),
            timestamp=now_timestamp()
        )
        embed.add_field(name=t("embeds","pioneer","f_role"), value=rolle.mention, inline=True)
        embed.add_field(name=t("embeds","pioneer","f_new"), value=str(assigned_count), inline=True)
        embed.add_field(name=t("embeds","pioneer","f_errors"), value=str(errors), inline=True)
        if interaction.guild.icon:
            embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        config = load_config()
        # Auto-assign join roles
        join_role_ids = config.get(guild_id, {}).get("join_roles", [])
        for rid in join_role_ids:
            role = member.guild.get_role(rid)
            if role:
                try:
                    await member.add_roles(role, reason="Auto Join Role")
                except Exception:
                    pass
        welcome_channel_id = config.get(guild_id, {}).get("welcome_channel_id")
        if welcome_channel_id:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                member_number = sum(1 for m in member.guild.members if not m.bot and m.joined_at and m.joined_at <= member.joined_at)
                embed = discord.Embed(
                    title=t("embeds","welcome","title", server=member.guild.name),
                    description=t("embeds","welcome","desc", mention=member.mention),
                    color=discord.Color.green(),
                    timestamp=now_timestamp()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name=t("embeds","welcome","f_user"), value=member.mention, inline=True)
                embed.add_field(name=t("embeds","welcome","f_acc"), value=discord.utils.format_dt(member.created_at, style="R"), inline=True)
                embed.add_field(name=t("embeds","welcome","f_member"), value=f"**#{member_number}**", inline=True)
                footer_text = f"{member.guild.name}"
                if member.guild.icon:
                    embed.set_footer(text=footer_text, icon_url=member.guild.icon.url)
                else:
                    embed.set_footer(text=footer_text)
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild_id = str(member.guild.id)
        config = load_config()
        waiting_room_id = config.get(guild_id, {}).get("waiting_room_id")
        if not waiting_room_id:
            return
        voice_channel = member.guild.get_channel(waiting_room_id)
        if not voice_channel:
            return
        if after.channel and after.channel.id == waiting_room_id:
            vc = discord.utils.get(self.bot.voice_clients, guild=member.guild)
            if not vc:
                try:
                    vc = await voice_channel.connect()
                    self.bot.loop.create_task(self.play_looping_music(vc))
                except Exception:
                    pass
        elif before.channel and before.channel.id == waiting_room_id:
            vc = discord.utils.get(self.bot.voice_clients, guild=member.guild)
            if vc and len(voice_channel.members) <= 1:
                await vc.disconnect()

    async def play_looping_music(self, vc):
        music_file = os.path.join(os.getcwd(), "support_music.mp3")
        if not os.path.exists(music_file):
            return
        final_ffmpeg_exe = "ffmpeg"
        if HAS_STATIC_FFMPEG:
            final_ffmpeg_exe = ffmpeg_exe
        else:
            found = shutil.which("ffmpeg")
            if found:
                final_ffmpeg_exe = found
            else:
                return
        while vc.is_connected():
            if not vc.is_playing():
                try:
                    source = discord.FFmpegPCMAudio(music_file, executable=final_ffmpeg_exe)
                    vc.play(source)
                except Exception:
                    break
            await asyncio.sleep(2)
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        from urllib.parse import urlparse
        import re
        from utils import load_whitelist

        link_pattern = r'(https?://\S+|www\.\S+)'
        links = re.findall(link_pattern, message.content)

        if links and not message.author.guild_permissions.administrator:
            whitelist = load_whitelist()
            for link in links:
                try:
                    full_url = link if link.startswith("http") else f"http://{link}"
                    domain = urlparse(full_url).netloc.lower()
                    if domain.startswith("www."):
                        domain = domain[4:]

                    is_allowed = any(allowed.lower() in domain for allowed in whitelist)

                    if not is_allowed:
                        try:
                            await message.delete()
                            await send_log(
                                message.guild,
                                t("embeds","log_link","title"),
                                t("embeds","log_link","desc", channel=message.channel.mention),
                                discord.Color.red(),
                                message.author,
                                extra_fields=[
                                    (t("embeds","log_link","f_content"), f"```{message.content[:900]}```", False)
                                ]
                            )
                            allowed_str = ", ".join(f"`{d}`" for d in whitelist)
                            await message.channel.send(
                                t("errors","link_not_allowed", mention=message.author.mention, domains=allowed_str),
                                delete_after=6
                            )
                            return
                        except discord.Forbidden:
                            pass
                except Exception:
                    continue

async def setup(bot):
    await bot.add_cog(General(bot))
