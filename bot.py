import discord
from discord import app_commands
from discord.ext import commands
import re
import json
import os
import asyncio
import shutil
import platform
import datetime

try:
    from static_ffmpeg import run
    ffmpeg_exe, ffprobe_exe = run.get_or_fetch_platform_executables_else_raise()
    HAS_STATIC_FFMPEG = True
except ImportError:
    HAS_STATIC_FFMPEG = False

# --- SETUP AUS UMGEBUNGSVARIABLEN ---
TOKEN = os.getenv('DISCORD_TOKEN')
CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                return json.loads(content) if content else {}
        except json.JSONDecodeError:
            return {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

# --- HELPER: SEND DM ---
async def send_dm(user: discord.User, message: str, embed: discord.Embed = None):
    try:
        await user.send(content=message, embed=embed)
    except discord.Forbidden:
        pass

# --- TICKET CONTROL PANEL ---
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def get_creator_id(self, interaction: discord.Interaction):
        try:
            embed = interaction.message.embeds[0]
            match = re.search(r'<@!?(\d+)>', embed.description)
            if match:
                return int(match.group(1))
        except:
            pass
        return None

    @discord.ui.button(label="Ticket Claimen", style=discord.ButtonStyle.blurple, custom_id="persistent_claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        if any(field.name == "Bearbeiter" for field in embed.fields):
            return await interaction.response.send_message("Dieses Ticket wurde bereits übernommen!", ephemeral=True)
            
        embed.add_field(name="Bearbeiter", value=interaction.user.mention, inline=False)
        embed.color = discord.Color.blue()
        
        button.disabled = True
        button.label = "Ticket beansprucht"
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {interaction.user.mention} hat dieses Ticket übernommen.", ephemeral=False)
        
        creator_id = self.get_creator_id(interaction)
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = discord.Embed(
                    title="Ticket Update",
                    description=f"Dein Ticket in **{interaction.guild.name}** wurde von {interaction.user.mention} übernommen.\n\n[Zum Ticket springen]({interaction.channel.jump_url})",
                    color=discord.Color.blue()
                )
                await send_dm(creator, "", embed=dm_embed)

    @discord.ui.button(label="Ticket Schließen", style=discord.ButtonStyle.red, custom_id="persistent_close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Das Ticket wird geschlossen und archiviert...")
        
        creator_id = self.get_creator_id(interaction)
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = discord.Embed(
                    title="Ticket Geschlossen",
                    description=f"Dein Ticket in **{interaction.guild.name}** wurde abgeschlossen und archiviert.",
                    color=discord.Color.red()
                )
                await send_dm(creator, "", embed=dm_embed)
            
        thread = interaction.channel
        await thread.edit(locked=True, archived=True)

# --- VERIFY SYSTEM ---
class VerifyView(discord.ui.View):
    def __init__(self, role_id: int):
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(label="Verifizieren", style=discord.ButtonStyle.green, custom_id="verify_btn_persistent")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"✅ Du hast die Rolle **{role.name}** erhalten!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Mir fehlen die Rechte, um Rollen zu vergeben.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Diese Rolle existiert nicht mehr.", ephemeral=True)

# --- TICKET SYSTEM ---
class TicketSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Wähle dein Anliegen...", options=options, custom_id="ticket_select_persistent")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Ticket für **{self.values[0]}** wird erstellt...", ephemeral=True)
        
        thread = await interaction.channel.create_thread(
            name=f"ticket-{interaction.user.display_name}-{self.values[0]}",
            type=discord.ChannelType.private_thread
        )
        
        await thread.add_user(interaction.user)
        
        config = load_config()
        guild_id = str(interaction.guild_id)
        team_role_ids = config.get(guild_id, {}).get("support_roles", [])
        
        for role_id in team_role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                for member in role.members:
                    await thread.add_user(member)
        
        embed = discord.Embed(
            title="Support-Ticket geöffnet",
            description=f"Hallo {interaction.user.mention}!\n\nKategorie: **{self.values[0]}**\nBitte beschreibe dein Anliegen hier im Thread.",
            color=discord.Color.green()
        )
        await thread.send(embed=embed, view=TicketControlView())

        dm_embed = discord.Embed(
            title="Ticket erstellt",
            description=f"Du hast erfolgreich ein Ticket in **{interaction.guild.name}** eröffnet.\n\n[Klicke hier, um zum Ticket zu gelangen]({thread.jump_url})",
            color=discord.Color.green()
        )
        await send_dm(interaction.user, "", embed=dm_embed)
        await interaction.message.edit(view=self.view)

class TicketView(discord.ui.View):
    def __init__(self, categories_data):
        super().__init__(timeout=None)
        options = []
        for item in categories_data:
            options.append(discord.SelectOption(
                label=item['label'][:100], 
                value=item['value'][:100], 
                emoji=item.get('emoji'),
                description=item.get('description')[:100] if item.get('description') else None
            ))
        self.add_item(TicketSelect(options))

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        config = load_config()
        for guild_id_str, data in config.items():
            for panel in data.get("verify_panels", []):
                self.add_view(VerifyView(panel["role_id"]))
            for t_panel in data.get("ticket_panels", []):
                self.add_view(TicketView(t_panel["categories"]))
        self.add_view(TicketControlView())
        await self.tree.sync()

    # --- MODERATION: ANTI-LINK ---
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Prüfe auf Links (sehr einfacher Regex)
        link_pattern = r'(https?://\S+|www\.\S+)'
        if re.search(link_pattern, message.content):
            # Wenn der Nutzer kein Admin ist, Nachricht löschen
            if not message.author.guild_permissions.administrator:
                try:
                    await message.delete()
                    await message.channel.send(f"⚠️ {message.author.mention}, das Senden von Links ist hier nicht erlaubt!", delete_after=5)
                    return
                except discord.Forbidden:
                    pass

        await self.process_commands(message)

    # --- EVENT: WILLKOMMENSNACHRICHT ---
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        config = load_config()
        welcome_channel_id = config.get(guild_id, {}).get("welcome_channel_id")
        
        if welcome_channel_id:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                embed = discord.Embed(
                    title="Herzlich Willkommen! ✨",
                    description=f"Hallo {member.mention}, schön dass du da bist!\nWir freuen uns, dich auf **{member.guild.name}** begrüßen zu dürfen.",
                    color=discord.Color.from_rgb(46, 204, 113)
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="Mitgliedernummer", value=f"#{len(member.guild.members)}", inline=True)
                embed.set_footer(text=f"ID: {member.id}")
                
                await channel.send(content=f"Willkommen im Team, {member.mention}!", embed=embed)

    # --- EVENT: WARTESCHLEIFENMUSIK ---
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        guild_id = str(member.guild.id)
        config = load_config()
        waiting_room_id = config.get(guild_id, {}).get("waiting_room_id")
        if not waiting_room_id: return
        voice_channel = member.guild.get_channel(waiting_room_id)
        if not voice_channel: return

        if after.channel and after.channel.id == waiting_room_id:
            vc = discord.utils.get(self.voice_clients, guild=member.guild)
            if not vc:
                try:
                    vc = await voice_channel.connect()
                    self.loop.create_task(self.play_looping_music(vc))
                except: pass
        elif before.channel and before.channel.id == waiting_room_id:
            vc = discord.utils.get(self.voice_clients, guild=member.guild)
            if vc and len(voice_channel.members) <= 1:
                await vc.disconnect()

    async def play_looping_music(self, vc):
        music_file = os.path.join(os.getcwd(), "support_music.mp3")
        if not os.path.exists(music_file): return

        final_ffmpeg_exe = "ffmpeg"
        if HAS_STATIC_FFMPEG:
            final_ffmpeg_exe = ffmpeg_exe
        else:
            found = shutil.which("ffmpeg")
            if found: final_ffmpeg_exe = found
            else: return

        while vc.is_connected():
            if not vc.is_playing():
                try:
                    source = discord.FFmpegPCMAudio(music_file, executable=final_ffmpeg_exe)
                    vc.play(source)
                except: break
            await asyncio.sleep(2)

bot = MyBot()

# --- MODERATION COMMANDS ---

@bot.tree.command(name="warn", description="Warne einen Nutzer per DM")
@app_commands.default_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, nutzer: discord.Member, grund: str):
    embed = discord.Embed(title="Verwarnung erhalten", description=f"Du wurdest auf **{interaction.guild.name}** verwarnt.", color=discord.Color.orange())
    embed.add_field(name="Grund", value=grund)
    embed.add_field(name="Moderator", value=interaction.user.name)
    
    await send_dm(nutzer, "", embed=embed)
    await interaction.response.send_message(f"✅ {nutzer.mention} wurde verwarnt. Grund: {grund}")

@bot.tree.command(name="kick", description="Kicke einen Nutzer vom Server")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    try:
        await nutzer.kick(reason=grund)
        await interaction.response.send_message(f"✅ {nutzer.mention} wurde gekickt. Grund: {grund}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Banne einen Nutzer vom Server")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    try:
        await nutzer.ban(reason=grund)
        await interaction.response.send_message(f"✅ {nutzer.mention} wurde gebannt. Grund: {grund}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)

@bot.tree.command(name="timeout", description="Versetze einen Nutzer in einen Timeout")
@app_commands.default_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, nutzer: discord.Member, minuten: int, grund: str = "Kein Grund angegeben"):
    try:
        duration = datetime.timedelta(minutes=minuten)
        await nutzer.timeout(duration, reason=grund)
        await interaction.response.send_message(f"✅ {nutzer.mention} ist nun für {minuten} Minuten im Timeout. Grund: {grund}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)

# --- ADMIN COMMANDS ---

@bot.tree.command(name="set_welcome_channel", description="Legt den Kanal für Willkommensnachrichten fest")
@app_commands.default_permissions(administrator=True)
async def set_welcome_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config: config[guild_id] = {}
    config[guild_id]["welcome_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Willkommensnachrichten werden nun in {kanal.mention} gesendet.", ephemeral=True)

@bot.tree.command(name="set_waiting_room", description="Legt den Sprachkanal für die Warteschleifenmusik fest")
@app_commands.default_permissions(administrator=True)
async def set_waiting_room(interaction: discord.Interaction, kanal: discord.VoiceChannel):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config: config[guild_id] = {}
    config[guild_id]["waiting_room_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Warteschleifen-Kanal auf **{kanal.name}** gesetzt.", ephemeral=True)

@bot.tree.command(name="setup_verify", description="Erstellt ein Verify-Panel")
@app_commands.default_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction, rolle: discord.Role):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config: config[guild_id] = {"verify_panels": [], "ticket_panels": [], "support_roles": []}
    embed = discord.Embed(title="Server Verifizierung", description=f"Klicke auf den Button für die Rolle **{rolle.name}**.", color=discord.Color.blue())
    message = await interaction.channel.send(embed=embed, view=VerifyView(rolle.id))
    config[guild_id].setdefault("verify_panels", []).append({"role_id": rolle.id, "channel_id": interaction.channel_id, "message_id": message.id})
    save_config(config)
    await interaction.response.send_message(f"✅ Verify-Panel erstellt.", ephemeral=True)

@bot.tree.command(name="setup_tickets", description="Erstellt ein Ticket-System")
@app_commands.default_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction, kategorien: str):
    guild_id = str(interaction.guild_id)
    raw_list = re.findall(r'"([^"]*)"', kategorien)
    if not raw_list: raw_list = [c.strip() for c in kategorien.split(",") if c.strip()]
    formatted_cats = []
    for item in raw_list:
        parts = item.split("|")
        main_part = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else None
        emoji, label = None, main_part
        match = re.search(r'^([^\x00-\x7F]|\W+)\s*(.*)', main_part)
        if match:
            emoji = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else emoji
        formatted_cats.append({"label": label, "value": label, "emoji": emoji, "description": description})
    
    config = load_config()
    if guild_id not in config: config[guild_id] = {}
    view = TicketView(formatted_cats)
    embed = discord.Embed(title="Support-Tickets", description="Wähle eine Kategorie aus dem Menü unten aus.", color=discord.Color.gold())
    message = await interaction.channel.send(embed=embed, view=view)
    config[guild_id].setdefault("ticket_panels", []).append({"categories": formatted_cats, "channel_id": interaction.channel_id, "message_id": message.id})
    save_config(config)
    await interaction.response.send_message(f"✅ Ticket-Panel erstellt (ID: {message.id}).", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online als {bot.user}')

if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
    else: print("Fehler: DISCORD_TOKEN fehlt!")