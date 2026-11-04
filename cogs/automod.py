import re
import time
import json
import os
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands


# =========================================================
# FILES
# =========================================================

WHITELIST_FILE = "gali_whitelist.json"
LINK_WHITELIST_FILE = "link_whitelist.json"


# =========================================================
# AUTOMOD
# =========================================================

class AutoMod(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # -------------------------------------------------
        # MEMORY
        # -------------------------------------------------

        self.message_history = defaultdict(
            lambda: deque(maxlen=20)
        )

        self.last_messages = {}

        self.duplicate_counts = defaultdict(int)

        # -------------------------------------------------
        # SETTINGS
        # -------------------------------------------------

        self.settings = defaultdict(
            lambda: {
                "links": True,
                "spam": True,
                "duplicates": True,
                "badwords": True,
            }
        )

        # -------------------------------------------------
        # GALI WHITELIST & LINK WHITELIST
        #
        # {
        #     "guild_id": [user_id, user_id]
        # }
        # -------------------------------------------------

        self.gali_whitelist = {}
        self.link_whitelist = {}

        self.load_gali_whitelist()
        self.load_link_whitelist()

        # -------------------------------------------------
        # LINK REGEX
        # -------------------------------------------------

        self.link_pattern = re.compile(
            r"(https?://\S+|"
            r"www\.\S+|"
            r"discord\.gg/\S+|"
            r"discord\.com/invite/\S+|"
            r"discordapp\.com/invite/\S+)",
            re.IGNORECASE
        )

        # -------------------------------------------------
        # BAD WORDS
        # -------------------------------------------------

        self.bad_words = {
            "mc",
            "bc",
            "bkl",
            "bsdk",
            "randi",
            "maderchod",
            "madarchod",
            "chakka",
            "bhenchod",
            "bhosdika",
            "bhosdike",
            "chutiye",
            "chutiya",
            "gand",
            "gand mara",
            "muh me lele",
            "teri maa chod dunga",
            "tun chakka hai",
            "lodu",
            "bhen ka loda",
            "maa ka bhosda",
            "chut",
            "bhund",
            "fudda",
            "sex",
            "radn",
            "randdd",
            "pussy",
        }

        # -------------------------------------------------
        # LIMITS
        # -------------------------------------------------

        self.max_messages = 5
        self.time_window = 5

        self.max_duplicates = 3

        self.automod_timeout_minutes = 10

        print("🛡️ AutoMod initialized", flush=True)

    # =====================================================
    # WHITELIST LOAD (GALI)
    # =====================================================

    def load_gali_whitelist(self):

        try:

            if not os.path.exists(WHITELIST_FILE):
                self.gali_whitelist = {}
                return

            with open(
                WHITELIST_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            self.gali_whitelist = {}

            if not isinstance(data, dict):
                self.gali_whitelist = {}
                return

            for guild_id, users in data.items():

                try:

                    if not isinstance(users, list):
                        users = []

                    self.gali_whitelist[str(guild_id)] = [
                        int(user_id)
                        for user_id in users
                    ]

                except (ValueError, TypeError):

                    self.gali_whitelist[str(guild_id)] = []

            print(
                "[AUTOMOD] Loaded gali whitelist: "
                f"{len(self.gali_whitelist)} server(s)",
                flush=True
            )

        except Exception as e:

            print(
                f"[AUTOMOD] Whitelist load error: {e}",
                flush=True
            )

            self.gali_whitelist = {}

    # =====================================================
    # WHITELIST LOAD (LINK)
    # =====================================================

    def load_link_whitelist(self):

        try:

            if not os.path.exists(LINK_WHITELIST_FILE):
                self.link_whitelist = {}
                return

            with open(
                LINK_WHITELIST_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            self.link_whitelist = {}

            if not isinstance(data, dict):
                self.link_whitelist = {}
                return

            for guild_id, users in data.items():

                try:

                    if not isinstance(users, list):
                        users = []

                    self.link_whitelist[str(guild_id)] = [
                        int(user_id)
                        for user_id in users
                    ]

                except (ValueError, TypeError):

                    self.link_whitelist[str(guild_id)] = []

            print(
                "[AUTOMOD] Loaded link whitelist: "
                f"{len(self.link_whitelist)} server(s)",
                flush=True
            )

        except Exception as e:

            print(
                f"[AUTOMOD] Link Whitelist load error: {e}",
                flush=True
            )

            self.link_whitelist = {}

    # =====================================================
    # WHITELIST SAVE (GALI)
    # =====================================================

    def save_gali_whitelist(self):

        try:

            with open(
                WHITELIST_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.gali_whitelist,
                    f,
                    indent=4
                )

        except Exception as e:

            print(
                f"[AUTOMOD] Whitelist save error: {e}",
                flush=True
            )

    # =====================================================
    # WHITELIST SAVE (LINK)
    # =====================================================

    def save_link_whitelist(self):

        try:

            with open(
                LINK_WHITELIST_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.link_whitelist,
                    f,
                    indent=4
                )

        except Exception as e:

            print(
                f"[AUTOMOD] Link Whitelist save error: {e}",
                flush=True
            )

    # =====================================================
    # CHECK GALI WHITELIST
    # =====================================================

    def is_gali_whitelisted(
        self,
        guild_id: int,
        user_id: int
    ):

        guild_users = self.gali_whitelist.get(
            str(guild_id),
            []
        )

        return int(user_id) in guild_users

    # =====================================================
    # CHECK LINK WHITELIST
    # =====================================================

    def is_link_whitelisted(
        self,
        guild_id: int,
        user_id: int
    ):

        guild_users = self.link_whitelist.get(
            str(guild_id),
            []
        )

        return int(user_id) in guild_users

    # =====================================================
    # ADD GALI WHITELIST
    # =====================================================

    def add_gali_whitelist(
        self,
        guild_id: int,
        user_id: int
    ):

        guild_id = str(guild_id)
        user_id = int(user_id)

        if guild_id not in self.gali_whitelist:
            self.gali_whitelist[guild_id] = []

        if user_id in self.gali_whitelist[guild_id]:
            return False

        self.gali_whitelist[guild_id].append(user_id)

        self.save_gali_whitelist()

        return True

    # =====================================================
    # ADD LINK WHITELIST
    # =====================================================

    def add_link_whitelist(
        self,
        guild_id: int,
        user_id: int
    ):

        guild_id = str(guild_id)
        user_id = int(user_id)

        if guild_id not in self.link_whitelist:
            self.link_whitelist[guild_id] = []

        if user_id in self.link_whitelist[guild_id]:
            return False

        self.link_whitelist[guild_id].append(user_id)

        self.save_link_whitelist()

        return True

    # =====================================================
    # REMOVE GALI WHITELIST
    # =====================================================

    def remove_gali_whitelist(
        self,
        guild_id: int,
        user_id: int
    ):

        guild_id = str(guild_id)
        user_id = int(user_id)

        if guild_id not in self.gali_whitelist:
            return False

        if user_id not in self.gali_whitelist[guild_id]:
            return False

        self.gali_whitelist[guild_id].remove(user_id)

        if not self.gali_whitelist[guild_id]:
            del self.gali_whitelist[guild_id]

        self.save_gali_whitelist()

        return True

    # =====================================================
    # REMOVE LINK WHITELIST
    # =====================================================

    def remove_link_whitelist(
        self,
        guild_id: int,
        user_id: int
    ):

        guild_id = str(guild_id)
        user_id = int(user_id)

        if guild_id not in self.link_whitelist:
            return False

        if user_id not in self.link_whitelist[guild_id]:
            return False

        self.link_whitelist[guild_id].remove(user_id)

        if not self.link_whitelist[guild_id]:
            del self.link_whitelist[guild_id]

        self.save_link_whitelist()

        return True

    # =====================================================
    # SERVER OWNER
    # =====================================================

    def is_server_owner(
        self,
        message: discord.Message
    ):

        return (
            message.guild is not None
            and message.guild.owner_id == message.author.id
        )

    # =====================================================
    # TIMEOUT
    # =====================================================

    async def timeout_member(
        self,
        member: discord.Member,
        reason: str
    ):

        try:

            # Never timeout server owner
            if member.guild.owner_id == member.id:
                return False

            await member.timeout(
                timedelta(
                    minutes=self.automod_timeout_minutes
                ),
                reason=reason
            )

            return True

        except discord.Forbidden:

            print(
                "[AUTOMOD] Cannot timeout "
                f"{member} - permissions/role hierarchy.",
                flush=True
            )

            return False

        except discord.HTTPException as e:

            print(
                f"[AUTOMOD] Discord timeout error: {e}",
                flush=True
            )

            return False

        except Exception as e:

            print(
                f"[AUTOMOD] Timeout error: {e}",
                flush=True
            )

            return False

    # =====================================================
    # EMBED
    # =====================================================

    def security_embed(
        self,
        title,
        description,
        color
    ):

        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )

        embed.set_footer(
            text="HSL SECURITY • AutoMod Protection"
        )

        return embed

    # =====================================================
    # SEND SECURITY ALERT
    # =====================================================

    async def send_security_alert(
        self,
        channel,
        embed
    ):

        try:

            await channel.send(
                embed=embed,
                delete_after=7
            )

        except (
            discord.Forbidden,
            discord.HTTPException
        ):

            pass

        except Exception as e:

            print(
                f"[AUTOMOD] Alert error: {e}",
                flush=True
            )

    # =====================================================
    # READY
    # =====================================================

   
    @commands.Cog.listener()
    async def on_ready(self):

        for guild in self.bot.guilds:

            try:
                row = (
                    self.bot.db.get_guild(guild.id)
                    if hasattr(self.bot, "db")
                    else None
                )

                if row is not None:
                    # sqlite3.Row ko dictionary mein convert karo
                    row_data = dict(row)

                    self.settings[guild.id]["links"] = bool(
                        row_data.get("automod_links", 1)
                    )

                    self.settings[guild.id]["spam"] = bool(
                        row_data.get("automod_spam", 1)
                    )

                    self.settings[guild.id]["duplicates"] = bool(
                        row_data.get("automod_duplicates", 1)
                    )

                    self.settings[guild.id]["badwords"] = bool(
                        row_data.get("automod_badwords", 1)
                    )

            except Exception as e:
                print(
                    f"[AUTOMOD] Database load error for {guild.name}: {e}",
                    flush=True
                )

        print(
            "💾 AutoMod settings loaded",
            flush=True
        )

        print(
            "🛡️ Gali & Link whitelist systems loaded",
            flush=True
        )


    # =====================================================
    # MESSAGE LISTENER
    # =====================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):

        # -------------------------------------------------
        # IGNORE BOTS
        # -------------------------------------------------

        if message.author.bot:
            return

        # -------------------------------------------------
        # IGNORE DMS
        # -------------------------------------------------

        if message.guild is None:
            return

        # -------------------------------------------------
        # SERVER OWNER BYPASS
        # -------------------------------------------------

        if self.is_server_owner(message):
            return

        guild_id = message.guild.id
        user_id = message.author.id

        settings = self.settings[guild_id]

        # =================================================
        # ANTI LINK
        # =================================================

        if settings["links"]:

            link_whitelisted = self.is_link_whitelisted(
                guild_id,
                user_id
            )

            if not link_whitelisted:

                if self.link_pattern.search(
                    message.content
                ):

                    try:

                        await message.delete()

                    except (
                        discord.Forbidden,
                        discord.NotFound,
                        discord.HTTPException
                    ):

                        pass

                    timed_out = await self.timeout_member(
                        message.author,
                        "HSL AutoMod: Unauthorized link"
                    )

                    if timed_out:

                        embed = self.security_embed(
                            "🔗 LINK BLOCKED",
                            (
                                "### 🛡️ Security Action\n\n"
                                f"👤 **Member:** {message.author.mention}\n"
                                "🔗 **Violation:** Unauthorized link\n"
                                "🟢 **Action:** 10 Minute Timeout\n"
                                "🗑️ **Message:** Deleted"
                            ),
                            discord.Color.red()
                        )

                        try:

                            embed.set_thumbnail(
                                url=message.author.display_avatar.url
                            )

                        except Exception:
                            pass

                        await self.send_security_alert(
                            message.channel,
                            embed
                        )

                    return

        # =================================================
        # ANTI BADWORD
        #
        # GALI WHITELIST ONLY BYPASSES BADWORDS.
        #
        # LINKS / SPAM / DUPLICATES STILL WORK.
        # =================================================

        if settings["badwords"]:

            whitelisted = self.is_gali_whitelisted(
                guild_id,
                user_id
            )

            if not whitelisted:

                content = message.content.lower()

                found_word = None

                for word in self.bad_words:

                    pattern = (
                        r"(?<!\w)"
                        + re.escape(
                            word.lower()
                        )
                        + r"(?!\w)"
                    )

                    if re.search(
                        pattern,
                        content,
                        re.IGNORECASE
                    ):

                        found_word = word
                        break

                # -----------------------------------------
                # BADWORD FOUND
                # -----------------------------------------

                if found_word is not None:

                    try:

                        await message.delete()

                    except (
                        discord.Forbidden,
                        discord.NotFound,
                        discord.HTTPException
                    ):

                        pass

                    timed_out = await self.timeout_member(
                        message.author,
                        "HSL AutoMod: Inappropriate language"
                    )

                    if timed_out:

                        embed = self.security_embed(
                            "🚨 LANGUAGE VIOLATION",
                            (
                                "### 🛡️ Security Action\n\n"
                                f"👤 **Member:** {message.author.mention}\n"
                                "⚠️ **Violation:** Inappropriate language\n"
                                "🟢 **Action:** 10 Minute Timeout\n"
                                "🗑️ **Message:** Deleted"
                            ),
                            discord.Color.red()
                        )

                        try:

                            embed.set_thumbnail(
                                url=message.author.display_avatar.url
                            )

                        except Exception:
                            pass

                        await self.send_security_alert(
                            message.channel,
                            embed
                        )

                    else:

                        try:

                            await message.channel.send(
                                (
                                    "⚠️ **AutoMod Alert:** "
                                    f"{message.author.mention} ne bad word use kiya, "
                                    "lekin bot ke paas **Timeout** dene ki "
                                    "permission / role priority nahi hai!"
                                ),
                                delete_after=7
                            )

                        except Exception:
                            pass

                    return

        # =================================================
        # ANTI SPAM
        # =================================================

        if settings["spam"]:

            now = time.monotonic()

            history_key = (
                guild_id,
                user_id
            )

            history = self.message_history[
                history_key
            ]

            history.append(now)

            while (
                history
                and now - history[0] > self.time_window
            ):

                history.popleft()

            if len(history) >= self.max_messages:

                try:

                    await message.delete()

                except (
                    discord.Forbidden,
                    discord.NotFound,
                    discord.HTTPException
                ):

                    pass

                timed_out = await self.timeout_member(
                    message.author,
                    "HSL AutoMod: Spamming"
                )

                if timed_out:

                    embed = self.security_embed(
                        "🚨 SPAM DETECTED",
                        (
                            "### 🛡️ Security Action\n\n"
                            f"👤 **Member:** {message.author.mention}\n"
                            "📊 **Violation:** Message spam\n"
                            "🟢 **Action:** 10 Minute Timeout\n"
                            "🗑️ **Message:** Deleted"
                        ),
                        discord.Color.red()
                    )

                    try:

                        embed.set_thumbnail(
                            url=message.author.display_avatar.url
                        )

                    except Exception:
                        pass

                    await self.send_security_alert(
                        message.channel,
                        embed
                    )

                history.clear()

                return

        # =================================================
        # ANTI DUPLICATE
        # =================================================

        if settings["duplicates"]:

            content = (
                message.content
                .strip()
                .lower()
            )

            duplicate_key = (
                guild_id,
                user_id
            )

            if (
                content
                and self.last_messages.get(
                    duplicate_key
                ) == content
            ):

                self.duplicate_counts[
                    duplicate_key
                ] += 1

                if (
                    self.duplicate_counts[
                        duplicate_key
                    ] >= self.max_duplicates
                ):

                    try:

                        await message.delete()

                    except (
                        discord.Forbidden,
                        discord.NotFound,
                        discord.HTTPException
                    ):

                        pass

                    timed_out = await self.timeout_member(
                        message.author,
                        "HSL AutoMod: Repeated messages"
                    )

                    if timed_out:

                        embed = self.security_embed(
                            "🔁 REPEATED MESSAGE",
                            (
                                "### 🛡️ Security Action\n\n"
                                f"👤 **Member:** {message.author.mention}\n"
                                "⚠️ **Violation:** Repeated message\n"
                                "🟢 **Action:** 10 Minute Timeout\n"
                                "🗑️ **Message:** Deleted"
                            ),
                            discord.Color.red()
                        )

                        try:

                            embed.set_thumbnail(
                                url=message.author.display_avatar.url
                            )

                        except Exception:
                            pass

                        await self.send_security_alert(
                            message.channel,
                            embed
                        )

                    self.duplicate_counts[
                        duplicate_key
                    ] = 0

                    return

            else:

                self.duplicate_counts[
                    duplicate_key
                ] = 0

            self.last_messages[
                duplicate_key
            ] = content

    # =====================================================
    # /WHITELISTGALI
    # =====================================================

    @app_commands.command(
        name="whitelistgali",
        description=(
            "Allow a member to use bad words "
            "without Anti-Gali punishment"
        )
    )
    @app_commands.describe(
        member=(
            "Member who should be allowed "
            "to use bad words"
        )
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def whitelistgali(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Ye command server ke andar use karo.",
                ephemeral=True
            )

            return

        added = self.add_gali_whitelist(
            interaction.guild.id,
            member.id
        )

        if added:

            await interaction.response.send_message(
                (
                    f"✅ {member.mention} ko "
                    "**Gali Whitelist** kar diya.\n\n"
                    "🤬 Ab Anti-Gali uski gali delete nahi karega.\n"
                    "🔗 Anti-Link active rahega.\n"
                    "🚨 Anti-Spam active rahega.\n"
                    "🔁 Anti-Duplicate active rahega."
                ),
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                (
                    f"ℹ️ {member.mention} already "
                    "**Gali Whitelist** me hai."
                ),
                ephemeral=True
            )

    # =====================================================
    # /UNWHITELISTGALI
    # =====================================================

    @app_commands.command(
        name="unwhitelistgali",
        description=(
            "Remove a member from the "
            "badword whitelist"
        )
    )
    @app_commands.describe(
        member="Member to remove from Gali Whitelist"
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def unwhitelistgali(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Ye command server ke andar use karo.",
                ephemeral=True
            )

            return

        removed = self.remove_gali_whitelist(
            interaction.guild.id,
            member.id
        )

        if removed:

            await interaction.response.send_message(
                (
                    f"🔴 {member.mention} ko "
                    "**Gali Whitelist** se remove kar diya.\n\n"
                    "🤬 Ab Anti-Gali normally apply hoga."
                ),
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                (
                    f"ℹ️ {member.mention} "
                    "Gali Whitelist me tha hi nahi."
                ),
                ephemeral=True
            )

    # =====================================================
    # /GALIWHITELIST
    # =====================================================

    @app_commands.command(
        name="galiwhitelist",
        description=(
            "Show members who are allowed "
            "to use bad words"
        )
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def galiwhitelist(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Ye command server ke andar use karo.",
                ephemeral=True
            )

            return

        users = self.gali_whitelist.get(
            str(interaction.guild.id),
            []
        )

        if not users:

            await interaction.response.send_message(
                "📋 **Gali Whitelist empty hai.**",
                ephemeral=True
            )

            return

        mentions = []

        for user_id in users:

            member = interaction.guild.get_member(
                user_id
            )

            if member:

                mentions.append(
                    f"• {member.mention} (`{member.id}`)"
                )

            else:

                mentions.append(
                    f"• <@{user_id}> (`{user_id}`)"
                )

        embed = discord.Embed(
            title="🤬 GALI WHITELIST",
            description="\n".join(mentions),
            color=discord.Color.green()
        )

        embed.set_footer(
            text="HSL SECURITY • AutoMod"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # /WHITELISTLINK
    # =====================================================

   # =====================================================
    # /WHITELISTLINK
    # =====================================================

    @app_commands.command(
        name="whitelistlink",
        description=(
            "Allow a member to post links "
            "without Anti-Link punishment"
        )
    )
    @app_commands.describe(
        member=(
            "Member who should be allowed "
            "to post links"
        )
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def whitelistlink(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        # Discord Timeout issue fix
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            return await interaction.followup.send(
                "❌ Ye command server ke andar use karo."
            )

        added = self.add_link_whitelist(
            interaction.guild.id,
            member.id
        )

        if added:
            await interaction.followup.send(
                f"✅ {member.mention} ko **Link Whitelist** kar diya.\n\n"
                "🔗 Ab Anti-Link uske links delete nahi karega.\n"
                "🤬 Anti-Badword active rahega.\n"
                "🚨 Anti-Spam active rahega.\n"
                "🔁 Anti-Duplicate active rahega."
            )
        else:
            await interaction.followup.send(
                f"ℹ️ {member.mention} already **Link Whitelist** me hai."
            )

    # =====================================================
    # /UNWHITELISTLINK
    # =====================================================

    @app_commands.command(
        name="unwhitelistlink",
        description=(
            "Remove a member from the "
            "link whitelist"
        )
    )
    @app_commands.describe(
        member="Member to remove from Link Whitelist"
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def unwhitelistlink(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Ye command server ke andar use karo.",
                ephemeral=True
            )

            return

        removed = self.remove_link_whitelist(
            interaction.guild.id,
            member.id
        )

        if removed:

            await interaction.response.send_message(
                (
                    f"🔴 {member.mention} ko "
                    "**Link Whitelist** se remove kar diya.\n\n"
                    "🔗 Ab Anti-Link normally apply hoga."
                ),
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                (
                    f"ℹ️ {member.mention} "
                    "Link Whitelist me tha hi nahi."
                ),
                ephemeral=True
            )

    # =====================================================
    # /LINKWHITELIST
    # =====================================================

    @app_commands.command(
        name="linkwhitelist",
        description=(
            "Show members who are allowed "
            "to post links"
        )
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def linkwhitelist(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Ye command server ke andar use karo.",
                ephemeral=True
            )

            return

        users = self.link_whitelist.get(
            str(interaction.guild.id),
            []
        )

        if not users:

            await interaction.response.send_message(
                "📋 **Link Whitelist empty hai.**",
                ephemeral=True
            )

            return

        mentions = []

        for user_id in users:

            member = interaction.guild.get_member(
                user_id
            )

            if member:

                mentions.append(
                    f"• {member.mention} (`{member.id}`)"
                )

            else:

                mentions.append(
                    f"• <@{user_id}> (`{user_id}`)"
                )

        embed = discord.Embed(
            title="🔗 LINK WHITELIST",
            description="\n".join(mentions),
            color=discord.Color.green()
        )

        embed.set_footer(
            text="HSL SECURITY • AutoMod"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # /AUTOMOD_STATUS
    # =====================================================

    @app_commands.command(
        name="automod_status",
        description="Show AutoMod security status"
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def automod_status(
        self,
        interaction: discord.Interaction
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Ye command server ke andar use karo.",
                ephemeral=True
            )

            return

        settings = self.settings[
            interaction.guild.id
        ]

        def status(value):

            if value:
                return "🟢 **ONLINE**"

            return "🔴 **OFFLINE**"

        gali_whitelist_count = len(
            self.gali_whitelist.get(
                str(interaction.guild.id),
                []
            )
        )

        link_whitelist_count = len(
            self.link_whitelist.get(
                str(interaction.guild.id),
                []
            )
        )

        embed = discord.Embed(
            title="🛡️ HSL SECURITY",
            description=(
                "### SECURITY STATUS\n\n"
                "━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="🔗 Anti-Link",
            value=status(
                settings["links"]
            ),
            inline=True
        )

        embed.add_field(
            name="🚨 Anti-Spam",
            value=status(
                settings["spam"]
            ),
            inline=True
        )

        embed.add_field(
            name="🔁 Anti-Duplicate",
            value=status(
                settings["duplicates"]
            ),
            inline=True
        )

        embed.add_field(
            name="🤬 Anti-Badword",
            value=status(
                settings["badwords"]
            ),
            inline=True
        )

        embed.add_field(
            name="🔇 Auto Timeout",
            value="🟢 **10 MINUTES**",
            inline=True
        )

        embed.add_field(
            name="🤬 Gali Whitelist",
            value=(
                f"🟢 **{gali_whitelist_count} MEMBER(S)**"
            ),
            inline=True
        )

        embed.add_field(
            name="🔗 Link Whitelist",
            value=(
                f"🟢 **{link_whitelist_count} MEMBER(S)**"
            ),
            inline=True
        )

        embed.set_footer(
            text="HSL SECURITY • Protection System"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        AutoMod(bot)
    )

    print(
        "✅ automod.py successfully loaded",
        flush=True
    )