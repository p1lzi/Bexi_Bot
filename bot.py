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
_current_lang: str = "en"

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
        code = cfg.get(guild_id, {}).get("language", "en")
    else:
        # Beim Start: ersten Server mit Spracheinstellung nehmen, sonst "de"
        code = "en"
        for key, val in cfg.items():
            if isinstance(val, dict) and "language" in val:
                code = val["language"]
                break
    _current_lang = code
    _lang_cache = load_language(_current_lang)
    if not _lang_cache:
        _current_lang = "en"
        _lang_cache = load_language("en")

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
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
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

        main_category_name = "▄▬▬「Tickets」▬▬▄"
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
#  APPLICATION SYSTEM
# ─────────────────────────────────────────────

pending_applications: dict = {}
QUESTIONS_PER_STEP = 4

DEFAULT_APPLICATION_QUESTIONS = [
    {"label": "Roblox Username",                "placeholder": "Your Roblox username",                             "style": "short",    "required": True},
    {"label": "Roblox User ID",                 "placeholder": "Your Roblox User ID (numbers only)",              "style": "short",    "required": True},
    {"label": "Discord Name + Tag",             "placeholder": "e.g. username or username#0000",                  "style": "short",    "required": True},
    {"label": "Age",                            "placeholder": "Your age",                                         "style": "short",    "required": True},
    {"label": "Timezone",                       "placeholder": "e.g. UTC+1, EST, PST",                            "style": "short",    "required": True},
    {"label": "Country / Region",               "placeholder": "e.g. Germany, USA",                               "style": "short",    "required": True},
    {"label": "Previous Staff Experience?",     "placeholder": "Yes/No — If yes: servers, position, why left",   "style": "paragraph","required": True},
    {"label": "ERLC Moderation Experience?",    "placeholder": "Yes/No — tools used, situations handled",        "style": "paragraph","required": True},
    {"label": "Why do you want to be staff?",   "placeholder": "Minimum 5 sentences",                             "style": "paragraph","required": True},
    {"label": "What makes you a good staff?",   "placeholder": "Minimum 5 sentences",                             "style": "paragraph","required": True},
    {"label": "Your Strengths",                 "placeholder": "List your strengths",                             "style": "paragraph","required": True},
    {"label": "Your Weaknesses",                "placeholder": "List your weaknesses",                            "style": "paragraph","required": True},
    {"label": "Daily Activity (hours)",         "placeholder": "1-2h / 2-4h / 4-6h / 6+h",                      "style": "short",    "required": True},
    {"label": "When are you usually online?",   "placeholder": "e.g. evenings 6pm-10pm UTC+1",                   "style": "short",    "required": True},
    {"label": "Handle tickets regularly?",      "placeholder": "Yes / No",                                        "style": "short",    "required": True},
    {"label": "Player insults you in RP?",      "placeholder": "Describe your response",                          "style": "paragraph","required": True},
    {"label": "Two players yelling in ticket?", "placeholder": "How do you de-escalate?",                         "style": "paragraph","required": True},
    {"label": "Friend breaking rules?",         "placeholder": "How do you handle it?",                           "style": "paragraph","required": True},
    {"label": "Accused of being unfair?",       "placeholder": "How do you react?",                               "style": "paragraph","required": True},
    {"label": "Unsure if rule was broken?",     "placeholder": "What steps do you take?",                         "style": "paragraph","required": True},
    {"label": "Define: FRP / RDM / VDM",        "placeholder": "Explain each term briefly",                       "style": "paragraph","required": True},
    {"label": "Define: FearRP / Meta / CombLog","placeholder": "Explain each term briefly",                       "style": "paragraph","required": True},
    {"label": "What is staff abuse?",           "placeholder": "Your definition",                                  "style": "paragraph","required": True},
    {"label": "What must staff NEVER do?",      "placeholder": "Even when off-duty",                               "style": "paragraph","required": True},
    {"label": "Working microphone? (Yes/No)",   "placeholder": "Yes / No",                                        "style": "short",    "required": True},
    {"label": "Voice tickets? (Yes/No)",        "placeholder": "Yes / No",                                        "style": "short",    "required": True},
    {"label": "Can record evidence? (Yes/No)",  "placeholder": "Yes / No",                                        "style": "short",    "required": True},
    {"label": "Accept staff rules & removal?",  "placeholder": "Yes / No",                                        "style": "short",    "required": True},
    {"label": "All info is truthful? (Yes/No)", "placeholder": "Yes / No",                                        "style": "short",    "required": True},
]

QUESTION_SECTIONS = {
    0:  "👤  Personal Information",
    6:  "🏆  Experience",
    8:  "💬  Motivation",
    12: "📅  Activity",
    15: "⚡  Situation Questions",
    20: "📖  Rule Knowledge",
    24: "🔧  Technical",
    27: "✅  Agreement",
}


def get_application_steps(questions: list) -> list:
    steps = []
    for i in range(0, len(questions), QUESTIONS_PER_STEP):
        steps.append(questions[i:i + QUESTIONS_PER_STEP])
    return steps


def _section_for_index(idx: int) -> str:
    result = "📋  Application"
    for sec_idx in sorted(QUESTION_SECTIONS.keys()):
        if idx >= sec_idx:
            result = QUESTION_SECTIONS[sec_idx]
    return result


def build_review_embeds(guild, applicant, answers, panel_title, questions) -> list:
    """Build structured multi-embed review with section grouping."""
    BLURPLE = discord.Color.from_rgb(88, 101, 242)

    # ── Header Embed ──────────────────────────────────────────────────────────
    header = discord.Embed(color=BLURPLE, timestamp=now_timestamp())
    header.set_author(
        name=t("embeds", "application", "review_author", title=panel_title),
        icon_url=applicant.display_avatar.url
    )
    joined_str = discord.utils.format_dt(applicant.joined_at, style="R") if applicant.joined_at else "—"
    header.description = "\n".join([
        t("embeds", "application", "review_applicant") + f" {applicant.mention}  `{applicant.id}`",
        t("embeds", "application", "review_account")   + f" {discord.utils.format_dt(applicant.created_at, style='R')}",
        t("embeds", "application", "review_joined")    + " " + joined_str,
        t("embeds", "application", "review_submitted") + f" {discord.utils.format_dt(now_timestamp(), style='f')}",
    ])
    header.set_thumbnail(url=applicant.display_avatar.url)
    if guild.icon:
        header.set_footer(
            text=guild.name + "  •  " + t("embeds", "application", "footer"),
            icon_url=guild.icon.url
        )
    else:
        header.set_footer(text=guild.name + "  •  " + t("embeds", "application", "footer"))

    embeds = [header]

    # ── Answer Embeds — grouped by section ────────────────────────────────────
    current_section = None
    current_embed = None
    field_count = 0

    for i, (label, value) in enumerate(answers):
        global_idx = next((j for j, q in enumerate(questions) if q["label"] == label), i)
        section = _section_for_index(global_idx)

        # New embed when section changes or field limit reached
        if section != current_section or current_embed is None or field_count >= 5:
            new_emb = discord.Embed(
                title=section if section != current_section else None,
                color=BLURPLE
            )
            embeds.append(new_emb)
            current_embed = new_emb
            current_section = section
            field_count = 0

        display_value = ("```" + value[:950] + "```") if len(value) > 80 else (value[:1024] or "*— —*")
        current_embed.add_field(name=label, value=display_value, inline=False)
        field_count += 1

    return embeds





# ── Application Setup Wizard ──────────────────────────────────────────────────
_setup_wizard_state: dict = {}


def _build_wizard_embed(state: dict, guild) -> discord.Embed:
    """Builds a status embed showing current wizard progress."""
    BLURPLE = discord.Color.from_rgb(88, 101, 242)
    embed = discord.Embed(
        title=t("embeds", "wizard", "title"),
        color=BLURPLE
    )

    # Step 1 — Basic info
    title_val   = state.get("title") or t("embeds", "wizard", "not_set")
    channel_id  = state.get("review_channel_id")
    channel_val = ("<#" + str(channel_id) + ">") if channel_id else t("embeds", "wizard", "not_set")
    role_ids    = state.get("reviewer_role_ids", [])
    roles_val   = (" ".join("<@&" + str(r) + ">" for r in role_ids)
                   if role_ids else t("embeds", "wizard", "not_set"))

    embed.add_field(
        name=t("embeds", "wizard", "f_step1"),
        value=(
            t("embeds", "wizard", "f_title")   + " " + title_val + "\n" +
            t("embeds", "wizard", "f_channel")  + " " + channel_val + "\n" +
            t("embeds", "wizard", "f_roles")    + " " + roles_val
        ),
        inline=False
    )

    # Step 2 — Questions (grouped by section)
    questions = state.get("questions")
    current_section = state.get("current_section")
    if questions is None:
        q_val = t("embeds", "wizard", "q_default")
        embed.add_field(
            name=t("embeds", "wizard", "f_step2") + " (—)",
            value=q_val,
            inline=False
        )
    elif len(questions) == 0:
        q_val = t("embeds", "wizard", "q_none")
        embed.add_field(
            name=t("embeds", "wizard", "f_step2") + " (0)",
            value=q_val,
            inline=False
        )
    else:
        # Group by section
        shown = 0
        last_section = None
        field_lines = []
        field_name = t("embeds", "wizard", "f_step2") + " (" + str(len(questions)) + ")"
        for i, q in enumerate(questions):
            if shown >= 15:
                field_lines.append(t("embeds", "wizard", "q_more", n=len(questions) - shown))
                break
            sec = q.get("section") or ""
            if sec and sec != last_section:
                field_lines.append("__**" + sec + "**__")
                last_section = sec
            min_l = q.get("min_length", 0)
            ph    = q.get("placeholder", "")
            style = q.get("style", "paragraph")
            meta_parts = []
            if style == "short":
                meta_parts.append(t("embeds", "wizard", "q_meta_short"))
            if min_l:
                meta_parts.append(t("embeds", "wizard", "q_meta_minlen", n=min_l))
            if ph:
                meta_parts.append(t("embeds", "wizard", "q_meta_ph", ph=ph[:25]))
            meta = ("  `" + " · ".join(meta_parts) + "`") if meta_parts else ""
            field_lines.append("**" + str(i + 1) + ".** " + q["label"] + meta)
            shown += 1
        embed.add_field(name=field_name, value="\n".join(field_lines) or "—", inline=False)

    # Active section indicator
    if current_section:
        embed.add_field(
            name=t("embeds", "wizard", "f_current_section"),
            value="`" + current_section + "`",
            inline=False
        )

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    else:
        embed.set_footer(text=guild.name if guild else "Bexi Bot")
    return embed


class AppSetupStep1Modal(discord.ui.Modal):
    """Step 1: Title + Description + Review channel + Reviewer role"""
    def __init__(self):
        super().__init__(title=t("modals", "app_setup_s1_title"))
        self.f_title = discord.ui.TextInput(
            label=t("modals", "app_setup_title_label"),
            placeholder=t("modals", "app_setup_title_ph"),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "app_setup_desc_label"),
            placeholder=t("modals", "app_setup_desc_ph"),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.f_channel = discord.ui.TextInput(
            label=t("modals", "app_setup_channel_label"),
            placeholder=t("modals", "app_setup_channel_ph"),
            style=discord.TextStyle.short, required=True, max_length=30
        )
        self.f_role = discord.ui.TextInput(
            label=t("modals", "app_setup_role_label"),
            placeholder=t("modals", "app_setup_role_ph"),
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)
        self.add_item(self.f_channel)
        self.add_item(self.f_role)

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id

        channel_raw = self.f_channel.value.strip().lstrip("<#").rstrip(">")
        try:
            channel = interaction.guild.get_channel(int(channel_raw))
        except ValueError:
            channel = discord.utils.get(interaction.guild.text_channels, name=channel_raw.lstrip("#"))
        if not channel:
            return await interaction.response.send_message(
                t("errors", "setup_channel_not_found"), ephemeral=True
            )

        reviewer_role_ids = []
        if self.f_role.value.strip():
            reviewer_role_ids = [rid for rid in extract_role_ids(self.f_role.value)
                                 if interaction.guild.get_role(rid)]

        _setup_wizard_state[uid] = {
            "title":             self.f_title.value,
            "desc":              self.f_desc.value or "",
            "review_channel_id": channel.id,
            "reviewer_role_ids": reviewer_role_ids,
            "questions":         [],
            "current_section":   None,
            "use_default":       None
        }

        embed = _build_wizard_embed(_setup_wizard_state[uid], interaction.guild)
        view  = AppSetupMainView(uid)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AppSetupSectionModal(discord.ui.Modal):
    """Set the active section/category for subsequent questions."""
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "app_setup_section_title"))
        self.user_id = user_id
        state = _setup_wizard_state.get(user_id, {})
        self.f_section = discord.ui.TextInput(
            label=t("modals", "app_setup_section_label"),
            placeholder=t("modals", "app_setup_section_ph"),
            default=state.get("current_section") or "",
            style=discord.TextStyle.short, required=False, max_length=60
        )
        self.add_item(self.f_section)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _setup_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        val = self.f_section.value.strip() or None
        _setup_wizard_state[uid]["current_section"] = val
        embed = _build_wizard_embed(_setup_wizard_state[uid], interaction.guild)
        view  = AppSetupMainView(uid)
        await interaction.response.edit_message(embed=embed, view=view)


class AppSetupMainView(discord.ui.View):
    """Main wizard hub — shown after step 1, always visible between actions."""
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.edit_info_btn.label    = t("buttons", "wizard_edit_info")
        self.add_q_btn.label        = t("buttons", "wizard_add_q")
        self.add_section_btn.label  = t("buttons", "wizard_add_section")
        self.default_q_btn.label    = t("buttons", "wizard_default_q")
        self.clear_q_btn.label      = t("buttons", "wizard_clear_q")
        self.remove_last_btn.label  = t("buttons", "wizard_remove_last")
        self.preview_btn.label      = t("buttons", "wizard_preview")
        self.finish_btn.label       = t("buttons", "wizard_finish")
        self.cancel_btn.label       = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def _refresh(self, interaction: discord.Interaction):
        """Re-render the wizard embed in place."""
        state = _setup_wizard_state.get(self.user_id)
        if not state:
            return
        embed = _build_wizard_embed(state, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    # ── Row 0 ──────────────────────────────────────────────────────────────────
    @discord.ui.button(label="✏️ Edit Info",     style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AppSetupEditInfoModal(self.user_id))

    @discord.ui.button(label="➕ Add Questions", style=discord.ButtonStyle.blurple,   row=0)
    async def add_q_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _setup_wizard_state.get(self.user_id, {})
        if state.get("questions") is None:
            _setup_wizard_state[self.user_id]["questions"] = []
        await interaction.response.send_modal(AppSetupQuestionsModal(self.user_id))

    @discord.ui.button(label="📂 Add Section",       style=discord.ButtonStyle.secondary, row=0)
    async def add_section_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _setup_wizard_state.get(self.user_id, {})
        if state.get("questions") is None:
            _setup_wizard_state[self.user_id]["questions"] = []
        await interaction.response.send_modal(AppSetupSectionModal(self.user_id))

    # ── Row 1 ──────────────────────────────────────────────────────────────────
    @discord.ui.button(label="✅ Default Questions", style=discord.ButtonStyle.green,  row=1)
    async def default_q_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _setup_wizard_state[self.user_id]["questions"] = None
        await self._refresh(interaction)

    @discord.ui.button(label="🗑️ Clear Questions",  style=discord.ButtonStyle.danger,   row=1)
    async def clear_q_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _setup_wizard_state[self.user_id]["questions"] = []
        _setup_wizard_state[self.user_id]["current_section"] = None
        await self._refresh(interaction)

    @discord.ui.button(label="↩️ Remove Last",      style=discord.ButtonStyle.secondary, row=1)
    async def remove_last_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _setup_wizard_state.get(self.user_id, {})
        questions = state.get("questions")
        if not questions:
            return await interaction.response.send_message(t("errors", "app_no_questions"), ephemeral=True)
        questions.pop()
        await self._refresh(interaction)

    # ── Row 2 ──────────────────────────────────────────────────────────────────
    @discord.ui.button(label="👁️ Preview",          style=discord.ButtonStyle.secondary, row=2)
    async def preview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _setup_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        questions = state.get("questions") or DEFAULT_APPLICATION_QUESTIONS
        # Build preview: show panel embed + first step modal fields as description
        BLURPLE = discord.Color.from_rgb(88, 101, 242)
        preview_embed = discord.Embed(
            title=state.get("title") or t("embeds", "application", "default_title"),
            description=state.get("desc") or t("embeds", "application", "default_desc"),
            color=BLURPLE,
            timestamp=now_timestamp()
        )
        if interaction.guild.icon:
            preview_embed.set_thumbnail(url=interaction.guild.icon.url)
        preview_embed.set_footer(
            text=t("embeds", "application", "panel_footer", name=interaction.guild.name)
        )
        # Show questions as fields grouped by section
        last_sec = None
        shown = 0
        for q in questions:
            if shown >= 20:
                preview_embed.add_field(
                    name="...",
                    value=t("embeds", "wizard", "q_more", n=len(questions) - shown),
                    inline=False
                )
                break
            sec = q.get("section") or ""
            if sec and sec != last_sec:
                preview_embed.add_field(name="━━━  " + sec + "  ━━━", value="", inline=False)
                last_sec = sec
            min_l = q.get("min_length", 0)
            meta  = (" *(min. " + str(min_l) + " chars)*") if min_l else ""
            ph    = q.get("placeholder") or t("embeds", "wizard", "preview_answer_ph")
            preview_embed.add_field(
                name=q["label"] + meta,
                value="> " + ph[:80],
                inline=False
            )
            shown += 1
        await interaction.response.send_message(
            content=t("success", "wizard_preview_note"),
            embed=preview_embed,
            ephemeral=True
        )

    @discord.ui.button(label="🚀 Finish & Create",  style=discord.ButtonStyle.green,   row=2)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _setup_wizard_state.get(self.user_id)
        if not state or not state.get("title") or not state.get("review_channel_id"):
            return await interaction.response.send_message(
                t("errors", "wizard_incomplete"), ephemeral=True
            )
        await self._finalize(interaction)

    @discord.ui.button(label="✖️ Cancel",           style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _setup_wizard_state.pop(self.user_id, None)
        await interaction.response.edit_message(
            content=t("errors", "application_cancelled"),
            embed=None, view=None
        )

    async def _finalize(self, interaction: discord.Interaction):
        state = _setup_wizard_state.pop(self.user_id, None)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        guild_id    = str(interaction.guild_id)
        config      = load_config()
        if guild_id not in config:
            config[guild_id] = {}
        panel_index = len(config[guild_id].get("application_panels", []))
        panel_title = state["title"]
        panel_desc  = state["desc"] or t("embeds", "application", "default_desc")
        questions   = state.get("questions")  # None = use default

        embed = discord.Embed(
            title=panel_title, description=panel_desc,
            color=discord.Color.blurple(), timestamp=now_timestamp()
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=t("embeds", "application", "panel_footer", name=interaction.guild.name))

        view    = ApplicationPanelView(panel_index=panel_index)
        message = await interaction.channel.send(embed=embed, view=view)
        config[guild_id].setdefault("application_panels", []).append({
            "message_id":        message.id,
            "channel_id":        interaction.channel_id,
            "review_channel_id": state["review_channel_id"],
            "reviewer_role_ids": state.get("reviewer_role_ids", []),
            "title":             panel_title,
            "questions":         questions
        })
        save_config(config)
        review_ch  = interaction.guild.get_channel(state["review_channel_id"])
        ch_mention = review_ch.mention if review_ch else str(state["review_channel_id"])

        done_embed = discord.Embed(
            title=t("embeds", "wizard", "done_title"),
            description=t("success", "application_panel_created",
                          id=message.id, channel=ch_mention),
            color=discord.Color.green(),
            timestamp=now_timestamp()
        )
        if interaction.guild.icon:
            done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=done_embed, view=None)


class AppSetupEditInfoModal(discord.ui.Modal):
    """Re-edit title, desc, channel, roles after step 1."""
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "app_setup_edit_title"))
        self.user_id = user_id
        state = _setup_wizard_state.get(user_id, {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "app_setup_title_label"),
            placeholder=t("modals", "app_setup_title_ph"),
            default=state.get("title", ""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "app_setup_desc_label"),
            placeholder=t("modals", "app_setup_desc_ph"),
            default=state.get("desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.f_channel = discord.ui.TextInput(
            label=t("modals", "app_setup_channel_label"),
            placeholder=t("modals", "app_setup_channel_ph"),
            default=str(state.get("review_channel_id", "")),
            style=discord.TextStyle.short, required=True, max_length=30
        )
        self.f_role = discord.ui.TextInput(
            label=t("modals", "app_setup_role_label"),
            placeholder=t("modals", "app_setup_role_ph"),
            default=" ".join(str(r) for r in state.get("reviewer_role_ids", [])),
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)
        self.add_item(self.f_channel)
        self.add_item(self.f_role)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _setup_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        channel_raw = self.f_channel.value.strip().lstrip("<#").rstrip(">")
        try:
            channel = interaction.guild.get_channel(int(channel_raw))
        except ValueError:
            channel = discord.utils.get(interaction.guild.text_channels, name=channel_raw.lstrip("#"))
        if not channel:
            return await interaction.response.send_message(t("errors", "setup_channel_not_found"), ephemeral=True)

        reviewer_role_ids = []
        if self.f_role.value.strip():
            reviewer_role_ids = [rid for rid in extract_role_ids(self.f_role.value)
                                 if interaction.guild.get_role(rid)]

        _setup_wizard_state[uid].update({
            "title":             self.f_title.value,
            "desc":              self.f_desc.value or "",
            "review_channel_id": channel.id,
            "reviewer_role_ids": reviewer_role_ids,
        })

        embed = _build_wizard_embed(_setup_wizard_state[uid], interaction.guild)
        view  = AppSetupMainView(uid)
        await interaction.response.edit_message(embed=embed, view=view)


class AppSetupQuestionsModal(discord.ui.Modal):
    """Add one question with label, placeholder and min_length per modal."""
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "app_setup_q_title"))
        self.user_id = user_id
        existing_count = len(_setup_wizard_state.get(user_id, {}).get("questions") or [])
        self.q_num = existing_count + 1

        self.f_label = discord.ui.TextInput(
            label=t("modals", "app_setup_q_label"),
            placeholder=t("modals", "app_setup_q_label_ph"),
            style=discord.TextStyle.short,
            required=True,
            max_length=45
        )
        self.f_placeholder = discord.ui.TextInput(
            label=t("modals", "app_setup_q_placeholder_label"),
            placeholder=t("modals", "app_setup_q_placeholder_ph"),
            style=discord.TextStyle.short,
            required=False,
            max_length=100
        )
        self.f_min_length = discord.ui.TextInput(
            label=t("modals", "app_setup_q_minlen_label"),
            placeholder=t("modals", "app_setup_q_minlen_ph"),
            style=discord.TextStyle.short,
            required=False,
            max_length=4
        )
        self.f_style = discord.ui.TextInput(
            label=t("modals", "app_setup_q_style_label"),
            placeholder=t("modals", "app_setup_q_style_ph"),
            style=discord.TextStyle.short,
            required=False,
            max_length=10
        )
        self.add_item(self.f_label)
        self.add_item(self.f_placeholder)
        self.add_item(self.f_min_length)
        self.add_item(self.f_style)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _setup_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        if _setup_wizard_state[uid].get("questions") is None:
            _setup_wizard_state[uid]["questions"] = []

        # Parse min_length
        min_len = 0
        try:
            min_len = max(0, int(self.f_min_length.value.strip()))
        except (ValueError, AttributeError):
            min_len = 0

        # Parse style: "short"/"s" or default paragraph
        style_raw = (self.f_style.value or "").strip().lower()
        style = "short" if style_raw in ("short", "s", "kurz", "k") else "paragraph"

        _setup_wizard_state[uid]["questions"].append({
            "label":       self.f_label.value.strip()[:45],
            "placeholder": (self.f_placeholder.value or "").strip()[:100],
            "style":       style,
            "required":    True,
            "min_length":  min_len,
            "section":     _setup_wizard_state[uid].get("current_section") or ""
        })

        embed = _build_wizard_embed(_setup_wizard_state[uid], interaction.guild)
        view  = AppSetupMainView(uid)
        await interaction.response.edit_message(embed=embed, view=view)





class ApplicationReviewView(discord.ui.View):
    def __init__(self, applicant_id: int, thread_id: int = None, review_channel_id: int = None):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.thread_id = thread_id
        self.review_channel_id = review_channel_id
        self.accept_btn.label   = t("buttons", "app_accept")
        self.decline_btn.label  = t("buttons", "app_decline")
        self.question_btn.label = t("buttons", "app_question")

    def _check_perm(self, interaction: discord.Interaction) -> bool:
        return (interaction.user.guild_permissions.manage_guild
                or interaction.user.guild_permissions.administrator)

    @discord.ui.button(label="Accept",   style=discord.ButtonStyle.green,  emoji="✅", custom_id="app_review_accept")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction):
            return await interaction.response.send_message(t("errors", "no_permission_review"), ephemeral=True)
        await interaction.response.send_modal(
            ApplicationDecisionModal(self.applicant_id, "accept", interaction.user, interaction.guild, self.thread_id)
        )

    @discord.ui.button(label="Decline",  style=discord.ButtonStyle.red,    emoji="❌", custom_id="app_review_decline")
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction):
            return await interaction.response.send_message(t("errors", "no_permission_review"), ephemeral=True)
        await interaction.response.send_modal(
            ApplicationDecisionModal(self.applicant_id, "decline", interaction.user, interaction.guild, self.thread_id)
        )

    @discord.ui.button(label="Question", style=discord.ButtonStyle.blurple, emoji="❓", custom_id="app_review_question")
    async def question_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check_perm(interaction):
            return await interaction.response.send_message(t("errors", "no_permission_review"), ephemeral=True)
        await interaction.response.send_modal(
            ApplicationDecisionModal(self.applicant_id, "question", interaction.user, interaction.guild, self.thread_id)
        )


class ApplicationDecisionModal(discord.ui.Modal):
    def __init__(self, applicant_id: int, decision: str, reviewer, guild, thread_id: int = None):
        title_keys = {"accept": "app_accept_title", "decline": "app_decline_title", "question": "app_question_title"}
        super().__init__(title=t("modals", title_keys.get(decision, "app_decline_title")))
        self.applicant_id = applicant_id
        self.decision = decision
        self.reviewer = reviewer
        self.guild = guild
        self.thread_id = thread_id
        self.note = discord.ui.TextInput(
            label=t("modals", "app_decision_label"),
            placeholder=t("modals", "app_decision_placeholder"),
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        colors = {"accept": discord.Color.green(), "decline": discord.Color.red(), "question": discord.Color.blurple()}
        emojis = {"accept": "✅", "decline": "❌", "question": "❓"}
        color  = colors[self.decision]

        # Respond immediately to avoid 10062
        success_key = "application_accepted" if self.decision == "accept" else (
            "application_declined" if self.decision == "decline" else "application_questioned"
        )
        await interaction.response.send_message(
            t("success", success_key, mention="<@" + str(self.applicant_id) + ">"),
            ephemeral=True
        )

        # Fetch the application thread
        thread = None
        if self.thread_id:
            try:
                thread = self.guild.get_channel(self.thread_id) or await self.guild.fetch_channel(self.thread_id)
            except Exception:
                pass

        applicant = self.guild.get_member(self.applicant_id)

        if self.decision == "question":
            # Add reviewer to the existing thread and post question embed
            if thread:
                try:
                    await thread.add_user(self.reviewer)
                except Exception:
                    pass
                q_embed = discord.Embed(
                    title=t("embeds", "application", "dm_question_title"),
                    description=t("embeds", "application", "question_thread_desc",
                                  mention="<@" + str(self.applicant_id) + ">",
                                  reviewer=self.reviewer.mention),
                    color=discord.Color.blurple(),
                    timestamp=now_timestamp()
                )
                q_embed.add_field(
                    name=t("embeds", "application", "review_note"),
                    value=self.note.value,
                    inline=False
                )
                if self.guild.icon:
                    q_embed.set_footer(
                        text=self.guild.name + " • " + t("embeds", "application", "footer"),
                        icon_url=self.guild.icon.url
                    )
                await thread.send(
                    content="<@" + str(self.applicant_id) + ">",
                    embed=q_embed
                )
                # Also DM the applicant so they don't miss it
                if applicant:
                    dm_q_embed = make_dm_embed(
                        title=t("embeds", "application", "dm_question_title"),
                        description=t("embeds", "application", "dm_question_desc"),
                        color=discord.Color.blurple(),
                        guild=self.guild,
                        fields=[
                            (t("embeds", "application", "review_reviewer"), self.reviewer.mention, True),
                            (t("embeds", "application", "review_note"),     self.note.value,       False),
                        ],
                        footer_system=t("embeds", "application", "footer")
                    )
                    await send_dm(applicant, embed=dm_q_embed)
        else:
            # Accept / Decline: DM the applicant
            if applicant:
                dm_keys = {
                    "accept":  ("dm_accepted_title", "dm_accepted_desc"),
                    "decline": ("dm_declined_title", "dm_declined_desc"),
                }
                title_key, desc_key = dm_keys[self.decision]
                dm_embed = make_dm_embed(
                    title=t("embeds", "application", title_key),
                    description=t("embeds", "application", desc_key),
                    color=color,
                    guild=self.guild,
                    fields=[
                        (t("embeds", "application", "review_reviewer"), self.reviewer.mention, True),
                        (t("embeds", "application", "review_note"),     self.note.value,       False),
                    ],
                    footer_system=t("embeds", "application", "footer")
                )
                await send_dm(applicant, embed=dm_embed)

            # Post status embed in thread, disable buttons, lock + archive
            if thread:
                status_embed = discord.Embed(
                    title=emojis[self.decision] + "  " + t("embeds", "application", "status_handled"),
                    description=(
                        t("embeds", "application", "review_reviewer") + " " + self.reviewer.mention
                        + "\n" + t("embeds", "application", "review_note") + "\n" + self.note.value
                    ),
                    color=color,
                    timestamp=now_timestamp()
                )
                done_view = discord.ui.View()
                btn_label = (t("buttons", "app_" + self.decision) + "  (" + self.reviewer.display_name + ")")[:80]
                done_btn = discord.ui.Button(label=btn_label, style=discord.ButtonStyle.secondary, disabled=True)
                done_view.add_item(done_btn)
                try:
                    await thread.send(embed=status_embed)
                    await interaction.message.edit(view=done_view)
                    await thread.edit(locked=True, archived=True)
                except Exception:
                    pass


class ApplicationModal(discord.ui.Modal):
    def __init__(self, user_id, guild_id, step, steps, review_channel_id, panel_title, questions):
        total = len(steps)
        super().__init__(title=(panel_title[:40] + " (" + str(step + 1) + "/" + str(total) + ")"))
        self.user_id = user_id
        self.guild_id = guild_id
        self.step = step
        self.steps = steps
        self.review_channel_id = review_channel_id
        self.panel_title = panel_title
        self.questions = questions
        self.inputs = []
        self.input_labels = []
        for q in steps[step]:
            label_str = q["label"][:45]
            ti = discord.ui.TextInput(
                label=label_str,
                placeholder=q.get("placeholder", "")[:100],
                style=discord.TextStyle.paragraph if q.get("style") == "paragraph" else discord.TextStyle.short,
                required=q.get("required", True),
                max_length=1024
            )
            self.add_item(ti)
            self.inputs.append(ti)
            self.input_labels.append(label_str)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in pending_applications:
            pending_applications[uid] = {"answers": [], "guild_id": self.guild_id}
        # Validate min_length for each answer
        validation_errors = []
        for i, ti in enumerate(self.inputs):
            val = ti.value or ""
            step_questions = self.steps[self.step]
            if i < len(step_questions):
                min_len = step_questions[i].get("min_length", 0)
                if min_len and len(val.strip()) < min_len:
                    validation_errors.append(
                        t("errors", "app_answer_too_short",
                          label=self.input_labels[i], min=min_len, got=len(val.strip()))
                    )
        if validation_errors:
            return await interaction.response.send_message(
                "\n".join(validation_errors), ephemeral=True
            )

        for i, ti in enumerate(self.inputs):
            pending_applications[uid]["answers"].append((self.input_labels[i], ti.value))

        next_step = self.step + 1
        if next_step < len(self.steps):
            view = ApplicationContinueView(
                user_id=uid, guild_id=self.guild_id,
                step=next_step, steps=self.steps,
                review_channel_id=self.review_channel_id,
                panel_title=self.panel_title, questions=self.questions
            )
            done = next_step
            total = len(self.steps)
            bar = "█" * done + "░" * (total - done)
            await interaction.response.send_message(
                t("success", "application_step_done", current=done, total=total, bar=bar),
                view=view, ephemeral=True
            )
        else:
            await self._submit_application(interaction)  # response happens inside

    async def _submit_application(self, interaction: discord.Interaction):
        uid = self.user_id
        data = pending_applications.pop(uid, {"answers": [], "guild_id": self.guild_id})
        guild = interaction.guild
        applicant = interaction.user

        # Respond immediately — Discord 3s window
        await interaction.response.send_message(t("success", "application_submitted"), ephemeral=True)

        review_channel = guild.get_channel(self.review_channel_id)
        if not review_channel:
            return

        # Load reviewer role IDs from panel config
        config = load_config()
        guild_id = str(guild.id)
        panels = config.get(guild_id, {}).get("application_panels", [])
        reviewer_role_ids = []
        for p in panels:
            if p.get("review_channel_id") == self.review_channel_id:
                reviewer_role_ids = p.get("reviewer_role_ids", [])
                break

        # Create private thread in review_channel for this application
        thread_name = (self.panel_title[:20] + " — " + applicant.display_name[:20])
        try:
            thread = await review_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                reason="Application: " + applicant.display_name
            )
        except Exception:
            try:
                thread = await review_channel.create_thread(
                    name=thread_name,
                    type=discord.ChannelType.public_thread
                )
            except Exception:
                return

        # Add applicant to thread
        try:
            await thread.add_user(applicant)
        except Exception:
            pass

        # Add all members with reviewer roles to thread
        for rid in reviewer_role_ids:
            role = guild.get_role(rid)
            if role:
                for member in guild.members:
                    if member.bot:
                        continue
                    if role in member.roles:
                        try:
                            await thread.add_user(member)
                        except Exception:
                            pass

        # Build and send review embeds into thread
        embeds = build_review_embeds(
            guild=guild, applicant=applicant,
            answers=data["answers"],
            panel_title=self.panel_title, questions=self.questions
        )
        try:
            rv = ApplicationReviewView(
                applicant_id=applicant.id,
                thread_id=thread.id,
                review_channel_id=self.review_channel_id
            )
            for i, e in enumerate(embeds):
                if i == len(embeds) - 1:
                    await thread.send(embed=e, view=rv)
                else:
                    await thread.send(embed=e)
        except discord.Forbidden:
            pass

        # DM confirmation
        dm_embed = make_dm_embed(
            title=t("embeds", "application", "dm_title"),
            description=t("embeds", "application", "dm_desc"),
            color=discord.Color.green(),
            guild=guild,
            footer_system=t("embeds", "application", "footer")
        )
        await send_dm(applicant, embed=dm_embed)


class ApplicationContinueView(discord.ui.View):
    def __init__(self, user_id, guild_id, step, steps, review_channel_id, panel_title, questions):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id
        self.step = step
        self.steps = steps
        self.review_channel_id = review_channel_id
        self.panel_title = panel_title
        self.questions = questions
        self.continue_btn.label = t("buttons", "app_continue")
        self.cancel_btn.label   = t("buttons", "app_cancel")

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.blurple, emoji="📝")
    async def continue_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        modal = ApplicationModal(
            user_id=self.user_id, guild_id=self.guild_id,
            step=self.step, steps=self.steps,
            review_channel_id=self.review_channel_id,
            panel_title=self.panel_title, questions=self.questions
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        pending_applications.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), view=None)


class ApplicationPanelView(discord.ui.View):
    def __init__(self, panel_index: int):
        super().__init__(timeout=None)
        self.panel_index = panel_index
        self.apply_btn.label = t("buttons", "apply_now")

    @discord.ui.button(label="Apply Now", style=discord.ButtonStyle.green, emoji="📋", custom_id="application_panel_btn")
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild_id)
        config = load_config()
        panels = config.get(guild_id, {}).get("application_panels", [])
        panel = next((p for p in panels if p.get("message_id") == interaction.message.id), None)
        if not panel and panels:
            panel = panels[self.panel_index] if self.panel_index < len(panels) else panels[0]
        if not panel:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        if not panel.get("review_channel_id"):
            return await interaction.response.send_message(t("errors", "application_no_review_channel"), ephemeral=True)
        if interaction.user.id in pending_applications:
            return await interaction.response.send_message(t("errors", "application_already_open"), ephemeral=True)
        questions = panel.get("questions") or DEFAULT_APPLICATION_QUESTIONS
        steps = get_application_steps(questions)
        panel_title = panel.get("title", t("embeds", "application", "default_title"))
        modal = ApplicationModal(
            user_id=interaction.user.id, guild_id=interaction.guild_id,
            step=0, steps=steps,
            review_channel_id=panel["review_channel_id"],
            panel_title=panel_title, questions=questions
        )
        await interaction.response.send_modal(modal)



# ─────────────────────────────────────────────
#  SELFROLE SETUP WIZARD
# ─────────────────────────────────────────────

_selfrole_wizard_state: dict = {}


def _build_selfrole_embed(state: dict, guild) -> discord.Embed:
    BLUE = discord.Color.blue()
    embed = discord.Embed(title=t("embeds", "selfrole_wizard", "title"), color=BLUE)

    title_val  = state.get("title") or t("embeds", "wizard", "not_set")
    desc_val   = state.get("desc")  or t("embeds", "wizard", "not_set")
    color_val  = state.get("color_hex") or t("embeds", "selfrole_wizard", "color_default")

    embed.add_field(
        name=t("embeds", "selfrole_wizard", "f_info"),
        value=(
            t("embeds", "selfrole_wizard", "f_title")  + " " + title_val  + "\n" +
            t("embeds", "selfrole_wizard", "f_desc")   + " " + desc_val[:60] + "\n" +
            t("embeds", "selfrole_wizard", "f_color")  + " " + color_val
        ),
        inline=False
    )

    roles = state.get("roles", [])
    if roles:
        lines = []
        for i, r in enumerate(roles[:15]):
            emoji_str = (r.get("emoji") + " ") if r.get("emoji") else ""
            role_mention = "<@&" + str(r["role_id"]) + ">"
            desc_str = ("  —  " + r["description"][:30]) if r.get("description") else ""
            lines.append("**" + str(i + 1) + ".** " + emoji_str + r["label"] + "  " + role_mention + desc_str)
        if len(roles) > 15:
            lines.append(t("embeds", "wizard", "q_more", n=len(roles) - 15))
        roles_val = "\n".join(lines)
    else:
        roles_val = t("embeds", "selfrole_wizard", "roles_empty")

    embed.add_field(
        name=t("embeds", "selfrole_wizard", "f_roles") + " (" + str(len(roles)) + ")",
        value=roles_val,
        inline=False
    )

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class SelfRoleSetupInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "selfrole_setup_info_title"))
        self.user_id = user_id
        state = _selfrole_wizard_state.get(user_id, {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "selfrole_setup_title_label"),
            placeholder=t("modals", "selfrole_setup_title_ph"),
            default=state.get("title", ""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "selfrole_setup_desc_label"),
            placeholder=t("modals", "selfrole_setup_desc_ph"),
            default=state.get("desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=500
        )
        self.f_color = discord.ui.TextInput(
            label=t("modals", "selfrole_setup_color_label"),
            placeholder=t("modals", "selfrole_setup_color_ph"),
            default=state.get("color_hex", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)
        self.add_item(self.f_color)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _selfrole_wizard_state:
            _selfrole_wizard_state[uid] = {"roles": []}
        _selfrole_wizard_state[uid].update({
            "title":     self.f_title.value.strip(),
            "desc":      self.f_desc.value.strip(),
            "color_hex": self.f_color.value.strip().lstrip("#"),
        })
        embed = _build_selfrole_embed(_selfrole_wizard_state[uid], interaction.guild)
        view  = SelfRoleSetupMainView(uid)
        if interaction.message:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SelfRoleSetupAddRoleModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "selfrole_setup_role_title"))
        self.user_id = user_id
        self.f_role = discord.ui.TextInput(
            label=t("modals", "selfrole_setup_role_label"),
            placeholder=t("modals", "selfrole_setup_role_ph"),
            style=discord.TextStyle.short, required=True, max_length=30
        )
        self.f_name = discord.ui.TextInput(
            label=t("modals", "selfrole_setup_name_label"),
            placeholder=t("modals", "selfrole_setup_name_ph"),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_emoji = discord.ui.TextInput(
            label=t("modals", "selfrole_setup_emoji_label"),
            placeholder=t("modals", "selfrole_setup_emoji_ph"),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_description = discord.ui.TextInput(
            label=t("modals", "selfrole_setup_roledesc_label"),
            placeholder=t("modals", "selfrole_setup_roledesc_ph"),
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_role)
        self.add_item(self.f_name)
        self.add_item(self.f_emoji)
        self.add_item(self.f_description)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _selfrole_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        # Parse role ID
        raw = self.f_role.value.strip().lstrip("<@&").rstrip(">")
        role_id = None
        try:
            role_id = int(raw)
        except ValueError:
            id_match = re.search(r"\d+", raw)
            if id_match:
                role_id = int(id_match.group())
        if not role_id:
            return await interaction.response.send_message(t("errors", "selfrole_no_id", entry=self.f_role.value), ephemeral=True)
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message(t("errors", "selfrole_role_missing", entry=self.f_role.value, role_id=role_id), ephemeral=True)

        # Check duplicate
        existing = _selfrole_wizard_state[uid].get("roles", [])
        if any(r["role_id"] == role_id for r in existing):
            return await interaction.response.send_message(t("errors", "selfrole_duplicate"), ephemeral=True)

        # Parse label / emoji
        label = self.f_name.value.strip()[:100]
        emoji_raw = self.f_emoji.value.strip() or None
        emoji = None
        if emoji_raw:
            for char in emoji_raw:
                cp = ord(char)
                if cp > 0x27BF:
                    emoji = char
                    break
            if not emoji:
                emoji = emoji_raw[:10]

        _selfrole_wizard_state[uid].setdefault("roles", []).append({
            "label":       label,
            "role_id":     role_id,
            "emoji":       emoji,
            "description": self.f_description.value.strip()[:100] or None
        })

        embed = _build_selfrole_embed(_selfrole_wizard_state[uid], interaction.guild)
        view  = SelfRoleSetupMainView(uid)
        await interaction.response.edit_message(embed=embed, view=view)


class SelfRoleSetupMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.edit_info_btn.label  = t("buttons", "wizard_edit_info")
        self.add_role_btn.label   = t("buttons", "selfrole_wizard_add")
        self.remove_role_btn.label= t("buttons", "selfrole_wizard_remove")
        self.finish_btn.label     = t("buttons", "wizard_finish")
        self.cancel_btn.label     = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="✏️ Edit Info",    style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(SelfRoleSetupInfoModal(self.user_id))

    @discord.ui.button(label="➕ Add Role",     style=discord.ButtonStyle.blurple,   row=0)
    async def add_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _selfrole_wizard_state.get(self.user_id, {})
        if len(state.get("roles", [])) >= 25:
            return await interaction.response.send_message(t("errors", "selfrole_max_roles"), ephemeral=True)
        await interaction.response.send_modal(SelfRoleSetupAddRoleModal(self.user_id))

    @discord.ui.button(label="🗑️ Remove Last",  style=discord.ButtonStyle.danger,    row=1)
    async def remove_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _selfrole_wizard_state.get(self.user_id, {})
        if not state.get("roles"):
            return await interaction.response.send_message(t("errors", "selfrole_no_roles_to_remove"), ephemeral=True)
        removed = state["roles"].pop()
        embed = _build_selfrole_embed(state, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🚀 Finish",        style=discord.ButtonStyle.green,     row=1)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _selfrole_wizard_state.get(self.user_id)
        if not state or not state.get("title"):
            return await interaction.response.send_message(t("errors", "wizard_incomplete"), ephemeral=True)
        if not state.get("roles"):
            return await interaction.response.send_message(t("errors", "selfrole_no_roles_to_remove"), ephemeral=True)
        await self._finalize(interaction)

    @discord.ui.button(label="✖️ Cancel",        style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _selfrole_wizard_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), embed=None, view=None)

    async def _finalize(self, interaction: discord.Interaction):
        state = _selfrole_wizard_state.pop(self.user_id, None)
        if not state:
            return
        guild_id = str(interaction.guild_id)
        config = load_config()
        if guild_id not in config:
            config[guild_id] = {}

        color = discord.Color.blue()
        if state.get("color_hex"):
            try:
                color = discord.Color(int(state["color_hex"].lstrip("#"), 16))
            except ValueError:
                pass

        panel_id = str(interaction.id)
        roles    = state["roles"]

        embed = discord.Embed(
            title=state["title"],
            description=format_discord_text(state.get("desc", "")),
            color=color,
            timestamp=now_timestamp()
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(
            text=t("embeds", "selfrole", "panel_footer", name=interaction.guild.name, count=len(roles)),
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )

        view    = SelfRoleView(roles, panel_id)
        message = await interaction.channel.send(embed=embed, view=view)
        config[guild_id].setdefault("selfrole_panels", []).append({
            "message_id": message.id,
            "channel_id": interaction.channel_id,
            "panel_id":   panel_id,
            "title":      state["title"],
            "roles":      roles
        })
        save_config(config)

        done_embed = discord.Embed(
            title=t("embeds", "wizard", "done_title"),
            description=t("success", "selfrole_panel_created",
                          title=state["title"], count=len(roles), skipped=""),
            color=discord.Color.green(),
            timestamp=now_timestamp()
        )
        if interaction.guild.icon:
            done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=done_embed, view=None)


# ─────────────────────────────────────────────
#  TICKET SETUP WIZARD
# ─────────────────────────────────────────────

_ticket_wizard_state: dict = {}


def _build_ticket_embed(state: dict, guild) -> discord.Embed:
    GOLD = discord.Color.gold()
    embed = discord.Embed(title=t("embeds", "ticket_wizard", "title"), color=GOLD)

    title_val = state.get("title") or t("embeds", "wizard", "not_set")
    roles     = state.get("supporter_role_ids", [])
    roles_val = (" ".join("<@&" + str(r) + ">" for r in roles)
                 if roles else t("embeds", "wizard", "not_set"))

    # Embed styling values
    desc_val    = (state.get("embed_desc") or "")[:40] + ("..." if len(state.get("embed_desc") or "") > 40 else "")
    color_val   = ("#" + state["embed_color"]) if state.get("embed_color") else t("embeds", "ticket_wizard", "color_default")
    thumb_val   = t("embeds", "ticket_wizard", "thumb_on") if state.get("embed_thumbnail") else t("embeds", "ticket_wizard", "thumb_off")

    embed.add_field(
        name=t("embeds", "ticket_wizard", "f_info"),
        value=(
            t("embeds", "ticket_wizard", "f_title")  + " " + title_val  + "\n" +
            t("embeds", "ticket_wizard", "f_roles")  + " " + roles_val
        ),
        inline=False
    )

    embed.add_field(
        name=t("embeds", "ticket_wizard", "f_embed_style"),
        value=(
            t("embeds", "ticket_wizard", "f_desc")   + " " + (desc_val or t("embeds", "wizard", "not_set")) + "\n" +
            t("embeds", "ticket_wizard", "f_color")  + " " + color_val + "\n" +
            t("embeds", "ticket_wizard", "f_thumb")  + " " + thumb_val
        ),
        inline=False
    )

    cats = state.get("categories", [])
    if cats:
        lines = []
        for i, c in enumerate(cats[:10]):
            emoji_str = (c.get("emoji") + " ") if c.get("emoji") else ""
            desc_str  = ("  —  " + c["description"][:30]) if c.get("description") else ""
            lines.append("**" + str(i + 1) + ".** " + emoji_str + c["label"] + desc_str)
        if len(cats) > 10:
            lines.append(t("embeds", "wizard", "q_more", n=len(cats) - 10))
        cats_val = "\n".join(lines)
    else:
        cats_val = t("embeds", "ticket_wizard", "cats_empty")

    embed.add_field(
        name=t("embeds", "ticket_wizard", "f_cats") + " (" + str(len(cats)) + ")",
        value=cats_val,
        inline=False
    )

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class TicketSetupEmbedModal(discord.ui.Modal):
    """Edit the visual styling of the ticket panel embed."""
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "ticket_setup_embed_title"))
        self.user_id = user_id
        state = _ticket_wizard_state.get(user_id, {})
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_desc_label"),
            placeholder=t("modals", "ticket_setup_embed_desc_ph"),
            default=state.get("embed_desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.f_color = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_color_label"),
            placeholder=t("modals", "ticket_setup_embed_color_ph"),
            default=state.get("embed_color", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_thumbnail = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_thumb_label"),
            placeholder=t("modals", "ticket_setup_embed_thumb_ph"),
            default="yes" if state.get("embed_thumbnail", True) else "no",
            style=discord.TextStyle.short, required=False, max_length=5
        )
        self.add_item(self.f_desc)
        self.add_item(self.f_color)
        self.add_item(self.f_thumbnail)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _ticket_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        # Parse color
        color_raw = self.f_color.value.strip().lstrip("#")
        if color_raw:
            try:
                int(color_raw, 16)  # validate hex
            except ValueError:
                return await interaction.response.send_message(
                    t("errors", "ticket_invalid_color"), ephemeral=True
                )

        # Parse thumbnail toggle
        thumb_raw = self.f_thumbnail.value.strip().lower()
        thumbnail = thumb_raw not in ("no", "n", "false", "0", "nein")

        _ticket_wizard_state[uid].update({
            "embed_desc":      self.f_desc.value.strip(),
            "embed_color":     color_raw,
            "embed_thumbnail": thumbnail,
        })
        embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
        view  = TicketSetupMainView(uid)
        await interaction.response.edit_message(embed=embed, view=view)


class TicketSetupInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "ticket_setup_info_title"))
        self.user_id = user_id
        state = _ticket_wizard_state.get(user_id, {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "ticket_setup_title_label"),
            placeholder=t("modals", "ticket_setup_title_ph"),
            default=state.get("title", ""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_roles = discord.ui.TextInput(
            label=t("modals", "ticket_setup_roles_label"),
            placeholder=t("modals", "ticket_setup_roles_ph"),
            default=" ".join(str(r) for r in state.get("supporter_role_ids", [])),
            style=discord.TextStyle.short, required=True, max_length=200
        )
        self.add_item(self.f_title)
        self.add_item(self.f_roles)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _ticket_wizard_state:
            _ticket_wizard_state[uid] = {"categories": []}

        role_ids = [rid for rid in extract_role_ids(self.f_roles.value)
                    if interaction.guild.get_role(rid)]
        if not role_ids:
            return await interaction.response.send_message(t("errors", "no_valid_role"), ephemeral=True)

        _ticket_wizard_state[uid].update({
            "title":              self.f_title.value.strip(),
            "supporter_role_ids": role_ids,
        })
        # Ensure embed style keys exist with defaults
        _ticket_wizard_state[uid].setdefault("embed_desc", "")
        _ticket_wizard_state[uid].setdefault("embed_color", "")
        _ticket_wizard_state[uid].setdefault("embed_thumbnail", True)
        embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
        view  = TicketSetupMainView(uid)
        if interaction.message:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TicketSetupCategoryModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "ticket_setup_cat_title"))
        self.user_id = user_id
        self.f_label = discord.ui.TextInput(
            label=t("modals", "ticket_setup_cat_label"),
            placeholder=t("modals", "ticket_setup_cat_label_ph"),
            style=discord.TextStyle.short, required=True, max_length=100
        )
        self.f_emoji = discord.ui.TextInput(
            label=t("modals", "ticket_setup_cat_emoji"),
            placeholder=t("modals", "ticket_setup_cat_emoji_ph"),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "ticket_setup_cat_desc"),
            placeholder=t("modals", "ticket_setup_cat_desc_ph"),
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_label)
        self.add_item(self.f_emoji)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _ticket_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        label = self.f_label.value.strip()[:100]

        # Parse emoji
        emoji = None
        emoji_raw = self.f_emoji.value.strip()
        if emoji_raw:
            for char in emoji_raw:
                cp = ord(char)
                if cp > 0x27BF:
                    emoji = char
                    break
            if not emoji:
                emoji = emoji_raw[:10]

        _ticket_wizard_state[uid].setdefault("categories", []).append({
            "label":             label,
            "value":             label,
            "emoji":             emoji,
            "description":       self.f_desc.value.strip()[:100] or None,
            "supporter_role_ids": None
        })

        embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
        view  = TicketSetupMainView(uid)
        await interaction.response.edit_message(embed=embed, view=view)


class TicketSetupMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.edit_info_btn.label   = t("buttons", "wizard_edit_info")
        self.edit_embed_btn.label  = t("buttons", "ticket_wizard_edit_embed")
        self.add_cat_btn.label     = t("buttons", "ticket_wizard_add_cat")
        self.remove_cat_btn.label  = t("buttons", "ticket_wizard_remove_cat")
        self.preview_btn.label     = t("buttons", "wizard_preview")
        self.finish_btn.label      = t("buttons", "wizard_finish")
        self.cancel_btn.label      = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="✏️ Edit Info",      style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(TicketSetupInfoModal(self.user_id))

    @discord.ui.button(label="🎨 Edit Embed",     style=discord.ButtonStyle.secondary, row=0)
    async def edit_embed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(TicketSetupEmbedModal(self.user_id))

    @discord.ui.button(label="➕ Add Category",   style=discord.ButtonStyle.blurple,   row=0)
    async def add_cat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id, {})
        if len(state.get("categories", [])) >= 25:
            return await interaction.response.send_message(t("errors", "ticket_max_cats"), ephemeral=True)
        await interaction.response.send_modal(TicketSetupCategoryModal(self.user_id))

    @discord.ui.button(label="🗑️ Remove Last",    style=discord.ButtonStyle.danger,    row=1)
    async def remove_cat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id, {})
        if not state.get("categories"):
            return await interaction.response.send_message(t("errors", "ticket_no_cats"), ephemeral=True)
        state["categories"].pop()
        embed = _build_ticket_embed(state, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="👁️ Preview",         style=discord.ButtonStyle.secondary, row=1)
    async def preview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        # Build the actual panel embed as it will appear in the channel
        title = state.get("title") or t("embeds", "ticket_panel", "title")
        desc  = state.get("embed_desc") or t("embeds", "ticket_panel", "desc")
        color_hex = state.get("embed_color")
        try:
            color = discord.Color(int(color_hex, 16)) if color_hex else discord.Color.gold()
        except (ValueError, TypeError):
            color = discord.Color.gold()

        preview = discord.Embed(title=title, description=desc, color=color, timestamp=now_timestamp())
        if state.get("embed_thumbnail", True) and interaction.guild.icon:
            preview.set_thumbnail(url=interaction.guild.icon.url)
        preview.set_footer(text=t("embeds", "ticket_panel", "footer", name=interaction.guild.name))

        cats = state.get("categories", [])
        if cats:
            cat_lines = []
            for c in cats:
                emoji_str = (c.get("emoji") + " ") if c.get("emoji") else ""
                desc_str  = " — " + c["description"] if c.get("description") else ""
                cat_lines.append("• " + emoji_str + "**" + c["label"] + "**" + desc_str)
            preview.add_field(
                name=t("embeds", "ticket_wizard", "preview_cats_title"),
                value="\n".join(cat_lines),
                inline=False
            )

        await interaction.response.send_message(
            content=t("success", "wizard_preview_note"),
            embed=preview,
            ephemeral=True
        )

    @discord.ui.button(label="🚀 Finish",          style=discord.ButtonStyle.green,     row=2)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id)
        if not state or not state.get("title") or not state.get("supporter_role_ids"):
            return await interaction.response.send_message(t("errors", "wizard_incomplete"), ephemeral=True)
        if not state.get("categories"):
            return await interaction.response.send_message(t("errors", "ticket_no_cats"), ephemeral=True)
        await self._finalize(interaction)

    @discord.ui.button(label="✖️ Cancel",          style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _ticket_wizard_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), embed=None, view=None)

    async def _finalize(self, interaction: discord.Interaction):
        state = _ticket_wizard_state.pop(self.user_id, None)
        if not state:
            return
        guild_id = str(interaction.guild_id)
        config = load_config()
        if guild_id not in config:
            config[guild_id] = {}

        cats     = state["categories"]
        role_ids = state["supporter_role_ids"]
        title    = state.get("title", t("embeds", "ticket_panel", "title"))

        view = TicketView(cats, role_ids)
        desc      = state.get("embed_desc") or t("embeds", "ticket_panel", "desc")
        color_hex = state.get("embed_color")
        try:
            color = discord.Color(int(color_hex, 16)) if color_hex else discord.Color.gold()
        except (ValueError, TypeError):
            color = discord.Color.gold()
        embed = discord.Embed(title=title, description=desc, color=color)
        if state.get("embed_thumbnail", True) and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=t("embeds", "ticket_panel", "footer", name=interaction.guild.name))

        message = await interaction.channel.send(embed=embed, view=view)
        config[guild_id].setdefault("ticket_panels", []).append({
            "categories":        cats,
            "channel_id":        interaction.channel_id,
            "message_id":        message.id,
            "supporter_role_ids":role_ids,
            "created_at":        datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
            "title":             title
        })
        save_config(config)

        done_embed = discord.Embed(
            title=t("embeds", "wizard", "done_title"),
            description=t("success", "ticket_panel_created", id=message.id),
            color=discord.Color.green(),
            timestamp=now_timestamp()
        )
        if interaction.guild.icon:
            done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=done_embed, view=None)



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
        for guild_id_str2, data2 in config.items():
            if not isinstance(data2, dict):
                continue
            for idx2, _ap in enumerate(data2.get("application_panels", [])):
                self.add_view(ApplicationPanelView(panel_index=idx2))
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
                footer_text = f"{member.guild.name}"
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

@bot.tree.command(name="selfrole_create", description=td("selfrole_erstellen"))
@app_commands.default_permissions(administrator=True)
async def selfrole_erstellen(interaction: discord.Interaction):
    """Starts the interactive self-role panel setup wizard."""
    uid = interaction.user.id
    _selfrole_wizard_state[uid] = {"title": "", "desc": "", "color_hex": "", "roles": []}
    await interaction.response.send_modal(SelfRoleSetupInfoModal(uid))

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
async def setup_tickets(interaction: discord.Interaction):
    """Starts the interactive ticket panel setup wizard."""
    uid = interaction.user.id
    _ticket_wizard_state[uid] = {"title": "", "supporter_role_ids": [], "categories": []}
    await interaction.response.send_modal(TicketSetupInfoModal(uid))

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







# ─────────────────────────────────────────────
#  APPLICATION COMMANDS
# ─────────────────────────────────────────────

@bot.tree.command(name="setup_application", description=td("setup_application"))
@app_commands.default_permissions(administrator=True)
async def setup_application(interaction: discord.Interaction):
    """Starts the interactive application panel setup wizard."""
    await interaction.response.send_modal(AppSetupStep1Modal())


@bot.tree.command(name="application_custom", description=td("application_custom"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    review_kanal=tp("application_custom", "review_kanal"),
    titel=tp("application_custom", "titel"),
    fragen=tp("application_custom", "fragen"),
    beschreibung=tp("application_custom", "beschreibung"),
)
async def application_custom(
    interaction: discord.Interaction,
    review_kanal: discord.TextChannel,
    titel: str,
    fragen: str,
    beschreibung: str = None,
):
    """
    fragen format: "Label|placeholder|short/paragraph, Label2|..."
    """
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config:
        config[guild_id] = {}

    raw_questions = []
    errors = []
    for entry in [e.strip() for e in fragen.split(",") if e.strip()]:
        parts = [p.strip() for p in entry.split("|")]
        if not parts[0]:
            errors.append(entry)
            continue
        style = "paragraph"
        if len(parts) >= 3 and parts[2].lower() in ("short", "s"):
            style = "short"
        raw_questions.append({
            "label":       parts[0][:45],
            "placeholder": parts[1][:100] if len(parts) > 1 else "",
            "style":       style,
            "required":    True
        })

    if not raw_questions:
        return await interaction.response.send_message(t("errors", "no_categories"), ephemeral=True)

    panel_title = titel
    panel_desc  = format_discord_text(beschreibung) if beschreibung else t("embeds", "application", "default_desc")
    existing = config[guild_id].get("application_panels", [])
    panel_index = len(existing)

    embed = discord.Embed(title=panel_title, description=panel_desc, color=discord.Color.blurple(), timestamp=now_timestamp())
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=t("embeds", "application", "panel_footer", name=interaction.guild.name))

    view = ApplicationPanelView(panel_index=panel_index)
    message = await interaction.channel.send(embed=embed, view=view)
    config[guild_id].setdefault("application_panels", []).append({
        "message_id": message.id,
        "channel_id": interaction.channel_id,
        "review_channel_id": review_kanal.id,
        "title": panel_title,
        "questions": raw_questions
    })
    save_config(config)

    skipped = t("success", "skipped_entries", entries=", ".join(errors)) if errors else ""
    await interaction.response.send_message(
        t("success", "application_panel_created", id=message.id, channel=review_kanal.mention) + skipped,
        ephemeral=True
    )


@bot.tree.command(name="application_delete", description=td("application_delete"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(message_id=tp("application_delete", "message_id"))
async def application_delete(interaction: discord.Interaction, message_id: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    panels = config.get(guild_id, {}).get("application_panels", [])
    target = next((p for p in panels if str(p.get("message_id")) == message_id), None)
    if not target:
        return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
    panels.remove(target)
    save_config(config)
    try:
        channel = interaction.guild.get_channel(target["channel_id"]) or await interaction.guild.fetch_channel(target["channel_id"])
        msg = await channel.fetch_message(int(message_id))
        await msg.delete()
        await interaction.response.send_message(t("success", "application_panel_deleted"), ephemeral=True)
    except Exception:
        await interaction.response.send_message(t("errors", "panel_removed_only"), ephemeral=True)


@bot.tree.command(name="set_join_roles", description=td("set_join_roles"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(rollen=tp("set_join_roles", "rollen"))
async def set_join_roles(interaction: discord.Interaction, rollen: str):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config:
        config[guild_id] = {}

    role_ids = extract_role_ids(rollen)
    valid_roles = []
    invalid = []
    for rid in role_ids:
        role = interaction.guild.get_role(rid)
        if role:
            valid_roles.append(rid)
        else:
            invalid.append(str(rid))

    if not valid_roles:
        return await interaction.response.send_message(t("errors", "no_valid_role"), ephemeral=True)

    config[guild_id]["join_roles"] = valid_roles
    save_config(config)

    role_mentions = " ".join(interaction.guild.get_role(r).mention for r in valid_roles)
    skipped = (" — " + t("errors", "role_not_found") + ": " + ", ".join(invalid)) if invalid else ""
    await interaction.response.send_message(
        t("success", "join_roles_set", roles=role_mentions) + skipped, ephemeral=True
    )


@bot.tree.command(name="remove_join_roles", description=td("remove_join_roles"))
@app_commands.default_permissions(administrator=True)
async def remove_join_roles(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config or "join_roles" not in config[guild_id]:
        return await interaction.response.send_message(t("errors", "join_roles_none"), ephemeral=True)
    config[guild_id].pop("join_roles", None)
    save_config(config)
    await interaction.response.send_message(t("success", "join_roles_removed"), ephemeral=True)



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