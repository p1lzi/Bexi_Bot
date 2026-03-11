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
    if os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("allowed_domains", ["tenor.com"])
        except (json.JSONDecodeError, KeyError):
            return ["tenor.com"]
    return ["tenor.com"]

def save_whitelist(domains):
    with open(WHITELIST_FILE, 'w', encoding='utf-8') as f:
        json.dump({"allowed_domains": list(set(domains))}, f, indent=4)

def format_discord_text(text: str):
    if not text:
        return ""
    text = text.replace("/n", "\n")
    return text

def extract_role_ids(input_str: str):
    return [int(id_str) for id_str in re.findall(r'\d+', input_str)]

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
        embed.add_field(name="🔗 Link", value=f"[Zum Ticket springen]({jump_url})", inline=False)

    system_label = footer_system or "Bot-System"
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

    embed.add_field(name="🏠 Server", value=guild.name if guild else "Unbekannt", inline=True)
    embed.add_field(name="👤 Nutzer", value=f"{target_user.mention}\n`{target_user.id}`", inline=True)

    if moderator:
        embed.add_field(name="🛡️ Moderator", value=moderator.mention, inline=True)

    if extra_fields:
        for name, value, inline in extra_fields:
            embed.add_field(name=name, value=value, inline=inline)

    if reason:
        embed.add_field(name="📋 Grund", value=reason, inline=False)

    footer_text = f"{guild.name if guild else 'Bot'} • Moderations-System"
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
    config = load_config()
    gid = str(guild.id)
    log_channel_id = config.get(gid, {}).get("log_channel_id")

    if log_channel_id:
        channel = guild.get_channel(log_channel_id)
        if channel:
            embed = make_log_embed(
                title=title,
                description=description,
                color=color,
                target_user=target_user,
                moderator=moderator,
                reason=reason,
                guild=guild,
                extra_fields=extra_fields
            )
            try:
                await channel.send(embed=embed)
            except Exception:
                pass


async def send_dm(user: discord.User, content: str = "", embed: discord.Embed = None):
    try:
        await user.send(content=content if content else None, embed=embed)
    except discord.Forbidden:
        pass


# ─────────────────────────────────────────────
#  SELF ROLE SYSTEM
# ─────────────────────────────────────────────

class SelfRoleSelect(discord.ui.Select):
    def __init__(self, roles_data: list, panel_id: str):
        self.roles_data = roles_data
        options = []
        for r in roles_data:
            options.append(discord.SelectOption(
                label=r['label'][:100],
                value=str(r['role_id']),
                emoji=r.get('emoji') or None,
                description=r.get('description', '')[:100] if r.get('description') else None
            ))
        super().__init__(
            placeholder="🎭 Wähle eine Rolle aus...",
            options=options,
            custom_id=f"selfrole_select_{panel_id}",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message(
                "❌ Diese Rolle existiert nicht mehr.", ephemeral=True
            )
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            embed = discord.Embed(
                description=f"🔴 Die Rolle **{role.name}** wurde dir entfernt.",
                color=discord.Color.red()
            )
        else:
            try:
                await interaction.user.add_roles(role)
                embed = discord.Embed(
                    description=f"🟢 Die Rolle **{role.name}** wurde dir hinzugefügt.",
                    color=discord.Color.green()
                )
            except discord.Forbidden:
                embed = discord.Embed(
                    description="❌ Ich habe nicht genug Rechte, um diese Rolle zu vergeben.",
                    color=discord.Color.red()
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SelfRoleView(discord.ui.View):
    def __init__(self, roles_data: list, panel_id: str = "default"):
        super().__init__(timeout=None)
        self.add_item(SelfRoleSelect(roles_data[:25], panel_id))


# ─────────────────────────────────────────────
#  TICKET CLOSE MODAL
# ─────────────────────────────────────────────

class TicketCloseModal(discord.ui.Modal, title="Ticket schließen"):
    grund = discord.ui.TextInput(
        label="Grund für das Schließen",
        placeholder="z.B. Problem gelöst, keine Antwort erhalten...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, creator_id: int = None):
        super().__init__()
        self.creator_id = creator_id

    async def on_submit(self, interaction: discord.Interaction):
        grund_text = self.grund.value
        thread = interaction.channel
        guild = interaction.guild

        # Abschluss-Embed im Ticket
        close_embed = discord.Embed(
            title="🔒 Ticket geschlossen",
            description=f"Dieses Ticket wurde von {interaction.user.mention} geschlossen.",
            color=discord.Color.red(),
            timestamp=now_timestamp()
        )
        close_embed.add_field(name="🛡️ Geschlossen von", value=interaction.user.mention, inline=True)
        close_embed.add_field(name="📅 Geschlossen am", value=short_time(), inline=True)
        close_embed.add_field(name="📋 Grund", value=grund_text, inline=False)
        footer_txt = f"{guild.name} • Ticket-System"
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
                    title="🔒 Ticket geschlossen",
                    description="dein Ticket wurde geschlossen und archiviert. Falls du ein neues Anliegen hast, kannst du jederzeit ein neues Ticket öffnen.",
                    color=discord.Color.red(),
                    guild=guild,
                    fields=[
                        ("🏠 Server", guild.name, True),
                        ("🛡️ Geschlossen von", str(interaction.user), True),
                        ("📅 Geschlossen am", short_time(), True),
                        ("📋 Grund", grund_text, False),
                    ],
                    footer_system="Ticket-System"
                )
                await send_dm(creator, embed=dm_embed)

        await thread.edit(locked=True, archived=True)


# ─────────────────────────────────────────────
#  TICKET CONTROL PANEL
# ─────────────────────────────────────────────

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def get_creator_id(self, interaction: discord.Interaction):
        try:
            embed = interaction.message.embeds[0]
            match = re.search(r'<@!?(\d+)>', embed.description)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def is_supporter(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        config = load_config()
        guild_data = config.get(str(interaction.guild_id), {})
        user_role_ids = [role.id for role in interaction.user.roles]
        for panel in guild_data.get("ticket_panels", []):
            if any(rid in user_role_ids for rid in panel.get("supporter_role_ids", [])):
                return True
            for cat in panel.get("categories", []):
                cat_role_ids = cat.get("supporter_role_ids") or []
                if any(rid in user_role_ids for rid in cat_role_ids):
                    return True
        return False

    @discord.ui.button(
        label="Ticket übernehmen",
        style=discord.ButtonStyle.blurple,
        emoji="📋",
        custom_id="persistent_claim_ticket"
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message(
                "❌ Nur Supporter können Tickets übernehmen.", ephemeral=True
            )

        embed = interaction.message.embeds[0]
        if any(field.name == "⚙️ Bearbeiter" for field in embed.fields):
            return await interaction.response.send_message(
                "⚠️ Dieses Ticket wurde bereits übernommen!", ephemeral=True
            )

        embed.add_field(name="⚙️ Bearbeiter", value=interaction.user.mention, inline=True)
        embed.color = discord.Color.blue()
        if interaction.guild and interaction.guild.icon:
            embed.set_footer(text=f"{interaction.guild.name} • Ticket-System", icon_url=interaction.guild.icon.url)
        else:
            embed.set_footer(text=f"Ticket übernommen")

        button.disabled = True
        button.label = "Übernommen"
        await interaction.response.edit_message(embed=embed, view=self)

        status_embed = discord.Embed(
            description=f"✅ {interaction.user.mention} hat dieses Ticket übernommen und wird sich kümmern.",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=status_embed)

        # DM an Ticket-Ersteller
        creator_id = self.get_creator_id(interaction)
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = make_dm_embed(
                    title="📋 Ticket übernommen",
                    description="dein Ticket wurde von einem Supporter übernommen. Du wirst in Kürze eine Antwort erhalten. 🙂",
                    color=discord.Color.blue(),
                    guild=interaction.guild,
                    fields=[
                        ("🏠 Server", interaction.guild.name, True),
                        ("⚙️ Bearbeiter", interaction.user.mention, True),
                        ("📅 Übernommen am", short_time(), True),
                    ],
                    jump_url=interaction.channel.jump_url,
                    footer_system="Ticket-System"
                )
                await send_dm(creator, embed=dm_embed)

    @discord.ui.button(
        label="Ticket schließen",
        style=discord.ButtonStyle.red,
        emoji="🔒",
        custom_id="persistent_close_ticket"
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message(
                "❌ Nur Supporter können Tickets schließen.", ephemeral=True
            )
        await interaction.response.send_modal(TicketCloseModal(self.get_creator_id(interaction)))


# ─────────────────────────────────────────────
#  VERIFY SYSTEM
# ─────────────────────────────────────────────

class VerifyView(discord.ui.View):
    def __init__(self, role_id: int):
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(
        label="Jetzt verifizieren",
        style=discord.ButtonStyle.green,
        emoji="✅",
        custom_id="verify_btn_persistent"
    )
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(
                    f"✅ Du wurdest erfolgreich verifiziert und hast die Rolle **{role.name}** erhalten!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Mir fehlen die Rechte, um Rollen zu vergeben.", ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "❌ Diese Rolle existiert nicht mehr.", ephemeral=True
            )


# ─────────────────────────────────────────────
#  TICKET SYSTEM
# ─────────────────────────────────────────────

class TicketSelect(discord.ui.Select):
    def __init__(self, options, supporter_role_ids, categories_full_data=None):
        super().__init__(
            placeholder="📂 Wähle dein Anliegen...",
            options=options,
            custom_id="ticket_select_persistent"
        )
        self.supporter_role_ids = supporter_role_ids
        self.categories_full_data = categories_full_data or []

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        guild = interaction.guild
        guild_id = str(guild.id)
        config = load_config()

        if guild_id not in config:
            config[guild_id] = {}
        if "category_counters" not in config[guild_id]:
            config[guild_id]["category_counters"] = {}
        if selected_value not in config[guild_id]["category_counters"]:
            config[guild_id]["category_counters"][selected_value] = 0

        config[guild_id]["category_counters"][selected_value] += 1
        ticket_id = config[guild_id]["category_counters"][selected_value]
        formatted_id = f"{ticket_id:04d}"

        # Supporter-Rollen für diese Kategorie ermitteln
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
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    manage_channels=True,
                    manage_roles=True
                )
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
                    guild.me: discord.PermissionOverwrite(
                        view_channel=True,
                        manage_channels=True,
                        send_messages=True
                    )
                }
                for rid in target_role_ids:
                    role = guild.get_role(rid)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(
                            view_channel=True,
                            send_messages=True,
                            manage_threads=True
                        )

                target_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=f"Zentraler Kanal für {selected_value} Anfragen."
                )

                info_embed = discord.Embed(
                    title=f"📂 Ticket-Kanal: {selected_value}",
                    description=(
                        f"In diesem Kanal werden alle Tickets der Kategorie **{selected_value}** verwaltet.\n\n"
                        "⚠️ **Hinweis:** Hier kann nicht direkt geschrieben werden. "
                        "Dein Ticket wird als privater Thread erstellt."
                    ),
                    color=discord.Color.blurple()
                )
                if guild.icon:
                    info_embed.set_thumbnail(url=guild.icon.url)
                info_embed.set_footer(text=guild.name)
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
                        except Exception:
                            pass

        ticket_embed = discord.Embed(
            title=f"🎫 Ticket #{formatted_id} — {selected_value}",
            description=(
                f"Willkommen {interaction.user.mention}!\n\n"
                f"Dein Ticket wurde erfolgreich erstellt. Bitte schildere dein Anliegen "
                f"so **detailliert wie möglich**, damit wir dir schnell helfen können."
            ),
            color=discord.Color.green(),
            timestamp=now_timestamp()
        )
        ticket_embed.add_field(name="🔢 Ticket-Nummer", value=f"`#{formatted_id}`", inline=True)
        ticket_embed.add_field(name="📂 Kategorie", value=f"`{selected_value}`", inline=True)
        ticket_embed.add_field(name="👤 Erstellt von", value=interaction.user.mention, inline=True)
        ticket_embed.add_field(
            name="📝 Nächste Schritte",
            value=(
                "**1.** Beschreibe dein Anliegen ausführlich\n"
                "**2.** Füge Screenshots oder weitere Infos hinzu\n"
                "**3.** Warte auf einen Supporter"
            ),
            inline=False
        )
        footer_txt = f"{guild.name}  •  Ticket-System"
        if guild.icon:
            ticket_embed.set_footer(text=footer_txt, icon_url=guild.icon.url)
        else:
            ticket_embed.set_footer(text=footer_txt)

        await thread.send(embed=ticket_embed, view=TicketControlView())

        # DM an Nutzer
        dm_embed = make_dm_embed(
            title="🎫 Ticket erfolgreich erstellt",
            description="dein Ticket wurde erfolgreich erstellt. Ein Supporter wird sich so schnell wie möglich bei dir melden. Bitte habe etwas Geduld. 🙂",
            color=discord.Color.green(),
            guild=guild,
            fields=[
                ("🏠 Server", guild.name, True),
                ("📂 Kategorie", selected_value, True),
                ("🔢 Ticket-Nr.", f"#{formatted_id}", True),
            ],
            jump_url=thread.jump_url,
            footer_system="Ticket-System"
        )
        await send_dm(interaction.user, embed=dm_embed)

        # Select zurücksetzen: Panel-Nachricht mit frischer View editieren
        try:
            fresh_view = TicketView(self.categories_full_data, self.supporter_role_ids)
            await interaction.message.edit(view=fresh_view)
        except Exception:
            pass


class TicketView(discord.ui.View):
    def __init__(self, categories_data, supporter_role_ids):
        super().__init__(timeout=None)
        options = []
        for item in categories_data:
            options.append(discord.SelectOption(
                label=item['label'][:100],
                value=item['value'][:100],
                emoji=item.get('emoji'),
                description=item.get('description', '')[:100] if item.get('description') else None
            ))
        self.clear_items()
        self.add_item(TicketSelect(options, supporter_role_ids, categories_data))


# ─────────────────────────────────────────────
#  BOT
# ─────────────────────────────────────────────

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
            for panel in data.get("verify_panels", []):
                self.add_view(VerifyView(panel["role_id"]))
            for t_panel in data.get("ticket_panels", []):
                supp_ids = t_panel.get("supporter_role_ids")
                if not supp_ids:
                    old_id = t_panel.get("supporter_role_id")
                    supp_ids = [old_id] if old_id else []
                self.add_view(TicketView(t_panel["categories"], supp_ids))
            for s_panel in data.get("selfrole_panels", []):
                self.add_view(SelfRoleView(s_panel["roles"], str(s_panel.get("message_id", "default"))))

        self.add_view(TicketControlView())
        await self.tree.sync()
        print("🌐 Slash Commands wurden global synchronisiert.")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

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
                                "🚫 Link gelöscht",
                                f"In {message.channel.mention} wurde ein nicht erlaubter Link entfernt.",
                                discord.Color.red(),
                                message.author,
                                extra_fields=[
                                    ("💬 Nachrichteninhalt", f"```{message.content[:900]}```", False)
                                ]
                            )
                            allowed_str = ", ".join(f"`{d}`" for d in whitelist)
                            await message.channel.send(
                                f"⚠️ {message.author.mention}, dieser Link ist nicht erlaubt!\n"
                                f"Erlaubte Seiten: {allowed_str}",
                                delete_after=6
                            )
                            return
                        except discord.Forbidden:
                            pass
                except Exception:
                    continue

        await self.process_commands(message)

    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        config = load_config()
        welcome_channel_id = config.get(guild_id, {}).get("welcome_channel_id")
        if welcome_channel_id:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                # Mitgliedsnummer berechnen
                member_number = sum(1 for m in member.guild.members if not m.bot and m.joined_at and m.joined_at <= member.joined_at)

                embed = discord.Embed(
                    title=f"👋 Willkommen auf {member.guild.name}!",
                    description=(
                        f"Hallo {member.mention}, schön dass du da bist!\n\n"
                        f"Schau dir die Regeln und Kanäle an und mach dich zu Hause. 🏠"
                    ),
                    color=discord.Color.green(),
                    timestamp=now_timestamp()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(
                    name="👤 Nutzer",
                    value=member.mention,
                    inline=True
                )
                embed.add_field(
                    name="🪪 Account erstellt",
                    value=discord.utils.format_dt(member.created_at, style="R"),
                    inline=True
                )
                embed.add_field(
                    name="👥 Mitglied Nr.",
                    value=f"**#{member_number}**",
                    inline=True
                )
                footer_text = f"Bexi-Bot • {member.guild.name}"
                if member.guild.icon:
                    embed.set_footer(text=footer_text, icon_url=member.guild.icon.url)
                else:
                    embed.set_footer(text=footer_text)
                await channel.send(embed=embed)

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
            vc = discord.utils.get(self.voice_clients, guild=member.guild)
            if not vc:
                try:
                    vc = await voice_channel.connect()
                    self.loop.create_task(self.play_looping_music(vc))
                except Exception:
                    pass
        elif before.channel and before.channel.id == waiting_room_id:
            vc = discord.utils.get(self.voice_clients, guild=member.guild)
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


bot = MyBot()


# ─────────────────────────────────────────────
#  PIONEER ROLLE COMMAND
# ─────────────────────────────────────────────

@bot.tree.command(name="setup_pioneer_role", description="Vergibt automatisch eine Pionier-Rolle an die ersten 100 Mitglieder des Servers")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    rolle="Die Rolle, die an die ersten 100 beigetretenen Mitglieder vergeben werden soll"
)
async def setup_pioneer_role(interaction: discord.Interaction, rolle: discord.Role):
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
        title="🏆 Pioneer-Rolle vergeben",
        description=f"Die Analyse wurde abgeschlossen. Hier ist die Zusammenfassung:",
        color=discord.Color.gold(),
        timestamp=now_timestamp()
    )
    embed.add_field(name="🎖️ Rolle", value=rolle.mention, inline=True)
    embed.add_field(name="✅ Neu zugewiesen", value=str(assigned_count), inline=True)
    embed.add_field(name="❌ Fehler", value=str(errors), inline=True)
    if interaction.guild.icon:
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)

    await interaction.followup.send(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  SELFROLE COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(
    name="selfrole_erstellen",
    description="Erstellt ein Dropdown-Panel, über das Nutzer sich selbst Rollen vergeben können"
)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    titel="Titel des Panels z.B. 'Wähle deine Rollen'",
    beschreibung="Erklärungstext für die Nutzer, der unter dem Titel angezeigt wird",
    farbe="Hex-Farbe des Panels z.B. #5865F2 für Blurple (optional, Standard: Blau)",
    rollen="Format: 🎮 Name|RollenID|Beschreibung — Emoji davor, RollenID (nicht @Erwähnung!), Beschreibung optional. Mehrere mit Komma trennen. Bsp: 🎮 Gamer|123456|Für Gamer, 🎵 Musik|654321"
)
async def selfrole_erstellen(
    interaction: discord.Interaction,
    titel: str,
    beschreibung: str,
    rollen: str,
    farbe: str = None
):
    await interaction.response.defer(ephemeral=True)
    guild_id = str(interaction.guild_id)

    # Parse Rollen: "Name|RollenID|Beschreibung" oder "Name|RollenID"
    formatted_roles = []
    entries = [e.strip() for e in rollen.split(",") if e.strip()]
    errors = []

    for entry in entries:
        parts = [p.strip() for p in entry.split("|")]
        if len(parts) < 2:
            errors.append(f"`{entry}` — fehlendes Format (Name|@Rolle)")
            continue
        label = parts[0][:100]
        role_id_str = parts[1]
        description = parts[2][:100] if len(parts) > 2 else None

        # Emoji aus Label extrahieren
        emoji = None
        match = re.search(r'^([^-]|\W)\s*(.*)', label)
        if match and match.group(1).strip():
            emoji = match.group(1).strip()
            label = match.group(2).strip() or emoji

        # Rollen-ID extrahieren
        id_match = re.search(r'\d+', role_id_str)
        if not id_match:
            errors.append(f"`{entry}` — keine gültige Rollen-ID gefunden")
            continue
        role_id = int(id_match.group())

        # Prüfen ob Rolle existiert
        role = interaction.guild.get_role(role_id)
        if not role:
            errors.append(f"`{entry}` — Rolle mit ID `{role_id}` nicht gefunden")
            continue

        formatted_roles.append({
            "label": label,
            "role_id": role_id,
            "emoji": emoji,
            "description": description
        })

    if not formatted_roles:
        return await interaction.followup.send(
            f"❌ Keine gültigen Rollen gefunden.\n\n**Fehler:**\n" + "\n".join(errors),
            ephemeral=True
        )

    # Panel-Farbe
    color = discord.Color.blue()
    if farbe:
        try:
            color = discord.Color(int(farbe.replace("#", ""), 16))
        except ValueError:
            pass

    panel_id = str(interaction.id)

    embed = discord.Embed(
        title=titel,
        description=format_discord_text(beschreibung),
        color=color,
        timestamp=now_timestamp()
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(
        text=f"{interaction.guild.name} • {len(formatted_roles)} Rolle(n) verfügbar",
        icon_url=interaction.guild.icon.url if interaction.guild.icon else None
    )

    view = SelfRoleView(formatted_roles, panel_id)
    message = await interaction.channel.send(embed=embed, view=view)

    config = load_config()
    if guild_id not in config:
        config[guild_id] = {}
    config[guild_id].setdefault("selfrole_panels", []).append({
        "message_id": message.id,
        "channel_id": interaction.channel_id,
        "panel_id": panel_id,
        "title": titel,
        "roles": formatted_roles
    })
    save_config(config)

    result_msg = f"✅ Self-Role Panel **{titel}** wurde erstellt mit **{len(formatted_roles)}** Rolle(n)."
    if errors:
        result_msg += f"\n\n⚠️ **Übersprungene Einträge:**\n" + "\n".join(errors)
    await interaction.followup.send(result_msg, ephemeral=True)


@bot.tree.command(
    name="selfrole_loeschen",
    description="Löscht ein bestehendes Self-Role Panel anhand der Nachrichten-ID"
)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    panel_id="Die Nachrichten-ID des Panels — Entwicklermodus aktivieren, dann Rechtsklick auf die Panel-Nachricht → 'ID kopieren'"
)
async def selfrole_loeschen(interaction: discord.Interaction, panel_id: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("selfrole_panels", [])
    target = next((p for p in panels if str(p.get("message_id")) == panel_id), None)

    if not target:
        return await interaction.response.send_message(
            "❌ Kein Self-Role Panel mit dieser ID gefunden.", ephemeral=True
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
        await interaction.response.send_message("✅ Panel gelöscht.", ephemeral=True)
    except Exception:
        await interaction.response.send_message(
            "✅ Panel aus Config entfernt (Nachricht konnte nicht gelöscht werden).", ephemeral=True
        )


@bot.tree.command(
    name="selfrole_liste",
    description="Zeigt alle aktiven Self-Role Panels auf diesem Server an"
)
@app_commands.default_permissions(administrator=True)
async def selfrole_liste(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("selfrole_panels", [])

    if not panels:
        return await interaction.response.send_message(
            "ℹ️ Keine Self-Role Panels auf diesem Server.", ephemeral=True
        )

    embed = discord.Embed(
        title="🎭 Self-Role Panels",
        description=f"Es gibt **{len(panels)}** Panel(s) auf diesem Server.",
        color=discord.Color.blue(),
        timestamp=now_timestamp()
    )
    for p in panels:
        roles_list = ", ".join([f"`{r['label']}`" for r in p.get("roles", [])]) or "—"
        embed.add_field(
            name=f"📋 {p.get('title', 'Unbekannt')}",
            value=f"**ID:** `{p.get('message_id', '?')}`\n**Rollen:** {roles_list}",
            inline=False
        )
    if interaction.guild.icon:
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  WHITELIST COMMAND
# ─────────────────────────────────────────────

@bot.tree.command(name="whitelist", description="Verwaltet die Liste der erlaubten Link-Domains")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(aktion=[
    app_commands.Choice(name="Hinzufügen", value="add"),
    app_commands.Choice(name="Entfernen", value="remove"),
    app_commands.Choice(name="Liste anzeigen", value="list")
])
@app_commands.describe(
    aktion="Aktion auswählen: Hinzufügen, Entfernen oder Liste anzeigen",
    domain="Die Domain ohne https:// (z.B. youtube.com oder discord.com)"
)
async def whitelist_cmd(interaction: discord.Interaction, aktion: app_commands.Choice[str], domain: str = None):
    whitelist = load_whitelist()

    if aktion.value == "list":
        domains_str = "\n".join([f"• `{d}`" for d in whitelist]) if whitelist else "_Keine Domains erlaubt._"
        embed = discord.Embed(
            title="🛡️ Erlaubte Domains",
            description=domains_str,
            color=discord.Color.blue(),
            timestamp=now_timestamp()
        )
        embed.set_footer(text=f"{len(whitelist)} Domain(s) auf der Whitelist")
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    if not domain:
        return await interaction.response.send_message("❌ Bitte gib eine Domain an.", ephemeral=True)

    clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

    if aktion.value == "add":
        if clean_domain in whitelist:
            await interaction.response.send_message(
                f"ℹ️ `{clean_domain}` ist bereits auf der Whitelist.", ephemeral=True
            )
        else:
            whitelist.append(clean_domain)
            save_whitelist(whitelist)
            await interaction.response.send_message(
                f"✅ `{clean_domain}` wurde zur Whitelist hinzugefügt.", ephemeral=True
            )
    elif aktion.value == "remove":
        if clean_domain in whitelist:
            whitelist.remove(clean_domain)
            save_whitelist(whitelist)
            await interaction.response.send_message(
                f"✅ `{clean_domain}` wurde von der Whitelist entfernt.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ `{clean_domain}` ist nicht in der Whitelist.", ephemeral=True
            )


# ─────────────────────────────────────────────
#  MODERATION COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="ban", description="Bannt ein Mitglied permanent vom Server")
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(
    nutzer="Das Mitglied, das permanent gebannt werden soll",
    grund="Der Grund für den Bann — wird dem Nutzer per DM mitgeteilt"
)
async def ban(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    # DM vor dem Bann senden
    dm_embed = make_dm_embed(
        title="🔨 Du wurdest gebannt",
        description="du wurdest permanent vom Server ausgeschlossen. Wenn du der Meinung bist, dass dies ein Fehler ist, wende dich bitte an einen Administrator.",
        color=discord.Color.red(),
        guild=interaction.guild,
        fields=[
            ("🏠 Server", interaction.guild.name, True),
            ("🛡️ Moderator", str(interaction.user), True),
            ("📅 Datum", short_time(), True),
            ("📋 Grund", grund, False),
        ],
        footer_system="Moderations-System"
    )
    await send_dm(nutzer, embed=dm_embed)

    try:
        await nutzer.ban(reason=grund)
        await interaction.response.send_message(
            f"✅ **{nutzer}** wurde gebannt.", ephemeral=True
        )
        await send_log(
            interaction.guild, "🔨 Mitglied gebannt",
            f"Ein Mitglied wurde permanent vom Server ausgeschlossen.",
            discord.Color.red(), nutzer, interaction.user, grund
        )
    except Exception:
        await interaction.response.send_message("❌ Fehler beim Bannen.", ephemeral=True)


@bot.tree.command(name="kick", description="Kickt ein Mitglied vom Server")
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(
    nutzer="Das Mitglied, das gekickt werden soll",
    grund="Der Grund für den Kick — wird dem Nutzer per DM mitgeteilt"
)
async def kick(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    dm_embed = make_dm_embed(
        title="👢 Du wurdest gekickt",
        description="du wurdest vom Server gekickt. Du kannst dem Server jederzeit über einen neuen Einladungslink wieder beitreten.",
        color=discord.Color.orange(),
        guild=interaction.guild,
        fields=[
            ("🏠 Server", interaction.guild.name, True),
            ("🛡️ Moderator", str(interaction.user), True),
            ("📅 Datum", short_time(), True),
            ("📋 Grund", grund, False),
        ],
        footer_system="Moderations-System"
    )
    await send_dm(nutzer, embed=dm_embed)

    try:
        await nutzer.kick(reason=grund)
        await interaction.response.send_message(
            f"✅ **{nutzer}** wurde gekickt.", ephemeral=True
        )
        await send_log(
            interaction.guild, "👢 Mitglied gekickt",
            "Ein Mitglied wurde vom Server gekickt.",
            discord.Color.orange(), nutzer, interaction.user, grund
        )
    except Exception:
        await interaction.response.send_message("❌ Fehler beim Kicken.", ephemeral=True)


@bot.tree.command(name="timeout", description="Versetzt ein Mitglied für eine bestimmte Zeit in den Timeout")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    nutzer="Das Mitglied, das in den Timeout versetzt werden soll",
    minuten="Dauer des Timeouts in Minuten (z.B. 10 für 10 Minuten)",
    grund="Der Grund für den Timeout — wird dem Nutzer per DM mitgeteilt"
)
async def timeout(interaction: discord.Interaction, nutzer: discord.Member, minuten: int, grund: str = "Kein Grund angegeben"):
    timeout_ends = discord.utils.format_dt(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minuten),
        style="R"
    )
    dm_embed = make_dm_embed(
        title="⏳ Du wurdest in den Timeout versetzt",
        description=f"du wurdest vorübergehend stummgeschaltet und kannst auf **{interaction.guild.name}** bis {discord.utils.format_dt(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minuten))} nicht schreiben.",
        color=discord.Color.light_grey(),
        guild=interaction.guild,
        fields=[
            ("🏠 Server", interaction.guild.name, True),
            ("🛡️ Moderator", str(interaction.user), True),
            ("⏱️ Dauer", f"{minuten} Minuten", True),
            ("🔓 Endet", timeout_ends, True),
            ("📋 Grund", grund, False),
        ],
        footer_system="Moderations-System"
    )
    await send_dm(nutzer, embed=dm_embed)

    try:
        duration = datetime.timedelta(minutes=minuten)
        await nutzer.timeout(duration, reason=grund)
        await interaction.response.send_message(
            f"✅ **{nutzer}** ist nun für {minuten} Minute(n) im Timeout.", ephemeral=True
        )
        await send_log(
            interaction.guild, "⏳ Timeout verhängt",
            f"Ein Mitglied wurde stummgeschaltet.",
            discord.Color.light_grey(), nutzer, interaction.user, grund,
            extra_fields=[("⏱️ Dauer", f"`{minuten} Minute(n)`", True)]
        )
    except Exception:
        await interaction.response.send_message("❌ Fehler beim Timeout.", ephemeral=True)


@bot.tree.command(name="warn", description="Verwarnt ein Mitglied und speichert den Warn")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    nutzer="Das Mitglied, das eine Verwarnung erhalten soll",
    grund="Der Grund für die Verwarnung — wird dem Nutzer per DM mitgeteilt"
)
async def warn(interaction: discord.Interaction, nutzer: discord.Member, grund: str):
    config = load_config()
    gid = str(interaction.guild_id)
    uid = str(nutzer.id)

    if gid not in config:
        config[gid] = {}
    if "warns" not in config[gid]:
        config[gid]["warns"] = {}

    current_warns = config[gid]["warns"].get(uid, 0)
    new_warn_count = current_warns + 1
    config[gid]["warns"][uid] = new_warn_count
    save_config(config)

    # Warn-Farbe eskaliert mit Anzahl
    warn_color = discord.Color.yellow()
    if new_warn_count >= 3:
        warn_color = discord.Color.orange()
    if new_warn_count >= 5:
        warn_color = discord.Color.red()

    warn_icons = {1: "⚠️", 2: "⚠️⚠️", 3: "🚨", 4: "🚨🚨", 5: "🔴"}
    icon = warn_icons.get(new_warn_count, "🔴")

    dm_embed = make_dm_embed(
        title=f"{icon} Du hast eine Verwarnung erhalten",
        description="du wurdest offiziell verwarnt. Bitte beachte die Serverregeln, um weitere Konsequenzen zu vermeiden.",
        color=warn_color,
        guild=interaction.guild,
        fields=[
            ("🏠 Server", interaction.guild.name, True),
            ("🛡️ Moderator", str(interaction.user), True),
            ("🔢 Verwarnungen gesamt", str(new_warn_count), True),
            ("📋 Grund", grund, False),
        ],
        footer_system="Moderations-System"
    )
    await send_dm(nutzer, embed=dm_embed)

    await interaction.response.send_message(
        f"✅ {nutzer.mention} wurde verwarnt. (Warns gesamt: {new_warn_count})", ephemeral=True
    )
    await send_log(
        interaction.guild, f"⚠️ Verwarnung #{new_warn_count}",
        "Ein Mitglied wurde offiziell verwarnt.",
        warn_color, nutzer, interaction.user, grund,
        extra_fields=[("🔢 Gesamte Verwarnungen", f"`{new_warn_count}`", True)]
    )


@bot.tree.command(name="warn_edit", description="Bearbeitet oder löscht die Anzahl der Verwarnungen eines Nutzers")
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    nutzer="Das Mitglied, dessen Verwarnungen bearbeitet werden sollen",
    anzahl="Die neue Gesamtanzahl an Verwarnungen (0 = alle Verwarnungen löschen)"
)
async def warn_edit(interaction: discord.Interaction, nutzer: discord.Member, anzahl: int):
    if anzahl < 0:
        return await interaction.response.send_message(
            "❌ Die Anzahl darf nicht negativ sein.", ephemeral=True
        )

    config = load_config()
    gid = str(interaction.guild_id)
    uid = str(nutzer.id)

    if gid not in config:
        config[gid] = {}
    if "warns" not in config[gid]:
        config[gid]["warns"] = {}

    alte_anzahl = config[gid]["warns"].get(uid, 0)
    config[gid]["warns"][uid] = anzahl
    save_config(config)

    msg = f"✅ Warns für {nutzer.mention}: **{alte_anzahl}** ➔ **{anzahl}**."
    if anzahl == 0:
        msg = f"✅ Alle Warns für {nutzer.mention} wurden zurückgesetzt."

    await interaction.response.send_message(msg, ephemeral=True)
    await send_log(
        interaction.guild, "🔧 Verwarnungen bearbeitet",
        "Die Anzahl der Verwarnungen wurde manuell angepasst.",
        discord.Color.blue(), nutzer, interaction.user,
        extra_fields=[
            ("📊 Änderung", f"`{alte_anzahl}` ➔ `{anzahl}`", True)
        ]
    )


@bot.tree.command(name="userinfo", description="Zeigt deine eigenen Infos an — Admins können auch andere Mitglieder einsehen")
@app_commands.describe(
    nutzer="Nur für Admins: Das Mitglied, dessen Informationen angezeigt werden sollen (leer lassen = eigene Infos)"
)
async def userinfo(interaction: discord.Interaction, nutzer: discord.Member = None):
    # Prüfen ob jemand anderes angegeben wurde
    if nutzer is not None and nutzer.id != interaction.user.id:
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Du kannst nur deine eigenen Informationen abrufen.", ephemeral=True
            )

    target = nutzer or interaction.user
    gid = str(interaction.guild_id)
    config = load_config()

    warns = 0
    if gid in config and "warns" in config[gid]:
        warns = config[gid]["warns"].get(str(target.id), 0)

    roles = [role.mention for role in target.roles if role != interaction.guild.default_role]

    warn_display = f"`{warns}`" if warns == 0 else f"⚠️ `{warns}`"

    embed = discord.Embed(
        title=f"👤 {target.display_name}",
        color=target.color if target.color.value != 0 else discord.Color.blurple(),
        timestamp=now_timestamp()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🪪 ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="⚠️ Verwarnungen", value=warn_display, inline=True)
    embed.add_field(name="🤖 Bot", value="Ja" if target.bot else "Nein", inline=True)
    embed.add_field(
        name="📅 Server beigetreten",
        value=target.joined_at.strftime("%d.%m.%Y") if target.joined_at else "Unbekannt",
        inline=True
    )
    embed.add_field(
        name="🎂 Discord-Konto erstellt",
        value=target.created_at.strftime("%d.%m.%Y"),
        inline=True
    )
    embed.add_field(name="🎨 Rollen", value=" ".join(roles) if roles else "_Keine_", inline=False)
    if interaction.guild.icon:
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  CONFIG COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="set_log_channel", description="Legt den Kanal für Moderations-Logs fest")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    kanal="Der Textkanal, in dem alle Moderations-Aktionen (Bans, Kicks, Warns etc.) protokolliert werden"
)
async def set_log_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid]["log_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(
        f"✅ Log-Kanal wurde auf {kanal.mention} gesetzt.", ephemeral=True
    )


@bot.tree.command(name="set_welcome_channel", description="Legt den Kanal für Willkommensnachrichten fest")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    kanal="Der Textkanal, in dem neue Mitglieder beim Beitreten begrüßt werden"
)
async def set_welcome_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid]["welcome_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(
        f"✅ Willkommens-Kanal auf {kanal.mention} gesetzt.", ephemeral=True
    )


@bot.tree.command(name="set_waiting_room", description="Konfiguriert den Warteraum für die Support-Musik")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    kanal="Der Sprachkanal, in dem automatisch Support-Musik abgespielt wird, wenn jemand wartet"
)
async def set_waiting_room(interaction: discord.Interaction, kanal: discord.VoiceChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid]["waiting_room_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(
        f"✅ Warteraum auf {kanal.mention} gesetzt.", ephemeral=True
    )


@bot.tree.command(name="setup_verify", description="Erstellt eine Nachricht mit einem Verifizierungs-Button")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    titel="Die Überschrift des Verifizierungs-Panels (z.B. 'Verifizierung')",
    beschreibung="Der Erklärungstext für die Nutzer (z.B. 'Klicke den Button um Zugang zu erhalten')",
    rolle="Die Rolle, die nach der Verifizierung automatisch vergeben wird"
)
async def setup_verify(interaction: discord.Interaction, titel: str, beschreibung: str, rolle: discord.Role):
    embed = discord.Embed(
        title=titel,
        description=format_discord_text(beschreibung),
        color=discord.Color.green()
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=f"Rolle: {rolle.name}")

    view = VerifyView(rolle.id)
    msg = await interaction.channel.send(embed=embed, view=view)

    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {}
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
    status="Der Online-Status des Bots (Online, Abwesend, Bitte nicht stören, Unsichtbar)",
    aktivitaet_typ="Die Art der angezeigten Aktivität (Spielt, Streamt, Hört zu, Schaut)",
    text="Der Text der Aktivität, der unter dem Bot-Namen angezeigt wird",
    stream_url="Stream-URL für den Streaming-Status (nur bei Typ 'Streamt' relevant)"
)
async def status_config(
    interaction: discord.Interaction,
    status: app_commands.Choice[str],
    aktivitaet_typ: app_commands.Choice[str],
    text: str,
    stream_url: str = "https://twitch.tv/discord"
):
    discord_status = getattr(discord.Status, status.value, discord.Status.online)
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
    config["bot_presence"] = {"status": status.value, "type": aktivitaet_typ.value, "text": text, "url": stream_url}
    save_config(config)
    await interaction.response.send_message("✅ Status aktualisiert.", ephemeral=True)


# ─────────────────────────────────────────────
#  TICKET SETUP COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="setup_tickets", description="Erstellt ein neues Support-Ticket-Panel")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    supporter_rollen="Die Rollen, die Tickets bearbeiten dürfen — als Erwähnung oder ID (mehrere mit Leerzeichen trennen)",
    kategorien="Kategorien im Format: 'Name|Beschreibung', mehrere in Anführungszeichen mit Komma trennen"
)
async def setup_tickets(interaction: discord.Interaction, supporter_rollen: str, kategorien: str):
    guild_id = str(interaction.guild_id)
    role_ids = extract_role_ids(supporter_rollen)
    if not role_ids:
        return await interaction.response.send_message(
            "❌ Bitte gib mindestens eine gültige Rolle an.", ephemeral=True
        )

    raw_list = re.findall(r'"([^"]*)"', kategorien)
    if not raw_list:
        raw_list = [c.strip() for c in kategorien.split(",") if c.strip()]

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
        formatted_cats.append({
            "label": label, "value": label,
            "emoji": emoji, "description": desc,
            "supporter_role_ids": None
        })

    config = load_config()
    if guild_id not in config:
        config[guild_id] = {}

    view = TicketView(formatted_cats, role_ids)
    default_title = "🎫 Support-Tickets"
    embed = discord.Embed(
        title=default_title,
        description=(
            "Brauchst du Hilfe oder hast ein Anliegen?\n\n"
            "Wähle die passende Kategorie aus dem Dropdown-Menü unten, "
            "um ein Ticket zu öffnen. Wir helfen dir so schnell wie möglich! 🙂"
        ),
        color=discord.Color.gold()
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=f"{interaction.guild.name}  •  Support-System")

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
    await interaction.response.send_message(
        f"✅ Ticket-Panel erstellt (ID: `{message.id}`).", ephemeral=True
    )


@bot.tree.command(name="ticket_edit", description="Bearbeitet ein bestehendes Ticket-Panel")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    message_id="Die ID der Panel-Nachricht (Autocomplete verfügbar)",
    titel="Neuer Titel des Panels (leer lassen = unverändert)",
    beschreibung="Neuer Beschreibungstext des Panels (leer lassen = unverändert)",
    farbe="Neue Farbe als Hex-Code z.B. #FF0000 für Rot (leer lassen = unverändert)"
)
async def ticket_edit(
    interaction: discord.Interaction,
    message_id: str,
    titel: str = None,
    beschreibung: str = None,
    farbe: str = None
):
    guild_id = str(interaction.guild_id)
    config = load_config()
    target_panel = next(
        (p for p in config.get(guild_id, {}).get("ticket_panels", []) if str(p["message_id"]) == message_id),
        None
    )
    if not target_panel:
        return await interaction.response.send_message("❌ Panel nicht gefunden.", ephemeral=True)
    try:
        channel = (
            interaction.guild.get_channel(target_panel["channel_id"])
            or await interaction.guild.fetch_channel(target_panel["channel_id"])
        )
        msg = await channel.fetch_message(int(message_id))
        embed = msg.embeds[0]
        if titel:
            embed.title = titel
            target_panel["title"] = titel
        if beschreibung:
            embed.description = format_discord_text(beschreibung)
        if farbe:
            embed.color = discord.Color(int(farbe.replace("#", ""), 16))
        await msg.edit(embed=embed)
        save_config(config)
        await interaction.response.send_message("✅ Panel aktualisiert.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


@bot.tree.command(name="ticket_delete", description="Löscht ein Ticket-Panel")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    message_id="Die ID der Panel-Nachricht, die gelöscht werden soll (Autocomplete verfügbar)"
)
async def ticket_delete(interaction: discord.Interaction, message_id: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    target = next((p for p in panels if str(p["message_id"]) == message_id), None)
    if not target:
        return await interaction.response.send_message("❌ Nicht in Config.", ephemeral=True)
    panels.remove(target)
    save_config(config)
    try:
        channel = (
            interaction.guild.get_channel(target["channel_id"])
            or await interaction.guild.fetch_channel(target["channel_id"])
        )
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()
        await interaction.response.send_message("✅ Panel gelöscht.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("✅ Aus Config entfernt.", ephemeral=True)


# ─────────────────────────────────────────────
#  BASIS COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="ping", description="Zeigt die Latenz an")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    color = discord.Color.green() if latency < 100 else discord.Color.orange() if latency < 200 else discord.Color.red()
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Aktuelle Latenz: **{latency}ms**",
        color=color
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
    print(f'✅ Bot online als {bot.user}')
    if not os.path.exists(WHITELIST_FILE):
        save_whitelist(["tenor.com", "giphy.com"])
    config = load_config()
    pres = config.get("bot_presence")
    if pres:
        status_val = pres.get("status", "online")
        d_status = getattr(discord.Status, status_val, discord.Status.online)
        t_val = pres.get("type", "playing")
        text = pres.get("text", "")
        url = pres.get("url", "https://twitch.tv/discord")
        act = None
        if t_val == "playing":
            act = discord.Game(name=text)
        elif t_val == "streaming":
            act = discord.Streaming(name=text, url=url)
        elif t_val == "listening":
            act = discord.Activity(type=discord.ActivityType.listening, name=text)
        elif t_val == "watching":
            act = discord.Activity(type=discord.ActivityType.watching, name=text)
        await bot.change_presence(status=d_status, activity=act)


if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Fehler: DISCORD_TOKEN fehlt!")