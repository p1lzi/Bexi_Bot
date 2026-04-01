# 🤖 AI Development Instructions — Bexi Bot v2.0.0

Diese Datei ist für KI-Assistenten gedacht, die an diesem Projekt weiterarbeiten.

---

## 📁 Projektstruktur

```
bexi_bot/
├── bot.py                              # Einzige Haupt-Datei (~9100 Zeilen)
├── support_music.mp3                   # Warteraum-Musik (wird per /music_upload ersetzt)
├── language/
│   ├── de.json                         # Deutsche Texte (Primärsprache)
│   └── en.json                         # Englische Texte
├── configs/
│   ├── config.json                     # Laufzeit-Konfiguration (pro Server)
│   ├── whitelist.json                  # Erlaubte Link-Domains
│   ├── open_applications.json          # Offene Bewerbungs-Threads
│   ├── audit_log.db                    # SQLite Audit-Log
│   ├── default_application.json        # Standard-Bewerbung (EN, 29 Fragen)
│   └── default_application_de.json     # Standard-Bewerbung (DE, 29 Fragen)
├── Docker/
│   ├── Dockerfile
│   └── compose.yaml
└── AI_instructions/
    └── instructions.md
```

---

## 🏗️ Architektur von bot.py

Sektionen in Reihenfolge:

1. **Imports & Env-Setup** — inkl. `BOT_VERSION`, `BOT_AUTHOR`, `BOT_GITHUB`
2. **I18N-System** — `t()`, `td()`, `tp()`, `tch()`
3. **Config-Helpers** — `load_config()`, `save_config()`, `load_whitelist()` etc.
4. **Open-Apps-Helpers** — `load_open_apps()`, `save_open_app()`, `delete_open_app()`
5. **Utility-Helpers** — `format_discord_text()`, `extract_role_ids()`, `now_timestamp()`, `short_time()`
6. **Embed-Builder** — `make_dm_embed()`, `make_log_embed()`
7. **Send-Helpers** — `send_log()`, `send_dm()`
8. **UI-Klassen** — Self-Roles, Tickets, Applications, Admin-Panel, alle Wizards
9. **Embed-Generator** — `_default_embed_state()`, `_build_preview_embed()`, `_build_button_view()`, alle EmbedGen-Klassen
10. **Audit Log (SQLite)** — `_init_db()`, `log_action()`, `query_log()`, `count_log()`, `_query_log_page()`
11. **History Pagination** — `ACTION_EMOJIS`, `ACTION_CATEGORIES`, `_build_history_embed()`, `_build_detail_embed()`, `HistoryView`, `HistoryDetailSelect`, `HistoryFilterModal`
12. **Bot-Klasse** — `MyBot` mit `setup_hook`, `on_message`, `on_member_join`, `on_voice_state_update`
13. **Slash-Commands** — alle `@bot.tree.command`
14. **on_ready** + `bot.run()`

---

## 🌐 I18N-System

### Hilfsfunktionen

```python
t("section", "key1", "key2", ..., param=value)  # beliebig tief
td("command_name")                               # Command-Beschreibung
tp("command_name", "param_name")                 # Parameter-Beschreibung
tch("command_name", "choices_group", "value")    # Choice-Label
```

### Eiserne Regel

**Jeder user-facing String muss in `de.json` UND `en.json` vorhanden sein.** Keine Ausnahmen. Beim Hinzufügen einer Funktion zuerst beide JSON-Dateien aktualisieren.

---

## 💾 Config-System

### Dateipfade

```python
CONFIGS_DIR      = 'configs'
CONFIG_FILE      = os.path.join(CONFIGS_DIR, 'config.json')
WHITELIST_FILE   = os.path.join(CONFIGS_DIR, 'whitelist.json')
OPEN_APPS_FILE   = os.path.join(CONFIGS_DIR, 'open_applications.json')
DEFAULT_APP_FILE = os.path.join(CONFIGS_DIR, 'default_application.json')
AUDIT_DB         = os.path.join(CONFIGS_DIR, 'audit_log.db')
```

### Config-Struktur (config.json)

```json
{
    "GUILD_ID": {
        "language":           "de",
        "log_channel_id":     0,
        "welcome_channel_id": 0,
        "waiting_room_id":    0,
        "join_roles":         [],
        "warns":              {},
        "category_counters":  {},
        "category_channels":  {},
        "ticket_panels":      [{"categories":[{"label":"X","value":"X_abc123"}], "supporter_role_ids":[], "message_id":0, "channel_id":0}],
        "verify_panels":      [{"role_id":0, "message_id":0, "channel_id":0}],
        "selfrole_panels":    [{"roles":[{"label":"X","role_id":0}], "message_id":0, "channel_id":0}],
        "application_panels": [{"questions":null, "review_channel_id":0, "message_id":0, "channel_id":0}]
    },
    "bot_presence": {"status":"online","type":"playing","text":"...","url":"..."}
}
```

### Pflicht-Check bei Iteration

```python
for guild_id_str, data in config.items():
    if not isinstance(data, dict):
        continue  # überspringt "bot_presence" und andere nicht-guild Keys
```

---

## 🗄️ Audit-Log (SQLite)

### Schema

```sql
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    timestamp   TEXT NOT NULL,   -- "2026-01-15 14:32:00 UTC"
    actor_id    TEXT NOT NULL,
    actor_name  TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT,            -- Nutzer-String oder Domain
    detail      TEXT,            -- Freitext (Grund, Größe etc.)
    payload     TEXT             -- JSON für reiche Detail-Ansicht
);
```

### log_action Signatur

```python
log_action(guild_id: str, actor: object, action: str,
           target: str = None, detail: str = None, payload: dict = None)
```

### Payload-Konventionen

```python
# Moderation (ban/kick/warn/timeout):
payload={"user_id": nutzer.id, "user_name": str(nutzer),
         "reason": grund, "avatar": str(nutzer.display_avatar.url)}

# Embed gesendet:
payload={...gesamter embed state dict..., "sent_channel_id": ch.id, "message_id": msg.id}
```

### Geloggte Aktionen (alle)

`ban` · `kick` · `timeout` · `warn` · `warn_edit` · `whitelist` · `language` · `config_export` · `config_import` · `config_rollback` · `music_upload` · `embed_sent` · `embed_create` · `setup_tickets` · `setup_verify` · `setup_selfroles` · `setup_application` · `setup_log_channel` · `setup_welcome_channel` · `setup_waiting_room` · `admin_ban` · `admin_kick` · `admin_warn` · `admin_timeout` · `admin_timeout_remove` · `admin_lock` · `admin_unlock` · `admin_slowmode` · `admin_purge` · `history`

---

## 📋 Slash-Commands (vollständige Liste)

| Command | Berechtigung |
|---|---|
| `/setup` | Admin — universeller Setup-Wizard (10 Optionen) |
| `/edit` | Admin — Panel bearbeiten |
| `/delete` | Admin — interaktiver Lösch-Assistent |
| `/adminpanel` | Admin — User (UserSelect → sofortige Userinfo) + Chat |
| `/embed_create` | Admin — Embed-Generator (Felder, Bilder, Link-Buttons, Dropdown) |
| `/whitelist` | Admin — Link-Whitelist |
| `/ban` / `/kick` / `/timeout` / `/warn` / `/warn_edit` | Moderation |
| `/userinfo` | Jeder / Admin für andere |
| `/set_language` | Admin |
| `/config_export` / `/config_import` | Admin |
| `/history` | Admin — paginierter Audit-Log mit Filtern |
| `/music_upload` / `/music_download` | Admin |
| `/ticket_edit` | Admin |
| `/setup_pioneer_role` | Admin |
| `/info` | Jeder — Bot-Infos, Statistiken, Version |
| `/ping` | Jeder |

> **Kein `/setup_tickets`, `/setup_verify` etc. mehr** — alles über `/setup`.

---

## 🖱️ Wizard-Pattern

### Interaktions-Referenz

```python
# Beim Start:
await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
_wizard_interactions[uid] = interaction

# In Modal.on_submit():
await interaction.response.defer(ephemeral=True)
orig = _wizard_interactions.get(uid)
if orig:
    try:
        await orig.edit_original_response(embed=new_embed, view=new_view)
    except Exception:
        pass
```

### Setup-Wizard (`/setup`) — 10 Optionen

`SetupMenuView` → `SetupMenuSelect` → öffnet direkt den passenden Wizard-View oder Channel-Select.

---

## 🎨 Embed-Generator

### State-Struktur

```python
{
    "title": "", "description": "", "color": "5865F2",
    "author_name": "", "author_icon": "",
    "footer_text": "", "footer_icon": "",
    "image_url": "", "thumbnail_url": "",
    "fields":   [{"name":str,"value":str,"inline":bool}],
    "buttons":  [{"label":str,"url":str,"emoji":str}],     # link buttons
    "dropdown_options": [{"label":str,"description":str,"emoji":str}],  # dropdown
    "component_type": None | "buttons" | "dropdown",
    "timestamp": False,
}
```

### View-Rows

- Row 0: Inhalt (Titel/Farbe, Bilder, Author/Footer, Timestamp)
- Row 1: Felder (Hinzufügen, Bearbeiten, Löschen)
- Row 2: Komponenten (Link-Buttons ODER Dropdown)
- Row 3: Senden (In Kanal, Hier, Vorschau, Abbrechen)

---

## 📦 Config Export/Import

### Export-Format

```json
{
    "GUILD_ID": {...guild_data...},
    "open_applications": {"thread_id": {...}},
    "open_tickets":      {"thread_id": {"thread_id":0,"thread_name":"...","channel_id":0,"member_ids":[]}}
}
```

### Import-Flow

1. Datei hochladen → Vorschau (Panel-Anzahl + offene Tickets/Bewerbungen)
2. `deepcopy(load_config())` als unveränderlicher Snapshot ← **kritisch!**
3. Merge, `_recreate_panels()`, Tickets + Bewerbungen wiederherstellen
4. Rollback-Button im Log-Kanal (24h, nur Admins)
5. Beim Rollback: `imported_msg_ids` löschen → Snapshot neu erstellen

---

## 🔠 Bewerbungen — Mehrsprachig

```python
def _load_default_application(lang: str = None) -> list:
    """Lädt sprachspezifische Standard-Fragen.
    Sucht: configs/default_application_{lang}.json → configs/default_application.json
    """
```

Verfügbare Dateien:
- `configs/default_application.json` — Englisch (29 Fragen)
- `configs/default_application_de.json` — Deutsch (29 Fragen)

`ApplicationPanelView` übergibt automatisch die Guild-Sprache:
```python
guild_lang = load_config().get(str(interaction.guild_id), {}).get("language", "en")
questions = panel.get("questions") or _load_default_application(guild_lang)
```

---

## ⚠️ Bekannte Fallstricke

### 1. `t()` bei Dekoratoren

```python
# ❌ Wird zur Importzeit ausgewertet
@app_commands.describe(grund=t("commands","ban","params","grund"))
# ✅ Korrekt
@app_commands.describe(grund=tp("ban","grund"))
```

### 2. Modal → Wizard-Update

```python
# ❌ Falsch
await interaction.response.edit_message(...)
# ✅ Richtig
await interaction.response.defer(ephemeral=True)
await orig.edit_original_response(embed=embed, view=view)
```

### 3. Deep Copy für Snapshots

```python
import copy as _copy
snapshot_config = _copy.deepcopy(load_config())  # NIEMALS ohne deepcopy!
```

### 4. SQLite Thread-Safety

```python
with _db_lock:
    conn = _db_conn()
    conn.execute(...)
    conn.commit()
    conn.close()
```

### 5. Button-Labels in `__init__`

```python
class MyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.my_btn.label = t("buttons", "my_key")  # NICHT im Decorator!
```

---

## ➕ Neues Feature — Checkliste

```
[ ] @bot.tree.command definieren
[ ] description in de.json UND en.json ("commands")
[ ] params/choices in beide JSONs
[ ] Alle Texte (embeds/errors/success/buttons/modals/selects) in beide JSONs
[ ] log_action() aufrufen wenn Admin-Aktion
[ ] Falls persistent: add_view() in setup_hook
[ ] Falls Wizard: _wizard_interactions[uid] = interaction beim Start
[ ] Falls Button-Labels: self.methode.label = t(...) in __init__
[ ] python3 -c "import ast; ast.parse(open('bot.py').read())" ← Syntax-Check
[ ] python3 -c "import json; [json.load(open(f'language/{l}.json')) for l in ['de','en']]" ← JSON-Check
```

---

## 🔍 Debugging

| Fehler | Ursache | Lösung |
|---|---|---|
| `[not-str: embeds.x.y]` | Key ist kein String | Tiefe im `t()`-Aufruf prüfen |
| `[missing: embeds.x.y]` | Key fehlt in JSON | In beide JSONs eintragen |
| `AttributeError: no attribute 'xyz'` | Button-Attributname falsch | Muss der **Methoden**name sein |
| Rollback stellt falsche IDs her | Shallow copy | `deepcopy(load_config())` |
| Modal aktualisiert Wizard nicht | Falsches Pattern | `defer()` + `edit_original_response()` |

---

## 🐳 Docker

```yaml
services:
  discord-bot:
    image: pilzithegoat/bexi_bot:VERSION
    environment:
      - DISCORD_TOKEN=${Bot_Token}
      - DISCORD_GUILD_ID=${Guild_ID}
      - TZ=Europe/Berlin
    volumes:
      - ./configs:/app/configs
      - ./support_music.mp3:/app/support_music.mp3
    platform: linux/arm64
```

---

## 📦 Abhängigkeiten

```
discord.py          # Discord API
PyNaCl              # Voice-Verschlüsselung
ffmpeg              # Audio
discord.py[voice]   # Voice-Support
static-ffmpeg       # Portables FFmpeg
python-dotenv       # .env laden
```

SQLite ist in Python's Standardbibliothek enthalten.