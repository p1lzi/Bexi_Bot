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

<<<<<<< Updated upstream
async def send_log(guild: discord.Guild, title: str, description: str, color: discord.Color, target_user: discord.Member, moderator: discord.Member = None, reason: str = None):
    """Hilfsfunktion zum Senden von Logs in den konfigurierten Log-Kanal."""
=======
def now_timestamp():
    return datetime.datetime.now(datetime.timezone.utc)

def short_time():
    return discord.utils.format_dt(datetime.datetime.now(datetime.timezone.utc), style="f")

# ─────────────────────────────────────────────
#  EMBED BUILDER HELPERS
# ─────────────────────────────────────────────

def make_dm_embed(
    title: str,
    description: str,
    color: discord.Color,
    guild: discord.Guild = None,
    mention_name: str = None,
    fields: list = None,
    jump_url: str = None,
    footer_system: str = None
) -> discord.Embed:
    """
    Erstellt ein DM-Embed im Stil des Screenshots:
    - Server-Icon als Thumbnail
    - Felder nebeneinander (inline=True)
    - Footer: BotName • System • Datum
    """
    embed = discord.Embed(
        title=title,
        description=f"Hallo {mention_name},\n\n{description}" if mention_name else description,
        color=color,
        timestamp=now_timestamp()
    )

    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    if jump_url:
        embed.add_field(name="🔗 Link", value=f"[{t('embeds','shared','link_jump')}]({jump_url})", inline=False)

    system_label = footer_system or t("embeds","shared","footer_bot")
    footer_text = f"{guild.name if guild else 'Bot'} • {system_label}"
    if guild and guild.icon:
        embed.set_footer(text=footer_text, icon_url=guild.icon.url)
    else:
        embed.set_footer(text=footer_text)

    return embed


def make_log_embed(
    title: str,
    description: str,
    color: discord.Color,
    target_user: discord.Member,
    moderator: discord.Member = None,
    reason: str = None,
    guild: discord.Guild = None,
    extra_fields: list = None
) -> discord.Embed:
    """
    Erstellt ein Log-Embed im Stil des Screenshots:
    - Nutzer-Avatar als Thumbnail
    - Felder: Nutzer, Moderator, Grund etc. inline nebeneinander
    - Footer: ServerName • Moderations-System • Datum
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=now_timestamp()
    )

    embed.set_thumbnail(url=target_user.display_avatar.url)

    embed.add_field(name=t("embeds","shared","f_server"), value=guild.name if guild else "?", inline=True)
    embed.add_field(name=t("embeds","shared","f_user"), value=f"{target_user.mention}\n`{target_user.id}`", inline=True)

    if moderator:
        embed.add_field(name=t("embeds","shared","f_moderator"), value=moderator.mention, inline=True)

    if extra_fields:
        for name, value, inline in extra_fields:
            embed.add_field(name=name, value=value, inline=inline)

    if reason:
        embed.add_field(name=t("embeds","shared","f_reason"), value=reason, inline=False)

    footer_text = f"{guild.name if guild else 'Bot'} • {t('embeds','shared','footer_mod')}"
    if guild and guild.icon:
        embed.set_footer(text=footer_text, icon_url=guild.icon.url)
    else:
        embed.set_footer(text=footer_text)

    return embed


# ─────────────────────────────────────────────
#  SEND LOG HELPER
# ─────────────────────────────────────────────

async def send_log(
    guild: discord.Guild,
    title: str,
    description: str,
    color: discord.Color,
    target_user: discord.Member,
    moderator: discord.Member = None,
    reason: str = None,
    extra_fields: list = None
):
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        for data in roles_data:
            self.add_item(SelfRoleButton(label=data['label'], role_id=data['role_id'], emoji=data.get('emoji')))
=======
        self.roles_data = roles_data
        self.panel_id = panel_id
        member_role_ids = {r.id for r in member.roles} if member else set()
        for role_data in roles_data[:25]:
            has_role = role_data['role_id'] in member_role_ids
            self.add_item(SelfRoleButton(role_data, has_role))


# ─────────────────────────────────────────────
#  TICKET CLOSE MODAL
# ─────────────────────────────────────────────

class TicketCloseModal(discord.ui.Modal):
    def __init__(self, creator_id: int = None):
        super().__init__(title=t("modals","ticket_close_title"))
        self.creator_id = creator_id
        self.grund = discord.ui.TextInput(
            label=t("modals","ticket_close_label"),
            placeholder=t("modals","ticket_close_placeholder"),
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.grund)

    async def on_submit(self, interaction: discord.Interaction):
        grund_text = self.grund.value
        thread = interaction.channel
        guild = interaction.guild

        # Abschluss-Embed im Ticket
        close_embed = discord.Embed(
            title=t("embeds","ticket_closed","title"),
            description=t("embeds","ticket_closed","desc", mention=interaction.user.mention),
            color=discord.Color.red(),
            timestamp=now_timestamp()
        )
        close_embed.add_field(name=t("embeds","ticket_closed","f_by"), value=interaction.user.mention, inline=True)
        close_embed.add_field(name=t("embeds","ticket_closed","f_date"), value=short_time(), inline=True)
        close_embed.add_field(name=t("embeds","ticket_closed","f_reason"), value=grund_text, inline=False)
        footer_txt = f"{guild.name} • {t('embeds','shared','footer_ticket')}"
        if guild.icon:
            close_embed.set_footer(text=footer_txt, icon_url=guild.icon.url)
        else:
            close_embed.set_footer(text=footer_txt)

        await interaction.response.send_message(embed=close_embed)

        # DM an Ticket-Ersteller
        if self.creator_id:
            creator = guild.get_member(self.creator_id)
            if creator:
                dm_embed = make_dm_embed(
                    title=t("embeds","dm_ticket_closed","title"),
                    description=t("embeds","dm_ticket_closed","desc"),
                    color=discord.Color.red(),
                    guild=guild,
                    fields=[
                        (t("embeds","dm_ticket_closed","f_server"), guild.name, True),
                        (t("embeds","dm_ticket_closed","f_by"), str(interaction.user), True),
                        (t("embeds","dm_ticket_closed","f_date"), short_time(), True),
                        (t("embeds","dm_ticket_closed","f_reason"), grund_text, False),
                    ],
                    footer_system=t("embeds","shared","footer_ticket")
                )
                await send_dm(creator, embed=dm_embed)

        await thread.edit(locked=True, archived=True)


# ─────────────────────────────────────────────
#  TICKET CONTROL PANEL
# ─────────────────────────────────────────────
>>>>>>> Stashed changes

# --- TICKET CONTROL PANEL ---
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Button-Labels dynamisch aus Sprachdatei laden
        self.claim.label = t("buttons", "claim_ticket")
        self.close.label = t("buttons", "close_ticket")

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

<<<<<<< Updated upstream
    @discord.ui.button(label="Ticket Claimen", style=discord.ButtonStyle.blurple, custom_id="persistent_claim_ticket")
=======
    @discord.ui.button(
        label="Claim Ticket",
        style=discord.ButtonStyle.blurple,
        emoji="📋",
        custom_id="persistent_claim_ticket"
    )
>>>>>>> Stashed changes
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message("❌ Nur Supporter können Tickets claimen.", ephemeral=True)

        embed = interaction.message.embeds[0]
<<<<<<< Updated upstream
        if any(field.name == "Bearbeiter" for field in embed.fields):
            return await interaction.response.send_message("Dieses Ticket wurde bereits übernommen!", ephemeral=True)
            
        embed.add_field(name="Bearbeiter", value=interaction.user.mention, inline=False)
        embed.color = discord.Color.blue()
        
=======
        if any(field.name == t("embeds","ticket_closed","f_agent") for field in embed.fields):
            return await interaction.response.send_message(
                t("errors","already_claimed"), ephemeral=True
            )

        embed.add_field(name=t("embeds","ticket_closed","f_agent"), value=interaction.user.mention, inline=True)
        embed.color = discord.Color.blue()
        if interaction.guild and interaction.guild.icon:
            embed.set_footer(text=f"{interaction.guild.name} • {t('embeds','shared','footer_ticket')}", icon_url=interaction.guild.icon.url)
        else:
            embed.set_footer(text=t("embeds","shared","footer_ticket"))

>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
    @discord.ui.button(label="Ticket Schließen", style=discord.ButtonStyle.red, custom_id="persistent_close_ticket")
=======
    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.red,
        emoji="🔒",
        custom_id="persistent_close_ticket"
    )
>>>>>>> Stashed changes
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
        self.verify.label = t("buttons", "verify")

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
                for member in guild.members:
                    if member.bot or member.id in added_members:
                        continue
                    if any(r.position >= base_role.position for r in member.roles):
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
<<<<<<< Updated upstream
        await send_dm(interaction.user, "", dm_embed)
=======
        footer_txt = f"{guild.name}  •  {t('embeds','shared','footer_ticket')}"
        if guild.icon:
            ticket_embed.set_footer(text=footer_txt, icon_url=guild.icon.url)
        else:
            ticket_embed.set_footer(text=footer_txt)

        await thread.send(embed=ticket_embed, view=TicketControlView())

        # DM an Nutzer
        dm_embed = make_dm_embed(
            title=t("embeds","dm_ticket_created","title"),
            description=t("embeds","dm_ticket_created","desc"),
            color=discord.Color.green(),
            guild=guild,
            fields=[
                (t("embeds","dm_ticket_created","f_server"), guild.name, True),
                (t("embeds","dm_ticket_created","f_cat"), selected_value, True),
                (t("embeds","dm_ticket_created","f_nr"), f"#{formatted_id}", True),
            ],
            jump_url=thread.jump_url,
            footer_system=t("embeds","shared","footer_ticket")
        )
        await send_dm(interaction.user, embed=dm_embed)

        # Select zurücksetzen: Panel-Nachricht mit frischer View editieren
        try:
            fresh_view = TicketView(self.categories_full_data, self.supporter_role_ids)
            await interaction.message.edit(view=fresh_view)
        except Exception:
            pass

>>>>>>> Stashed changes

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
@app_commands.describe(rolle="Die Rolle für die Top 100 Mitglieder")
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

<<<<<<< Updated upstream
@bot.tree.command(name="setup_selfrole", description="Erstellt ein Panel, an dem Nutzer sich selbst Rollen geben können")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    titel="Titel des Panels",
    beschreibung="Anleitung für die Nutzer",
    rollen_config="Format: \"Emoji Name|RollenID\", \"Emoji Name|RollenID\"..."
=======

# ─────────────────────────────────────────────
#  SELFROLE COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(
    name="selfrole_erstellen",
    description=td("selfrole_erstellen")
)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    titel=tp("selfrole_erstellen","titel"),
    beschreibung=tp("selfrole_erstellen","beschreibung"),
    farbe=tp("selfrole_erstellen","farbe"),
    rollen=tp("selfrole_erstellen","rollen")
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        match = re.search(r'^([^\x00-\x7F]|\W+)\s*(.*)', label_part)
        if match:
            emoji = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else emoji
        else:
            label = label_part
=======
        emoji_match = re.match(r'^([𐀀-􏿿☀-➿🌀-🫿]+)\s*(.*)', label)
        if emoji_match:
            emoji = emoji_match.group(1).strip() or None
            label = emoji_match.group(2).strip() or label

        # Rollen-ID extrahieren
        id_match = re.search(r'\d+', role_id_str)
        if not id_match:
            errors.append(t("errors","selfrole_no_id", entry=entry))
            continue
        role_id = int(id_match.group())

        # Prüfen ob Rolle existiert
        role = interaction.guild.get_role(role_id)
        if not role:
            errors.append(t("errors","selfrole_role_missing", entry=entry, role_id=role_id))
            continue
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
@bot.tree.command(name="whitelist", description="Verwaltet die Liste der erlaubten Link-Domains")
=======

@bot.tree.command(
    name="selfrole_loeschen",
    description=td("selfrole_loeschen")
)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    panel_id=tp("selfrole_loeschen","panel_id")
)
async def selfrole_loeschen(interaction: discord.Interaction, panel_id: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("selfrole_panels", [])
    target = next((p for p in panels if str(p.get("message_id")) == panel_id), None)

    if not target:
        return await interaction.response.send_message(
            t("errors","selfrole_panel_not_found"), ephemeral=True
        )

    panels.remove(target)
    save_config(config)

    try:
        channel = (
            interaction.guild.get_channel(target["channel_id"])
            or await interaction.guild.fetch_channel(target["channel_id"])
        )
        msg = await channel.fetch_message(int(panel_id))
        await msg.delete()
        await interaction.response.send_message(t("success","selfrole_panel_deleted"), ephemeral=True)
    except Exception:
        await interaction.response.send_message(
            t("errors","panel_removed_only"), ephemeral=True
        )


@bot.tree.command(
    name="selfrole_liste",
    description=td("selfrole_liste")
)
@app_commands.default_permissions(administrator=True)
async def selfrole_liste(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("selfrole_panels", [])

    if not panels:
        return await interaction.response.send_message(
            t("errors","no_panels"), ephemeral=True
        )

    embed = discord.Embed(
        title=t("embeds","selfrole","list_title"),
        description=t("embeds","selfrole","list_desc", count=len(panels)),
        color=discord.Color.blue(),
        timestamp=now_timestamp()
    )
    for p in panels:
        roles_list = ", ".join([f"`{r['label']}`" for r in p.get("roles", [])]) or "—"
        embed.add_field(
            name=f"📋 {p.get('title', '?')}",
            value=f"{t('embeds','selfrole','list_id_label')}: `{p.get('message_id', '?')}`\n{roles_list}",
            inline=False
        )
    if interaction.guild.icon:
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  WHITELIST COMMAND
# ─────────────────────────────────────────────

@bot.tree.command(name="whitelist", description=td("whitelist"))
>>>>>>> Stashed changes
@app_commands.default_permissions(administrator=True)
@app_commands.choices(aktion=[
    app_commands.Choice(name="Hinzufügen", value="add"),
    app_commands.Choice(name="Entfernen", value="remove"),
    app_commands.Choice(name="Liste anzeigen", value="list")
])
@app_commands.describe(domain="Die Domain (z.B. youtube.com oder google.com)")
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
@app_commands.describe(nutzer="Das zu bannende Mitglied", grund="Der Grund für den Bann")
async def ban(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    try:
        await nutzer.ban(reason=grund)
        await interaction.response.send_message(f"✅ **{nutzer}** wurde gebannt. Grund: {grund}", ephemeral=True)
        await send_log(interaction.guild, "🔨 Mitglied Gebannt", f"Ein Nutzer wurde permanent vom Server ausgeschlossen.", discord.Color.red(), nutzer, interaction.user, grund)
    except:
        await interaction.response.send_message("❌ Fehler beim Bannen.", ephemeral=True)

@bot.tree.command(name="kick", description="Kickt ein Mitglied vom Server")
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(nutzer="Das zu kickende Mitglied", grund="Der Grund für den Kick")
async def kick(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    try:
        await nutzer.kick(reason=grund)
        await interaction.response.send_message(f"✅ **{nutzer}** wurde gekickt. Grund: {grund}", ephemeral=True)
        await send_log(interaction.guild, "👢 Mitglied Gekickt", f"Ein Nutzer wurde vom Server gekickt.", discord.Color.orange(), nutzer, interaction.user, grund)
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
        await send_log(interaction.guild, "⏳ Timeout Verhängt", f"Ein Nutzer wurde stummgeschaltet (Timeout für {minuten} Min).", discord.Color.light_grey(), nutzer, interaction.user, grund)
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
    new_warn_count = current_warns + 1
    config[gid]["warns"][uid] = new_warn_count
    save_config(config)

    embed = discord.Embed(title="Verwarnung", description=f"Du wurdest auf **{interaction.guild.name}** verwarnt.\n\n**Grund:** {grund}\n**Gesamt-Warns:** {new_warn_count}", color=discord.Color.orange())
    await send_dm(nutzer, "", embed)
    await interaction.response.send_message(f"✅ {nutzer.mention} wurde verwarnt. Grund: {grund} (Warns: {new_warn_count})", ephemeral=True)
    await send_log(interaction.guild, "⚠️ Verwarnung ausgesprochen", f"Ein Nutzer wurde verwarnt. (Warnung #{new_warn_count})", discord.Color.gold(), nutzer, interaction.user, grund)

<<<<<<< Updated upstream
@bot.tree.command(name="warn_edit", description="Bearbeitet oder löscht die Anzahl der Verwarnungen eines Nutzers")
=======
    _wi = {1:"icon_1",2:"icon_2",3:"icon_3",4:"icon_4",5:"icon_5"}
    icon = t("embeds","dm_warn",_wi.get(new_warn_count,"icon_max"))

    dm_embed = make_dm_embed(
        title=f"{icon} {t('embeds','dm_warn','title')}",
        description=t("embeds","dm_warn","desc"),
        color=warn_color,
        guild=interaction.guild,
        fields=[
            (t("embeds","dm_warn","f_server"), interaction.guild.name, True),
            (t("embeds","dm_warn","f_mod"), str(interaction.user), True),
            (t("embeds","dm_warn","f_total"), str(new_warn_count), True),
            (t("embeds","dm_warn","f_reason"), grund, False),
        ],
        footer_system=t("embeds","shared","footer_mod")
    )
    await send_dm(nutzer, embed=dm_embed)

    await interaction.response.send_message(
        t("success","warn_success", mention=nutzer.mention, count=new_warn_count), ephemeral=True
    )
    await send_log(
        interaction.guild, t("embeds","log_warn","title", count=new_warn_count),
        t("embeds","log_warn","desc"),
        warn_color, nutzer, interaction.user, grund,
        extra_fields=[(t("embeds","log_warn","f_total"), f"`{new_warn_count}`", True)]
    )


@bot.tree.command(name="warn_edit", description=td("warn_edit"))
>>>>>>> Stashed changes
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(nutzer="Das Mitglied", anzahl="Die neue Anzahl an Verwarnungen (0 zum Löschen)")
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
@app_commands.describe(nutzer="Das Mitglied (leer lassen für dich selbst)")
async def userinfo(interaction: discord.Interaction, nutzer: discord.Member = None):
    target = nutzer or interaction.user
    gid = str(interaction.guild_id)
    config = load_config()
    
    warns = 0
    if gid in config and "warns" in config[gid]:
        warns = config[gid]["warns"].get(str(target.id), 0)

    roles = [role.mention for role in target.roles if role != interaction.guild.default_role]
<<<<<<< Updated upstream
    embed = discord.Embed(title=f"Infos zu {target.name}", color=target.color)
=======

    warn_display = t("embeds","userinfo","warns_none") if warns == 0 else t("embeds","userinfo","warns_fmt", count=warns)

    embed = discord.Embed(
        title=f"👤 {target.display_name}",
        color=target.color if target.color.value != 0 else discord.Color.blurple(),
        timestamp=now_timestamp()
    )
>>>>>>> Stashed changes
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
@app_commands.describe(kanal="Der Kanal, in dem Logs gesendet werden sollen")
async def set_log_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config: config[gid] = {}
    config[gid]["log_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Log-Kanal wurde auf {kanal.mention} gesetzt.", ephemeral=True)

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
<<<<<<< Updated upstream
@app_commands.describe(titel="Überschrift des Panels", beschreibung="Anleitungstext", rolle="Rolle, die vergeben wird")
async def setup_verify(interaction: discord.Interaction, titel: str, beschreibung: str, rolle: discord.Role):
    embed = discord.Embed(title=titel, description=format_discord_text(beschreibung), color=discord.Color.blue())
=======
@app_commands.describe(
    titel=tp("setup_verify","titel"),
    beschreibung=tp("setup_verify","beschreibung"),
    rolle=tp("setup_verify","rolle")
)
async def setup_verify(interaction: discord.Interaction, rolle: discord.Role, titel: str = None, beschreibung: str = None):
    final_title = titel or t("embeds","verify_panel","default_title")
    final_desc  = format_discord_text(beschreibung) if beschreibung else t("embeds","verify_panel","default_desc")
    embed = discord.Embed(
        title=final_title,
        description=final_desc,
        color=discord.Color.green()
    )
    embed.set_footer(text=t("embeds","verify_panel","footer", role=rolle.name))

>>>>>>> Stashed changes
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
async def setup_tickets(interaction: discord.Interaction, supporter_rollen: str, kategorien: str):
    guild_id = str(interaction.guild_id)
    role_ids = extract_role_ids(supporter_rollen)
    if not role_ids:
        return await interaction.response.send_message("❌ Bitte gib mindestens eine gültige Rolle an.", ephemeral=True)

<<<<<<< Updated upstream
    raw_list = re.findall(r'"([^"]*)"', kategorien)
    if not raw_list: raw_list = [c.strip() for c in kategorien.split(",") if c.strip()]
    
=======
    # Hochkommas und Anführungszeichen aus dem gesamten String entfernen
    kategorien_clean = kategorien.replace("'", "").replace('"', "")
    # Kategorien per Komma trennen
    raw_list = [c.strip() for c in kategorien_clean.split(",") if c.strip()]

    if not raw_list:
        return await interaction.response.send_message(
            t("errors","no_categories"),
            ephemeral=True
        )

>>>>>>> Stashed changes
    formatted_cats = []
    parse_errors = []
    for item in raw_list:
        parts = item.split("|")
        if not parts[0].strip():
            parse_errors.append(f"`{item}` — leerer Name")
            continue
        label = parts[0].strip()
        desc = format_discord_text(parts[1].strip()) if len(parts) > 1 else None

        # Emoji aus Label extrahieren: nur echte Unicode-Emoji
        emoji = None
<<<<<<< Updated upstream
        match = re.search(r'^([^\x00-\x7F]|\W+)\s*(.*)', label)
        if match:
            emoji = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else emoji
        formatted_cats.append({"label": label, "value": label, "emoji": emoji, "description": desc, "supporter_role_ids": None})
    
=======
        for char in label:
            cp = ord(char)
            if cp > 0x27BF and cp not in range(0x2000, 0x206F):
                emoji = char
                label = label[len(char):].strip()
                break
        if not label:
            label = item.strip()

        formatted_cats.append({
            "label": label[:100], "value": label[:100],
            "emoji": emoji,
            "description": desc,
            "supporter_role_ids": None
        })

    if not formatted_cats:
        err_text = "\n".join(parse_errors) if parse_errors else "Unbekannter Fehler"
        return await interaction.response.send_message(
            t("errors","no_categories_detail", errors=err_text), ephemeral=True
        )

    if parse_errors:
        # Weitermachen aber Fehler am Ende melden
        pass

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    await interaction.response.send_message(f"✅ Ticket-Panel erstellt (ID: {message.id}).", ephemeral=True)
=======
    success_msg = t("success","ticket_panel_created", id=message.id)
    if parse_errors:
        success_msg += t("success","skipped_entries", entries="\n".join(parse_errors))
    await interaction.response.send_message(success_msg, ephemeral=True)
>>>>>>> Stashed changes

@bot.tree.command(name="ticket_edit", description="Bearbeitet ein bestehendes Ticket-Panel")
@app_commands.default_permissions(administrator=True)
async def ticket_edit(interaction: discord.Interaction, message_id: str, titel: str = None, beschreibung: str = None, farbe: str = None):
    guild_id = str(interaction.guild_id)
    config = load_config()
    target_panel = next((p for p in config.get(guild_id, {}).get("ticket_panels", []) if str(p["message_id"]) == message_id), None)
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
<<<<<<< Updated upstream
        await interaction.response.send_message("✅ Panel aktualisiert.", ephemeral=True)
    except Exception as e: await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)
=======
        await interaction.response.send_message(t("success","ticket_panel_updated"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(t("errors","generic_error", error=str(e)), ephemeral=True)
>>>>>>> Stashed changes

@bot.tree.command(name="ticket_delete", description="Löscht ein Ticket-Panel")
@app_commands.default_permissions(administrator=True)
async def ticket_delete(interaction: discord.Interaction, message_id: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    target = next((p for p in panels if str(p["message_id"]) == message_id), None)
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
async def ticket_category_edit(interaction: discord.Interaction, message_id: str, kategorie_name: str, neue_rollen: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    role_ids = extract_role_ids(neue_rollen)
    panel = next((p for p in config.get(guild_id, {}).get("ticket_panels", []) if str(p["message_id"]) == message_id), None)
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
    choices = [app_commands.Choice(name=f"{p['message_id']} | {p.get('title', 'Ticket')}", value=str(p["message_id"])) for p in panels if current.lower() in str(p["message_id"]).lower() or current.lower() in p.get('title', '').lower()]
    return choices[:25]

@ticket_category_edit.autocomplete("kategorie_name")
async def ticket_cat_autocomplete(interaction: discord.Interaction, current: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    mid = interaction.namespace.message_id
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    choices = []
    for p in panels:
        if not mid or str(p["message_id"]) == mid:
            for cat in p.get("categories", []):
                if current.lower() in cat["value"].lower():
                    choices.append(app_commands.Choice(name=cat["value"], value=cat["value"]))
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

if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
    else: print("Fehler: DISCORD_TOKEN fehlt!")