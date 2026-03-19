
<div align="center">

<img src="https://discord.com/assets/b8dafcbec499ac71.svg" alt="Util Bot" width="120" height="120" />

# Util Bot

**Ein vollständiger Discord-Bot für Roleplay-Server**

Ticket-System · Bewerbungen · Moderation · Verifizierung · Self-Roles · Mehrsprachig

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ARM64%20%2F%20x86-2496ED?style=for-the-badge&logo=docker&logoColor=white)](Docker/)

</div>

---

## 📖 Inhaltsverzeichnis

- [Features](#-features)
- [Voraussetzungen](#-voraussetzungen)
- [Installation](#-installation)
  - [Methode 1: Python (lokal)](#methode-1-python-lokal)
  - [Methode 2: Docker](#methode-2-docker-empfohlen)
  - [Methode 3: Raspberry Pi](#methode-3-raspberry-pi)
- [Bot auf Discord einrichten](#-bot-auf-discord-einrichten)
- [Ersteinrichtung](#-ersteinrichtung)
- [Commands](#-commands)
- [Features im Detail](#-features-im-detail)
- [Konfigurationsdateien](#-konfigurationsdateien)
- [Berechtigungen](#-berechtigungen)
- [Lizenz](#-lizenz)

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

## 📋 Voraussetzungen

| Anforderung | Version | Anmerkung |
|---|---|---|
| Python | 3.11+ | Für lokale Installation |
| docker + docker compose | aktuell | Für Docker-Installation |
| Discord Bot Token | — | Siehe [Bot einrichten](#-bot-auf-discord-einrichten) |
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

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Dann die Werte eintragen:

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

**4. Logs anzeigen**

```bash
docker compose logs -f
```

**5. Stoppen**

```bash
docker compose down
```

> **Hinweis:** Der `configs/`-Ordner wird automatisch als Volume gemountet, sodass alle Panel-Einstellungen bei Updates erhalten bleiben.

---

### Methode 3: Raspberry Pi

Das Docker-Image ist für **ARM64** optimiert und läuft nativ auf dem Raspberry Pi (4, 5).

```bash
git clone https://github.com/pilzithegoat/bexi_bot.git
cd bexi_bot/Docker

# .env erstellen
echo "Bot_Token=dein_token" > .env
echo "Guild_ID=deine_guild_id" >> .env

# Starten
docker compose up -d
```

Für x86-Systeme die `platform: linux/arm64` Zeile in `compose.yaml` entfernen oder auskommentieren.

---

## 🤖 Bot auf Discord einrichten

### 1. Application erstellen

1. Öffne das [Discord Developer Portal](https://discord.com/developers/applications)
2. Klicke **"New Application"** und gib einen Namen ein
3. Gehe zu **"Bot"** im linken Menü
4. Klicke **"Add Bot"** → bestätige

### 2. Token kopieren

1. Unter **Bot** → **"Reset Token"** klicken
2. Token kopieren und in die `.env` Datei eintragen

> ⚠️ **Den Token niemals veröffentlichen oder in Git commiten!**

### 3. Privileged Intents aktivieren

Unter **Bot** → **Privileged Gateway Intents** alle drei aktivieren:

- ✅ Presence Intent
- ✅ Server Members Intent
- ✅ Message Content Intent

### 4. Bot einladen

Unter **OAuth2** → **URL Generator**:

**Scopes auswählen:**
- `bot`
- `applications.commands`

**Bot Permissions auswählen:**

| Kategorie | Berechtigung |
|---|---|
| General | Manage Roles, Manage Channels, Read Messages/View Channels |
| Text | Send Messages, Send Messages in Threads, Create Private Threads, Manage Messages, Embed Links, Read Message History, Manage Threads |
| Voice | Connect, Speak |
| Moderation | Ban Members, Kick Members, Moderate Members |

Generierten Link öffnen und Bot zum Server einladen.

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

| Command | Beschreibung |
|---|---|
| `/setup_tickets` | Interaktiven Ticket-Wizard starten |
| `/ticket_edit` | Bestehendes Panel bearbeiten (Embed, Kategorien, Rollen) |

### 📋 Bewerbungen

| Command | Beschreibung |
|---|---|
| `/setup_application` | Bewerbungs-Panel-Wizard starten |

### 🎭 Self-Roles

| Command | Beschreibung |
|---|---|
| `/selfrole_create` | Self-Role-Panel-Wizard starten |
| `/selfrole_list` | Alle aktiven Self-Role-Panels anzeigen |

### ✅ Verifizierung

| Command | Beschreibung |
|---|---|
| `/setup_verify` | Verify-Panel-Wizard starten |

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
| `/whitelist` | `aktion`, `domain` | Link-Whitelist verwalten |

### ⚙️ Server-Einstellungen

| Command | Beschreibung |
|---|---|
| `/set_language` | Sprache umschalten (🇩🇪 / 🇬🇧) |
| `/set_log_channel` | Log-Kanal festlegen |
| `/set_welcome_channel` | Willkommens-Kanal festlegen |
| `/set_waiting_room` | Warteraum für Support-Musik |
| `/set_join_roles` | Auto-Join-Rollen Wizard |
| `/status_config` | Bot-Status & Aktivität konfigurieren |
| `/setup_pioneer_role` | Erste 100 Mitglieder mit Rolle versehen |
| `/delete` | Panels aller Typen über Wizard löschen |
| `/ping` | Bot-Latenz anzeigen |

---

## 🔍 Features im Detail

### 🎫 Ticket-System

Der Wizard führt durch alle Schritte:

1. **Titel** festlegen
2. **Supporter-Rollen** per Discord-Dropdown auswählen
3. **Kategorien** hinzufügen (Name, Emoji, Beschreibung)
4. **Embed gestalten** — Farbe (Hex-Code), Beschreibung, Thumbnail
5. **Vorschau** anzeigen
6. Panel erstellen

Nutzer wählen im Panel eine Kategorie — es wird automatisch ein **privater Thread** erstellt. Supporter können das Ticket **claimen** (übernehmen) oder **schließen** (mit Begründung). Der Ersteller bekommt bei jeder Aktion eine DM.

Bestehende Panels lassen sich mit `/ticket_edit` vollständig anpassen — Änderungen werden sofort auf das Discord-Panel übernommen.

---

### 📋 Bewerbungssystem

Bewerbungen laufen mehrstufig ab (4 Fragen pro Schritt). Mindestlängen werden direkt im Eingabefeld erzwungen. Nach dem Einreichen wird ein **privater Thread** im Review-Channel erstellt.

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

Felder: `style` = `short` oder `paragraph`, `min_length` = Mindestzeichen (0 = kein Limit).

---

### 🎭 Self-Roles

Nutzer sehen ein einziges Dropdown-Menü mit allen verfügbaren Rollen. Bereits vorhandene Rollen sind mit **✅** vorausgewählt. Mehrere Rollen können gleichzeitig an- und abgehakt werden — die Häkchen bleiben beim nächsten Öffnen korrekt gesetzt.

---

### 🌐 Mehrsprachigkeit

Alle Texte sind in `language/de.json` und `language/en.json` gespeichert und ohne Code-Änderung anpassbar. Die Sprache wird pro Server gespeichert:

```
/set_language sprache:🇩🇪 Deutsch
/set_language sprache:🇬🇧 English
```

---

## 📁 Konfigurationsdateien

Alle Configs liegen im `configs/`-Ordner und werden automatisch erstellt.

| Datei | Inhalt |
|---|---|
| `config.json` | Server-Konfigurationen (Panels, Warn-Counts, Kanal-IDs) |
| `whitelist.json` | Erlaubte Link-Domains |
| `open_applications.json` | Offene Bewerbungen (für Button-Persistenz nach Neustart) |
| `default_application.json` | Standard-Bewerbungsformular (editierbar) |

> Alle Buttons und Panels bleiben nach einem Neustart vollständig funktionsfähig — der Bot stellt alle Views automatisch wieder her.

---

## 🔒 Berechtigungen

Der Bot benötigt folgende Berechtigungen:

```
✅ Manage Roles              → Rollen vergeben (Verify, Self-Roles, Join-Roles)
✅ Manage Channels           → Ticket-Kanäle erstellen
✅ Manage Threads            → Ticket-Threads verwalten
✅ Create Private Threads    → Bewerbungs-Review-Threads
✅ Ban Members               → /ban
✅ Kick Members              → /kick
✅ Moderate Members          → /timeout, /warn
✅ Send Messages             → Allgemein
✅ Send Messages in Threads  → Ticket-Threads
✅ Embed Links               → Embeds senden
✅ Manage Messages           → Link-Whitelist
✅ Read Message History      → Panel-Nachrichten abrufen
✅ Connect + Speak           → Support-Musik (optional)
```

---

## 📦 Abhängigkeiten

```
discord.py          Discord API Wrapper
discord.py[voice]   Voice-Support für Support-Musik
PyNaCl              Verschlüsselung für Voice
static-ffmpeg       Portables FFmpeg (kein System-Install nötig)
python-dotenv       .env Datei laden
```

---

## 📝 Lizenz

Dieses Projekt steht unter der [MIT License](LICENSE).

---

<div align="center">

Made with ❤️ by **p1lzi*

</div>
