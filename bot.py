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

# Ensure configs directory exists
os.makedirs('configs', exist_ok=True)


def _debug(msg: str):
    """Print debug message only when DEBUG=true in .env"""
    if DEBUG:
        print(f"[DEBUG] {msg}")


def _load_default_application(lang: str = None) -> list:
    """Load default application questions — language-aware.
    Tries configs/default_application_{lang}.json first, then falls back to default_application.json.
    """
    code = lang or _current_lang or "en"
    lang_file = os.path.join(CONFIGS_DIR, f"default_application_{code}.json")
    for path in [lang_file, DEFAULT_APP_FILE]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f).get('questions', [])
            except (json.JSONDecodeError, OSError):
                pass
    return []


try:
    from static_ffmpeg import run
    ffmpeg_exe, ffprobe_exe = run.get_or_fetch_platform_executables_else_raise()
    HAS_STATIC_FFMPEG = True
except ImportError:
    HAS_STATIC_FFMPEG = False

# --- SETUP DATEIEN ---
TOKEN        = os.getenv('DISCORD_TOKEN')
BOT_VERSION  = "2.0.0"           # local fallback — real value fetched from GitHub
BOT_AUTHOR   = "p1lzi"
BOT_GITHUB   = "https://github.com/p1lzi/Bexi_Bot"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/p1lzi/Bexi_Bot/main/version.txt"
_cached_version: str = BOT_VERSION
DEBUG        = os.getenv('DEBUG', 'false').lower() in ('1', 'true', 'yes')
DEFAULT_LANG = os.getenv('DEFAULT_LANG', 'en').lower().strip()
CONFIGS_DIR      = 'configs'
CONFIG_FILE      = os.path.join(CONFIGS_DIR, 'config.json')
WHITELIST_FILE   = os.path.join(CONFIGS_DIR, 'whitelist.json')
OPEN_APPS_FILE   = os.path.join(CONFIGS_DIR, 'open_applications.json')
DEFAULT_APP_FILE = os.path.join(CONFIGS_DIR, 'default_application.json')
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
        # Beim Start: ersten Server mit Spracheinstellung nehmen, sonst DEFAULT_LANG aus .env
        code = DEFAULT_LANG if DEFAULT_LANG in ("de", "en") else "en"
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

def load_open_apps() -> dict:
    """Loads open application data from JSON. Structure:
    { "thread_id": { "applicant_id": int, "thread_id": int, "review_channel_id": int } }
    """
    if os.path.exists(OPEN_APPS_FILE):
        try:
            with open(OPEN_APPS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_open_app(thread_id: int, applicant_id: int, review_channel_id: int):
    data = load_open_apps()
    data[str(thread_id)] = {
        "applicant_id":      applicant_id,
        "thread_id":         thread_id,
        "review_channel_id": review_channel_id
    }
    with open(OPEN_APPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def delete_open_app(thread_id: int):
    data = load_open_apps()
    data.pop(str(thread_id), None)
    with open(OPEN_APPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


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

class SelfRoleSelect(discord.ui.Select):
    """Dropdown mit allen Rollen — bereits vorhandene sind vorausgewaehlt."""
    def __init__(self, roles_data: list, panel_id: str, member_role_ids: set):
        self.roles_data      = roles_data
        self.panel_id        = panel_id
        self.member_role_ids = member_role_ids

        options = []
        for role_data in roles_data[:25]:
            has_role = role_data['role_id'] in member_role_ids
            label    = role_data['label'][:100]
            desc_raw = role_data.get('description') or ""
            display_label = ("checkmark " + label)[:100] if has_role else label
            display_label = ("✅ " + label)[:100] if has_role else label
            options.append(discord.SelectOption(
                label=display_label,
                value=str(role_data['role_id']),
                emoji=role_data.get('emoji') or None,
                description=desc_raw[:100] or None,
                default=has_role,
            ))

        super().__init__(
            placeholder=t("selects", "selfrole_pick_role"),
            min_values=0,
            max_values=len(options) if options else 1,
            options=options,
            custom_id="selfrole_select_" + panel_id
        )

    async def callback(self, interaction: discord.Interaction):
        member       = interaction.user
        selected_ids = {int(v) for v in self.values}
        current_ids  = self.member_role_ids

        added   = []
        removed = []
        errors  = []

        for role_data in self.roles_data:
            rid  = role_data['role_id']
            role = interaction.guild.get_role(rid)
            if not role:
                continue
            if rid in selected_ids and rid not in current_ids:
                try:
                    await member.add_roles(role)
                    added.append(role.name)
                except discord.Forbidden:
                    errors.append(role.name)
            elif rid not in selected_ids and rid in current_ids:
                try:
                    await member.remove_roles(role)
                    removed.append(role.name)
                except discord.Forbidden:
                    errors.append(role.name)

        # Neue Rollenmenge berechnen
        panel_role_ids = {r['role_id'] for r in self.roles_data}
        new_ids = (current_ids - panel_role_ids) | selected_ids

        # Feedback
        lines = []
        for name in added:
            lines.append("🟢 **" + name + "** hinzugefügt")
        for name in removed:
            lines.append("🔴 **" + name + "** entfernt")
        for name in errors:
            lines.append("❌ **" + name + "** — " + t("errors", "no_permission_give_role"))
        if not lines:
            lines.append("ℹ️ " + t("success", "selfrole_no_change"))

        color = discord.Color.green()  if added and not removed else                 discord.Color.red()    if removed and not added  else                 discord.Color.blurple()

        feedback = discord.Embed(description="\n".join(lines), color=color)

        new_view = SelfRoleView(
            roles_data=self.roles_data,
            panel_id=self.panel_id,
            member_role_ids=new_ids
        )
        await interaction.response.edit_message(view=new_view)
        await interaction.followup.send(embed=feedback, ephemeral=True)


class SelfRoleView(discord.ui.View):
    def __init__(self, roles_data: list, panel_id: str = "default",
                 member: discord.Member = None, member_role_ids: set = None):
        super().__init__(timeout=None)
        self.roles_data = roles_data
        self.panel_id   = panel_id
        if member_role_ids is None:
            member_role_ids = {r.id for r in member.roles} if member else set()
        if roles_data:
            self.add_item(SelfRoleSelect(roles_data, panel_id, member_role_ids))


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

        # Resolve human-readable label for this category value
        cat_label = selected_value
        for cat in self.categories_full_data:
            if cat.get("value") == selected_value:
                cat_label = cat.get("label", selected_value)
                break

        config[guild_id].setdefault("category_channels", {})
        cached_channel_id = config[guild_id]["category_channels"].get(selected_value)
        target_channel = None

        if cached_channel_id:
            target_channel = guild.get_channel(cached_channel_id)

        if not target_channel:
            # cat_label is the human-readable label — use directly for channel name
            clean_label  = cat_label.strip()
            channel_name = re.sub(r'[^a-z0-9\-]', '-',
                                  clean_label.lower().replace(' ', '-'))[:80].strip('-') + "-tickets"
            channel_name = re.sub(r'-+', '-', channel_name)  # collapse multiple dashes
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
                    topic="Tickets: " + clean_label
                )

                info_embed = discord.Embed(
                    title=t("embeds","ticket_channel","title", category=clean_label),
                    description=t("embeds","ticket_channel","desc", category=clean_label),
                    color=discord.Color.blurple()
                )
                if guild.icon:
                    info_embed.set_thumbnail(url=guild.icon.url)
                info_embed.set_footer(text=guild.name)
                await target_channel.send(embed=info_embed)

            config[guild_id]["category_channels"][selected_value] = target_channel.id

        save_config(config)

        clean_username  = interaction.user.display_name.replace(' ', '-').lower()
        clean_cat_short = cat_label.lower()[:5]
        thread_name = f"{clean_cat_short}-{formatted_id}-{clean_username}"

        thread = await target_channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.private_thread
        )

        await interaction.response.send_message(
            t("success","ticket_created_reply", id=formatted_id, category=cat_label,
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
            title=t("embeds","ticket_thread","title", id=formatted_id, category=cat_label),
            description=t("embeds","ticket_thread","desc", mention=interaction.user.mention),
            color=discord.Color.green(),
            timestamp=now_timestamp()
        )
        ticket_embed.add_field(name=t("embeds","ticket_thread","f_number"), value=f"`#{formatted_id}`", inline=True)
        ticket_embed.add_field(name=t("embeds","ticket_thread","f_category"), value=f"`{cat_label}`", inline=True)
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
        seen_values = set()
        for i, item in enumerate(categories_data):
            # Ensure value is unique — append index if collision
            base_val = (item.get('value') or item['label'])[:95]
            val = base_val
            if val in seen_values:
                val = (base_val[:90] + "_" + str(i))[:100]
            seen_values.add(val)
            options.append(discord.SelectOption(
                label=item['label'][:100],
                value=val,
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

DEFAULT_APPLICATION_QUESTIONS = _load_default_application()


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
        # Find matching question to get its section
        matched_q = next((q for q in questions if q["label"] == label), None)
        global_idx = questions.index(matched_q) if matched_q else i

        # Use custom section from question if set, else fall back to hardcoded sections
        sec_raw = matched_q.get("section") if matched_q else None
        if sec_raw:
            sec_name = sec_raw.get("name", "") if isinstance(sec_raw, dict) else str(sec_raw)
            sec_desc = sec_raw.get("desc", "") if isinstance(sec_raw, dict) else ""
            section  = sec_name or _section_for_index(global_idx)
        else:
            section  = _section_for_index(global_idx)
            sec_desc = ""

        # New embed when section changes or field limit reached
        if section != current_section or current_embed is None or field_count >= 5:
            sec_title = section if section != current_section else None
            new_emb = discord.Embed(title=sec_title, color=BLURPLE)
            # Add section description as embed description if available
            if sec_title and sec_desc:
                new_emb.description = "*" + sec_desc + "*"
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
            sec_raw = q.get("section")
            sec_name = sec_raw.get("name", "") if isinstance(sec_raw, dict) else (sec_raw or "")
            sec_desc = sec_raw.get("desc", "") if isinstance(sec_raw, dict) else ""
            if sec_name and sec_name != last_section:
                sec_header = "__**" + sec_name + "**__"
                if sec_desc:
                    sec_header += "  *" + sec_desc + "*"
                field_lines.append(sec_header)
                last_section = sec_name
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
        sec_name = current_section.get("name", "") if isinstance(current_section, dict) else str(current_section)
        sec_desc = current_section.get("desc", "") if isinstance(current_section, dict) else ""
        sec_display = "`" + sec_name + "`"
        if sec_desc:
            sec_display += "  —  " + sec_desc
        embed.add_field(
            name=t("embeds", "wizard", "f_current_section"),
            value=sec_display,
            inline=False
        )

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    else:
        embed.set_footer(text=guild.name if guild else "Bexi Bot")
    return embed


class AppSetupSectionModal(discord.ui.Modal):
    """Set the active section/category for subsequent questions."""
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "app_setup_section_title"))
        self.user_id = user_id
        state = _setup_wizard_state.get(user_id, {})
        cur = state.get("current_section") or {}
        self.f_name = discord.ui.TextInput(
            label=t("modals", "app_setup_section_label"),
            placeholder=t("modals", "app_setup_section_ph"),
            default=cur.get("name", "") if isinstance(cur, dict) else (cur or ""),
            style=discord.TextStyle.short, required=False, max_length=60
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "app_setup_section_desc_label"),
            placeholder=t("modals", "app_setup_section_desc_ph"),
            default=cur.get("desc", "") if isinstance(cur, dict) else "",
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_name)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _setup_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        name = self.f_name.value.strip()
        desc = self.f_desc.value.strip()
        # Store as dict so we keep both name and desc
        _setup_wizard_state[uid]["current_section"] = {"name": name, "desc": desc} if name else None
        embed = _build_wizard_embed(_setup_wizard_state[uid], interaction.guild)
        view  = AppSetupMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


class AppSetupMainView(discord.ui.View):
    """Main wizard hub — shown after step 1, always visible between actions."""
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        state = _setup_wizard_state.get(user_id, {})
        has_title   = bool(state.get("title"))
        has_channel = bool(state.get("review_channel_id"))

        self.edit_info_btn.label     = t("buttons", "wizard_edit_info")
        self.edit_info_btn.style     = discord.ButtonStyle.secondary if has_title else discord.ButtonStyle.danger
        self.pick_channel_btn.label  = t("buttons", "wizard_pick_channel")
        self.pick_channel_btn.style  = discord.ButtonStyle.secondary if has_channel else discord.ButtonStyle.danger
        self.pick_reviewer_btn.label = t("buttons", "wizard_pick_reviewer")
        self.add_q_btn.label         = t("buttons", "wizard_add_q")
        self.add_section_btn.label   = t("buttons", "wizard_add_section")
        self.default_q_btn.label     = t("buttons", "wizard_default_q")
        self.clear_q_btn.label       = t("buttons", "wizard_clear_q")
        self.remove_last_btn.label   = t("buttons", "wizard_remove_last")
        self.preview_btn.label       = t("buttons", "wizard_preview")
        self.finish_btn.label        = t("buttons", "wizard_finish")
        self.cancel_btn.label        = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def _refresh(self, interaction: discord.Interaction):
        """Re-render the wizard embed in place — rebuild view so button colors update."""
        state = _setup_wizard_state.get(self.user_id)
        if not state:
            return
        embed = _build_wizard_embed(state, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=AppSetupMainView(self.user_id))

    # ── Row 0 ──────────────────────────────────────────────────────────────────
    @discord.ui.button(label="✏️ Edit Info",     style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AppSetupEditInfoModal(self.user_id))

    @discord.ui.button(label="📢 Review Channel", style=discord.ButtonStyle.secondary, row=0)
    async def pick_channel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        view = _make_channel_select_view(
            self.user_id, "review_channel_id", _setup_wizard_state,
            t("selects", "wizard_pick_channel"),
            refresh_fn=lambda uid, guild: (_build_wizard_embed(_setup_wizard_state[uid], guild), AppSetupMainView(uid))
        )
        await interaction.response.send_message(
            content=t("success", "wizard_pick_channel_hint"), view=view, ephemeral=True
        )

    @discord.ui.button(label="👥 Reviewer Role",  style=discord.ButtonStyle.secondary, row=0)
    async def pick_reviewer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        view = _make_role_select_view(
            self.user_id, "reviewer_role_ids", _setup_wizard_state,
            t("selects", "wizard_pick_roles"), multi=True,
            refresh_fn=lambda uid, guild: (_build_wizard_embed(_setup_wizard_state[uid], guild), AppSetupMainView(uid))
        )
        await interaction.response.send_message(
            content=t("success", "wizard_pick_roles_hint"), view=view, ephemeral=True
        )

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
            sec_raw  = q.get("section")
            sec_name = sec_raw.get("name", "") if isinstance(sec_raw, dict) else (sec_raw or "")
            sec_desc = sec_raw.get("desc", "") if isinstance(sec_raw, dict) else ""
            if sec_name and sec_name != last_sec:
                sep_val  = "*" + sec_desc + "*" if sec_desc else "​"
                preview_embed.add_field(name="━━━  " + sec_name + "  ━━━", value=sep_val, inline=False)
                last_sec = sec_name
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
            content=t("success", "wizard_preview_note_application"),
            embed=preview_embed,
            ephemeral=True
        )

    @discord.ui.button(label="🚀 Finish & Create",  style=discord.ButtonStyle.green,   row=2)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _setup_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        if not state.get("title"):
            return await interaction.response.send_message(t("errors", "wizard_missing_title"), ephemeral=True)
        if not state.get("review_channel_id"):
            return await interaction.response.send_message(t("errors", "wizard_missing_channel"), ephemeral=True)
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
        self.add_item(self.f_title)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _setup_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        _setup_wizard_state[uid].update({
            "title": self.f_title.value,
            "desc":  self.f_desc.value or "",
        })
        embed = _build_wizard_embed(_setup_wizard_state[uid], interaction.guild)
        view  = AppSetupMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


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
            "section":     _setup_wizard_state[uid].get("current_section") or None
        })

        embed = _build_wizard_embed(_setup_wizard_state[uid], interaction.guild)
        view  = AppSetupMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


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
            # Add reviewer + applicant to thread (first time applicant gets access)
            if thread:
                try:
                    await thread.add_user(self.reviewer)
                except Exception:
                    pass
                if applicant:
                    try:
                        await thread.add_user(applicant)
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
                # DM the applicant with thread link so they don't miss it
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
                        jump_url=thread.jump_url,
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
                    delete_open_app(thread.id)
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
        # Safety guard — should never be empty if apply_btn validated correctly
        if not steps or step >= len(steps) or not steps[step]:
            raise ValueError(f"ApplicationModal: steps={steps!r} step={step!r} — no questions to display")
        for q in steps[step]:
            label_str = q["label"][:45]
            min_len   = max(0, min(int(q.get("min_length") or 0), 1023))
            ti = discord.ui.TextInput(
                label=label_str,
                placeholder=q.get("placeholder", "")[:100],
                style=discord.TextStyle.paragraph if q.get("style") == "paragraph" else discord.TextStyle.short,
                required=q.get("required", True),
                min_length=min_len if min_len > 0 else None,
                max_length=1024
            )
            self.add_item(ti)
            self.inputs.append(ti)
            self.input_labels.append(label_str)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in pending_applications:
            pending_applications[uid] = {"answers": [], "guild_id": self.guild_id}

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
        # Match by review_channel_id — collect from ALL matching panels (union)
        config = load_config()
        guild_id = str(guild.id)
        panels = config.get(guild_id, {}).get("application_panels", [])
        reviewer_role_ids_set = set()
        for p in panels:
            # review_channel_id may be stored as int or str — compare both
            stored = p.get("review_channel_id")
            if stored == self.review_channel_id or stored == str(self.review_channel_id):
                for rid in p.get("reviewer_role_ids") or []:
                    reviewer_role_ids_set.add(int(rid))
        reviewer_role_ids = list(reviewer_role_ids_set)

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

        # Add reviewer role members to the private thread.
        # Private threads require explicit add_user — channel permissions alone don't work.
        # The applicant is NOT added here; only when a team member sends a follow-up question.
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
            # Persist so buttons survive a bot restart
            save_open_app(thread.id, applicant.id, self.review_channel_id)
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
        # None = use defaults; [] or missing = try reload, then error
        questions = panel.get("questions")
        if questions is None:
            questions = DEFAULT_APPLICATION_QUESTIONS
        if not questions:
            questions = _load_default_application()
        if not questions:
            return await interaction.response.send_message(
                "\u274c Keine Fragen konfiguriert. Bitte `configs/default_application.json` "
                "pr\u00fcfen oder das Panel neu erstellen.",
                ephemeral=True
            )
        steps = get_application_steps(questions)
        if not steps:
            return await interaction.response.send_message(
                "\u274c Fehler: Fragen konnten nicht geladen werden. Bitte das Panel neu erstellen.",
                ephemeral=True
            )
        panel_title = panel.get("title", t("embeds", "application", "default_title"))
        modal = ApplicationModal(
            user_id=interaction.user.id, guild_id=interaction.guild_id,
            step=0, steps=steps,
            review_channel_id=panel["review_channel_id"],
            panel_title=panel_title, questions=questions
        )
        await interaction.response.send_modal(modal)


# ─────────────────────────────────────────────
#  SHARED WIZARD SELECT HELPERS
# ─────────────────────────────────────────────

class WizardRoleSelect(discord.ui.RoleSelect):
    """Generic role selector used across wizards."""
    def __init__(self, user_id: int, state_key: str, state_dict: dict,
                 placeholder: str, multi: bool = False, max_vals: int = 10,
                 refresh_fn=None):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=max_vals if multi else 1
        )
        self.user_id    = user_id
        self.state_key  = state_key
        self.state_dict = state_dict
        self.multi      = multi
        self.refresh_fn = refresh_fn

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors", "application_not_yours"), ephemeral=True
            )
        if self.state_dict.get(self.user_id) is None:
            return await interaction.response.send_message(
                t("errors", "panel_not_found"), ephemeral=True
            )
        if self.multi:
            self.state_dict[self.user_id][self.state_key] = [r.id for r in self.values]
        else:
            self.state_dict[self.user_id][self.state_key] = self.values[0].id
        await interaction.response.edit_message(
            content=t("success", "wizard_select_done"), view=None
        )
        if self.refresh_fn:
            _orig = _wizard_interactions.get(self.user_id)
            if _orig:
                try:
                    embed, view = self.refresh_fn(self.user_id, interaction.guild)
                    await _orig.edit_original_response(embed=embed, view=view)
                except Exception:
                    pass


class WizardChannelSelect(discord.ui.ChannelSelect):
    """Generic channel selector used across wizards."""
    def __init__(self, user_id: int, state_key: str, state_dict: dict,
                 placeholder: str, channel_types: list = None, refresh_fn=None):
        super().__init__(
            placeholder=placeholder,
            min_values=1, max_values=1,
            channel_types=channel_types or [discord.ChannelType.text]
        )
        self.user_id    = user_id
        self.state_key  = state_key
        self.state_dict = state_dict
        self.refresh_fn = refresh_fn

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors", "application_not_yours"), ephemeral=True
            )
        if self.state_dict.get(self.user_id) is None:
            return await interaction.response.send_message(
                t("errors", "panel_not_found"), ephemeral=True
            )
        self.state_dict[self.user_id][self.state_key] = self.values[0].id
        await interaction.response.edit_message(
            content=t("success", "wizard_select_done"), view=None
        )
        if self.refresh_fn:
            _orig = _wizard_interactions.get(self.user_id)
            if _orig:
                try:
                    embed, view = self.refresh_fn(self.user_id, interaction.guild)
                    await _orig.edit_original_response(embed=embed, view=view)
                except Exception:
                    pass


def _make_role_select_view(user_id: int, state_key: str, state_dict: dict,
                           placeholder: str, multi: bool = False,
                           refresh_fn=None) -> discord.ui.View:
    view = discord.ui.View(timeout=120)
    view.add_item(WizardRoleSelect(user_id, state_key, state_dict, placeholder,
                                   multi=multi, max_vals=10 if multi else 1,
                                   refresh_fn=refresh_fn))
    return view


def _make_channel_select_view(user_id: int, state_key: str, state_dict: dict,
                               placeholder: str, refresh_fn=None) -> discord.ui.View:
    view = discord.ui.View(timeout=120)
    view.add_item(WizardChannelSelect(user_id, state_key, state_dict, placeholder,
                                      refresh_fn=refresh_fn))
    return view

# ─────────────────────────────────────────────
#  SELFROLE SETUP WIZARD
# ─────────────────────────────────────────────

_selfrole_wizard_state: dict = {}


def _build_selfrole_embed(state: dict, guild) -> discord.Embed:
    color_hex = state.get("color_hex", "")
    try:
        color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.blue()
    except (ValueError, TypeError):
        color = discord.Color.blue()

    embed = discord.Embed(title=t("embeds", "selfrole_wizard", "title"), color=color)

    title_val = state.get("title") or t("embeds", "wizard", "not_set")
    desc_val  = (state.get("desc") or "")[:60] + ("..." if len(state.get("desc") or "") > 60 else "")
    color_val = ("#" + state["color_hex"]) if state.get("color_hex") else t("embeds", "selfrole_wizard", "color_default")

    embed.add_field(
        name=t("embeds", "selfrole_wizard", "f_info"),
        value=(
            t("embeds", "selfrole_wizard", "f_title") + " " + title_val + "\n" +
            t("embeds", "selfrole_wizard", "f_desc")  + " " + (desc_val or t("embeds", "wizard", "not_set")) + "\n" +
            t("embeds", "selfrole_wizard", "f_color") + " " + color_val
        ),
        inline=False
    )

    roles = state.get("roles", [])
    if roles:
        lines = []
        for i, r in enumerate(roles[:15]):
            emoji_str    = (r.get("emoji") + " ") if r.get("emoji") else ""
            role_mention = "<@&" + str(r["role_id"]) + ">"
            desc_str     = ("  —  " + r["description"][:30]) if r.get("description") else ""
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


async def _selfrole_refresh(interaction: discord.Interaction, uid: int, view=None):
    """Helper: edit wizard message with updated embed."""
    embed = _build_selfrole_embed(_selfrole_wizard_state[uid], interaction.guild)
    v = view or SelfRoleSetupMainView(uid)
    _orig = _wizard_interactions.get(uid)
    if _orig:
        try:
            await _orig.edit_original_response(embed=embed, view=v)
        except Exception:
            pass


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
        _selfrole_wizard_state.setdefault(uid, {"roles": []}).update({
            "title":     self.f_title.value.strip(),
            "desc":      self.f_desc.value.strip(),
            "color_hex": self.f_color.value.strip().lstrip("#"),
        })
        await interaction.response.defer(ephemeral=True)
        await _selfrole_refresh(interaction, uid)


class SelfRoleSetupRoleDetailsModal(discord.ui.Modal):
    """After role is selected via dropdown: set label, emoji, description."""
    def __init__(self, user_id: int, role_id: int, role_name: str):
        super().__init__(title=t("modals", "selfrole_setup_role_title"))
        self.user_id = user_id
        self.role_id = role_id
        self.f_name = discord.ui.TextInput(
            label=t("modals", "selfrole_setup_name_label"),
            placeholder=t("modals", "selfrole_setup_name_ph"),
            default=role_name[:80],
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
        self.add_item(self.f_name)
        self.add_item(self.f_emoji)
        self.add_item(self.f_description)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _selfrole_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        # Check duplicate
        if any(r["role_id"] == self.role_id for r in _selfrole_wizard_state[uid].get("roles", [])):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send_message(t("errors", "selfrole_duplicate"), ephemeral=True)
            return

        # Parse emoji
        emoji = None
        emoji_raw = self.f_emoji.value.strip()
        if emoji_raw:
            for char in emoji_raw:
                if ord(char) > 0x27BF:
                    emoji = char
                    break
            if not emoji:
                emoji = emoji_raw[:10]

        _selfrole_wizard_state[uid].setdefault("roles", []).append({
            "label":       self.f_name.value.strip()[:100],
            "role_id":     self.role_id,
            "emoji":       emoji,
            "description": self.f_description.value.strip()[:100] or None
        })

        await interaction.response.defer(ephemeral=True)
        await _selfrole_refresh(interaction, uid)


class SelfRoleAddRoleSelect(discord.ui.RoleSelect):
    """Dropdown to pick a role to add."""
    def __init__(self, user_id: int):
        super().__init__(
            placeholder=t("selects", "selfrole_pick_role"),
            min_values=1, max_values=1
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        uid = self.user_id
        if interaction.user.id != uid:
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        role = self.values[0]
        state = _selfrole_wizard_state.get(uid, {})
        if len(state.get("roles", [])) >= 25:
            return await interaction.response.send_message(t("errors", "selfrole_max_roles"), ephemeral=True)
        # Open details modal for label/emoji/desc
        await interaction.response.send_modal(
            SelfRoleSetupRoleDetailsModal(uid, role.id, role.name)
        )


class SelfRoleRemoveRoleSelect(discord.ui.Select):
    """Dropdown to pick a role to remove."""
    def __init__(self, user_id: int, roles: list):
        options = [
            discord.SelectOption(
                label=r["label"][:100],
                value=str(r["role_id"]),
                emoji=r.get("emoji"),
                description=r.get("description", "")[:100] if r.get("description") else None
            )
            for r in roles[:25]
        ]
        super().__init__(
            placeholder=t("selects", "selfrole_remove_role"),
            min_values=1, max_values=1,
            options=options
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        uid = self.user_id
        if interaction.user.id != uid:
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        role_id = int(self.values[0])
        state = _selfrole_wizard_state.get(uid, {})
        state["roles"] = [r for r in state.get("roles", []) if r["role_id"] != role_id]
        # Close the dropdown message
        await interaction.response.edit_message(content=t("success", "wizard_select_done"), view=None)
        # Update the main wizard embed
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                await _orig.edit_original_response(
                    embed=_build_selfrole_embed(state, interaction.guild),
                    view=SelfRoleSetupMainView(uid)
                )
            except Exception:
                pass


class SelfRoleAddRoleView(discord.ui.View):
    """Ephemeral view with role dropdown."""
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.add_item(SelfRoleAddRoleSelect(user_id))


class SelfRoleRemoveRoleView(discord.ui.View):
    """Ephemeral view with remove role dropdown."""
    def __init__(self, user_id: int, roles: list):
        super().__init__(timeout=120)
        self.add_item(SelfRoleRemoveRoleSelect(user_id, roles))


class SelfRoleSetupMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        state = _selfrole_wizard_state.get(user_id, {})
        has_title = bool(state.get("title"))
        has_roles = bool(state.get("roles"))

        self.edit_info_btn.label   = t("buttons", "wizard_edit_info")
        self.edit_info_btn.style   = discord.ButtonStyle.secondary if has_title else discord.ButtonStyle.danger
        self.add_role_btn.label    = t("buttons", "selfrole_wizard_add")
        self.add_role_btn.style    = discord.ButtonStyle.blurple if has_roles else discord.ButtonStyle.danger
        self.remove_role_btn.label = t("buttons", "selfrole_wizard_remove")
        self.finish_btn.label      = t("buttons", "wizard_finish")
        self.cancel_btn.label      = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="✏️ Edit Info",    style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(SelfRoleSetupInfoModal(self.user_id))

    @discord.ui.button(label="➕ Add Role",     style=discord.ButtonStyle.blurple, row=0)
    async def add_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _selfrole_wizard_state.get(self.user_id, {})
        if len(state.get("roles", [])) >= 25:
            return await interaction.response.send_message(t("errors", "selfrole_max_roles"), ephemeral=True)
        # Show role picker dropdown in a separate ephemeral message
        await interaction.response.send_message(
            content=t("success", "selfrole_pick_role_hint"),
            view=SelfRoleAddRoleView(self.user_id),
            ephemeral=True
        )

    @discord.ui.button(label="🗑️ Remove Role",  style=discord.ButtonStyle.danger, row=0)
    async def remove_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _selfrole_wizard_state.get(self.user_id, {})
        roles = state.get("roles", [])
        if not roles:
            return await interaction.response.send_message(t("errors", "selfrole_no_roles_to_remove"), ephemeral=True)
        await interaction.response.send_message(
            content=t("success", "selfrole_remove_role_hint"),
            view=SelfRoleRemoveRoleView(self.user_id, roles),
            ephemeral=True
        )

    @discord.ui.button(label="🚀 Finish",        style=discord.ButtonStyle.green, row=1)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _selfrole_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        if not state.get("title"):
            return await interaction.response.send_message(t("errors", "wizard_missing_selfrole_title"), ephemeral=True)
        if not state.get("roles"):
            return await interaction.response.send_message(t("errors", "wizard_missing_selfroles"), ephemeral=True)
        await self._finalize(interaction)

    @discord.ui.button(label="✖️ Cancel",        style=discord.ButtonStyle.secondary, row=1)
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

        color_hex = state.get("color_hex", "")
        try:
            color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.blue()
        except (ValueError, TypeError):
            color = discord.Color.blue()

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
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


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
        self.add_item(self.f_title)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        _ticket_wizard_state.setdefault(uid, {"categories": []}).update({
            "title": self.f_title.value.strip(),
        })
        embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
        view  = TicketSetupMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


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

        # value must be unique per panel — use label + short uuid suffix (hidden from users)
        import uuid as _uuid
        unique_val = (label[:85] + "_" + _uuid.uuid4().hex[:6])[:100]
        _ticket_wizard_state[uid].setdefault("categories", []).append({
            "label":             label,
            "value":             unique_val,
            "emoji":             emoji,
            "description":       self.f_desc.value.strip()[:100] or None,
            "supporter_role_ids": None
        })

        embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
        view  = TicketSetupMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


class TicketSetupMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        state = _ticket_wizard_state.get(user_id, {})
        has_title = bool(state.get("title"))
        has_roles = bool(state.get("supporter_role_ids"))
        has_cats  = bool(state.get("categories"))

        self.edit_info_btn.label   = t("buttons", "wizard_edit_info")
        self.edit_info_btn.style   = discord.ButtonStyle.secondary if has_title else discord.ButtonStyle.danger
        self.pick_roles_btn.label  = t("buttons", "wizard_pick_roles")
        self.pick_roles_btn.style  = discord.ButtonStyle.secondary if has_roles else discord.ButtonStyle.danger
        self.edit_embed_btn.label  = t("buttons", "ticket_wizard_edit_embed")
        self.add_cat_btn.label     = t("buttons", "ticket_wizard_add_cat")
        self.add_cat_btn.style     = discord.ButtonStyle.blurple if has_cats else discord.ButtonStyle.danger
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

    @discord.ui.button(label="👥", style=discord.ButtonStyle.secondary, row=0)
    async def pick_roles_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        view = _make_role_select_view(
            self.user_id, "supporter_role_ids", _ticket_wizard_state,
            t("selects", "wizard_pick_roles"), multi=True,
            refresh_fn=lambda uid, guild: (_build_ticket_embed(_ticket_wizard_state[uid], guild), TicketSetupMainView(uid))
        )
        await interaction.response.send_message(
            content=t("success", "wizard_pick_roles_hint"), view=view, ephemeral=True
        )

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
        await interaction.response.edit_message(embed=embed, view=TicketSetupMainView(self.user_id))

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
            content=t("success", "wizard_preview_note_ticket"),
            embed=preview,
            ephemeral=True
        )

    @discord.ui.button(label="🚀 Finish",          style=discord.ButtonStyle.green,     row=2)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        if not state.get("title"):
            return await interaction.response.send_message(t("errors", "wizard_missing_title"), ephemeral=True)
        if not state.get("supporter_role_ids"):
            return await interaction.response.send_message(t("errors", "wizard_missing_roles"), ephemeral=True)
        if not state.get("categories"):
            return await interaction.response.send_message(t("errors", "wizard_missing_categories"), ephemeral=True)
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
#  STATUS CONFIG WIZARD
# ─────────────────────────────────────────────

_status_wizard_state: dict = {}
_wizard_messages: dict = {}  # user_id -> wizard message id
_wizard_interactions: dict = {}  # user_id -> original command interaction (for ephemeral edits)

STATUS_OPTIONS  = ["online", "idle", "dnd", "invisible"]
ACTIVITY_OPTIONS = ["playing", "streaming", "listening", "watching"]


def _build_status_embed(state: dict) -> discord.Embed:
    BLUE = discord.Color.blurple()
    embed = discord.Embed(title=t("embeds", "status_wizard", "title"), color=BLUE)

    status_val   = state.get("status")   or t("embeds", "wizard", "not_set")
    activity_val = state.get("activity") or t("embeds", "wizard", "not_set")
    text_val     = state.get("text")     or t("embeds", "wizard", "not_set")
    url_val      = state.get("stream_url") or t("embeds", "wizard", "not_set")

    status_emoji = {"online": "🟢", "idle": "🟡", "dnd": "🔴", "invisible": "⚫"}.get(status_val, "❓")
    activity_emoji = {"playing": "🎮", "streaming": "📡", "listening": "🎵", "watching": "👀"}.get(activity_val, "❓")

    lines = [
        t("embeds", "status_wizard", "f_status")   + " " + status_emoji + " `" + status_val + "`",
        t("embeds", "status_wizard", "f_activity") + " " + activity_emoji + " `" + activity_val + "`",
        t("embeds", "status_wizard", "f_text")     + " " + text_val,
    ]
    if state.get("activity") == "streaming":
        lines.append(t("embeds", "status_wizard", "f_url") + " " + url_val)
    embed.add_field(name=t("embeds", "status_wizard", "f_settings"), value="\n".join(lines), inline=False)
    return embed


class StatusTextModal(discord.ui.Modal):
    """Modal only for activity text + stream URL."""
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "status_wizard_title"))
        self.user_id = user_id
        state = _status_wizard_state.get(user_id, {})
        self.f_text = discord.ui.TextInput(
            label=t("modals", "status_wizard_text_label"),
            placeholder=t("modals", "status_wizard_text_ph"),
            default=state.get("text", ""),
            style=discord.TextStyle.short, required=True, max_length=128
        )
        self.f_url = discord.ui.TextInput(
            label=t("modals", "status_wizard_url_label"),
            placeholder=t("modals", "status_wizard_url_ph"),
            default=state.get("stream_url", ""),
            style=discord.TextStyle.short, required=False, max_length=200
        )
        self.add_item(self.f_text)
        self.add_item(self.f_url)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        _status_wizard_state.setdefault(uid, {}).update({
            "text":       self.f_text.value.strip(),
            "stream_url": self.f_url.value.strip() or "https://twitch.tv/discord",
        })
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                embed2 = _build_status_embed(_status_wizard_state[uid])
                view2  = StatusWizardView(uid)
                await _orig.edit_original_response(embed=embed2, view=view2)
            except Exception:
                pass


class StatusSelect(discord.ui.Select):
    """Dropdown for online status selection."""
    def __init__(self, user_id: int):
        options = [
            discord.SelectOption(label="🟢 Online",    value="online",    description=t("selects", "status_online_desc"),    default=_status_wizard_state.get(user_id, {}).get("status") == "online"),
            discord.SelectOption(label="🟡 Idle",      value="idle",      description=t("selects", "status_idle_desc"),      default=_status_wizard_state.get(user_id, {}).get("status") == "idle"),
            discord.SelectOption(label="🔴 Do Not Disturb", value="dnd",  description=t("selects", "status_dnd_desc"),       default=_status_wizard_state.get(user_id, {}).get("status") == "dnd"),
            discord.SelectOption(label="⚫ Invisible",  value="invisible", description=t("selects", "status_invisible_desc"), default=_status_wizard_state.get(user_id, {}).get("status") == "invisible"),
        ]
        super().__init__(placeholder=t("selects", "status_pick"), min_values=1, max_values=1, options=options)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _status_wizard_state.setdefault(self.user_id, {})["status"] = self.values[0]
        await interaction.response.edit_message(content=t("success", "wizard_select_done"), view=None)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(
                    embed=_build_status_embed(_status_wizard_state[self.user_id]),
                    view=StatusWizardView(self.user_id)
                )
            except Exception:
                pass


class ActivitySelect(discord.ui.Select):
    """Dropdown for activity type selection."""
    def __init__(self, user_id: int):
        options = [
            discord.SelectOption(label="🎮 Playing",   value="playing",   description=t("selects", "activity_playing_desc"),   default=_status_wizard_state.get(user_id, {}).get("activity") == "playing"),
            discord.SelectOption(label="📡 Streaming", value="streaming", description=t("selects", "activity_streaming_desc"), default=_status_wizard_state.get(user_id, {}).get("activity") == "streaming"),
            discord.SelectOption(label="🎵 Listening", value="listening", description=t("selects", "activity_listening_desc"), default=_status_wizard_state.get(user_id, {}).get("activity") == "listening"),
            discord.SelectOption(label="👀 Watching",  value="watching",  description=t("selects", "activity_watching_desc"),  default=_status_wizard_state.get(user_id, {}).get("activity") == "watching"),
        ]
        super().__init__(placeholder=t("selects", "activity_pick"), min_values=1, max_values=1, options=options)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _status_wizard_state.setdefault(self.user_id, {})["activity"] = self.values[0]
        await interaction.response.edit_message(content=t("success", "wizard_select_done"), view=None)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(
                    embed=_build_status_embed(_status_wizard_state[self.user_id]),
                    view=StatusWizardView(self.user_id)
                )
            except Exception:
                pass


class StatusWizardView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.status_btn.label   = t("buttons", "status_wizard_pick_status")
        self.activity_btn.label = t("buttons", "status_wizard_pick_activity")
        self.text_btn.label     = t("buttons", "status_wizard_edit_text")
        self.apply_btn.label    = t("buttons", "status_wizard_apply")
        self.cancel_btn.label   = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="🟢 Status",       style=discord.ButtonStyle.secondary, row=0)
    async def status_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(StatusSelect(self.user_id))
        await interaction.response.send_message(
            content=t("success", "status_wizard_pick_status_hint"), view=view, ephemeral=True
        )

    @discord.ui.button(label="🎮 Activity",     style=discord.ButtonStyle.secondary, row=0)
    async def activity_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(ActivitySelect(self.user_id))
        await interaction.response.send_message(
            content=t("success", "status_wizard_pick_activity_hint"), view=view, ephemeral=True
        )

    @discord.ui.button(label="✏️ Text / URL",   style=discord.ButtonStyle.blurple,   row=0)
    async def text_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(StatusTextModal(self.user_id))

    @discord.ui.button(label="✅ Apply", style=discord.ButtonStyle.green, row=0)
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _status_wizard_state.pop(self.user_id, None)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        discord_status = getattr(discord.Status, state["status"], discord.Status.online)
        activity = None
        act = state["activity"]
        text = state["text"]
        url  = state["stream_url"]
        if act == "playing":
            activity = discord.Game(name=text)
        elif act == "streaming":
            activity = discord.Streaming(name=text, url=url)
        elif act == "listening":
            activity = discord.Activity(type=discord.ActivityType.listening, name=text)
        elif act == "watching":
            activity = discord.Activity(type=discord.ActivityType.watching, name=text)

        await bot.change_presence(status=discord_status, activity=activity)
        config = load_config()
        config["bot_presence"] = {"status": state["status"], "type": act, "text": text, "url": url}
        save_config(config)

        done_embed = discord.Embed(
            title=t("embeds", "status_wizard", "done_title"),
            description=t("success", "status_updated"),
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=done_embed, view=None)
        await send_log(
            interaction.guild,
            t("embeds", "log_status", "title"),
            t("embeds", "log_status", "desc",
              status=state["status"], activity=act, text=text),
            discord.Color.blurple(),
            interaction.user,
            moderator=interaction.user,
        )

    @discord.ui.button(label="✖️ Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _status_wizard_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), embed=None, view=None)


# ─────────────────────────────────────────────
#  JOIN ROLES WIZARD
# ─────────────────────────────────────────────

_joinroles_wizard_state: dict = {}


def _build_joinroles_embed(state: dict, guild) -> discord.Embed:
    TEAL = discord.Color.teal()
    embed = discord.Embed(title=t("embeds", "joinroles_wizard", "title"), color=TEAL)
    roles = state.get("role_ids", [])
    if roles:
        roles_val = "\n".join(
            "**" + str(i + 1) + ".** <@&" + str(rid) + ">"
            for i, rid in enumerate(roles)
        )
    else:
        roles_val = t("embeds", "joinroles_wizard", "empty")
    embed.add_field(
        name=t("embeds", "joinroles_wizard", "f_roles") + " (" + str(len(roles)) + ")",
        value=roles_val,
        inline=False
    )
    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class JoinRolesAddModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "joinroles_add_title"))
        self.user_id = user_id
        self.f_roles = discord.ui.TextInput(
            label=t("modals", "joinroles_add_label"),
            placeholder=t("modals", "joinroles_add_ph"),
            style=discord.TextStyle.short, required=True, max_length=200
        )
        self.add_item(self.f_roles)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _joinroles_wizard_state:
            _joinroles_wizard_state[uid] = {"role_ids": []}
        role_ids = [rid for rid in extract_role_ids(self.f_roles.value)
                    if interaction.guild.get_role(rid)]
        if not role_ids:
            return await interaction.response.send_message(t("errors", "no_valid_role"), ephemeral=True)
        existing = _joinroles_wizard_state[uid]["role_ids"]
        added = 0
        for rid in role_ids:
            if rid not in existing:
                existing.append(rid)
                added += 1
        embed = _build_joinroles_embed(_joinroles_wizard_state[uid], interaction.guild)
        view  = JoinRolesWizardView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


class JoinRolesWizardView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        state = _joinroles_wizard_state.get(user_id, {})
        has_roles = bool(state.get("role_ids"))

        self.add_btn.label    = t("buttons", "joinroles_add")
        self.add_btn.style    = discord.ButtonStyle.blurple if has_roles else discord.ButtonStyle.danger
        self.remove_btn.label = t("buttons", "joinroles_remove")
        self.apply_btn.label  = t("buttons", "status_wizard_apply")
        self.cancel_btn.label = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="➕ Add Roles",    style=discord.ButtonStyle.blurple,   row=0)
    async def add_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        uid = self.user_id

        class _JoinRoleAddSelect(discord.ui.RoleSelect):
            def __init__(self_inner):
                super().__init__(placeholder=t("selects", "wizard_pick_roles"),
                                 min_values=1, max_values=10)
            async def callback(self_inner, itr: discord.Interaction):
                if itr.user.id != uid:
                    return await itr.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
                existing = _joinroles_wizard_state.get(uid, {}).get("role_ids", [])
                for r in self_inner.values:
                    if r.id not in existing:
                        existing.append(r.id)
                _joinroles_wizard_state.setdefault(uid, {})["role_ids"] = existing
                await itr.response.edit_message(content=t("success", "wizard_select_done"), view=None)

        v = discord.ui.View(timeout=120)
        v.add_item(_JoinRoleAddSelect())
        await interaction.response.send_message(
            content=t("success", "wizard_pick_roles_hint"), view=v, ephemeral=True
        )

    @discord.ui.button(label="🗑️ Remove Last",  style=discord.ButtonStyle.danger,    row=0)
    async def remove_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _joinroles_wizard_state.get(self.user_id, {})
        if not state.get("role_ids"):
            return await interaction.response.send_message(t("errors", "joinroles_none_to_remove"), ephemeral=True)
        state["role_ids"].pop()
        embed = _build_joinroles_embed(state, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=JoinRolesWizardView(self.user_id))

    @discord.ui.button(label="✅ Apply",         style=discord.ButtonStyle.green,     row=1)
    async def apply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _joinroles_wizard_state.pop(self.user_id, None)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        role_ids = state.get("role_ids", [])
        if not role_ids:
            return await interaction.response.send_message(t("errors", "wizard_missing_question_roles"), ephemeral=True)
        gid = str(interaction.guild_id)
        config = load_config()
        config.setdefault(gid, {})["join_roles"] = role_ids
        save_config(config)
        role_mentions = " ".join("<@&" + str(r) + ">" for r in role_ids)
        done_embed = discord.Embed(
            title=t("embeds", "joinroles_wizard", "done_title"),
            description=t("success", "join_roles_set", roles=role_mentions),
            color=discord.Color.green()
        )
        if interaction.guild.icon:
            done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=done_embed, view=None)

    @discord.ui.button(label="✖️ Cancel",        style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _joinroles_wizard_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), embed=None, view=None)


# ─────────────────────────────────────────────
#  VERIFY SETUP WIZARD
# ─────────────────────────────────────────────

_verify_wizard_state: dict = {}


def _build_verify_embed_preview(state: dict, guild) -> discord.Embed:
    """Builds the actual verify panel embed as it will appear."""
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
    """Builds the wizard status embed."""
    BLURPLE = discord.Color.blurple()
    embed = discord.Embed(title=t("embeds", "verify_wizard", "title"), color=BLURPLE)

    role_id   = state.get("role_id")
    role_val  = ("<@&" + str(role_id) + ">") if role_id else t("embeds", "wizard", "not_set")
    title_val = state.get("title") or t("embeds", "verify_panel", "default_title")
    desc_val  = (state.get("desc") or "")[:50] + ("..." if len(state.get("desc") or "") > 50 else "")
    color_val = ("#" + state["color_hex"]) if state.get("color_hex") else t("embeds", "verify_wizard", "color_default")
    thumb_val = t("embeds", "ticket_wizard", "thumb_on") if state.get("thumbnail", True) else t("embeds", "ticket_wizard", "thumb_off")

    embed.add_field(
        name=t("embeds", "verify_wizard", "f_settings"),
        value=(
            t("embeds", "verify_wizard", "f_role")  + " " + role_val  + "\n" +
            t("embeds", "verify_wizard", "f_title") + " " + title_val + "\n" +
            t("embeds", "verify_wizard", "f_desc")  + " " + (desc_val or t("embeds", "wizard", "not_set")) + "\n" +
            t("embeds", "verify_wizard", "f_color") + " " + color_val + "\n" +
            t("embeds", "verify_wizard", "f_thumb") + " " + thumb_val
        ),
        inline=False
    )
    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
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
        self.add_item(self.f_title)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        _verify_wizard_state.setdefault(uid, {"thumbnail": True}).update({
            "title": self.f_title.value.strip(),
            "desc":  self.f_desc.value.strip(),
        })
        embed = _build_verify_wizard_embed(_verify_wizard_state[uid], interaction.guild)
        view  = VerifyWizardMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


class VerifySetupEmbedModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "verify_setup_embed_title"))
        self.user_id = user_id
        state = _verify_wizard_state.get(user_id, {})
        self.f_color = discord.ui.TextInput(
            label=t("modals", "verify_setup_color_label"),
            placeholder=t("modals", "verify_setup_color_ph"),
            default=state.get("color_hex", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_thumb = discord.ui.TextInput(
            label=t("modals", "verify_setup_thumb_label"),
            placeholder=t("modals", "verify_setup_thumb_ph"),
            default="yes" if state.get("thumbnail", True) else "no",
            style=discord.TextStyle.short, required=False, max_length=5
        )
        self.add_item(self.f_color)
        self.add_item(self.f_thumb)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _verify_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        color_raw = self.f_color.value.strip().lstrip("#")
        if color_raw:
            try:
                int(color_raw, 16)
            except ValueError:
                return await interaction.response.send_message(t("errors", "ticket_invalid_color"), ephemeral=True)
        thumb_raw = self.f_thumb.value.strip().lower()
        thumbnail = thumb_raw not in ("no", "n", "false", "0", "nein")
        _verify_wizard_state[uid].update({"color_hex": color_raw, "thumbnail": thumbnail})
        embed = _build_verify_wizard_embed(_verify_wizard_state[uid], interaction.guild)
        view  = VerifyWizardMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass


class VerifyWizardMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        state = _verify_wizard_state.get(user_id, {})
        has_role  = bool(state.get("role_id"))
        has_title = bool(state.get("title"))

        self.edit_info_btn.label  = t("buttons", "wizard_edit_info")
        self.pick_role_btn.label  = t("buttons", "wizard_pick_verify_role")
        self.pick_role_btn.style  = discord.ButtonStyle.blurple if has_role else discord.ButtonStyle.danger
        self.edit_embed_btn.label = t("buttons", "ticket_wizard_edit_embed")
        self.preview_btn.label    = t("buttons", "wizard_preview")
        self.finish_btn.label     = t("buttons", "wizard_finish")
        self.cancel_btn.label     = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="✏️ Edit Info",   style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(VerifySetupInfoModal(self.user_id))

    @discord.ui.button(label="🎭 Verify Role",  style=discord.ButtonStyle.blurple,   row=0)
    async def pick_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        view = _make_role_select_view(
            self.user_id, "role_id", _verify_wizard_state,
            t("selects", "wizard_pick_verify_role"), multi=False,
            refresh_fn=lambda uid, guild: (_build_verify_wizard_embed(_verify_wizard_state[uid], guild), VerifyWizardMainView(uid))
        )
        await interaction.response.send_message(
            content=t("success", "wizard_pick_roles_hint"), view=view, ephemeral=True
        )

    @discord.ui.button(label="🎨 Edit Embed",  style=discord.ButtonStyle.secondary, row=0)
    async def edit_embed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(VerifySetupEmbedModal(self.user_id))

    @discord.ui.button(label="👁️ Preview",     style=discord.ButtonStyle.secondary, row=0)
    async def preview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _verify_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        preview = _build_verify_embed_preview(state, interaction.guild)
        await interaction.response.send_message(
            content=t("success", "wizard_preview_note_verify"), embed=preview, ephemeral=True
        )

    @discord.ui.button(label="🚀 Finish",       style=discord.ButtonStyle.green,    row=1)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _verify_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        if not state.get("role_id"):
            return await interaction.response.send_message(t("errors", "wizard_missing_verify_role"), ephemeral=True)
        state = _verify_wizard_state.pop(self.user_id, None)

        guild = interaction.guild
        panel_embed = _build_verify_embed_preview(state, guild)
        view = VerifyView(state["role_id"])
        msg  = await interaction.channel.send(embed=panel_embed, view=view)

        config = load_config()
        gid = str(interaction.guild_id)
        config.setdefault(gid, {}).setdefault("verify_panels", []).append({
            "role_id":    state["role_id"],
            "message_id": msg.id,
            "channel_id": interaction.channel_id,
            "title":      state.get("title") or t("embeds", "verify_panel", "default_title"),
        })
        save_config(config)

        done_embed = discord.Embed(
            title=t("embeds", "wizard", "done_title"),
            description=t("success", "verify_panel_created"),
            color=discord.Color.green()
        )
        if guild.icon:
            done_embed.set_footer(text=guild.name, icon_url=guild.icon.url)
        await interaction.response.edit_message(embed=done_embed, view=None)

    @discord.ui.button(label="✖️ Cancel",       style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _verify_wizard_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), embed=None, view=None)


# ─────────────────────────────────────────────
#  DELETE WIZARD
# ─────────────────────────────────────────────

async def _delete_panel(guild, config, guild_id: str, panel_type: str, panel: dict) -> bool:
    """Removes panel from config and deletes the Discord message. Returns True on full success."""
    panels = config.get(guild_id, {}).get(panel_type, [])
    if panel in panels:
        panels.remove(panel)
    save_config(config)
    msg_id = panel.get("message_id") or panel.get("msg_id")
    if not msg_id:
        return True  # nothing to delete from Discord
    try:
        ch_id = panel.get("channel_id")
        if ch_id:
            channel = guild.get_channel(int(ch_id)) or await guild.fetch_channel(int(ch_id))
            msg = await channel.fetch_message(int(msg_id))
            await msg.delete()
        else:
            # No channel_id stored — search all text channels
            for channel in guild.text_channels:
                try:
                    msg = await channel.fetch_message(int(msg_id))
                    await msg.delete()
                    break
                except Exception:
                    continue
        return True
    except Exception:
        return False


class DeleteTypeSelect(discord.ui.Select):
    """Step 1: choose what to delete."""
    def __init__(self, user_id: int, guild_id: str):
        self.user_id  = user_id
        self.guild_id = guild_id
        config = load_config()
        gdata  = config.get(guild_id, {})

        options = []
        if gdata.get("ticket_panels"):
            options.append(discord.SelectOption(
                label=t("selects", "delete_tickets"),
                value="ticket_panels", emoji="🎫",
                description=t("selects", "delete_tickets_desc",
                              n=len(gdata["ticket_panels"]))
            ))
        if gdata.get("selfrole_panels"):
            options.append(discord.SelectOption(
                label=t("selects", "delete_selfroles"),
                value="selfrole_panels", emoji="🎭",
                description=t("selects", "delete_selfroles_desc",
                              n=len(gdata["selfrole_panels"]))
            ))
        if gdata.get("application_panels"):
            options.append(discord.SelectOption(
                label=t("selects", "delete_applications"),
                value="application_panels", emoji="📋",
                description=t("selects", "delete_applications_desc",
                              n=len(gdata["application_panels"]))
            ))
        if gdata.get("verify_panels"):
            options.append(discord.SelectOption(
                label=t("selects", "delete_verify"),
                value="verify_panels", emoji="✅",
                description=t("selects", "delete_verify_desc",
                              n=len(gdata["verify_panels"]))
            ))
        if gdata.get("join_roles"):
            options.append(discord.SelectOption(
                label=t("selects", "delete_joinroles"),
                value="join_roles", emoji="👋",
                description=t("selects", "delete_joinroles_desc")
            ))

        if not options:
            options.append(discord.SelectOption(
                label=t("selects", "delete_nothing"),
                value="__none__"
            ))

        super().__init__(
            placeholder=t("selects", "delete_type_ph"),
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors", "application_not_yours"), ephemeral=True
            )
        panel_type = self.values[0]
        if panel_type == "__none__":
            return await interaction.response.edit_message(
                content=t("errors", "delete_nothing_found"), view=None
            )

        # Special case: join_roles has no panels, just delete directly
        if panel_type == "join_roles":
            config = load_config()
            config.get(self.guild_id, {}).pop("join_roles", None)
            save_config(config)
            return await interaction.response.edit_message(
                content=t("success", "join_roles_removed"), view=None
            )

        # Show panel picker for this type
        view = DeletePanelView(self.user_id, self.guild_id, panel_type)
        if not view.has_panels:
            return await interaction.response.edit_message(
                content=t("errors", "no_panels"), view=None
            )
        embed = _build_delete_embed(self.guild_id, panel_type, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=view)


def _build_delete_embed(guild_id: str, panel_type: str, guild) -> discord.Embed:
    config = load_config()
    panels = config.get(guild_id, {}).get(panel_type, [])
    type_labels = {
        "ticket_panels":      ("🎫", t("selects", "delete_tickets")),
        "selfrole_panels":    ("🎭", t("selects", "delete_selfroles")),
        "application_panels": ("📋", t("selects", "delete_applications")),
        "verify_panels":      ("✅", t("selects", "delete_verify")),
    }
    emoji, label = type_labels.get(panel_type, ("🗑️", panel_type))
    embed = discord.Embed(
        title=t("embeds", "delete_wizard", "title", emoji=emoji, label=label),
        description=t("embeds", "delete_wizard", "desc", count=len(panels)),
        color=discord.Color.red()
    )
    for i, p in enumerate(panels[:10]):
        title = p.get("title") or t("embeds", "delete_wizard", "untitled")
        msg_id = str(p.get("message_id") or p.get("msg_id") or "?")
        ch_id  = p.get("channel_id")
        ch_str = ("<#" + str(ch_id) + ">") if ch_id else "?"
        embed.add_field(
            name=f"**{i+1}.** {title}",
            value=f"ID: `{msg_id}`  •  {ch_str}",
            inline=False
        )
    if len(panels) > 10:
        embed.add_field(name="...", value=t("embeds", "wizard", "q_more", n=len(panels)-10), inline=False)
    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class DeletePanelSelect(discord.ui.Select):
    """Step 2: choose which panel to delete."""
    def __init__(self, user_id: int, guild_id: str, panel_type: str):
        self.user_id    = user_id
        self.guild_id   = guild_id
        self.panel_type = panel_type
        config  = load_config()
        panels  = config.get(guild_id, {}).get(panel_type, [])

        options = []
        for p in panels[:25]:
            title  = (p.get("title") or t("embeds", "delete_wizard", "untitled"))[:90]
            msg_id = str(p.get("message_id") or p.get("msg_id") or "?")
            options.append(discord.SelectOption(
                label=title,
                value=msg_id,
                description=f"ID: {msg_id}"
            ))

        super().__init__(
            placeholder=t("selects", "delete_panel_ph"),
            min_values=1, max_values=1,
            options=options if options else [discord.SelectOption(label="—", value="__empty__")]
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors", "application_not_yours"), ephemeral=True
            )
        msg_id = self.values[0]
        if msg_id == "__empty__":
            return await interaction.response.edit_message(content=t("errors", "no_panels"), view=None)

        config  = load_config()
        panels  = config.get(self.guild_id, {}).get(self.panel_type, [])
        target  = next(
            (p for p in panels if str(p.get("message_id") or p.get("msg_id")) == msg_id),
            None
        )
        if not target:
            return await interaction.response.edit_message(
                content=t("errors", "panel_not_found"), view=None
            )

        success = await _delete_panel(interaction.guild, config, self.guild_id, self.panel_type, target)
        msg = t("success", "panel_deleted_ok") if success else t("errors", "panel_removed_only")

        # Show back button in case user wants to delete more
        view = DeleteBackView(self.user_id, self.guild_id)
        await interaction.response.edit_message(content=msg, embed=None, view=view)


class DeletePanelView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: str, panel_type: str):
        super().__init__(timeout=120)
        select = DeletePanelSelect(user_id, guild_id, panel_type)
        self.has_panels = bool(select.options and select.options[0].value != "__empty__")
        self.add_item(select)
        # Back button
        back = discord.ui.Button(label=t("buttons", "delete_wizard_back"),
                                  style=discord.ButtonStyle.secondary, row=1)
        async def back_cb(itr: discord.Interaction):
            view2 = DeleteTypeView(user_id, guild_id)
            await itr.response.edit_message(
                content=t("success", "delete_wizard_back_hint"),
                embed=None, view=view2
            )
        back.callback = back_cb
        self.add_item(back)


class DeleteBackView(discord.ui.View):
    """After deletion: delete more or close."""
    def __init__(self, user_id: int, guild_id: str):
        super().__init__(timeout=120)
        more = discord.ui.Button(label=t("buttons", "delete_wizard_more"),
                                  style=discord.ButtonStyle.blurple)
        async def more_cb(itr: discord.Interaction):
            view2 = DeleteTypeView(user_id, guild_id)
            await itr.response.edit_message(
                content=t("success", "delete_wizard_back_hint"),
                view=view2
            )
        more.callback = more_cb
        self.add_item(more)

        done = discord.ui.Button(label=t("buttons", "wizard_cancel"),
                                  style=discord.ButtonStyle.secondary)
        async def done_cb(itr: discord.Interaction):
            await itr.response.edit_message(content=t("success", "delete_wizard_done"), view=None)
        done.callback = done_cb
        self.add_item(done)


class DeleteTypeView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: str):
        super().__init__(timeout=120)
        self.add_item(DeleteTypeSelect(user_id, guild_id))


# ─────────────────────────────────────────────
#  TICKET EDIT WIZARD
# ─────────────────────────────────────────────

_ticket_edit_state: dict = {}  # user_id -> {panel, guild_id, discord_message}


def _build_ticket_edit_embed(state: dict, guild) -> discord.Embed:
    panel = state.get("panel", {})
    GOLD  = discord.Color.gold()
    embed = discord.Embed(title=t("embeds", "ticket_wizard", "title") + " — Edit", color=GOLD)

    title_val  = panel.get("title")     or t("embeds", "wizard", "not_set")
    desc_val   = (panel.get("embed_desc") or "")[:60] + ("..." if len(panel.get("embed_desc") or "") > 60 else "")
    color_val  = ("#" + panel["embed_color"]) if panel.get("embed_color") else t("embeds", "ticket_wizard", "color_default")
    thumb_val  = t("embeds", "ticket_wizard", "thumb_on") if panel.get("embed_thumbnail", True) else t("embeds", "ticket_wizard", "thumb_off")
    roles      = panel.get("supporter_role_ids", [])
    roles_val  = " ".join("<@&" + str(r) + ">" for r in roles) if roles else t("embeds", "wizard", "not_set")

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
            t("embeds", "ticket_wizard", "f_desc")  + " " + (desc_val or t("embeds", "wizard", "not_set")) + "\n" +
            t("embeds", "ticket_wizard", "f_color") + " " + color_val + "\n" +
            t("embeds", "ticket_wizard", "f_thumb") + " " + thumb_val
        ),
        inline=False
    )

    cats = panel.get("categories", [])
    if cats:
        lines = []
        for i, c in enumerate(cats[:10]):
            emoji_str = (c.get("emoji") + " ") if c.get("emoji") else ""
            desc_str  = ("  —  " + c["description"][:30]) if c.get("description") else ""
            lines.append("**" + str(i+1) + ".** " + emoji_str + c["label"] + desc_str)
        if len(cats) > 10:
            lines.append(t("embeds", "wizard", "q_more", n=len(cats)-10))
        cats_val = "\n".join(lines)
    else:
        cats_val = t("embeds", "ticket_wizard", "cats_empty")

    embed.add_field(
        name=t("embeds", "ticket_wizard", "f_cats") + " (" + str(len(cats)) + ")",
        value=cats_val,
        inline=False
    )

    embed.add_field(
        name="🆔 Panel ID",
        value="`" + str(panel.get("message_id", "?")) + "`",
        inline=True
    )
    ch_id = panel.get("channel_id")
    embed.add_field(
        name="📢 Channel",
        value=("<#" + str(ch_id) + ">") if ch_id else "?",
        inline=True
    )

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class TicketEditPanelSelect(discord.ui.Select):
    """Select which ticket panel to edit."""
    def __init__(self, user_id: int, guild_id: str):
        self.user_id  = user_id
        self.guild_id = guild_id
        config = load_config()
        panels = config.get(guild_id, {}).get("ticket_panels", [])

        options = []
        for p in panels[:25]:
            title  = (p.get("title") or t("embeds", "delete_wizard", "untitled"))[:90]
            msg_id = str(p.get("message_id", "?"))
            ch_id  = p.get("channel_id")
            ch_str = (" • <#" + str(ch_id) + ">") if ch_id else ""
            options.append(discord.SelectOption(
                label=title,
                value=msg_id,
                description="ID: " + msg_id
            ))

        if not options:
            options.append(discord.SelectOption(label="—", value="__none__"))

        super().__init__(
            placeholder="🎫 Panel auswählen...",
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors", "application_not_yours"), ephemeral=True
            )
        msg_id = self.values[0]
        if msg_id == "__none__":
            return await interaction.response.edit_message(
                content=t("errors", "panel_not_found"), view=None
            )

        config = load_config()
        panels = config.get(self.guild_id, {}).get("ticket_panels", [])
        panel  = next((p for p in panels if str(p.get("message_id")) == msg_id), None)
        if not panel:
            return await interaction.response.edit_message(
                content=t("errors", "panel_not_found"), view=None
            )

        # Load embed_desc/color/thumbnail from Discord message if not in config
        if "embed_desc" not in panel or "embed_color" not in panel:
            try:
                ch = (interaction.guild.get_channel(panel["channel_id"])
                      or await interaction.guild.fetch_channel(panel["channel_id"]))
                msg = await ch.fetch_message(int(msg_id))
                if msg.embeds:
                    e = msg.embeds[0]
                    panel.setdefault("embed_desc",      e.description or "")
                    panel.setdefault("embed_color",     format(e.color.value, "06x") if e.color else "")
                    panel.setdefault("embed_thumbnail", bool(e.thumbnail))
            except Exception:
                panel.setdefault("embed_desc",      "")
                panel.setdefault("embed_color",     "")
                panel.setdefault("embed_thumbnail", True)

        uid = self.user_id
        _ticket_edit_state[uid] = {
            "panel":    panel,
            "guild_id": self.guild_id,
            "msg_id":   int(msg_id),
        }
        embed = _build_ticket_edit_embed(_ticket_edit_state[uid], interaction.guild)
        view  = TicketEditMainView(uid)
        await interaction.response.edit_message(embed=embed, view=view)
        # Store the select interaction — its edit_original_response edits this wizard msg
        _wizard_interactions[uid] = interaction


class TicketEditEmbedModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "ticket_setup_embed_title"))
        self.user_id = user_id
        panel = _ticket_edit_state.get(user_id, {}).get("panel", {})
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_desc_label"),
            placeholder=t("modals", "ticket_setup_embed_desc_ph"),
            default=panel.get("embed_desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.f_color = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_color_label"),
            placeholder=t("modals", "ticket_setup_embed_color_ph"),
            default=panel.get("embed_color", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_thumb = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_thumb_label"),
            placeholder=t("modals", "ticket_setup_embed_thumb_ph"),
            default="yes" if panel.get("embed_thumbnail", True) else "no",
            style=discord.TextStyle.short, required=False, max_length=5
        )
        self.f_title = discord.ui.TextInput(
            label=t("modals", "ticket_setup_title_label"),
            placeholder=t("modals", "ticket_setup_title_ph"),
            default=panel.get("title", ""),
            style=discord.TextStyle.short, required=False, max_length=80
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)
        self.add_item(self.f_color)
        self.add_item(self.f_thumb)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _ticket_edit_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        color_raw = self.f_color.value.strip().lstrip("#")
        if color_raw:
            try:
                int(color_raw, 16)
            except ValueError:
                return await interaction.response.send_message(t("errors", "ticket_invalid_color"), ephemeral=True)

        thumb_raw = self.f_thumb.value.strip().lower()
        thumbnail = thumb_raw not in ("no", "n", "false", "0", "nein")

        panel = _ticket_edit_state[uid]["panel"]
        if self.f_title.value.strip():
            panel["title"]      = self.f_title.value.strip()
        panel["embed_desc"]     = self.f_desc.value.strip()
        panel["embed_color"]    = color_raw
        panel["embed_thumbnail"]= thumbnail

        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                await _orig.edit_original_response(
                    embed=_build_ticket_edit_embed(_ticket_edit_state[uid], interaction.guild),
                    view=TicketEditMainView(uid)
                )
            except Exception:
                # Fallback: try editing via stored channel/message
                state = _ticket_edit_state.get(uid, {})
                ch_id  = state.get("_wiz_ch_id")
                msg_id = state.get("_wiz_msg_id")
                if ch_id and msg_id:
                    try:
                        ch  = interaction.guild.get_channel(ch_id) or await interaction.guild.fetch_channel(ch_id)
                        msg = await ch.fetch_message(msg_id)
                        await msg.edit(
                            embed=_build_ticket_edit_embed(_ticket_edit_state[uid], interaction.guild),
                            view=TicketEditMainView(uid)
                        )
                    except Exception:
                        pass


class TicketEditCategoryModal(discord.ui.Modal):
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
        if uid not in _ticket_edit_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        panel = _ticket_edit_state[uid]["panel"]
        if len(panel.get("categories", [])) >= 25:
            return await interaction.response.send_message(t("errors", "ticket_max_cats"), ephemeral=True)

        label = self.f_label.value.strip()[:100]
        emoji = None
        for char in (self.f_emoji.value or ""):
            if ord(char) > 0x27BF:
                emoji = char
                break
        if not emoji and self.f_emoji.value.strip():
            emoji = self.f_emoji.value.strip()[:10]

        import uuid as _uuid
        unique_val = (label[:85] + "_" + _uuid.uuid4().hex[:6])[:100]
        panel.setdefault("categories", []).append({
            "label":       label,
            "value":       unique_val,
            "emoji":       emoji,
            "description": self.f_desc.value.strip()[:100] or None,
        })

        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                await _orig.edit_original_response(
                    embed=_build_ticket_edit_embed(_ticket_edit_state[uid], interaction.guild),
                    view=TicketEditMainView(uid)
                )
            except Exception:
                state = _ticket_edit_state.get(uid, {})
                ch_id  = state.get("_wiz_ch_id")
                msg_id = state.get("_wiz_msg_id")
                if ch_id and msg_id:
                    try:
                        ch  = interaction.guild.get_channel(ch_id) or await interaction.guild.fetch_channel(ch_id)
                        msg = await ch.fetch_message(msg_id)
                        await msg.edit(
                            embed=_build_ticket_edit_embed(_ticket_edit_state[uid], interaction.guild),
                            view=TicketEditMainView(uid)
                        )
                    except Exception:
                        pass


class TicketEditRemoveCatSelect(discord.ui.Select):
    """Dropdown to pick a category to remove."""
    def __init__(self, user_id: int, categories: list):
        options = [
            discord.SelectOption(
                label=(c.get("emoji", "") + " " + c["label"])[:100],
                value=str(i),
                description=c.get("description", "")[:100] if c.get("description") else None
            )
            for i, c in enumerate(categories[:25])
        ]
        super().__init__(
            placeholder="🗑️ Kategorie entfernen...",
            min_values=1, max_values=1,
            options=options
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        uid = self.user_id
        if interaction.user.id != uid:
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        idx = int(self.values[0])
        panel = _ticket_edit_state[uid]["panel"]
        if 0 <= idx < len(panel.get("categories", [])):
            panel["categories"].pop(idx)
        await interaction.response.edit_message(content=t("success", "wizard_select_done"), view=None)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                await _orig.edit_original_response(
                    embed=_build_ticket_edit_embed(_ticket_edit_state[uid], interaction.guild),
                    view=TicketEditMainView(uid)
                )
            except Exception:
                pass


class TicketEditMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.edit_embed_btn.label  = t("buttons", "ticket_wizard_edit_embed")
        self.pick_roles_btn.label  = t("buttons", "wizard_pick_roles")
        self.add_cat_btn.label     = t("buttons", "ticket_wizard_add_cat")
        self.remove_cat_btn.label  = t("buttons", "ticket_wizard_remove_cat")
        self.save_btn.label        = t("buttons", "status_wizard_apply")
        self.cancel_btn.label      = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="🎨 Edit Embed",    style=discord.ButtonStyle.secondary, row=0)
    async def edit_embed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(TicketEditEmbedModal(self.user_id))

    @discord.ui.button(label="👥", style=discord.ButtonStyle.secondary, row=0)
    async def pick_roles_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        uid = self.user_id
        view = _make_role_select_view(
            uid, "supporter_role_ids",
            {uid: _ticket_edit_state[uid]["panel"]},
            t("selects", "wizard_pick_roles"), multi=True,
            refresh_fn=lambda u, g: (_build_ticket_edit_embed(_ticket_edit_state[u], g), TicketEditMainView(u))
        )
        await interaction.response.send_message(
            content=t("success", "wizard_pick_roles_hint"), view=view, ephemeral=True
        )

    @discord.ui.button(label="➕ Add Category",  style=discord.ButtonStyle.blurple,   row=0)
    async def add_cat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        panel = _ticket_edit_state.get(self.user_id, {}).get("panel", {})
        if len(panel.get("categories", [])) >= 25:
            return await interaction.response.send_message(t("errors", "ticket_max_cats"), ephemeral=True)
        await interaction.response.send_modal(TicketEditCategoryModal(self.user_id))

    @discord.ui.button(label="🗑️ Remove Category", style=discord.ButtonStyle.danger,  row=1)
    async def remove_cat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        panel = _ticket_edit_state.get(self.user_id, {}).get("panel", {})
        cats  = panel.get("categories", [])
        if not cats:
            return await interaction.response.send_message(t("errors", "ticket_no_cats"), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(TicketEditRemoveCatSelect(self.user_id, cats))
        await interaction.response.send_message(
            content="Wähle eine Kategorie zum Entfernen:", view=view, ephemeral=True
        )

    @discord.ui.button(label="✅ Save",           style=discord.ButtonStyle.green,    row=1)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_edit_state.pop(self.user_id, None)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

        panel    = state["panel"]
        guild_id = state["guild_id"]
        config   = load_config()
        panels   = config.get(guild_id, {}).get("ticket_panels", [])

        # Strip internal wizard keys before saving
        clean_panel = {k: v for k, v in panel.items() if not k.startswith("_wiz")}

        # Update panel in config
        updated = False
        for i, p in enumerate(panels):
            if str(p.get("message_id")) == str(clean_panel.get("message_id")):
                panels[i] = clean_panel
                updated = True
                break
        if not updated:
            panels.append(clean_panel)
        save_config(config)

        # Rebuild and update the Discord panel message
        error_msg = None
        try:
            ch_id  = clean_panel.get("channel_id")
            msg_id = clean_panel.get("message_id")
            if not ch_id or not msg_id:
                error_msg = "Kein channel_id oder message_id im Panel."
            else:
                ch  = (interaction.guild.get_channel(int(ch_id))
                       or await interaction.guild.fetch_channel(int(ch_id)))
                msg = await ch.fetch_message(int(msg_id))

                color_hex = clean_panel.get("embed_color") or ""
                try:
                    color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.gold()
                except (ValueError, TypeError):
                    color = discord.Color.gold()

                new_embed = discord.Embed(
                    title=clean_panel.get("title") or t("embeds", "ticket_panel", "title"),
                    description=clean_panel.get("embed_desc") or t("embeds", "ticket_panel", "desc"),
                    color=color
                )
                if clean_panel.get("embed_thumbnail", True) and interaction.guild.icon:
                    new_embed.set_thumbnail(url=interaction.guild.icon.url)
                new_embed.set_footer(
                    text=t("embeds", "ticket_panel", "footer", name=interaction.guild.name)
                )

                cats     = clean_panel.get("categories", [])
                role_ids = clean_panel.get("supporter_role_ids", [])
                new_view = TicketView(cats, role_ids)
                await msg.edit(embed=new_embed, view=new_view)

        except Exception as e:
            error_msg = str(e)
            _debug(f"ticket_edit save error: {e}")

        if error_msg:
            done_embed = discord.Embed(
                title="⚠️ Gespeichert (Discord-Update fehlgeschlagen)",
                description=f"Config wurde gespeichert, aber das Panel-Embed konnte nicht aktualisiert werden:\n```{error_msg}```",
                color=discord.Color.orange()
            )
        else:
            done_embed = discord.Embed(
                title="✅ " + t("success", "ticket_panel_updated"),
                color=discord.Color.green()
            )
        await interaction.response.edit_message(embed=done_embed, view=None)

    @discord.ui.button(label="✖️ Cancel",         style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _ticket_edit_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), embed=None, view=None)


# ─────────────────────────────────────────────
#  CONFIG IMPORT / EXPORT
# ─────────────────────────────────────────────

async def _recreate_panels(guild: discord.Guild, config: dict, guild_id: str):
    """Delete old panel messages and recreate all panels from config."""
    gdata  = config.get(guild_id, {})
    issues = []

    async def _del_msg(ch_id, msg_id):
        try:
            ch  = guild.get_channel(int(ch_id)) or await guild.fetch_channel(int(ch_id))
            msg = await ch.fetch_message(int(msg_id))
            await msg.delete()
        except Exception:
            pass

    # ── Ticket Panels ─────────────────────────────────────────────────────────
    for panel in gdata.get("ticket_panels", []):
        ch_id  = panel.get("channel_id")
        msg_id = panel.get("message_id")
        if ch_id and msg_id:
            await _del_msg(ch_id, msg_id)
        if not ch_id:
            issues.append("Ticket panel '" + str(panel.get("title")) + "': channel_id missing")
            continue
        try:
            ch = guild.get_channel(int(ch_id)) or await guild.fetch_channel(int(ch_id))
            color_hex = panel.get("embed_color") or ""
            try:
                color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.gold()
            except (ValueError, TypeError):
                color = discord.Color.gold()
            embed = discord.Embed(
                title=panel.get("title") or t("embeds", "ticket_panel", "title"),
                description=panel.get("embed_desc") or t("embeds", "ticket_panel", "desc"),
                color=color
            )
            if panel.get("embed_thumbnail", True) and guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            embed.set_footer(text=t("embeds", "ticket_panel", "footer", name=guild.name))
            cats     = panel.get("categories", [])
            role_ids = panel.get("supporter_role_ids", [])
            new_msg  = await ch.send(embed=embed, view=TicketView(cats, role_ids))
            panel["message_id"] = new_msg.id
        except Exception as e:
            issues.append("Ticket panel '" + str(panel.get("title")) + "': " + str(e))

    # ── Self-Role Panels ──────────────────────────────────────────────────────
    for panel in gdata.get("selfrole_panels", []):
        ch_id  = panel.get("channel_id")
        msg_id = panel.get("message_id")
        if ch_id and msg_id:
            await _del_msg(ch_id, msg_id)
        if not ch_id:
            issues.append("Self-role panel '" + str(panel.get("title")) + "': channel_id missing")
            continue
        try:
            ch = guild.get_channel(int(ch_id)) or await guild.fetch_channel(int(ch_id))
            color_hex = panel.get("color_hex", "")
            try:
                color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.blue()
            except (ValueError, TypeError):
                color = discord.Color.blue()
            roles    = panel.get("roles", [])
            panel_id = str(panel.get("panel_id") or panel.get("message_id") or "default")
            embed = discord.Embed(
                title=panel.get("title", ""),
                description=format_discord_text(panel.get("desc", "")),
                color=color,
                timestamp=now_timestamp()
            )
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
                embed.set_footer(text=t("embeds", "selfrole", "panel_footer",
                                        name=guild.name, count=len(roles)),
                                 icon_url=guild.icon.url)
            new_msg = await ch.send(embed=embed, view=SelfRoleView(roles, panel_id))
            panel["message_id"] = new_msg.id
            panel["panel_id"]   = str(new_msg.id)
        except Exception as e:
            issues.append("Self-role panel '" + str(panel.get("title")) + "': " + str(e))

    # ── Verify Panels ─────────────────────────────────────────────────────────
    for panel in gdata.get("verify_panels", []):
        ch_id  = panel.get("channel_id")
        msg_id = panel.get("message_id") or panel.get("msg_id")
        if ch_id and msg_id:
            await _del_msg(ch_id, msg_id)
        if not ch_id:
            issues.append("Verify panel: channel_id missing")
            continue
        try:
            ch      = guild.get_channel(int(ch_id)) or await guild.fetch_channel(int(ch_id))
            role_id = panel.get("role_id")
            role    = guild.get_role(int(role_id)) if role_id else None
            color_hex = panel.get("color_hex", "")
            try:
                color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.green()
            except (ValueError, TypeError):
                color = discord.Color.green()
            embed = discord.Embed(
                title=panel.get("title") or t("embeds", "verify_panel", "default_title"),
                description=panel.get("desc") or t("embeds", "verify_panel", "default_desc"),
                color=color
            )
            if panel.get("thumbnail", True) and guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            embed.set_footer(text=t("embeds", "verify_panel", "footer",
                                    role=role.name if role else str(role_id)))
            view    = VerifyView(int(role_id)) if role_id else discord.ui.View()
            new_msg = await ch.send(embed=embed, view=view)
            panel["message_id"] = new_msg.id
            panel["channel_id"] = ch.id
        except Exception as e:
            issues.append("Verify panel: " + str(e))

    # ── Application Panels ────────────────────────────────────────────────────
    for idx, panel in enumerate(gdata.get("application_panels", [])):
        ch_id  = panel.get("channel_id")
        msg_id = panel.get("message_id")
        if ch_id and msg_id:
            await _del_msg(ch_id, msg_id)
        if not ch_id:
            issues.append("Application panel '" + str(panel.get("title")) + "': channel_id missing")
            continue
        try:
            ch    = guild.get_channel(int(ch_id)) or await guild.fetch_channel(int(ch_id))
            embed = discord.Embed(
                title=panel.get("title") or t("embeds", "application", "default_title"),
                description=panel.get("desc") or t("embeds", "application", "default_desc"),
                color=discord.Color.blurple(),
                timestamp=now_timestamp()
            )
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            embed.set_footer(text=t("embeds", "application", "panel_footer", name=guild.name))
            new_msg = await ch.send(embed=embed, view=ApplicationPanelView(panel_index=idx))
            panel["message_id"] = new_msg.id
        except Exception as e:
            issues.append("Application panel '" + str(panel.get("title")) + "': " + str(e))

    save_config(config)
    return issues


class ConfigUploadView(discord.ui.View):
    """Confirmation view shown after uploading a new config."""
    def __init__(self, user_id: int, new_config: dict, guild_id: str, preview: str):
        super().__init__(timeout=120)
        self.user_id    = user_id
        self.new_config = new_config
        self.guild_id   = guild_id
        self.preview    = preview
        self.confirm_btn.label = t("buttons","config_import_apply")
        self.cancel_btn.label  = t("buttons","wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="✅", style=discord.ButtonStyle.green)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        # ── Snapshot BEFORE applying — used for rollback ──────────────────────
        # Deep copy so _recreate_panels cannot mutate the snapshot in-place
        import copy as _copy
        snapshot_config    = _copy.deepcopy(load_config())
        snapshot_open_apps = load_open_apps()

        config = _copy.deepcopy(snapshot_config)  # working copy
        # Merge: preserve bot_presence, open_applications, open_tickets
        for key, val in self.new_config.items():
            if key not in ("bot_presence", "open_applications", "open_tickets"):
                config[key] = val
        save_config(config)

        # Restore open_applications if present in the imported config
        imported_open_apps = self.new_config.get("open_applications", {})
        if imported_open_apps:
            existing_open_apps = load_open_apps()
            existing_open_apps.update(imported_open_apps)
            with open(OPEN_APPS_FILE, 'w', encoding='utf-8') as _f:
                json.dump(existing_open_apps, _f, indent=4)
            for entry in imported_open_apps.values():
                try:
                    bot.add_view(ApplicationReviewView(
                        applicant_id=entry["applicant_id"],
                        thread_id=entry["thread_id"],
                        review_channel_id=entry["review_channel_id"]
                    ))
                except Exception:
                    pass

        # Restore open tickets — re-add members to threads that still exist
        imported_open_tickets = self.new_config.get("open_tickets", {})
        tickets_restored = 0
        if imported_open_tickets:
            for entry in imported_open_tickets.values():
                try:
                    thread = (
                        interaction.guild.get_channel(entry["thread_id"])
                        or await interaction.guild.fetch_channel(entry["thread_id"])
                    )
                    if thread and not thread.archived and not thread.locked:
                        for member_id in entry.get("member_ids", []):
                            member = interaction.guild.get_member(member_id)
                            if member:
                                try:
                                    await thread.add_user(member)
                                except Exception:
                                    pass
                        bot.add_view(TicketControlView())
                        tickets_restored += 1
                except Exception:
                    pass

        # Re-register persistent views
        for gid_str, data in config.items():
            if not isinstance(data, dict):
                continue
            for panel in data.get("verify_panels", []):
                try: bot.add_view(VerifyView(panel["role_id"]))
                except Exception: pass
            for t_panel in data.get("ticket_panels", []):
                supp = t_panel.get("supporter_role_ids", [])
                try: bot.add_view(TicketView(t_panel.get("categories", []), supp))
                except Exception: pass
            for s_panel in data.get("selfrole_panels", []):
                try: bot.add_view(SelfRoleView(s_panel["roles"], str(s_panel.get("message_id", "default"))))
                except Exception: pass
            for idx2, _ap in enumerate(data.get("application_panels", [])):
                try: bot.add_view(ApplicationPanelView(panel_index=idx2))
                except Exception: pass

        issues = await _recreate_panels(interaction.guild, config, self.guild_id)

        # ── Collect new message IDs for rollback cleanup ──────────────────────
        config_after_import = load_config()
        gdata_after         = config_after_import.get(self.guild_id, {})
        imported_msg_ids    = []
        for panel_type in ("ticket_panels","selfrole_panels","application_panels","verify_panels"):
            for p in gdata_after.get(panel_type, []):
                ch_id  = p.get("channel_id")
                msg_id = p.get("message_id") or p.get("msg_id")
                if ch_id and msg_id:
                    imported_msg_ids.append((ch_id, msg_id))

        restored_apps    = len(imported_open_apps)
        result_lines = [
            t("success","config_import_done")
            + (" " + str(restored_apps) + " " + t("success","config_import_apps") if restored_apps else "")
            + (" " + str(tickets_restored) + " " + t("success","config_import_tickets") if tickets_restored else "")
        ]
        if issues:
            result_lines.append("")
            result_lines.append(t("success","config_import_errors", n=len(issues)))
            for iss in issues[:10]:
                result_lines.append("• " + iss)

        panel_count = (
            len(self.new_config.get(self.guild_id, {}).get("ticket_panels", [])) +
            len(self.new_config.get(self.guild_id, {}).get("selfrole_panels", [])) +
            len(self.new_config.get(self.guild_id, {}).get("application_panels", [])) +
            len(self.new_config.get(self.guild_id, {}).get("verify_panels", []))
        )
        log_action(str(interaction.guild_id), interaction.user, "config_import",
                   None, str(panel_count)+" panels, "+str(len(issues))+" errors")
        await send_log(
            interaction.guild,
            t("embeds", "log_config_import", "title"),
            t("embeds", "log_config_import", "desc",
              panels=panel_count, errors=len(issues)),
            discord.Color.orange() if issues else discord.Color.green(),
            interaction.user,
            moderator=interaction.user,
        )

        # ── Confirm to user (ephemeral) ───────────────────────────────────────
        await interaction.followup.send("\n".join(result_lines), ephemeral=True)

        # ── Post rollback button to log channel (visible to all admins) ───────
        config_after = load_config()
        log_ch_id = config_after.get(self.guild_id, {}).get("log_channel_id")
        if log_ch_id:
            log_ch = interaction.guild.get_channel(log_ch_id)
            if log_ch:
                rollback_embed = discord.Embed(
                    title=t("embeds","log_config_import","rollback_title"),
                    description=(
                        interaction.user.mention + " " + t("success","config_import_by") + "\n\n"
                        + t("success","config_rollback_hint")
                    ),
                    color=discord.Color.orange(),
                    timestamp=now_timestamp()
                )
                if interaction.guild.icon:
                    rollback_embed.set_footer(
                        text=interaction.guild.name + " • " + t("success","config_rollback_admin_only"),
                        icon_url=interaction.guild.icon.url
                    )
                rollback_view = ConfigRollbackView(
                    snapshot_config=snapshot_config,
                    snapshot_open_apps=snapshot_open_apps,
                    guild_id=self.guild_id,
                    imported_msg_ids=imported_msg_ids
                )
                await log_ch.send(embed=rollback_embed, view=rollback_view)

    @discord.ui.button(label="✖️", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.edit_message(content=t("errors","config_import_cancelled"), embed=None, view=None)


class ConfigRollbackView(discord.ui.View):
    """Posted in the log channel after an import — any admin can trigger rollback.
    Auto-disables after 24 hours."""
    def __init__(self, snapshot_config: dict, snapshot_open_apps: dict,
                 guild_id: str, imported_msg_ids: list = None):
        super().__init__(timeout=86400)   # 24 hours
        self.snapshot_config    = snapshot_config
        self.snapshot_open_apps = snapshot_open_apps
        self.guild_id           = guild_id
        self.imported_msg_ids   = imported_msg_ids or []
        self.rollback_btn.label = t("buttons", "config_rollback_btn_label")

    async def on_timeout(self):
        """Disable button when 24h window expires."""
        self.rollback_btn.disabled = True
        self.rollback_btn.label    = t("buttons", "config_rollback_expired")
        try:
            # message reference is not directly available, but Discord will
            # auto-remove the components when view expires via timeout=
            pass
        except Exception:
            pass

    @discord.ui.button(
        label="↩️",
        style=discord.ButtonStyle.danger,
        custom_id="config_rollback_btn"
    )
    async def rollback_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                t("errors","config_rollback_no_perm"), ephemeral=True
            )
        await interaction.response.defer()

        # ── Restore config ────────────────────────────────────────────────────
        save_config(self.snapshot_config)

        # ── Restore open_applications ─────────────────────────────────────────
        with open(OPEN_APPS_FILE, 'w', encoding='utf-8') as _f:
            json.dump(self.snapshot_open_apps, _f, indent=4)

        # ── Restore open tickets from snapshot ────────────────────────────────
        snapshot_open_tickets = self.snapshot_config.get("open_tickets", {})
        for entry in snapshot_open_tickets.values():
            try:
                thread = (
                    interaction.guild.get_channel(entry["thread_id"])
                    or await interaction.guild.fetch_channel(entry["thread_id"])
                )
                if thread and not thread.archived:
                    for mid in entry.get("member_ids", []):
                        member = interaction.guild.get_member(mid)
                        if member:
                            try:
                                await thread.add_user(member)
                            except Exception:
                                pass
            except Exception:
                pass

        # ── Re-register persistent views for restored config ──────────────────
        for gid_str, data in self.snapshot_config.items():
            if not isinstance(data, dict):
                continue
            for panel in data.get("verify_panels", []):
                try: bot.add_view(VerifyView(panel["role_id"]))
                except Exception: pass
            for t_panel in data.get("ticket_panels", []):
                supp = t_panel.get("supporter_role_ids", [])
                try: bot.add_view(TicketView(t_panel.get("categories", []), supp))
                except Exception: pass
            for s_panel in data.get("selfrole_panels", []):
                try: bot.add_view(SelfRoleView(s_panel["roles"], str(s_panel.get("message_id", "default"))))
                except Exception: pass
            for idx2, _ap in enumerate(data.get("application_panels", [])):
                try: bot.add_view(ApplicationPanelView(panel_index=idx2))
                except Exception: pass
        for entry in self.snapshot_open_apps.values():
            try:
                bot.add_view(ApplicationReviewView(
                    applicant_id=entry["applicant_id"],
                    thread_id=entry["thread_id"],
                    review_channel_id=entry["review_channel_id"]
                ))
            except Exception:
                pass

        # ── Delete panels that were created during the import ────────────────
        for ch_id, msg_id in self.imported_msg_ids:
            try:
                ch  = interaction.guild.get_channel(int(ch_id)) or await interaction.guild.fetch_channel(int(ch_id))
                msg = await ch.fetch_message(int(msg_id))
                await msg.delete()
            except Exception:
                pass

        # ── Recreate panels from snapshot ─────────────────────────────────────
        issues = await _recreate_panels(
            interaction.guild, self.snapshot_config, self.guild_id
        )

        # ── Log ───────────────────────────────────────────────────────────────
        log_action(str(interaction.guild_id), interaction.user, "config_rollback",
                   None, str(len(issues))+" errors")
        await send_log(
            interaction.guild,
            t("embeds", "log_config_rollback", "title"),
            t("embeds", "log_config_rollback", "desc", errors=len(issues)),
            discord.Color.red(),
            interaction.user,
            moderator=interaction.user,
        )

        # ── Disable button on log message so it can't be used twice ──────────
        button.disabled = True
        button.label    = t("buttons","config_rollback_done") + " " + interaction.user.display_name
        await interaction.message.edit(view=self)

        # ── Reply in log channel ──────────────────────────────────────────────
        done_embed = discord.Embed(
            title=t("embeds","log_config_rollback","title"),
            description=(
                interaction.user.mention + " " + t("success","config_rollback_by") + "\n"
                + (t("errors","config_rollback_errors", n=len(issues)) if issues
                   else t("success","config_rollback_ok"))
            ),
            color=discord.Color.red(),
            timestamp=now_timestamp()
        )
        if interaction.guild.icon:
            done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.followup.send(embed=done_embed)

# ─────────────────────────────────────────────
#  UNIFIED EDIT WIZARD
# ─────────────────────────────────────────────

_edit_state: dict = {}   # user_id -> {type, panel_idx, panel, guild_id}


# ── Generic helpers ───────────────────────────────────────────────────────────

def _get_panels(guild_id: str, panel_type: str) -> list:
    return load_config().get(guild_id, {}).get(panel_type, [])


def _save_panel(guild_id: str, panel_type: str, panel_idx: int, panel: dict):
    config = load_config()
    config.setdefault(guild_id, {}).setdefault(panel_type, [])
    config[guild_id][panel_type][panel_idx] = panel
    save_config(config)


# ── Type selector ─────────────────────────────────────────────────────────────

class EditTypeSelect(discord.ui.Select):
    def __init__(self, user_id: int, guild_id: str):
        self.user_id  = user_id
        self.guild_id = guild_id
        config = load_config()
        gdata  = config.get(guild_id, {})

        options = []
        if gdata.get("ticket_panels"):
            options.append(discord.SelectOption(
                label=t("selects", "edit_tickets"),
                value="ticket_panels", emoji="🎫",
                description=t("selects", "edit_panels_count", n=len(gdata["ticket_panels"]))
            ))
        if gdata.get("selfrole_panels"):
            options.append(discord.SelectOption(
                label=t("selects", "edit_selfroles"),
                value="selfrole_panels", emoji="🎭",
                description=t("selects", "edit_panels_count", n=len(gdata["selfrole_panels"]))
            ))
        if gdata.get("application_panels"):
            options.append(discord.SelectOption(
                label=t("selects", "edit_applications"),
                value="application_panels", emoji="📋",
                description=t("selects", "edit_panels_count", n=len(gdata["application_panels"]))
            ))
        if gdata.get("verify_panels"):
            options.append(discord.SelectOption(
                label=t("selects", "edit_verify"),
                value="verify_panels", emoji="✅",
                description=t("selects", "edit_panels_count", n=len(gdata["verify_panels"]))
            ))

        if not options:
            options.append(discord.SelectOption(label=t("selects", "delete_nothing"), value="__none__"))

        super().__init__(
            placeholder=t("selects", "edit_type_ph"),
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors", "application_not_yours"), ephemeral=True
            )
        panel_type = self.values[0]
        if panel_type == "__none__":
            return await interaction.response.edit_message(
                content=t("errors", "panel_not_found"), view=None
            )
        panels = _get_panels(self.guild_id, panel_type)
        if not panels:
            return await interaction.response.edit_message(
                content=t("errors", "panel_not_found"), view=None
            )
        if len(panels) == 1:
            # Skip panel picker, go straight to edit
            await _open_edit_view(
                interaction, self.user_id, self.guild_id,
                panel_type, 0, panels[0], edit_message=True
            )
        else:
            view = discord.ui.View(timeout=120)
            view.add_item(EditPanelSelect(self.user_id, self.guild_id, panel_type))
            await interaction.response.edit_message(
                content=t("success", "edit_pick_panel"),
                view=view
            )


class EditTypeView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: str):
        super().__init__(timeout=120)
        self.add_item(EditTypeSelect(user_id, guild_id))


# ── Panel selector ────────────────────────────────────────────────────────────

class EditPanelSelect(discord.ui.Select):
    def __init__(self, user_id: int, guild_id: str, panel_type: str):
        self.user_id    = user_id
        self.guild_id   = guild_id
        self.panel_type = panel_type
        panels = _get_panels(guild_id, panel_type)

        options = []
        for i, p in enumerate(panels[:25]):
            title  = (p.get("title") or t("embeds", "delete_wizard", "untitled"))[:90]
            msg_id = str(p.get("message_id") or "?")
            options.append(discord.SelectOption(
                label=title,
                value=str(i),
                description="ID: " + msg_id
            ))

        super().__init__(
            placeholder=t("selects", "delete_panel_ph"),
            min_values=1, max_values=1,
            options=options if options else [discord.SelectOption(label="—", value="0")]
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors", "application_not_yours"), ephemeral=True
            )
        idx    = int(self.values[0])
        panels = _get_panels(self.guild_id, self.panel_type)
        if idx >= len(panels):
            return await interaction.response.edit_message(
                content=t("errors", "panel_not_found"), view=None
            )
        await _open_edit_view(
            interaction, self.user_id, self.guild_id,
            self.panel_type, idx, panels[idx], edit_message=True
        )


async def _open_edit_view(interaction, user_id, guild_id, panel_type, panel_idx, panel, edit_message=False):
    """Open the correct edit view for a panel type."""
    _edit_state[user_id] = {
        "type":      panel_type,
        "panel_idx": panel_idx,
        "panel":     dict(panel),
        "guild_id":  guild_id,
    }
    _wizard_interactions[user_id] = interaction

    type_builders = {
        "ticket_panels":      (_build_edit_ticket_embed,      EditTicketView),
        "selfrole_panels":    (_build_edit_selfrole_embed,    EditSelfroleView),
        "application_panels": (_build_edit_application_embed, EditApplicationView),
        "verify_panels":      (_build_edit_verify_embed,      EditVerifyView),
    }
    build_fn, view_cls = type_builders[panel_type]
    embed = build_fn(user_id, interaction.guild)
    view  = view_cls(user_id)

    if edit_message:
        await interaction.response.edit_message(content=None, embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def _refresh_edit(interaction, user_id):
    state    = _edit_state.get(user_id, {})
    ptype    = state.get("type")
    type_builders = {
        "ticket_panels":      (_build_edit_ticket_embed,      EditTicketView),
        "selfrole_panels":    (_build_edit_selfrole_embed,    EditSelfroleView),
        "application_panels": (_build_edit_application_embed, EditApplicationView),
        "verify_panels":      (_build_edit_verify_embed,      EditVerifyView),
    }
    if ptype not in type_builders:
        return
    build_fn, view_cls = type_builders[ptype]
    embed = build_fn(user_id, interaction.guild)
    view  = view_cls(user_id)
    orig  = _wizard_interactions.get(user_id)
    if orig:
        try:
            await orig.edit_original_response(embed=embed, view=view)
        except Exception:
            pass


def _edit_check(interaction, user_id):
    if interaction.user.id != user_id:
        return False
    return True


# ── TICKET EDIT ───────────────────────────────────────────────────────────────

def _build_edit_ticket_embed(user_id: int, guild) -> discord.Embed:
    state = _edit_state.get(user_id, {})
    panel = state.get("panel", {})
    GOLD  = discord.Color.gold()
    embed = discord.Embed(title=t("embeds", "edit_ticket", "title"), color=GOLD)

    title_val   = panel.get("title") or t("embeds", "wizard", "not_set")
    roles       = panel.get("supporter_role_ids", [])
    roles_val   = " ".join("<@&" + str(r) + ">" for r in roles) if roles else t("embeds", "wizard", "not_set")
    color_val   = ("#" + panel["embed_color"]) if panel.get("embed_color") else "*Standard*"
    thumb_val   = "✅ An" if panel.get("embed_thumbnail", True) else "❌ Aus"
    desc_val    = (panel.get("embed_desc") or "")[:50] + ("..." if len(panel.get("embed_desc") or "") > 50 else "")

    embed.add_field(name=t("embeds", "edit_shared", "f_settings"), value=(
        "**Titel:** " + title_val + "\\n"
        "**Rollen:** " + roles_val + "\\n"
        "**Farbe:** " + color_val + "\\n"
        "**Thumbnail:** " + thumb_val + "\\n"
        "**Beschreibung:** " + (desc_val or "*leer*")
    ), inline=False)

    cats = panel.get("categories", [])
    if cats:
        lines = []
        for i, c in enumerate(cats[:15]):
            emoji_str = (c.get("emoji") + " ") if c.get("emoji") else ""
            desc_str  = ("  —  " + c["description"][:25]) if c.get("description") else ""
            lines.append("**" + str(i+1) + ".** " + emoji_str + c["label"] + desc_str)
        if len(cats) > 15:
            lines.append(t("embeds", "wizard", "q_more", n=len(cats)-15))
        embed.add_field(
            name=t("embeds", "edit_shared", "f_categories") + " (" + str(len(cats)) + ")",
            value="\\n".join(lines),
            inline=False
        )
    else:
        embed.add_field(name=t("embeds", "edit_shared", "f_categories"), value="*Keine Kategorien*", inline=False)

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class EditTicketEmbedModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "edit_embed_title"))
        self.user_id = user_id
        panel = _edit_state.get(user_id, {}).get("panel", {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "edit_label_title"),
            default=panel.get("title", ""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "edit_label_desc"),
            default=panel.get("embed_desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.f_color = discord.ui.TextInput(
            label=t("modals", "edit_label_color"),
            placeholder="z.B. FFD700 für Gold",
            default=panel.get("embed_color", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_thumb = discord.ui.TextInput(
            label=t("modals", "edit_label_thumb"),
            default="yes" if panel.get("embed_thumbnail", True) else "no",
            style=discord.TextStyle.short, required=False, max_length=5
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)
        self.add_item(self.f_color)
        self.add_item(self.f_thumb)

    async def on_submit(self, interaction: discord.Interaction):
        uid   = self.user_id
        panel = _edit_state[uid]["panel"]
        color_raw = self.f_color.value.strip().lstrip("#")
        if color_raw:
            try:
                int(color_raw, 16)
            except ValueError:
                return await interaction.response.send_message(
                    t("errors", "ticket_invalid_color"), ephemeral=True
                )
        thumb = self.f_thumb.value.strip().lower() not in ("no", "n", "false", "0", "nein")
        panel.update({
            "title":           self.f_title.value.strip(),
            "embed_desc":      self.f_desc.value.strip(),
            "embed_color":     color_raw,
            "embed_thumbnail": thumb,
        })
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, uid)


class EditTicketCatSelect(discord.ui.Select):
    """Pick a category to edit."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        cats = _edit_state.get(user_id, {}).get("panel", {}).get("categories", [])
        options = []
        for i, c in enumerate(cats[:25]):
            emoji_str = c.get("emoji") or None
            options.append(discord.SelectOption(
                label=c["label"][:100],
                value=str(i),
                emoji=emoji_str,
                description=(c.get("description") or "")[:100] or None
            ))
        if not options:
            options.append(discord.SelectOption(label="—", value="__none__"))
        super().__init__(
            placeholder=t("selects", "edit_cat_ph"),
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors", "application_not_yours"), ephemeral=True
            )
        if self.values[0] == "__none__":
            return await interaction.response.edit_message(content=t("errors", "ticket_no_cats"), view=None)
        cat_idx = int(self.values[0])
        await interaction.response.send_modal(EditTicketCatModal(self.user_id, cat_idx))


class EditTicketCatModal(discord.ui.Modal):
    def __init__(self, user_id: int, cat_idx: int):
        super().__init__(title=t("modals", "edit_cat_title"))
        self.user_id = user_id
        self.cat_idx = cat_idx
        cats = _edit_state.get(user_id, {}).get("panel", {}).get("categories", [])
        cat  = cats[cat_idx] if cat_idx < len(cats) else {}
        self.f_label = discord.ui.TextInput(
            label=t("modals", "edit_label_name"),
            default=cat.get("label", ""),
            style=discord.TextStyle.short, required=True, max_length=100
        )
        self.f_emoji = discord.ui.TextInput(
            label=t("modals", "edit_label_emoji"),
            default=cat.get("emoji", "") or "",
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "edit_label_desc_opt"),
            default=cat.get("description", "") or "",
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_label)
        self.add_item(self.f_emoji)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid  = self.user_id
        cats = _edit_state[uid]["panel"]["categories"]
        # Parse emoji
        emoji = None
        emoji_raw = self.f_emoji.value.strip()
        if emoji_raw:
            for char in emoji_raw:
                if ord(char) > 0x27BF:
                    emoji = char
                    break
            if not emoji:
                emoji = emoji_raw[:10]
        cats[self.cat_idx].update({
            "label":       self.f_label.value.strip()[:100],
            "emoji":       emoji,
            "description": self.f_desc.value.strip()[:100] or None,
        })
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, uid)


class EditTicketView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.embed_btn.label      = t("buttons", "edit_btn_embed")
        self.roles_btn.label      = t("buttons", "edit_btn_roles")
        self.edit_cat_btn.label   = t("buttons", "edit_btn_edit_cat")
        self.add_cat_btn.label    = t("buttons", "edit_btn_add_cat")
        self.remove_cat_btn.label = t("buttons", "edit_btn_remove_cat")
        self.save_btn.label       = t("buttons", "edit_btn_save")
        self.cancel_btn.label     = t("buttons", "edit_btn_cancel")

    def _check(self, i):
        return i.user.id == self.user_id

    @discord.ui.button(label="🎨",   style=discord.ButtonStyle.secondary, row=0)
    async def embed_btn(self, interaction, button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EditTicketEmbedModal(self.user_id))

    @discord.ui.button(label="👥",    style=discord.ButtonStyle.secondary, row=0)
    async def roles_btn(self, interaction, button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        uid = self.user_id
        view = _make_role_select_view(
            uid, "supporter_role_ids",
            {uid: _edit_state[uid]["panel"]},
            t("selects","wizard_pick_roles"), multi=True,
            refresh_fn=lambda u, g: (_build_edit_ticket_embed(u, g), EditTicketView(u))
        )
        await interaction.response.send_message(content=t("success","wizard_pick_roles_hint"), view=view, ephemeral=True)

    @discord.ui.button(label="📂", style=discord.ButtonStyle.blurple, row=0)
    async def edit_cat_btn(self, interaction, button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        cats = _edit_state.get(self.user_id, {}).get("panel", {}).get("categories", [])
        if not cats:
            return await interaction.response.send_message(t("errors","ticket_no_cats"), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(EditTicketCatSelect(self.user_id))
        await interaction.response.send_message(content=t("success", "edit_pick_cat"), view=view, ephemeral=True)

    @discord.ui.button(label="➕", style=discord.ButtonStyle.secondary, row=1)
    async def add_cat_btn(self, interaction, button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        panel = _edit_state.get(self.user_id, {}).get("panel", {})
        if len(panel.get("categories", [])) >= 25:
            return await interaction.response.send_message(t("errors","ticket_max_cats"), ephemeral=True)
        await interaction.response.send_modal(TicketEditCategoryModal(self.user_id))

    @discord.ui.button(label="🗑️a", style=discord.ButtonStyle.danger,    row=1)
    async def remove_cat_btn(self, interaction, button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        cats = _edit_state.get(self.user_id, {}).get("panel", {}).get("categories", [])
        if not cats:
            return await interaction.response.send_message(t("errors","ticket_no_cats"), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(TicketEditRemoveCatSelect(self.user_id))
        await interaction.response.send_message(content=t("success", "edit_remove_cat"), view=view, ephemeral=True)

    @discord.ui.button(label="✅",           style=discord.ButtonStyle.green,     row=2)
    async def save_btn(self, interaction, button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await _save_edit_and_update(interaction, self.user_id)

    @discord.ui.button(label="✖️",           style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction, button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        _edit_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors","application_cancelled"), embed=None, view=None)


async def _save_edit_and_update(interaction: discord.Interaction, user_id: int):
    """Save panel to config and update Discord message."""
    await interaction.response.defer(ephemeral=True)
    state      = _edit_state.pop(user_id, None)
    if not state:
        return await interaction.followup.send(t("errors","panel_not_found"), ephemeral=True)

    guild_id   = state["guild_id"]
    panel_type = state["type"]
    panel_idx  = state["panel_idx"]
    panel      = state["panel"]

    _save_panel(guild_id, panel_type, panel_idx, panel)

    # Update Discord message
    try:
        ch_id  = panel.get("channel_id")
        msg_id = panel.get("message_id") or panel.get("msg_id")
        if ch_id and msg_id:
            ch  = interaction.guild.get_channel(int(ch_id)) or await interaction.guild.fetch_channel(int(ch_id))
            msg = await ch.fetch_message(int(msg_id))

            if panel_type == "ticket_panels":
                color_hex = panel.get("embed_color") or ""
                try:
                    color = discord.Color(int(color_hex, 16)) if color_hex else discord.Color.gold()
                except (ValueError, TypeError):
                    color = discord.Color.gold()
                embed = discord.Embed(
                    title=panel.get("title") or t("embeds","ticket_panel","title"),
                    description=panel.get("embed_desc") or t("embeds","ticket_panel","desc"),
                    color=color
                )
                if panel.get("embed_thumbnail", True) and interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(text=t("embeds","ticket_panel","footer", name=interaction.guild.name))
                view = TicketView(panel.get("categories", []), panel.get("supporter_role_ids", []))
                await msg.edit(embed=embed, view=view)

            elif panel_type == "selfrole_panels":
                color_hex = panel.get("color_hex", "")
                try:
                    color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.blue()
                except (ValueError, TypeError):
                    color = discord.Color.blue()
                roles    = panel.get("roles", [])
                panel_id = str(panel.get("panel_id") or msg_id)
                embed = discord.Embed(
                    title=panel.get("title", ""),
                    description=format_discord_text(panel.get("desc", "")),
                    color=color,
                    timestamp=now_timestamp()
                )
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                    embed.set_footer(text=t("embeds","selfrole","panel_footer",
                                           name=interaction.guild.name, count=len(roles)),
                                     icon_url=interaction.guild.icon.url)
                await msg.edit(embed=embed, view=SelfRoleView(roles, panel_id))

            elif panel_type == "verify_panels":
                role_id  = panel.get("role_id")
                role     = interaction.guild.get_role(int(role_id)) if role_id else None
                color_hex = panel.get("color_hex", "")
                try:
                    color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.green()
                except (ValueError, TypeError):
                    color = discord.Color.green()
                embed = discord.Embed(
                    title=panel.get("title") or t("embeds","verify_panel","default_title"),
                    description=panel.get("desc") or t("embeds","verify_panel","default_desc"),
                    color=color
                )
                if panel.get("thumbnail", True) and interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(text=t("embeds","verify_panel","footer",
                                        role=role.name if role else str(role_id)))
                await msg.edit(embed=embed, view=VerifyView(int(role_id)) if role_id else discord.ui.View())

            elif panel_type == "application_panels":
                embed = discord.Embed(
                    title=panel.get("title") or t("embeds","application","default_title"),
                    description=panel.get("desc") or t("embeds","application","default_desc"),
                    color=discord.Color.blurple(),
                    timestamp=now_timestamp()
                )
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(text=t("embeds","application","panel_footer", name=interaction.guild.name))
                await msg.edit(embed=embed, view=ApplicationPanelView(panel_index=panel_idx))

    except Exception as e:
        await interaction.followup.send(
            t("errors", "edit_discord_update_failed") + str(e),
            ephemeral=True
        )
        return

    type_labels = {
        "ticket_panels":      "🎫 Ticket-Panel",
        "selfrole_panels":    "🎭 Self-Role-Panel",
        "application_panels": "📋 Bewerbungs-Panel",
        "verify_panels":      "✅ Verify-Panel",
    }
    done_embed = discord.Embed(
        title=t("embeds", "edit_shared", "done_title"),
        description=t("success", "edit_saved"),
        color=discord.Color.green()
    )
    if interaction.guild.icon:
        done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
    await interaction.followup.send(embed=done_embed, ephemeral=True)


# ── SELF-ROLE EDIT ────────────────────────────────────────────────────────────

def _build_edit_selfrole_embed(user_id: int, guild) -> discord.Embed:
    state = _edit_state.get(user_id, {})
    panel = state.get("panel", {})
    color_hex = panel.get("color_hex", "")
    try:
        color = discord.Color(int(color_hex.lstrip("#"), 16)) if color_hex else discord.Color.blue()
    except (ValueError, TypeError):
        color = discord.Color.blue()

    embed = discord.Embed(title=t("embeds", "edit_selfrole", "title"), color=color)
    title_val = panel.get("title") or t("embeds","wizard","not_set")
    desc_val  = (panel.get("desc") or "")[:50] + ("..." if len(panel.get("desc") or "") > 50 else "")
    color_val = ("#" + panel["color_hex"]) if panel.get("color_hex") else "*Standard (Blau)*"
    embed.add_field(name=t("embeds", "edit_shared", "f_settings"), value=(
        "**Titel:** " + title_val + "\\n"
        "**Beschreibung:** " + (desc_val or "*leer*") + "\\n"
        "**Farbe:** " + color_val
    ), inline=False)

    roles = panel.get("roles", [])
    if roles:
        lines = []
        for i, r in enumerate(roles[:15]):
            emoji_str = (r.get("emoji") + " ") if r.get("emoji") else ""
            desc_str  = ("  —  " + r["description"][:25]) if r.get("description") else ""
            lines.append("**" + str(i+1) + ".** " + emoji_str + r["label"] + "  <@&" + str(r["role_id"]) + ">" + desc_str)
        if len(roles) > 15:
            lines.append(t("embeds","wizard","q_more", n=len(roles)-15))
        embed.add_field(name=t("embeds", "edit_shared", "f_roles") + " (" + str(len(roles)) + ")", value="\\n".join(lines), inline=False)
    else:
        embed.add_field(name=t("embeds", "edit_shared", "f_roles"), value="*Keine Rollen*", inline=False)

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class EditSelfroleInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "edit_info_title"))
        self.user_id = user_id
        panel = _edit_state.get(user_id, {}).get("panel", {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "edit_label_title"),
            default=panel.get("title", ""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "edit_label_desc_opt"),
            default=panel.get("desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=500
        )
        self.f_color = discord.ui.TextInput(
            label=t("modals", "edit_label_color"),
            placeholder="z.B. 5865F2",
            default=panel.get("color_hex", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)
        self.add_item(self.f_color)

    async def on_submit(self, interaction: discord.Interaction):
        uid   = self.user_id
        panel = _edit_state[uid]["panel"]
        panel.update({
            "title":     self.f_title.value.strip(),
            "desc":      self.f_desc.value.strip(),
            "color_hex": self.f_color.value.strip().lstrip("#"),
        })
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, uid)


class EditSelfroleRoleSelect(discord.ui.Select):
    """Pick a role entry to edit."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        roles = _edit_state.get(user_id, {}).get("panel", {}).get("roles", [])
        options = []
        for i, r in enumerate(roles[:25]):
            options.append(discord.SelectOption(
                label=r["label"][:100],
                value=str(i),
                emoji=r.get("emoji") or None,
                description=(r.get("description") or "")[:100] or None
            ))
        if not options:
            options.append(discord.SelectOption(label="—", value="__none__"))
        super().__init__(
            placeholder=t("selects", "edit_role_ph"),
            min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        if self.values[0] == "__none__":
            return await interaction.response.edit_message(content=t("errors", "selfrole_no_roles_to_remove"), view=None)
        await interaction.response.send_modal(EditSelfroleRoleModal(self.user_id, int(self.values[0])))


class EditSelfroleRoleModal(discord.ui.Modal):
    def __init__(self, user_id: int, role_idx: int):
        super().__init__(title=t("modals", "edit_role_title"))
        self.user_id  = user_id
        self.role_idx = role_idx
        roles = _edit_state.get(user_id, {}).get("panel", {}).get("roles", [])
        r     = roles[role_idx] if role_idx < len(roles) else {}
        self.f_label = discord.ui.TextInput(
            label=t("modals", "edit_label_display_name"),
            default=r.get("label", ""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_emoji = discord.ui.TextInput(
            label=t("modals", "edit_label_emoji"),
            default=r.get("emoji", "") or "",
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "edit_label_role_desc"),
            default=r.get("description", "") or "",
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_label)
        self.add_item(self.f_emoji)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid   = self.user_id
        roles = _edit_state[uid]["panel"]["roles"]
        emoji = None
        emoji_raw = self.f_emoji.value.strip()
        if emoji_raw:
            for char in emoji_raw:
                if ord(char) > 0x27BF:
                    emoji = char
                    break
            if not emoji:
                emoji = emoji_raw[:10]
        roles[self.role_idx].update({
            "label":       self.f_label.value.strip()[:100],
            "emoji":       emoji,
            "description": self.f_desc.value.strip()[:100] or None,
        })
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, uid)


class EditSelfroleView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.info_btn.label        = t("buttons", "edit_btn_info")
        self.edit_role_btn.label   = t("buttons", "edit_btn_edit_role")
        self.remove_role_btn.label = t("buttons", "edit_btn_remove_role")
        self.save_btn.label        = t("buttons", "edit_btn_save")
        self.cancel_btn.label      = t("buttons", "edit_btn_cancel")

    def _check(self, i): return i.user.id == self.user_id

    @discord.ui.button(label="✏️",     style=discord.ButtonStyle.secondary, row=0)
    async def info_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EditSelfroleInfoModal(self.user_id))

    @discord.ui.button(label="🎭a",    style=discord.ButtonStyle.blurple,   row=0)
    async def edit_role_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        roles = _edit_state.get(self.user_id, {}).get("panel", {}).get("roles", [])
        if not roles:
            return await interaction.response.send_message(t("errors","selfrole_no_roles_to_remove"), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(EditSelfroleRoleSelect(self.user_id))
        await interaction.response.send_message(content=t("success", "edit_pick_role"), view=view, ephemeral=True)

    @discord.ui.button(label="🗑️b",     style=discord.ButtonStyle.danger,    row=0)
    async def remove_role_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        roles = _edit_state.get(self.user_id, {}).get("panel", {}).get("roles", [])
        if not roles:
            return await interaction.response.send_message(t("errors","selfrole_no_roles_to_remove"), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(SelfRoleRemoveRoleSelect(self.user_id))
        await interaction.response.send_message(content=t("success", "edit_remove_role"), view=view, ephemeral=True)

    @discord.ui.button(label="✅",            style=discord.ButtonStyle.green,     row=1)
    async def save_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await _save_edit_and_update(interaction, self.user_id)

    @discord.ui.button(label="✖️",            style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        _edit_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors","application_cancelled"), embed=None, view=None)


# ── VERIFY EDIT ───────────────────────────────────────────────────────────────

def _build_edit_verify_embed(user_id: int, guild) -> discord.Embed:
    state = _edit_state.get(user_id, {})
    panel = state.get("panel", {})
    embed = discord.Embed(title=t("embeds", "edit_verify", "title"), color=discord.Color.green())
    role_id   = panel.get("role_id")
    role_val  = ("<@&" + str(role_id) + ">") if role_id else t("embeds","wizard","not_set")
    title_val = panel.get("title") or t("embeds","verify_panel","default_title")
    desc_val  = (panel.get("desc") or "")[:50] + ("..." if len(panel.get("desc") or "") > 50 else "")
    color_val = ("#" + panel["color_hex"]) if panel.get("color_hex") else "*Standard (Grün)*"
    thumb_val = "✅ An" if panel.get("thumbnail", True) else "❌ Aus"
    embed.add_field(name=t("embeds", "edit_shared", "f_settings"), value=(
        "**Rolle:** " + role_val + "\\n"
        "**Titel:** " + title_val + "\\n"
        "**Beschreibung:** " + (desc_val or "*leer*") + "\\n"
        "**Farbe:** " + color_val + "\\n"
        "**Thumbnail:** " + thumb_val
    ), inline=False)
    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class EditVerifyInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "edit_verify_title"))
        self.user_id = user_id
        panel = _edit_state.get(user_id, {}).get("panel", {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "edit_label_title"),
            default=panel.get("title", ""),
            style=discord.TextStyle.short, required=False, max_length=80
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "edit_label_desc"),
            default=panel.get("desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.f_color = discord.ui.TextInput(
            label=t("modals", "edit_label_color"),
            placeholder="z.B. 57F287 für Grün",
            default=panel.get("color_hex", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_thumb = discord.ui.TextInput(
            label=t("modals", "edit_label_thumb"),
            default="yes" if panel.get("thumbnail", True) else "no",
            style=discord.TextStyle.short, required=False, max_length=5
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)
        self.add_item(self.f_color)
        self.add_item(self.f_thumb)

    async def on_submit(self, interaction: discord.Interaction):
        uid   = self.user_id
        panel = _edit_state[uid]["panel"]
        thumb = self.f_thumb.value.strip().lower() not in ("no","n","false","0","nein")
        panel.update({
            "title":     self.f_title.value.strip(),
            "desc":      self.f_desc.value.strip(),
            "color_hex": self.f_color.value.strip().lstrip("#"),
            "thumbnail": thumb,
        })
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, uid)


class EditVerifyView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.info_btn.label    = t("buttons", "edit_btn_info")
        self.role_btn.label    = t("buttons", "edit_btn_change_role")
        self.save_btn.label    = t("buttons", "edit_btn_save")
        self.cancel_btn.label  = t("buttons", "edit_btn_cancel")

    def _check(self, i): return i.user.id == self.user_id

    @discord.ui.button(label="✏️",   style=discord.ButtonStyle.secondary, row=0)
    async def info_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EditVerifyInfoModal(self.user_id))

    @discord.ui.button(label="🎭b",      style=discord.ButtonStyle.blurple,   row=0)
    async def role_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        uid = self.user_id
        view = _make_role_select_view(
            uid, "role_id",
            {uid: _edit_state[uid]["panel"]},
            t("selects","wizard_pick_verify_role"), multi=False,
            refresh_fn=lambda u, g: (_build_edit_verify_embed(u, g), EditVerifyView(u))
        )
        await interaction.response.send_message(content=t("success","wizard_pick_roles_hint"), view=view, ephemeral=True)

    @discord.ui.button(label="✅",          style=discord.ButtonStyle.green,     row=1)
    async def save_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await _save_edit_and_update(interaction, self.user_id)

    @discord.ui.button(label="✖️",          style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        _edit_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors","application_cancelled"), embed=None, view=None)


# ── APPLICATION EDIT ──────────────────────────────────────────────────────────

def _build_edit_application_embed(user_id: int, guild) -> discord.Embed:
    state = _edit_state.get(user_id, {})
    panel = state.get("panel", {})
    embed = discord.Embed(title=t("embeds", "edit_application", "title"), color=discord.Color.blurple())

    title_val   = panel.get("title") or t("embeds","wizard","not_set")
    ch_id       = panel.get("review_channel_id")
    channel_val = ("<#" + str(ch_id) + ">") if ch_id else t("embeds","wizard","not_set")
    role_ids    = panel.get("reviewer_role_ids") or []
    roles_val   = " ".join("<@&" + str(r) + ">" for r in role_ids) if role_ids else t("embeds","wizard","not_set")

    embed.add_field(name=t("embeds", "edit_shared", "f_settings"), value=(
        "**Titel:** " + title_val + "\\n"
        "**Review-Kanal:** " + channel_val + "\\n"
        "**Reviewer-Rollen:** " + roles_val
    ), inline=False)

    questions = panel.get("questions")
    if questions is None:
        q_val = t("embeds", "wizard", "q_default")
    elif not questions:
        q_val = "*Keine Fragen*"
    else:
        shown = ["**" + str(i+1) + ".** " + q["label"] for i, q in enumerate(questions[:8])]
        if len(questions) > 8:
            shown.append(t("embeds","wizard","q_more", n=len(questions)-8))
        q_val = "\\n".join(shown)
    embed.add_field(name=t("embeds", "edit_application", "f_questions") + " (" + (str(len(questions)) if questions is not None else "Standard") + ")",
                    value=q_val, inline=False)

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class EditApplicationInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "edit_info_title"))
        self.user_id = user_id
        panel = _edit_state.get(user_id, {}).get("panel", {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "edit_label_title"),
            default=panel.get("title", ""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "edit_label_desc"),
            default=panel.get("desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.add_item(self.f_title)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid   = self.user_id
        panel = _edit_state[uid]["panel"]
        panel.update({
            "title": self.f_title.value.strip(),
            "desc":  self.f_desc.value.strip(),
        })
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, uid)


class EditAppQuestionSelect(discord.ui.Select):
    """Pick a question to edit."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        panel     = _edit_state.get(user_id, {}).get("panel", {})
        # Load language-appropriate default questions if panel uses defaults
        guild_lang = load_config().get(str(interaction.guild_id), {}).get("language", "en")
        questions = panel.get("questions") or _load_default_application(guild_lang)
        options   = []
        for i, q in enumerate(questions[:25]):
            label_str = q["label"][:90]
            sec_raw   = q.get("section")
            sec_name  = sec_raw.get("name", "") if isinstance(sec_raw, dict) else (sec_raw or "")
            desc_str  = (sec_name + " · " + q.get("style","paragraph"))[:100]
            options.append(discord.SelectOption(
                label=label_str, value=str(i), description=desc_str or None
            ))
        if not options:
            options.append(discord.SelectOption(label="—", value="__none__"))
        super().__init__(
            placeholder=t("selects", "edit_q_ph"),
            min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        if self.values[0] == "__none__":
            return await interaction.response.edit_message(content=t("errors","app_no_questions"), view=None)
        await interaction.response.send_modal(EditAppQuestionModal(self.user_id, int(self.values[0])))


class EditAppQuestionModal(discord.ui.Modal):
    def __init__(self, user_id: int, q_idx: int):
        super().__init__(title=t("modals", "edit_q_title"))
        self.user_id = user_id
        self.q_idx   = q_idx
        panel     = _edit_state.get(user_id, {}).get("panel", {})
        questions = list(panel.get("questions") or DEFAULT_APPLICATION_QUESTIONS)
        q         = questions[q_idx] if q_idx < len(questions) else {}

        self.f_label = discord.ui.TextInput(
            label=t("modals", "app_setup_q_label"),
            default=q.get("label", ""),
            style=discord.TextStyle.short, required=True, max_length=45
        )
        self.f_placeholder = discord.ui.TextInput(
            label=t("modals", "app_setup_q_placeholder_label"),
            default=q.get("placeholder", ""),
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.f_min_length = discord.ui.TextInput(
            label=t("modals", "app_setup_q_minlen_label"),
            default=str(q.get("min_length", 0)),
            style=discord.TextStyle.short, required=False, max_length=4
        )
        self.f_style = discord.ui.TextInput(
            label=t("modals", "app_setup_q_style_label"),
            default=q.get("style", "paragraph"),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.add_item(self.f_label)
        self.add_item(self.f_placeholder)
        self.add_item(self.f_min_length)
        self.add_item(self.f_style)

    async def on_submit(self, interaction: discord.Interaction):
        uid   = self.user_id
        panel = _edit_state[uid]["panel"]
        # If questions is None (default), materialise a copy first
        if panel.get("questions") is None:
            panel["questions"] = [dict(q) for q in DEFAULT_APPLICATION_QUESTIONS]

        min_len = 0
        try:
            min_len = max(0, int(self.f_min_length.value.strip()))
        except (ValueError, AttributeError):
            pass

        style_raw = (self.f_style.value or "").strip().lower()
        style     = "short" if style_raw in ("short", "s", "kurz", "k") else "paragraph"

        panel["questions"][self.q_idx].update({
            "label":       self.f_label.value.strip()[:45],
            "placeholder": self.f_placeholder.value.strip()[:100],
            "min_length":  min_len,
            "style":       style,
        })
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, uid)


class EditAppQuestionSectionModal(discord.ui.Modal):
    """Edit the section of a question."""
    def __init__(self, user_id: int, q_idx: int):
        super().__init__(title=t("modals", "app_setup_section_title"))
        self.user_id = user_id
        self.q_idx   = q_idx
        panel     = _edit_state.get(user_id, {}).get("panel", {})
        questions = list(panel.get("questions") or DEFAULT_APPLICATION_QUESTIONS)
        q         = questions[q_idx] if q_idx < len(questions) else {}
        sec_raw   = q.get("section") or {}
        sec_name  = sec_raw.get("name", "") if isinstance(sec_raw, dict) else (sec_raw or "")
        sec_desc  = sec_raw.get("desc", "") if isinstance(sec_raw, dict) else ""

        self.f_name = discord.ui.TextInput(
            label=t("modals", "app_setup_section_label"),
            placeholder=t("modals", "app_setup_section_ph"),
            default=sec_name,
            style=discord.TextStyle.short, required=False, max_length=60
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "app_setup_section_desc_label"),
            placeholder=t("modals", "app_setup_section_desc_ph"),
            default=sec_desc,
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_name)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid   = self.user_id
        panel = _edit_state[uid]["panel"]
        if panel.get("questions") is None:
            panel["questions"] = [dict(q) for q in DEFAULT_APPLICATION_QUESTIONS]
        name = self.f_name.value.strip()
        desc = self.f_desc.value.strip()
        panel["questions"][self.q_idx]["section"] = {"name": name, "desc": desc} if name else None
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, uid)


class EditAppQSelectView(discord.ui.View):
    """Ephemeral view: pick question + action."""
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.add_item(EditAppQuestionSelect(user_id))
        self.add_q_btn.label     = t("buttons", "edit_btn_add_q")
        self.remove_last_btn.label = t("buttons", "edit_btn_remove_last_q")

    @discord.ui.button(label="➕", style=discord.ButtonStyle.blurple, row=1)
    async def add_q_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        panel     = _edit_state.get(self.user_id, {}).get("panel", {})
        if panel.get("questions") is None:
            _edit_state[self.user_id]["panel"]["questions"] = [dict(q) for q in DEFAULT_APPLICATION_QUESTIONS]
        await interaction.response.send_modal(AppSetupQuestionsModal(self.user_id))

    @discord.ui.button(label="↩️", style=discord.ButtonStyle.danger, row=1)
    async def remove_last_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        panel = _edit_state.get(self.user_id, {}).get("panel", {})
        if panel.get("questions") is None:
            _edit_state[self.user_id]["panel"]["questions"] = [dict(q) for q in DEFAULT_APPLICATION_QUESTIONS]
        questions = _edit_state[self.user_id]["panel"]["questions"]
        if not questions:
            return await interaction.response.send_message(t("errors","app_no_questions"), ephemeral=True)
        questions.pop()
        await interaction.response.edit_message(content=t("success","edit_q_removed"), view=None)
        await _refresh_edit(interaction, self.user_id)

class EditApplicationView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.info_btn.label         = t("buttons", "edit_btn_info")
        self.channel_btn.label      = t("buttons", "edit_btn_channel")
        self.reviewer_btn.label     = t("buttons", "edit_btn_reviewer_roles")
        self.edit_q_btn.label       = t("buttons", "edit_btn_questions")
        self.default_q_btn.label    = t("buttons", "edit_btn_default_q")
        self.save_btn.label         = t("buttons", "edit_btn_save")
        self.cancel_btn.label       = t("buttons", "edit_btn_cancel")

    def _check(self, i): return i.user.id == self.user_id

    @discord.ui.button(label="✏️",      style=discord.ButtonStyle.secondary, row=0)
    async def info_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EditApplicationInfoModal(self.user_id))

    @discord.ui.button(label="📢",         style=discord.ButtonStyle.secondary, row=0)
    async def channel_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        uid = self.user_id
        view = _make_channel_select_view(
            uid, "review_channel_id",
            {uid: _edit_state[uid]["panel"]},
            t("selects","wizard_pick_channel"),
            refresh_fn=lambda u, g: (_build_edit_application_embed(u, g), EditApplicationView(u))
        )
        await interaction.response.send_message(content=t("success","wizard_pick_channel_hint"), view=view, ephemeral=True)

    @discord.ui.button(label="👥b",      style=discord.ButtonStyle.secondary, row=0)
    async def reviewer_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        uid = self.user_id
        view = _make_role_select_view(
            uid, "reviewer_role_ids",
            {uid: _edit_state[uid]["panel"]},
            t("selects","wizard_pick_roles"), multi=True,
            refresh_fn=lambda u, g: (_build_edit_application_embed(u, g), EditApplicationView(u))
        )
        await interaction.response.send_message(content=t("success","wizard_pick_roles_hint"), view=view, ephemeral=True)

    @discord.ui.button(label="❓",        style=discord.ButtonStyle.blurple,   row=1)
    async def edit_q_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        panel     = _edit_state.get(self.user_id, {}).get("panel", {})
        questions = panel.get("questions") or DEFAULT_APPLICATION_QUESTIONS
        if not questions:
            return await interaction.response.send_message(t("errors","app_no_questions"), ephemeral=True)
        view = EditAppQSelectView(self.user_id)
        await interaction.response.send_message(
            content=t("success","edit_pick_question"), view=view, ephemeral=True
        )

    @discord.ui.button(label="✅b",      style=discord.ButtonStyle.secondary, row=1)
    async def default_q_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        _edit_state[self.user_id]["panel"]["questions"] = None
        await interaction.response.defer(ephemeral=True)
        await _refresh_edit(interaction, self.user_id)

    @discord.ui.button(label="✅",             style=discord.ButtonStyle.green,     row=2)
    async def save_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await _save_edit_and_update(interaction, self.user_id)

    @discord.ui.button(label="✖️",             style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        _edit_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors","application_cancelled"), embed=None, view=None)


# ─────────────────────────────────────────────
#  ADMIN PANEL
# ─────────────────────────────────────────────

class AdminTypeSelect(discord.ui.Select):
    """Top-level: User or Chat."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        options = [
            discord.SelectOption(
                label=t("selects","admin_user"), value="user",
                emoji="👤", description=t("selects","admin_user_desc")
            ),
            discord.SelectOption(
                label=t("selects","admin_chat"), value="chat",
                emoji="💬", description=t("selects","admin_chat_desc")
            ),
        ]
        super().__init__(
            placeholder=t("selects","admin_type_ph"),
            min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        if self.values[0] == "user":
            # Show member select dropdown directly
            view = AdminMemberSelectView(self.user_id, interaction.guild)
            embed = discord.Embed(
                title=t("embeds","admin_panel","user_title"),
                description=t("embeds","admin_panel","user_select_desc"),
                color=discord.Color.blurple()
            )
            if interaction.guild.icon:
                embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            embed = discord.Embed(
                title=t("embeds","admin_panel","chat_title"),
                description=t("embeds","admin_panel","chat_desc"),
                color=discord.Color.og_blurple()
            )
            if interaction.guild.icon:
                embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
            await interaction.response.edit_message(embed=embed, view=AdminChatView(self.user_id, interaction.channel_id))


class AdminStartView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(AdminTypeSelect(user_id))


# ── User Panel ────────────────────────────────────────────────────────────────

def _build_userinfo_embed(target: discord.Member, guild: discord.Guild) -> discord.Embed:
    """Shared helper — builds the user info embed shown in admin panel."""
    config = load_config()
    warns  = config.get(str(guild.id), {}).get("warns", {}).get(str(target.id), 0)
    roles  = [r.mention for r in target.roles if r != guild.default_role]
    embed  = discord.Embed(
        title="👤 " + target.display_name,
        color=target.color if target.color.value != 0 else discord.Color.blurple(),
        timestamp=now_timestamp()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name=t("embeds","userinfo","f_id"),     value="`" + str(target.id) + "`", inline=True)
    embed.add_field(name=t("embeds","userinfo","f_warns"),   value=("⚠️ `" + str(warns) + "`") if warns else "`0`", inline=True)
    embed.add_field(name=t("embeds","userinfo","f_bot"),     value=t("embeds","userinfo","bot_yes") if target.bot else t("embeds","userinfo","bot_no"), inline=True)
    embed.add_field(name=t("embeds","userinfo","f_joined"),  value=discord.utils.format_dt(target.joined_at, "R") if target.joined_at else "?", inline=True)
    embed.add_field(name=t("embeds","userinfo","f_created"), value=discord.utils.format_dt(target.created_at, "R"), inline=True)
    if target.timed_out_until:
        embed.add_field(
            name="⏳ " + t("buttons","admin_timeout"),
            value=discord.utils.format_dt(target.timed_out_until, "R"),
            inline=True
        )
    embed.add_field(
        name=t("embeds","userinfo","f_roles"),
        value=" ".join(roles) if roles else t("embeds","userinfo","roles_none"),
        inline=False
    )
    if guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class AdminMemberSelect(discord.ui.UserSelect):
    """Discord native user select — shows all server members."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(
            placeholder=t("selects","admin_pick_member_ph"),
            min_values=1, max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                t("errors","application_not_yours"), ephemeral=True
            )
        target = interaction.guild.get_member(self.values[0].id)
        if not target:
            return await interaction.response.send_message(
                t("errors","admin_user_not_found"), ephemeral=True
            )
        # Show userinfo embed + action buttons immediately
        embed = _build_userinfo_embed(target, interaction.guild)
        await interaction.response.edit_message(
            embed=embed,
            view=AdminUserView(self.user_id, target)
        )


class AdminMemberSelectView(discord.ui.View):
    """Step 1: pick a member via Discord native user select."""
    def __init__(self, user_id: int, guild: discord.Guild):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.add_item(AdminMemberSelect(user_id))
        self.back_btn.label = t("buttons","admin_back")

    def _check(self, i): return i.user.id == self.user_id

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        embed = discord.Embed(
            title=t("embeds","admin_panel","title"),
            description=t("embeds","admin_panel","desc"),
            color=discord.Color.blurple()
        )
        if interaction.guild.icon:
            embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=embed, view=AdminStartView(self.user_id))


class AdminUserView(discord.ui.View):
    def __init__(self, user_id: int, target: discord.Member):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.target  = target
        self.timeout_btn.label        = t("buttons", "admin_timeout")
        self.extend_timeout_btn.label = t("buttons", "admin_extend_timeout")
        self.remove_timeout_btn.label = t("buttons", "admin_remove_timeout")
        self.warn_btn.label           = t("buttons", "admin_warn")
        self.kick_btn.label           = t("buttons", "admin_kick")
        self.ban_btn.label            = t("buttons", "admin_ban")
        self.change_user_btn.label    = t("buttons", "admin_pick_user")
        self.back_btn.label           = t("buttons", "admin_back")

    def _check(self, i): return i.user.id == self.user_id

    @discord.ui.button(label="⏳", style=discord.ButtonStyle.secondary, row=0)
    async def timeout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AdminTimeoutModal(self.user_id, self.target, extend=False))

    @discord.ui.button(label="⏳+", style=discord.ButtonStyle.secondary, row=1)
    async def extend_timeout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AdminTimeoutModal(self.user_id, self.target, extend=True))

    @discord.ui.button(label="⏳✖", style=discord.ButtonStyle.secondary, row=1)
    async def remove_timeout_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        try:
            await self.target.timeout(None, reason="Admin Panel — Timeout removed")
            try:
                updated = await interaction.guild.fetch_member(self.target.id)
            except Exception:
                updated = self.target
            updated_embed = _build_userinfo_embed(updated, interaction.guild)
            await interaction.response.edit_message(
                embed=updated_embed, view=AdminUserView(self.user_id, updated)
            )
            log_action(str(interaction.guild_id), interaction.user,
                        "admin_timeout_remove", str(self.target), "removed")
            await interaction.followup.send(
                t("success","admin_timeout_removed", user=self.target.display_name), ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(t("errors","timeout_error") + " " + str(e), ephemeral=True)

    @discord.ui.button(label="⚠️", style=discord.ButtonStyle.secondary, row=2)
    async def warn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AdminWarnModal(self.user_id, self.target))

    @discord.ui.button(label="👢", style=discord.ButtonStyle.danger, row=2)
    async def kick_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AdminKickModal(self.user_id, self.target))

    @discord.ui.button(label="🔨", style=discord.ButtonStyle.danger, row=2)
    async def ban_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AdminBanModal(self.user_id, self.target))

    @discord.ui.button(label="👤", style=discord.ButtonStyle.blurple, row=3)
    async def change_user_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        view = AdminMemberSelectView(self.user_id, interaction.guild)
        embed = discord.Embed(
            title=t("embeds","admin_panel","user_title"),
            description=t("embeds","admin_panel","user_select_desc"),
            color=discord.Color.blurple()
        )
        if interaction.guild.icon:
            embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary, row=3)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        embed = discord.Embed(
            title=t("embeds","admin_panel","title"),
            description=t("embeds","admin_panel","desc"),
            color=discord.Color.blurple()
        )
        if interaction.guild.icon:
            embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=embed, view=AdminStartView(self.user_id))


class AdminTimeoutModal(discord.ui.Modal):
    def __init__(self, user_id: int, target: discord.Member, extend: bool = False):
        title_key = "admin_extend_timeout_title" if extend else "admin_timeout_title"
        super().__init__(title=t("modals", title_key))
        self.user_id = user_id
        self.target  = target
        self.extend  = extend
        self.f_min = discord.ui.TextInput(
            label=t("modals","admin_timeout_label"),
            placeholder=t("modals","admin_timeout_ph"),
            style=discord.TextStyle.short, required=True, max_length=6
        )
        self.f_reason = discord.ui.TextInput(
            label=t("modals","admin_reason_label"),
            placeholder=t("modals","admin_reason_ph"),
            style=discord.TextStyle.short, required=False, max_length=200
        )
        self.add_item(self.f_min)
        self.add_item(self.f_reason)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.f_min.value.strip())
        except ValueError:
            return await interaction.response.send_message(t("errors","admin_invalid_number"), ephemeral=True)
        reason = self.f_reason.value.strip() or t("errors","no_default_reason")

        if self.extend and self.target.timed_out_until:
            # Extend: add minutes to existing timeout
            remaining = self.target.timed_out_until - discord.utils.utcnow()
            total_sec  = max(0, remaining.total_seconds()) + minutes * 60
            duration   = datetime.timedelta(seconds=total_sec)
        else:
            duration = datetime.timedelta(minutes=minutes)

        try:
            await self.target.timeout(duration, reason=reason)

            # ── DM to target ──────────────────────────────────────────────────
            until_dt  = discord.utils.utcnow() + duration
            until_str = discord.utils.format_dt(until_dt, "R")
            dm_embed  = make_dm_embed(
                title=t("embeds","dm_timeout","title"),
                description=t("embeds","dm_timeout","desc",
                              server=interaction.guild.name, until=until_str),
                color=discord.Color.light_grey(),
                guild=interaction.guild,
                fields=[
                    (t("embeds","dm_timeout","f_server"), interaction.guild.name,  True),
                    (t("embeds","dm_timeout","f_mod"),    str(interaction.user),   True),
                    (t("embeds","dm_timeout","f_dur"),
                     t("embeds","dm_timeout","dur_val", minutes=minutes),          True),
                    (t("embeds","dm_timeout","f_ends"),   until_str,               True),
                    (t("embeds","dm_timeout","f_reason"), reason,                  False),
                ],
                footer_system=t("embeds","shared","footer_mod")
            )
            await send_dm(self.target, embed=dm_embed)

            # ── Update embed with fresh userinfo (includes new timeout) ───────
            # Need to re-fetch member so timed_out_until is current
            try:
                updated = await interaction.guild.fetch_member(self.target.id)
            except Exception:
                updated = self.target
            updated_embed = _build_userinfo_embed(updated, interaction.guild)
            await interaction.response.edit_message(
                embed=updated_embed,
                view=AdminUserView(self.user_id, updated)
            )
            await interaction.followup.send(
                t("success","admin_timeout_set",
                  user=self.target.display_name, minutes=minutes), ephemeral=True
            )
            log_action(str(interaction.guild_id), interaction.user,
                        "admin_timeout", str(self.target),
                        str(minutes) + "min | " + reason)
            await send_log(
                interaction.guild,
                t("embeds","log_timeout","title"),
                t("embeds","log_timeout","desc"),
                discord.Color.light_grey(),
                self.target, interaction.user, reason,
                extra_fields=[(t("embeds","log_timeout","f_dur"), "`" + str(minutes) + "`", True)]
            )
        except Exception as e:
            await interaction.response.send_message(t("errors","timeout_error") + " " + str(e), ephemeral=True)


class AdminWarnModal(discord.ui.Modal):
    def __init__(self, user_id: int, target: discord.Member):
        super().__init__(title=t("modals","admin_warn_title"))
        self.user_id = user_id
        self.target  = target
        self.f_reason = discord.ui.TextInput(
            label=t("modals","admin_reason_label"),
            placeholder=t("modals","admin_reason_ph"),
            style=discord.TextStyle.short, required=True, max_length=200
        )
        self.add_item(self.f_reason)

    async def on_submit(self, interaction: discord.Interaction):
        grund  = self.f_reason.value.strip()
        config = load_config()
        gid    = str(interaction.guild_id)
        uid    = str(self.target.id)
        config.setdefault(gid, {}).setdefault("warns", {})
        new_count = config[gid]["warns"].get(uid, 0) + 1
        config[gid]["warns"][uid] = new_count
        save_config(config)
        warn_color = discord.Color.yellow() if new_count < 3 else discord.Color.orange() if new_count < 5 else discord.Color.red()
        _wi = {1:"icon_1",2:"icon_2",3:"icon_3",4:"icon_4",5:"icon_5"}
        icon = t("embeds","dm_warn",_wi.get(new_count,"icon_max"))
        dm_embed = make_dm_embed(
            title=icon + " " + t("embeds","dm_warn","title"),
            description=t("embeds","dm_warn","desc"),
            color=warn_color, guild=interaction.guild,
            fields=[
                (t("embeds","dm_warn","f_server"), interaction.guild.name, True),
                (t("embeds","dm_warn","f_mod"), str(interaction.user), True),
                (t("embeds","dm_warn","f_total"), str(new_count), True),
                (t("embeds","dm_warn","f_reason"), grund, False),
            ],
            footer_system=t("embeds","shared","footer_mod")
        )
        await send_dm(self.target, embed=dm_embed)
        await interaction.response.send_message(
            t("success","warn_success", mention=self.target.mention, count=new_count), ephemeral=True
        )
        log_action(str(interaction.guild_id), interaction.user,
                   "admin_warn", str(self.target),
                   "#" + str(new_count) + ": " + grund,
                   payload={"user_id": self.target.id, "user_name": str(self.target),
                             "count": new_count, "reason": grund,
                             "avatar": str(self.target.display_avatar.url)})
        await send_log(
            interaction.guild,
            t("embeds","log_warn","title", count=new_count),
            t("embeds","log_warn","desc"),
            warn_color, self.target, interaction.user, grund,
            extra_fields=[(t("embeds","log_warn","f_total"), "`" + str(new_count) + "`", True)]
        )


class AdminKickModal(discord.ui.Modal):
    def __init__(self, user_id: int, target: discord.Member):
        super().__init__(title=t("modals","admin_kick_title"))
        self.user_id = user_id
        self.target  = target
        self.f_reason = discord.ui.TextInput(
            label=t("modals","admin_reason_label"),
            placeholder=t("modals","admin_reason_ph"),
            style=discord.TextStyle.short, required=False, max_length=200
        )
        self.add_item(self.f_reason)

    async def on_submit(self, interaction: discord.Interaction):
        grund = self.f_reason.value.strip() or t("errors","no_default_reason")
        dm_embed = make_dm_embed(
            title=t("embeds","dm_kick","title"), description=t("embeds","dm_kick","desc"),
            color=discord.Color.orange(), guild=interaction.guild,
            fields=[
                (t("embeds","dm_kick","f_server"), interaction.guild.name, True),
                (t("embeds","dm_kick","f_mod"), str(interaction.user), True),
                (t("embeds","dm_kick","f_date"), short_time(), True),
                (t("embeds","dm_kick","f_reason"), grund, False),
            ],
            footer_system=t("embeds","shared","footer_mod")
        )
        await send_dm(self.target, embed=dm_embed)
        try:
            await self.target.kick(reason=grund)
            await interaction.response.send_message(
                t("success","kick_success", user=str(self.target)), ephemeral=True
            )
            log_action(str(interaction.guild_id), interaction.user,
                        "admin_kick", str(self.target), grund,
                        payload={"user_id": self.target.id, "user_name": str(self.target),
                                  "reason": grund, "avatar": str(self.target.display_avatar.url)})
            await send_log(interaction.guild, t("embeds","log_kick","title"),
                t("embeds","log_kick","desc"), discord.Color.orange(),
                self.target, interaction.user, grund)
        except Exception:
            await interaction.response.send_message(t("errors","kick_error"), ephemeral=True)


class AdminBanModal(discord.ui.Modal):
    def __init__(self, user_id: int, target: discord.Member):
        super().__init__(title=t("modals","admin_ban_title"))
        self.user_id = user_id
        self.target  = target
        self.f_reason = discord.ui.TextInput(
            label=t("modals","admin_reason_label"),
            placeholder=t("modals","admin_reason_ph"),
            style=discord.TextStyle.short, required=False, max_length=200
        )
        self.add_item(self.f_reason)

    async def on_submit(self, interaction: discord.Interaction):
        grund = self.f_reason.value.strip() or t("errors","no_default_reason")
        dm_embed = make_dm_embed(
            title=t("embeds","dm_ban","title"), description=t("embeds","dm_ban","desc"),
            color=discord.Color.red(), guild=interaction.guild,
            fields=[
                (t("embeds","dm_ban","f_server"), interaction.guild.name, True),
                (t("embeds","dm_ban","f_mod"), str(interaction.user), True),
                (t("embeds","dm_ban","f_date"), short_time(), True),
                (t("embeds","dm_ban","f_reason"), grund, False),
            ],
            footer_system=t("embeds","shared","footer_mod")
        )
        await send_dm(self.target, embed=dm_embed)
        try:
            await self.target.ban(reason=grund)
            await interaction.response.send_message(
                t("success","ban_success", user=str(self.target)), ephemeral=True
            )
            log_action(str(interaction.guild_id), interaction.user,
                        "admin_ban", str(self.target), grund,
                        payload={"user_id": self.target.id, "user_name": str(self.target),
                                  "reason": grund, "avatar": str(self.target.display_avatar.url)})
            await send_log(interaction.guild, t("embeds","log_ban","title"),
                t("embeds","log_ban","desc"), discord.Color.red(),
                self.target, interaction.user, grund)
        except Exception:
            await interaction.response.send_message(t("errors","ban_error"), ephemeral=True)


# ── Chat Panel ────────────────────────────────────────────────────────────────

class AdminChatView(discord.ui.View):
    def __init__(self, user_id: int, channel_id: int):
        super().__init__(timeout=300)
        self.user_id    = user_id
        self.channel_id = channel_id
        self.lock_btn.label       = t("buttons","admin_lock")
        self.unlock_btn.label     = t("buttons","admin_unlock")
        self.slowmode_btn.label   = t("buttons","admin_slowmode")
        self.purge_btn.label      = t("buttons","admin_purge")
        self.back_btn.label       = t("buttons","admin_back")

    def _check(self, i): return i.user.id == self.user_id

    @discord.ui.button(label="🔒", style=discord.ButtonStyle.danger, row=0)
    async def lock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            await channel.set_permissions(
                interaction.guild.default_role, send_messages=False
            )
            await interaction.response.send_message(
                t("success","admin_chat_locked", channel=channel.mention), ephemeral=True
            )
            log_action(str(interaction.guild_id), interaction.user,
                        "admin_lock", str(channel))
            await send_log(
                interaction.guild,
                t("embeds","log_chat_lock","title"),
                t("embeds","log_chat_lock","desc", channel=channel.mention),
                discord.Color.red(), interaction.user, moderator=interaction.user,
            )
        except Exception as e:
            await interaction.response.send_message(t("errors","admin_chat_error") + str(e), ephemeral=True)

    @discord.ui.button(label="🔓", style=discord.ButtonStyle.green, row=0)
    async def unlock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            await channel.set_permissions(
                interaction.guild.default_role, send_messages=None
            )
            await interaction.response.send_message(
                t("success","admin_chat_unlocked", channel=channel.mention), ephemeral=True
            )
            log_action(str(interaction.guild_id), interaction.user,
                        "admin_unlock", str(channel))
            await send_log(
                interaction.guild,
                t("embeds","log_chat_unlock","title"),
                t("embeds","log_chat_unlock","desc", channel=channel.mention),
                discord.Color.green(), interaction.user, moderator=interaction.user,
            )
        except Exception as e:
            await interaction.response.send_message(t("errors","admin_chat_error") + str(e), ephemeral=True)

    @discord.ui.button(label="🐌", style=discord.ButtonStyle.secondary, row=0)
    async def slowmode_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AdminSlowmodeModal(self.user_id, self.channel_id))

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger, row=0)
    async def purge_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(AdminPurgeModal(self.user_id, self.channel_id))

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        embed = discord.Embed(
            title=t("embeds","admin_panel","title"),
            description=t("embeds","admin_panel","desc"),
            color=discord.Color.blurple()
        )
        if interaction.guild.icon:
            embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=embed, view=AdminStartView(self.user_id))


class AdminSlowmodeModal(discord.ui.Modal):
    def __init__(self, user_id: int, channel_id: int):
        super().__init__(title=t("modals","admin_slowmode_title"))
        self.user_id    = user_id
        self.channel_id = channel_id
        self.f_seconds = discord.ui.TextInput(
            label=t("modals","admin_slowmode_label"),
            placeholder=t("modals","admin_slowmode_ph"),
            style=discord.TextStyle.short, required=True, max_length=6
        )
        self.add_item(self.f_seconds)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            seconds = int(self.f_seconds.value.strip())
            if not 0 <= seconds <= 21600:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                t("errors","admin_slowmode_invalid"), ephemeral=True
            )
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            await channel.edit(slowmode_delay=seconds)
            msg = t("success","admin_slowmode_off", channel=channel.mention) if seconds == 0                   else t("success","admin_slowmode_set", channel=channel.mention, seconds=seconds)
            await interaction.response.send_message(msg, ephemeral=True)
            log_action(str(interaction.guild_id), interaction.user,
                        "admin_slowmode", str(channel), str(seconds) + "s")
            await send_log(
                interaction.guild,
                t("embeds","log_slowmode","title"),
                t("embeds","log_slowmode","desc", channel=channel.mention, seconds=seconds),
                discord.Color.blurple(), interaction.user, moderator=interaction.user,
            )
        except Exception as e:
            await interaction.response.send_message(t("errors","admin_chat_error") + str(e), ephemeral=True)


class AdminPurgeModal(discord.ui.Modal):
    def __init__(self, user_id: int, channel_id: int):
        super().__init__(title=t("modals","admin_purge_title"))
        self.user_id    = user_id
        self.channel_id = channel_id
        self.f_count = discord.ui.TextInput(
            label=t("modals","admin_purge_label"),
            placeholder=t("modals","admin_purge_ph"),
            style=discord.TextStyle.short, required=True, max_length=4
        )
        self.add_item(self.f_count)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.f_count.value.strip())
            if not 1 <= count <= 1000:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                t("errors","admin_purge_invalid"), ephemeral=True
            )
        await interaction.response.defer(ephemeral=True)
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            deleted = await channel.purge(limit=count)
            await interaction.followup.send(
                t("success","admin_purge_done", channel=channel.mention, count=len(deleted)),
                ephemeral=True
            )
            log_action(str(interaction.guild_id), interaction.user,
                        "admin_purge", str(channel), str(len(deleted)) + " msgs")
            await send_log(
                interaction.guild,
                t("embeds","log_purge","title"),
                t("embeds","log_purge","desc", channel=channel.mention, count=len(deleted)),
                discord.Color.red(), interaction.user, moderator=interaction.user,
            )
        except Exception as e:
            await interaction.followup.send(t("errors","admin_chat_error") + str(e), ephemeral=True)


# ─────────────────────────────────────────────
#  EMBED GENERATOR
# ─────────────────────────────────────────────

_embed_gen_state: dict = {}  # user_id -> embed data dict


def _default_embed_state() -> dict:
    return {
        "title":        "",
        "description":  "",
        "color":        "5865F2",
        "author_name":  "",
        "author_icon":  "",
        "footer_text":  "",
        "footer_icon":  "",
        "image_url":    "",
        "thumbnail_url":"",
        "fields":       [],   # [{"name":str,"value":str,"inline":bool}]
        "timestamp":    False,
        "buttons":      [],   # [{"label":str,"url":str,"emoji":str}]
    }


def _build_preview_embed(state: dict) -> discord.Embed:
    color_hex = state.get("color", "5865F2")
    try:
        color = discord.Color(int(color_hex.lstrip("#"), 16))
    except (ValueError, TypeError):
        color = discord.Color.blurple()

    embed = discord.Embed(
        title       = state.get("title") or None,
        description = state.get("description") or None,
        color       = color,
        timestamp   = now_timestamp() if state.get("timestamp") else None
    )
    if state.get("author_name"):
        embed.set_author(name=state["author_name"], icon_url=state.get("author_icon") or None)
    if state.get("footer_text"):
        embed.set_footer(text=state["footer_text"], icon_url=state.get("footer_icon") or None)
    if state.get("image_url"):
        embed.set_image(url=state["image_url"])
    if state.get("thumbnail_url"):
        embed.set_thumbnail(url=state["thumbnail_url"])
    for field in state.get("fields", []):
        # Field images are added as separate image-only embeds when sending;
        # here we note them in the value with a link placeholder
        embed.add_field(
            name   = field.get("name", "\u200b"),
            value  = field.get("value", "\u200b") or "\u200b",
            inline = field.get("inline", False)
        )
    return embed


def _build_embed_gen_status(state: dict, guild) -> discord.Embed:
    color_hex = state.get("color", "5865F2")
    try:
        color = discord.Color(int(color_hex.lstrip("#"), 16))
    except (ValueError, TypeError):
        color = discord.Color.blurple()

    embed = discord.Embed(title=t("embeds","embed_gen","title"), color=color)
    lines = [
        t("embeds","embed_gen","f_title")      + " " + (state.get("title") or t("embeds","wizard","not_set")),
        t("embeds","embed_gen","f_desc")        + " " + ((state.get("description","")[:40] + "…") if len(state.get("description","")) > 40 else (state.get("description") or t("embeds","wizard","not_set"))),
        t("embeds","embed_gen","f_color")       + " #" + color_hex,
        t("embeds","embed_gen","f_author")      + " " + (state.get("author_name") or t("embeds","wizard","not_set")),
        t("embeds","embed_gen","f_footer")      + " " + (state.get("footer_text") or t("embeds","wizard","not_set")),
        t("embeds","embed_gen","f_image")       + " " + ("✅" if state.get("image_url") else "—"),
        t("embeds","embed_gen","f_thumbnail")   + " " + ("✅" if state.get("thumbnail_url") else "—"),
        t("embeds","embed_gen","f_timestamp")   + " " + ("✅" if state.get("timestamp") else "—"),
        t("embeds","embed_gen","f_fields")      + " " + str(len(state.get("fields", []))),
        t("embeds","embed_gen","f_comp_type")   + " " + (
            t("embeds","embed_gen","comp_type_btns") if state.get("component_type") == "buttons"
            else t("embeds","embed_gen","comp_type_dd") if state.get("component_type") == "dropdown"
            else t("embeds","wizard","not_set")
        ),
        t("embeds","embed_gen","f_buttons")     + " " + str(
            len(state.get("buttons", [])) if state.get("component_type") == "buttons"
            else len(state.get("dropdown_options", []))
        ),
    ]
    embed.add_field(name=t("embeds","embed_gen","f_settings"), value="\n".join(lines), inline=False)

    # Show fields list
    fields = state.get("fields", [])
    if fields:
        flines = []
        for i, f in enumerate(fields[:10]):
            inline_marker = " ↔️" if f.get("inline") else ""
            flines.append("**" + str(i+1) + ".** " + f.get("name","​")[:40] + inline_marker)
        if len(fields) > 10:
            flines.append(t("embeds","wizard","q_more", n=len(fields)-10))
        embed.add_field(name=t("embeds","embed_gen","f_fields_list"), value="\n".join(flines), inline=False)

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


async def _refresh_embed_gen(interaction: discord.Interaction, uid: int):
    orig = _wizard_interactions.get(uid)
    if orig:
        try:
            state = _embed_gen_state.get(uid, _default_embed_state())
            await orig.edit_original_response(
                embed=_build_embed_gen_status(state, interaction.guild),
                view=EmbedGenView(uid)
            )
        except Exception:
            pass


# ── Modals ────────────────────────────────────────────────────────────────────

class EmbedGenBaseModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals","embed_gen_base_title"))
        self.user_id = user_id
        state = _embed_gen_state.get(user_id, _default_embed_state())
        self.f_title = discord.ui.TextInput(label=t("modals","embed_gen_title_label"), placeholder=t("modals","embed_gen_title_ph"), default=state.get("title",""), style=discord.TextStyle.short, required=False, max_length=256)
        self.f_desc  = discord.ui.TextInput(label=t("modals","embed_gen_desc_label"),  placeholder=t("modals","embed_gen_desc_ph"),  default=state.get("description",""), style=discord.TextStyle.paragraph, required=False, max_length=4000)
        self.f_color = discord.ui.TextInput(label=t("modals","embed_gen_color_label"), placeholder=t("modals","embed_gen_color_ph"), default=state.get("color","5865F2"), style=discord.TextStyle.short, required=False, max_length=10)
        self.add_item(self.f_title); self.add_item(self.f_desc); self.add_item(self.f_color)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        color_raw = self.f_color.value.strip().lstrip("#") or "5865F2"
        try: int(color_raw, 16)
        except ValueError: color_raw = "5865F2"
        _embed_gen_state[uid].update({"title": self.f_title.value.strip(), "description": self.f_desc.value.strip(), "color": color_raw})
        await interaction.response.defer(ephemeral=True)
        await _refresh_embed_gen(interaction, uid)


class EmbedGenMediaModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals","embed_gen_media_title"))
        self.user_id = user_id
        state = _embed_gen_state.get(user_id, _default_embed_state())
        self.f_image = discord.ui.TextInput(label=t("modals","embed_gen_image_label"), placeholder=t("modals","embed_gen_url_ph"), default=state.get("image_url",""), style=discord.TextStyle.short, required=False, max_length=500)
        self.f_thumb = discord.ui.TextInput(label=t("modals","embed_gen_thumb_label"), placeholder=t("modals","embed_gen_url_ph"), default=state.get("thumbnail_url",""), style=discord.TextStyle.short, required=False, max_length=500)
        self.add_item(self.f_image); self.add_item(self.f_thumb)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        _embed_gen_state[uid].update({"image_url": self.f_image.value.strip(), "thumbnail_url": self.f_thumb.value.strip()})
        await interaction.response.defer(ephemeral=True)
        await _refresh_embed_gen(interaction, uid)


class EmbedGenAuthorFooterModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals","embed_gen_authorfooter_title"))
        self.user_id = user_id
        state = _embed_gen_state.get(user_id, _default_embed_state())
        self.f_aname = discord.ui.TextInput(label=t("modals","embed_gen_author_name_label"), placeholder=t("modals","embed_gen_author_ph"),      default=state.get("author_name",""),  style=discord.TextStyle.short, required=False, max_length=256)
        self.f_aicon = discord.ui.TextInput(label=t("modals","embed_gen_author_icon_label"), placeholder=t("modals","embed_gen_url_ph"),           default=state.get("author_icon",""),  style=discord.TextStyle.short, required=False, max_length=500)
        self.f_ftext = discord.ui.TextInput(label=t("modals","embed_gen_footer_label"),      placeholder=t("modals","embed_gen_footer_ph"),         default=state.get("footer_text",""),  style=discord.TextStyle.short, required=False, max_length=2048)
        self.f_ficon = discord.ui.TextInput(label=t("modals","embed_gen_footer_icon_label"), placeholder=t("modals","embed_gen_url_ph"),            default=state.get("footer_icon",""),  style=discord.TextStyle.short, required=False, max_length=500)
        self.add_item(self.f_aname); self.add_item(self.f_aicon); self.add_item(self.f_ftext); self.add_item(self.f_ficon)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        _embed_gen_state[uid].update({"author_name": self.f_aname.value.strip(), "author_icon": self.f_aicon.value.strip(), "footer_text": self.f_ftext.value.strip(), "footer_icon": self.f_ficon.value.strip()})
        await interaction.response.defer(ephemeral=True)
        await _refresh_embed_gen(interaction, uid)


class EmbedGenAddFieldModal(discord.ui.Modal):
    def __init__(self, user_id: int, edit_idx: int = -1):
        title_key = "embed_gen_field_edit_title" if edit_idx >= 0 else "embed_gen_field_title"
        super().__init__(title=t("modals", title_key))
        self.user_id  = user_id
        self.edit_idx = edit_idx
        # Pre-fill if editing
        existing = {}
        if edit_idx >= 0:
            fields = _embed_gen_state.get(user_id, {}).get("fields", [])
            existing = fields[edit_idx] if edit_idx < len(fields) else {}
        self.f_name   = discord.ui.TextInput(label=t("modals","embed_gen_field_name_label"),   placeholder=t("modals","embed_gen_field_name_ph"),   default=existing.get("name",""),  style=discord.TextStyle.short,     required=True,  max_length=256)
        self.f_value  = discord.ui.TextInput(label=t("modals","embed_gen_field_value_label"),  placeholder=t("modals","embed_gen_field_value_ph"),  default=existing.get("value",""), style=discord.TextStyle.paragraph, required=True,  max_length=1024)
        self.f_inline = discord.ui.TextInput(label=t("modals","embed_gen_field_inline_label"), placeholder="yes / no",                              default="yes" if existing.get("inline") else "no", style=discord.TextStyle.short, required=False, max_length=5)
        self.add_item(self.f_name); self.add_item(self.f_value); self.add_item(self.f_inline)

    async def on_submit(self, interaction: discord.Interaction):
        uid    = self.user_id
        fields = _embed_gen_state[uid].get("fields", [])
        if self.edit_idx < 0 and len(fields) >= 25:
            return await interaction.response.send_message(t("errors","embed_gen_max_fields"), ephemeral=True)
        inline = self.f_inline.value.strip().lower() in ("yes","y","ja","true","1")
        entry  = {"name": self.f_name.value.strip(), "value": self.f_value.value.strip(), "inline": inline}
        if self.edit_idx >= 0 and self.edit_idx < len(fields):
            fields[self.edit_idx] = entry
        else:
            fields.append(entry)
        _embed_gen_state[uid]["fields"] = fields
        await interaction.response.defer(ephemeral=True)
        await _refresh_embed_gen(interaction, uid)


class EmbedGenFieldSelect(discord.ui.Select):
    """Select a specific field to edit or delete."""
    def __init__(self, user_id: int, action: str):
        self.user_id = user_id
        self.action  = action  # "edit" or "delete"
        fields = _embed_gen_state.get(user_id, {}).get("fields", [])
        options = []
        for i, f in enumerate(fields[:25]):
            img = " 🖼️" if f.get("image_url") else ""
            options.append(discord.SelectOption(
                label=f.get("name","(empty)")[:90] + img,
                value=str(i),
                description=(f.get("value","")[:50] if f.get("value") else None)
            ))
        if not options:
            options.append(discord.SelectOption(label="—", value="__none__"))
        ph_key = "embed_gen_edit_field_ph" if action == "edit" else "embed_gen_delete_field_ph"
        super().__init__(placeholder=t("selects", ph_key), min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        if self.values[0] == "__none__":
            return await interaction.response.edit_message(content=t("errors","embed_gen_no_fields"), view=None)
        idx = int(self.values[0])
        if self.action == "edit":
            await interaction.response.send_modal(EmbedGenAddFieldModal(self.user_id, edit_idx=idx))
        else:
            fields = _embed_gen_state[self.user_id].get("fields", [])
            if idx < len(fields):
                fields.pop(idx)
            await interaction.response.edit_message(
                content=t("success","embed_gen_field_deleted"), view=None
            )
            await _refresh_embed_gen(interaction, self.user_id)


class EmbedGenAddButtonModal(discord.ui.Modal):
    """Add or edit a link button."""
    def __init__(self, user_id: int, edit_idx: int = -1):
        title_key = "embed_gen_btn_edit_title" if edit_idx >= 0 else "embed_gen_btn_add_title"
        super().__init__(title=t("modals", title_key))
        self.user_id  = user_id
        self.edit_idx = edit_idx
        existing = {}
        if edit_idx >= 0:
            btns = _embed_gen_state.get(user_id, {}).get("buttons", [])
            existing = btns[edit_idx] if edit_idx < len(btns) else {}
        self.f_label = discord.ui.TextInput(
            label=t("modals","embed_gen_btn_label_label"),
            placeholder=t("modals","embed_gen_btn_label_ph"),
            default=existing.get("label",""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.f_url = discord.ui.TextInput(
            label=t("modals","embed_gen_btn_url_label"),
            placeholder=t("modals","embed_gen_btn_url_ph"),
            default=existing.get("url",""),
            style=discord.TextStyle.short, required=True, max_length=512
        )
        self.f_emoji = discord.ui.TextInput(
            label=t("modals","embed_gen_btn_emoji_label"),
            placeholder=t("modals","embed_gen_btn_emoji_ph"),
            default=existing.get("emoji",""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.add_item(self.f_label)
        self.add_item(self.f_url)
        self.add_item(self.f_emoji)

    async def on_submit(self, interaction: discord.Interaction):
        uid   = self.user_id
        btns  = _embed_gen_state[uid].get("buttons", [])
        url   = self.f_url.value.strip()
        if not url.startswith("http"):
            url = "https://" + url
        entry = {
            "label": self.f_label.value.strip()[:80],
            "url":   url,
            "emoji": self.f_emoji.value.strip() or None,
        }
        if self.edit_idx >= 0 and self.edit_idx < len(btns):
            btns[self.edit_idx] = entry
        else:
            if len(btns) >= 5:
                return await interaction.response.send_message(
                    t("errors","embed_gen_max_buttons"), ephemeral=True
                )
            btns.append(entry)
        _embed_gen_state[uid]["buttons"] = btns
        await interaction.response.defer(ephemeral=True)
        await _refresh_embed_gen(interaction, uid)


class EmbedGenButtonSelect(discord.ui.Select):
    """Select a button to edit or delete."""
    def __init__(self, user_id: int, action: str):
        self.user_id = user_id
        self.action  = action
        btns = _embed_gen_state.get(user_id, {}).get("buttons", [])
        options = [
            discord.SelectOption(
                label=b.get("label","?")[:90],
                value=str(i),
                emoji=b.get("emoji") or None,
                description=b.get("url","")[:50]
            )
            for i, b in enumerate(btns[:25])
        ]
        if not options:
            options = [discord.SelectOption(label="—", value="__none__")]
        ph_key = "embed_gen_edit_btn_ph" if action == "edit" else "embed_gen_delete_btn_ph"
        super().__init__(placeholder=t("selects", ph_key), min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        if self.values[0] == "__none__":
            return await interaction.response.edit_message(content=t("errors","embed_gen_no_buttons"), view=None)
        idx = int(self.values[0])
        if self.action == "edit":
            await interaction.response.send_modal(EmbedGenAddButtonModal(self.user_id, edit_idx=idx))
        else:
            btns = _embed_gen_state[self.user_id].get("buttons", [])
            if idx < len(btns):
                btns.pop(idx)
            await interaction.response.edit_message(content=t("success","embed_gen_btn_deleted"), view=None)
            await _refresh_embed_gen(interaction, self.user_id)



class EmbedGenDropdownOptionSelect(discord.ui.Select):
    """Select a dropdown option to edit or delete."""
    def __init__(self, user_id: int, action: str):
        self.user_id = user_id
        self.action  = action
        opts = _embed_gen_state.get(user_id, {}).get("dropdown_options", [])
        options = [
            discord.SelectOption(
                label=o.get("label","?")[:90], value=str(i),
                emoji=o.get("emoji") or None,
                description=o.get("description","")[:50] if o.get("description") else None
            )
            for i, o in enumerate(opts[:25])
        ]
        if not options:
            options = [discord.SelectOption(label="—", value="__none__")]
        ph_key = "embed_gen_edit_dd_ph" if action == "edit" else "embed_gen_delete_dd_ph"
        super().__init__(placeholder=t("selects", ph_key), min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        if self.values[0] == "__none__":
            return await interaction.response.edit_message(content=t("errors","embed_gen_no_dd_options"), view=None)
        idx = int(self.values[0])
        if self.action == "edit":
            await interaction.response.send_modal(EmbedGenAddDropdownOptionModal(self.user_id, edit_idx=idx))
        else:
            opts = _embed_gen_state[self.user_id].get("dropdown_options", [])
            if idx < len(opts):
                opts.pop(idx)
            await interaction.response.edit_message(content=t("success","embed_gen_dd_option_deleted"), view=None)
            await _refresh_embed_gen(interaction, self.user_id)


class EmbedGenSendModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals","embed_gen_send_title"))
        self.user_id = user_id
        self.f_channel = discord.ui.TextInput(label=t("modals","embed_gen_send_channel_label"), placeholder=t("modals","embed_gen_send_channel_ph"), style=discord.TextStyle.short, required=True, max_length=100)
        self.add_item(self.f_channel)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        raw = self.f_channel.value.strip()
        channel = None
        raw_id  = raw.strip("<#>")
        if raw_id.isdigit():
            channel = interaction.guild.get_channel(int(raw_id))
        if not channel:
            channel = discord.utils.find(lambda c: c.name.lower() == raw.lstrip("#").lower(), interaction.guild.text_channels)
        if not channel:
            return await interaction.response.send_message(t("errors","setup_channel_not_found"), ephemeral=True)
        state = _embed_gen_state.pop(uid, _default_embed_state())
        try:
            await _send_embed_with_field_images(channel, state,
                guild_id=str(interaction.guild_id), actor=interaction.user)
            await interaction.response.send_message(t("success","embed_gen_sent", channel=channel.mention), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(t("errors","generic_error", error=str(e)), ephemeral=True)


def _build_button_view(state: dict) -> discord.ui.View:
    """Build a View with link buttons OR a select dropdown from state."""
    comp_type = state.get("component_type", "buttons")

    if comp_type == "dropdown":
        opts = state.get("dropdown_options", [])
        if not opts:
            return None
        options = []
        for o in opts[:25]:
            options.append(discord.SelectOption(
                label=o.get("label","Option")[:100],
                value=o.get("label","Option")[:100],
                description=o.get("description","")[:100] if o.get("description") else None,
                emoji=o.get("emoji") or None,
            ))
        if not options:
            return None
        select = discord.ui.Select(
            placeholder=state.get("dropdown_placeholder") or t("selects","embed_gen_dd_placeholder"),
            min_values=1, max_values=1, options=options
        )
        async def _noop(interaction: discord.Interaction):
            url = next((o.get("url") for o in opts if o.get("label") == select.values[0]), None)
            if url:
                await interaction.response.send_message(url, ephemeral=True)
            else:
                await interaction.response.send_message(
                    t("success","embed_gen_dd_selected", value=select.values[0]), ephemeral=True
                )
        select.callback = _noop
        v = discord.ui.View(timeout=None)
        v.add_item(select)
        return v

    # Link buttons
    btns = state.get("buttons", [])
    if not btns:
        return None
    view = discord.ui.View(timeout=None)
    for b in btns[:5]:
        url   = b.get("url","https://discord.com")
        label = b.get("label","Link")[:80]
        emoji = b.get("emoji") or None
        try:
            btn = discord.ui.Button(
                label=label, url=url, emoji=emoji,
                style=discord.ButtonStyle.link
            )
            view.add_item(btn)
        except Exception:
            pass
    return view if view.children else None


async def _send_embed_with_field_images(channel, state: dict,
                                        guild_id: str = None, actor = None):
    """Send the embed with optional link buttons."""
    embed    = _build_preview_embed(state)
    btn_view = _build_button_view(state)
    msg = await channel.send(embed=embed, view=btn_view)
    if guild_id and actor:
        payload = dict(state)
        payload["sent_channel_id"] = channel.id
        payload["message_id"]      = msg.id
        log_action(guild_id, actor, "embed_sent",
                   "#" + channel.name, state.get("title","(no title)"),
                   payload=payload)
    return msg


# ── Main View ─────────────────────────────────────────────────────────────────

class EmbedGenComponentTypeView(discord.ui.View):
    """Choose: link buttons or select dropdown."""
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.link_btn.label     = t("buttons","embed_gen_comp_link_btns")
        self.dropdown_btn.label = t("buttons","embed_gen_comp_dropdown")
        self.back_btn.label     = t("buttons","delete_wizard_back")

    def _check(self, i): return i.user.id == self.user_id

    @discord.ui.button(label="🔗", style=discord.ButtonStyle.blurple, row=0)
    async def link_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        _embed_gen_state[self.user_id]["component_type"] = "buttons"
        await interaction.response.send_modal(EmbedGenAddButtonModal(self.user_id))

    @discord.ui.button(label="📋", style=discord.ButtonStyle.secondary, row=0)
    async def dropdown_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        _embed_gen_state[self.user_id]["component_type"] = "dropdown"
        await interaction.response.send_modal(EmbedGenAddDropdownOptionModal(self.user_id))

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary, row=0)
    async def back_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        orig = _wizard_interactions.get(self.user_id)
        if orig:
            state = _embed_gen_state.get(self.user_id, _default_embed_state())
            try:
                await orig.edit_original_response(
                    embed=_build_embed_gen_status(state, interaction.guild),
                    view=EmbedGenView(self.user_id)
                )
            except Exception:
                pass


class EmbedGenAddDropdownOptionModal(discord.ui.Modal):
    def __init__(self, user_id: int, edit_idx: int = -1):
        title_key = "embed_gen_dd_edit_title" if edit_idx >= 0 else "embed_gen_dd_add_title"
        super().__init__(title=t("modals", title_key))
        self.user_id  = user_id
        self.edit_idx = edit_idx
        existing = {}
        if edit_idx >= 0:
            opts = _embed_gen_state.get(user_id, {}).get("dropdown_options", [])
            existing = opts[edit_idx] if edit_idx < len(opts) else {}
        self.f_label = discord.ui.TextInput(
            label=t("modals","embed_gen_dd_label_label"), placeholder=t("modals","embed_gen_dd_label_ph"),
            default=existing.get("label",""), style=discord.TextStyle.short, required=True, max_length=100
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals","embed_gen_dd_desc_label"), placeholder=t("modals","embed_gen_dd_desc_ph"),
            default=existing.get("description",""), style=discord.TextStyle.short, required=False, max_length=100
        )
        self.f_emoji = discord.ui.TextInput(
            label=t("modals","embed_gen_btn_emoji_label"), placeholder=t("modals","embed_gen_btn_emoji_ph"),
            default=existing.get("emoji",""), style=discord.TextStyle.short, required=False, max_length=10
        )
        self.add_item(self.f_label)
        self.add_item(self.f_desc)
        self.add_item(self.f_emoji)

    async def on_submit(self, interaction: discord.Interaction):
        uid  = self.user_id
        opts = _embed_gen_state[uid].setdefault("dropdown_options", [])
        entry = {
            "label":       self.f_label.value.strip()[:100],
            "description": self.f_desc.value.strip()[:100] or None,
            "emoji":       self.f_emoji.value.strip() or None,
        }
        if self.edit_idx >= 0 and self.edit_idx < len(opts):
            opts[self.edit_idx] = entry
        else:
            if len(opts) >= 25:
                return await interaction.response.send_message(t("errors","embed_gen_max_dd_options"), ephemeral=True)
            opts.append(entry)
        _embed_gen_state[uid]["component_type"] = "dropdown"
        await interaction.response.defer(ephemeral=True)
        await _refresh_embed_gen(interaction, uid)


class EmbedGenView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id   = user_id
        state          = _embed_gen_state.get(user_id, {})
        has_fields     = bool(state.get("fields"))
        comp_type      = state.get("component_type")
        has_comps      = bool(
            state.get("buttons") if comp_type == "buttons"
            else state.get("dropdown_options") if comp_type == "dropdown"
            else False
        )
        # Row 0 labels
        self.base_btn.label         = t("buttons","embed_gen_base")
        self.media_btn.label        = t("buttons","embed_gen_media")
        self.authorfooter_btn.label = t("buttons","embed_gen_authorfooter")
        self.timestamp_btn.label    = (t("buttons","embed_gen_timestamp_off")
                                       if state.get("timestamp")
                                       else t("buttons","embed_gen_timestamp_on"))
        # Row 1 labels
        self.add_field_btn.label    = t("buttons","embed_gen_add_field")
        self.edit_field_btn.label   = t("buttons","embed_gen_edit_field")
        self.delete_field_btn.label = t("buttons","embed_gen_delete_field")
        self.edit_field_btn.disabled   = not has_fields
        self.delete_field_btn.disabled = not has_fields
        # Row 2 labels
        self.add_comp_btn.label    = t("buttons","embed_gen_add_comp")
        self.edit_comp_btn.label   = (t("buttons","embed_gen_edit_btn")
                                      if comp_type != "dropdown"
                                      else t("buttons","embed_gen_edit_dd_option"))
        self.delete_comp_btn.label = (t("buttons","embed_gen_delete_btn")
                                      if comp_type != "dropdown"
                                      else t("buttons","embed_gen_delete_dd_option"))
        self.edit_comp_btn.disabled   = not has_comps
        self.delete_comp_btn.disabled = not has_comps
        # Row 3 labels
        self.preview_btn.label      = t("buttons","wizard_preview")
        self.send_channel_btn.label = t("buttons","embed_gen_send_channel")
        self.send_here_btn.label    = t("buttons","embed_gen_send_here")
        self.cancel_btn.label       = t("buttons","wizard_cancel")

    def _check(self, i): return i.user.id == self.user_id

    # ── Row 0 ─────────────────────────────────────────────────────────────────
    @discord.ui.button(label="✏️", style=discord.ButtonStyle.blurple, row=0)
    async def base_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EmbedGenBaseModal(self.user_id))

    @discord.ui.button(label="🖼️", style=discord.ButtonStyle.secondary, row=0)
    async def media_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EmbedGenMediaModal(self.user_id))

    @discord.ui.button(label="👤", style=discord.ButtonStyle.secondary, row=0)
    async def authorfooter_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EmbedGenAuthorFooterModal(self.user_id))

    @discord.ui.button(label="⏱️", style=discord.ButtonStyle.secondary, row=0)
    async def timestamp_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        state = _embed_gen_state.get(self.user_id, {})
        state["timestamp"] = not state.get("timestamp", False)
        await interaction.response.defer(ephemeral=True)
        await _refresh_embed_gen(interaction, self.user_id)

    # ── Row 1 ─────────────────────────────────────────────────────────────────
    @discord.ui.button(label="➕", style=discord.ButtonStyle.secondary, row=1)
    async def add_field_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EmbedGenAddFieldModal(self.user_id))

    @discord.ui.button(label="✏️", style=discord.ButtonStyle.secondary, row=1)
    async def edit_field_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        v = discord.ui.View(timeout=120)
        v.add_item(EmbedGenFieldSelect(self.user_id, "edit"))
        await interaction.response.send_message(content=t("success","embed_gen_pick_field_edit"), view=v, ephemeral=True)

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def delete_field_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        v = discord.ui.View(timeout=120)
        v.add_item(EmbedGenFieldSelect(self.user_id, "delete"))
        await interaction.response.send_message(content=t("success","embed_gen_pick_field_delete"), view=v, ephemeral=True)

    # ── Row 2 — Components ────────────────────────────────────────────────────
    @discord.ui.button(label="🔗", style=discord.ButtonStyle.blurple, row=2)
    async def add_comp_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        state     = _embed_gen_state.get(self.user_id, {})
        comp_type = state.get("component_type")
        if comp_type == "buttons":
            await interaction.response.send_modal(EmbedGenAddButtonModal(self.user_id))
        elif comp_type == "dropdown":
            await interaction.response.send_modal(EmbedGenAddDropdownOptionModal(self.user_id))
        else:
            comp_embed = discord.Embed(
                title=t("embeds","embed_gen","comp_choose_title"),
                description=t("embeds","embed_gen","comp_choose_desc"),
                color=discord.Color.blurple()
            )
            await interaction.response.send_message(
                embed=comp_embed, view=EmbedGenComponentTypeView(self.user_id), ephemeral=True
            )

    @discord.ui.button(label="✏️", style=discord.ButtonStyle.secondary, row=2)
    async def edit_comp_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        state     = _embed_gen_state.get(self.user_id, {})
        comp_type = state.get("component_type", "buttons")
        v = discord.ui.View(timeout=120)
        v.add_item(EmbedGenDropdownOptionSelect(self.user_id, "edit") if comp_type == "dropdown"
                   else EmbedGenButtonSelect(self.user_id, "edit"))
        await interaction.response.send_message(content=t("success","embed_gen_pick_btn_edit"), view=v, ephemeral=True)

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger, row=2)
    async def delete_comp_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        state     = _embed_gen_state.get(self.user_id, {})
        comp_type = state.get("component_type", "buttons")
        v = discord.ui.View(timeout=120)
        v.add_item(EmbedGenDropdownOptionSelect(self.user_id, "delete") if comp_type == "dropdown"
                   else EmbedGenButtonSelect(self.user_id, "delete"))
        await interaction.response.send_message(content=t("success","embed_gen_pick_btn_delete"), view=v, ephemeral=True)

    # ── Row 3 — Send/Preview/Cancel ───────────────────────────────────────────
    @discord.ui.button(label="👁️", style=discord.ButtonStyle.secondary, row=3)
    async def preview_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        state = _embed_gen_state.get(self.user_id, _default_embed_state())
        try:
            preview  = _build_preview_embed(state)
            btn_view = _build_button_view(state)
            await interaction.response.send_message(
                content=t("success","wizard_preview_note_embed"),
                embed=preview, view=btn_view, ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(t("errors","generic_error", error=str(e)), ephemeral=True)

    @discord.ui.button(label="📤", style=discord.ButtonStyle.green, row=3)
    async def send_channel_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(EmbedGenSendModal(self.user_id))

    @discord.ui.button(label="📨", style=discord.ButtonStyle.green, row=3)
    async def send_here_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        state = _embed_gen_state.pop(self.user_id, _default_embed_state())
        try:
            await _send_embed_with_field_images(interaction.channel, state,
                guild_id=str(interaction.guild_id), actor=interaction.user)
            await interaction.response.edit_message(
                content=t("success","embed_gen_sent", channel=interaction.channel.mention),
                embed=None, view=None
            )
        except Exception as e:
            await interaction.response.send_message(t("errors","generic_error", error=str(e)), ephemeral=True)

    @discord.ui.button(label="✖️", style=discord.ButtonStyle.secondary, row=3)
    async def cancel_btn(self, interaction, button):
        if not self._check(interaction): return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        _embed_gen_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors","application_cancelled"), embed=None, view=None)

# ─────────────────────────────────────────────
#  AUDIT LOG (SQLite)
# ─────────────────────────────────────────────
import sqlite3 as _sqlite3
import threading as _threading

_db_lock = _threading.Lock()
AUDIT_DB = os.path.join(CONFIGS_DIR, "audit_log.db")

def _db_conn():
    conn = _sqlite3.connect(AUDIT_DB, check_same_thread=False)
    conn.row_factory = _sqlite3.Row
    return conn

def _init_db():
    with _db_lock:
        conn = _db_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL,
                actor_id    TEXT    NOT NULL,
                actor_name  TEXT    NOT NULL,
                action      TEXT    NOT NULL,
                target      TEXT,
                detail      TEXT,
                payload     TEXT
            )
        """)
        # Migrate: add payload column if it doesn't exist yet
        try:
            conn.execute("ALTER TABLE audit_log ADD COLUMN payload TEXT")
        except Exception:
            pass
        conn.commit()
        conn.close()

def log_action(guild_id: str, actor: object, action: str,
               target: str = None, detail: str = None, payload: dict = None):
    """Write an audit entry. payload is stored as JSON for rich detail view."""
    import datetime as _dt, json as _json
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    actor_id   = str(getattr(actor, "id",   actor))
    actor_name = str(getattr(actor, "display_name", actor))
    payload_str = _json.dumps(payload, ensure_ascii=False) if payload else None
    with _db_lock:
        conn = _db_conn()
        conn.execute(
            "INSERT INTO audit_log "
            "(guild_id,timestamp,actor_id,actor_name,action,target,detail,payload) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (guild_id, ts, actor_id, actor_name, action, target, detail, payload_str)
        )
        conn.commit()
        conn.close()

def query_log(guild_id: str, limit: int = 25, action_filter: str = None,
              user_id: str = None, date_filter: str = None) -> list:
    """
    Query audit log with optional filters.
    action_filter : partial match on action (e.g. "ban")
    user_id       : exact match on actor_id
    date_filter   : partial match on timestamp (e.g. "2026-03" for March 2026)
    """
    where  = "WHERE guild_id=?"
    params = [guild_id]
    if action_filter:
        where += " AND action LIKE ?"
        params.append("%" + action_filter + "%")
    if user_id:
        where += " AND actor_id=?"
        params.append(user_id)
    if date_filter:
        where += " AND timestamp LIKE ?"
        params.append("%" + date_filter + "%")
    with _db_lock:
        conn = _db_conn()
        rows = conn.execute(
            "SELECT * FROM audit_log " + where + " ORDER BY id DESC LIMIT ?",
            params + [limit]
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def count_log(guild_id: str, action_filter: str = None,
              user_id: str = None, date_filter: str = None) -> int:
    """Return total matching rows (without limit) for pagination."""
    where  = "WHERE guild_id=?"
    params = [guild_id]
    if action_filter:
        where += " AND action LIKE ?"
        params.append("%" + action_filter + "%")
    if user_id:
        where += " AND actor_id=?"
        params.append(user_id)
    if date_filter:
        where += " AND timestamp LIKE ?"
        params.append("%" + date_filter + "%")
    with _db_lock:
        conn = _db_conn()
        n = conn.execute(
            "SELECT COUNT(*) FROM audit_log " + where, params
        ).fetchone()[0]
        conn.close()
    return n

_init_db()


def _query_log_page(guild_id: str, limit: int, page: int,
                    action_filter: str = None, user_id: str = None,
                    date_filter: str = None) -> list:
    where  = "WHERE guild_id=?"
    params = [guild_id]
    if action_filter:
        where += " AND action LIKE ?"
        params.append("%" + action_filter + "%")
    if user_id:
        where += " AND actor_id=?"
        params.append(user_id)
    if date_filter:
        where += " AND timestamp LIKE ?"
        params.append("%" + date_filter + "%")
    offset = page * limit
    with _db_lock:
        conn = _db_conn()
        rows = conn.execute(
            "SELECT * FROM audit_log " + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  HISTORY PAGINATION VIEW
# ─────────────────────────────────────────────

ACTION_EMOJIS = {
    "ban":             "🔨", "kick":            "👢",
    "timeout":         "⏳", "warn":             "⚠️",
    "warn_edit":       "✏️", "config_export":   "📥",
    "config_import":   "📤", "config_rollback":  "↩️",
    "language":        "🌐", "music_upload":    "🎵",
    "music_download":  "🎵", "setup":            "⚙️",
    "setup_tickets":   "🎫", "setup_verify":     "✅",
    "setup_selfroles": "🎭", "setup_application":"📋",
    "setup_log":       "📋", "setup_welcome":    "👋",
    "setup_waiting":   "🎵", "setup_join":       "🚪",
    "setup_status":    "⚙️", "setup_language":   "🌐",
    "whitelist":       "🛡️", "userinfo":         "👤",
    "embed_create":    "🎨", "ticket_edit":      "🎫",
    "delete":          "🗑️", "edit":             "✏️",
    "pioneer":         "🏆", "admin_timeout":    "⏳",
    "admin_warn":      "⚠️", "admin_kick":       "👢",
    "admin_ban":       "🔨", "selfrole_list":    "🎭",
    "history":         "📋",
    "admin_timeout":       "⏳", "admin_timeout_remove": "✅",
    "admin_warn":          "⚠️", "admin_kick":           "👢",
    "admin_ban":           "🔨", "admin_lock":           "🔒",
    "admin_unlock":        "🔓", "admin_slowmode":       "🐌",
    "admin_purge":         "🗑️",
}

# Grouped for the category dropdown
ACTION_CATEGORIES = [
    ("⚔️", "moderation",  ["ban","kick","timeout","warn","warn_edit",
                            "admin_ban","admin_kick","admin_warn","admin_timeout",
                            "admin_timeout_remove","admin_lock","admin_unlock",
                            "admin_slowmode","admin_purge"]),
    ("⚙️", "setup",       ["setup","setup_tickets","setup_verify","setup_selfroles","setup_application",
                            "setup_log","setup_welcome","setup_waiting","setup_join","setup_status","setup_language"]),
    ("📦", "config",      ["config_export","config_import","config_rollback"]),
    ("🔧", "tools",       ["whitelist","embed_create","ticket_edit","edit","delete","pioneer","userinfo","language"]),
    ("🎵", "music",       ["music_upload","music_download"]),
]

PAGE_SIZE = 8   # slightly fewer so lines fit better in one embed field


def _build_history_embed(guild, rows: list, page: int, total: int,
                          filters: dict) -> discord.Embed:
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    # ── Color by active filter state ──────────────────────────────────────────
    has_filter = any(filters.get(k) for k in ("action", "user_id", "date", "category"))
    color = discord.Color.gold() if has_filter else discord.Color.blurple()

    embed = discord.Embed(color=color, timestamp=now_timestamp())
    embed.title = t("embeds", "history", "title")

    # ── Active filters pill bar in description ────────────────────────────────
    pills = []
    if filters.get("category"):
        emoji = next((e for e,k,_ in ACTION_CATEGORIES if k == filters["category"]), "📂")
        pills.append(emoji + " `" + filters["category"] + "`")
    if filters.get("action"):
        em = ACTION_EMOJIS.get(filters["action"], "📋")
        pills.append(em + " `" + filters["action"] + "`")
    if filters.get("user_id"):
        pills.append("👤 <@" + filters["user_id"] + ">")
    if filters.get("date"):
        pills.append("📅 `" + filters["date"] + "`")

    if pills:
        embed.description = (
            t("embeds","history","active_filters") + "  " + "  ·  ".join(pills) + "\n"
            + t("embeds","history","filter_hint")
        )

    # ── Entries ───────────────────────────────────────────────────────────────
    if rows:
        field_lines = []
        for row in rows:
            emoji  = ACTION_EMOJIS.get(row["action"], "📋")
            actor  = "<@" + row["actor_id"] + ">"
            target = (" \u2192 `" + str(row["target"])[:25] + "`") if row["target"] else ""
            detail = (" \u2014 *" + str(row["detail"])[:28] + "*") if row["detail"] else ""
            ts     = discord.utils.format_dt(
                __import__("datetime").datetime.strptime(
                    row["timestamp"], "%Y-%m-%d %H:%M:%S UTC"
                ).replace(tzinfo=__import__("datetime").timezone.utc),
                style="t"
            ) if False else ("`" + row["timestamp"][5:16] + "`")
            field_lines.append(
                ts + "  " + emoji + " **" + row["action"] + "**"
                + "  " + actor + target + detail
            )
        embed.add_field(
            name=t("embeds","history","f_entries")
                 + " (" + str(page * PAGE_SIZE + 1) + "\u2013"
                 + str(page * PAGE_SIZE + len(rows)) + ")",
            value="\n".join(field_lines),
            inline=False
        )
    else:
        embed.add_field(
            name=t("embeds","history","f_entries"),
            value="> " + t("errors","history_empty"),
            inline=False
        )

    # ── Stats bar ─────────────────────────────────────────────────────────────
    embed.add_field(
        name=t("embeds","history","f_stats"),
        value=(
            t("embeds","history","stat_total",   n=total)     + "\n"
            + t("embeds","history","stat_page",  page=page+1, total=total_pages) + "\n"
            + t("embeds","history","stat_filter",
               status=t("embeds","history","filter_active") if has_filter
                      else t("embeds","history","filter_none"))
        ),
        inline=True
    )

    if guild and guild.icon:
        embed.set_footer(
            text=t("embeds","history","footer", guild=guild.name),
            icon_url=guild.icon.url
        )
    else:
        embed.set_footer(text=t("embeds","history","footer", guild=guild.name if guild else "Bot"))
    return embed


def _build_detail_embed(row: dict, guild) -> discord.Embed:
    """Rich detail embed for a single log entry."""
    import json as _json
    emoji = ACTION_EMOJIS.get(row["action"], "\U0001f4cb")
    embed = discord.Embed(
        title=emoji + "  " + t("embeds","history","detail_title") + " " + row["action"],
        color=discord.Color.blurple(),
        timestamp=now_timestamp()
    )
    embed.add_field(name=t("embeds","history","detail_time"),
                    value="`" + row["timestamp"] + "`", inline=True)
    embed.add_field(name=t("embeds","history","detail_actor"),
                    value="<@" + row["actor_id"] + ">", inline=True)
    if row.get("target"):
        embed.add_field(name=t("embeds","history","detail_target"),
                        value="`" + str(row["target"])[:100] + "`", inline=True)
    if row.get("detail"):
        embed.add_field(name=t("embeds","history","detail_info"),
                        value=str(row["detail"])[:1024], inline=False)
    payload = {}
    if row.get("payload"):
        try:
            payload = _json.loads(row["payload"])
        except Exception:
            pass
    action = row["action"]
    if action in ("ban","kick","warn","timeout","warn_edit",
                  "admin_ban","admin_kick","admin_warn","admin_timeout","admin_timeout_remove"):
        uid  = payload.get("user_id")
        name = payload.get("user_name","?")
        av   = payload.get("avatar")
        if uid:
            embed.add_field(name=t("embeds","history","detail_user"),
                            value="<@" + str(uid) + ">  `" + name + "`", inline=False)
        if av:
            embed.set_thumbnail(url=av)
        if payload.get("count"):
            embed.add_field(name=t("embeds","history","detail_warn_count"),
                            value="\u26a0\ufe0f `" + str(payload["count"]) + "`", inline=True)
        if payload.get("minutes"):
            embed.add_field(name=t("embeds","history","detail_duration"),
                            value="`" + str(payload["minutes"]) + " min`", inline=True)
        if payload.get("reason"):
            embed.add_field(name=t("embeds","history","detail_reason"),
                            value=payload["reason"][:512], inline=False)
    elif action == "embed_sent":
        ch_id  = payload.get("sent_channel_id")
        msg_id = payload.get("message_id")
        if ch_id and msg_id:
            embed.add_field(
                name=t("embeds","history","detail_embed_link"),
                value="[" + t("embeds","history","detail_embed_jump") + "](https://discord.com/channels/"
                      + str(row["guild_id"]) + "/" + str(ch_id) + "/" + str(msg_id) + ")",
                inline=False
            )
        if payload.get("title") or payload.get("description"):
            no_val = "\u2014"
            embed.add_field(
                name=t("embeds","history","detail_embed_preview"),
                value=(
                    "**" + t("embeds","embed_gen","f_title")   + "** " + (payload.get("title") or no_val) + "\n"
                    + "**" + t("embeds","embed_gen","f_color") + "** #" + payload.get("color","5865F2") + "\n"
                    + "**" + t("embeds","embed_gen","f_fields") + "** " + str(len(payload.get("fields",[])))
                ),
                inline=False
            )
        if payload.get("image_url"):
            embed.set_image(url=payload["image_url"])
        elif payload.get("thumbnail_url"):
            embed.set_thumbnail(url=payload["thumbnail_url"])
    elif action in ("config_import","config_export","config_rollback"):
        if row.get("detail"):
            embed.add_field(name=t("embeds","history","detail_summary"),
                            value="`" + str(row["detail"]) + "`", inline=False)
    elif action == "whitelist":
        embed.add_field(name=t("embeds","history","detail_domain"),
                        value="`" + str(row.get("target","?")) + "`", inline=True)
        embed.add_field(name=t("embeds","history","detail_operation"),
                        value=str(row.get("detail","")), inline=True)
    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed


class HistoryDetailSelect(discord.ui.Select):
    """Dropdown to pick a log entry and see its full detail."""
    def __init__(self, parent_view: "HistoryView", rows: list):
        self.parent_view = parent_view
        options = []
        for row in rows[:25]:
            emoji = ACTION_EMOJIS.get(row["action"], "\U0001f4cb")
            ts    = row["timestamp"][5:16]
            label = (ts + "  " + row["action"])[:100]
            desc  = (str(row.get("target") or "")[:50] or str(row.get("detail") or "")[:50]) or None
            options.append(discord.SelectOption(
                label=label, value=str(row["id"]),
                emoji=emoji, description=desc
            ))
        if not options:
            options = [discord.SelectOption(label="\u2014", value="__none__")]
        super().__init__(
            placeholder=t("selects","history_detail_ph"),
            min_values=1, max_values=1,
            options=options, row=2
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "__none__":
            return await interaction.response.send_message(t("errors","history_empty"), ephemeral=True)
        import json as _json2
        entry_id = int(self.values[0])
        with _db_lock:
            conn = _db_conn()
            row  = conn.execute("SELECT * FROM audit_log WHERE id=?", (entry_id,)).fetchone()
            conn.close()
        if not row:
            return await interaction.response.send_message(t("errors","history_empty"), ephemeral=True)
        row = dict(row)
        detail_embed = _build_detail_embed(row, interaction.guild)

        # For embed_sent: reconstruct and send the original embed as a second embed
        extra_embeds = []
        extra_view   = None
        if row.get("action") == "embed_sent" and row.get("payload"):
            try:
                payload = _json2.loads(row["payload"])
                reconstructed = _build_preview_embed(payload)
                extra_embeds.append(reconstructed)
                extra_view = _build_button_view(payload)
            except Exception:
                pass

        await interaction.response.send_message(
            embeds=[detail_embed] + extra_embeds,
            view=extra_view,
            ephemeral=True
        )



class HistoryActionSelect(discord.ui.Select):
    """Category → then specific actions dropdown."""
    def __init__(self, parent_view: "HistoryView", mode: str = "category"):
        self.parent_view = parent_view
        self.mode        = mode  # "category" or action group key

        if mode == "category":
            options = [
                discord.SelectOption(
                    label=t("selects","history_cat_" + key),
                    value=key, emoji=emoji,
                    description=t("selects","history_cat_" + key + "_desc")
                )
                for emoji, key, _ in ACTION_CATEGORIES
            ]
            options.insert(0, discord.SelectOption(
                label=t("selects","history_cat_all"),
                value="__all__", emoji="📋"
            ))
            ph = t("selects","history_category_ph")
        else:
            # Specific actions for a given category
            actions = next(
                (acts for _, key, acts in ACTION_CATEGORIES if key == mode),
                list(ACTION_EMOJIS.keys())
            )
            options = [
                discord.SelectOption(
                    label=act, value=act,
                    emoji=ACTION_EMOJIS.get(act, "📋"),
                    default=(parent_view.filters.get("action") == act)
                )
                for act in actions[:25]
            ]
            options.insert(0, discord.SelectOption(
                label=t("selects","history_action_all"),
                value="__all__", emoji="📋"
            ))
            ph = t("selects","history_action_ph")

        super().__init__(placeholder=ph, min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if self.mode == "category":
            if val == "__all__":
                # Clear category and action filters
                self.parent_view.filters["category"] = None
                self.parent_view.filters["action"]   = None
                # Remove the action select if present, rebuild with category select
                self.parent_view.clear_items()
                self.parent_view._rebuild_components()
            else:
                # Show action select for this category
                self.parent_view.filters["category"] = val
                self.parent_view.filters["action"]   = None
                self.parent_view.clear_items()
                self.parent_view._rebuild_components(action_group=val)
        else:
            # Specific action selected
            if val == "__all__":
                self.parent_view.filters["action"] = None
            else:
                self.parent_view.filters["action"] = val
            self.parent_view.clear_items()
            self.parent_view._rebuild_components(action_group=self.mode)

        self.parent_view.page  = 0
        self.parent_view.total = count_log(
            self.parent_view.guild_id,
            self.parent_view.filters.get("action"),
            self.parent_view.filters.get("user_id"),
            self.parent_view.filters.get("date"),
        )
        rows  = self.parent_view._load_page()
        total_pages = max(1, (self.parent_view.total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.parent_view.prev_btn.disabled = True
        self.parent_view.next_btn.disabled = self.parent_view.page >= total_pages - 1
        embed = _build_history_embed(
            interaction.guild, rows, self.parent_view.page,
            self.parent_view.total, self.parent_view.filters
        )
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class HistoryView(discord.ui.View):
    def __init__(self, guild, guild_id: str, page: int, total: int,
                 filters: dict, action_group: str = None):
        super().__init__(timeout=300)
        self.guild        = guild
        self.guild_id     = guild_id
        self.page         = page
        self.total        = total
        self.filters      = filters
        self.action_group = action_group
        self._rebuild_components(action_group=action_group)

    def _rebuild_components(self, action_group: str = None):
        """Re-add all buttons and selects. Call after clear_items()."""
        self.action_group = action_group
        total_pages = max(1, (self.total + PAGE_SIZE - 1) // PAGE_SIZE)

        # Row 0 — navigation buttons
        self.prev_btn = discord.ui.Button(
            label=t("buttons","history_prev"), style=discord.ButtonStyle.secondary,
            disabled=(self.page == 0), row=0
        )
        self.next_btn = discord.ui.Button(
            label=t("buttons","history_next"), style=discord.ButtonStyle.secondary,
            disabled=(self.page >= total_pages - 1), row=0
        )
        self.filter_btn = discord.ui.Button(
            label=t("buttons","history_filter"), style=discord.ButtonStyle.blurple, row=0
        )
        self.reset_btn = discord.ui.Button(
            label=t("buttons","history_reset"),
            style=discord.ButtonStyle.danger,
            disabled=not any(self.filters.get(k) for k in ("action","user_id","date","category")),
            row=0
        )

        async def _prev(interaction: discord.Interaction):
            self.page = max(0, self.page - 1)
            await self._update(interaction)
        async def _next(interaction: discord.Interaction):
            tp = max(1, (self.total + PAGE_SIZE - 1) // PAGE_SIZE)
            self.page = min(tp - 1, self.page + 1)
            await self._update(interaction)
        async def _filter(interaction: discord.Interaction):
            await interaction.response.send_modal(HistoryFilterModal(self))
        async def _reset(interaction: discord.Interaction):
            self.filters   = {}
            self.action_group = None
            self.page      = 0
            self.total     = count_log(self.guild_id)
            self.clear_items()
            self._rebuild_components()
            rows  = self._load_page()
            embed = _build_history_embed(self.guild, rows, self.page, self.total, self.filters)
            await interaction.response.edit_message(embed=embed, view=self)

        self.prev_btn.callback   = _prev
        self.next_btn.callback   = _next
        self.filter_btn.callback = _filter
        self.reset_btn.callback  = _reset

        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)
        self.add_item(self.filter_btn)
        self.add_item(self.reset_btn)

        # Row 1 — category/action dropdown
        self.add_item(HistoryActionSelect(self, mode=action_group or "category"))

        # Row 2 — detail select (populated with current page rows)
        rows = self._load_page()
        if rows:
            self.add_item(HistoryDetailSelect(self, rows))

    def _load_page(self) -> list:
        return _query_log_page(
            self.guild_id, PAGE_SIZE, self.page,
            self.filters.get("action"),
            self.filters.get("user_id"),
            self.filters.get("date"),
        )

    async def _update(self, interaction: discord.Interaction):
        rows = self._load_page()
        total_pages = max(1, (self.total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= total_pages - 1
        embed = _build_history_embed(self.guild, rows, self.page, self.total, self.filters)
        await interaction.response.edit_message(embed=embed, view=self)


class HistoryFilterModal(discord.ui.Modal):
    def __init__(self, parent_view: HistoryView):
        super().__init__(title=t("modals","history_filter_title"))
        self.parent = parent_view
        cur = parent_view.filters
        self.f_user = discord.ui.TextInput(
            label=t("modals","history_filter_user_label"),
            placeholder=t("modals","history_filter_user_ph"),
            default=cur.get("user_raw","") or "",
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.f_date = discord.ui.TextInput(
            label=t("modals","history_filter_date_label"),
            placeholder=t("modals","history_filter_date_ph"),
            default=cur.get("date","") or "",
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.add_item(self.f_user)
        self.add_item(self.f_date)

    async def on_submit(self, interaction: discord.Interaction):
        raw_user = self.f_user.value.strip()
        user_id  = None
        if raw_user:
            clean = raw_user.strip("<@!>")
            if clean.isdigit():
                user_id = clean
            else:
                member = discord.utils.find(
                    lambda m: m.display_name.lower() == raw_user.lower()
                              or m.name.lower() == raw_user.lower(),
                    interaction.guild.members
                )
                if member:
                    user_id = str(member.id)
        self.parent.filters.update({
            "user_id":  user_id,
            "user_raw": raw_user,
            "date":     self.f_date.value.strip() or None,
        })
        self.parent.page  = 0
        self.parent.total = count_log(
            self.parent.guild_id,
            self.parent.filters.get("action"),
            self.parent.filters.get("user_id"),
            self.parent.filters.get("date"),
        )
        rows = self.parent._load_page()
        total_pages = max(1, (self.parent.total + PAGE_SIZE - 1) // PAGE_SIZE)
        # Rebuild buttons to reflect new reset-disabled state
        self.parent.clear_items()
        self.parent._rebuild_components(action_group=self.parent.action_group)
        embed = _build_history_embed(
            interaction.guild, rows, self.parent.page,
            self.parent.total, self.parent.filters
        )
        await interaction.response.edit_message(embed=embed, view=self.parent)


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

        # Restore open ApplicationReviewViews from persistent storage
        open_apps = load_open_apps()
        for entry in open_apps.values():
            try:
                self.add_view(ApplicationReviewView(
                    applicant_id=entry["applicant_id"],
                    thread_id=entry["thread_id"],
                    review_channel_id=entry["review_channel_id"]
                ))
            except Exception:
                pass

        await self.tree.sync()
        print("🌐 Slash Commands wurden global synchronisiert.")
        _debug(f"Loaded {len(bot.tree.get_commands())} commands")

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
                            _debug(f"Link deleted from {message.author}: {link}")
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
            log_action(str(interaction.guild_id), interaction.user, "whitelist", clean_domain, "add")
            await interaction.response.send_message(
                t("success","whitelist_added", domain=clean_domain), ephemeral=True
            )
    elif aktion.value == "remove":
        if clean_domain in whitelist:
            whitelist.remove(clean_domain)
            save_whitelist(whitelist)
            log_action(str(interaction.guild_id), interaction.user, "whitelist", clean_domain, "remove")
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
        log_action(str(interaction.guild_id), interaction.user, "ban", str(nutzer), grund,
                   payload={"user_id": nutzer.id, "user_name": str(nutzer),
                             "reason": grund, "avatar": str(nutzer.display_avatar.url)})
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
        log_action(str(interaction.guild_id), interaction.user, "kick", str(nutzer), grund,
                   payload={"user_id": nutzer.id, "user_name": str(nutzer),
                             "reason": grund, "avatar": str(nutzer.display_avatar.url)})
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
        log_action(str(interaction.guild_id), interaction.user, "timeout", str(nutzer),
                   str(minuten)+"min | "+grund,
                   payload={"user_id": nutzer.id, "user_name": str(nutzer),
                             "minutes": minuten, "reason": grund,
                             "avatar": str(nutzer.display_avatar.url)})
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
    log_action(gid, interaction.user, "warn", str(nutzer),
               "#"+str(new_warn_count)+": "+grund,
               payload={"user_id": nutzer.id, "user_name": str(nutzer),
                         "count": new_warn_count, "reason": grund,
                         "avatar": str(nutzer.display_avatar.url)})

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
    log_action(str(interaction.guild_id), interaction.user, "warn_edit",
               str(nutzer), str(alte_anzahl)+" -> "+str(anzahl))
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

@bot.tree.command(name="ticket_edit", description=td("ticket_edit"))
@app_commands.default_permissions(administrator=True)
async def ticket_edit(interaction: discord.Interaction):
    """Opens the interactive ticket panel edit wizard."""
    guild_id = str(interaction.guild_id)
    config   = load_config()
    panels   = config.get(guild_id, {}).get("ticket_panels", [])

    if not panels:
        return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)

    # If only one panel: go straight to edit view
    uid = interaction.user.id
    if len(panels) == 1:
        panel = dict(panels[0])
        # Always load current embed values from Discord message
        if panel.get("channel_id") and panel.get("message_id"):
            try:
                ch  = (interaction.guild.get_channel(int(panel["channel_id"]))
                       or await interaction.guild.fetch_channel(int(panel["channel_id"])))
                msg = await ch.fetch_message(int(panel["message_id"]))
                if msg.embeds:
                    e = msg.embeds[0]
                    panel["embed_desc"]      = e.description or ""
                    panel["embed_color"]     = format(e.color.value, "06x") if e.color else ""
                    panel["embed_thumbnail"] = bool(e.thumbnail)
            except Exception:
                panel.setdefault("embed_desc",      "")
                panel.setdefault("embed_color",     "")
                panel.setdefault("embed_thumbnail", True)
        else:
            panel.setdefault("embed_desc",      "")
            panel.setdefault("embed_color",     "")
            panel.setdefault("embed_thumbnail", True)

        _ticket_edit_state[uid] = {"panel": panel, "guild_id": guild_id}
        embed = _build_ticket_edit_embed(_ticket_edit_state[uid], interaction.guild)
        view  = TicketEditMainView(uid)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        _wiz_msg = await interaction.original_response()
        _ticket_edit_state[uid]["_wiz_ch_id"]  = _wiz_msg.channel.id
        _ticket_edit_state[uid]["_wiz_msg_id"] = _wiz_msg.id
        _wizard_interactions[uid] = interaction
    else:
        # Multiple panels: show selection dropdown first
        view = discord.ui.View(timeout=120)
        view.add_item(TicketEditPanelSelect(uid, guild_id))
        await interaction.response.send_message(
            content="Wähle das Ticket-Panel das du bearbeiten möchtest:",
            view=view, ephemeral=True
        )


# ─────────────────────────────────────────────
#  DELETE WIZARD COMMAND
# ─────────────────────────────────────────────

@bot.tree.command(name="edit", description=td("edit"))
@app_commands.default_permissions(administrator=True)
async def edit_cmd(interaction: discord.Interaction):
    """Universal edit wizard for all panel types."""
    guild_id = str(interaction.guild_id)
    config   = load_config()
    gdata    = config.get(guild_id, {})

    has_any = any([
        gdata.get("ticket_panels"),
        gdata.get("selfrole_panels"),
        gdata.get("application_panels"),
        gdata.get("verify_panels"),
    ])
    if not has_any:
        return await interaction.response.send_message(
            t("errors", "delete_nothing_found"), ephemeral=True
        )

    view = EditTypeView(interaction.user.id, guild_id)
    await interaction.response.send_message(
        content=t("success", "edit_pick_type"),
        view=view,
        ephemeral=True
    )
    _wizard_interactions[interaction.user.id] = interaction


@bot.tree.command(name="delete", description=td("delete_wizard"))
@app_commands.default_permissions(administrator=True)
async def delete_cmd(interaction: discord.Interaction):
    """Opens the delete wizard to remove panels and configurations."""
    guild_id = str(interaction.guild_id)
    config   = load_config()
    gdata    = config.get(guild_id, {})

    has_anything = any([
        gdata.get("ticket_panels"),
        gdata.get("selfrole_panels"),
        gdata.get("application_panels"),
        gdata.get("verify_panels"),
        gdata.get("join_roles"),
    ])
    if not has_anything:
        return await interaction.response.send_message(
            t("errors", "delete_nothing_found"), ephemeral=True
        )

    view = DeleteTypeView(interaction.user.id, guild_id)
    await interaction.response.send_message(
        content=t("success", "delete_wizard_start"),
        view=view,
        ephemeral=True
    )


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
    lang_names = {"de": "🇩🇪 Deutsch", "en": "🇬🇧 English"}
    log_action(str(interaction.guild_id), interaction.user, "language", sprache.value)
    await send_log(
        interaction.guild,
        t("embeds", "log_language", "title"),
        t("embeds", "log_language", "desc", lang=lang_names.get(sprache.value, sprache.value)),
        discord.Color.blurple(),
        interaction.user,
        moderator=interaction.user,
    )


@bot.tree.command(name="config_export", description=td("config_export"))
@app_commands.default_permissions(administrator=True)
async def config_export(interaction: discord.Interaction):
    """Download current server config as JSON."""
    await interaction.response.defer(ephemeral=True)
    config   = load_config()
    guild_id = str(interaction.guild_id)
    gdata    = config.get(guild_id, {})

    if not gdata:
        return await interaction.followup.send(
            t("errors","config_export_empty"), ephemeral=True
        )

    import io

    guild_channel_ids = {ch.id for ch in interaction.guild.channels}

    # ── Open applications ─────────────────────────────────────────────────────
    open_apps = load_open_apps()
    guild_open_apps = {
        tid: entry for tid, entry in open_apps.items()
        if entry.get("review_channel_id") in guild_channel_ids
    }

    # ── Open tickets (private threads in ticket channels) ─────────────────────
    open_tickets = {}
    ticket_channel_ids = set(gdata.get("category_channels", {}).values())
    for ch_id in ticket_channel_ids:
        ch = interaction.guild.get_channel(int(ch_id))
        if not ch:
            continue
        try:
            async for thread in ch.archived_threads(private=False):
                pass  # just to trigger cache — real threads come from active
        except Exception:
            pass
        for thread in ch.threads:
            if thread.archived or thread.locked:
                continue
            members = [m.id for m in thread.members if not interaction.guild.get_member(m.id) or not interaction.guild.get_member(m.id).bot]
            open_tickets[str(thread.id)] = {
                "thread_id":   thread.id,
                "thread_name": thread.name,
                "channel_id":  ch_id,
                "member_ids":  members,
            }

    export = {
        guild_id:              gdata,
        "open_applications":   guild_open_apps,
        "open_tickets":        open_tickets,
    }
    buf = io.BytesIO(json.dumps(export, indent=4, ensure_ascii=False).encode("utf-8"))
    buf.seek(0)
    open_apps_count    = len(guild_open_apps)
    open_tickets_count = len(open_tickets)
    file = discord.File(buf, filename="config_" + guild_id + ".json")

    summary_parts = []
    if open_apps_count:
        summary_parts.append(str(open_apps_count) + " " + t("success","config_export_apps"))
    if open_tickets_count:
        summary_parts.append(str(open_tickets_count) + " " + t("success","config_export_tickets"))
    suffix = " (" + ", ".join(summary_parts) + ")" if summary_parts else ""

    await interaction.followup.send(
        t("success","config_export_done") + suffix,
        file=file,
        ephemeral=True
    )
    log_action(str(interaction.guild_id), interaction.user, "config_export",
               None, str(open_apps_count)+" apps, "+str(open_tickets_count)+" tickets")
    await send_log(
        interaction.guild,
        t("embeds", "log_config_export", "title"),
        t("embeds", "log_config_export", "desc"),
        discord.Color.blurple(),
        interaction.user,
        moderator=interaction.user,
    )


@bot.tree.command(name="config_import", description=td("config_import"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(datei=tp("config_import","datei"))
async def config_import(interaction: discord.Interaction, datei: discord.Attachment):
    """Upload a new config JSON and migrate all panels."""
    if not datei.filename.endswith(".json"):
        return await interaction.response.send_message(
            t("errors","config_import_not_json"), ephemeral=True
        )
    await interaction.response.defer(ephemeral=True)

    try:
        raw = await datei.read()
        new_config = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return await interaction.followup.send(
            t("errors","config_import_invalid") + str(e), ephemeral=True
        )

    guild_id = str(interaction.guild_id)

    # Accept {guild_id: {...}} format or direct guild data
    if guild_id in new_config and isinstance(new_config[guild_id], dict):
        guild_data  = new_config[guild_id]
        full_config = new_config
    elif any(k.isdigit() and isinstance(v, dict) for k, v in new_config.items()):
        # Has some numeric guild ID — remap to current guild
        guild_data  = next(v for k, v in new_config.items() if k.isdigit() and isinstance(v, dict))
        full_config = {guild_id: guild_data}
    else:
        # Assume raw guild data dict
        guild_data  = new_config
        full_config = {guild_id: guild_data}

    # Build preview
    lines = [t("success","config_preview_title"), ""]
    imported_open_apps    = new_config.get("open_applications", {})
    imported_open_tickets = new_config.get("open_tickets", {})
    preview_items = [
        (t("selects", "edit_tickets"),                   len(guild_data.get("ticket_panels", []))),
        (t("selects", "edit_selfroles"),                 len(guild_data.get("selfrole_panels", []))),
        (t("selects", "edit_applications"),              len(guild_data.get("application_panels", []))),
        (t("selects", "edit_verify"),                    len(guild_data.get("verify_panels", []))),
        (t("success", "config_preview_join_roles"),      len(guild_data.get("join_roles", []))),
        (t("success", "config_preview_warns"),           len(guild_data.get("warns", {}))),
        (t("success", "config_preview_open_apps"),       len(imported_open_apps)),
        (t("success", "config_preview_open_tickets"),    len(imported_open_tickets)),
    ]
    for name, count in preview_items:
        if count:
            lines.append(name + ": **" + str(count) + "**")

    lines.append("")
    lines.append(t("success","config_import_warning"))
    lines.append(t("success","config_import_confirm"))

    embed = discord.Embed(
        title=t("embeds","config_import","title"),
        description="\n".join(lines),
        color=discord.Color.orange()
    )
    if interaction.guild.icon:
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)

    view = ConfigUploadView(interaction.user.id, full_config, guild_id, "\n".join(lines))
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="adminpanel", description=td("adminpanel"))
@app_commands.default_permissions(administrator=True)
async def adminpanel_cmd(interaction: discord.Interaction):
    """Opens the unified admin panel."""
    embed = discord.Embed(
        title=t("embeds","admin_panel","title"),
        description=t("embeds","admin_panel","desc"),
        color=discord.Color.blurple(),
        timestamp=now_timestamp()
    )
    if interaction.guild.icon:
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
    await interaction.response.send_message(
        embed=embed,
        view=AdminStartView(interaction.user.id),
        ephemeral=True
    )


@bot.tree.command(name="setup", description=td("setup"))
@app_commands.default_permissions(administrator=True)
async def setup_cmd(interaction: discord.Interaction):
    """Unified setup wizard — choose what to set up."""
    embed = discord.Embed(
        title=t("embeds","setup","title"),
        description=t("embeds","setup","desc"),
        color=discord.Color.blurple(),
        timestamp=now_timestamp()
    )
    if interaction.guild.icon:
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
    await interaction.response.send_message(embed=embed, view=SetupMenuView(interaction.user.id), ephemeral=True)
    _wizard_interactions[interaction.user.id] = interaction


class SetupMenuSelect(discord.ui.Select):
    """One dropdown — all setup options."""
    def __init__(self, user_id: int, guild_id: str):
        self.user_id  = user_id
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label=t("selects","setup_tickets"),      value="tickets",      emoji="🎫"),
            discord.SelectOption(label=t("selects","setup_verify"),       value="verify",       emoji="✅"),
            discord.SelectOption(label=t("selects","setup_selfroles"),    value="selfroles",    emoji="🎭"),
            discord.SelectOption(label=t("selects","setup_application"),  value="application",  emoji="📋"),
            discord.SelectOption(label=t("selects","setup_log"),          value="log",          emoji="📋",
                                 description=t("selects","setup_log_desc")),
            discord.SelectOption(label=t("selects","setup_welcome"),      value="welcome",      emoji="👋",
                                 description=t("selects","setup_welcome_desc")),
            discord.SelectOption(label=t("selects","setup_waiting_room"), value="waiting_room", emoji="🎵",
                                 description=t("selects","setup_waiting_room_desc")),
            discord.SelectOption(label=t("selects","setup_join_roles"),   value="join_roles",   emoji="🚪"),
            discord.SelectOption(label=t("selects","setup_status"),       value="status",       emoji="⚙️"),
            discord.SelectOption(label=t("selects","setup_language"),     value="language",     emoji="🌐"),
        ]
        super().__init__(
            placeholder=t("selects","setup_ph"),
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        val = self.values[0]
        uid = self.user_id
        gid = self.guild_id

        if val == "tickets":
            _ticket_wizard_state[uid] = {"title": "", "supporter_role_ids": [], "categories": []}
            embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
            view  = TicketSetupMainView(uid)
            log_action(str(interaction.guild_id), interaction.user, "setup_tickets")
            await interaction.response.edit_message(embed=embed, view=view)

        elif val == "verify":
            _verify_wizard_state[uid] = {"thumbnail": True, "title": "", "desc": "", "color_hex": "", "role_id": None}
            embed = _build_verify_wizard_embed(_verify_wizard_state[uid], interaction.guild)
            view  = VerifyWizardMainView(uid)
            log_action(str(interaction.guild_id), interaction.user, "setup_verify")
            await interaction.response.edit_message(embed=embed, view=view)

        elif val == "selfroles":
            _selfrole_wizard_state[uid] = {"title": "", "desc": "", "color_hex": "", "roles": []}
            embed = _build_selfrole_embed(_selfrole_wizard_state[uid], interaction.guild)
            view  = SelfRoleSetupMainView(uid)
            log_action(str(interaction.guild_id), interaction.user, "setup_selfroles")
            await interaction.response.edit_message(embed=embed, view=view)

        elif val == "application":
            _setup_wizard_state[uid] = {
                "title": "", "desc": "", "review_channel_id": None,
                "reviewer_role_ids": [], "questions": None, "current_section": None,
            }
            embed = _build_wizard_embed(_setup_wizard_state[uid], interaction.guild)
            view  = AppSetupMainView(uid)
            log_action(str(interaction.guild_id), interaction.user, "setup_application")
            await interaction.response.edit_message(embed=embed, view=view)

        elif val == "join_roles":
            config   = load_config()
            existing = config.get(gid, {}).get("join_roles", [])
            _joinroles_wizard_state[uid] = {"role_ids": list(existing)}
            embed = _build_joinroles_embed(_joinroles_wizard_state[uid], interaction.guild)
            view  = JoinRolesWizardView(uid)
            await interaction.response.edit_message(embed=embed, view=view)

        elif val == "status":
            config = load_config()
            pres   = config.get("bot_presence", {})
            _status_wizard_state[uid] = {
                "status":     pres.get("status", "online"),
                "activity":   pres.get("type", "playing"),
                "text":       pres.get("text", ""),
                "stream_url": pres.get("url", "https://twitch.tv/discord"),
            }
            embed = _build_status_embed(_status_wizard_state[uid])
            view  = StatusWizardView(uid)
            await interaction.response.edit_message(embed=embed, view=view)

        elif val == "language":
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(
                    title="🌐 " + t("selects","setup_language"),
                    description=t("embeds","setup","language_hint"),
                    color=discord.Color.blurple()
                ),
                view=SetupLanguageView(uid)
            )

        elif val == "log":
            view = discord.ui.View(timeout=120)
            view.add_item(SetupChannelSelect(uid, "log_channel_id", t("selects","setup_log_ph"), gid))
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(title="📋 " + t("selects","setup_log"),
                                    description=t("embeds","setup","channel_hint"),
                                    color=discord.Color.blurple()),
                view=view
            )

        elif val == "welcome":
            view = discord.ui.View(timeout=120)
            view.add_item(SetupChannelSelect(uid, "welcome_channel_id", t("selects","setup_welcome_ph"), gid))
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(title="👋 " + t("selects","setup_welcome"),
                                    description=t("embeds","setup","channel_hint"),
                                    color=discord.Color.blurple()),
                view=view
            )

        elif val == "waiting_room":
            view = discord.ui.View(timeout=120)
            view.add_item(SetupVoiceChannelSelect(uid, "waiting_room_id", t("selects","setup_waiting_room_ph"), gid))
            await interaction.response.edit_message(
                content=None,
                embed=discord.Embed(title="🎵 " + t("selects","setup_waiting_room"),
                                    description=t("embeds","setup","channel_hint"),
                                    color=discord.Color.blurple()),
                view=view
            )


class SetupMenuView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(SetupMenuSelect(user_id, ""))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Update guild_id on first real interaction
        for item in self.children:
            if hasattr(item, "guild_id"):
                item.guild_id = str(interaction.guild_id)
        return True


class SetupChannelSelect(discord.ui.ChannelSelect):
    """Generic text channel selector for log/welcome channels."""
    def __init__(self, user_id: int, config_key: str, placeholder: str, guild_id: str):
        self.user_id    = user_id
        self.config_key = config_key
        self.guild_id   = guild_id
        super().__init__(
            placeholder=placeholder,
            min_values=1, max_values=1,
            channel_types=[discord.ChannelType.text]
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        gid = str(interaction.guild_id)
        ch  = self.values[0]
        config = load_config()
        config.setdefault(gid, {})[self.config_key] = ch.id
        save_config(config)
        log_action(gid, interaction.user, "setup_" + self.config_key.replace("_id","").replace("_channel",""), str(ch))

        success_keys = {
            "log_channel_id":     ("success","log_channel_set"),
            "welcome_channel_id": ("success","welcome_channel_set"),
        }
        sk = success_keys.get(self.config_key, ("success","log_channel_set"))
        msg = t(sk[0], sk[1], channel=ch.mention)

        done_embed = discord.Embed(
            title="✅ " + msg, color=discord.Color.green()
        )
        if interaction.guild.icon:
            done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(
            embed=done_embed,
            view=SetupBackView(self.user_id)
        )


class SetupVoiceChannelSelect(discord.ui.ChannelSelect):
    """Voice channel selector for waiting room."""
    def __init__(self, user_id: int, config_key: str, placeholder: str, guild_id: str):
        self.user_id    = user_id
        self.config_key = config_key
        self.guild_id   = guild_id
        super().__init__(
            placeholder=placeholder,
            min_values=1, max_values=1,
            channel_types=[discord.ChannelType.voice]
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        gid = str(interaction.guild_id)
        ch  = self.values[0]
        config = load_config()
        config.setdefault(gid, {})[self.config_key] = ch.id
        save_config(config)
        log_action(gid, interaction.user, "setup_waiting_room", str(ch))
        done_embed = discord.Embed(
            title="✅ " + t("success","waiting_room_set", channel=ch.mention),
            color=discord.Color.green()
        )
        if interaction.guild.icon:
            done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=done_embed, view=SetupBackView(self.user_id))


class SetupLanguageView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="🇩🇪 Deutsch", style=discord.ButtonStyle.secondary)
    async def de_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        set_language("de", guild_id=str(interaction.guild_id))
        done = discord.Embed(title="✅ " + t("success","language_set"), color=discord.Color.green())
        await interaction.response.edit_message(embed=done, view=SetupBackView(self.user_id))

    @discord.ui.button(label="🇬🇧 English", style=discord.ButtonStyle.secondary)
    async def en_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        set_language("en", guild_id=str(interaction.guild_id))
        done = discord.Embed(title="✅ " + t("success","language_set"), color=discord.Color.green())
        await interaction.response.edit_message(embed=done, view=SetupBackView(self.user_id))


class SetupBackView(discord.ui.View):
    """After completing a simple setup step — offers to go back to menu."""
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.back_btn.label   = t("buttons","setup_back_menu")
        self.finish_btn.label = t("buttons","wizard_cancel")

    @discord.ui.button(label="←", style=discord.ButtonStyle.blurple)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        embed = discord.Embed(
            title=t("embeds","setup","title"),
            description=t("embeds","setup","desc"),
            color=discord.Color.blurple()
        )
        if interaction.guild.icon:
            embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(
            embed=embed,
            view=SetupMenuView(self.user_id)
        )

    @discord.ui.button(label="✖️", style=discord.ButtonStyle.secondary)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(t("errors","application_not_yours"), ephemeral=True)
        await interaction.response.edit_message(
            content=t("success","setup_done"), embed=None, view=None
        )


@bot.tree.command(name="embed_create", description=td("embed_create"))
@app_commands.default_permissions(administrator=True)
async def embed_create_cmd(interaction: discord.Interaction):
    """Opens the embed generator wizard."""
    uid = interaction.user.id
    _embed_gen_state[uid] = _default_embed_state()
    status_embed = _build_embed_gen_status(_embed_gen_state[uid], interaction.guild)
    log_action(str(interaction.guild_id), interaction.user, "embed_create")
    await interaction.response.send_message(embed=status_embed, view=EmbedGenView(uid), ephemeral=True)
    _wizard_interactions[uid] = interaction


@bot.tree.command(name="info", description=td("info"))
async def info_cmd(interaction: discord.Interaction):
    """Shows bot info, live statistics and current version fetched from GitHub."""
    await interaction.response.defer(ephemeral=True)

    # Fetch live version from GitHub (falls back to cached on error)
    live_version = await fetch_bot_version()

    guild_count  = len(bot.guilds)
    member_count = sum(g.member_count or 0 for g in bot.guilds)
    latency_ms   = round(bot.latency * 1000)
    config       = load_config()
    ticket_panels = selfrole_panels = verify_panels = app_panels = 0
    for gid, data in config.items():
        if not isinstance(data, dict): continue
        ticket_panels   += len(data.get("ticket_panels", []))
        selfrole_panels += len(data.get("selfrole_panels", []))
        verify_panels   += len(data.get("verify_panels", []))
        app_panels      += len(data.get("application_panels", []))
    try:
        with _db_lock:
            conn      = _db_conn()
            log_count = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            conn.close()
    except Exception:
        log_count = 0

    color = discord.Color.from_rgb(88, 101, 242)
    embed = discord.Embed(
        title=t("embeds","info","title"),
        description=t("embeds","info","desc"),
        color=color,
        timestamp=now_timestamp()
    )
    if bot.user and bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)

    # Version field — uses live_version from GitHub
    v1 = t("embeds","info","version_val", version=live_version)
    v2 = t("embeds","info","author_val",  author=BOT_AUTHOR)
    v3 = t("embeds","info","github_val",  url=BOT_GITHUB)
    embed.add_field(name=t("embeds","info","f_version"), value=v1+"\n"+v2+"\n"+v3, inline=True)

    s1 = t("embeds","info","stat_guilds",  n=guild_count)
    s2 = t("embeds","info","stat_members", n=member_count)
    s3 = t("embeds","info","stat_latency", ms=latency_ms)
    s4 = t("embeds","info","stat_log",     n=log_count)
    embed.add_field(name=t("embeds","info","f_stats"), value=s1+"\n"+s2+"\n"+s3+"\n"+s4, inline=True)

    p1 = t("embeds","info","panel_tickets",   n=ticket_panels)
    p2 = t("embeds","info","panel_selfroles", n=selfrole_panels)
    p3 = t("embeds","info","panel_verify",    n=verify_panels)
    p4 = t("embeds","info","panel_apps",      n=app_panels)
    embed.add_field(name=t("embeds","info","f_panels"), value=p1+"\n"+p2+"\n"+p3+"\n"+p4, inline=True)
    embed.add_field(name=t("embeds","info","f_features"), value=t("embeds","info","features_val"), inline=False)
    embed.set_footer(
        text=t("embeds","info","footer", version=live_version),
        icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
    )
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label=t("buttons","info_github"),
        url=BOT_GITHUB,
        style=discord.ButtonStyle.link,
        emoji="\U0001f517"
    ))
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


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

@bot.tree.command(name="music_upload", description=td("music_upload"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(datei=tp("music_upload","datei"))
async def music_upload_cmd(interaction: discord.Interaction, datei: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    allowed_ext = (".mp3", ".ogg", ".wav", ".flac", ".m4a")
    if not any(datei.filename.lower().endswith(ext) for ext in allowed_ext):
        return await interaction.followup.send(t("errors","music_invalid_format"), ephemeral=True)
    if datei.size > 25 * 1024 * 1024:
        return await interaction.followup.send(t("errors","music_too_large"), ephemeral=True)
    music_path = os.path.join(os.getcwd(), "support_music.mp3")
    try:
        data = await datei.read()
        with open(music_path, "wb") as f:
            f.write(data)
        log_action(str(interaction.guild_id), interaction.user, "music_upload",
                   datei.filename, str(round(datei.size/1024)) + " KB")
        await interaction.followup.send(
            t("success","music_uploaded", filename=datei.filename), ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(t("errors","generic_error", error=str(e)), ephemeral=True)


@bot.tree.command(name="music_download", description=td("music_download"))
@app_commands.default_permissions(administrator=True)
async def music_download_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    music_path = os.path.join(os.getcwd(), "support_music.mp3")
    if not os.path.exists(music_path):
        return await interaction.followup.send(t("errors","music_not_found"), ephemeral=True)
    import io as _io
    try:
        with open(music_path, "rb") as f:
            buf = _io.BytesIO(f.read())
        buf.seek(0)
        size_kb = round(os.path.getsize(music_path) / 1024)
        await interaction.followup.send(
            t("success","music_downloaded", size=size_kb),
            file=discord.File(buf, filename="support_music.mp3"),
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(t("errors","generic_error", error=str(e)), ephemeral=True)


# ─────────────────────────────────────────────
#  HISTORY COMMAND
# ─────────────────────────────────────────────

@bot.tree.command(name="history", description=td("history"))
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    action=tp("history","action"),
    user=tp("history","user"),
    date=tp("history","date")
)
async def history_cmd(interaction: discord.Interaction,
                      action: str = None, user: str = None, date: str = None):
    """Show paginated server audit log with optional filters."""
    await interaction.response.defer(ephemeral=True)
    guild_id = str(interaction.guild_id)

    # Resolve user argument
    user_id  = None
    user_raw = user or ""
    if user_raw:
        clean = user_raw.strip("<@!>")
        if clean.isdigit():
            user_id = clean
        else:
            member = discord.utils.find(
                lambda m: m.display_name.lower() == user_raw.lower()
                          or m.name.lower() == user_raw.lower(),
                interaction.guild.members
            )
            if member:
                user_id = str(member.id)

    filters = {
        "action":   action or None,
        "user_id":  user_id,
        "user_raw": user_raw,
        "date":     date or None,
    }
    total = count_log(guild_id, filters.get("action"), filters.get("user_id"), filters.get("date"))
    if total == 0:
        return await interaction.followup.send(t("errors","history_empty"), ephemeral=True)

    rows  = _query_log_page(guild_id, PAGE_SIZE, 0,
                             filters.get("action"), filters.get("user_id"), filters.get("date"))
    embed = _build_history_embed(interaction.guild, rows, 0, total, filters)
    view  = HistoryView(interaction.guild, guild_id, 0, total, filters)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


# ─────────────────────────────────────────────
#  GITHUB VERSION FETCH
# ─────────────────────────────────────────────

async def fetch_bot_version() -> str:
    """Fetch the current bot version from GitHub version.txt.
    Falls back silently to the locally cached value on any error."""
    global _cached_version
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                GITHUB_VERSION_URL,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    ver = (await resp.text()).strip()
                    if ver:
                        _cached_version = ver
    except Exception:
        pass  # silently fall back to cached / default
    return _cached_version


# ─────────────────────────────────────────────
#  HELP EMBED BUILDERS
# ─────────────────────────────────────────────

def _build_user_help_embed(guild) -> discord.Embed:
    """Help embed shown to regular (non-admin) users."""
    embed = discord.Embed(
        title=t("embeds", "help", "user_title"),
        description=t("embeds", "help", "user_desc"),
        color=discord.Color.from_rgb(88, 101, 242),
        timestamp=now_timestamp()
    )
    embed.add_field(
        name=t("embeds", "help", "f_general"),
        value=(
            "`/ping`  —  " + t("embeds", "help", "cmd_ping") + "\n"
            + "`/info`  —  " + t("embeds", "help", "cmd_info") + "\n"
            + "`/userinfo`  —  " + t("embeds", "help", "cmd_userinfo") + "\n"
            + "`/help`  —  " + t("embeds", "help", "cmd_help")
        ),
        inline=False
    )
    embed.add_field(
        name=t("embeds", "help", "f_tickets"),
        value=t("embeds", "help", "tickets_user_desc"),
        inline=False
    )
    embed.add_field(
        name=t("embeds", "help", "f_applications"),
        value=t("embeds", "help", "applications_user_desc"),
        inline=False
    )
    embed.add_field(
        name=t("embeds", "help", "f_selfroles"),
        value=t("embeds", "help", "selfroles_user_desc"),
        inline=False
    )
    embed.add_field(
        name=t("embeds", "help", "f_verify"),
        value=t("embeds", "help", "verify_user_desc"),
        inline=False
    )
    if guild and guild.icon:
        embed.set_footer(
            text=t("embeds", "help", "footer_user", name=guild.name),
            icon_url=guild.icon.url
        )
    else:
        embed.set_footer(text=t("embeds", "help", "footer_user", name="Bexi Bot"))
    return embed


def _build_admin_help_embed(guild) -> discord.Embed:
    """Help embed shown to administrators."""
    embed = discord.Embed(
        title=t("embeds", "help", "admin_title"),
        description=t("embeds", "help", "admin_desc"),
        color=discord.Color.gold(),
        timestamp=now_timestamp()
    )
    embed.add_field(
        name=t("embeds", "help", "f_setup"),
        value=(
            "`/setup`  —  " + t("embeds", "help", "cmd_setup") + "\n"
            + "`/edit`  —  " + t("embeds", "help", "cmd_edit") + "\n"
            + "`/delete`  —  " + t("embeds", "help", "cmd_delete") + "\n"
            + "`/ticket_edit`  —  " + t("embeds", "help", "cmd_ticket_edit")
        ),
        inline=False
    )
    embed.add_field(
        name=t("embeds", "help", "f_moderation"),
        value=(
            "`/ban`  —  " + t("embeds", "help", "cmd_ban") + "\n"
            + "`/kick`  —  " + t("embeds", "help", "cmd_kick") + "\n"
            + "`/timeout`  —  " + t("embeds", "help", "cmd_timeout") + "\n"
            + "`/warn`  —  " + t("embeds", "help", "cmd_warn") + "\n"
            + "`/warn_edit`  —  " + t("embeds", "help", "cmd_warn_edit") + "\n"
            + "`/adminpanel`  —  " + t("embeds", "help", "cmd_adminpanel")
        ),
        inline=False
    )
    embed.add_field(
        name=t("embeds", "help", "f_config"),
        value=(
            "`/config_export`  —  " + t("embeds", "help", "cmd_config_export") + "\n"
            + "`/config_import`  —  " + t("embeds", "help", "cmd_config_import") + "\n"
            + "`/history`  —  " + t("embeds", "help", "cmd_history") + "\n"
            + "`/whitelist`  —  " + t("embeds", "help", "cmd_whitelist") + "\n"
            + "`/embed_create`  —  " + t("embeds", "help", "cmd_embed_create") + "\n"
            + "`/set_language`  —  " + t("embeds", "help", "cmd_set_language")
        ),
        inline=False
    )
    embed.add_field(
        name=t("embeds", "help", "f_misc"),
        value=(
            "`/music_upload`  —  " + t("embeds", "help", "cmd_music_upload") + "\n"
            + "`/music_download`  —  " + t("embeds", "help", "cmd_music_download") + "\n"
            + "`/setup_pioneer_role`  —  " + t("embeds", "help", "cmd_pioneer") + "\n"
            + "`/userinfo`  —  " + t("embeds", "help", "cmd_userinfo")
        ),
        inline=False
    )
    if guild and guild.icon:
        embed.set_footer(
            text=t("embeds", "help", "footer_admin", name=guild.name),
            icon_url=guild.icon.url
        )
    else:
        embed.set_footer(text=t("embeds", "help", "footer_admin", name="Bexi Bot"))
    return embed


# ─────────────────────────────────────────────
#  /HELP COMMAND
# ─────────────────────────────────────────────

@bot.tree.command(name="help", description=td("help"))
async def help_cmd(interaction: discord.Interaction):
    """Role-aware help: admins see all admin commands, users see feature usage guide."""
    await interaction.response.defer(ephemeral=True)

    is_admin = (
        interaction.user.guild_permissions.administrator
        if interaction.guild
        else False
    )
    embed = (
        _build_admin_help_embed(interaction.guild)
        if is_admin
        else _build_user_help_embed(interaction.guild)
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
    global DEFAULT_APPLICATION_QUESTIONS
    DEFAULT_APPLICATION_QUESTIONS = _load_default_application()
    print(f'✅ Bot online als {bot.user}')
    print(f'🌐 Standardsprache: {DEFAULT_LANG}')
    if DEBUG:
        print('🐛 DEBUG-Modus aktiv')
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
