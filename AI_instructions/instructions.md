# 🤖 AI Development Instructions — Bexi Bot

Diese Datei ist für KI-Assistenten gedacht, die an diesem Projekt weiterarbeiten.
Sie beschreibt die vollständige Architektur, alle Konventionen, bekannte Fallstricke und den aktuellen Entwicklungsstand.

---

## 📁 Projektstruktur

```
bexi_bot/
├── bot.py                          # Einzige Haupt-Datei, ~4900 Zeilen
├── language/
│   ├── de.json                     # Deutsche Texte (Primärsprache)
│   └── en.json                     # Englische Texte
├── configs/
│   ├── config.json                 # Laufzeit-Konfiguration (pro Server, auto-generiert)
│   ├── whitelist.json              # Erlaubte Link-Domains
│   ├── open_applications.json      # Offene Bewerbungen (für Button-Persistenz nach Neustart)
│   └── default_application.json   # Standard-Bewerbungsformular (29 Fragen, editierbar)
├── AI_instructions/
│   └── instructions.md             # Diese Datei
├── requirements.txt
├── Docker/
│   ├── Dockerfile
│   └── compose.yaml
└── support_music.mp3               # Optional, für Warteraum-Musik
```

---

## 🏗️ Architektur von bot.py

Die Datei ist in diese Sektionen gegliedert (in Reihenfolge):

| Sektion | Inhalt |
|---|---|
| Imports & Env-Setup | discord.py, dotenv, json, os, re, datetime |
| Konstanten | TOKEN, CONFIGS_DIR, alle FILE-Pfade, LANG_DIR |
| `_load_default_application()` | Lädt Fragen aus `default_application.json` |
| I18N-System | `t()`, `td()`, `tp()`, `tch()`, `init_language()`, `set_language()` |
| Config-Helpers | `load_config()`, `save_config()`, `load_whitelist()`, `save_whitelist()` |
| Open-Apps-Helpers | `load_open_apps()`, `save_open_app()`, `delete_open_app()` |
| Utility-Helpers | `format_discord_text()`, `extract_role_ids()`, `now_timestamp()`, `short_time()` |
| Embed-Builder | `make_dm_embed()`, `make_log_embed()` |
| Send-Helpers | `send_log()`, `send_dm()` |
| Self-Role System | `SelfRoleButton`, `SelfRoleView` |
| Ticket-System | `TicketCloseModal`, `TicketControlView`, `TicketSelect`, `TicketView` |
| Verify-System | `VerifyView` |
| Application-System | `ApplicationModal`, `ApplicationContinueView`, `ApplicationPanelView`, `ApplicationReviewView`, `ApplicationDecisionModal`, `build_review_embeds()` |
| Shared Wizard Selects | `WizardRoleSelect`, `WizardChannelSelect`, `_make_role_select_view()`, `_make_channel_select_view()` |
| SelfRole Setup Wizard | `_selfrole_wizard_state`, `SelfRoleSetupInfoModal`, `SelfRoleSetupRoleDetailsModal`, `SelfRoleAddRoleSelect`, `SelfRoleRemoveRoleSelect`, `SelfRoleSetupMainView` |
| Ticket Setup Wizard | `_ticket_wizard_state`, `TicketSetupEmbedModal`, `TicketSetupInfoModal`, `TicketSetupCategoryModal`, `TicketSetupMainView` |
| Status Config Wizard | `_status_wizard_state`, `StatusTextModal`, `StatusSelect`, `ActivitySelect`, `StatusWizardView` |
| Join Roles Wizard | `_joinroles_wizard_state`, `JoinRolesWizardView` |
| Verify Setup Wizard | `_verify_wizard_state`, `VerifySetupInfoModal`, `VerifySetupEmbedModal`, `VerifyWizardMainView` |
| Delete Wizard | `DeleteTypeSelect`, `DeletePanelSelect`, `DeletePanelView`, `DeleteBackView`, `DeleteTypeView`, `_delete_panel()` |
| Ticket Edit Wizard | `_ticket_edit_state`, `TicketEditPanelSelect`, `TicketEditEmbedModal`, `TicketEditCategoryModal`, `TicketEditRemoveCatSelect`, `TicketEditMainView` |
| Application Setup Wizard | `_setup_wizard_state`, `AppSetupSectionModal`, `AppSetupMainView`, `AppSetupEditInfoModal`, `AppSetupQuestionsModal` |
| Bot-Klasse | `MyBot` mit `setup_hook`, `on_message`, `on_member_join`, `on_voice_state_update`, `play_looping_music` |
| Slash-Commands | alle `@bot.tree.command` Definitionen |
| `on_ready` + `bot.run()` | Startup-Logik |

---

## 📋 Alle Slash-Commands (aktuell)

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/setup_application` | Application-Panel Wizard starten | Admin |
| `/setup_tickets` | Ticket-Panel Wizard starten | Admin |
| `/setup_verify` | Verify-Panel Wizard starten | Admin |
| `/selfrole_create` | Self-Role Panel Wizard starten | Admin |
| `/ticket_edit` | Bestehendes Ticket-Panel bearbeiten | Admin |
| `/delete` | Delete-Wizard (löscht Panels aller Typen) | Admin |
| `/set_join_roles` | Auto-Join-Rollen Wizard | Admin |
| `/set_log_channel` | Log-Kanal festlegen | Admin |
| `/set_welcome_channel` | Willkommens-Kanal festlegen | Admin |
| `/set_waiting_room` | Warteraum-Sprachkanal festlegen | Admin |
| `/status_config` | Bot-Status Wizard (Dropdown-basiert) | Admin |
| `/set_language` | Sprache umschalten (de/en) | Admin |
| `/whitelist` | Link-Whitelist verwalten | Admin |
| `/setup_pioneer_role` | Erste 100 Mitglieder mit Rolle versehen | Admin |
| `/ban` | Nutzer bannen | Ban Members |
| `/kick` | Nutzer kicken | Kick Members |
| `/timeout` | Nutzer timeoutten | Moderate Members |
| `/warn` | Nutzer verwarnen | Moderate Members |
| `/warn_edit` | Verwarnungen bearbeiten | Moderate Members |
| `/userinfo` | Nutzerinfos anzeigen | Jeder / Admin für andere |
| `/ping` | Bot-Latenz anzeigen | Jeder |
| `/selfrole_list` | Alle Self-Role Panels anzeigen | Admin |

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
```

### JSON-Struktur (beide Dateien identisch aufgebaut)

```json
{
    "_info": { "language": "...", "code": "...", "author": "..." },
    "commands": {
        "command_name": {
            "description": "...",
            "params": { "param": "..." }
        }
    },
    "buttons": { "key": "Label" },
    "modals":  { "key": "..." },
    "selects": { "key": "..." },
    "errors":  { "key": "Fehlermeldung mit {platzhalter}" },
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
init_language(guild_id=str(interaction.guild_id))
set_language("de", guild_id=str(interaction.guild_id))
```

Gespeichert unter: `config[guild_id]["language"]`

### ⚠️ Wichtige Regel bei neuen Texten

Jeden neuen Text **in beide JSON-Dateien** (`de.json` UND `en.json`) eintragen. Sonst erscheint `[missing: ...]` in der anderen Sprache.

---

## 💾 Config-System

### Struktur von `configs/config.json`

```json
{
    "GUILD_ID": {
        "language": "de",
        "log_channel_id": 123456,
        "welcome_channel_id": 123456,
        "waiting_room_id": 123456,
        "join_roles": [123456, 789012],
        "warns": { "USER_ID": 3 },
        "ticket_counter": 42,
        "category_counters": { "Support": 12 },
        "category_channels": { "Support": 123456 },
        "ticket_panels": [
            {
                "message_id": 123456,
                "channel_id": 123456,
                "supporter_role_ids": [123456],
                "categories": [
                    {
                        "label": "Support",
                        "value": "Support_0",
                        "emoji": "🛠️",
                        "description": "Allgemeine Hilfe",
                        "supporter_role_ids": null
                    }
                ],
                "title": "Support Tickets",
                "embed_desc": "Brauchst du Hilfe?",
                "embed_color": "FFD700",
                "embed_thumbnail": true,
                "created_at": "01.01.2026 12:00"
            }
        ],
        "verify_panels": [
            {
                "role_id": 123456,
                "message_id": 123456,
                "channel_id": 123456,
                "title": "✅ Verifizierung"
            }
        ],
        "selfrole_panels": [
            {
                "message_id": 123456,
                "channel_id": 123456,
                "panel_id": "12345",
                "title": "Wähle deine Rollen",
                "roles": [
                    {
                        "label": "Gamer",
                        "role_id": 123456,
                        "emoji": "🎮",
                        "description": "Für alle Gamer"
                    }
                ]
            }
        ],
        "application_panels": [
            {
                "message_id": 123456,
                "channel_id": 123456,
                "review_channel_id": 123456,
                "reviewer_role_ids": [123456],
                "title": "Staff Bewerbung",
                "questions": null
            }
        ]
    },
    "bot_presence": {
        "status": "online",
        "type": "playing",
        "text": "Bexi RP",
        "url": "https://twitch.tv/..."
    }
}
```

### ⚠️ Kritisch beim Iterieren über config

```python
# IMMER isinstance-Check, da config auch "bot_presence" als Top-Level-Key hat
for guild_id_str, data in config.items():
    if not isinstance(data, dict):
        continue
    # ...
```

### Ticket-Kategorien: `value` muss eindeutig sein

Discord verlangt eindeutige `value`-Felder in Select-Dropdowns. Beim Erstellen neuer Kategorien immer `label_INDEX` als Value verwenden:

```python
cat_count = len(panel.get("categories", []))
unique_val = (label[:90] + "_" + str(cat_count))[:100]
```

---

## 🎨 Embed-Builder

### `make_dm_embed()`

```python
embed = make_dm_embed(
    title=t("embeds","dm_ban","title"),
    description=t("embeds","dm_ban","desc"),
    color=discord.Color.red(),
    guild=interaction.guild,
    fields=[
        (t("embeds","dm_ban","f_server"), guild.name, True),
        (t("embeds","dm_ban","f_reason"), grund, False),
    ],
    jump_url=thread.jump_url,          # optional — fügt 🔗 Link-Feld hinzu
    footer_system=t("embeds","shared","footer_mod")
)
```

### `make_log_embed()`

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

## 🖱️ Wizard-System — Überblick

Alle Setup-Wizards folgen demselben Pattern:

### Pattern: Wizard starten

```python
@bot.tree.command(name="...", ...)
async def my_wizard_cmd(interaction: discord.Interaction):
    uid = interaction.user.id
    _my_wizard_state[uid] = { ... }          # State initialisieren
    embed = _build_my_embed(state, guild)    # Wizard-Embed bauen
    view  = MyWizardView(uid)                # View mit Buttons
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    _wizard_interactions[uid] = interaction  # Interaction speichern für spätere Edits
```

### Pattern: Modal-Submit → Embed aktualisieren

```python
async def on_submit(self, interaction: discord.Interaction):
    # ... State updaten ...
    await interaction.response.defer(ephemeral=True)
    _orig = _wizard_interactions.get(self.user_id)
    if _orig:
        try:
            await _orig.edit_original_response(embed=embed, view=view)
        except Exception:
            pass  # Interaction abgelaufen (>15min)
```

### Pattern: Select-Dropdown → Embed aktualisieren

```python
# Generische Helper mit refresh_fn
view = _make_role_select_view(
    user_id, "state_key", state_dict,
    placeholder_text, multi=True,
    refresh_fn=lambda uid, guild: (build_embed(state[uid], guild), MyView(uid))
)
```

Nach Auswahl ruft `WizardRoleSelect.callback` automatisch `refresh_fn` auf und aktualisiert das Wizard-Embed.

### Globale Wizard-Dicts

```python
_setup_wizard_state:      dict = {}  # Application setup
_selfrole_wizard_state:   dict = {}  # Self-role setup
_ticket_wizard_state:     dict = {}  # Ticket setup
_ticket_edit_state:       dict = {}  # Ticket edit
_status_wizard_state:     dict = {}  # Status config
_joinroles_wizard_state:  dict = {}  # Join roles
_verify_wizard_state:     dict = {}  # Verify setup
_wizard_messages:         dict = {}  # user_id -> wizard message id (veraltet, nicht mehr primär genutzt)
_wizard_interactions:     dict = {}  # user_id -> original interaction (für edit_original_response)
```

---

## 🔧 Shared Select-Helpers

### `WizardRoleSelect` — generischer Rollen-Dropdown

```python
view = _make_role_select_view(
    user_id      = uid,
    state_key    = "supporter_role_ids",   # Key im State-Dict
    state_dict   = _ticket_wizard_state,   # Das State-Dict
    placeholder  = t("selects", "wizard_pick_roles"),
    multi        = True,                   # Multi-Select
    refresh_fn   = lambda uid, guild: (embed, view)  # Wird nach Auswahl aufgerufen
)
```

### `WizardChannelSelect` — generischer Kanal-Dropdown

```python
view = _make_channel_select_view(
    user_id     = uid,
    state_key   = "review_channel_id",
    state_dict  = _setup_wizard_state,
    placeholder = t("selects", "wizard_pick_channel"),
    refresh_fn  = lambda uid, guild: (embed, view)
)
```

---

## 🎫 Ticket-System

### Ticket-Erstellungs-Flow

```
User wählt Kategorie im Dropdown
    → TicketSelect.callback()
        → Zähler erhöhen (category_counters)
        → TICKETS Kategorie erstellen falls nötig
        → Kanal für Kategorie erstellen falls nötig (category_channels gecacht)
        → Privaten Thread erstellen
        → Supporter-Rollen dem Thread hinzufügen
        → Ticket-Embed + TicketControlView senden
        → DM an Nutzer
        → Select zurücksetzen (fresh_view)
```

**Thread-Name-Format:** `{kategorie[:5]}-{id:04d}-{username}`

**Kategorie-Kanal-Name-Format:** `{kategorie-lower-kebab}-tickets`

**Kategorie `value` muss eindeutig sein** — immer `label_INDEX` als Value verwenden (Discord-Anforderung).

### Ticket-Edit-Flow

```
/ticket_edit
    → Wenn 1 Panel: direkt zum Edit-Wizard
    → Wenn mehrere Panels: TicketEditPanelSelect Dropdown
        → Panel auswählen
        → Embed-Werte aus Discord-Message laden
        → TicketEditMainView anzeigen
            → 🎨 Edit Embed Modal (Titel, Beschreibung, Farbe, Thumbnail)
            → 👥 Supporter Roles Dropdown
            → ➕ Add Category Modal
            → 🗑️ Remove Category Dropdown
            → ✅ Save → config speichern + Discord-Message editieren
```

---

## 📋 Application-System

### Bewerbungs-Flow

```
User klickt "Jetzt bewerben"
    → ApplicationModal (Step 1/N, max 4 Fragen pro Schritt)
        → ApplicationContinueView (Weiter/Abbrechen)
            → Nächster Schritt...
                → _submit_application()
                    → sofort interaction.response.send_message() (10062-Fix!)
                    → Privaten Thread im Review-Channel erstellen
                    → Reviewer-Rollen-Mitglieder zum Thread hinzufügen
                    → Review-Embeds senden + ApplicationReviewView
                    → save_open_app() → open_applications.json
                    → DM an Bewerber
```

**Wichtig:** Bewerber wird NICHT beim Einreichen zum Thread hinzugefügt — erst wenn ein Teammitglied ❓ klickt.

### Review-View Buttons

- ✅ Accept → DM an Bewerber, Thread locked+archived, delete_open_app()
- ❌ Decline → DM an Bewerber, Thread locked+archived, delete_open_app()
- ❓ Question → Reviewer + Bewerber zum Thread hinzufügen, DM mit Thread-Link an Bewerber

### Application-Setup-Wizard

```
/setup_application
    → _setup_wizard_state[uid] initialisieren (questions=None = Default)
    → AppSetupMainView anzeigen
        → ✏️ Edit Info Modal (Titel, Beschreibung)
        → 📢 Review Channel Dropdown
        → 👥 Reviewer Role Dropdown (Multi)
        → ➕ Add Questions Modal (Label, Placeholder, Min-Length, Style)
        → 📂 Add Section Modal (Name, Beschreibung)
        → ✅ Default Questions (29 Fragen aus default_application.json)
        → 🗑️ Clear Questions
        → ↩️ Remove Last
        → 👁️ Preview
        → 🚀 Finish & Create
```

**Fragen-Struktur:**

```python
{
    "label":       str,          # max 45 Zeichen
    "placeholder": str,          # max 100 Zeichen
    "style":       "paragraph" | "short",
    "required":    True,
    "min_length":  int,          # 0 = kein Limit — wird als TextInput.min_length gesetzt!
    "section":     {"name": str, "desc": str} | None
}
```

**`min_length` wird direkt als `TextInput.min_length` übergeben** — Discord blockt das Absenden nativ, kein Code-seitiges Validieren nötig.

**`QUESTIONS_PER_STEP = 4`** — Fragen werden in 4er-Gruppen aufgeteilt.

### `default_application.json`

Editierbar ohne Code-Änderung. Struktur:

```json
{
    "_info": { "description": "...", "version": "1.0" },
    "panel": { "title": "...", "description": "..." },
    "questions": [
        {
            "label": "Roblox Username",
            "placeholder": "...",
            "style": "short",
            "required": true,
            "min_length": 0,
            "section": { "name": "👤 Personal Info", "desc": "..." }
        }
    ]
}
```

---

## 🎭 Self-Role-System

### Self-Role-Setup-Wizard

```
/selfrole_create
    → SelfRoleSetupMainView
        → ✏️ Edit Info Modal (Titel, Beschreibung, Farbe)
        → ➕ Add Role → SelfRoleAddRoleSelect (Discord RoleSelect Dropdown)
            → SelfRoleSetupRoleDetailsModal (Label, Emoji, Beschreibung)
        → 🗑️ Remove Role → SelfRoleRemoveRoleSelect Dropdown
        → 🚀 Finish → SelfRoleView erstellen + in config speichern
```

**Rollen-Struktur:**

```python
{
    "label":       str,   # Button-Text
    "role_id":     int,
    "emoji":       str | None,
    "description": str | None
}
```

---

## ✅ Verify-System

### Verify-Setup-Wizard

```
/setup_verify
    → _verify_wizard_state[uid] initialisieren
    → VerifyWizardMainView
        → ✏️ Edit Info Modal (Titel, Beschreibung)
        → 🎭 Verify Role Dropdown (RoleSelect)
        → 🎨 Edit Embed Modal (Farbe Hex, Thumbnail yes/no)
        → 👁️ Preview
        → 🚀 Finish → VerifyView erstellen + in config speichern
```

**Config-Struktur Verify-Panel:**

```json
{
    "role_id": 123456,
    "message_id": 123456,
    "channel_id": 123456,
    "title": "✅ Verifizierung"
}
```

---

## 🤖 Status-Wizard

```
/status_config
    → StatusWizardView
        → 🟢 Status Button → StatusSelect Dropdown (online/idle/dnd/invisible)
        → 🎮 Activity Button → ActivitySelect Dropdown (playing/streaming/listening/watching)
        → ✏️ Text/URL Button → StatusTextModal (Text + Stream-URL)
        → ✅ Apply → bot.change_presence() + config["bot_presence"] speichern
```

---

## 🗑️ Delete-Wizard

```
/delete
    → DeleteTypeView (Dropdown: welchen Typ löschen?)
        → Ticket Panels / Self-Role Panels / Application Panels / Verify Panels / Join Roles
        → DeletePanelView (Dropdown: welches Panel?)
            → _delete_panel() → config entfernen + Discord-Message löschen
            → DeleteBackView (Weiteres löschen? / Fertig)
```

### `_delete_panel()` Logic

```python
async def _delete_panel(guild, config, guild_id, panel_type, panel) -> bool:
    # 1. Aus config entfernen + speichern
    # 2. Discord-Message löschen:
    #    - Mit channel_id: direkt fetchen
    #    - Ohne channel_id (alte Panels): alle Text-Channels durchsuchen
    # Returns True bei Erfolg, False wenn Message nicht gelöscht werden konnte
```

---

## 🔄 Persistent Views (nach Bot-Neustart)

Alle persistent Views werden in `setup_hook` registriert:

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

    # Application Panels
    self.add_view(ApplicationPanelView(panel_index=idx))

    # Offene Bewerbungen (aus open_applications.json)
    self.add_view(ApplicationReviewView(
        applicant_id=entry["applicant_id"],
        thread_id=entry["thread_id"],
        review_channel_id=entry["review_channel_id"]
    ))
```

**`open_applications.json`** speichert offene Bewerbungs-Threads damit Accept/Decline/Question Buttons nach einem Neustart weiter funktionieren. Wird beim Abschließen einer Bewerbung gelöscht.

---

## ⚠️ Bekannte Fallstricke & Wichtige Regeln

### 1. Discord Interaction-Regeln

| Situation | Richtige Methode |
|---|---|
| Button-Callback | `interaction.response.edit_message()` |
| Modal-Submit → Wizard-Embed aktualisieren | `interaction.response.defer()` + `_wizard_interactions[uid].edit_original_response()` |
| Select-Callback → Wizard-Embed aktualisieren | `interaction.response.edit_message()` (schließt Select-Msg) + `_orig.edit_original_response()` via `refresh_fn` |
| Nach `send_modal()` | Modal-`on_submit` kann `edit_message` NICHT auf die ursprüngliche Nachricht aufrufen |
| Ephemere Nachrichten editieren | Nur über die **originale Command-Interaction** via `edit_original_response()` — 15min TTL |

### 2. `_wizard_interactions` — das zentrale Pattern

```python
# Beim Wizard-Start:
await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
_wizard_interactions[uid] = interaction   # MUSS gesetzt werden!

# In Modal on_submit:
_orig = _wizard_interactions.get(self.user_id)
if _orig:
    try:
        await _orig.edit_original_response(embed=embed, view=view)
    except Exception:
        pass  # Interaction >15min alt
```

### 3. Ticket-Kategorie `value` muss eindeutig sein

```python
# RICHTIG:
cat_count = len(panel.get("categories", []))
unique_val = (label[:90] + "_" + str(cat_count))[:100]
panel["categories"].append({"label": label, "value": unique_val, ...})

# FALSCH:
panel["categories"].append({"label": label, "value": label, ...})  # Kollision möglich!
```

### 4. `isinstance`-Check beim Config-Iterieren

```python
for guild_id_str, data in config.items():
    if not isinstance(data, dict):  # "bot_presence" ist auch ein Top-Level-Key!
        continue
```

### 5. `t()` bei Command-Dekoratoren

```python
# ❌ GEHT NICHT — wird zur Importzeit ausgewertet
@app_commands.describe(grund=t("commands","ban","params","grund"))

# ✅ RICHTIG — tp() liest direkt aus _lang_cache
@app_commands.describe(grund=tp("ban","grund"))
```

### 6. Button-Labels in `__init__` setzen

Discord-Decorator-Labels werden zur **Importzeit** ausgewertet — `t()` funktioniert dort nicht:

```python
class MyView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.my_button.label = t("buttons", "my_button")  # Methodenname!

    @discord.ui.button(label="Placeholder", ...)
    async def my_button(self, interaction, button):
        ...
```

### 7. `min_length` direkt in TextInput setzen

```python
# RICHTIG — Discord blockt Absenden nativ
ti = discord.ui.TextInput(
    label="...",
    min_length=min_len if min_len > 0 else None,
    max_length=1024
)

# FALSCH — führt zu Bugs bei geschlossenen Modals
# Manuelle Validierung in on_submit mit response.send_message()
```

### 8. Supporter-Rolle und `supporter_role_ids` vs `supporter_role_id`

Ältere Panel-Einträge können `supporter_role_id` (singular) haben. Kompatibilitäts-Fallback in `setup_hook`:

```python
supp_ids = t_panel.get("supporter_role_ids")
if not supp_ids:
    old_id = t_panel.get("supporter_role_id")
    supp_ids = [old_id] if old_id else []
```

### 9. Bewerbungen: sofort antworten bevor async-Operationen

```python
# RICHTIG — vermeidet Discord 10062 "Unknown Interaction" Error
await interaction.response.send_message(t("success", "application_submitted"), ephemeral=True)
# DANN erst: Thread erstellen, Embeds senden, etc.
```

---

## ➕ Neues Feature hinzufügen — Checkliste

```
[ ] Slash-Command mit @bot.tree.command definieren
[ ] Beschreibung in language/de.json und language/en.json unter "commands" eintragen
[ ] Parameter unter "commands.command_name.params" eintragen
[ ] Alle neuen Texte in "embeds", "errors", "success", "buttons", "modals", "selects" eintragen
[ ] In BEIDE JSON-Dateien eintragen (de + en)!
[ ] Falls Wizard: _wizard_interactions[uid] = interaction beim Start setzen
[ ] Falls Wizard: edit_original_response Pattern verwenden (nicht followup.edit_message)
[ ] Falls persistent: View in setup_hook registrieren
[ ] Falls Button-Labels dynamisch: in __init__ via self.methode.label = t(...) setzen
[ ] Falls Ticket-Kategorien: unique value verwenden (label_INDEX)
[ ] Syntax-Check: python3 -c "import ast; ast.parse(open('bot.py').read()); print('OK')"
[ ] JSON-Check: python3 -c "import json; [json.load(open(f'language/{l}.json')) for l in ['de','en']]; print('OK')"
```

---

## 🔍 Debugging

### Häufige Fehler

| Fehler | Ursache | Lösung |
|---|---|---|
| `[missing: embeds.x.y]` | Key fehlt in JSON | Key in beide JSON-Dateien eintragen |
| `[not-str: embeds.x.y]` | Key ist kein String (z.B. dict) | Tiefe im `t()`-Aufruf prüfen |
| `AttributeError: has no attribute 'xyz'` | Button-Attributname falsch | Muss der **Methoden**name sein |
| `404 Unknown Webhook` | `edit_original_response` nach >15min | Interaction TTL abgelaufen — nichts tun |
| `400 option value already used` | Duplicate `value` in Select-Options | unique_val mit Index verwenden |
| `Unknown Interaction (10062)` | Zu spät geantwortet | Sofort `send_message` oder `defer` aufrufen |
| Persistent View lädt nicht | Nicht in setup_hook registriert | `add_view()` in setup_hook |
| Wizard-Embed aktualisiert sich nicht | `_wizard_interactions[uid]` nicht gesetzt | Interaction beim Command-Start speichern |

### Schnell-Tests

```bash
# Syntax-Check
python3 -c "import ast; ast.parse(open('bot.py').read()); print('OK')"

# JSON-Validierung
python3 -c "import json; [json.load(open(f'language/{l}.json')) for l in ['de','en']]; print('OK')"

# Alle fehlenden Keys prüfen (sucht nach [missing: ...] Pattern)
grep "\[missing:" logs/
```

---

## 🐳 Docker-Deployment

```yaml
# Docker/compose.yaml
services:
  discord-bot:
    image: pilzithegoat/bexi_bot:VERSION
    container_name: bexi-bot
    restart: unless-stopped
    environment:
      - DISCORD_TOKEN=${Bot_Token}
      - DISCORD_GUILD_ID=${Guild_ID}
      - TZ=Europe/Berlin
    platform: linux/arm64   # Raspberry Pi — für x86 entfernen
    volumes:
      - ./configs:/app/configs        # Configs persistent mounten!
      - ./language:/app/language
```

**Neue Version deployen:**

```bash
docker pull pilzithegoat/bexi_bot:NEU
docker compose up -d
```

**Wichtig:** `configs/` als Volume mounten, sonst gehen alle Panel-Daten beim Update verloren.

---

## 📦 Dependencies (`requirements.txt`)

```
discord.py          # Discord API
discord.py[voice]   # Voice-Support
PyNaCl              # Voice-Verschlüsselung
ffmpeg              # Audio (Support-Musik)
static-ffmpeg       # Portables FFmpeg (kein System-Install nötig)
python-dotenv       # .env Datei laden
```

---

## 📝 Entwicklungskonventionen

- **Sprache:** Alle Kommentare und Variablennamen auf Englisch oder Deutsch — gemischt ist ok
- **Embed-Farben:** Konsistent: Grün = Erfolg, Rot = Fehler/Ban, Orange = Warnung, Blurple = Info, Gold = Tickets
- **Ephemeral:** Wizard-Nachrichten immer `ephemeral=True`
- **Error-Handling:** Niemals `except Exception: pass` ohne Kommentar — zumindest `print()` für Debugging
- **Config speichern:** Immer `save_config(config)` nach Änderungen aufrufen
- **IDs:** Immer als `int` in Discord-Calls, als `str` in config-Keys und JSON