# 🇬🇧 English
<div align="center">

# 🤖 Bexi Bot

**A fully-featured Discord bot for roleplay servers and communities**

Ticket System · Applications · Moderation · Verification · Self-Roles · Embed Generator · Audit Log · Multilingual

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![Version](https://img.shields.io/badge/Version-2.0.0-57F287?style=for-the-badge)](https://github.com/pilzithegoat/bexi_bot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ARM64%20%2F%20x86-2496ED?style=for-the-badge&logo=docker&logoColor=white)](Docker/)

<br/>

**🇬🇧 English** · [🇩🇪 Deutsch](#-deutsch)

</div>

---

## ✨ Features

<table>
<tr>
<td>

**🎫 Ticket System**
Dropdown panels with categories, private threads, Claim & Close

**📋 Application System**
Multi-step forms with sections, thread-based review, Accept / Decline / Question

**🛡️ Moderation**
Ban, Kick, Timeout, Warn — with DM & log channel

**✅ Verification**
Configurable embed with color, thumbnail & role

**🎭 Self-Roles**
Dropdown with checkmarks — select multiple roles at once

**🎨 Embed Generator**
Full embed builder: fields, images, link buttons OR dropdown menus

</td>
<td>

**👤 Admin Panel**
UserSelect dropdown → instant user info + Timeout / Warn / Kick / Ban + Chat management

**📋 Audit Log**
SQLite-based logging of all admin actions with `/history` (filter, pagination, detail view)

**🔗 Link Whitelist**
Automatic deletion of non-whitelisted links

**👋 Welcome**
Welcome embed with account age & member number

**🎵 Support Music**
Automatic music in waiting room voice channel

**🌐 Multilingual**
Fully in 🇩🇪 German & 🇬🇧 English, configurable per server

</td>
</tr>
</table>

> **All setup processes use visual wizards — a single `/setup` command with dropdown menus and modals. No manual ID input required.**

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

After the bot is online, use the unified setup wizard:

```
/setup    → Opens the setup wizard with all options in one dropdown:
            • Ticket System
            • Verification
            • Self-Roles
            • Application System
            • Log Channel
            • Welcome Channel
            • Waiting Room (support music)
            • Auto-Join Roles
            • Bot Status
            • Language
```

---

## 📋 Commands

### ⚙️ Setup & Management

| Command | Description | Permission |
|---|---|---|
| `/setup` | **Universal setup wizard** — all setup options in one dropdown | Administrator |
| `/edit` | Edit existing panels | Administrator |
| `/delete` | Delete panels & configurations | Administrator |
| `/ticket_edit` | Edit ticket panel (title / description / color) | Administrator |
| `/setup_pioneer_role` | Assign pioneer role to first 100 members | Administrator |
| `/set_language` | Switch language (🇩🇪 / 🇬🇧) | Administrator |

### 🛡️ Moderation

| Command | Parameters | Permission |
|---|---|---|
| `/ban` | `user`, `reason` | Ban Members |
| `/kick` | `user`, `reason` | Kick Members |
| `/timeout` | `user`, `minutes`, `reason` | Moderate Members |
| `/warn` | `user`, `reason` | Moderate Members |
| `/warn_edit` | `user`, `count` | Moderate Members |
| `/userinfo` | `user` (optional) | Everyone / Admin for others |
| `/whitelist` | `action`, `domain` | Administrator |
| `/adminpanel` | — | Administrator |

### 📋 Logs & Config

| Command | Description | Permission |
|---|---|---|
| `/history` | Paginated audit log with filters (action, user, date) + detail view | Administrator |
| `/config_export` | Export config as JSON (incl. open tickets & applications) | Administrator |
| `/config_import` | Import config + 24h rollback button | Administrator |

### 🎵 Music & Embed

| Command | Description | Permission |
|---|---|---|
| `/music_upload` | Upload waiting room music (.mp3/.ogg/.wav/.flac/.m4a, max 25 MB) | Administrator |
| `/music_download` | Download current waiting room music | Administrator |
| `/embed_create` | Embed generator (fields, images, link buttons, dropdown) | Administrator |

### ℹ️ General

| Command | Description | Permission |
|---|---|---|
| `/info` | Bot info, live statistics & version | Everyone |
| `/ping` | Bot latency | Everyone |

---

## 🔍 Feature Details

### 🎫 Ticket System

The wizard guides through all steps: title, supporter roles (dropdown), categories with emoji & description, embed styling (hex color, description, thumbnail), live preview.

Users select a category → a **private thread** is automatically created. Supporters can **claim** or **close** (with reason). The creator receives a DM on every action.

---

### 📋 Application System

Multi-step (4 questions per step), minimum lengths enforced directly in the input field. After submission a **private thread** is created in the review channel. Applicants only get access when the team sends a follow-up question.

**Default questions** (`configs/default_application.json` / `configs/default_application_de.json`):

The bot automatically loads the language-appropriate default questions based on the server language setting.

```json
{
  "questions": [
    {
      "label": "Roblox Username",
      "placeholder": "Your username",
      "style": "short",
      "required": true,
      "min_length": 0,
      "section": { "name": "👤 Personal Info", "desc": "Basic information" }
    }
  ]
}
```

| Field | Values | Description |
|---|---|---|
| `style` | `short` / `paragraph` | Single line or multi-line input |
| `min_length` | `0`–`1023` | Minimum characters (0 = no limit) |
| `section` | `{name, desc}` / `null` | Groups questions under a heading |

---

### 🎨 Embed Generator

Full embed builder with live preview:

- ✏️ **Title, description & color** (hex)
- 🖼️ **Images** (large bottom + thumbnail right)
- 👤 **Author & footer** with icons
- ➕ **Fields** — add, edit & delete individual fields via dropdown
- 🔗 **Link Buttons** (up to 5) — label, URL, emoji
- 📋 **Dropdown Menu** (up to 25 options) — as an alternative to buttons
- ⏱️ **Timestamp** toggle

---

### 👤 Admin Panel

Select a member via Discord's native **UserSelect** dropdown → userinfo is shown immediately. Then choose from: Timeout / Extend Timeout / Remove Timeout / Warn / Kick / Ban. Chat management: Lock / Unlock / Slowmode / Purge.

All Admin Panel actions are logged in the SQLite audit log.

---

### 📋 Audit Log (`/history`)

All admin actions are stored in a SQLite database (`configs/audit_log.db`):

- **Category dropdown** → specific action filter
- **🔍 Filter modal** — user (@mention / name / ID) and date / month
- **◀ / ▶ Pagination** — 8 entries per page
- **Detail dropdown** — full info including reconstructed embed (if `embed_sent`)
- **✖️ Reset filters** button

---

### ⚙️ Config Export / Import

Export includes: guild config, open applications, open ticket threads (member IDs for restore).

Import: preview with panel counts → confirm → panels recreated → rollback button in log channel (24h, admins only). Rollback deletes newly created panels and restores the old snapshot.

---

## 📁 Config Files

All configs are in the `configs/` folder and created automatically on first start.

| File | Contents |
|---|---|
| `config.json` | Server configurations — panels, warn counts, channel IDs |
| `whitelist.json` | Allowed link domains |
| `open_applications.json` | Open application threads (button persistence after restart) |
| `audit_log.db` | SQLite audit log database |
| `default_application.json` | Default application form (English) — freely editable |
| `default_application_de.json` | Default application form (German) — freely editable |

> All buttons and panels remain fully functional after a restart — no re-setup required.

---

## 🔒 Required Permissions

```
✅ Manage Roles              Role assignment (Verify, Self-Roles, Join-Roles)
✅ Manage Channels           Create ticket channels
✅ Manage Threads            Manage ticket threads
✅ Create Private Threads    Application review threads
✅ Ban Members               /ban
✅ Kick Members              /kick
✅ Moderate Members          /timeout, /warn
✅ Send Messages             General
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

<div align="center">

Made with ❤️ by **pilzithegoat**

</div>

---

# 🇩🇪 Deutsch

<div align="center">

# 🤖 Bexi Bot

**Ein vollwertiger Discord-Bot für Roleplay-Server und Communities**

Ticket-System · Bewerbungen · Moderation · Verifizierung · Self-Roles · Embed-Generator · Audit-Log · Mehrsprachig

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![Version](https://img.shields.io/badge/Version-2.0.0-57F287?style=for-the-badge)](https://github.com/pilzithegoat/bexi_bot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ARM64%20%2F%20x86-2496ED?style=for-the-badge&logo=docker&logoColor=white)](Docker/)

<br/>

[🇬🇧 English](#-english) · **🇩🇪 Deutsch**

</div>

---

## ✨ Features

<table>
<tr>
<td>

**🎫 Ticket-System**
Dropdown-Panels mit Kategorien, privaten Threads, Claim & Close

**📋 Bewerbungssystem**
Mehrstufige Formulare mit Sektionen, Thread-basiertes Review, Annehmen / Ablehnen / Rückfrage

**🛡️ Moderation**
Ban, Kick, Timeout, Warn — mit DM & Log-Kanal

**✅ Verifizierung**
Konfigurierbares Embed mit Farbe, Thumbnail & Rolle

**🎭 Self-Roles**
Dropdown mit Häkchen — mehrere Rollen gleichzeitig wählen

**🎨 Embed-Generator**
Vollständiger Embed-Builder: Felder, Bilder, Link-Buttons ODER Dropdown-Menü

</td>
<td>

**👤 Admin-Panel**
UserSelect-Dropdown → sofortige Nutzer-Info + Timeout / Warn / Kick / Ban + Chat-Verwaltung

**📋 Audit-Log**
SQLite-basiertes Logging aller Admin-Aktionen mit `/history` (Filter, Pagination, Detail-Ansicht)

**🔗 Link-Whitelist**
Automatisches Löschen nicht erlaubter Links

**👋 Willkommen**
Willkommens-Embed mit Account-Alter & Mitglieds-Nummer

**🎵 Support-Musik**
Automatische Musik im Warteraum-Sprachkanal

**🌐 Mehrsprachig**
Vollständig auf 🇩🇪 Deutsch & 🇬🇧 Englisch, pro Server konfigurierbar

</td>
</tr>
</table>

> **Alle Einrichtungsprozesse nutzen visuelle Wizards — ein einziger `/setup` Command mit Dropdown-Menüs und Modals. Keine manuelle ID-Eingabe erforderlich.**

---

## 🚀 Bot zum Server hinzufügen

Ersetze `YOUR_ID` mit der **Application ID** deines Bots aus dem [Discord Developer Portal](https://discord.com/developers/applications):

```
https://discord.com/oauth2/authorize?client_id=YOUR_ID&permissions=9175529923606&integration_type=0&scope=bot+applications.commands
```

> Die Application ID findet sich unter **General Information** im Developer Portal.

---

## 📖 Inhaltsverzeichnis

- [Features](#-features-1)
- [Bot zum Server hinzufügen](#-bot-zum-server-hinzufügen)
- [Voraussetzungen](#-voraussetzungen)
- [Installation](#-installation-1)
  - [Methode 1: Python (lokal)](#methode-1-python-lokal)
  - [Methode 2: Docker (empfohlen)](#methode-2-docker-empfohlen)
  - [Methode 3: Raspberry Pi](#methode-3-raspberry-pi)
- [Discord Bot einrichten](#-discord-bot-einrichten)
- [Ersteinrichtung](#-ersteinrichtung)
- [Commands](#-commands-1)
- [Features im Detail](#-features-im-detail)
- [Konfigurationsdateien](#-konfigurationsdateien)
- [Berechtigungen](#-berechtigungen)
- [Lizenz](#-lizenz)

---

## 📋 Voraussetzungen

| Anforderung | Version | Hinweis |
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

Einlade-Link aus [Bot zum Server hinzufügen](#-bot-zum-server-hinzufügen) verwenden — `YOUR_ID` durch die **Application ID** ersetzen (unter **General Information**).

---

## ⚙️ Ersteinrichtung

Nach dem Start den universellen Setup-Wizard verwenden:

```
/setup    → Öffnet den Setup-Wizard mit allen Optionen in einem Dropdown:
            • Ticket-System
            • Verifizierung
            • Self-Roles
            • Bewerbungssystem
            • Log-Kanal
            • Willkommens-Kanal
            • Warteraum (Support-Musik)
            • Auto-Join Rollen
            • Bot-Status
            • Sprache
```

---

## 📋 Commands

### ⚙️ Setup & Verwaltung

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/setup` | **Universeller Setup-Wizard** — alle Optionen in einem Dropdown | Administrator |
| `/edit` | Bestehende Panels bearbeiten | Administrator |
| `/delete` | Panels & Konfigurationen löschen | Administrator |
| `/ticket_edit` | Ticket-Panel bearbeiten (Titel / Beschreibung / Farbe) | Administrator |
| `/setup_pioneer_role` | Erste 100 Mitglieder mit Pionier-Rolle versehen | Administrator |
| `/set_language` | Sprache umschalten (🇩🇪 / 🇬🇧) | Administrator |

### 🛡️ Moderation

| Command | Parameter | Berechtigung |
|---|---|---|
| `/ban` | `nutzer`, `grund` | Ban Members |
| `/kick` | `nutzer`, `grund` | Kick Members |
| `/timeout` | `nutzer`, `minuten`, `grund` | Moderate Members |
| `/warn` | `nutzer`, `grund` | Moderate Members |
| `/warn_edit` | `nutzer`, `anzahl` | Moderate Members |
| `/userinfo` | `nutzer` (optional) | Jeder / Admin für andere |
| `/whitelist` | `aktion`, `domain` | Administrator |
| `/adminpanel` | — | Administrator |

### 📋 Logs & Config

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/history` | Paginierter Audit-Log mit Filtern (Aktion, Nutzer, Datum) + Detail-Ansicht | Administrator |
| `/config_export` | Config als JSON exportieren (inkl. offene Tickets & Bewerbungen) | Administrator |
| `/config_import` | Config importieren + 24h Rollback-Button | Administrator |

### 🎵 Musik & Embed

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/music_upload` | Warteraum-Musik hochladen (.mp3/.ogg/.wav/.flac/.m4a, max 25 MB) | Administrator |
| `/music_download` | Aktuelle Warteraum-Musik herunterladen | Administrator |
| `/embed_create` | Embed-Generator (Felder, Bilder, Link-Buttons, Dropdown) | Administrator |

### ℹ️ Allgemein

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/info` | Bot-Infos, Live-Statistiken & Version | Jeder |
| `/ping` | Bot-Latenz anzeigen | Jeder |

---

## 🔍 Features im Detail

### 🎫 Ticket-System

Der Wizard führt durch alle Schritte: Titel, Supporter-Rollen (Dropdown), Kategorien mit Emoji & Beschreibung, Embed gestalten (Hex-Farbe, Beschreibung, Thumbnail), Live-Vorschau.

Nutzer wählen eine Kategorie → **privater Thread** wird automatisch erstellt. Supporter können **übernehmen** oder **schließen** (mit Begründung). Der Ersteller bekommt bei jeder Aktion eine DM.

---

### 📋 Bewerbungssystem

Mehrstufig (4 Fragen pro Schritt), Mindestlängen werden direkt im Eingabefeld erzwungen. Nach dem Einreichen wird ein **privater Thread** im Review-Channel erstellt. Bewerber erhalten erst Zugang, wenn das Team eine Rückfrage stellt.

**Standard-Fragen** (`configs/default_application.json` / `configs/default_application_de.json`):

Der Bot lädt automatisch die sprachgerechten Standardfragen basierend auf der eingestellten Server-Sprache.

```json
{
  "questions": [
    {
      "label": "Roblox Benutzername",
      "placeholder": "Dein Nutzername",
      "style": "short",
      "required": true,
      "min_length": 0,
      "section": { "name": "👤 Persönliche Daten", "desc": "Grundlegende Informationen" }
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

### 🎨 Embed-Generator

Vollständiger Embed-Builder mit Live-Vorschau:

- ✏️ **Titel, Beschreibung & Farbe** (Hex)
- 🖼️ **Bilder** (groß unten + Thumbnail rechts)
- 👤 **Author & Footer** mit Icons
- ➕ **Felder** — einzeln hinzufügen, bearbeiten & löschen per Dropdown
- 🔗 **Link-Buttons** (bis zu 5) — Beschriftung, URL, Emoji
- 📋 **Dropdown-Menü** (bis zu 25 Optionen) — als Alternative zu Buttons
- ⏱️ **Timestamp** Toggle

---

### 👤 Admin-Panel

Mitglied über Discords natives **UserSelect**-Dropdown auswählen → Nutzer-Info wird sofort angezeigt. Dann wählen: Timeout / Timeout verlängern / Timeout aufheben / Verwarnen / Kicken / Bannen. Chat-Verwaltung: Sperren / Entsperren / Slowmode / Nachrichten löschen.

Alle Admin-Panel-Aktionen werden im SQLite-Audit-Log gespeichert.

---

### 📋 Audit-Log (`/history`)

Alle Admin-Aktionen werden in einer SQLite-Datenbank gespeichert:

- **Kategorie-Dropdown** → spezifischer Aktionsfilter
- **🔍 Filter-Modal** — Nutzer (@mention / Name / ID) und Datum / Monat
- **◀ / ▶ Pagination** — 8 Einträge pro Seite
- **Detail-Dropdown** — vollständige Infos inkl. rekonstruiertem Embed (bei `embed_sent`)
- **✖️ Filter zurücksetzen** Button

---

### ⚙️ Config Export / Import

Export enthält: Guild-Config, offene Bewerbungen, offene Ticket-Threads (Mitglieds-IDs zur Wiederherstellung).

Import: Vorschau mit Panel-Anzahl → bestätigen → Panels werden neu erstellt → Rollback-Button im Log-Kanal (24h, nur Admins). Rollback löscht neu erstellte Panels und stellt den alten Snapshot wieder her.

---

## 📁 Konfigurationsdateien

Alle Configs liegen im `configs/`-Ordner und werden beim ersten Start automatisch erstellt.

| Datei | Inhalt |
|---|---|
| `config.json` | Server-Konfigurationen — Panels, Warn-Counts, Kanal-IDs |
| `whitelist.json` | Erlaubte Link-Domains |
| `open_applications.json` | Offene Bewerbungs-Threads (Button-Persistenz nach Neustart) |
| `audit_log.db` | SQLite Audit-Log Datenbank |
| `default_application.json` | Standard-Bewerbungsformular (Englisch) — frei editierbar |
| `default_application_de.json` | Standard-Bewerbungsformular (Deutsch) — frei editierbar |

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

Made with ❤️ by **pilzithegoat**

</div>