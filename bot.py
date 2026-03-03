import discord
from discord import app_commands
from discord.ext import commands
import re
import json
import os

# --- SETUP AUS UMGEBUNGSVARIABLEN ---
TOKEN = os.getenv('DISCORD_TOKEN')
ENV_GUILD_ID = os.getenv('DISCORD_GUILD_ID')
CONFIG_FILE = 'config.json'

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

# --- TICKET CONTROL PANEL (INSIDE THREAD) ---
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket Claimen", style=discord.ButtonStyle.blurple, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        if any(field.name == "Bearbeiter" for field in embed.fields):
            return await interaction.response.send_message("Dieses Ticket wurde bereits übernommen!", ephemeral=True)
            
        embed.add_field(name="Bearbeiter", value=interaction.user.mention, inline=False)
        embed.color = discord.Color.blue()
        
        button.disabled = True
        button.label = "Ticket beansprucht"
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {interaction.user.mention} hat dieses Ticket übernommen.", ephemeral=False)

    @discord.ui.button(label="Ticket Schließen", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Das Ticket wird geschlossen und archiviert...")
        thread = interaction.channel
        await thread.edit(locked=True, archived=True)

# --- VERIFY SYSTEM ---
class VerifyView(discord.ui.View):
    def __init__(self, role_id: int):
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(label="Verifizieren", style=discord.ButtonStyle.green, custom_id="verify_btn_persistent")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"✅ Du hast die Rolle **{role.name}** erhalten!", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("❌ Mir fehlen die Rechte, um Rollen zu vergeben. (Hierarchie prüfen!)", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Diese Rolle existiert nicht mehr.", ephemeral=True)

# --- TICKET SYSTEM ---
class TicketSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Wähle dein Anliegen...", options=options, custom_id="ticket_select_persistent")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Ticket für **{self.values[0]}** wird erstellt...", ephemeral=True)
        
        thread = await interaction.channel.create_thread(
            name=f"ticket-{interaction.user.display_name}-{self.values[0]}",
            type=discord.ChannelType.private_thread
        )
        
        await thread.add_user(interaction.user)
        
        # Team-Rollen aus Config laden und Mitglieder hinzufügen
        config = load_config()
        guild_id = str(interaction.guild_id)
        team_role_ids = config.get(guild_id, {}).get("support_roles", [])
        
        for role_id in team_role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                for member in role.members:
                    await thread.add_user(member)
        
        embed = discord.Embed(
            title="Support-Ticket geöffnet",
            description=f"Hallo {interaction.user.mention}!\n\nKategorie: **{self.values[0]}**\nBitte beschreibe dein Anliegen hier im Thread.",
            color=discord.Color.green()
        )
        
        await thread.send(embed=embed, view=TicketControlView())

class TicketView(discord.ui.View):
    def __init__(self, categories_data):
        super().__init__(timeout=None)
        options = []
        for item in categories_data:
            emoji = item.get('emoji')
            if emoji and not self._is_valid_emoji(emoji):
                emoji = None
                
            options.append(discord.SelectOption(
                label=item['label'][:100], 
                value=item['value'][:100], 
                emoji=emoji,
                description=item.get('description')[:100] if item.get('description') else None
            ))
        
        self.add_item(TicketSelect(options))

    def _is_valid_emoji(self, emoji_str):
        return any(char for char in emoji_str if ord(char) > 127)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        config = load_config()
        for guild_id_str, data in config.items():
            # Panels registrieren für Persistenz
            for panel in data.get("verify_panels", []):
                self.add_view(VerifyView(panel["role_id"]))
            for t_panel in data.get("ticket_panels", []):
                self.add_view(TicketView(t_panel["categories"]))
            
        self.add_view(TicketControlView())
        await self.tree.sync()

bot = MyBot()

# --- ADMIN COMMANDS ---

ticket_roles_group = app_commands.Group(name="ticket_roles", description="Verwalte Supporter-Rollen für Tickets")

@ticket_roles_group.command(name="add", description="Fügt eine Supporter-Rolle hinzu")
@app_commands.describe(rolle="Die Rolle, die Tickets sehen darf")
@app_commands.checks.has_permissions(administrator=True)
async def add_support_role(interaction: discord.Interaction, rolle: discord.Role):
    guild_id = str(interaction.guild_id)
    config = load_config()
    
    if guild_id not in config:
        config[guild_id] = {"verify_panels": [], "ticket_panels": [], "support_roles": []}
    
    if "support_roles" not in config[guild_id]:
        config[guild_id]["support_roles"] = []
        
    if rolle.id not in config[guild_id]["support_roles"]:
        config[guild_id]["support_roles"].append(rolle.id)
        save_config(config)
        await interaction.response.send_message(f"✅ Rolle **{rolle.name}** als Supporter hinzugefügt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Diese Rolle ist bereits als Supporter eingetragen.", ephemeral=True)

@ticket_roles_group.command(name="remove", description="Entfernt eine Supporter-Rolle")
@app_commands.describe(rolle="Die Rolle, die den Zugriff verlieren soll")
@app_commands.checks.has_permissions(administrator=True)
async def remove_support_role(interaction: discord.Interaction, rolle: discord.Role):
    guild_id = str(interaction.guild_id)
    config = load_config()
    
    if guild_id in config and "support_roles" in config[guild_id]:
        if rolle.id in config[guild_id]["support_roles"]:
            config[guild_id]["support_roles"].remove(rolle.id)
            save_config(config)
            await interaction.response.send_message(f"✅ Rolle **{rolle.name}** entfernt.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ Diese Rolle war kein Supporter.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Keine Rollen konfiguriert.", ephemeral=True)

bot.tree.add_command(ticket_roles_group)

@bot.tree.command(name="setup_verify", description="Erstellt ein Verify-Panel für diesen Server")
@app_commands.describe(rolle="Die Rolle, die vergeben werden soll")
@app_commands.checks.has_permissions(administrator=True)
async def setup_verify(interaction: discord.Interaction, rolle: discord.Role):
    guild_id = str(interaction.guild_id)
    config = load_config()
    
    if guild_id not in config:
        config[guild_id] = {"verify_panels": [], "ticket_panels": [], "support_roles": []}
    
    embed = discord.Embed(
        title="Server Verifizierung",
        description=f"Klicke auf den Button, um die Rolle **{rolle.name}** zu erhalten.",
        color=discord.Color.blue()
    )
    
    # Nachricht senden
    view = VerifyView(rolle.id)
    message = await interaction.channel.send(embed=embed, view=view)
    
    # In Config speichern
    panel_data = {
        "role_id": rolle.id,
        "channel_id": interaction.channel_id,
        "message_id": message.id
    }
    
    if "verify_panels" not in config[guild_id]:
        config[guild_id]["verify_panels"] = []
        
    config[guild_id]["verify_panels"].append(panel_data)
    save_config(config)
    
    await interaction.response.send_message(f"✅ Verify-Panel erstellt und gespeichert.", ephemeral=True)

@bot.tree.command(name="setup_tickets", description="Erstellt ein Ticket-System mit Emojis und Beschreibungen")
@app_commands.describe(kategorien='Format: "Emoji Name | Beschreibung", "Emoji Name | Beschreibung"')
@app_commands.checks.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction, kategorien: str):
    guild_id = str(interaction.guild_id)
    
    raw_list = re.findall(r'"([^"]*)"', kategorien)
    if not raw_list:
        raw_list = [c.strip() for c in kategorien.split(",") if c.strip()]

    formatted_cats = []
    for item in raw_list:
        item = item.strip()
        if not item: continue
        
        parts = item.split("|")
        main_part = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else None
        
        emoji = None
        label = main_part
        
        match = re.search(r'^([^\x00-\x7F]|\W+)\s*(.*)', main_part)
        if match:
            emoji_candidate = match.group(1).strip()
            if emoji_candidate:
                emoji = emoji_candidate
                label = match.group(2).strip() if match.group(2) else emoji_candidate

        formatted_cats.append({
            "label": label[:100], 
            "value": label[:100], 
            "emoji": emoji, 
            "description": description[:100] if description else None
        })

    if not formatted_cats:
        return await interaction.response.send_message('❌ Fehler: Bitte nutze Anführungszeichen, z.B.: "🛠️ Support | Hilfe, Infos"', ephemeral=True)

    config = load_config()
    if guild_id not in config:
        config[guild_id] = {"verify_panels": [], "ticket_panels": [], "support_roles": []}
        
    view = TicketView(formatted_cats)
    message = await interaction.channel.send(embed=discord.Embed(
        title="Support-Tickets",
        description="Wähle eine Kategorie aus dem Menü.",
        color=discord.Color.gold()
    ), view=view)

    panel_info = {
        "categories": formatted_cats,
        "channel_id": interaction.channel_id,
        "message_id": message.id
    }
    
    if "ticket_panels" not in config[guild_id]:
        config[guild_id]["ticket_panels"] = []
        
    config[guild_id]["ticket_panels"].append(panel_info)
    save_config(config)
    
    await interaction.response.send_message("✅ Ticket-Panel erstellt und gespeichert.", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online als {bot.user}')

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Fehler: DISCORD_TOKEN fehlt!")