#English
<div align="center">

# 🤖 Util

**A fully-featured Discord bot for roleplay servers and normal servers**

Ticket System · Applications · Moderation · Verification · Self-Roles · Multilingual

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ARM64%20%2F%20x86-2496ED?style=for-the-badge&logo=docker&logoColor=white)](Docker/)

<br/>

**🇬🇧 English** · [🇩🇪 Deutsch](#Deutsch)

</div>

---

## ✨ Features

<table>
<tr>
<td>

**🎫 Ticket System**
Dropdown panels with categories, private threads, Claim & Close

**📋 Application System**
Multi-step forms, thread-based review, Accept / Decline / Question

**🛡️ Moderation**
Ban, Kick, Timeout, Warn — with DM & log channel

**✅ Verification**
Configurable embed with color, thumbnail & role

**🎭 Self-Roles**
Dropdown with checkmarks — select multiple roles at once

**🔗 Link Whitelist**
Automatic deletion of non-whitelisted links

</td>
<td>

**👋 Welcome**
Welcome embed with account age & member number

**🎵 Support Music**
Automatic music in waiting room voice channel

**🌐 Multilingual**
Fully in 🇩🇪 German & 🇬🇧 English, configurable per server

**🗑️ Delete Wizard**
Delete all panel types via interactive dropdowns

**⚙️ Status Wizard**
Configure bot status & activity via dropdowns

**🏆 Pioneer Role**
Automatically assigned to the first 100 members

</td>
</tr>
</table>

> **All setup processes use visual wizards with dropdowns and modals — no manual ID input required.**

---

## 🚀 Add to Your Server

Replace `YOUR_ID` with your bot's **Application ID** from the [Discord Developer Portal](https://discord.com/developers/applications):

```
https://discord.com/oauth2/authorize?client_id=YOUR_ID&permissions=9175529923606&integration_type=0&scope=bot+applications.commands
```

> Your Application ID can be found under **General Information** in the Developer Portal.

---

## 📖 Table of Contents

- [Features](#-features)
- [Add to Server](#-add-to-your-server)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
  - [Method 1: Python (local)](#method-1-python-local)
  - [Method 2: Docker (recommended)](#method-2-docker-recommended)
  - [Method 3: Raspberry Pi](#method-3-raspberry-pi)
- [Discord Bot Setup](#-discord-bot-setup)
- [Initial Setup](#-initial-setup)
- [Commands](#-commands)
- [Feature Details](#-feature-details)
- [Config Files](#-config-files)
- [Required Permissions](#-required-permissions)
- [License](#-license)

---

## 📋 Prerequisites

| Requirement | Version | Note |
|---|---|---|
| Python | 3.11+ | For local installation |
| Docker + Docker Compose | latest | For Docker installation |
| Discord Bot Token | — | See [Bot Setup](#-discord-bot-setup) |
| FFmpeg | any | Optional, only for support music |

---

## 🔧 Installation

### Method 1: Python (local)

**1. Clone the repository**

```bash
git clone https://github.com/pilzithegoat/bexi_bot.git
cd bexi_bot
```

**2. Create a virtual environment** *(recommended)*

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Create `.env` file**

```env
DISCORD_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here
```

**5. Start the bot**

```bash
python bot.py
```

---

### Method 2: Docker *(recommended)*

> Easiest option — no Python installation required.

**1. Clone the repository**

```bash
git clone https://github.com/pilzithegoat/bexi_bot.git
cd bexi_bot/Docker
```

**2. Create `.env` file**

```env
Bot_Token=your_bot_token_here
Guild_ID=your_server_id_here
```

**3. Start**

```bash
docker compose up -d
```

**Useful commands:**

```bash
docker compose logs -f    # View live logs
docker compose down       # Stop the bot
docker compose restart    # Restart the bot
```

> **Note:** The `configs/` folder is automatically mounted as a volume so all panel settings persist across updates.

---

### Method 3: Raspberry Pi

The Docker image is optimized for **ARM64** and runs natively on Raspberry Pi 4 & 5.

```bash
git clone https://github.com/pilzithegoat/bexi_bot.git
cd bexi_bot/Docker

echo "Bot_Token=your_token" > .env
echo "Guild_ID=your_guild_id" >> .env

docker compose up -d
```

> For x86 systems, remove the `platform: linux/arm64` line from `compose.yaml`.

---

## 🤖 Discord Bot Setup

### 1. Create Application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"** — enter a name → confirm
3. Navigate to **"Bot"** in the left sidebar
4. Click **"Add Bot"** → confirm

### 2. Copy Your Token

1. Under **Bot** → click **"Reset Token"**
2. Copy the token → paste it into your `.env` file

> ⚠️ **Never share your token or commit it to Git!**

### 3. Enable Privileged Intents

Under **Bot** → **Privileged Gateway Intents**, enable all three:

- ✅ Presence Intent
- ✅ Server Members Intent
- ✅ Message Content Intent

### 4. Invite the Bot

Use the invite link from [Add to Your Server](#-add-to-your-server) — replace `YOUR_ID` with your **Application ID** (found under **General Information**).

---

## ⚙️ Initial Setup

After the bot is online, run these commands in the recommended order:

```
/set_language          → Choose 🇩🇪 German or 🇬🇧 English
/set_log_channel       → Channel for all moderation logs
/set_welcome_channel   → Channel for welcome messages
/setup_verify          → Create verification panel
/setup_tickets         → Create ticket panel with categories
/setup_application     → Create application panel   (optional)
/selfrole_create       → Create self-role panel      (optional)
/set_join_roles        → Auto-join roles             (optional)
/set_waiting_room      → Support music channel       (optional)
```

---

## 📋 Commands

### 🎫 Tickets

| Command | Description | Permission |
|---|---|---|
| `/setup_tickets` | Start interactive ticket wizard | Administrator |
| `/ticket_edit` | Edit existing panel (embed, categories, roles) | Administrator |

### 📋 Applications

| Command | Description | Permission |
|---|---|---|
| `/setup_application` | Start application panel wizard | Administrator |

### 🎭 Self-Roles

| Command | Description | Permission |
|---|---|---|
| `/selfrole_create` | Start self-role panel wizard | Administrator |
| `/selfrole_list` | Show all active self-role panels | Administrator |

### ✅ Verification

| Command | Description | Permission |
|---|---|---|
| `/setup_verify` | Start verify panel wizard | Administrator |

### 🛡️ Moderation

| Command | Parameters | Permission |
|---|---|---|
| `/ban` | `user`, `reason` | Ban Members |
| `/kick` | `user`, `reason` | Kick Members |
| `/timeout` | `user`, `minutes`, `reason` | Moderate Members |
| `/warn` | `user`, `reason` | Moderate Members |
| `/warn_edit` | `user`, `count` | Moderate Members |
| `/userinfo` | `user` (optional) | Everyone |

### 🔗 Whitelist

| Command | Parameters | Description |
|---|---|---|
| `/whitelist` | `action`, `domain` | Manage link whitelist (add / remove / list) |

### ⚙️ Server Settings

| Command | Description | Permission |
|---|---|---|
| `/set_language` | Switch language (🇩🇪 / 🇬🇧) | Administrator |
| `/set_log_channel` | Set log channel | Administrator |
| `/set_welcome_channel` | Set welcome channel | Administrator |
| `/set_waiting_room` | Set support music channel | Administrator |
| `/set_join_roles` | Auto-join roles wizard | Administrator |
| `/status_config` | Configure bot status & activity | Administrator |
| `/setup_pioneer_role` | Assign role to first 100 members | Administrator |
| `/delete` | Delete panels via interactive wizard | Administrator |
| `/ping` | Show bot latency | Everyone |

---

## 🔍 Feature Details

### 🎫 Ticket System

The wizard guides through all steps: title, supporter roles (dropdown), categories with emoji & description, embed styling (hex color, description, thumbnail), and a live preview before creating.

When a user selects a category, a **private thread** is automatically created. Supporters can **claim** (take ownership) or **close** tickets with a reason. The creator receives a DM for every action.

Use `/ticket_edit` to update any existing panel — changes apply immediately to the Discord message.

---

### 📋 Application System

Applications are split into steps of 4 questions each. Minimum lengths are enforced natively in the input field. After submission, a **private thread** is created in the configured review channel. Reviewers can Accept, Decline, or ask a follow-up Question — the applicant only gets access to the thread when a question is asked.

**Customize the default questions** in `configs/default_application.json`:

```json
{
  "questions": [
    {
      "label": "Roblox Username",
      "placeholder": "Your username",
      "style": "short",
      "required": true,
      "min_length": 0,
      "section": {
        "name": "👤 Personal Info",
        "desc": "Basic information about you"
      }
    }
  ]
}
```

| Field | Values | Description |
|---|---|---|
| `style` | `short` / `paragraph` | Single line or multiline input |
| `min_length` | `0`–`1023` | Minimum characters (0 = no limit) |
| `section` | `{name, desc}` / `null` | Groups questions under a heading |

---

### 🎭 Self-Roles

Users see a single dropdown menu listing all available roles. Roles they already have are marked with **✅** and pre-selected. Multiple roles can be toggled at once — checkmarks remain correct when the dropdown is reopened.

---

### ⚙️ Status Wizard

Configure the bot's online presence without typing — select the status (Online / Idle / DnD / Invisible) and activity type (Playing / Streaming / Listening / Watching) via dropdowns, then set the display text via modal. Settings are restored automatically after a restart.

---

## 📁 Config Files

All files are in the `configs/` folder and created automatically on first run.

| File | Content |
|---|---|
| `config.json` | Server configs — panels, warn counts, channel IDs |
| `whitelist.json` | Allowed link domains |
| `open_applications.json` | Open application threads (button persistence after restart) |
| `default_application.json` | Default application form — edit freely |

> All buttons and panels remain fully functional after a bot restart — no reconfiguration needed.

---

## 🔒 Required Permissions

```
✅ Manage Roles              Assign roles (Verify, Self-Roles, Join-Roles)
✅ Manage Channels           Create ticket channels
✅ Manage Threads            Manage ticket threads
✅ Create Private Threads    Application review threads
✅ Ban Members               /ban
✅ Kick Members              /kick
✅ Moderate Members          /timeout, /warn
✅ Send Messages             General messaging
✅ Send Messages in Threads  Ticket threads
✅ Embed Links               Send embeds
✅ Manage Messages           Link whitelist
✅ Read Message History      Fetch panel messages
✅ Connect + Speak           Support music (optional)
```

---

## 📝 License

This project is licensed under the [MIT License](LICENSE).

---
---
---
#Deutsch

<div align="center">

# 🤖 Util Bot

**Ein vollständiger Discord-Bot für Roleplay-Server**

Ticket-System · Bewerbungen · Moderation · Verifizierung · Self-Roles · Mehrsprachig

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ARM64%20%2F%20x86-2496ED?style=for-the-badge&logo=docker&logoColor=white)](Docker/)

<br/>

[🇬🇧 English](#-English) · **🇩🇪 Deutsch**

</div>

---

## ✨ Features

<table>
<tr>
<td>

**🎫 Ticket-System**
Dropdown-Panels mit Kategorien, private Threads, Claim & Close

**📋 Bewerbungssystem**
Mehrstufige Formulare, Thread-Review, Accept / Decline / Rückfrage

**🛡️ Moderation**
Ban, Kick, Timeout, Warn — mit DM & Log-Kanal

**✅ Verifizierung**
Konfigurierbares Embed mit Farbe, Thumbnail & Rolle

**🎭 Self-Roles**
Dropdown mit Häkchen — mehrere Rollen gleichzeitig wählen

**🔗 Link-Whitelist**
Automatisches Löschen nicht erlaubter Links

</td>
<td>

**👋 Willkommen**
Begrüßungs-Embed mit Account-Alter & Mitglieder-Nummer

**🎵 Support-Musik**
Automatische Musik im Warteraum-Sprachkanal

**🌐 Mehrsprachig**
Vollständig auf 🇩🇪 Deutsch & 🇬🇧 Englisch, pro Server

**🗑️ Delete-Wizard**
Alle Panels bequem über Dropdowns löschen

**⚙️ Status-Wizard**
Bot-Status & Aktivität per Dropdown konfigurieren

**🏆 Pioneer-Rolle**
Automatisch an die ersten 100 Mitglieder vergeben

</td>
</tr>
</table>

> **Alle Einrichtungen funktionieren über visuelle Wizards mit Dropdowns und Modals — kein Eintippen von IDs nötig.**

---

## 🚀 Bot zum Server hinzufügen

Ersetze `YOUR_ID` mit der **Application ID** deines Bots aus dem [Discord Developer Portal](https://discord.com/developers/applications):

```
https://discord.com/oauth2/authorize?client_id=YOUR_ID&permissions=9175529923606&integration_type=0&scope=bot+applications.commands
```

> Die Application ID findest du unter **General Information** im Developer Portal.

---

## 📖 Inhaltsverzeichnis

- [Features](#-features-1)
- [Bot hinzufügen](#-bot-zum-server-hinzufügen)
- [Voraussetzungen](#-voraussetzungen)
- [Installation](#-installation-1)
  - [Methode 1: Python (lokal)](#methode-1-python-lokal)
  - [Methode 2: Docker (empfohlen)](#methode-2-docker-empfohlen)
  - [Methode 3: Raspberry Pi](#methode-3-raspberry-pi)
- [Bot einrichten](#-discord-bot-einrichten)
- [Ersteinrichtung](#-ersteinrichtung)
- [Commands](#-commands-1)
- [Features im Detail](#-features-im-detail)
- [Konfigurationsdateien](#-konfigurationsdateien)
- [Berechtigungen](#-berechtigungen)
- [Lizenz](#-lizenz)

---

## 📋 Voraussetzungen

| Anforderung | Version | Anmerkung |
|---|---|---|
| Python | 3.11+ | Für lokale Installation |
| Docker + Docker Compose | aktuell | Für Docker-Installation |
| Discord Bot Token | — | Siehe [Bot einrichten](#-discord-bot-einrichten) |
| FFmpeg | beliebig | Optional, nur für Support-Musik |

---

## 🔧 Installation

### Methode 1: Python (lokal)

**1. Repository klonen**

```bash
git clone https://github.com/pilzithegoat/bexi_bot.git
cd bexi_bot
```

**2. Virtuelle Umgebung erstellen** *(empfohlen)*

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

**3. Abhängigkeiten installieren**

```bash
pip install -r requirements.txt
```

**4. `.env` Datei erstellen**

```env
DISCORD_TOKEN=dein_bot_token_hier
DISCORD_GUILD_ID=deine_server_id_hier
```

**5. Bot starten**

```bash
python bot.py
```

---

### Methode 2: Docker *(empfohlen)*

> Am einfachsten — keine Python-Installation nötig.

**1. Repository klonen**

```bash
git clone https://github.com/pilzithegoat/bexi_bot.git
cd bexi_bot/Docker
```

**2. `.env` Datei erstellen**

```env
Bot_Token=dein_bot_token_hier
Guild_ID=deine_server_id_hier
```

**3. Starten**

```bash
docker compose up -d
```

**Nützliche Befehle:**

```bash
docker compose logs -f    # Live-Logs anzeigen
docker compose down       # Bot stoppen
docker compose restart    # Bot neustarten
```

> **Hinweis:** Der `configs/`-Ordner wird automatisch als Volume gemountet — alle Einstellungen bleiben bei Updates erhalten.

---

### Methode 3: Raspberry Pi

Das Docker-Image ist für **ARM64** optimiert und läuft nativ auf dem Raspberry Pi 4 & 5.

```bash
git clone https://github.com/pilzithegoat/bexi_bot.git
cd bexi_bot/Docker

echo "Bot_Token=dein_token" > .env
echo "Guild_ID=deine_guild_id" >> .env

docker compose up -d
```

> Für x86-Systeme die `platform: linux/arm64` Zeile in `compose.yaml` entfernen.

---

## 🤖 Discord Bot einrichten

### 1. Application erstellen

1. Öffne das [Discord Developer Portal](https://discord.com/developers/applications)
2. Klicke **"New Application"** — Namen eingeben → bestätigen
3. Gehe zu **"Bot"** im linken Menü
4. Klicke **"Add Bot"** → bestätigen

### 2. Token kopieren

1. Unter **Bot** → **"Reset Token"** klicken
2. Token kopieren → in die `.env` Datei eintragen

> ⚠️ **Den Token niemals veröffentlichen oder in Git commiten!**

### 3. Privileged Intents aktivieren

Unter **Bot** → **Privileged Gateway Intents** alle drei aktivieren:

- ✅ Presence Intent
- ✅ Server Members Intent
- ✅ Message Content Intent

### 4. Bot einladen

Einlade-Link aus [Bot zum Server hinzufügen](#-bot-zum-server-hinzufügen) verwenden — `YOUR_ID` durch die **Application ID** ersetzen (zu finden unter **General Information**).

---

## ⚙️ Ersteinrichtung

Nach dem Start empfiehlt sich folgende Reihenfolge:

```
/set_language          → 🇩🇪 Deutsch oder 🇬🇧 English wählen
/set_log_channel       → Kanal für alle Moderations-Logs
/set_welcome_channel   → Kanal für Willkommensnachrichten
/setup_verify          → Verifizierungs-Panel erstellen
/setup_tickets         → Ticket-Panel mit Kategorien erstellen
/setup_application     → Bewerbungs-Panel erstellen  (optional)
/selfrole_create       → Self-Role-Panel erstellen    (optional)
/set_join_roles        → Auto-Join-Rollen             (optional)
/set_waiting_room      → Support-Musik-Kanal          (optional)
```

---

## 📋 Commands

### 🎫 Tickets

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/setup_tickets` | Interaktiven Ticket-Wizard starten | Administrator |
| `/ticket_edit` | Bestehendes Panel bearbeiten | Administrator |

### 📋 Bewerbungen

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/setup_application` | Bewerbungs-Panel-Wizard starten | Administrator |

### 🎭 Self-Roles

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/selfrole_create` | Self-Role-Panel-Wizard starten | Administrator |
| `/selfrole_list` | Alle aktiven Self-Role-Panels anzeigen | Administrator |

### ✅ Verifizierung

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/setup_verify` | Verify-Panel-Wizard starten | Administrator |

### 🛡️ Moderation

| Command | Parameter | Berechtigung |
|---|---|---|
| `/ban` | `nutzer`, `grund` | Ban Members |
| `/kick` | `nutzer`, `grund` | Kick Members |
| `/timeout` | `nutzer`, `minuten`, `grund` | Moderate Members |
| `/warn` | `nutzer`, `grund` | Moderate Members |
| `/warn_edit` | `nutzer`, `anzahl` | Moderate Members |
| `/userinfo` | `nutzer` (optional) | Jeder |

### 🔗 Whitelist

| Command | Parameter | Beschreibung |
|---|---|---|
| `/whitelist` | `aktion`, `domain` | Link-Whitelist verwalten (hinzufügen / entfernen / anzeigen) |

### ⚙️ Server-Einstellungen

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/set_language` | Sprache umschalten (🇩🇪 / 🇬🇧) | Administrator |
| `/set_log_channel` | Log-Kanal festlegen | Administrator |
| `/set_welcome_channel` | Willkommens-Kanal festlegen | Administrator |
| `/set_waiting_room` | Warteraum für Support-Musik | Administrator |
| `/set_join_roles` | Auto-Join-Rollen Wizard | Administrator |
| `/status_config` | Bot-Status & Aktivität konfigurieren | Administrator |
| `/setup_pioneer_role` | Erste 100 Mitglieder mit Rolle versehen | Administrator |
| `/delete` | Panels aller Typen über Wizard löschen | Administrator |
| `/ping` | Bot-Latenz anzeigen | Jeder |

---

## 🔍 Features im Detail

### 🎫 Ticket-System

Der Wizard führt durch alle Schritte: Titel, Supporter-Rollen (Dropdown), Kategorien mit Emoji & Beschreibung, Embed gestalten (Hex-Farbe, Beschreibung, Thumbnail), Live-Vorschau.

Nutzer wählen eine Kategorie → **privater Thread** wird automatisch erstellt. Supporter können **claimen** (übernehmen) oder **schließen** (mit Begründung). Der Ersteller bekommt bei jeder Aktion eine DM.

Mit `/ticket_edit` lassen sich bestehende Panels vollständig anpassen — Änderungen werden sofort auf die Discord-Nachricht übernommen.

---

### 📋 Bewerbungssystem

Mehrstufig (4 Fragen pro Schritt), Mindestlängen werden direkt im Eingabefeld erzwungen. Nach dem Einreichen wird ein **privater Thread** im Review-Channel erstellt. Bewerber erhalten erst Zugang wenn das Team eine Rückfrage stellt.

**Standard-Fragen anpassen** (`configs/default_application.json`):

```json
{
  "questions": [
    {
      "label": "Roblox Username",
      "placeholder": "Dein Nutzername",
      "style": "short",
      "required": true,
      "min_length": 0,
      "section": {
        "name": "👤 Persönliche Daten",
        "desc": "Grundlegende Informationen"
      }
    }
  ]
}
```

| Feld | Werte | Beschreibung |
|---|---|---|
| `style` | `short` / `paragraph` | Einzeiler oder Mehrzeileneingabe |
| `min_length` | `0`–`1023` | Mindestzeichen (0 = kein Limit) |
| `section` | `{name, desc}` / `null` | Gruppiert Fragen unter einer Überschrift |

---

### 🎭 Self-Roles

Nutzer sehen ein einziges Dropdown mit allen verfügbaren Rollen. Bereits vorhandene Rollen sind mit **✅** vorausgewählt. Mehrere Rollen gleichzeitig an- und abhaken — Häkchen bleiben beim nächsten Öffnen korrekt gesetzt.

---

### ⚙️ Status-Wizard

Bot-Präsenz ohne Tippen konfigurieren: Online-Status (Online / Idle / DnD / Invisible) und Aktivitätstyp (Playing / Streaming / Listening / Watching) per Dropdown, Text per Modal. Einstellungen werden nach einem Neustart automatisch wiederhergestellt.

---

## 📁 Konfigurationsdateien

Alle Configs liegen im `configs/`-Ordner und werden beim ersten Start automatisch erstellt.

| Datei | Inhalt |
|---|---|
| `config.json` | Server-Konfigurationen — Panels, Warn-Counts, Kanal-IDs |
| `whitelist.json` | Erlaubte Link-Domains |
| `open_applications.json` | Offene Bewerbungs-Threads (Button-Persistenz nach Neustart) |
| `default_application.json` | Standard-Bewerbungsformular — frei editierbar |

> Alle Buttons und Panels bleiben nach einem Neustart vollständig funktionsfähig — keine erneute Einrichtung nötig.

---

## 🔒 Berechtigungen

```
✅ Manage Roles              Rollen vergeben (Verify, Self-Roles, Join-Roles)
✅ Manage Channels           Ticket-Kanäle erstellen
✅ Manage Threads            Ticket-Threads verwalten
✅ Create Private Threads    Bewerbungs-Review-Threads
✅ Ban Members               /ban
✅ Kick Members              /kick
✅ Moderate Members          /timeout, /warn
✅ Send Messages             Allgemein
✅ Send Messages in Threads  Ticket-Threads
✅ Embed Links               Embeds senden
✅ Manage Messages           Link-Whitelist
✅ Read Message History      Panel-Nachrichten abrufen
✅ Connect + Speak           Support-Musik (optional)
```

---

## 📝 Lizenz

Dieses Projekt steht unter der [MIT License](LICENSE).

---

<div align="center">

Made with ❤️ by **p1lzi**

</div>
