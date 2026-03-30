# 🤖 AI Development Instructions — Bexi Bot

Diese Datei ist für KI-Assistenten gedacht, die an diesem Projekt weiterarbeiten. Sie beschreibt die komplette Architektur, alle Konventionen und bekannte Fallstricke.

---

## 📁 Projektstruktur

```
bexi_bot/
├── bot.py                        # Einzige Haupt-Datei, ~8100 Zeilen
├── support_music.mp3             # Warteraum-Musik (wird per /music_upload ersetzt)
├── language/
│   ├── de.json                   # Deutsche Texte (Primärsprache)
│   └── en.json                   # Englische Texte
├── configs/
│   ├── config.json               # Laufzeit-Konfiguration (pro Server)
│   ├── whitelist.json            # Erlaubte Link-Domains
│   ├── open_applications.json    # Offene Bewerbungs-Threads
│   ├── default_application.json  # Standard-Bewerbungsfragen (29 Stück)
│   └── audit_log.db              # SQLite-Audit-Log
├── requirements.txt
├── Docker/
│   ├── Dockerfile
│   └── compose.yaml
└── AI_instructions/
    └── instructions.md
```

---

## 🏗️ Architektur von bot.py

Die Datei ist in diese Sektionen gegliedert (in Reihenfolge):

1. **Imports & Env-Setup**
2. **I18N-System** — `t()`, `td()`, `tp()`, `tch()`
3. **Config-Helpers** — `load_config()`, `save_config()`, `load_whitelist()`, `save_whitelist()`
4. **Open-Apps-Helpers** — `load_open_apps()`, `save_open_app()`, `delete_open_app()`
5. **Utility-Helpers** — `format_discord_text()`, `extract_role_ids()`, `now_timestamp()`, `short_time()`
6. **Embed-Builder** — `make_dm_embed()`, `make_log_embed()`
7. **Send-Helpers** — `send_log()`, `send_dm()`
8. **UI-Klassen** — Self-Roles, Tickets, Applications, Admin-Panel, Embed-Generator, alle Wizards
9. **Audit Log (SQLite)** — `_init_db()`, `log_action()`, `query_log()`
10. **Bot-Klasse** — `MyBot` mit `setup_hook`, `on_message`, `on_member_join`, `on_voice_state_update`
11. **Slash-Commands** — alle `@bot.tree.command` Definitionen
12. **on_ready** + `bot.run()`

---

## 🌐 I18N-System — Sprachsystem

### Hilfsfunktionen

```python
t("section", "key1", "key2", ..., param=value)  # beliebig tief verschachtelt
td("command_name")                               # Command-Beschreibung
tp("command_name", "param_name")                 # Parameter-Beschreibung
tch("command_name", "choices_group", "value")    # Choice-Label
```

### Wichtige Konvention

**Kein einziger hardcodierter String** darf in irgendeiner Sprache direkt im Code stehen. Alle user-facing Texte gehören in `language/de.json` UND `language/en.json`.

### JSON-Struktur (beide Dateien identisch aufgebaut)

```json
{
    "_info": { "language": "...", "code": "...", "author": "..." },
    "commands": {
        "command_name": {
            "description": "...",
            "params": { "param": "..." },
            "choices": { "group": { "value": "label" } }
        }
    },
    "buttons":  { "key": "Label" },
    "modals":   { "key": "..." },
    "selects":  { "key": "..." },
    "errors":   { "key": "Fehlermeldung mit {platzhalter}" },
    "success":  { "key": "Erfolgsmeldung mit {platzhalter}" },
    "embeds": {
        "section_name": {
            "title": "...",
            "desc":  "...",
            "f_field_name": "Feldname"
        }
    }
}
```

### Sprache pro Server

```python
init_language(guild_id=str(interaction.guild_id))   # laden
set_language("de", guild_id=str(interaction.guild_id))  # setzen
```

Gespeichert unter: `config[guild_id]["language"]`

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

### Config-Struktur

```json
{
    "GUILD_ID": {
        "language":           "de",
        "log_channel_id":     123456,
        "welcome_channel_id": 123456,
        "waiting_room_id":    123456,
        "join_roles":         [123456],
        "warns":              { "USER_ID": 3 },
        "ticket_counter":     42,
        "category_counters":  { "Support": 12 },
        "category_channels":  { "Support_abc123": 123456 },
        "ticket_panels": [
            {
                "categories":         [{"label":"X","value":"X_abc123","emoji":"🛠️","description":"...","supporter_role_ids":null}],
                "supporter_role_ids": [],
                "message_id":         0,
                "channel_id":         0,
                "title":              "...",
                "created_at":         "01.01.2026 12:00"
            }
        ],
        "verify_panels":      [{"role_id":123, "message_id":456, "channel_id":789, "title":"..."}],
        "selfrole_panels":    [{"roles":[{"label":"X","role_id":0,"emoji":null}], "message_id":0, "channel_id":0, "title":"..."}],
        "application_panels": [{"questions":null, "review_channel_id":0, "reviewer_role_ids":[], "message_id":0, "channel_id":0, "title":"..."}]
    },
    "bot_presence": {"status":"online","type":"playing","text":"...","url":"..."}
}
```

### Wichtig beim Iterieren

```python
# config.json hat auch "bot_presence" als Top-Level-Key (kein Guild-Dict)
for guild_id_str, data in config.items():
    if not isinstance(data, dict):
        continue
```

---

## 🗄️ Audit-Log (SQLite)

### Tabelle `audit_log`

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,   -- "2026-01-15 14:32:00 UTC"
    actor_id    TEXT    NOT NULL,
    actor_name  TEXT    NOT NULL,
    action      TEXT    NOT NULL,   -- "ban", "kick", "warn", "timeout", ...
    target      TEXT,               -- z.B. "Username#0000" oder Dateiname
    detail      TEXT                -- Freitext (Grund, Größe, etc.)
);
```

### Verwendung

```python
# Schreiben (thread-safe via _db_lock)
log_action(str(interaction.guild_id), interaction.user, "ban",    str(nutzer), grund)
log_action(str(interaction.guild_id), interaction.user, "kick",   str(nutzer), grund)
log_action(str(interaction.guild_id), interaction.user, "timeout",str(nutzer), str(min)+"min | "+grund)
log_action(gid,                       interaction.user, "warn",   str(nutzer), "#3: "+grund)
log_action(str(interaction.guild_id), interaction.user, "music_upload", datei.filename, "42 KB")
log_action(str(interaction.guild_id), interaction.user, "config_export", None, "3 apps, 5 tickets")

# Lesen
rows = query_log(guild_id, limit=25, action_filter="ban")
# rows = [{"id":1,"guild_id":"...","timestamp":"...","actor_id":"...","action":"ban",...}]
```

### Geloggte Aktionen

| Action | Trigger |
|---|---|
| `ban` | `/ban` Command |
| `kick` | `/kick` Command |
| `timeout` | `/timeout` Command und AdminPanel |
| `warn` | `/warn` Command |
| `config_export` | `/config_export` Command |
| `config_import` | `ConfigUploadView.confirm_btn` |
| `config_rollback` | `ConfigRollbackView.rollback_btn` |
| `music_upload` | `/music_upload` Command |

---

## 📋 Slash-Commands (vollständige Liste)

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/setup` | **Universeller Setup-Wizard** (Tickets, Verify, Self-Roles, Bewerbungen, Log-Kanal, Willkommen, Warteraum, Auto-Join, Status, Sprache) | Admin |
| `/edit` | Unified Edit-Wizard für alle Panel-Typen | Admin |
| `/delete` | Interaktiver Lösch-Assistent | Admin |
| `/adminpanel` | Admin-Panel (User: Timeout/Warn/Kick/Ban via UserSelect, Chat: Lock/Slowmode/Purge) | Admin |
| `/embed_create` | Embed-Generator mit Vorschau, Feld-Editierung, Bild-Support | Admin |
| `/whitelist` | Link-Whitelist verwalten (add/remove/list) | Admin |
| `/ban` | Mitglied permanent bannen (DM + Log) | Ban Members |
| `/kick` | Mitglied kicken (DM + Log) | Kick Members |
| `/timeout` | Mitglied timeoutten (DM + Log) | Moderate Members |
| `/warn` | Mitglied verwarnen (DM + Log) | Moderate Members |
| `/warn_edit` | Verwarnungen eines Nutzers bearbeiten | Moderate Members |
| `/userinfo` | Nutzer-Informationen anzeigen | Jeder / Admin für andere |
| `/set_language` | Bot-Sprache ändern (de/en) | Admin |
| `/config_export` | Config + offene Tickets/Bewerbungen als JSON exportieren | Admin |
| `/config_import` | Config importieren, Panels neu erstellen, 24h-Rollback | Admin |
| `/history` | SQLite Audit-Log anzeigen (filter + limit Parameter) | Admin |
| `/music_upload` | Neue Warteraum-Musik hochladen (.mp3/.ogg/.wav/.flac/.m4a, max 25 MB) | Admin |
| `/music_download` | Aktuelle Warteraum-Musik herunterladen | Admin |
| `/ticket_edit` | Ticket-Panel bearbeiten (Titel/Beschreibung/Farbe) | Admin |
| `/setup_pioneer_role` | Pionier-Rolle an erste 100 Mitglieder vergeben | Admin |
| `/ping` | Bot-Latenz anzeigen | Jeder |

> **Kein separater `/setup_tickets`, `/setup_verify`, `/status_config` etc. mehr** — alles läuft über `/setup`.

---

## 🖱️ UI-Klassen — Wizard-Pattern

### Wizard-Interaktions-Referenz

Alle Wizards nutzen `_wizard_interactions[uid] = interaction` für die ursprüngliche Interaktion, damit Modals die Wizard-Nachricht per `edit_original_response()` aktualisieren können:

```python
# Beim Command-Start:
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

### Setup-Wizard (`/setup`)

`SetupMenuView` → `SetupMenuSelect` (10 Optionen) → öffnet direkt den passenden Wizard-View:

| Option | Öffnet |
|---|---|
| 🎫 Ticket-System | `TicketSetupMainView` |
| ✅ Verifizierung | `VerifyWizardMainView` |
| 🎭 Self-Roles | `SelfRoleSetupMainView` |
| 📋 Bewerbungssystem | `AppSetupMainView` |
| 📋 Log-Kanal | `SetupChannelSelect` (Text-Channel-Dropdown) |
| 👋 Willkommens-Kanal | `SetupChannelSelect` (Text-Channel-Dropdown) |
| 🎵 Warteraum | `SetupVoiceChannelSelect` (Voice-Channel-Dropdown) |
| 🚪 Auto-Join Rollen | `JoinRolesWizardView` |
| ⚙️ Bot-Status | `StatusWizardView` |
| 🌐 Sprache | `SetupLanguageView` (DE/EN Buttons) |

Nach Abschluss einfacher Schritte: `SetupBackView` mit "← Zurück zum Menü".

### Persistent Views — Registrierung in setup_hook

```python
async def setup_hook(self):
    config = load_config()
    for guild_id_str, data in config.items():
        if not isinstance(data, dict): continue
        for panel in data.get("verify_panels", []):
            self.add_view(VerifyView(panel["role_id"]))
        for t_panel in data.get("ticket_panels", []):
            supp_ids = t_panel.get("supporter_role_ids") or []
            self.add_view(TicketView(t_panel["categories"], supp_ids))
        for s_panel in data.get("selfrole_panels", []):
            self.add_view(SelfRoleView(s_panel["roles"], str(s_panel.get("message_id","default"))))
        for idx, _ap in enumerate(data.get("application_panels", [])):
            self.add_view(ApplicationPanelView(panel_index=idx))
    self.add_view(TicketControlView())
    for entry in load_open_apps().values():
        self.add_view(ApplicationReviewView(
            applicant_id=entry["applicant_id"],
            thread_id=entry["thread_id"],
            review_channel_id=entry["review_channel_id"]
        ))
```

### Button-Labels in `__init__` setzen

Discord-Decorator-Labels werden zur Importzeit ausgewertet — `t()` funktioniert dort nicht:

```python
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claim.label = t("buttons", "claim_ticket")   # Methodenname
        self.close.label = t("buttons", "close_ticket")
```

---

## 🎫 Ticket-System

### Thread-Name-Format
`{kategorie[:5]}-{id:04d}-{username}`

### Kategorie-Wert
Jede Kategorie hat ein eindeutiges `value` = `label_<uuid6hex>` — verhindert Kollisionen bei gleichnamigen Kategorien.

### Supporter-Berechtigung
Rollen-Position-Vergleich (`r.position >= base_role.position`) — höhere Rollen gelten automatisch als Supporter.

---

## 📦 Config Export/Import

### Export-Format

```json
{
    "GUILD_ID": { ...guild_data... },
    "open_applications": {
        "thread_id": {"applicant_id": 0, "thread_id": 0, "review_channel_id": 0}
    },
    "open_tickets": {
        "thread_id": {"thread_id": 0, "thread_name": "...", "channel_id": 0, "member_ids": []}
    }
}
```

### Import-Flow

1. Datei hochladen → `ConfigUploadView` zeigt Vorschau (Panel-Zählungen inkl. Tickets/Bewerbungen)
2. Confirm: `deepcopy(load_config())` als unveränderlicher Snapshot
3. Merge neuer Config (überspringt `bot_presence`, `open_applications`, `open_tickets`)
4. `_recreate_panels()` löscht alte Panel-Nachrichten und erstellt neue
5. Offene Bewerbungen + Tickets werden wiederhergestellt (Thread-Mitglieder re-added)
6. Neue Panel-IDs werden als `imported_msg_ids` gespeichert und an `ConfigRollbackView` übergeben
7. **Rollback-Button** im Log-Kanal — 24h Timeout (`timeout=86400`), nur Admins
8. Beim Rollback: `imported_msg_ids` werden gelöscht → Snapshot wird neu erstellt

### Deep Copy ist absolut kritisch

```python
# ❌ FALSCH — _recreate_panels mutiert panel["message_id"] in-place!
snapshot_config = load_config()

# ✅ RICHTIG
import copy as _copy
snapshot_config = _copy.deepcopy(load_config())
```

---

## 🎨 Embed-Generator (`/embed_create`)

### State-Struktur

```python
{
    "title": "", "description": "", "color": "5865F2",
    "author_name": "", "author_icon": "",
    "footer_text": "", "footer_icon": "",
    "image_url": "",    # Großes Bild unten
    "thumbnail_url": "", # Kleines Bild rechts
    "fields": [{"name": str, "value": str, "inline": bool}],
    "timestamp": False,
}
```

### Feld-Editierung

- `EmbedGenFieldSelect(user_id, action="edit"|"delete")` — Discord StringSelect mit allen Feldern
- Auswahl öffnet `EmbedGenAddFieldModal(user_id, edit_idx=N)` mit vorausgefüllten Werten
- Kein Feld-Bild — wurde bewusst entfernt

### Vorschau-Texte (kontextspezifisch)

```python
t("success", "wizard_preview_note_application")  # Bewerbungs-Panel
t("success", "wizard_preview_note_ticket")        # Ticket-Panel
t("success", "wizard_preview_note_verify")        # Verify-Panel
t("success", "wizard_preview_note_embed")         # Embed-Generator
```

---

## 🎵 Musik-System

```python
music_path = os.path.join(os.getcwd(), "support_music.mp3")
# Erlaubte Formate: .mp3 .ogg .wav .flac .m4a — max 25 MB
# FFmpeg spielt die Datei im Warteraum-Voice-Channel in Endlosschleife
```

---

## ⚠️ Bekannte Fallstricke

### 1. `t()` bei Command-Dekoratoren

```python
# ❌ GEHT NICHT — wird zur Importzeit ausgewertet
@app_commands.describe(grund=t("commands","ban","params","grund"))

# ✅ RICHTIG — tp() liest aus _lang_cache
@app_commands.describe(grund=tp("ban","grund"))
```

### 2. Modal → Wizard-Update Pattern

```python
# ❌ FALSCH aus einem Modal
await interaction.response.edit_message(...)

# ✅ RICHTIG
await interaction.response.defer(ephemeral=True)
orig = _wizard_interactions.get(uid)
if orig:
    await orig.edit_original_response(embed=embed, view=view)
```

### 3. Supporter-Rollen Rückwärtskompatibilität

```python
supp_ids = t_panel.get("supporter_role_ids")
if not supp_ids:
    old_id = t_panel.get("supporter_role_id")   # ältere Panel-Einträge
    supp_ids = [old_id] if old_id else []
```

### 4. Ticket category value Eindeutigkeit

```python
import uuid
value = label + "_" + uuid.uuid4().hex[:6]
```

### 5. SQLite Thread-Safety

```python
_db_lock = threading.Lock()   # globaler Lock
with _db_lock:
    conn = _db_conn()
    conn.execute(...)
    conn.commit()
    conn.close()
```

### 6. Config-Import Keys überspringen

```python
for key, val in self.new_config.items():
    if key not in ("bot_presence", "open_applications", "open_tickets"):
        config[key] = val
```

---

## ➕ Neues Feature hinzufügen — Checkliste

```
[ ] Slash-Command mit @bot.tree.command definieren
[ ] Beschreibung in language/de.json UND language/en.json unter "commands" eintragen
[ ] Parameter/Choices in beide JSONs eintragen
[ ] Embed-Texte unter "embeds.neue_sektion" in beide JSONs
[ ] Fehlermeldungen unter "errors" in beide JSONs
[ ] Erfolgsmeldungen unter "success" in beide JSONs
[ ] Falls Audit relevant: log_action() aufrufen
[ ] Falls persistent: View in setup_hook registrieren
[ ] Falls Wizard: _wizard_interactions[uid] = interaction beim Start
[ ] Falls Button-Labels dynamisch: self.methode.label = t(...) in __init__
[ ] Syntax-Check: python3 -c "import ast; ast.parse(open('bot.py').read())"
[ ] JSON-Check: python3 -c "import json; [json.load(open(f'language/{l}.json')) for l in ['de','en']]"
```

---

## 🔍 Debugging

| Fehler | Ursache | Lösung |
|---|---|---|
| `[not-str: embeds.x.y]` | Key ist kein String (z.B. dict) | Tiefe im `t()`-Aufruf prüfen |
| `[missing: embeds.x.y]` | Key fehlt in JSON | In beide JSONs eintragen |
| `AttributeError: has no attribute 'xyz'` | Button-Attributname falsch | Muss der **Methoden**name sein |
| `KeyError` in setup_hook | Alte config.json Struktur | isinstance-Check + `.get()` |
| Persistent View lädt nicht | Nicht in setup_hook | `add_view()` hinzufügen |
| Rollback stellt falsche IDs her | Shallow copy von config | `deepcopy(load_config())` |
| Modal aktualisiert Wizard nicht | Falsches response-Pattern | `defer()` + `edit_original_response()` |

### Schnell-Tests

```bash
python3 -c "import ast; ast.parse(open('bot.py').read()); print('Syntax OK')"
python3 -c "import json; [json.load(open(f'language/{l}.json')) for l in ['de','en']]; print('JSON OK')"
python3 -c "import sqlite3; c=sqlite3.connect('configs/audit_log.db'); print('DB rows:', c.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0])"
```

---

## 🐳 Docker-Deployment

```yaml
services:
  discord-bot:
    image: pilzithegoat/bexi_bot:VERSION
    environment:
      - DISCORD_TOKEN=${Bot_Token}
      - DISCORD_GUILD_ID=${Guild_ID}
      - TZ=Europe/Berlin
    volumes:
      - ./configs:/app/configs         # Config + SQLite-DB persistieren
      - ./support_music.mp3:/app/support_music.mp3
    platform: linux/arm64
```

```bash
# Neue Version deployen
docker pull pilzithegoat/bexi_bot:NEU
docker-compose up -d
```

---

## 📦 Abhängigkeiten (requirements.txt)

```
discord.py          # Discord API
PyNaCl              # Voice-Verschlüsselung
ffmpeg              # Audio
discord.py[voice]   # Voice-Support
static-ffmpeg       # Portables FFmpeg
python-dotenv       # .env laden
```

SQLite ist in Python's Standardbibliothek enthalten — kein extra Paket nötig.