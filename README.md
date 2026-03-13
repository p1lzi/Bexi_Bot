# 🤖 Bexi Bot

Ein vielseitiger Discord-Bot mit Ticket-System, Moderations-Tools, Verifizierung, Self-Role Panels und mehrsprachigem Interface.

---

## ✨ Features

| Feature | Beschreibung |
|---|---|
| 🎫 Ticket-System | Dropdown-Panels mit Kategorien, privaten Threads, Claim & Close |
| 🛡️ Moderation | Ban, Kick, Timeout, Warn — mit DM-Benachrichtigung & Log |
| ✅ Verifizierung | Button-Panel zum Verifizieren mit automatischer Rollenvergabe |
| 🎭 Self-Roles | Button-Panels für selbst wählbare Rollen (toggle) |
| 🔗 Whitelist | Automatisches Löschen nicht erlaubter Links |
| 👋 Willkommen | Automatische Begrüßungsnachricht für neue Mitglieder |
| 🎵 Support-Musik | Automatische Musik im Warteraum-Sprachkanal |
| 🌐 Mehrsprachig | Vollständig auf Deutsch & Englisch konfigurierbar |

---

## 🚀 Installation

### Voraussetzungen

- Python 3.11+
- Ein Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- FFmpeg (für Support-Musik, optional)

### 1. Repository klonen

```bash
git clone https://github.com/pilzithegoat/bexi_bot.git
cd bexi_bot
```

### 2. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 3. Umgebungsvariablen setzen

Erstelle eine `.env` Datei im Projektverzeichnis:

```env
DISCORD_TOKEN=dein_bot_token_hier
DISCORD_GUILD_ID=deine_guild_id_hier
```

### 4. Bot starten

```bash
python bot.py
```

---

## 🐳 Docker

### Mit docker-compose starten

Erstelle eine `.env` Datei:

```env
Bot_Token=dein_bot_token_hier
Guild_ID=deine_guild_id_hier
```

Dann starten:

```bash
docker-compose up -d
```

Das Image ist für **ARM64 (Raspberry Pi)** optimiert. Für x86 in `compose.yaml` die `platform`-Zeile entfernen.

---

## 📁 Dateistruktur

```
bexi_bot/
├── bot.py                  # Haupt-Bot-Datei
├── config.json             # Server-Konfigurationen (automatisch erstellt)
├── whitelist.json          # Erlaubte Link-Domains
├── support_music.mp3       # Musik für den Warteraum (optional)
├── requirements.txt
├── Dockerfile
├── compose.yaml
└── language/
    ├── de.json             # Deutsche Texte
    └── en.json             # Englische Texte
```

---

## ⚙️ Konfiguration

### Sprache einstellen

```
/set_language sprache:Deutsch
/set_language sprache:English
```

Die Sprache wird **pro Server** gespeichert. Alle Embeds, Fehlermeldungen und Button-Labels wechseln automatisch.

### Erste Einrichtung (empfohlene Reihenfolge)

```
1. /set_log_channel       → Kanal für Mod-Logs
2. /set_welcome_channel   → Kanal für Willkommensnachrichten
3. /setup_verify          → Verifizierungs-Panel erstellen
4. /setup_tickets         → Ticket-Panel erstellen
5. /set_waiting_room      → Warteraum für Support-Musik (optional)
```

---

## 📋 Slash-Commands

### 🎫 Ticket-System

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/setup_tickets` | Erstellt ein neues Ticket-Panel mit Kategorien | Admin |
| `/ticket_edit` | Titel, Beschreibung oder Farbe eines Panels ändern | Admin |
| `/ticket_delete` | Ein Ticket-Panel löschen | Admin |

**Format für Kategorien:**
```
Support|Allgemeine Fragen, Bann|Entbannungsanträge, Bewerbung|Jobs im Team
```

Mit Emoji:
```
🛠️ Support|Allgemeine Fragen, 🚫 Bann|Entbannungsanträge
```

---

### 🎭 Self-Role System

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/selfrole_erstellen` | Erstellt ein Button-Panel für selbst wählbare Rollen | Admin |
| `/selfrole_loeschen` | Löscht ein Self-Role Panel per Nachrichten-ID | Admin |
| `/selfrole_liste` | Zeigt alle aktiven Self-Role Panels | Admin |

**Format für Rollen:**
```
🎮 Gamer|RollenID|Für alle Gamer, 🎵 Musik|RollenID
```

---

### 🛡️ Moderation

| Command | Parameter | Berechtigung |
|---|---|---|
| `/ban` | `nutzer`, `grund` | Ban Members |
| `/kick` | `nutzer`, `grund` | Kick Members |
| `/timeout` | `nutzer`, `minuten`, `grund` | Moderate Members |
| `/warn` | `nutzer`, `grund` | Moderate Members |
| `/warn_edit` | `nutzer`, `anzahl` | Moderate Members |
| `/userinfo` | `nutzer` (optional) | Jeder / Admin für andere |

Alle Moderationsaktionen senden dem betroffenen Nutzer automatisch eine **DM** und loggen die Aktion im festgelegten **Log-Kanal**.

---

### ✅ Verifizierung

| Command | Parameter | Berechtigung |
|---|---|---|
| `/setup_verify` | `rolle`, `titel` (optional), `beschreibung` (optional) | Admin |

Erstellt ein Embed mit einem grünen Button. Nach dem Klick erhält der Nutzer die angegebene Rolle automatisch.

---

### 🔗 Link-Whitelist

| Command | Parameter | Berechtigung |
|---|---|---|
| `/whitelist` | `aktion` (Hinzufügen/Entfernen/Liste), `domain` | Admin |

Nicht erlaubte Links werden automatisch gelöscht und der Nutzer wird informiert. Administratoren sind ausgenommen.

**Standardmäßig erlaubt:** `cdn.discordapp.com`, `giphy.com`, `tenor.com`

---

### ⚙️ Sonstiges

| Command | Beschreibung | Berechtigung |
|---|---|---|
| `/setup_pioneer_role` | Vergibt eine Rolle an die ersten 100 Mitglieder | Admin |
| `/set_log_channel` | Log-Kanal festlegen | Admin |
| `/set_welcome_channel` | Willkommens-Kanal festlegen | Admin |
| `/set_waiting_room` | Warteraum-Kanal festlegen | Admin |
| `/status_config` | Bot-Status & Aktivität ändern | Admin |
| `/set_language` | Sprache des Bots ändern | Admin |
| `/ping` | Bot-Latenz anzeigen | Jeder |

---

## 🌐 Mehrsprachigkeit

Alle Bot-Texte sind in `language/de.json` und `language/en.json` gespeichert. Die Struktur:

```json
{
    "commands": { ... },     // Slash-Command Beschreibungen & Parameter
    "buttons": { ... },      // Button-Labels
    "modals": { ... },       // Modal-Titel & Felder
    "selects": { ... },      // Dropdown-Placeholder
    "errors": { ... },       // Fehlermeldungen
    "success": { ... },      // Erfolgsmeldungen
    "embeds": { ... }        // Alle Embed-Texte
}
```

Um Texte anzupassen, einfach die entsprechende JSON-Datei bearbeiten — kein Code-Änderung nötig.

---

## 🔒 Berechtigungen

Der Bot benötigt folgende Discord-Berechtigungen:

- `Manage Roles` — für Verifizierung & Self-Roles
- `Manage Channels` — für Ticket-Kanäle & Threads
- `Manage Threads` — für Ticket-Threads
- `Ban Members` / `Kick Members` — für Moderation
- `Moderate Members` — für Timeout & Warn
- `Send Messages` — allgemein
- `Embed Links` — für Embeds
- `Manage Messages` — für Link-Whitelist
- `Connect` / `Speak` — für Support-Musik (optional)

---

## 📝 Lizenz

MIT License — siehe [LICENSE](LICENSE)