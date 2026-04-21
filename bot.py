import discord
from discord.ext import commands
import os
import json
import datetime
from dotenv import load_dotenv
from utils import (
    load_config, load_open_apps, _load_default_application, init_language,
    DEFAULT_LANG, TOKEN, DEBUG, WHITELIST_FILE, save_whitelist
)

load_dotenv()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True
        intents.presences = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Ensure configs directory exists
        os.makedirs('configs', exist_ok=True)

        # Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'✅ Cog loaded: {filename}')
                except Exception as e:
                    print(f'❌ Error loading {filename}: {e}')

        # Persistent Views Registration
        from cogs.tickets import TicketView, TicketControlView
        from cogs.verify import VerifyView
        from cogs.selfroles import SelfRoleView
        from cogs.applications import ApplicationPanelView, ApplicationReviewView

        config = load_config()
        for guild_id_str, data in config.items():
            if not isinstance(data, dict):
                continue
            
            # Verify Panels
            for panel in data.get("verify_panels", []):
                self.add_view(VerifyView(panel["role_id"]))
            
            # Ticket Panels
            for t_panel in data.get("ticket_panels", []):
                supp_ids = t_panel.get("supporter_role_ids")
                if not supp_ids:
                    old_id = t_panel.get("supporter_role_id")
                    supp_ids = [old_id] if old_id else []
                self.add_view(TicketView(t_panel["categories"], supp_ids))
            
            # Self Role Panels
            for s_panel in data.get("selfrole_panels", []):
                # Using the message_id as panel_id for persistence
                self.add_view(SelfRoleView(s_panel["roles"], str(s_panel.get("message_id", "default"))))
            
            # Application Panels
            for idx, _ap in enumerate(data.get("application_panels", [])):
                self.add_view(ApplicationPanelView(panel_index=idx))

        # Persistent Views that don't depend on guild config directly for init
        self.add_view(TicketControlView())

        # Restore open ApplicationReviewViews
        open_apps = load_open_apps()
        for entry in open_apps.values():
            try:
                self.add_view(ApplicationReviewView(
                    applicant_id=entry["applicant_id"],
                    thread_id=entry["thread_id"],
                    review_channel_id=entry["review_channel_id"]
                ))
            except Exception:
                pass

        await self.tree.sync()
        print("🌐 Slash Commands synchronized globally.")

bot = MyBot()

@bot.event
async def on_ready():
    print(f'✅ Bot online as {bot.user}')
    init_language()
    
    if not os.path.exists(WHITELIST_FILE):
        save_whitelist(["tenor.com", "giphy.com"])
    
    config = load_config()
    pres = config.get("bot_presence")
    if pres:
        status_val = pres.get("status", "online")
        d_status = getattr(discord.Status, status_val, discord.Status.online)
        t_val = pres.get("type", "playing")
        text = pres.get("text", "")
        url = pres.get("url", "https://twitch.tv/discord")
        act = None
        if t_val == "playing":
            act = discord.Game(name=text)
        elif t_val == "streaming":
            act = discord.Streaming(name=text, url=url)
        elif t_val == "listening":
            act = discord.Activity(type=discord.ActivityType.listening, name=text)
        elif t_val == "watching":
            act = discord.Activity(type=discord.ActivityType.watching, name=text)
        await bot.change_presence(status=d_status, activity=act)

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_TOKEN is missing!")