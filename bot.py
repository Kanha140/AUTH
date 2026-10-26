import discord
from discord.ext import commands
from discord import app_commands, Embed, PermissionOverwrite
import logging
import asyncio

import database
import webhook_logger
from config import DISCORD_TOKEN, MAIN_OWNER_ID, GUILD_ID, API_HOST, API_PORT
from panel import ResellerPanelView, create_panel_embed, can_manage_reseller
from api import start_api_server

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AuthBot")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

class AuthBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.api_runner = None

    async def setup_hook(self):
        # 1. Initialize SQLite Database
        database.init_db()
        logger.info("Database initialized successfully.")

        # 2. Register Persistent View for Buttons
        self.add_view(ResellerPanelView())
        logger.info("Persistent ResellerPanelView registered.")

        # 3. Start Built-in Auth API HTTP Server
        try:
            self.api_runner = await start_api_server(API_HOST, API_PORT)
            logger.info(f"Auth API server started on http://{API_HOST}:{API_PORT}")
        except Exception as e:
            logger.error(f"Failed to start Auth API server: {e}")

        # 4. Instant Slash Command Sync to Guild
        try:
            guild_obj = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild_obj)
            synced = await self.tree.sync(guild=guild_obj)
            logger.info(f"Synced {len(synced)} slash commands to Guild ID: {GUILD_ID}")
        except Exception as e:
            logger.error(f"Failed to sync slash commands to guild: {e}")

    async def close(self):
        if self.api_runner:
            await self.api_runner.cleanup()
        await super().close()

bot = AuthBot()

async def keep_alive_task():
    """Pings the public Render URL every 10 minutes so the free tier never sleeps."""
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not render_url:
        return
    logger.info(f"Keep-Alive auto-pinger initialized for {render_url}")
    await asyncio.sleep(60)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{render_url}/api/status", timeout=10) as resp:
                    logger.info(f"Keep-Alive ping sent to {render_url}, status: {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-Alive ping error: {e}")
        await asyncio.sleep(600)  # Ping every 10 minutes

@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user} (ID: {bot.user.id})")
    activity = discord.Activity(type=discord.ActivityType.watching, name="Keys & HWID Auth")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    asyncio.create_task(keep_alive_task())

# ================= PERMISSION HELPERS =================

def is_main_owner(user_id: int) -> bool:
    """Only the primary Owner ID (1378068938847424522)."""
    return user_id == MAIN_OWNER_ID

def is_any_owner(user_id: int) -> bool:
    """Main Owner or any co-owner added via /owner add."""
    return database.is_owner(user_id)

def to_bold_font(text: str) -> str:
    """Converts regular text to aesthetic Unicode bold font for Discord channel names."""
    bold_map = {
        'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴',
        'h': '𝗵', 'i': '𝗶', 'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻',
        'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿', 's': '𝘀', 't': '𝘁', 'u': '𝘂',
        'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
        'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚',
        'H': '𝗛', 'I': '𝗜', 'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡',
        'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥', 'S': '𝗦', 'T': '𝗧', 'U': '𝗨',
        'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭',
        '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲',
        '7': '𝟳', '8': '𝟴', '9': '𝟵'
    }
    return ''.join(bold_map.get(ch, ch) for ch in text)

def format_reseller_channel_name(raw_name: str) -> str:
    """Formats channel name with Lock Emoji and Bold Text (e.g. 🔒・𝗿𝗲𝘀𝗲𝗹𝗹𝗲𝗿-𝗮𝗹𝗲𝘅)."""
    cleaned = raw_name.strip().replace(' ', '-')
    if cleaned.startswith("🔒"):
        cleaned = cleaned.lstrip("🔒・┆|- ")
    bold_text = to_bold_font(cleaned)
    return f"🔒・{bold_text}"

# ================= OWNER COMMAND GROUP =================

owner_group = app_commands.Group(name="owner", description="Owner management commands (Main Owner Only)")

@owner_group.command(name="add", description="Add a co-owner with full management rights (Main Owner Only)")
@app_commands.describe(member="Select user to grant Owner access")
async def owner_add(interaction: discord.Interaction, member: discord.Member):
    if not is_main_owner(interaction.user.id):
        await interaction.response.send_message("❌ **Access Denied:** Only the Main Owner can add new owners.", ephemeral=True)
        return

    if member.id == MAIN_OWNER_ID:
        await interaction.response.send_message("ℹ️ That user is already the Main Owner.", ephemeral=True)
        return

    success = database.add_owner(member.id, interaction.user.id)
    if not success:
        await interaction.response.send_message(f"❌ {member.mention} is already an Owner.", ephemeral=True)
        return

    # Grant new owner access to all existing reseller channels
    guild = interaction.guild
    resellers = database.get_all_resellers()
    updated_channels_count = 0
    for r in resellers:
        ch = guild.get_channel(r["channel_id"])
        if ch:
            try:
                await ch.set_permissions(
                    member,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True
                )
                updated_channels_count += 1
            except Exception:
                pass

    embed = Embed(
        title="👑 Co-Owner Added Successfully",
        description=f"{member.mention} (`{member.id}`) has been granted full Owner privileges.",
        color=0xF1C40F
    )
    embed.add_field(name="Reseller Channels Updated", value=f"`{updated_channels_count}` channels synced with access.", inline=False)
    embed.set_footer(text=f"Authorized by Main Owner {interaction.user.name}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Webhook Log
    await webhook_logger.log_owner_added(member.id, interaction.user.id)


@owner_group.command(name="remove", description="Remove a co-owner (Main Owner Only)")
@app_commands.describe(member="Select owner to remove")
async def owner_remove(interaction: discord.Interaction, member: discord.Member):
    if not is_main_owner(interaction.user.id):
        await interaction.response.send_message("❌ **Access Denied:** Only the Main Owner can remove owners.", ephemeral=True)
        return

    if member.id == MAIN_OWNER_ID:
        await interaction.response.send_message("❌ You cannot remove the Main Owner.", ephemeral=True)
        return

    removed = database.remove_owner(member.id)
    if not removed:
        await interaction.response.send_message(f"❌ {member.mention} is not in the co-owners list.", ephemeral=True)
        return

    # Revoke channel overrides
    guild = interaction.guild
    resellers = database.get_all_resellers()
    for r in resellers:
        ch = guild.get_channel(r["channel_id"])
        if ch:
            try:
                await ch.set_permissions(member, overwrite=None)
            except Exception:
                pass

    embed = Embed(
        title="⛔ Owner Removed",
        description=f"{member.mention} (`{member.id}`) has been removed from the Owners list.",
        color=0xC0392B
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Webhook Log
    await webhook_logger.log_owner_removed(member.id, interaction.user.id)


@owner_group.command(name="list", description="List Main Owner and all registered co-owners")
async def owner_list(interaction: discord.Interaction):
    if not is_any_owner(interaction.user.id):
        await interaction.response.send_message("❌ **Access Denied:** Owners only.", ephemeral=True)
        return

    owners = database.get_all_owners()
    embed = Embed(
        title="👑 System Owners List",
        color=0xF1C40F
    )
    embed.add_field(
        name="⭐ Main Owner",
        value=f"<@{MAIN_OWNER_ID}> (`{MAIN_OWNER_ID}`)",
        inline=False
    )

    if owners:
        owner_lines = [f"• <@{o['user_id']}> (`{o['user_id']}`) — Added: `{o['created_at']}`" for o in owners]
        embed.add_field(name=f"🛡️ Co-Owners ({len(owners)})", value="\n".join(owner_lines), inline=False)
    else:
        embed.add_field(name="🛡️ Co-Owners", value="*No co-owners added yet. Use `/owner add` to add one.*", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.tree.add_command(owner_group)

# ================= WEBHOOK LOGS COMMAND =================

@bot.tree.command(name="set_logs_webhook", description="Set or update Discord Webhook URL for logs (Owner Only)")
@app_commands.describe(webhook_url="Discord Webhook URL (leave empty to disable)")
async def set_logs_webhook_cmd(interaction: discord.Interaction, webhook_url: str = ""):
    if not is_any_owner(interaction.user.id):
        await interaction.response.send_message("❌ **Access Denied:** Owners only.", ephemeral=True)
        return

    clean_url = webhook_url.strip()
    database.set_setting("webhook_url", clean_url)

    if clean_url:
        embed = Embed(
            title="🔗 Webhook Logs Configured",
            description="Discord webhook logging has been successfully configured and activated!",
            color=0x2ECC71
        )
        embed.add_field(name="Webhook URL", value=f"`{clean_url[:35]}...`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Send test log to confirm webhook works
        test_embed = {
            "title": "✅ Webhook Connection Verified",
            "description": f"Webhook logging was enabled by {interaction.user.mention}.",
            "color": 0x2ECC71,
            "footer": {"text": "Axenor Auth Logging System"}
        }
        await webhook_logger.send_webhook(test_embed)
    else:
        embed = Embed(
            title="📴 Webhook Logs Disabled",
            description="Webhook URL has been cleared.",
            color=0xE74C3C
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ================= KEY COMMAND GROUP =================

key_group = app_commands.Group(name="key", description="Key and Auth management commands")

@key_group.command(name="generate", description="Generate a new auth key with username, password, and days")
@app_commands.describe(username="User login username", password="User login password", days="Subscription duration in days")
async def key_generate(interaction: discord.Interaction, username: str, password: str, days: int):
    # Restriction: Command ONLY works in reseller created channel
    if not database.is_reseller_channel(interaction.channel_id):
        await interaction.response.send_message(
            "❌ **Error:** `/key generate` can ONLY be used inside an authorized reseller channel!",
            ephemeral=True
        )
        return

    # Check authorization within reseller channel: Main Owner, Co-Owner, or assigned Reseller
    reseller_data = database.get_reseller_by_channel(interaction.channel_id)
    user_is_owner = is_any_owner(interaction.user.id)
    user_is_reseller = (reseller_data and reseller_data["user_id"] == interaction.user.id)

    if not user_is_owner and not user_is_reseller and not interaction.permissions.administrator:
        await interaction.response.send_message(
            "❌ You are not authorized to generate keys in this reseller channel.",
            ephemeral=True
        )
        return

    if days <= 0:
        await interaction.response.send_message("❌ Days must be at least 1.", ephemeral=True)
        return

    result = database.create_key(
        username=username,
        password=password,
        days=days,
        created_by=interaction.user.id,
        channel_id=interaction.channel_id
    )

    if not result["success"]:
        await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)
        return

    # Public in channel: "SABKOI DEKH PAYEGA ONLY YOU CAN SEE KEY GENRATE MAI NHI RAHEGA"
    embed = Embed(
        title="🔑 Key Generated Successfully",
        description="User account created! Device HWID will **auto-bind** on first login.",
        color=0x2ECC71
    )
    embed.add_field(name="👤 Username", value=f"`{result['username']}`", inline=True)
    embed.add_field(name="🔒 Password", value=f"`{result['password']}`", inline=True)
    embed.add_field(name="⏳ Duration", value=f"`{result['days']} Days`", inline=True)
    embed.add_field(name="📅 Expires At", value=f"`{result['expires_at']}`", inline=False)
    embed.add_field(name="💻 HWID Status", value="`🟢 Ready to auto-bind on first login`", inline=False)
    embed.set_footer(text=f"Created by {interaction.user.name}", icon_url=interaction.user.display_avatar.url)

    # Public message in the reseller channel!
    await interaction.response.send_message(embed=embed, ephemeral=False)

    # Webhook Log
    await webhook_logger.log_key_generated(
        username=result["username"],
        password=result["password"],
        days=result["days"],
        expires_at=result["expires_at"],
        created_by=interaction.user.id,
        channel_id=interaction.channel_id
    )


@key_group.command(name="delete", description="Delete an auth key / user")
@app_commands.describe(username="Username of the key to delete")
async def key_delete(interaction: discord.Interaction, username: str):
    # Check permissions
    if not database.is_reseller_channel(interaction.channel_id) and not is_any_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Error:** `/key delete` can only be used inside a reseller channel or by an Owner!",
            ephemeral=True
        )
        return

    uname = username.strip()
    deleted = database.delete_key(uname)
    if deleted:
        embed = Embed(
            title="🗑️ Key Deleted",
            description=f"User credentials for **`{uname}`** have been deleted permanently.",
            color=0xE74C3C
        )
        embed.set_footer(text=f"Deleted by {interaction.user.name}")
        await interaction.response.send_message(embed=embed, ephemeral=False)

        # Webhook Log
        await webhook_logger.log_key_deleted(uname, interaction.user.id, interaction.channel_id)
    else:
        await interaction.response.send_message(f"❌ User **`{uname}`** not found.", ephemeral=True)


@key_group.command(name="reset_hwid", description="Reset HWID for a user so they can bind a new machine")
@app_commands.describe(username="Username whose HWID to reset")
async def key_reset_hwid(interaction: discord.Interaction, username: str):
    if not database.is_reseller_channel(interaction.channel_id) and not is_any_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ This command can only be used inside a reseller channel or by an Owner!",
            ephemeral=True
        )
        return

    uname = username.strip()
    result = database.reset_hwid(uname)
    if not result["success"]:
        await interaction.response.send_message(f"❌ {result['message']}", ephemeral=True)
        return

    embed = Embed(
        title="🔄 HWID Reset Successful",
        description=f"HWID for **`{uname}`** has been cleared. The new machine's HWID will auto-bind on next login.",
        color=0x3498DB
    )
    if result.get("old_hwid"):
        embed.add_field(name="Previous HWID", value=f"`{result['old_hwid']}`", inline=False)
    embed.set_footer(text=f"Reset by {interaction.user.name}")
    await interaction.response.send_message(embed=embed, ephemeral=False)

    # Webhook Log
    await webhook_logger.log_hwid_reset(uname, interaction.user.id, result.get("old_hwid"))


@key_group.command(name="info", description="View key details, expiry, and bound HWID")
@app_commands.describe(username="Username to lookup")
async def key_info(interaction: discord.Interaction, username: str):
    if not database.is_reseller_channel(interaction.channel_id) and not is_any_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ This command can only be used inside a reseller channel or by an Owner!",
            ephemeral=True
        )
        return

    uname = username.strip()
    info = database.get_key_info(uname)
    if not info:
        await interaction.response.send_message(f"❌ User **`{uname}`** not found.", ephemeral=True)
        return

    status_text = "🔴 Expired" if info["is_expired"] else "🟢 Active"
    hwid_text = f"`{info['hwid']}`" if info.get("hwid") else "🟡 *Not Bound (Will auto-bind on 1st login)*"
    last_login_text = f"`{info['last_login']} UTC`" if info.get("last_login") else "*Never logged in*"

    embed = Embed(
        title=f"📋 Key Info: {info['username']}",
        color=0x9B59B6
    )
    embed.add_field(name="👤 Username", value=f"`{info['username']}`", inline=True)
    embed.add_field(name="🔒 Password", value=f"`{info['password']}`", inline=True)
    embed.add_field(name="📊 Status", value=status_text, inline=True)
    embed.add_field(name="📅 Expires At", value=f"`{info['expires_at']} UTC`", inline=True)
    embed.add_field(name="⏳ Time Remaining", value=f"{info['remaining_days']}d {info['remaining_hours']}h", inline=True)
    embed.add_field(name="🕒 Last Login", value=last_login_text, inline=True)
    embed.add_field(name="💻 Bound HWID", value=hwid_text, inline=False)
    embed.add_field(name="🛠️ Created By", value=f"<@{info['created_by']}>", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.tree.add_command(key_group)

# ================= RESELLER COMMAND GROUP =================

reseller_group = app_commands.Group(name="reseller", description="Reseller administration commands (Owner Only)")

@reseller_group.command(name="add", description="Add a reseller, create dedicated channel & panel (Owner Only)")
@app_commands.describe(
    member="Discord user to make reseller",
    category="Select category where the channel should be created (Optional)",
    channel_name="Optional custom channel name"
)
async def reseller_add(
    interaction: discord.Interaction,
    member: discord.Member,
    category: discord.CategoryChannel = None,
    channel_name: str = None
):
    # Main Owner or Co-Owners can add resellers
    if not is_any_owner(interaction.user.id):
        await interaction.response.send_message("❌ **Access Denied:** Only Owners can add resellers.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    raw_name = channel_name if channel_name else f"reseller-{member.name.lower()}"
    c_name = format_reseller_channel_name(raw_name)

    # Setup channel permission overwrites
    # 1. Deny everyone
    overwrites = {
        guild.default_role: PermissionOverwrite(view_channel=False),
        # 2. Reseller access
        member: PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True
        ),
        # 3. Bot access
        guild.me: PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            read_message_history=True
        )
    }

    # 4. Main Owner access
    main_owner_member = guild.get_member(MAIN_OWNER_ID)
    if main_owner_member:
        overwrites[main_owner_member] = PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True
        )

    # 5. Access for all registered Co-Owners
    co_owners = database.get_all_owners()
    for o in co_owners:
        co_mem = guild.get_member(o["user_id"])
        if co_mem:
            overwrites[co_mem] = PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )

    # 6. Current interacting user (if owner but not in guild cache above)
    if interaction.user not in overwrites:
        overwrites[interaction.user] = PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )

    try:
        channel = await guild.create_text_channel(
            name=c_name,
            category=category,
            overwrites=overwrites,
            topic=f"Dedicated Key Generation & Auth Channel for {member.display_name} | HWID Auto-Bind System"
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create channel: {e}", ephemeral=True)
        return

    # Add to database
    database.add_reseller(user_id=member.id, channel_id=channel.id, added_by=interaction.user.id)

    # Post interactive Panel with 4 buttons into the reseller channel
    panel_embed = create_panel_embed(reseller_user=member)
    panel_view = ResellerPanelView()
    await channel.send(
        content=f"👋 Welcome {member.mention}! Here is your personal Auth & Key Management Panel.",
        embed=panel_embed,
        view=panel_view
    )

    success_embed = Embed(
        title="✅ Reseller Added Successfully",
        description=f"Created dedicated channel {channel.mention} for reseller {member.mention}.",
        color=0x2ECC71
    )
    success_embed.add_field(name="Reseller", value=f"{member.mention} (`{member.id}`)", inline=True)
    success_embed.add_field(name="Channel", value=f"{channel.mention} (`{channel.id}`)", inline=True)
    if category:
        success_embed.add_field(name="📁 Category", value=f"`{category.name}`", inline=True)
    success_embed.add_field(name="Access Granted", value="Reseller, Main Owner, and Co-Owners have full channel access.", inline=False)
    await interaction.followup.send(embed=success_embed, ephemeral=True)

    # Webhook Log
    await webhook_logger.log_reseller_added(
        member.id,
        channel.id,
        interaction.user.id,
        category_name=category.name if category else None
    )


@reseller_group.command(name="remove", description="Remove a reseller and delete their reseller channel (Owner Only)")
@app_commands.describe(channel="Select the reseller channel to remove", member="Or select the reseller member")
async def reseller_remove(interaction: discord.Interaction, channel: discord.TextChannel = None, member: discord.Member = None):
    if not is_any_owner(interaction.user.id):
        await interaction.response.send_message("❌ **Access Denied:** Only Owners can remove resellers.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if not channel and not member:
        await interaction.followup.send("❌ Please provide either a `channel` or a `member` to remove.", ephemeral=True)
        return

    deleted_channels = []
    if channel:
        if not database.is_reseller_channel(channel.id):
            await interaction.followup.send(f"❌ {channel.mention} is not registered as a reseller channel in the database.", ephemeral=True)
            return
        database.remove_reseller_by_channel(channel.id)
        ch_name = channel.name
        try:
            await channel.delete(reason=f"Reseller channel removed by {interaction.user.name}")
            deleted_channels.append(ch_name)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Reseller removed from DB but failed to delete channel: {e}", ephemeral=True)
            return
    elif member:
        ch_ids = database.remove_reseller_by_user(member.id)
        for cid in ch_ids:
            ch = interaction.guild.get_channel(cid)
            if ch:
                try:
                    cname = ch.name
                    await ch.delete(reason=f"Reseller {member.name} removed by owner")
                    deleted_channels.append(cname)
                except Exception:
                    pass

    embed = Embed(
        title="🗑️ Reseller Removed",
        description=f"Reseller deleted. Channel(s) (`{', '.join(deleted_channels) or 'None'}`) were permanently removed.",
        color=0xE74C3C
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

    # Webhook Log
    await webhook_logger.log_reseller_removed(', '.join(deleted_channels) or "Unknown", interaction.user.id)


@reseller_group.command(name="total", description="Show total registered resellers and their channels")
async def reseller_total(interaction: discord.Interaction):
    if not is_any_owner(interaction.user.id):
        await interaction.response.send_message("❌ **Access Denied:** Owners only.", ephemeral=True)
        return

    resellers = database.get_all_resellers()
    total_count = len(resellers)

    embed = Embed(
        title="📊 Total Resellers Overview",
        description=f"**Total Resellers:** `{total_count}`\n",
        color=0x3498DB
    )

    if total_count == 0:
        embed.description += "\n*No resellers have been added yet. Use `/reseller add` to create one!*"
    else:
        for idx, r in enumerate(resellers, 1):
            embed.add_field(
                name=f"#{idx} Reseller",
                value=f"• User: <@{r['user_id']}> (`{r['user_id']}`)\n• Channel: <#{r['channel_id']}>\n• Added: `{r['created_at']}`",
                inline=False
            )

    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.tree.add_command(reseller_group)

# ================= TOP-LEVEL ALIAS SLASH COMMANDS =================
# Matches exact requested names like /total resellers, /resellers add, etc.

@bot.tree.command(name="reseller_add", description="Add a reseller, create dedicated channel & panel (Owner Only)")
@app_commands.describe(
    member="Discord user to make reseller",
    category="Select category where the channel should be created (Optional)",
    channel_name="Optional custom channel name"
)
async def reseller_add_alias(
    interaction: discord.Interaction,
    member: discord.Member,
    category: discord.CategoryChannel = None,
    channel_name: str = None
):
    await reseller_add.callback(interaction, member, category, channel_name)

@bot.tree.command(name="total_resellers", description="View all resellers and assigned channels (Owner Only)")
async def total_resellers_cmd(interaction: discord.Interaction):
    await reseller_total.callback(interaction)

@bot.tree.command(name="key_generate", description="Generate user & pass key (Only works in Reseller Channel)")
@app_commands.describe(username="User login username", password="User login password", days="Duration in days")
async def key_gen_alias(interaction: discord.Interaction, username: str, password: str, days: int):
    await key_generate.callback(interaction, username, password, days)

@bot.tree.command(name="key_delete", description="Delete an auth key (Reseller channel or Owner)")
@app_commands.describe(username="Username to delete")
async def key_del_alias(interaction: discord.Interaction, username: str):
    await key_delete.callback(interaction, username)

# ================= RUN SCRIPT =================

if __name__ == "__main__":
    if DISCORD_TOKEN == "YOUR_BOT_TOKEN_HERE" or not DISCORD_TOKEN:
        print("[!] ERROR: Please set your DISCORD_TOKEN in .env or config.py before running.")
    else:
        bot.run(DISCORD_TOKEN)
