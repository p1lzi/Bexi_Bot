import discord
from discord import app_commands
from discord.ext import commands, tasks
import re
import json
import os
import asyncio
import shutil
import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# HINWEIS: Installiere 'static-ffmpeg' in deiner .venv via: pip install static-ffmpeg
try:
    from static_ffmpeg import run
    ffmpeg_exe, ffprobe_exe = run.get_or_fetch_platform_executables_else_raise()
    HAS_STATIC_FFMPEG = True
except ImportError:
    HAS_STATIC_FFMPEG = False

# --- SETUP DATEIEN ---
TOKEN = os.getenv('DISCORD_TOKEN')
CONFIG_FILE = 'config.json'
WHITELIST_FILE = 'whitelist.json'
BACKUP_DIR = 'config_backups'
MAX_BACKUPS = 3

def create_config_backup(user: discord.User = None, guild: discord.Guild = None):
    """Erstellt ein Backup der config.json im Backup-Ordner (max. 3 Backups) und loggt die Änderung."""
    if not os.path.exists(CONFIG_FILE):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp_readable = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    backup_path = os.path.join(BACKUP_DIR, f"config_backup_{timestamp}.json")
    shutil.copy2(CONFIG_FILE, backup_path)

    # Alte Backups löschen, nur die neuesten MAX_BACKUPS behalten
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("config_backup_") and f.endswith(".json")]
    )
    while len(backups) > MAX_BACKUPS:
        os.remove(os.path.join(BACKUP_DIR, backups.pop(0)))

    # Changelog schreiben
    log_path = os.path.join(BACKUP_DIR, "changelog.log")
    user_info = f"{user} (ID: {user.id})" if user else "Unbekannt"
    guild_info = f"{guild.name} (ID: {guild.id})" if guild else "Unbekannt"
    log_entry = (
        f"[{timestamp_readable}]\n"
        f"  Geändert von : {user_info}\n"
        f"  Server       : {guild_info}\n"
        f"  Backup-Datei : config_backup_{timestamp}.json\n"
        f"{'-' * 50}\n"
    )
    with open(log_path, 'a', encoding='utf-8') as log_file:
        log_file.write(log_entry)

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

def load_whitelist():
    """Lädt die Liste der erlaubten Domains aus der JSON-Datei."""
    if os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("allowed_domains", ["tenor.com"])
        except (json.JSONDecodeError, KeyError):
            return ["tenor.com"]
    return ["tenor.com"]

def save_whitelist(domains):
    """Speichert die Liste der erlaubten Domains in die JSON-Datei."""
    with open(WHITELIST_FILE, 'w', encoding='utf-8') as f:
        json.dump({"allowed_domains": list(set(domains))}, f, indent=4)

def format_discord_text(text: str):
    if not text:
        return ""
    text = text.replace("/n", "\n")
    return text

def extract_role_ids(input_str: str):
    """Extrahiert alle Rollen-IDs aus einem String (Erwähnungen oder reine IDs)."""
    return [int(id_str) for id_str in re.findall(r'\d+', input_str)]

async def send_log(guild: discord.Guild, title: str, description: str, color: discord.Color, target_user: discord.Member, moderator: discord.Member = None, reason: str = None):
    """Hilfsfunktion zum Senden von Logs in den konfigurierten Log-Kanal."""
    config = load_config()
    gid = str(guild.id)
    log_channel_id = config.get(gid, {}).get("log_channel_id")
    
    if log_channel_id:
        channel = guild.get_channel(log_channel_id)
        if channel:
            embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.add_field(name="Nutzer", value=f"{target_user.mention} ({target_user.id})", inline=True)
            
            if moderator:
                embed.add_field(name="Moderator", value=f"{moderator.mention}", inline=True)
            if reason:
                embed.add_field(name="Grund", value=reason, inline=False)
                
            embed.set_footer(text=f"Server: {guild.name}")
            try:
                await channel.send(embed=embed)
            except:
                pass

# --- NEU: SELF ROLE SYSTEM ---
class SelfRoleButton(discord.ui.Button):
    def __init__(self, label, role_id, emoji=None):
        # Wir nutzen die role_id als custom_id, um sie beim Neustart zu identifizieren
        super().__init__(label=label, style=discord.ButtonStyle.secondary, emoji=emoji, custom_id=f"selfrole_{role_id}")
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("❌ Diese Rolle existiert nicht mehr.", ephemeral=True)
        
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"✅ Rolle **{role.name}** wurde entfernt.", ephemeral=True)
        else:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"✅ Rolle **{role.name}** wurde hinzugefügt.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Ich habe nicht genug Rechte, um diese Rolle zu vergeben.", ephemeral=True)

class SelfRoleView(discord.ui.View):
    def __init__(self, roles_data):
        super().__init__(timeout=None)
        for data in roles_data:
            self.add_item(SelfRoleButton(label=data['label'], role_id=data['role_id'], emoji=data.get('emoji')))

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
        
        thread = interaction.channel
        closer = interaction.user

        creator_id = self.get_creator_id(interaction)
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = discord.Embed(
                    title="🔒 Ticket Geschlossen",
                    description=(
                        f"Dein Ticket in **{interaction.guild.name}** wurde geschlossen und archiviert.\n\n"
                        f"**Geschlossen von:** {closer.mention} ({closer})\n"
                        f"**Ticket:** [{thread.name}]({thread.jump_url})"
                    ),
                    color=discord.Color.red()
                )
                dm_embed.set_footer(text=f"Server: {interaction.guild.name}")
                dm_embed.timestamp = discord.utils.utcnow()
                await send_dm(creator, "", dm_embed)

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
        guild = interaction.guild
        guild_id = str(guild.id)
        config = load_config()
        
        if guild_id not in config: config[guild_id] = {}
        
        if "category_counters" not in config[guild_id]:
            config[guild_id]["category_counters"] = {}
        
        if selected_value not in config[guild_id]["category_counters"]:
            config[guild_id]["category_counters"][selected_value] = 0
            
        config[guild_id]["category_counters"][selected_value] += 1
        ticket_id = config[guild_id]["category_counters"][selected_value]
        
        formatted_id = f"{ticket_id:04d}"
        
        # Bestimme die Ziel-Rollen für diese Kategorie
        target_role_ids = self.supporter_role_ids
        for cat in self.categories_full_data:
            if cat['value'] == selected_value and cat.get('supporter_role_ids'):
                target_role_ids = cat['supporter_role_ids']
                break

        main_category_name = "TICKETS"
        category = discord.utils.get(guild.categories, name=main_category_name)
        
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True, 
                    send_messages=False, 
                    add_reactions=False, 
                    create_public_threads=False, 
                    create_private_threads=False,
                    send_messages_in_threads=True 
                ),
                guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, manage_roles=True)
            }
            category = await guild.create_category(name=main_category_name, overwrites=overwrites)

        config[guild_id].setdefault("category_channels", {})
        cached_channel_id = config[guild_id]["category_channels"].get(selected_value)
        target_channel = None

        if cached_channel_id:
            target_channel = guild.get_channel(cached_channel_id)

        if not target_channel:
            channel_name = f"{selected_value.lower().replace(' ', '-')}-tickets"
            target_channel = discord.utils.get(category.text_channels, name=channel_name)
            
            if not target_channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=True, 
                        send_messages=False, 
                        add_reactions=False,
                        use_application_commands=False
                    ),
                    guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, send_messages=True)
                }
                for rid in target_role_ids:
                    role = guild.get_role(rid)
                    if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_threads=True)

                target_channel = await guild.create_text_channel(
                    name=channel_name, 
                    category=category, 
                    overwrites=overwrites,
                    topic=f"Zentraler Kanal für {selected_value} Anfragen."
                )
                
                info_embed = discord.Embed(
                    title=f"Ticket-Kanal: {selected_value}",
                    description=(
                        f"In diesem Kanal werden alle Tickets der Kategorie **{selected_value}** erstellt.\n\n"
                        "⚠️ **Hinweis:** Hier kann nicht geschrieben werden. Dein Ticket wird als privater Thread unterhalb "
                        "einer Nachricht in diesem Kanal erstellt."
                    ),
                    color=discord.Color.blue()
                )
                await target_channel.send(embed=info_embed)
            
            config[guild_id]["category_channels"][selected_value] = target_channel.id

        save_config(config)

        clean_username = interaction.user.display_name.replace(' ', '-').lower()
        thread_name = f"{selected_value.lower()[:5]}-{formatted_id}-{clean_username}"

        thread = await target_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread
        )
        
        await interaction.response.send_message(
            f"✅ Dein Ticket **#{formatted_id}** ({selected_value}) wurde erstellt: {thread.mention}\n"
            f"[Klicke hier, um zum Ticket zu springen]({thread.jump_url})", 
            ephemeral=True
        )
        
        await thread.add_user(interaction.user)
        
        added_members = set()
        for rid in target_role_ids:
            base_role = guild.get_role(rid)
            if base_role:
                for member in base_role.members:
                    if member.bot or member.id in added_members:
                        continue
                    try:
                        await thread.add_user(member)
                        added_members.add(member.id)
                    except:
                        pass
        
        embed = discord.Embed(
            title=f"{selected_value}-Ticket #{formatted_id}",
            description=f"Hallo {interaction.user.mention}!\n\nDein Ticket wurde erfolgreich erstellt.",
            color=discord.Color.green()
        )
        embed.add_field(name="Ticket-Nummer", value=f"#{formatted_id}", inline=True)
        embed.add_field(name="Kategorie", value=selected_value, inline=True)
        embed.add_field(name="Info", value="Bitte beschreibe dein Anliegen so detailliert wie möglich.", inline=False)
        embed.set_footer(text=f"User-ID: {interaction.user.id}")
        
        await thread.send(embed=embed, view=TicketControlView())

        dm_embed = discord.Embed(
            title=f"Ticket #{formatted_id} ({selected_value}) erstellt",
            description=f"Du hast erfolgreich ein Ticket in **{interaction.guild.name}** eröffnet.\n\n**Kategorie:** {selected_value}\n\n[Klicke hier, um zum Ticket zu gelangen]({thread.jump_url})",
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
        intents.guilds = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        config = load_config()
        for guild_id_str, data in config.items():
            # Persistent Verify Views
            for panel in data.get("verify_panels", []):
                self.add_view(VerifyView(panel["role_id"]))
            # Persistent Ticket Views
            for t_panel in data.get("ticket_panels", []):
                supp_ids = t_panel.get("supporter_role_ids")
                if not supp_ids:
                    old_id = t_panel.get("supporter_role_id")
                    supp_ids = [old_id] if old_id else []
                self.add_view(TicketView(t_panel["categories"], supp_ids))
            # Persistent Self-Role Views
            for s_panel in data.get("selfrole_panels", []):
                self.add_view(SelfRoleView(s_panel["roles"]))
                
        self.add_view(TicketControlView())
        
        await self.tree.sync()
        print("🌐 Slash Commands wurden global synchronisiert.")

    async def on_message(self, message: discord.Message):
        if message.author.bot: return
        
        link_pattern = r'(https?://\S+|www\.\S+)'
        links = re.findall(link_pattern, message.content)
        
        if links and not message.author.guild_permissions.administrator:
            whitelist = load_whitelist()
            for link in links:
                try:
                    full_url = link if link.startswith("http") else f"http://{link}"
                    domain = urlparse(full_url).netloc.lower()
                    if domain.startswith("www."): domain = domain[4:]
                    
                    is_allowed = False
                    for allowed in whitelist:
                        if allowed.lower() in domain:
                            is_allowed = True
                            break
                    
                    if not is_allowed:
                        try:
                            await message.delete()
                            await send_log(
                                message.guild, 
                                "🚫 Link gelöscht", 
                                f"In Kanal {message.channel.mention} wurde ein unerlaubter Link entfernt.\n**Inhalt:** `{message.content[:1000]}`", 
                                discord.Color.red(), 
                                message.author
                            )
                            allowed_str = ", ".join(whitelist)
                            await message.channel.send(
                                f"⚠️ {message.author.mention}, dieser Link ist nicht erlaubt! Erlaubte Seiten: `{allowed_str}`", 
                                delete_after=6
                            )
                            return 
                        except discord.Forbidden: pass
                except:
                    continue
                    
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

# --- PIONIER ROLLE COMMAND ---

@bot.tree.command(name="setup_pioneer_role", description="Vergibt eine Rolle an die ersten 100 Mitglieder des Servers")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(rolle="Die Rolle, die den ersten 100 Mitgliedern (nach Beitrittsdatum) vergeben wird – z.B. @Pioneer")
async def setup_pioneer_role(interaction: discord.Interaction, rolle: discord.Role):
    """Ermittelt die ersten 100 Mitglieder und weist ihnen die gewählte Rolle zu."""
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
            except discord.Forbidden:
                errors += 1
            except Exception:
                errors += 1
                
    await interaction.followup.send(
        f"✅ Analyse abgeschlossen!\n"
        f"• Rolle: {rolle.mention}\n"
        f"• Neu zugewiesen: **{assigned_count}**\n"
        f"• Fehler (z.B. fehlende Rechte): **{errors}**\n\n", 
        ephemeral=True
    )

# --- NEU: SELFROLE SETUP COMMAND ---

@bot.tree.command(name="setup_selfrole", description="Erstellt ein Panel, an dem Nutzer sich selbst Rollen geben können")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    titel="Überschrift des Self-Role Panels, z.B. 'Wähle deine Rollen'",
    beschreibung="Erklärungstext unter dem Titel. Zeilenumbruch mit /n möglich, z.B. 'Klicke einen Button/nfür deine Rolle.'",
    rollen_config="Format: \"Emoji Label|RollenID\", \"Emoji Label|RollenID\" – Beispiel: \"🎮 Gamer|123456789\", \"🎵 Musik|987654321\""
)
async def setup_selfrole(interaction: discord.Interaction, titel: str, beschreibung: str, rollen_config: str):
    """Erstellt ein Panel mit Buttons für Self-Roles."""
    guild_id = str(interaction.guild_id)
    
    # Extrahiere Konfiguration (ähnl. wie Ticket-Setup)
    raw_list = re.findall(r'"([^"]*)"', rollen_config)
    if not raw_list: raw_list = [c.strip() for c in rollen_config.split(",") if c.strip()]
    
    formatted_roles = []
    for item in raw_list:
        parts = item.split("|")
        label_part = parts[0].strip()
        role_id_part = parts[1].strip() if len(parts) > 1 else None
        
        if not role_id_part: continue
        
        role_id = int(re.search(r'\d+', role_id_part).group())
        
        emoji = None
        match = re.search(r'^([^\x00-\x7F]|\W+)\s*(.*)', label_part)
        if match:
            emoji = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else emoji
        else:
            label = label_part

        formatted_roles.append({
            "label": label,
            "role_id": role_id,
            "emoji": emoji
        })

    if not formatted_roles:
        return await interaction.response.send_message("❌ Ungültiges Format. Beispiel: `\"⭐ Star|12345\", \"🎮 Gamer|67890\"`", ephemeral=True)

    embed = discord.Embed(
        title=titel, 
        description=format_discord_text(beschreibung), 
        color=discord.Color.blue()
    )
    
    view = SelfRoleView(formatted_roles)
    message = await interaction.channel.send(embed=embed, view=view)
    
    # In Config speichern für Persistenz
    config = load_config()
    if guild_id not in config: config[guild_id] = {}
    config[guild_id].setdefault("selfrole_panels", []).append({
        "message_id": message.id,
        "roles": formatted_roles
    })
    save_config(config)
    
    await interaction.response.send_message("✅ Self-Role Panel wurde erstellt!", ephemeral=True)

# --- WHITELIST MANAGEMENT COMMAND ---

@bot.tree.command(name="whitelist", description="Verwaltet die Liste der erlaubten Link-Domains")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(aktion=[
    app_commands.Choice(name="➕ Hinzufügen – Domain zur Whitelist hinzufügen", value="add"),
    app_commands.Choice(name="➖ Entfernen – Domain von der Whitelist löschen", value="remove"),
    app_commands.Choice(name="📋 Liste anzeigen – Alle erlaubten Domains anzeigen", value="list")
])
@app_commands.describe(domain="Domain ohne https:// und www – Beispiel: youtube.com | Bei 'Liste anzeigen' kann leer gelassen werden")
async def whitelist_cmd(interaction: discord.Interaction, aktion: app_commands.Choice[str], domain: str = None):
    whitelist = load_whitelist()
    
    if aktion.value == "list":
        domains_str = "\n".join([f"• {d}" for d in whitelist]) if whitelist else "Keine Domains erlaubt."
        embed = discord.Embed(title="🛡️ Erlaubte Domains", description=domains_str, color=discord.Color.blue())
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if not domain:
        return await interaction.response.send_message("❌ Bitte gib eine Domain an.", ephemeral=True)
    
    clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

    if aktion.value == "add":
        if clean_domain in whitelist:
            await interaction.response.send_message(f"ℹ️ `{clean_domain}` ist bereits auf der Whitelist.", ephemeral=True)
        else:
            whitelist.append(clean_domain)
            save_whitelist(whitelist)
            await interaction.response.send_message(f"✅ `{clean_domain}` wurde zur Whitelist hinzugefügt.", ephemeral=True)
            
    elif aktion.value == "remove":
        if clean_domain in whitelist:
            whitelist.remove(clean_domain)
            save_whitelist(whitelist)
            await interaction.response.send_message(f"✅ `{clean_domain}` wurde von der Whitelist entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ `{clean_domain}` ist nicht in der Whitelist.", ephemeral=True)

# --- MODERATION COMMANDS ---

@bot.tree.command(name="ban", description="Bannt ein Mitglied permanent vom Server")
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(nutzer="Das Mitglied, das gebannt werden soll – per @Erwähnung oder Klick auswählen", grund="Sichtbarer Grund im Log-Kanal, z.B. 'Spam', 'Toxisches Verhalten' (optional)")
async def ban(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    try:
        await nutzer.ban(reason=grund)
        await interaction.response.send_message(f"✅ **{nutzer}** wurde gebannt. Grund: {grund}", ephemeral=True)
        await send_log(interaction.guild, "🔨 Mitglied Gebannt", f"Ein Nutzer wurde permanent vom Server ausgeschlossen.", discord.Color.red(), nutzer, interaction.user, grund)
    except:
        await interaction.response.send_message("❌ Fehler beim Bannen.", ephemeral=True)

@bot.tree.command(name="kick", description="Kickt ein Mitglied vom Server")
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(nutzer="Das Mitglied, das gekickt werden soll – per @Erwähnung oder Klick auswählen", grund="Sichtbarer Grund im Log-Kanal, z.B. 'Regelverstoß' (optional)")
async def kick(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    try:
        await nutzer.kick(reason=grund)
        await interaction.response.send_message(f"✅ **{nutzer}** wurde gekickt. Grund: {grund}", ephemeral=True)
        await send_log(interaction.guild, "👢 Mitglied Gekickt", f"Ein Nutzer wurde vom Server gekickt.", discord.Color.orange(), nutzer, interaction.user, grund)
    except:
        await interaction.response.send_message("❌ Fehler beim Kicken.", ephemeral=True)

@bot.tree.command(name="timeout", description="Versetzt ein Mitglied für eine bestimmte Zeit in den Timeout")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(nutzer="Das Mitglied, das stumm gestellt werden soll – per @Erwähnung auswählen", minuten="Dauer in Minuten – z.B. 10, 60, 1440 (= 1 Tag), max. 40320 (28 Tage)", grund="Sichtbarer Grund im Log-Kanal (optional)")
async def timeout(interaction: discord.Interaction, nutzer: discord.Member, minuten: int, grund: str = "Kein Grund angegeben"):
    try:
        duration = datetime.timedelta(minutes=minuten)
        await nutzer.timeout(duration, reason=grund)
        await interaction.response.send_message(f"✅ **{nutzer}** ist nun für {minuten} Minuten im Timeout. Grund: {grund}", ephemeral=True)
        await send_log(interaction.guild, "⏳ Timeout Verhängt", f"Ein Nutzer wurde stummgeschaltet (Timeout für {minuten} Min).", discord.Color.light_grey(), nutzer, interaction.user, grund)
    except:
        await interaction.response.send_message("❌ Fehler beim Timeout.", ephemeral=True)

@bot.tree.command(name="warn", description="Verwarnt ein Mitglied und speichert den Warn")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(nutzer="Das Mitglied, das verwarnt werden soll – per @Erwähnung auswählen", grund="Grund der Verwarnung – wird dem Nutzer per DM und im Log angezeigt")
async def warn(interaction: discord.Interaction, nutzer: discord.Member, grund: str):
    config = load_config()
    gid = str(interaction.guild_id)
    uid = str(nutzer.id)
    
    if gid not in config: config[gid] = {}
    if "warns" not in config[gid]: config[gid]["warns"] = {}
    
    current_warns = config[gid]["warns"].get(uid, 0)
    new_warn_count = current_warns + 1
    config[gid]["warns"][uid] = new_warn_count
    save_config(config)

    embed = discord.Embed(title="Verwarnung", description=f"Du wurdest auf **{interaction.guild.name}** verwarnt.\n\n**Grund:** {grund}\n**Gesamt-Warns:** {new_warn_count}", color=discord.Color.orange())
    await send_dm(nutzer, "", embed)
    await interaction.response.send_message(f"✅ {nutzer.mention} wurde verwarnt. Grund: {grund} (Warns: {new_warn_count})", ephemeral=True)
    await send_log(interaction.guild, "⚠️ Verwarnung ausgesprochen", f"Ein Nutzer wurde verwarnt. (Warnung #{new_warn_count})", discord.Color.gold(), nutzer, interaction.user, grund)

@bot.tree.command(name="warn_edit", description="Bearbeitet oder löscht die Anzahl der Verwarnungen eines Nutzers")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(nutzer="Das Mitglied, dessen Warns angepasst werden sollen – per @Erwähnung auswählen", anzahl="Neue Gesamtanzahl der Warns – z.B. 2 zum Setzen oder 0 zum vollständigen Löschen")
async def warn_edit(interaction: discord.Interaction, nutzer: discord.Member, anzahl: int):
    if anzahl < 0:
        return await interaction.response.send_message("❌ Die Anzahl darf nicht negativ sein.", ephemeral=True)
        
    config = load_config()
    gid = str(interaction.guild_id)
    uid = str(nutzer.id)
    
    if gid not in config: config[gid] = {}
    if "warns" not in config[gid]: config[gid]["warns"] = {}
    
    alte_anzahl = config[gid]["warns"].get(uid, 0)
    config[gid]["warns"][uid] = anzahl
    save_config(config)
    
    msg = f"✅ Warns für {nutzer.mention} angepasst: **{alte_anzahl}** ➔ **{anzahl}**."
    if anzahl == 0:
        msg = f"✅ Alle Warns für {nutzer.mention} wurden gelöscht (auf 0 gesetzt)."
        
    await interaction.response.send_message(msg, ephemeral=True)
    await send_log(interaction.guild, "🔧 Warns bearbeitet", f"Die Anzahl der Verwarnungen wurde manuell geändert.", discord.Color.blue(), nutzer, interaction.user, f"Geändert von {alte_anzahl} auf {anzahl}")

@bot.tree.command(name="userinfo", description="Zeigt detaillierte Informationen über ein Mitglied an")
@app_commands.describe(nutzer="Das Mitglied, über das Infos angezeigt werden sollen – leer lassen für eigene Infos")
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

@bot.tree.command(name="set_log_channel", description="Legt den Kanal für Moderations-Logs fest")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(kanal="Der Textkanal, in dem alle Moderations-Logs erscheinen sollen – z.B. #mod-logs")
async def set_log_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config: config[gid] = {}
    config[gid]["log_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Log-Kanal wurde auf {kanal.mention} gesetzt.", ephemeral=True)

@bot.tree.command(name="set_welcome_channel", description="Legt den Kanal für Willkommensnachrichten fest")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(kanal="Der Textkanal, in dem neue Mitglieder begrüßt werden sollen – z.B. #willkommen")
async def set_welcome_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config: config[gid] = {}
    config[gid]["welcome_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Willkommens-Kanal auf {kanal.mention} gesetzt.", ephemeral=True)

@bot.tree.command(name="set_waiting_room", description="Konfiguriert den Warteraum für die Support-Musik")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(kanal="Der Sprachkanal, in dem Support-Musik abgespielt wird, wenn jemand wartet – z.B. 'Warteraum'")
async def set_waiting_room(interaction: discord.Interaction, kanal: discord.VoiceChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config: config[gid] = {}
    config[gid]["waiting_room_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Warteraum auf {kanal.mention} gesetzt.", ephemeral=True)

@bot.tree.command(name="setup_verify", description="Erstellt eine Nachricht mit einem Verifizierungs-Button")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(titel="Überschrift des Panels, z.B. 'Verifizierung'", beschreibung="Erklärungstext, z.B. 'Klicke den Button um Zugang zu erhalten.' Zeilenumbruch mit /n", rolle="Die Rolle, die beim Klick auf den Button vergeben wird – z.B. @Verifiziert")
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
@app_commands.describe(
    status="Online-Status des Bots – z.B. Online, Idle, DnD oder Unsichtbar",
    aktivitaet_typ="Art der Aktivität – Spielt / Streamt / Hört zu / Schaut",
    text="Anzeigetext der Aktivität – z.B. 'Minecraft' oder 'euren Server'",
    stream_url="Nur bei 'Streamt' nötig – vollständige Twitch-URL, z.B. https://twitch.tv/deinname"
)
@app_commands.choices(status=[
    app_commands.Choice(name="🟢 Online – Bot erscheint als verfügbar", value="online"),
    app_commands.Choice(name="🌙 Abwesend (Idle) – Bot erscheint als abwesend", value="idle"),
    app_commands.Choice(name="🔴 Bitte nicht stören (DnD) – rotes Symbol, keine Benachrichtigungen", value="dnd"),
    app_commands.Choice(name="⚫ Unsichtbar (Offline) – Bot wirkt offline, läuft aber", value="invisible")
])
@app_commands.choices(aktivitaet_typ=[
    app_commands.Choice(name="🎮 Spielt – zeigt 'Spielt [Text]' unter dem Namen", value="playing"),
    app_commands.Choice(name="🎥 Streamt – zeigt 'Streamt [Text]' mit Link (Stream-URL pflichtfeld)", value="streaming"),
    app_commands.Choice(name="🎵 Hört zu – zeigt 'Hört [Text]' unter dem Namen", value="listening"),
    app_commands.Choice(name="📺 Schaut – zeigt 'Schaut [Text]' unter dem Namen", value="watching")
])
async def status_config(interaction: discord.Interaction, status: app_commands.Choice[str], aktivitaet_typ: app_commands.Choice[str], text: str, stream_url: str = "https://twitch.tv/discord"):
    discord_status = getattr(discord.Status, status.value, discord.Status.online)
    activity = None
    if aktivitaet_typ.value == "playing": activity = discord.Game(name=text)
    elif aktivitaet_typ.value == "streaming": activity = discord.Streaming(name=text, url=stream_url)
    elif aktivitaet_typ.value == "listening": activity = discord.Activity(type=discord.ActivityType.listening, name=text)
    elif aktivitaet_typ.value == "watching": activity = discord.Activity(type=discord.ActivityType.watching, name=text)
    await bot.change_presence(status=discord_status, activity=activity)
    config = load_config()
    config["bot_presence"] = {"status": status.value, "type": aktivitaet_typ.value, "text": text, "url": stream_url}
    save_config(config)
    await interaction.response.send_message(f"✅ Status aktualisiert.", ephemeral=True)

# --- TICKET SETUP COMMANDS ---

@bot.tree.command(name="setup_tickets", description="Erstellt ein neues Support-Ticket-Panel")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    supporter_rollen="Rollen, die alle Tickets sehen dürfen – als @Erwähnung oder ID, mehrere mit Leerzeichen trennen, z.B. @Support @Moderator",
    kategorien="Ticket-Kategorien – Format: \"Emoji Name|Beschreibung\", \"Emoji Name\" – Beispiel: \"🔧 Technik|Technische Probleme\", \"💬 Allgemein\""
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

@bot.tree.command(name="ticket_edit", description="Bearbeitet ein bestehendes Ticket-Panel")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    message_id="ID der Panel-Nachricht – wird nach Eingabe als Autocomplete-Liste angezeigt",
    titel="Neuer Titel des Panels (optional) – leer lassen um nicht zu ändern",
    beschreibung="Neuer Beschreibungstext (optional) – Zeilenumbruch mit /n",
    farbe="Neue Randfarbe als Hex-Code (optional) – Beispiel: #FF0000 für Rot"
)
async def ticket_edit(interaction: discord.Interaction, message_id: str, titel: str = None, beschreibung: str = None, farbe: str = None):
    guild_id = str(interaction.guild_id)
    config = load_config()
    target_panel = next((p for p in config.get(guild_id, {}).get("ticket_panels", []) if str(p.get("message_id", "")) == message_id), None)
    if not target_panel: return await interaction.response.send_message("❌ Panel nicht gefunden.", ephemeral=True)
    try:
        channel = interaction.guild.get_channel(target_panel["channel_id"]) or await interaction.guild.fetch_channel(target_panel["channel_id"])
        msg = await channel.fetch_message(int(message_id))
        embed = msg.embeds[0]
        if titel: embed.title = titel; target_panel["title"] = titel
        if beschreibung: embed.description = format_discord_text(beschreibung)
        if farbe: embed.color = discord.Color(int(farbe.replace("#", ""), 16))
        await msg.edit(embed=embed)
        save_config(config)
        await interaction.response.send_message("✅ Panel aktualisiert.", ephemeral=True)
    except Exception as e: await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)

@bot.tree.command(name="ticket_delete", description="Löscht ein Ticket-Panel")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(message_id="ID des zu löschenden Panels – wird als Autocomplete-Liste angezeigt")
async def ticket_delete(interaction: discord.Interaction, message_id: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    target = next((p for p in panels if str(p.get("message_id", "")) == message_id), None)
    if not target: return await interaction.response.send_message("❌ Nicht in Config.", ephemeral=True)
    panels.remove(target); save_config(config)
    try:
        channel = interaction.guild.get_channel(target["channel_id"]) or await interaction.guild.fetch_channel(target["channel_id"])
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()
        await interaction.response.send_message("✅ Gelöscht.", ephemeral=True)
    except: await interaction.response.send_message("✅ Aus Config entfernt.", ephemeral=True)

@bot.tree.command(name="ticket_category_edit", description="Weist einer Ticket-Kategorie spezifische Supporter-Rollen zu")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    message_id="ID des Ticket-Panels – wird als Autocomplete-Liste angezeigt",
    kategorie_name="Name der Kategorie, die bearbeitet werden soll – wird als Autocomplete-Liste angezeigt",
    neue_rollen="Neue Supporter-Rollen für diese Kategorie – als @Erwähnung oder ID, mehrere mit Leerzeichen, z.B. @Support @Admin"
)
async def ticket_category_edit(interaction: discord.Interaction, message_id: str, kategorie_name: str, neue_rollen: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    role_ids = extract_role_ids(neue_rollen)
    panel = next((p for p in config.get(guild_id, {}).get("ticket_panels", []) if str(p.get("message_id", "")) == message_id), None)
    if not panel: return await interaction.response.send_message("❌ Panel nicht gefunden.", ephemeral=True)
    cat = next((c for c in panel["categories"] if c["value"].lower() == kategorie_name.lower()), None)
    if not cat: return await interaction.response.send_message("❌ Kategorie nicht gefunden.", ephemeral=True)
    cat["supporter_role_ids"] = role_ids; save_config(config)
    try:
        channel = interaction.guild.get_channel(panel["channel_id"]) or await interaction.guild.fetch_channel(panel["channel_id"])
        msg = await channel.fetch_message(int(message_id))
        await msg.edit(view=TicketView(panel["categories"], panel.get("supporter_role_ids", [])))
        await interaction.response.send_message("✅ Kategorie-Rollen aktualisiert.", ephemeral=True)
    except Exception as e: await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)

@ticket_category_edit.autocomplete("message_id")
@ticket_edit.autocomplete("message_id")
@ticket_delete.autocomplete("message_id")
async def ticket_panel_autocomplete(interaction: discord.Interaction, current: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    choices = []
    for p in panels:
        mid = p.get("message_id")
        if not mid:
            continue  # Überspringe fehlerhafte Einträge ohne message_id
        title = p.get("title", "Ticket")
        mid_str = str(mid)
        if current.lower() in mid_str.lower() or current.lower() in title.lower():
            choices.append(app_commands.Choice(name=f"{mid_str} | {title}", value=mid_str))
    return choices[:25]

@ticket_category_edit.autocomplete("kategorie_name")
async def ticket_cat_autocomplete(interaction: discord.Interaction, current: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    mid = interaction.namespace.message_id
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    choices = []
    for p in panels:
        panel_mid = p.get("message_id")
        if not panel_mid:
            continue  # Überspringe fehlerhafte Einträge ohne message_id
        if not mid or str(panel_mid) == mid:
            for cat in p.get("categories", []):
                cat_value = cat.get("value", "")
                if cat_value and current.lower() in cat_value.lower():
                    choices.append(app_commands.Choice(name=cat_value, value=cat_value))
    return choices[:25]

# --- BASIS COMMANDS ---

@bot.tree.command(name="ping", description="Zeigt die Latenz an")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(bot.latency * 1000)}ms", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online als {bot.user}')
    if not os.path.exists(WHITELIST_FILE): save_whitelist(["tenor.com", "giphy.com"])
    config = load_config()
    pres = config.get("bot_presence")
    if pres:
        status_val = pres.get("status", "online")
        d_status = getattr(discord.Status, status_val, discord.Status.online)
        t_val = pres.get("type", "playing")
        text = pres.get("text", "")
        url = pres.get("url", "https://twitch.tv/discord")
        act = None
        if t_val == "playing": act = discord.Game(name=text)
        elif t_val == "streaming": act = discord.Streaming(name=text, url=url)
        elif t_val == "listening": act = discord.Activity(type=discord.ActivityType.listening, name=text)
        elif t_val == "watching": act = discord.Activity(type=discord.ActivityType.watching, name=text)
        await bot.change_presence(status=d_status, activity=act)


# --- CONFIG EXPORT / IMPORT ---

@bot.tree.command(name="config_export", description="Sendet die aktuelle config.json als Datei zum Herunterladen")
@app_commands.default_permissions(administrator=True)
async def config_export(interaction: discord.Interaction):
    if not os.path.exists(CONFIG_FILE):
        return await interaction.response.send_message("❌ Keine config.json gefunden.", ephemeral=True)
    await interaction.response.send_message(
        "📤 Hier ist die aktuelle `config.json`:",
        file=discord.File(CONFIG_FILE),
        ephemeral=True
    )

@bot.tree.command(name="config_import", description="Lädt eine neue config.json hoch und wendet sie sofort an")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(datei="Die neue config.json Datei – vorher per /config_export herunterladen, bearbeiten und hier hochladen")
async def config_import(interaction: discord.Interaction, datei: discord.Attachment):
    if not datei.filename.endswith(".json"):
        return await interaction.response.send_message("❌ Bitte lade eine `.json`-Datei hoch.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    try:
        content = await datei.read()
        new_config = json.loads(content)
    except json.JSONDecodeError:
        return await interaction.followup.send("❌ Die Datei enthält kein gültiges JSON.", ephemeral=True)

    # Backup der alten Config anlegen (mit Nutzer & Server-Info)
    create_config_backup(user=interaction.user, guild=interaction.guild)

    # Neue Config speichern
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_config, f, indent=4)


    # --- Live-Reload aller Config-abhängigen Bereiche ---
    applied = []

    # 1. Bot-Presence / Status aktualisieren
    pres = new_config.get("bot_presence")
    if pres:
        status_val = pres.get("status", "online")
        d_status = getattr(discord.Status, status_val, discord.Status.online)
        t_val = pres.get("type", "playing")
        text = pres.get("text", "")
        url = pres.get("url", "https://twitch.tv/discord")
        act = None
        if t_val == "playing":    act = discord.Game(name=text)
        elif t_val == "streaming": act = discord.Streaming(name=text, url=url)
        elif t_val == "listening": act = discord.Activity(type=discord.ActivityType.listening, name=text)
        elif t_val == "watching":  act = discord.Activity(type=discord.ActivityType.watching, name=text)
        await bot.change_presence(status=d_status, activity=act)
        applied.append("✅ Bot-Status")

    # 2. Persistent Views neu registrieren (Verify, Tickets, Self-Roles)
    for guild_id_str, data in new_config.items():
        if not isinstance(data, dict):
            continue
        for panel in data.get("verify_panels", []):
            bot.add_view(VerifyView(panel["role_id"]))
        for t_panel in data.get("ticket_panels", []):
            supp_ids = t_panel.get("supporter_role_ids") or ([t_panel["supporter_role_id"]] if t_panel.get("supporter_role_id") else [])
            bot.add_view(TicketView(t_panel["categories"], supp_ids))
        for s_panel in data.get("selfrole_panels", []):
            bot.add_view(SelfRoleView(s_panel["roles"]))
    applied.append("✅ Persistent Views")

    applied_str = "\n".join(applied)
    await interaction.followup.send(
        f"✅ Neue `config.json` wurde gespeichert & live angewendet (Backup angelegt).\n\n{applied_str}",
        ephemeral=True
    )

if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
    else: print("Fehler: DISCORD_TOKEN fehlt!")