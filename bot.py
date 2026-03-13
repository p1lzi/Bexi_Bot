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
LANG_DIR = 'language'

# ─────────────────────────────────────────────
#  I18N – SPRACHSYSTEM
# ─────────────────────────────────────────────
_lang_cache: dict = {}
_current_lang: str = "de"

def load_language(code: str) -> dict:
    """Lädt eine Sprachdatei aus dem lang/-Ordner."""
    path = os.path.join(LANG_DIR, f"{code}.json")
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def init_language(guild_id: str = None):
    """Initialisiert die aktive Sprache pro Server aus der config.json."""
    global _lang_cache, _current_lang
    cfg = load_config()
    if guild_id:
        code = cfg.get(guild_id, {}).get("language", "de")
    else:
        # Beim Start: ersten Server mit Spracheinstellung nehmen, sonst "de"
        code = "de"
        for key, val in cfg.items():
            if isinstance(val, dict) and "language" in val:
                code = val["language"]
                break
    _current_lang = code
    _lang_cache = load_language(_current_lang)
    if not _lang_cache:
        _current_lang = "de"
        _lang_cache = load_language("de")

def set_language(code: str, guild_id: str = None) -> bool:
    """Setzt die Sprache pro Server. Gibt True zurueck wenn erfolgreich."""
    global _lang_cache, _current_lang
    data = load_language(code)
    if not data:
        return False
    _lang_cache = data
    _current_lang = code
    if guild_id:
        cfg = load_config()
        if guild_id not in cfg:
            cfg[guild_id] = {}
        cfg[guild_id]["language"] = code
        save_config(cfg)
    return True

def t(section: str, *keys, **kwargs) -> str:
    """Übersetzt einen Text mit beliebig tiefer Verschachtelung.
    Beispiele:
      t("errors", "ban_error")
      t("embeds", "dm_ban", "title")
      t("embeds", "shared", "f_server")
    """
    node = _lang_cache.get(section, {})
    path = list(keys)
    while path:
        key = path.pop(0)
        if isinstance(node, dict):
            node = node.get(key, f"[{section}.{'.'.join(keys)}]")
        else:
            node = f"[missing: {section}.{'.'.join(keys)}]"
            break
    val = node if isinstance(node, str) else f"[not-str: {section}.{'.'.join(keys)}]"
    if kwargs:
        try:
            val = val.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return val

def td(cmd: str) -> str:
    """Command-Beschreibung: td('ban')"""
    return _lang_cache.get("commands", {}).get(cmd, {}).get("description", f"[cmd.{cmd}]")

def tp(cmd: str, param: str) -> str:
    """Parameter-Beschreibung: tp('ban','grund')"""
    return _lang_cache.get("commands", {}).get(cmd, {}).get("params", {}).get(param, f"[{cmd}.{param}]")

def tch(cmd: str, group: str, value: str) -> str:
    """Choice-Label: tch('whitelist','aktion','add')"""
    return _lang_cache.get("commands", {}).get(cmd, {}).get("choices", {}).get(group, {}).get(value, value)
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

class SelfRoleButton(discord.ui.Button):
    def __init__(self, role_data: dict, has_role: bool):
        emoji = role_data.get('emoji') or None
        label = role_data['label'][:80]
        # Grün = Rolle aktiv, Grau = Rolle nicht aktiv
        style = discord.ButtonStyle.success if has_role else discord.ButtonStyle.secondary
        super().__init__(
            label=label,
            emoji=emoji,
            style=style,
            custom_id=f"selfrole_btn_{role_data['role_id']}"
        )
        self.role_data = role_data

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_data['role_id'])
        if not role:
            return await interaction.response.send_message(
                t("errors","role_not_found"), ephemeral=True
            )

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            msg = t("success","role_removed", role=role.name)
            color = discord.Color.red()
        else:
            try:
                await interaction.user.add_roles(role)
                msg = t("success","role_added", role=role.name)
                color = discord.Color.green()
            except discord.Forbidden:
                return await interaction.response.send_message(
                    t("errors","no_permission_give_role"), ephemeral=True
                )

        # View neu aufbauen mit aktuellem Rollenstatus des Users
        # (Member-Cache nach Rollenänderung kurz warten)
        member = interaction.user
        new_view = SelfRoleView(
            roles_data=self.view.roles_data,
            panel_id=self.view.panel_id,
            member=member
        )
        await interaction.response.edit_message(view=new_view)
        await interaction.followup.send(
            embed=discord.Embed(description=msg, color=color),
            ephemeral=True
        )


class SelfRoleView(discord.ui.View):
    def __init__(self, roles_data: list, panel_id: str = "default", member: discord.Member = None):
        super().__init__(timeout=None)
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
        label="Claim Ticket",
        style=discord.ButtonStyle.blurple,
        emoji="📋",
        custom_id="persistent_claim_ticket"
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message(
                t("errors","supporter_only_claim"), ephemeral=True
            )

        embed = interaction.message.embeds[0]
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

        button.disabled = True
        button.label = t("buttons","claimed_done")
        await interaction.response.edit_message(embed=embed, view=self)

        status_embed = discord.Embed(
            description=t("success","ticket_claimed_followup", mention=interaction.user.mention),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=status_embed)

        # DM an Ticket-Ersteller
        creator_id = self.get_creator_id(interaction)
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = make_dm_embed(
                    title=t("embeds","dm_ticket_claimed","title"),
                    description=t("embeds","dm_ticket_claimed","desc"),
                    color=discord.Color.blue(),
                    guild=interaction.guild,
                    fields=[
                        (t("embeds","dm_ticket_claimed","f_server"), interaction.guild.name, True),
                        (t("embeds","dm_ticket_claimed","f_agent"), interaction.user.mention, True),
                        (t("embeds","dm_ticket_claimed","f_date"), short_time(), True),
                    ],
                    jump_url=interaction.channel.jump_url,
                    footer_system=t("embeds","shared","footer_ticket")
                )
                await send_dm(creator, embed=dm_embed)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.red,
        emoji="🔒",
        custom_id="persistent_close_ticket"
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message(
                t("errors","supporter_only_close"), ephemeral=True
            )
        await interaction.response.send_modal(TicketCloseModal(self.get_creator_id(interaction)))


# ─────────────────────────────────────────────
#  VERIFY SYSTEM
# ─────────────────────────────────────────────

class VerifyView(discord.ui.View):
    def __init__(self, role_id: int):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.verify.label = t("buttons", "verify")

    @discord.ui.button(
        label="Verify",
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
                    t("success","verify_success", role=role.name),
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    t("errors","verify_no_permission"), ephemeral=True
                )
        else:
            await interaction.response.send_message(
                t("errors","role_not_found"), ephemeral=True
            )


# ─────────────────────────────────────────────
#  TICKET SYSTEM
# ─────────────────────────────────────────────

class TicketSelect(discord.ui.Select):
    def __init__(self, options, supporter_role_ids, categories_full_data=None):
        super().__init__(
            placeholder=t("selects","ticket_placeholder"),
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
                    topic=f"Tickets: {selected_value}"
                )

                info_embed = discord.Embed(
                    title=t("embeds","ticket_channel","title", category=selected_value),
                    description=t("embeds","ticket_channel","desc", category=selected_value),
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
            t("success","ticket_created_reply", id=formatted_id, category=selected_value,
              mention=thread.mention, url=thread.jump_url),
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
            title=t("embeds","ticket_thread","title", id=formatted_id, category=selected_value),
            description=t("embeds","ticket_thread","desc", mention=interaction.user.mention),
            color=discord.Color.green(),
            timestamp=now_timestamp()
        )
        ticket_embed.add_field(name=t("embeds","ticket_thread","f_number"), value=f"`#{formatted_id}`", inline=True)
        ticket_embed.add_field(name=t("embeds","ticket_thread","f_category"), value=f"`{selected_value}`", inline=True)
        ticket_embed.add_field(name=t("embeds","ticket_thread","f_created_by"), value=interaction.user.mention, inline=True)
        ticket_embed.add_field(
            name=t("embeds","ticket_thread","f_next_steps"),
            value=t("embeds","ticket_thread","next_steps_val"),
            inline=False
        )
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
            if not isinstance(data, dict):
                continue
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
                    title=t("embeds","welcome","title", server=member.guild.name),
                    description=t("embeds","welcome","desc", mention=member.mention),
                    color=discord.Color.green(),
                    timestamp=now_timestamp()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(
                    name=t("embeds","welcome","f_user"),
                    value=member.mention,
                    inline=True
                )
                embed.add_field(
                    name=t("embeds","welcome","f_acc"),
                    value=discord.utils.format_dt(member.created_at, style="R"),
                    inline=True
                )
                embed.add_field(
                    name=t("embeds","welcome","f_member"),
                    value=f"**#{member_number}**",
                    inline=True
                )
                footer_text = f"{t('embeds','footer_bot_name')} • {member.guild.name}"
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
init_language()


# ─────────────────────────────────────────────
#  PIONEER ROLLE COMMAND
# ─────────────────────────────────────────────

@bot.tree.command(name="setup_pioneer_role", description=td("setup_pioneer_role"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    rolle=tp("setup_pioneer_role","rolle")
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


# ─────────────────────────────────────────────
#  SELFROLE COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(
    name="selfrole_create",
    description=td("selfrole_erstellen")
)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    titel=tp("selfrole_erstellen","titel"),
    beschreibung=tp("selfrole_erstellen","beschreibung"),
    farbe=tp("selfrole_erstellen","farbe"),
    rollen=tp("selfrole_erstellen","rollen")
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
            errors.append(t("errors","selfrole_bad_format", entry=entry))
            continue
        label = parts[0][:100]
        role_id_str = parts[1]
        description = parts[2][:100] if len(parts) > 2 else None

        # Emoji aus Label extrahieren
        emoji = None
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

        formatted_roles.append({
            "label": label,
            "role_id": role_id,
            "emoji": emoji,
            "description": description
        })

    if not formatted_roles:
        return await interaction.followup.send(
            t("errors","selfrole_no_roles", errors="\n".join(errors)),
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
        text=t("embeds","selfrole","panel_footer", name=interaction.guild.name, count=len(formatted_roles)),
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

    skipped = t("success","selfrole_skipped", errors="\n".join(errors)) if errors else ""
    result_msg = t("success","selfrole_panel_created", title=titel, count=len(formatted_roles), skipped=skipped)
    await interaction.followup.send(result_msg, ephemeral=True)


@bot.tree.command(
    name="selfrole_delete",
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
    name="selfrole_list",
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
@app_commands.default_permissions(administrator=True)
@app_commands.choices(aktion=[
    app_commands.Choice(name=tch("whitelist","aktion","add"), value="add"),
    app_commands.Choice(name=tch("whitelist","aktion","remove"), value="remove"),
    app_commands.Choice(name=tch("whitelist","aktion","list"), value="list")
])
@app_commands.describe(
    aktion=tp("whitelist","aktion"),
    domain=tp("whitelist","domain")
)
async def whitelist_cmd(interaction: discord.Interaction, aktion: app_commands.Choice[str], domain: str = None):
    whitelist = load_whitelist()

    if aktion.value == "list":
        domains_str = "\n".join([f"• `{d}`" for d in whitelist]) if whitelist else t("embeds","whitelist","empty")
        embed = discord.Embed(
            title=t("embeds","whitelist","title"),
            description=domains_str,
            color=discord.Color.blue(),
            timestamp=now_timestamp()
        )
        embed.set_footer(text=t("embeds","whitelist","footer", count=len(whitelist)))
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    if not domain:
        return await interaction.response.send_message(t("errors","whitelist_no_domain"), ephemeral=True)

    clean_domain = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

    if aktion.value == "add":
        if clean_domain in whitelist:
            await interaction.response.send_message(
                t("errors","whitelist_already_in", domain=clean_domain), ephemeral=True
            )
        else:
            whitelist.append(clean_domain)
            save_whitelist(whitelist)
            await interaction.response.send_message(
                t("success","whitelist_added", domain=clean_domain), ephemeral=True
            )
    elif aktion.value == "remove":
        if clean_domain in whitelist:
            whitelist.remove(clean_domain)
            save_whitelist(whitelist)
            await interaction.response.send_message(
                t("success","whitelist_removed", domain=clean_domain), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                t("errors","whitelist_not_in", domain=clean_domain), ephemeral=True
            )


# ─────────────────────────────────────────────
#  MODERATION COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="ban", description=td("ban"))
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(
    nutzer=tp("ban","nutzer"),
    grund=tp("ban","grund")
)
async def ban(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    # DM vor dem Bann senden
    dm_embed = make_dm_embed(
        title=t("embeds","dm_ban","title"),
        description=t("embeds","dm_ban","desc"),
        color=discord.Color.red(),
        guild=interaction.guild,
        fields=[
            (t("embeds","dm_ban","f_server"), interaction.guild.name, True),
            (t("embeds","dm_ban","f_mod"), str(interaction.user), True),
            (t("embeds","dm_ban","f_date"), short_time(), True),
            (t("embeds","dm_ban","f_reason"), grund, False),
        ],
        footer_system=t("embeds","shared","footer_mod")
    )
    await send_dm(nutzer, embed=dm_embed)

    try:
        await nutzer.ban(reason=grund)
        await interaction.response.send_message(
            t("success","ban_success", user=str(nutzer)), ephemeral=True
        )
        await send_log(
            interaction.guild, t("embeds","log_ban","title"),
            t("embeds","log_ban","desc"),
            discord.Color.red(), nutzer, interaction.user, grund
        )
    except Exception:
        await interaction.response.send_message(t("errors","ban_error"), ephemeral=True)


@bot.tree.command(name="kick", description=td("kick"))
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(
    nutzer=tp("kick","nutzer"),
    grund=tp("kick","grund")
)
async def kick(interaction: discord.Interaction, nutzer: discord.Member, grund: str = "Kein Grund angegeben"):
    dm_embed = make_dm_embed(
        title=t("embeds","dm_kick","title"),
        description=t("embeds","dm_kick","desc"),
        color=discord.Color.orange(),
        guild=interaction.guild,
        fields=[
            (t("embeds","dm_kick","f_server"), interaction.guild.name, True),
            (t("embeds","dm_kick","f_mod"), str(interaction.user), True),
            (t("embeds","dm_kick","f_date"), short_time(), True),
            (t("embeds","dm_kick","f_reason"), grund, False),
        ],
        footer_system=t("embeds","shared","footer_mod")
    )
    await send_dm(nutzer, embed=dm_embed)

    try:
        await nutzer.kick(reason=grund)
        await interaction.response.send_message(
            t("success","kick_success", user=str(nutzer)), ephemeral=True
        )
        await send_log(
            interaction.guild, t("embeds","log_kick","title"),
            t("embeds","log_kick","desc"),
            discord.Color.orange(), nutzer, interaction.user, grund
        )
    except Exception:
        await interaction.response.send_message(t("errors","kick_error"), ephemeral=True)


@bot.tree.command(name="timeout", description=td("timeout"))
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    nutzer=tp("timeout","nutzer"),
    minuten=tp("timeout","minuten"),
    grund="Der Grund für den Timeout — wird dem Nutzer per DM mitgeteilt"
)
async def timeout(interaction: discord.Interaction, nutzer: discord.Member, minuten: int, grund: str = "Kein Grund angegeben"):
    timeout_ends = discord.utils.format_dt(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minuten),
        style="R"
    )
    until_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minuten)
    dm_embed = make_dm_embed(
        title=t("embeds","dm_timeout","title"),
        description=t("embeds","dm_timeout","desc", server=interaction.guild.name, until=discord.utils.format_dt(until_dt)),
        color=discord.Color.light_grey(),
        guild=interaction.guild,
        fields=[
            (t("embeds","dm_timeout","f_server"), interaction.guild.name, True),
            (t("embeds","dm_timeout","f_mod"), str(interaction.user), True),
            (t("embeds","dm_timeout","f_dur"), t("embeds","dm_timeout","dur_val", minutes=minuten), True),
            (t("embeds","dm_timeout","f_ends"), timeout_ends, True),
            (t("embeds","dm_timeout","f_reason"), grund, False),
        ],
        footer_system=t("embeds","shared","footer_mod")
    )
    await send_dm(nutzer, embed=dm_embed)

    try:
        duration = datetime.timedelta(minutes=minuten)
        await nutzer.timeout(duration, reason=grund)
        await interaction.response.send_message(
            t("success","timeout_success", user=str(nutzer), minutes=minuten), ephemeral=True
        )
        await send_log(
            interaction.guild, t("embeds","log_timeout","title"),
            t("embeds","log_timeout","desc"),
            discord.Color.light_grey(), nutzer, interaction.user, grund,
            extra_fields=[(t("embeds","log_timeout","f_dur"), f"`{minuten}`", True)]
        )
    except Exception:
        await interaction.response.send_message(t("errors","timeout_error"), ephemeral=True)


@bot.tree.command(name="warn", description=td("warn"))
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    nutzer=tp("warn","nutzer"),
    grund=tp("warn","grund")
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
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(
    nutzer=tp("warn_edit","nutzer"),
    anzahl=tp("warn_edit","anzahl")
)
async def warn_edit(interaction: discord.Interaction, nutzer: discord.Member, anzahl: int):
    if anzahl < 0:
        return await interaction.response.send_message(
            t("errors","warn_negative"), ephemeral=True
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

    msg = t("success","warn_edit_changed", mention=nutzer.mention, old=alte_anzahl, new=anzahl)
    if anzahl == 0:
        msg = t("success","warn_edit_reset", mention=nutzer.mention)

    await interaction.response.send_message(msg, ephemeral=True)
    await send_log(
        interaction.guild, t("embeds","log_warn_edit","title"),
        t("embeds","log_warn_edit","desc"),
        discord.Color.blue(), nutzer, interaction.user,
        extra_fields=[
            (t("embeds","log_warn_edit","f_change"), f"`{alte_anzahl}` ➔ `{anzahl}`", True)
        ]
    )


@bot.tree.command(name="userinfo", description=td("userinfo"))
@app_commands.describe(
    nutzer=tp("userinfo","nutzer")
)
async def userinfo(interaction: discord.Interaction, nutzer: discord.Member = None):
    # Prüfen ob jemand anderes angegeben wurde
    if nutzer is not None and nutzer.id != interaction.user.id:
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                t("errors","userinfo_no_permission"), ephemeral=True
            )

    target = nutzer or interaction.user
    gid = str(interaction.guild_id)
    config = load_config()

    warns = 0
    if gid in config and "warns" in config[gid]:
        warns = config[gid]["warns"].get(str(target.id), 0)

    roles = [role.mention for role in target.roles if role != interaction.guild.default_role]

    warn_display = t("embeds","userinfo","warns_none") if warns == 0 else t("embeds","userinfo","warns_fmt", count=warns)

    embed = discord.Embed(
        title=f"👤 {target.display_name}",
        color=target.color if target.color.value != 0 else discord.Color.blurple(),
        timestamp=now_timestamp()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name=t("embeds","userinfo","f_id"), value=f"`{target.id}`", inline=True)
    embed.add_field(name=t("embeds","userinfo","f_warns"), value=warn_display, inline=True)
    embed.add_field(name=t("embeds","userinfo","f_bot"), value=t("embeds","userinfo","bot_yes") if target.bot else t("embeds","userinfo","bot_no"), inline=True)
    embed.add_field(
        name=t("embeds","userinfo","f_joined"),
        value=target.joined_at.strftime("%d.%m.%Y") if target.joined_at else t("embeds","userinfo","joined_unk"),
        inline=True
    )
    embed.add_field(
        name=t("embeds","userinfo","f_created"),
        value=target.created_at.strftime("%d.%m.%Y"),
        inline=True
    )
    embed.add_field(name=t("embeds","userinfo","f_roles"), value=" ".join(roles) if roles else t("embeds","userinfo","roles_none"), inline=False)
    if interaction.guild.icon:
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────
#  CONFIG COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="set_log_channel", description=td("set_log_channel"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    kanal=tp("set_log_channel","kanal")
)
async def set_log_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid]["log_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(
        t("success","log_channel_set", channel=kanal.mention), ephemeral=True
    )


@bot.tree.command(name="set_welcome_channel", description=td("set_welcome_channel"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    kanal=tp("set_welcome_channel","kanal")
)
async def set_welcome_channel(interaction: discord.Interaction, kanal: discord.TextChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid]["welcome_channel_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(
        t("success","welcome_channel_set", channel=kanal.mention), ephemeral=True
    )


@bot.tree.command(name="set_waiting_room", description=td("set_waiting_room"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    kanal=tp("set_waiting_room","kanal")
)
async def set_waiting_room(interaction: discord.Interaction, kanal: discord.VoiceChannel):
    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid]["waiting_room_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(
        t("success","waiting_room_set", channel=kanal.mention), ephemeral=True
    )


@bot.tree.command(name="setup_verify", description=td("setup_verify"))
@app_commands.default_permissions(administrator=True)
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

    view = VerifyView(rolle.id)
    msg = await interaction.channel.send(embed=embed, view=view)

    config = load_config()
    gid = str(interaction.guild_id)
    if gid not in config:
        config[gid] = {}
    config[gid].setdefault("verify_panels", []).append({"role_id": rolle.id, "msg_id": msg.id})
    save_config(config)
    await interaction.response.send_message(t("success","verify_panel_created"), ephemeral=True)


@bot.tree.command(name="status_config", description=td("status_config"))
@app_commands.default_permissions(administrator=True)
@app_commands.choices(status=[
    app_commands.Choice(name=tch("status_config","status","online"), value="online"),
    app_commands.Choice(name=tch("status_config","status","idle"), value="idle"),
    app_commands.Choice(name=tch("status_config","status","dnd"), value="dnd"),
    app_commands.Choice(name=tch("status_config","status","invisible"), value="invisible")
])
@app_commands.choices(aktivitaet_typ=[
    app_commands.Choice(name=tch("status_config","aktivitaet_typ","playing"), value="playing"),
    app_commands.Choice(name=tch("status_config","aktivitaet_typ","streaming"), value="streaming"),
    app_commands.Choice(name=tch("status_config","aktivitaet_typ","listening"), value="listening"),
    app_commands.Choice(name=tch("status_config","aktivitaet_typ","watching"), value="watching")
])
@app_commands.describe(
    status=tp("status_config","status"),
    aktivitaet_typ=tp("status_config","aktivitaet_typ"),
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
    await interaction.response.send_message(t("success","status_updated"), ephemeral=True)


# ─────────────────────────────────────────────
#  TICKET SETUP COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="setup_tickets", description=td("setup_tickets"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    supporter_rollen=tp("setup_tickets","supporter_rollen"),
    kategorien="Kategorien im Format: 'Name|Beschreibung', mehrere in Anführungszeichen mit Komma trennen"
)
async def setup_tickets(interaction: discord.Interaction, supporter_rollen: str, kategorien: str):
    guild_id = str(interaction.guild_id)
    role_ids = extract_role_ids(supporter_rollen)
    if not role_ids:
        return await interaction.response.send_message(
            t("errors","no_valid_role"), ephemeral=True
        )

    # Hochkommas und Anführungszeichen aus dem gesamten String entfernen
    kategorien_clean = kategorien.replace("'", "").replace('"', "")
    # Kategorien per Komma trennen
    raw_list = [c.strip() for c in kategorien_clean.split(",") if c.strip()]

    if not raw_list:
        return await interaction.response.send_message(
            t("errors","no_categories"),
            ephemeral=True
        )

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

    config = load_config()
    if guild_id not in config:
        config[guild_id] = {}

    view = TicketView(formatted_cats, role_ids)
    default_title = t("embeds","ticket_panel","title")
    embed = discord.Embed(
        title=default_title,
        description=t("embeds","ticket_panel","desc"),
        color=discord.Color.gold()
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=t("embeds","ticket_panel","footer", name=interaction.guild.name))

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
    success_msg = t("success","ticket_panel_created", id=message.id)
    if parse_errors:
        success_msg += t("success","skipped_entries", entries="\n".join(parse_errors))
    await interaction.response.send_message(success_msg, ephemeral=True)


@bot.tree.command(name="ticket_edit", description=td("ticket_edit"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    message_id=tp("ticket_edit","message_id"),
    titel=tp("ticket_edit","titel"),
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
        return await interaction.response.send_message(t("errors","panel_not_found"), ephemeral=True)
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
        await interaction.response.send_message(t("success","ticket_panel_updated"), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(t("errors","generic_error", error=str(e)), ephemeral=True)


@bot.tree.command(name="ticket_delete", description=td("ticket_delete"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    message_id=tp("ticket_delete","message_id")
)
async def ticket_delete(interaction: discord.Interaction, message_id: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("ticket_panels", [])
    target = next((p for p in panels if str(p["message_id"]) == message_id), None)
    if not target:
        return await interaction.response.send_message(t("errors","panel_not_found"), ephemeral=True)
    panels.remove(target)
    save_config(config)
    try:
        channel = (
            interaction.guild.get_channel(target["channel_id"])
            or await interaction.guild.fetch_channel(target["channel_id"])
        )
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()
        await interaction.response.send_message(t("success","ticket_panel_deleted"), ephemeral=True)
    except Exception:
        await interaction.response.send_message(t("errors","panel_removed_only"), ephemeral=True)


# ─────────────────────────────────────────────
#  BASIS COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="set_language", description=td("set_language"))
@app_commands.default_permissions(administrator=True)
@app_commands.choices(sprache=[
    app_commands.Choice(name="🇩🇪 Deutsch", value="de"),
    app_commands.Choice(name="🇬🇧 English", value="en"),
])
@app_commands.describe(sprache=tp("set_language","sprache"))
async def set_language_cmd(interaction: discord.Interaction, sprache: app_commands.Choice[str]):
    ok = set_language(sprache.value, guild_id=str(interaction.guild_id))
    if not ok:
        return await interaction.response.send_message(
            t("errors", "unknown_language"), ephemeral=True
        )
    await interaction.response.send_message(
        t("success", "language_set"), ephemeral=True
    )


@bot.tree.command(name="ping", description=td("ping"))
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    color = discord.Color.green() if latency < 100 else discord.Color.orange() if latency < 200 else discord.Color.red()
    embed = discord.Embed(
        title=t("embeds","ping","title"),
        description=t("embeds","ping","desc", ms=latency),
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