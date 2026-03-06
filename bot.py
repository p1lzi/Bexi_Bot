import discord
from discord import app_commands
from discord.ext import commands
import re
import json
import os
import asyncio
import shutil
import datetime
from dotenv import load_dotenv

load_dotenv()

# HINWEIS: Installiere 'static-ffmpeg' in deiner .venv via: pip install static-ffmpeg
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

def format_discord_text(text: str):
    if not text:
        return ""
    text = text.replace("/n", "\n")
    return text

def extract_role_ids(input_str: str):
    """Extrahiert alle Rollen-IDs aus einem String (Erwähnungen oder reine IDs)."""
    return [int(id_str) for id_str in re.findall(r'\d+', input_str)]

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

    def is_supporter(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
            
        config = load_config()
        guild_data = config.get(str(interaction.guild_id), {})
        panels = guild_data.get("ticket_panels", [])
        
        user_role_ids = [role.id for role in interaction.user.roles]
        
        for panel in panels:
            supp_role_ids = panel.get("supporter_role_ids", [])
            if any(rid in user_role_ids for rid in supp_role_ids):
                return True
                
            for cat in panel.get("categories", []):
                cat_role_ids = cat.get("supporter_role_ids", [])
                if cat_role_ids and any(rid in user_role_ids for rid in cat_role_ids):
                    return True
        return False

    @discord.ui.button(label="Ticket Claimen", style=discord.ButtonStyle.blurple, custom_id="persistent_claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message("❌ Nur Supporter können Tickets claimen.", ephemeral=True)

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
                await send_dm(creator, "", dm_embed)

    @discord.ui.button(label="Ticket Schließen", style=discord.ButtonStyle.red, custom_id="persistent_close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message("❌ Nur Supporter können Tickets schließen.", ephemeral=True)

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
                await send_dm(creator, "", dm_embed)
            
        thread = interaction.channel
        await thread.edit(locked=True, archived=True)

async def send_dm(user: discord.User, message: str, embed: discord.Embed = None):
    try:
        await user.send(content=message, embed=embed)
    except discord.Forbidden:
        pass

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
    def __init__(self, options, supporter_role_ids, categories_full_data=None):
        super().__init__(placeholder="Wähle dein Anliegen...", options=options, custom_id="ticket_select_persistent")
        self.supporter_role_ids = supporter_role_ids
        self.categories_full_data = categories_full_data or []

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        guild_id = str(interaction.guild_id)
        config = load_config()
        
        if guild_id not in config: config[guild_id] = {}
        if "ticket_counter" not in config[guild_id]:
            config[guild_id]["ticket_counter"] = 0
            
        config[guild_id]["ticket_counter"] += 1
        ticket_id = config[guild_id]["ticket_counter"]
        save_config(config)
        
        formatted_id = f"{ticket_id:04d}"
        
        target_role_ids = self.supporter_role_ids
        for cat in self.categories_full_data:
            if cat['value'] == selected_value and cat.get('supporter_role_ids'):
                target_role_ids = cat['supporter_role_ids']
                break

        clean_category = re.sub(r'[^\w\s-]', '', selected_value).strip().replace(' ', '-').lower()
        clean_username = interaction.user.display_name.replace(' ', '-').lower()
        thread_name = f"{clean_category}-{clean_username}-{formatted_id}"

        thread = await interaction.channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread
        )
        
        await interaction.response.send_message(
            f"✅ Dein Ticket **#{formatted_id}** wurde erstellt: {thread.mention}\n"
            f"[Klicke hier, um zum Ticket zu springen]({thread.jump_url})", 
            ephemeral=True
        )
        
        await thread.add_user(interaction.user)
        
        for rid in target_role_ids:
            role = interaction.guild.get_role(rid)
            if role:
                for member in role.members:
                    await thread.add_user(member)
        
        embed = discord.Embed(
            title=f"Support-Ticket #{formatted_id}",
            description=f"Hallo {interaction.user.mention}!\n\nDein Ticket wurde erfolgreich erstellt.",
            color=discord.Color.green()
        )
        embed.add_field(name="Ticket-Nummer", value=f"#{formatted_id}", inline=True)
        embed.add_field(name="Kategorie / Grund", value=selected_value, inline=True)
        embed.add_field(name="Info", value="Bitte beschreibe dein Anliegen so detailliert wie möglich.", inline=False)
        embed.set_footer(text=f"User-ID: {interaction.user.id}")
        
        await thread.send(embed=embed, view=TicketControlView())

        dm_embed = discord.Embed(
            title=f"Ticket #{formatted_id} erstellt",
            description=f"Du hast erfolgreich ein Ticket in **{interaction.guild.name}** eröffnet.\n\n**Grund:** {selected_value}\n\n[Klicke hier, um zum Ticket zu gelangen]({thread.jump_url})",
            color=discord.Color.green()
        )
        await send_dm(interaction.user, "", dm_embed)

class TicketView(discord.ui.View):
    def __init__(self, categories_data, supporter_role_ids):
        super().__init__(timeout=None)
        options = []
        for item in categories_data:
            options.append(discord.SelectOption(
                label=item['label'][:100], 
                value=item['value'][:100], 
                emoji=item.get('emoji'),
                description=item.get('description')[:100] if item.get('description') else None
            ))
        self.clear_items()
        self.add_item(TicketSelect(options, supporter_role_ids, categories_data))

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        config = load_config()
        for guild_id_str, data in config.items():
            for panel in data.get("verify_panels", []):
                self.add_view(VerifyView(panel["role_id"]))
            for t_panel in data.get("ticket_panels", []):
                supp_ids = t_panel.get("supporter_role_ids")
                if not supp_ids:
                    old_id = t_panel.get("supporter_role_id")
                    supp_ids = [old_id] if old_id else []
                self.add_view(TicketView(t_panel["categories"], supp_ids))
        self.add_view(TicketControlView())
        
        await self.tree.sync()
        print("🌐 Slash Commands wurden global synchronisiert.")

    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        link_pattern = r'(https?://\S+|www\.\S+)'
        if re.search(link_pattern, message.content):
            if not message.author.guild_permissions.administrator:
                try:
                    await message.delete()
                    await message.channel.send(f"⚠️ {message.author.mention}, Links verboten!", delete_after=5)
                    return
                except discord.Forbidden: pass
        await self.process_commands(message)

    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        config = load_config()
        welcome_channel_id = config.get(guild_id, {}).get("welcome_channel_id")
        if welcome_channel_id:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                embed = discord.Embed(title="Willkommen!", description=f"Hallo {member.mention} auf {member.guild.name}!", color=0x2ecc71)
                await channel.send(embed=embed)

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
        if HAS_STATIC_FFMPEG: final_ffmpeg_exe = ffmpeg_exe
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

@bot.tree.command(name="ban", description="Bannt ein Mitglied permanent vom Server")
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(nutzer="Das zu bannende Mitglied", grund="Der Grund für den Bann")
async def ban(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    try:
        await nutzer.ban(reason=grund)
        await interaction.response.send_message(f"✅ **{nutzer}** wurde gebannt. Grund: {grund}", ephemeral=True)
    except:
        await interaction.response.send_message("❌ Fehler beim Bannen.", ephemeral=True)

@bot.tree.command(name="kick", description="Kickt ein Mitglied vom Server")
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(nutzer="Das zu kickende Mitglied", grund="Der Grund für den Kick")
async def kick(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    try:
        await nutzer.kick(reason=grund)
        await interaction.response.send_message(f"✅ **{nutzer}** wurde gekickt. Grund: {grund}", ephemeral=True)
    except:
        await interaction.response.send_message("❌ Fehler beim Kicken.", ephemeral=True)

@bot.tree.command(name="timeout", description="Versetzt ein Mitglied für eine bestimmte Zeit in den Timeout")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(nutzer="Das Mitglied", minuten="Dauer in Minuten", grund="Grund für den Timeout")
async def timeout(interaction: discord.Interaction, nutzer: discord.Member, minuten: int, grund: str = "Kein Grund angegeben"):
    try:
        duration = datetime.timedelta(minutes=minuten)
        await nutzer.timeout(duration, reason=grund)
        await interaction.response.send_message(f"✅ **{nutzer}** ist nun für {minuten} Minuten im Timeout. Grund: {grund}", ephemeral=True)
    except:
        await interaction.response.send_message("❌ Fehler beim Timeout.", ephemeral=True)

@bot.tree.command(name="warn", description="Verwarnt ein Mitglied und speichert den Warn")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(nutzer="Das Mitglied", grund="Grund der Verwarnung")
async def warn(interaction: discord.Interaction, nutzer: discord.Member, grund: str):
    config = load_config()
    gid = str(interaction.guild_id)
    uid = str(nutzer.id)
    
    if gid not in config: config[gid] = {}
    if "warns" not in config[gid]: config[gid]["warns"] = {}
    
    current_warns = config[gid]["warns"].get(uid, 0)
    config[gid]["warns"][uid] = current_warns + 1
    save_config(config)

    embed = discord.Embed(title="Verwarnung", description=f"Du wurdest auf **{interaction.guild.name}** verwarnt.\n\n**Grund:** {grund}\n**Gesamt-Warns:** {current_warns + 1}", color=discord.Color.orange())
    await send_dm(nutzer, "", embed)
    await interaction.response.send_message(f"✅ {nutzer.mention} wurde verwarnt. Grund: {grund} (Warns: {current_warns + 1})", ephemeral=True)

@bot.tree.command(name="userinfo", description="Zeigt detaillierte Informationen über ein Mitglied an")
@app_commands.describe(nutzer="Das Mitglied (leer lassen für dich selbst)")
async def userinfo(interaction: discord.Interaction, nutzer: discord.Member = None):
    target = nutzer or interaction.user
    gid = str(interaction.guild_id)
    config = load_config()
    
    warns = 0
    if gid in config and "warns" in config[gid]:
        warns = config[gid]["warns"].get(str(target.id), 0)

    roles = [role.mention for role in target.roles if role != interaction.guild.default_role]
    embed = discord.Embed(title=f"Infos zu {target.name}", color=target.color)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=target.id)
    embed.add_field(name="Warns", value=str(warns))
    embed.add_field(name="Server beigetreten", value=target.joined_at.strftime("%d.%m.%Y"))
    embed.add_field(name="Discord beigetreten", value=target.created_at.strftime("%d.%m.%Y"))
    embed.add_field(name="Rollen", value=" ".join(roles) if roles else "Keine", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- CONFIG COMMANDS ---

@bot.tree.command(name="set_welcome_channel", description="Legt den Kanal für Willkommensnachrichten fest")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(kanal="Der Textkanal für die Nachrichten")
async def set_welcome_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config: config[gid] = {}
    config[gid]["welcome_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Willkommens-Kanal auf {kanal.mention} gesetzt.", ephemeral=True)

@bot.tree.command(name="set_waiting_room", description="Konfiguriert den Warteraum für die Support-Musik")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(kanal="Der Sprachkanal, der als Warteraum dient")
async def set_waiting_room(interaction: discord.Interaction, kanal: discord.VoiceChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config: config[gid] = {}
    config[gid]["waiting_room_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Warteraum auf {kanal.mention} gesetzt.", ephemeral=True)

@bot.tree.command(name="setup_verify", description="Erstellt eine Nachricht mit einem Verifizierungs-Button")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(titel="Überschrift des Panels", beschreibung="Anleitungstext", rolle="Rolle, die vergeben wird")
async def setup_verify(interaction: discord.Interaction, titel: str, beschreibung: str, rolle: discord.Role):
    embed = discord.Embed(title=titel, description=format_discord_text(beschreibung), color=discord.Color.blue())
    view = VerifyView(rolle.id)
    msg = await interaction.channel.send(embed=embed, view=view)
    
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config: config[gid] = {}
    config[gid].setdefault("verify_panels", []).append({"role_id": rolle.id, "msg_id": msg.id})
    save_config(config)
    await interaction.response.send_message("✅ Verifizierungs-Panel erstellt.", ephemeral=True)

@bot.tree.command(name="status_config", description="Ändert den Online-Status und die Aktivität des Bots")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(status=[
    app_commands.Choice(name="Online", value="online"),
    app_commands.Choice(name="Abwesend (Idle)", value="idle"),
    app_commands.Choice(name="Bitte nicht stören (DnD)", value="dnd"),
    app_commands.Choice(name="Unsichtbar (Offline)", value="invisible")
])
@app_commands.choices(aktivitaet_typ=[
    app_commands.Choice(name="Spielt", value="playing"),
    app_commands.Choice(name="Streamt", value="streaming"),
    app_commands.Choice(name="Hört zu", value="listening"),
    app_commands.Choice(name="Schaut", value="watching")
])
@app_commands.describe(
    status="Wähle den Online-Status",
    aktivitaet_typ="Was macht der Bot?",
    text="Der Text, der angezeigt werden soll",
    stream_url="Nur nötig, wenn 'Streamt' gewählt wurde"
)
async def status_config(
    interaction: discord.Interaction, 
    status: app_commands.Choice[str], 
    aktivitaet_typ: app_commands.Choice[str], 
    text: str, 
    stream_url: str = "https://twitch.tv/discord"
):
    discord_status = discord.Status.online
    if status.value == "idle": discord_status = discord.Status.idle
    elif status.value == "dnd": discord_status = discord.Status.dnd
    elif status.value == "invisible": discord_status = discord.Status.invisible

    activity = None
    if aktivitaet_typ.value == "playing":
        activity = discord.Game(name=text)
    elif aktivitaet_typ.value == "streaming":
        activity = discord.Streaming(name=text, url=stream_url)
    elif aktivitaet_typ.value == "listening":
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)
    elif aktivitaet_typ.value == "watching":
        activity = discord.Activity(type=discord.ActivityType.watching, name=text)

    await bot.change_presence(status=discord_status, activity=activity)
    
    config = load_config()
    config["bot_presence"] = {
        "status": status.value,
        "type": aktivitaet_typ.value,
        "text": text,
        "url": stream_url
    }
    save_config(config)

    await interaction.response.send_message(f"✅ Bot-Status aktualisiert auf: **{status.name}** | **{aktivitaet_typ.name} {text}**", ephemeral=True)

# --- TICKET COMMANDS ---

@bot.tree.command(name="setup_tickets", description="Erstellt ein neues Support-Ticket-Panel")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    supporter_rollen="Erwähne Rollen, die alle Tickets sehen dürfen (z.B. @Admin @Supporter)",
    kategorien="Format: \"Emoji Name|Beschreibung\", \"Emoji Name|Beschreibung\"..."
)
async def setup_tickets(interaction: discord.Interaction, supporter_rollen: str, kategorien: str):
    guild_id = str(interaction.guild_id)
    role_ids = extract_role_ids(supporter_rollen)
    if not role_ids:
        return await interaction.response.send_message("❌ Bitte gib mindestens eine gültige Rolle an.", ephemeral=True)

    raw_list = re.findall(r'"([^"]*)"', kategorien)
    if not raw_list: raw_list = [c.strip() for c in kategorien.split(",") if c.strip()]
    
    formatted_cats = []
    for item in raw_list:
        parts = item.split("|")
        label = parts[0].strip()
        desc = format_discord_text(parts[1].strip()) if len(parts) > 1 else None
        emoji = None
        match = re.search(r'^([^\x00-\x7F]|\W+)\s*(.*)', label)
        if match:
            emoji = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else emoji
        formatted_cats.append({"label": label, "value": label, "emoji": emoji, "description": desc, "supporter_role_ids": None})
    
    config = load_config()
    if guild_id not in config: config[guild_id] = {}
    
    view = TicketView(formatted_cats, role_ids)
    default_title = "Support-Tickets"
    embed = discord.Embed(title=default_title, description="Wähle eine Kategorie aus dem Dropdown-Menü unten.", color=discord.Color.gold())
    message = await interaction.channel.send(embed=embed, view=view)
    
    config[guild_id].setdefault("ticket_panels", []).append({
        "categories": formatted_cats, 
        "channel_id": interaction.channel_id, 
        "message_id": message.id,
        "supporter_role_ids": role_ids,
        "created_at": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "title": default_title
    })
    save_config(config)
    await interaction.response.send_message(f"✅ Ticket-Panel erstellt (ID: {message.id}).", ephemeral=True)

@bot.tree.command(name="ticket_edit", description="Bearbeitet ein bestehendes Ticket-Panel (Titel, Text, Farbe)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    message_id="Wähle das Panel aus der Liste", 
    titel="Neuer Titel (leer lassen für keine Änderung)", 
    beschreibung="Neue Beschreibung (leer lassen für keine Änderung)", 
    farbe="Farbe als Hex-Code (z.B. #ff0000)"
)
async def ticket_edit(interaction: discord.Interaction, message_id: str, titel: str = None, beschreibung: str = None, farbe: str = None):
    guild_id = str(interaction.guild_id)
    config = load_config()
    
    target_panel = None
    if guild_id in config and "ticket_panels" in config[guild_id]:
        for p in config[guild_id]["ticket_panels"]:
            if str(p["message_id"]) == message_id:
                target_panel = p
                break

    try:
        target_channel_id = target_panel["channel_id"] if target_panel else interaction.channel_id
        channel = interaction.guild.get_channel(target_channel_id) or await interaction.guild.fetch_channel(target_channel_id)
        msg = await channel.fetch_message(int(message_id))
        
        embed = msg.embeds[0]
        if titel: 
            embed.title = titel
            if target_panel: 
                target_panel["title"] = titel # Synchronisiert Titel in Config
        if beschreibung: 
            embed.description = format_discord_text(beschreibung)
        if farbe:
            try:
                farbe = farbe.replace("#", "")
                embed.color = discord.Color(int(farbe, 16))
            except ValueError:
                return await interaction.response.send_message("❌ Ungültiger Hex-Code für die Farbe!", ephemeral=True)
        
        await msg.edit(embed=embed)
        save_config(config)
        await interaction.response.send_message("✅ Panel und Konfiguration aktualisiert.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Fehler beim Bearbeiten: {e}", ephemeral=True)

@bot.tree.command(name="ticket_delete", description="Löscht ein Ticket-Panel permanent aus Discord und der Konfiguration")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(message_id="Wähle das Panel zum Löschen aus")
async def ticket_delete(interaction: discord.Interaction, message_id: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    
    if guild_id not in config or "ticket_panels" not in config[guild_id]:
        return await interaction.response.send_message("❌ Keine Ticket-Panels gefunden.", ephemeral=True)
    
    panels = config[guild_id]["ticket_panels"]
    target_panel = None
    target_index = -1
    
    for i, p in enumerate(panels):
        if str(p["message_id"]) == message_id:
            target_panel = p
            target_index = i
            break
            
    if target_index == -1:
        return await interaction.response.send_message("❌ Dieses Panel existiert nicht in der Konfiguration.", ephemeral=True)
    
    # 1. Aus Config entfernen
    panels.pop(target_index)
    save_config(config)
    
    # 2. Nachricht in Discord löschen
    try:
        channel = interaction.guild.get_channel(target_panel["channel_id"]) or await interaction.guild.fetch_channel(target_panel["channel_id"])
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()
        await interaction.response.send_message(f"✅ Ticket-Panel (ID: {message_id}) wurde gelöscht.", ephemeral=True)
    except discord.NotFound:
        await interaction.response.send_message("✅ Panel wurde aus der Config gelöscht (Nachricht wurde bereits gelöscht).", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"⚠️ Aus Config gelöscht, aber Fehler beim Löschen der Discord-Nachricht: {e}", ephemeral=True)

@bot.tree.command(name="ticket_category_edit", description="Weist einer Ticket-Kategorie spezifische Supporter-Rollen zu")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    message_id="Wähle das Panel aus der Liste",
    kategorie_name="Wähle die Kategorie aus der Liste",
    neue_rollen="Rollen, die NUR diese Kategorie sehen sollen (z.B. @Technik)"
)
async def ticket_category_edit(interaction: discord.Interaction, message_id: str, kategorie_name: str, neue_rollen: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    role_ids = extract_role_ids(neue_rollen)
    
    if not role_ids:
        return await interaction.response.send_message("❌ Bitte gib mindestens eine gültige Rolle an.", ephemeral=True)

    if guild_id not in config or "ticket_panels" not in config[guild_id]:
        return await interaction.response.send_message("❌ Keine Ticket-Panels für diesen Server konfiguriert.", ephemeral=True)
    
    target_panel = None
    for panel in config[guild_id]["ticket_panels"]:
        if str(panel["message_id"]) == message_id:
            target_panel = panel
            break
            
    if not target_panel:
        return await interaction.response.send_message("❌ Panel nicht gefunden.", ephemeral=True)
    
    found = False
    for cat in target_panel["categories"]:
        if cat["value"].lower() == kategorie_name.lower():
            cat["supporter_role_ids"] = role_ids
            found = True
            break
            
    if not found:
        return await interaction.response.send_message(f"❌ Kategorie '{kategorie_name}' nicht im Panel gefunden.", ephemeral=True)
    
    save_config(config)
    
    try:
        channel = interaction.guild.get_channel(target_panel["channel_id"]) or await interaction.guild.fetch_channel(target_panel["channel_id"])
        message = await channel.fetch_message(int(message_id))
        panel_supp_ids = target_panel.get("supporter_role_ids", [])
        new_view = TicketView(target_panel["categories"], panel_supp_ids)
        
        await message.edit(view=new_view)
        bot.add_view(new_view)
        
        await interaction.response.send_message(f"✅ Kategorie **{kategorie_name}** wurde aktualisiert.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Fehler beim Aktualisieren der Nachricht: {e}", ephemeral=True)

# Autocomplete für Panel-Auswahl
@ticket_category_edit.autocomplete("message_id")
@ticket_edit.autocomplete("message_id")
@ticket_delete.autocomplete("message_id")
async def ticket_panel_autocomplete(interaction: discord.Interaction, current: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    
    choices = []
    for p in panels:
        mid = str(p["message_id"])
        created = p.get("created_at", "Unbekannt")
        channel = interaction.guild.get_channel(p["channel_id"])
        channel_name = channel.name if channel else "???"
        title = p.get("title", "Support")
        
        label = f"{mid} | {created} | {title} | #{channel_name}"
        
        if current.lower() in label.lower():
            choices.append(app_commands.Choice(name=label[:100], value=mid))
            
    return choices[:25]

@ticket_category_edit.autocomplete("kategorie_name")
async def ticket_cat_autocomplete(interaction: discord.Interaction, current: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    selected_mid = interaction.namespace.message_id
    
    choices = []
    for p in panels:
        if selected_mid and str(p["message_id"]) != selected_mid:
            continue
            
        for cat in p.get("categories", []):
            name = cat["value"]
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name[:100], value=name))
    
    final_choices = []
    seen = set()
    for c in choices:
        if c.name not in seen:
            final_choices.append(c)
            seen.add(c.name)

    return final_choices[:25]

# --- BASIS COMMANDS ---

@bot.tree.command(name="ping", description="Zeigt die aktuelle Verbindungslatenz des Bots an")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online als {bot.user}')
    
    config = load_config()
    pres = config.get("bot_presence")
    if pres:
        status_val = pres.get("status", "online")
        d_status = discord.Status.online
        if status_val == "idle": d_status = discord.Status.idle
        elif status_val == "dnd": d_status = discord.Status.dnd
        elif status_val == "invisible": d_status = discord.Status.invisible
        
        t_val = pres.get("type", "playing")
        text = pres.get("text", "")
        url = pres.get("url", "https://twitch.tv/discord")
        
        act = None
        if t_val == "playing": act = discord.Game(name=text)
        elif t_val == "streaming": act = discord.Streaming(name=text, url=url)
        elif t_val == "listening": act = discord.Activity(type=discord.ActivityType.listening, name=text)
        elif t_val == "watching": act = discord.Activity(type=discord.ActivityType.watching, name=text)
        
        await bot.change_presence(status=d_status, activity=act)

if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
    else: print("Fehler: DISCORD_TOKEN fehlt!")