import discord
from discord import app_commands
from discord.ext import commands
import datetime
import re
import json
from utils import (
    t, td, tp, load_config, save_config, now_timestamp, short_time,
    make_dm_embed, send_dm, _make_role_select_view
)
from state import _ticket_wizard_state, _wizard_interactions

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # No specific slash commands for tickets yet, they are handled via setup and views

class TicketCloseModal(discord.ui.Modal):
    def __init__(self, creator_id: int = None):
        super().__init__(title=t("modals", "ticket_close_title"))
        self.creator_id = creator_id
        self.reason = discord.ui.TextInput(
            label=t("modals", "ticket_close_label"),
            placeholder=t("modals", "ticket_close_ph"),
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        thread = interaction.channel
        grund_text = self.reason.value
        
        await interaction.response.send_message(t("success", "ticket_closed_reply"), ephemeral=True)

        close_embed = discord.Embed(
            title=t("embeds", "ticket_closed", "title"),
            description=t("embeds", "ticket_closed", "desc"),
            color=discord.Color.red(),
            timestamp=now_timestamp()
        )
        close_embed.add_field(name=t("embeds", "ticket_closed", "f_by"), value=interaction.user.mention, inline=True)
        close_embed.add_field(name=t("embeds", "ticket_closed", "f_reason"), value=grund_text, inline=False)
        
        if interaction.guild.icon:
            close_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        
        await thread.send(embed=close_embed)

        if self.creator_id:
            guild = interaction.guild
            creator = guild.get_member(self.creator_id)
            if creator:
                dm_embed = make_dm_embed(
                    title=t("embeds", "dm_ticket_closed", "title"),
                    description=t("embeds", "dm_ticket_closed", "desc"),
                    color=discord.Color.red(),
                    guild=guild,
                    fields=[
                        (t("embeds", "dm_ticket_closed", "f_server"), guild.name, True),
                        (t("embeds", "dm_ticket_closed", "f_by"), str(interaction.user), True),
                        (t("embeds", "dm_ticket_closed", "f_date"), short_time(), True),
                        (t("embeds", "dm_ticket_closed", "f_reason"), grund_text, False),
                    ],
                    footer_system=t("embeds", "shared", "footer_ticket")
                )
                await send_dm(creator, embed=dm_embed)

        await thread.edit(locked=True, archived=True)

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claim.label = t("buttons", "claim_ticket")
        self.close.label = t("buttons", "close_ticket")

    def get_creator_id(self, interaction: discord.Interaction):
        try:
            embed = interaction.message.embeds[0]
            match = re.search(r'<@!?(\d+)>', embed.description)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def is_supporter(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        config = load_config()
        guild_data = config.get(str(interaction.guild_id), {})
        user_role_ids = [role.id for role in interaction.user.roles]
        for panel in guild_data.get("ticket_panels", []):
            if any(rid in user_role_ids for rid in panel.get("supporter_role_ids", [])):
                return True
            for cat in panel.get("categories", []):
                cat_role_ids = cat.get("supporter_role_ids") or []
                if any(rid in user_role_ids for rid in cat_role_ids):
                    return True
        return False

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.blurple, emoji="📋", custom_id="persistent_claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message(t("errors", "supporter_only_claim"), ephemeral=True)
        embed = interaction.message.embeds[0]
        if any(field.name == t("embeds", "ticket_closed", "f_agent") for field in embed.fields):
            return await interaction.response.send_message(t("errors", "already_claimed"), ephemeral=True)
        embed.add_field(name=t("embeds", "ticket_closed", "f_agent"), value=interaction.user.mention, inline=True)
        embed.color = discord.Color.blue()
        if interaction.guild and interaction.guild.icon:
            embed.set_footer(text=f"{interaction.guild.name} • {t('embeds', 'shared', 'footer_ticket')}", icon_url=interaction.guild.icon.url)
        else:
            embed.set_footer(text=t("embeds", "shared", "footer_ticket"))
        button.disabled = True
        button.label = t("buttons", "claimed_done")
        await interaction.response.edit_message(embed=embed, view=self)
        status_embed = discord.Embed(
            description=t("success", "ticket_claimed_followup", mention=interaction.user.mention),
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=status_embed)
        creator_id = self.get_creator_id(interaction)
        if creator_id:
            creator = interaction.guild.get_member(creator_id)
            if creator:
                dm_embed = make_dm_embed(
                    title=t("embeds", "dm_ticket_claimed", "title"),
                    description=t("embeds", "dm_ticket_claimed", "desc"),
                    color=discord.Color.blue(),
                    guild=interaction.guild,
                    fields=[
                        (t("embeds", "dm_ticket_claimed", "f_server"), interaction.guild.name, True),
                        (t("embeds", "dm_ticket_claimed", "f_agent"), interaction.user.mention, True),
                        (t("embeds", "dm_ticket_claimed", "f_date"), short_time(), True),
                    ],
                    jump_url=interaction.channel.jump_url,
                    footer_system=t("embeds", "shared", "footer_ticket")
                )
                await send_dm(creator, embed=dm_embed)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="persistent_close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_supporter(interaction):
            return await interaction.response.send_message(t("errors", "supporter_only_close"), ephemeral=True)
        await interaction.response.send_modal(TicketCloseModal(self.get_creator_id(interaction)))

class TicketSelect(discord.ui.Select):
    def __init__(self, options, supporter_role_ids, categories_full_data=None):
        super().__init__(
            placeholder=t("selects", "ticket_placeholder"),
            options=options,
            custom_id="ticket_select_persistent"
        )
        self.supporter_role_ids = supporter_role_ids
        self.categories_full_data = categories_full_data or []

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        guild = interaction.guild
        guild_id = str(guild.id)
        config = load_config()

        if guild_id not in config:
            config[guild_id] = {}
        if "category_counters" not in config[guild_id]:
            config[guild_id]["category_counters"] = {}
        if selected_value not in config[guild_id]["category_counters"]:
            config[guild_id]["category_counters"][selected_value] = 0

        config[guild_id]["category_counters"][selected_value] += 1
        ticket_id = config[guild_id]["category_counters"][selected_value]
        formatted_id = f"{ticket_id:04d}"

        target_role_ids = self.supporter_role_ids
        for cat in self.categories_full_data:
            if cat['value'] == selected_value and cat.get('supporter_role_ids'):
                target_role_ids = cat['supporter_role_ids']
                break

        main_category_name = "▄▬▬「Tickets」▬▬▄"
        category = discord.utils.get(guild.categories, name=main_category_name)

        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True, send_messages=False, add_reactions=False,
                    create_public_threads=False, create_private_threads=False, send_messages_in_threads=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, manage_channels=True, manage_roles=True
                )
            }
            category = await guild.create_category(name=main_category_name, overwrites=overwrites)

        cat_label = selected_value
        for cat in self.categories_full_data:
            if cat.get("value") == selected_value:
                cat_label = cat.get("label", selected_value)
                break

        config[guild_id].setdefault("category_channels", {})
        cached_channel_id = config[guild_id]["category_channels"].get(selected_value)
        target_channel = None

        if cached_channel_id:
            target_channel = guild.get_channel(cached_channel_id)

        if not target_channel:
            clean_label  = cat_label.strip()
            channel_name = re.sub(r'[^a-z0-9\-]', '-', clean_label.lower().replace(' ', '-'))[:80].strip('-') + "-tickets"
            channel_name = re.sub(r'-+', '-', channel_name)
            target_channel = discord.utils.get(category.text_channels, name=channel_name)

            if not target_channel:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=True, send_messages=False, add_reactions=False, use_application_commands=False
                    ),
                    guild.me: discord.PermissionOverwrite(
                        view_channel=True, manage_channels=True, send_messages=True
                    )
                }
                for rid in target_role_ids:
                    role = guild.get_role(rid)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(
                            view_channel=True, send_messages=True, manage_threads=True
                        )

                target_channel = await guild.create_text_channel(
                    name=channel_name, category=category, overwrites=overwrites, topic="Tickets: " + clean_label
                )

                info_embed = discord.Embed(
                    title=t("embeds", "ticket_channel", "title", category=clean_label),
                    description=t("embeds", "ticket_channel", "desc", category=clean_label),
                    color=discord.Color.blurple()
                )
                if guild.icon:
                    info_embed.set_thumbnail(url=guild.icon.url)
                info_embed.set_footer(text=guild.name)
                await target_channel.send(embed=info_embed)

            config[guild_id]["category_channels"][selected_value] = target_channel.id

        save_config(config)

        clean_username  = interaction.user.display_name.replace(' ', '-').lower()
        clean_cat_short = cat_label.lower()[:5]
        thread_name = f"{clean_cat_short}-{formatted_id}-{clean_username}"

        thread = await target_channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread)

        await interaction.response.send_message(
            t("success", "ticket_created_reply", id=formatted_id, category=cat_label, mention=thread.mention, url=thread.jump_url),
            ephemeral=True
        )

        await thread.add_user(interaction.user)

        added_members = set()
        for rid in target_role_ids:
            base_role = guild.get_role(rid)
            if base_role:
                for member in guild.members:
                    if member.bot or member.id in added_members:
                        continue
                    if any(r.position >= base_role.position for r in member.roles):
                        try:
                            await thread.add_user(member)
                            added_members.add(member.id)
                        except Exception:
                            pass

        ticket_embed = discord.Embed(
            title=t("embeds", "ticket_thread", "title", id=formatted_id, category=cat_label),
            description=t("embeds", "ticket_thread", "desc", mention=interaction.user.mention),
            color=discord.Color.green(),
            timestamp=now_timestamp()
        )
        ticket_embed.add_field(name=t("embeds", "ticket_thread", "f_number"), value=f"`#{formatted_id}`", inline=True)
        ticket_embed.add_field(name=t("embeds", "ticket_thread", "f_category"), value=f"`{cat_label}`", inline=True)
        ticket_embed.add_field(name=t("embeds", "ticket_thread", "f_created_by"), value=interaction.user.mention, inline=True)
        ticket_embed.add_field(name=t("embeds", "ticket_thread", "f_next_steps"), value=t("embeds", "ticket_thread", "next_steps_val"), inline=False)
        footer_txt = f"{guild.name}  •  {t('embeds', 'shared', 'footer_ticket')}"
        if guild.icon:
            ticket_embed.set_footer(text=footer_txt, icon_url=guild.icon.url)
        else:
            ticket_embed.set_footer(text=footer_txt)

        await thread.send(embed=ticket_embed, view=TicketControlView())

        dm_embed = make_dm_embed(
            title=t("embeds", "dm_ticket_created", "title"),
            description=t("embeds", "dm_ticket_created", "desc"),
            color=discord.Color.green(),
            guild=guild,
            fields=[
                (t("embeds", "dm_ticket_created", "f_server"), guild.name, True),
                (t("embeds", "dm_ticket_created", "f_cat"), selected_value, True),
                (t("embeds", "dm_ticket_created", "f_nr"), f"#{formatted_id}", True),
            ],
            jump_url=thread.jump_url,
            footer_system=t("embeds", "shared", "footer_ticket")
        )
        await send_dm(interaction.user, embed=dm_embed)

        try:
            fresh_view = TicketView(self.categories_full_data, self.supporter_role_ids)
            await interaction.message.edit(view=fresh_view)
        except Exception:
            pass

class TicketView(discord.ui.View):
    def __init__(self, categories_data, supporter_role_ids):
        super().__init__(timeout=None)
        options = []
        seen_values = set()
        for i, item in enumerate(categories_data):
            base_val = (item.get('value') or item['label'])[:95]
            val = base_val
            if val in seen_values:
                val = (base_val[:90] + "_" + str(i))[:100]
            seen_values.add(val)
            options.append(discord.SelectOption(
                label=item['label'][:100],
                value=val,
                emoji=item.get('emoji'),
                description=item.get('description', '')[:100] if item.get('description') else None
            ))
        self.clear_items()
        self.add_item(TicketSelect(options, supporter_role_ids, categories_data))

# --- TICKET WIZARD ---

def _build_ticket_embed(state: dict, guild) -> discord.Embed:
    GOLD = discord.Color.gold()
    embed = discord.Embed(title=t("embeds", "ticket_wizard", "title"), color=GOLD)

    title_val = state.get("title") or t("embeds", "wizard", "not_set")
    roles     = state.get("supporter_role_ids", [])
    roles_val = (" ".join("<@&" + str(r) + ">" for r in roles)
                 if roles else t("embeds", "wizard", "not_set"))

    desc_val    = (state.get("embed_desc") or "")[:40] + ("..." if len(state.get("embed_desc") or "") > 40 else "")
    color_val   = ("#" + state["embed_color"]) if state.get("embed_color") else t("embeds", "ticket_wizard", "color_default")
    thumb_val   = t("embeds", "ticket_wizard", "thumb_on") if state.get("embed_thumbnail") else t("embeds", "ticket_wizard", "thumb_off")

    embed.add_field(
        name=t("embeds", "ticket_wizard", "f_info"),
        value=(
            t("embeds", "ticket_wizard", "f_title")  + " " + title_val  + "\n" +
            t("embeds", "ticket_wizard", "f_roles")  + " " + roles_val
        ),
        inline=False
    )

    embed.add_field(
        name=t("embeds", "ticket_wizard", "f_embed_style"),
        value=(
            t("embeds", "ticket_wizard", "f_desc")   + " " + (desc_val or t("embeds", "wizard", "not_set")) + "\n" +
            t("embeds", "ticket_wizard", "f_color")  + " " + color_val + "\n" +
            t("embeds", "ticket_wizard", "f_thumb")  + " " + thumb_val
        ),
        inline=False
    )

    cats = state.get("categories", [])
    if cats:
        lines = []
        for i, c in enumerate(cats[:10]):
            emoji_str = (c.get("emoji") + " ") if c.get("emoji") else ""
            desc_str  = ("  —  " + c["description"][:30]) if c.get("description") else ""
            lines.append("**" + str(i + 1) + ".** " + emoji_str + c["label"] + desc_str)
        if len(cats) > 10:
            lines.append(t("embeds", "wizard", "q_more", n=len(cats) - 10))
        cats_val = "\n".join(lines)
    else:
        cats_val = t("embeds", "ticket_wizard", "cats_empty")

    embed.add_field(
        name=t("embeds", "ticket_wizard", "f_cats") + " (" + str(len(cats)) + ")",
        value=cats_val,
        inline=False
    )

    if guild and guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    return embed

class TicketSetupEmbedModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "ticket_setup_embed_title"))
        self.user_id = user_id
        state = _ticket_wizard_state.get(user_id, {})
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_desc_label"),
            placeholder=t("modals", "ticket_setup_embed_desc_ph"),
            default=state.get("embed_desc", ""),
            style=discord.TextStyle.paragraph, required=False, max_length=1000
        )
        self.f_color = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_color_label"),
            placeholder=t("modals", "ticket_setup_embed_color_ph"),
            default=state.get("embed_color", ""),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_thumbnail = discord.ui.TextInput(
            label=t("modals", "ticket_setup_embed_thumb_label"),
            placeholder=t("modals", "ticket_setup_embed_thumb_ph"),
            default="yes" if state.get("embed_thumbnail", True) else "no",
            style=discord.TextStyle.short, required=False, max_length=5
        )
        self.add_item(self.f_desc)
        self.add_item(self.f_color)
        self.add_item(self.f_thumbnail)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _ticket_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        color_raw = self.f_color.value.strip().lstrip("#")
        if color_raw:
            try:
                int(color_raw, 16)
            except ValueError:
                return await interaction.response.send_message(t("errors", "ticket_invalid_color"), ephemeral=True)
        thumb_raw = self.f_thumbnail.value.strip().lower()
        thumbnail = thumb_raw not in ("no", "n", "false", "0", "nein")
        _ticket_wizard_state[uid].update({
            "embed_desc":      self.f_desc.value.strip(),
            "embed_color":     color_raw,
            "embed_thumbnail": thumbnail,
        })
        embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
        view  = TicketSetupMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass

class TicketSetupInfoModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "ticket_setup_info_title"))
        self.user_id = user_id
        state = _ticket_wizard_state.get(user_id, {})
        self.f_title = discord.ui.TextInput(
            label=t("modals", "ticket_setup_title_label"),
            placeholder=t("modals", "ticket_setup_title_ph"),
            default=state.get("title", ""),
            style=discord.TextStyle.short, required=True, max_length=80
        )
        self.add_item(self.f_title)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        _ticket_wizard_state.setdefault(uid, {"categories": []}).update({
            "title": self.f_title.value.strip(),
        })
        embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
        view  = TicketSetupMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(uid)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass

class TicketSetupCategoryModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title=t("modals", "ticket_setup_cat_title"))
        self.user_id = user_id
        self.f_label = discord.ui.TextInput(
            label=t("modals", "ticket_setup_cat_label"),
            placeholder=t("modals", "ticket_setup_cat_label_ph"),
            style=discord.TextStyle.short, required=True, max_length=100
        )
        self.f_emoji = discord.ui.TextInput(
            label=t("modals", "ticket_setup_cat_emoji"),
            placeholder=t("modals", "ticket_setup_cat_emoji_ph"),
            style=discord.TextStyle.short, required=False, max_length=10
        )
        self.f_desc = discord.ui.TextInput(
            label=t("modals", "ticket_setup_cat_desc"),
            placeholder=t("modals", "ticket_setup_cat_desc_ph"),
            style=discord.TextStyle.short, required=False, max_length=100
        )
        self.add_item(self.f_label)
        self.add_item(self.f_emoji)
        self.add_item(self.f_desc)

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.user_id
        if uid not in _ticket_wizard_state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        label = self.f_label.value.strip()[:100]
        emoji = None
        emoji_raw = self.f_emoji.value.strip()
        if emoji_raw:
            for char in emoji_raw:
                if ord(char) > 0x27BF:
                    emoji = char
                    break
            if not emoji:
                emoji = emoji_raw[:10]
        import uuid as _uuid
        unique_val = (label[:85] + "_" + _uuid.uuid4().hex[:6])[:100]
        _ticket_wizard_state[uid].setdefault("categories", []).append({
            "label":             label,
            "value":             unique_val,
            "emoji":             emoji,
            "description":       self.f_desc.value.strip()[:100] or None,
            "supporter_role_ids": None
        })
        embed = _build_ticket_embed(_ticket_wizard_state[uid], interaction.guild)
        view  = TicketSetupMainView(uid)
        await interaction.response.defer(ephemeral=True)
        _orig = _wizard_interactions.get(self.user_id)
        if _orig:
            try:
                await _orig.edit_original_response(embed=embed, view=view)
            except Exception:
                pass

class TicketSetupMainView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        state = _ticket_wizard_state.get(user_id, {})
        has_title = bool(state.get("title"))
        has_roles = bool(state.get("supporter_role_ids"))
        has_cats  = bool(state.get("categories"))

        self.edit_info_btn.label   = t("buttons", "wizard_edit_info")
        self.edit_info_btn.style   = discord.ButtonStyle.secondary if has_title else discord.ButtonStyle.danger
        self.pick_roles_btn.label  = t("buttons", "wizard_pick_roles")
        self.pick_roles_btn.style  = discord.ButtonStyle.secondary if has_roles else discord.ButtonStyle.danger
        self.edit_embed_btn.label  = t("buttons", "ticket_wizard_edit_embed")
        self.add_cat_btn.label     = t("buttons", "ticket_wizard_add_cat")
        self.add_cat_btn.style     = discord.ButtonStyle.blurple if has_cats else discord.ButtonStyle.danger
        self.remove_cat_btn.label  = t("buttons", "ticket_wizard_remove_cat")
        self.preview_btn.label     = t("buttons", "wizard_preview")
        self.finish_btn.label      = t("buttons", "wizard_finish")
        self.cancel_btn.label      = t("buttons", "wizard_cancel")

    def _check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="✏️ Edit Info", style=discord.ButtonStyle.secondary, row=0)
    async def edit_info_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(TicketSetupInfoModal(self.user_id))

    @discord.ui.button(label="👥", style=discord.ButtonStyle.secondary, row=0)
    async def pick_roles_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        view = _make_role_select_view(
            self.user_id, "supporter_role_ids", _ticket_wizard_state,
            t("selects", "wizard_pick_roles"), multi=True,
            refresh_fn=lambda uid, guild: (_build_ticket_embed(_ticket_wizard_state[uid], guild), TicketSetupMainView(uid))
        )
        await interaction.response.send_message(content=t("success", "wizard_pick_roles_hint"), view=view, ephemeral=True)

    @discord.ui.button(label="🎨 Edit Embed", style=discord.ButtonStyle.secondary, row=0)
    async def edit_embed_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        await interaction.response.send_modal(TicketSetupEmbedModal(self.user_id))

    @discord.ui.button(label="➕ Add Category", style=discord.ButtonStyle.blurple, row=0)
    async def add_cat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id, {})
        if len(state.get("categories", [])) >= 25:
            return await interaction.response.send_message(t("errors", "ticket_max_cats"), ephemeral=True)
        await interaction.response.send_modal(TicketSetupCategoryModal(self.user_id))

    @discord.ui.button(label="🗑️ Remove Last", style=discord.ButtonStyle.danger, row=1)
    async def remove_cat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id, {})
        if not state.get("categories"):
            return await interaction.response.send_message(t("errors", "ticket_no_cats"), ephemeral=True)
        state["categories"].pop()
        embed = _build_ticket_embed(state, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=TicketSetupMainView(self.user_id))

    @discord.ui.button(label="👁️ Preview", style=discord.ButtonStyle.secondary, row=1)
    async def preview_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        title = state.get("title") or t("embeds", "ticket_panel", "title")
        desc  = state.get("embed_desc") or t("embeds", "ticket_panel", "desc")
        color_hex = state.get("embed_color")
        try:
            color = discord.Color(int(color_hex, 16)) if color_hex else discord.Color.gold()
        except (ValueError, TypeError):
            color = discord.Color.gold()
        preview = discord.Embed(title=title, description=desc, color=color, timestamp=now_timestamp())
        if state.get("embed_thumbnail", True) and interaction.guild.icon:
            preview.set_thumbnail(url=interaction.guild.icon.url)
        preview.set_footer(text=t("embeds", "ticket_panel", "footer", name=interaction.guild.name))
        cats = state.get("categories", [])
        if cats:
            cat_lines = ["• " + ((c.get("emoji") + " ") if c.get("emoji") else "") + "**" + c["label"] + "**" + (" — " + c["description"] if c.get("description") else "") for c in cats]
            preview.add_field(name=t("embeds", "ticket_wizard", "preview_cats_title"), value="\n".join(cat_lines), inline=False)
        await interaction.response.send_message(content=t("success", "wizard_preview_note"), embed=preview, ephemeral=True)

    @discord.ui.button(label="🚀 Finish", style=discord.ButtonStyle.green, row=2)
    async def finish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        state = _ticket_wizard_state.get(self.user_id)
        if not state:
            return await interaction.response.send_message(t("errors", "panel_not_found"), ephemeral=True)
        if not state.get("title") or not state.get("supporter_role_ids") or not state.get("categories"):
            return await interaction.response.send_message(t("errors", "wizard_missing_categories"), ephemeral=True)
        await self._finalize(interaction)

    @discord.ui.button(label="✖️ Cancel", style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._check(interaction):
            return await interaction.response.send_message(t("errors", "application_not_yours"), ephemeral=True)
        _ticket_wizard_state.pop(self.user_id, None)
        await interaction.response.edit_message(content=t("errors", "application_cancelled"), embed=None, view=None)

    async def _finalize(self, interaction: discord.Interaction):
        state = _ticket_wizard_state.pop(self.user_id, None)
        if not state: return
        guild_id = str(interaction.guild_id)
        config = load_config()
        if guild_id not in config: config[guild_id] = {}
        cats = state["categories"]
        role_ids = state["supporter_role_ids"]
        title = state.get("title", t("embeds", "ticket_panel", "title"))
        view = TicketView(cats, role_ids)
        desc = state.get("embed_desc") or t("embeds", "ticket_panel", "desc")
        color_hex = state.get("embed_color")
        try:
            color = discord.Color(int(color_hex, 16)) if color_hex else discord.Color.gold()
        except (ValueError, TypeError):
            color = discord.Color.gold()
        embed = discord.Embed(title=title, description=desc, color=color)
        if state.get("embed_thumbnail", True) and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=t("embeds", "ticket_panel", "footer", name=interaction.guild.name))
        message = await interaction.channel.send(embed=embed, view=view)
        config[guild_id].setdefault("ticket_panels", []).append({
            "categories": cats, "channel_id": interaction.channel_id, "message_id": message.id,
            "supporter_role_ids": role_ids, "created_at": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"), "title": title
        })
        save_config(config)
        done_embed = discord.Embed(title=t("embeds", "wizard", "done_title"), description=t("success", "ticket_panel_created", id=message.id), color=discord.Color.green(), timestamp=now_timestamp())
        if interaction.guild.icon: done_embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url)
        await interaction.response.edit_message(embed=done_embed, view=None)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
