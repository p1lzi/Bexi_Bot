# 🤖 AI Development Instructions — Bexi Bot

Diese Datei ist für KI-Assistenten gedacht, die an diesem Projekt weiterarbeiten. Sie beschreibt die komplette Architektur, alle Konventionen und bekannte Fallstricke.

---

## 📁 Projektstruktur

```
bexi_bot/
├── bot.py                  # Einzige Haupt-Datei, ~1850 Zeilen
├── config.json             # Laufzeit-Konfiguration (pro Server, auto-generiert)
├── whitelist.json          # Erlaubte Link-Domains
├── language/
│   ├── de.json             # Deutsche Texte (Primärsprache)
│   └── en.json             # Englische Texte
├── requirements.txt
├── Dockerfile
└── compose.yaml
```

---

## 🏗️ Architektur von bot.py

Die Datei ist in diese Sektionen gegliedert (in Reihenfolge):

1. **Imports & Env-Setup**
2. **I18N-System** — Sprachfunktionen `t()`, `td()`, `tp()`, `tch()`
3. **Config-Helpers** — `load_config()`, `save_config()`, `load_whitelist()`, `save_whitelist()`
4. **Utility-Helpers** — `format_discord_text()`, `extract_role_ids()`, `now_timestamp()`, `short_time()`
5. **Embed-Builder** — `make_dm_embed()`, `make_log_embed()`
6. **Send-Helpers** — `send_log()`, `send_dm()`
7. **UI-Klassen** — `SelfRoleButton`, `SelfRoleView`, `TicketCloseModal`, `TicketControlView`, `VerifyView`, `TicketSelect`, `TicketView`
8. **Bot-Klasse** — `MyBot` mit `setup_hook`, `on_message`, `on_member_join`, `on_voice_state_update`, `play_looping_music`
9. **Bot-Instanz** — `bot = MyBot()` + `init_language()`
10. **Slash-Commands** — alle `@bot.tree.command` Definitionen
11. **on_ready** + `bot.run()`

---

## 🌐 I18N-System — Sprachsystem

### Hilfsfunktionen

```python
t("section", "key1", "key2", ..., param=value)   # beliebig tief verschachtelt
td("command_name")                                 # Command-Beschreibung
tp("command_name", "param_name")                   # Parameter-Beschreibung
tch("command_name", "choices_group", "value")      # Choice-Label
```

### Beispiele

```python
t("errors", "ban_error")
t("embeds", "dm_ban", "title")
t("embeds", "shared", "f_server")
t("success", "warn_success", mention=nutzer.mention, count=5)
td("ban")
tp("ban", "grund")
tch("whitelist", "aktion", "add")
```

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
    "buttons": { "key": "Label" },
    "modals": { "key": "..." },
    "selects": { "key": "..." },
    "errors": { "key": "Fehlermeldung mit {platzhalter}" },
    "success": { "key": "Erfolgsmeldung mit {platzhalter}" },
    "embeds": {
        "section_name": {
            "title": "...",
            "desc": "...",
            "f_field_name": "Feldname"
        }
    }
}
```

### Sprache pro Server

```python
# Beim Command-Aufruf die Serversprache laden:
init_language(guild_id=str(interaction.guild_id))

# Sprache setzen:
set_language("de", guild_id=str(interaction.guild_id))
```

Gespeichert unter: `config[guild_id]["language"]`

---

## 💾 Config-System

### Struktur von config.json

```json
{
    "GUILD_ID": {
        "language": "de",
        "log_channel_id": 123456,
        "welcome_channel_id": 123456,
        "waiting_room_id": 123456,
        "warns": { "USER_ID": 3 },
        "ticket_counter": 42,
        "category_counters": { "Support": 12 },
        "category_channels": { "Support": 123456 },
        "ticket_panels": [ { ...panel_data } ],
        "verify_panels": [ { "role_id": 123, "msg_id": 456 } ],
        "selfrole_panels": [ { ...panel_data } ],
        "server_stats": { "category_id": 123, "member_channel_id": 456, "boost_channel_id": 789 }
    },
    "bot_presence": {
        "status": "online",
        "type": "streaming",
        "text": "...",
        "url": "https://..."
    }
}
```

### Wichtig beim Lesen

```python
# IMMER isinstance-Check, da config auch nicht-dict Einträge hat (z.B. "bot_presence")
for guild_id_str, data in config.items():
    if not isinstance(data, dict):
        continue
    # ...
```

---

## 🎨 Embed-Builder

### make_dm_embed()

Für DMs an Nutzer (Ticket-Ereignisse, Moderationsaktionen).

```python
embed = make_dm_embed(
    title=t("embeds","dm_ban","title"),
    description=t("embeds","dm_ban","desc"),
    color=discord.Color.red(),
    guild=interaction.guild,
    fields=[
        (t("embeds","dm_ban","f_server"), guild.name, True),   # (name, value, inline)
        (t("embeds","dm_ban","f_reason"), grund, False),
    ],
    jump_url=thread.jump_url,          # optional — fügt 🔗 Link-Feld hinzu
    footer_system=t("embeds","shared","footer_mod")
)
```

### make_log_embed()

Für Log-Kanal Einträge.

```python
embed = make_log_embed(
    title=t("embeds","log_ban","title"),
    description=t("embeds","log_ban","desc"),
    color=discord.Color.red(),
    target_user=nutzer,
    moderator=interaction.user,
    reason=grund,
    guild=interaction.guild,
    extra_fields=[(t("embeds","log_timeout","f_dur"), f"`{minuten}`", True)]
)
```

---

## 🖱️ UI-Klassen

### Persistent Views

Alle Views müssen in `setup_hook` registriert werden:

```python
async def setup_hook(self):
    # Verify Panels
    self.add_view(VerifyView(panel["role_id"]))
    # Ticket Panels
    self.add_view(TicketView(t_panel["categories"], supp_ids))
    # Self-Role Panels
    self.add_view(SelfRoleView(s_panel["roles"], str(s_panel["message_id"])))
    # Ticket Control (global, einmalig)
    self.add_view(TicketControlView())
```

### Button Labels in `__init__` setzen

Discord-Decorator-Labels werden zur **Importzeit** ausgewertet — `t()` funktioniert dort nicht. Labels werden deshalb im `__init__` überschrieben:

```python
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claim.label = t("buttons", "claim_ticket")   # Button-Methodenname
        self.close.label = t("buttons", "close_ticket")

class VerifyView(discord.ui.View):
    def __init__(self, role_id: int):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.verify.label = t("buttons", "verify")        # Methode heißt "verify"
```

**Wichtig:** Der Attributname ist der **Methodenname** des Callbacks (`self.verify`, nicht `self.verify_btn`).

### TicketCloseModal

`TextInput` darf **nicht** als Klassenattribut definiert werden (wird nicht übersetzt). Es wird im `__init__` via `add_item()` hinzugefügt:

```python
class TicketCloseModal(discord.ui.Modal):
    def __init__(self, creator_id=None):
        super().__init__(title=t("modals","ticket_close_title"))
        self.creator_id = creator_id
        self.grund = discord.ui.TextInput(
            label=t("modals","ticket_close_label"),
            ...
        )
        self.add_item(self.grund)
```

---

## 🎫 Ticket-System Logik

```
Nutzer wählt Kategorie im Dropdown
    → TicketSelect.callback()
        → Zähler erhöhen (category_counters)
        → TICKETS Kategorie erstellen falls nötig
        → Kanal für Kategorie erstellen falls nötig (category_channels cached)
        → Privaten Thread erstellen
        → Supporter-Rollen dem Thread hinzufügen
        → Ticket-Embed + TicketControlView senden
        → DM an Nutzer
        → Select zurücksetzen (fresh_view)
```

**Thread-Name-Format:** `{kategorie[:5]}-{id:04d}-{username}`

**Kategorie-Kanal-Name-Format:** `{kategorie-lower-kebab}-tickets`

**Supporter-Berechtigung:** Rollen-Position wird verglichen (`r.position >= base_role.position`), damit auch höhere Rollen als Supporter gelten.

---

## ⚠️ Bekannte Fallstricke

### 1. `t()` bei Command-Dekoratoren
```python
# ❌ GEHT NICHT — wird zur Importzeit ausgewertet, _lang_cache ist noch leer
@app_commands.describe(grund=t("commands","ban","params","grund"))

# ✅ RICHTIG — tp() liest direkt aus _lang_cache
@app_commands.describe(grund=tp("ban","grund"))
```

### 2. `isinstance`-Check in config-Iteration
```python
# config.json hat auch "bot_presence" als Top-Level-Key (kein dict mit guild-Daten)
for guild_id_str, data in config.items():
    if not isinstance(data, dict):  # IMMER machen!
        continue
```

### 3. `supporter_role_ids` vs. `supporter_role_id`
Ältere Panel-Einträge in config.json können noch `supporter_role_id` (singular) haben. Kompatibilitäts-Fallback in `setup_hook`:
```python
supp_ids = t_panel.get("supporter_role_ids")
if not supp_ids:
    old_id = t_panel.get("supporter_role_id")
    supp_ids = [old_id] if old_id else []
```

### 4. Ticket-Panel `channel_id` kann fehlen
Ältere Panels in config.json haben evtl. kein `channel_id`. Immer mit `.get()` abrufen.

### 5. Emoji-Parsing für Kategorien
```python
# Zeichen-für-Zeichen Codepoint-Check — robuster als Regex
for char in label:
    cp = ord(char)
    if cp > 0x27BF and cp not in range(0x2000, 0x206F):
        emoji = char
        label = label[len(char):].strip()
        break
```

### 6. `warn_icons` über JSON
Icons für Warn-Stufen kommen aus `embeds.dm_warn.icon_1` bis `icon_max`:
```python
_wi = {1:"icon_1", 2:"icon_2", 3:"icon_3", 4:"icon_4", 5:"icon_5"}
icon = t("embeds", "dm_warn", _wi.get(new_warn_count, "icon_max"))
```

---

## ➕ Neues Feature hinzufügen — Checkliste

```
[ ] Slash-Command mit @bot.tree.command definieren
[ ] Beschreibung in language/de.json und language/en.json unter "commands" eintragen
[ ] Parameter unter "commands.command_name.params" eintragen
[ ] Choices (falls vorhanden) unter "commands.command_name.choices" eintragen
[ ] Alle Embed-Texte unter "embeds.neue_sektion" eintragen
[ ] Fehlermeldungen unter "errors" eintragen
[ ] Erfolgsmeldungen unter "success" eintragen
[ ] Falls persistent: View in setup_hook registrieren
[ ] Falls Button-Labels dynamisch: in __init__ via self.methode.label = t(...) setzen
[ ] Syntax-Check: python3 -c "import ast; ast.parse(open('bot.py').read())"
[ ] JSON-Check: python3 -c "import json; json.load(open('language/de.json'))"
```

---

## 🔍 Debugging

### Häufige Fehler

| Fehler | Ursache | Lösung |
|---|---|---|
| `[not-str: embeds.x.y]` | Key existiert in JSON, ist aber kein String (z.B. dict) | Tiefe im `t()`-Aufruf prüfen |
| `[missing: embeds.x.y]` | Key existiert nicht in JSON | Key in beide JSON-Dateien eintragen |
| `AttributeError: has no attribute 'xyz'` | Button-Attributname falsch | Muss der **Methoden**name sein |
| `KeyError` in setup_hook | config.json hat alte Struktur | isinstance-Check + .get() verwenden |
| Persistent View lädt nicht | Nicht in setup_hook registriert | add_view() in setup_hook hinzufügen |

### Schnell-Tests

```bash
# Syntax-Check
python3 -c "import ast; ast.parse(open('bot.py').read()); print('OK')"

# JSON-Validierung
python3 -c "import json; [json.load(open(f'language/{l}.json')) for l in ['de','en']]; print('OK')"

# Alle t()-Aufrufe auf fehlende Keys prüfen
grep "t(\"" bot.py | grep -v "#"
```

---

## 📦 Abhängigkeiten (requirements.txt)

```
discord.py          # Discord API
PyNaCl              # Voice-Verschlüsselung
ffmpeg              # Audio (Support-Musik)
discord.py[voice]   # Voice-Support
static-ffmpeg       # Portables FFmpeg (kein System-Install nötig)
dotenv              # .env Datei laden
```

---

## 🐳 Docker-Deployment

```yaml
# compose.yaml
services:
  discord-bot:
    image: pilzithegoat/bexi_bot:VERSION
    environment:
      - DISCORD_TOKEN=${Bot_Token}
      - DISCORD_GUILD_ID=${Guild_ID}
      - TZ=Europe/Berlin
    platform: linux/arm64   # Raspberry Pi — für x86 entfernen
```

Neue Version deployen:
```bash
docker pull pilzithegoat/bexi_bot:NEU
docker-compose up -d
```