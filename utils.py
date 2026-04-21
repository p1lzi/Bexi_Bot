import discord
from discord import app_commands
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
    ffmpeg_exe, ffprobe_exe = None, None
    HAS_STATIC_FFMPEG = False


# --- SETUP DATEIEN ---
TOKEN        = os.getenv('DISCORD_TOKEN')
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
    """Übersetzt einen Text mit beliebig tiefer Verschachtelung."""
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
    return _lang_cache.get("commands", {}).get(cmd, {}).get("description", f"[cmd.{cmd}]")

def tp(cmd: str, param: str) -> str:
    return _lang_cache.get("commands", {}).get(cmd, {}).get("params", {}).get(param, f"[{cmd}.{param}]")

def tch(cmd: str, group: str, value: str) -> str:
    return _lang_cache.get("commands", {}).get(cmd, {}).get("choices", {}).get(group, {}).get(value, value)

# ─────────────────────────────────────────────
#  CONFIG HANDLING
# ─────────────────────────────────────────────
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
    if os.path.exists(OPEN_APPS_FILE):
        try:
            with open(OPEN_APPS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def _load_default_application() -> list:
    """Load default application questions from configs/default_application.json."""
    if os.path.exists(DEFAULT_APP_FILE):
        try:
            with open(DEFAULT_APP_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('questions', [])
        except (json.JSONDecodeError, OSError):
            pass
    return []

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

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _debug(msg: str):
    if DEBUG:
        print(f"[DEBUG] {msg}")

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
#  EMBED BUILDERS
# ─────────────────────────────────────────────
def make_dm_embed(title, description, color, guild=None, mention_name=None, fields=None, jump_url=None, footer_system=None):
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

def make_log_embed(title, description, color, target_user, moderator=None, reason=None, guild=None, extra_fields=None):
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
#  SEND HELPERS
# ─────────────────────────────────────────────
async def send_log(guild, title, description, color, target_user, moderator=None, reason=None, extra_fields=None):
    config = load_config()
    gid = str(guild.id)
    log_channel_id = config.get(gid, {}).get("log_channel_id")
    if log_channel_id:
        channel = guild.get_channel(log_channel_id)
        if channel:
            embed = make_log_embed(title, description, color, target_user, moderator, reason, guild, extra_fields)
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

async def send_dm(user, content="", embed=None):
    try:
        await user.send(content=content if content else None, embed=embed)
    except discord.Forbidden:
        pass


# ─────────────────────────────────────────────
#  WIZARD SELECT HELPERS (Generic)
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
        from state import _wizard_interactions
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
        from state import _wizard_interactions
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
