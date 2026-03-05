import discord
from discord import app_commands
from discord.ext import commands
import re
import json
import os
import asyncio

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

# --- HELPER: SEND DM ---
async def send_dm(user: discord.User, message: str, embed: discord.Embed = None):
    try:
        await user.send(content=message, embed=embed)
    except discord.Forbidden:
        # Falls der User DMs deaktiviert hat
        pass

# --- TICKET CONTROL PANEL (INSIDE THREAD) ---
class TicketControlView(discord.ui.View):
    def __init__(self):
        # timeout=None macht die View persistent
        super().__init__(timeout=None)

    def get_creator_id(self, interaction: discord.Interaction):
        """Extrahiert die Creator-ID aus dem Embed der Nachricht, falls vorhanden."""
        try:
            embed = interaction.message.embeds[0]
            # Wir suchen nach der Erwähnung im Description-Feld: "Hallo <@ID>!"
            match = re.search(r'<@!?(\d+)>', embed.description)
            if match:
                return int(match.group(1))
        except:
            pass
        return None

    @discord.ui.button(label="Ticket Claimen", style=discord.ButtonStyle.blurple, custom_id="persistent_claim_ticket")
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
        
        creator_id = self.get_creator_id(interaction)
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = discord.Embed(
                    title="Ticket Update",
                    description=f"Dein Ticket in **{interaction.guild.name}** wurde von {interaction.user.mention} übernommen.\n\n[Zum Ticket springen]({interaction.channel.jump_url})",
                    color=discord.Color.blue()
                )
                await send_dm(creator, "", embed=dm_embed)

    @discord.ui.button(label="Ticket Schließen", style=discord.ButtonStyle.red, custom_id="persistent_close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Das Ticket wird geschlossen und archiviert...")
        
        creator_id = self.get_creator_id(interaction)
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = discord.Embed(
                    title="Ticket Geschlossen",
                    description=f"Dein Ticket in **{interaction.guild.name}** wurde abgeschlossen und archiviert.",
                    color=discord.Color.red()
                )
                await send_dm(creator, "", embed=dm_embed)
            
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
        
        # Senden mit der persistenten View
        await thread.send(embed=embed, view=TicketControlView())

        # DM an den User
        dm_embed = discord.Embed(
            title="Ticket erstellt",
            description=f"Du hast erfolgreich ein Ticket in **{interaction.guild.name}** eröffnet.\n\nKategorie: **{self.values[0]}**\n[Klicke hier, um zu deinem Ticket zu gelangen]({thread.jump_url})",
            color=discord.Color.green()
        )
        await send_dm(interaction.user, "", embed=dm_embed)

        # Auswahl im Menü zurücksetzen
        await interaction.message.edit(view=self.view)

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
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        config = load_config()
        for guild_id_str, data in config.items():
            for panel in data.get("verify_panels", []):
                self.add_view(VerifyView(panel["role_id"]))
            for t_panel in data.get("ticket_panels", []):
                self.add_view(TicketView(t_panel["categories"]))
        
        # Wichtig: TicketControlView global registrieren für Persistenz in Threads
        self.add_view(TicketControlView())
            
        await self.tree.sync()

    # Logik für Warteschleifenmusik
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        guild_id = str(member.guild.id)
        config = load_config()
        waiting_room_id = config.get(guild_id, {}).get("waiting_room_id")

        if not waiting_room_id:
            return

        voice_channel = member.guild.get_channel(waiting_room_id)
        if not voice_channel:
            return

        if after.channel and after.channel.id == waiting_room_id:
            vc = discord.utils.get(self.voice_clients, guild=member.guild)
            if not vc or not vc.is_connected():
                vc = await voice_channel.connect()
                self.loop.create_task(self.play_looping_music(vc))

        elif before.channel and before.channel.id == waiting_room_id:
            vc = discord.utils.get(self.voice_clients, guild=member.guild)
            if vc and len(voice_channel.members) <= 1:
                await vc.disconnect()

    async def play_looping_music(self, vc):
        music_file = "support_music.mp3"
        if not os.path.exists(music_file):
            print(f"Warnung: {music_file} nicht gefunden!")
            return

        while vc.is_connected():
            if not vc.is_playing():
                vc.play(discord.FFmpegPCMAudio(music_file))
            await asyncio.sleep(1)

bot = MyBot()

# --- ADMIN COMMANDS ---

@bot.tree.command(name="set_waiting_room", description="Legt den Sprachkanal für die Warteschleifenmusik fest")
@app_commands.checks.has_permissions(administrator=True)
async def set_waiting_room(interaction: discord.Interaction, kanal: discord.VoiceChannel):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config: config[guild_id] = {}
    config[guild_id]["waiting_room_id"] = kanal.id
    save_config(config)
    await interaction.response.send_message(f"✅ Warteschleifen-Kanal auf **{kanal.name}** gesetzt.", ephemeral=True)

ticket_roles_group = app_commands.Group(name="ticket_roles", description="Verwalte Supporter-Rollen für Tickets")

@ticket_roles_group.command(name="add", description="Fügt eine Supporter-Rolle hinzu")
async def add_support_role(interaction: discord.Interaction, rolle: discord.Role):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config: config[guild_id] = {"verify_panels": [], "ticket_panels": [], "support_roles": []}
    if "support_roles" not in config[guild_id]: config[guild_id]["support_roles"] = []
    if rolle.id not in config[guild_id]["support_roles"]:
        config[guild_id]["support_roles"].append(rolle.id)
        save_config(config)
        await interaction.response.send_message(f"✅ Rolle **{rolle.name}** hinzugefügt.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Rolle ist bereits eingetragen.", ephemeral=True)

@ticket_roles_group.command(name="remove", description="Entfernt eine Supporter-Rolle")
async def remove_support_role(interaction: discord.Interaction, rolle: discord.Role):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id in config and "support_roles" in config[guild_id]:
        if rolle.id in config[guild_id]["support_roles"]:
            config[guild_id]["support_roles"].remove(rolle.id)
            save_config(config)
            await interaction.response.send_message(f"✅ Rolle **{rolle.name}** entfernt.", ephemeral=True)
            return
    await interaction.response.send_message(f"⚠️ Rolle nicht gefunden.", ephemeral=True)

bot.tree.add_command(ticket_roles_group)

@bot.tree.command(name="ticket_edit", description="Bearbeite ein spezifisches Ticket-Panel via Message ID")
@app_commands.describe(
    message_id="Die ID der Nachricht des Panels, das du bearbeiten willst",
    titel="Der neue Titel für dieses spezifische Panel",
    beschreibung="Die neue Beschreibung für dieses spezifische Panel (Nutze \\n für Zeilenumbrüche)",
    farbe="Hex-Farbe (z.B. #2ecc71 für Grün)"
)
@app_commands.checks.has_permissions(administrator=True)
async def ticket_edit(interaction: discord.Interaction, message_id: str, titel: str = None, beschreibung: str = None, farbe: str = None):
    try:
        msg_id = int(message_id)
        message = await interaction.channel.fetch_message(msg_id)
    except Exception:
        return await interaction.response.send_message("❌ Nachricht nicht gefunden.", ephemeral=True)

    if not message.embeds or message.author.id != bot.user.id:
        return await interaction.response.send_message("❌ Ungültige Nachricht.", ephemeral=True)

    embed = message.embeds[0]
    
    if titel: embed.title = titel
    if beschreibung: 
        embed.description = beschreibung.replace("\\n", "\n")
    if farbe:
        try:
            embed.color = discord.Color(int(farbe.replace("#", ""), 16))
        except ValueError:
            return await interaction.response.send_message("❌ Ungültige Farbe.", ephemeral=True)

    await message.edit(embed=embed)
    await interaction.response.send_message(f"✅ Panel aktualisiert.", ephemeral=True)

@bot.tree.command(name="setup_verify", description="Erstellt ein Verify-Panel")
async def setup_verify(interaction: discord.Interaction, rolle: discord.Role):
    guild_id = str(interaction.guild_id)
    config = load_config()
    if guild_id not in config: config[guild_id] = {"verify_panels": [], "ticket_panels": [], "support_roles": []}
    
    embed = discord.Embed(title="Server Verifizierung", description=f"Klicke auf den Button für die Rolle **{rolle.name}**.", color=discord.Color.blue())
    message = await interaction.channel.send(embed=embed, view=VerifyView(rolle.id))
    
    config[guild_id].setdefault("verify_panels", []).append({"role_id": rolle.id, "channel_id": interaction.channel_id, "message_id": message.id})
    save_config(config)
    await interaction.response.send_message(f"✅ Verify-Panel erstellt.", ephemeral=True)

@bot.tree.command(name="setup_tickets", description="Erstellt ein Ticket-System")
@app_commands.describe(kategorien='Format: "Emoji Name | Beschreibung", "Emoji Name | Beschreibung"')
async def setup_tickets(interaction: discord.Interaction, kategorien: str):
    guild_id = str(interaction.guild_id)
    raw_list = re.findall(r'"([^"]*)"', kategorien)
    if not raw_list: raw_list = [c.strip() for c in kategorien.split(",") if c.strip()]

    formatted_cats = []
    for item in raw_list:
        parts = item.split("|")
        main_part = parts[0].strip()
        description = (parts[1].strip().replace("\\n", "\n") if len(parts) > 1 else None)
        
        emoji, label = None, main_part
        match = re.search(r'^([^\x00-\x7F]|\W+)\s*(.*)', main_part)
        if match:
            emoji = match.group(1).strip()
            label = match.group(2).strip() if match.group(2) else emoji
            
        formatted_cats.append({
            "label": label[:100], 
            "value": label[:100], 
            "emoji": emoji, 
            "description": description[:100] if description else None
        })

    if not formatted_cats: 
        return await interaction.response.send_message('❌ Fehler: Nutze Anführungszeichen.', ephemeral=True)

    config = load_config()
    if guild_id not in config: config[guild_id] = {"verify_panels": [], "ticket_panels": [], "support_roles": []}
    
    view = TicketView(formatted_cats)
    embed = discord.Embed(
        title="Support-Tickets", 
        description="Wähle eine Kategorie aus dem Menü unten aus, um ein Ticket zu erstellen.", 
        color=discord.Color.gold()
    )
    
    message = await interaction.channel.send(embed=embed, view=view)
    
    config[guild_id].setdefault("ticket_panels", []).append({
        "categories": formatted_cats, 
        "channel_id": interaction.channel_id, 
        "message_id": message.id
    })
    save_config(config)
    
    # Anleitung zum Bearbeiten des Panels hinzufügen
    guide_text = (
        f"✅ **Ticket-Panel erstellt!**\n\n"
        f"Um das Aussehen des Panels (Titel, Beschreibung, Farbe) anzupassen, nutze:\n"
        f"`/ticket_edit message_id:{message.id} titel:... beschreibung:... farbe:...`"
    )
    await interaction.response.send_message(guide_text, ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ Bot online als {bot.user}')

if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
    else: print("Fehler: DISCORD_TOKEN fehlt!")