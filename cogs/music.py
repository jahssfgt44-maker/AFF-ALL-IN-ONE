import asyncio
import os
import shutil
import ctypes
import ctypes.util
import time
import re
from collections import deque

import aiohttp
import discord
from discord.ext import commands
import yt_dlp


# =========================================================
# HSL-CORP ULTRA FAST MUSIC SYSTEM
# =========================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_PATH = os.path.join(BASE_DIR, "cookies.txt")

COOKIE_FILE = None


# =========================================================
# COOKIES
# =========================================================

env_cookies = os.getenv("YOUTUBE_COOKIES")

if os.path.isfile(COOKIE_PATH):
    COOKIE_FILE = COOKIE_PATH
    print(f"[MUSIC] [COOKIE] Local cookies: {COOKIE_FILE}")

elif env_cookies:
    try:
        COOKIE_FILE = "/tmp/youtube_cookies.txt"

        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(env_cookies)

        print("[MUSIC] [COOKIE] Railway ENV cookies loaded.")

    except Exception as e:
        print("[MUSIC] [COOKIE] Failed:", repr(e))

else:
    print("[MUSIC] [WARN] No YouTube cookies found.")


# =========================================================
# OPUS
# =========================================================

def load_opus():

    if discord.opus.is_loaded():
        print("[MUSIC] [OK] Opus already loaded.")
        return True

    paths = [
        ctypes.util.find_library("opus"),
        "libopus.so.0",
        "libopus.so",
        "/usr/lib/x86_64-linux-gnu/libopus.so.0",
        "/usr/lib/aarch64-linux-gnu/libopus.so.0",
        "/usr/local/lib/libopus.so.0",
    ]

    for path in paths:

        if not path:
            continue

        try:
            ctypes.CDLL(path)
            discord.opus.load_opus(path)

            if discord.opus.is_loaded():
                print(f"[MUSIC] [OK] Opus loaded: {path}")
                return True

        except Exception as e:
            print(f"[MUSIC] [WARN] Opus failed {path}: {e}")

    print("[MUSIC] [ERROR] Opus NOT loaded.")
    return False


OPUS_LOADED = load_opus()


# =========================================================
# FFMPEG
# =========================================================

def find_ffmpeg():

    path = shutil.which("ffmpeg")

    if path:
        print(f"[MUSIC] [OK] FFmpeg: {path}")
        return path

    paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]

    for path in paths:

        if os.path.isfile(path):
            print(f"[MUSIC] [OK] FFmpeg: {path}")
            return path

    print("[MUSIC] [WARN] FFmpeg not found.")
    return "ffmpeg"


FFMPEG_PATH = find_ffmpeg()


# =========================================================
# CONSTANTS
# =========================================================

HSL_GIF = (
    "https://media3.giphy.com/media/"
    "v1.Y2lkPTc5MGI3NjExZ3RqemR3c3A0MHl3NWw1NHE4a2FjdWVkdDdqdXppaXdxdHhobGF5ayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/"
    "iBILBPeCHDVuELjOND/giphy.gif"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)


# =========================================================
# YTDLP BASE OPTIONS
# =========================================================

BASE_YTDLP = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "force_ipv4": True,
    "source_address": "0.0.0.0",
    "socket_timeout": 6,
    "retries": 1,
    "fragment_retries": 1,
    "nocheckcertificate": True,
    "geo_bypass": True,
    "http_headers": {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "*/*",
    },
}


def yt_options():
    options = dict(BASE_YTDLP)
    options["http_headers"] = dict(BASE_YTDLP["http_headers"])
    if COOKIE_FILE and os.path.isfile(COOKIE_FILE):
        options["cookiefile"] = COOKIE_FILE
    return options


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_title(text):
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"https?://\S+", " ", text)
    remove_words = [
        "official", "video", "audio", "lyrics", "lyric", "music", "song",
        "full", "hd", "4k", "8k", "remix", "mix", "slowed", "reverb",
        "sped", "speed up", "nightcore", "lofi", "lo-fi", "cover", "live",
        "version", "visualizer", "visualiser", "edit", "extended",
        "bass boosted", "bassboosted", "shorts", "short",
    ]
    for word in remove_words:
        text = re.sub(r"\b" + re.escape(word) + r"\b", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def title_tokens(text):
    normalized = normalize_title(text)
    if not normalized:
        return set()
    stop_words = {
        "the", "a", "an", "of", "and", "to", "in", "on", "for",
        "is", "with", "from", "by", "at", "this", "that",
    }
    return {x for x in normalized.split() if len(x) >= 2 and x not in stop_words}


def is_same_song(candidate_title, old_title):
    if not candidate_title or not old_title:
        return False
    a = normalize_title(candidate_title)
    b = normalize_title(old_title)
    if not a or not b:
        return False
    if a == b or (len(a) >= 5 and a in b) or (len(b) >= 5 and b in a):
        return True
    a_tokens = title_tokens(a)
    b_tokens = title_tokens(b)
    if not a_tokens or not b_tokens:
        return False
    overlap = len(a_tokens & b_tokens) / max(1, min(len(a_tokens), len(b_tokens)))
    return overlap >= 0.75


# =========================================================
# SONG
# =========================================================

class Song:
    def __init__(self, title, url, thumbnail, requester):
        self.title = title
        self.url = url
        self.thumbnail = thumbnail
        self.requester = requester


# =========================================================
# PLAYER
# =========================================================

class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.voice = None
        self.text_channel = None
        self.queue = deque()
        self.current = None
        self.volume = 1.0
        self.loop = False
        self.autoplay = True
        self.starting = False
        self.play_token = 0
        self.play_lock = asyncio.Lock()
        self.skip_lock = asyncio.Lock()
        self.now_playing_message = None
        self.last_play_request = None
        self.last_play_request_time = 0
        self.autoplay_history = deque(maxlen=100)
        self.play_history = deque(maxlen=100)
        self.last_manual_query = None
        self.song_start_time = 0
        self.total_paused = 0

    def invalidate(self):
        self.play_token += 1
        print(f"[MUSIC] [TOKEN] -> {self.play_token}")
        return self.play_token

    async def voice_status(self, text):
        if not self.voice or not self.voice.channel:
            return
        try:
            channel_id = self.voice.channel.id
            url = f"https://discord.com/api/v10/channels/{channel_id}/voice-status"
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json",
            }
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.put(url, headers=headers, json={"status": str(text)[:500]}) as response:
                    pass
        except Exception as e:
            pass

    async def clear_voice_status(self):
        await self.voice_status("")

    async def resolve_song(self, query, requester):
        loop = asyncio.get_running_loop()

        def extract():
            query_text = str(query).strip()
            if not query_text:
                return None
            try:
                if query_text.startswith(("http://", "https://")):
                    options = yt_options()
                    options.update({"skip_download": True, "noplaylist": True, "extract_flat": True})
                    with yt_dlp.YoutubeDL(options) as ydl:
                        info = ydl.extract_info(query_text, download=False)
                    if not info:
                        return None
                    if "entries" in info:
                        entries = [x for x in (info.get("entries") or []) if x]
                        if not entries:
                            return None
                        info = entries[0]
                    video_id = info.get("id")
                    url = info.get("webpage_url") or info.get("original_url")
                    if not url and video_id:
                        url = f"https://www.youtube.com/watch?v={video_id}"
                    if not url:
                        return None
                    thumbnail = info.get("thumbnail") or (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None)
                    return Song(info.get("title", "Unknown Song"), url, thumbnail, requester)

                options = yt_options()
                options["extract_flat"] = True
                options["skip_download"] = True
                options["noplaylist"] = True
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(f"ytsearch1:{query_text}", download=False)
                if not info:
                    return None
                entries = info.get("entries") or []
                if not entries:
                    return None
                entry = entries[0]
                if not entry:
                    return None
                title = entry.get("title") or ""
                video_id = entry.get("id")
                if not title or not video_id:
                    return None
                url = entry.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
                thumbnail = entry.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                return Song(title, url, thumbnail, requester)
            except Exception as e:
                print("[MUSIC] [SEARCH ERROR]", repr(e))
                return None

        return await loop.run_in_executor(None, extract)

    async def get_audio_stream(self, song):
        loop = asyncio.get_running_loop()

        def extract():
            options = yt_options()
            options.update({
                "skip_download": True,
                "noplaylist": True,
                "extract_flat": False,
                "format": "bestaudio/best",
            })
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    info = ydl.extract_info(song.url, download=False)
                if not info:
                    return None
                if "entries" in info:
                    entries = [x for x in (info.get("entries") or []) if x]
                    if not entries:
                        return None
                    info = entries[0]
                stream_url = info.get("url")
                if not stream_url:
                    formats = info.get("formats") or []
                    audio_formats = [f for f in formats if f.get("url") and f.get("acodec") not in (None, "none")]
                    if audio_formats:
                        audio_formats.sort(key=lambda f: f.get("abr") or 0, reverse=True)
                        stream_url = audio_formats[0].get("url")
                if not stream_url:
                    return None
                headers = dict(info.get("http_headers") or {})
                headers.setdefault("User-Agent", USER_AGENT)
                headers.setdefault("Referer", "https://www.youtube.com/")
                return {"url": stream_url, "headers": headers}
            except Exception as e:
                print("[MUSIC] [STREAM ERROR]", repr(e))
                return None

        return await loop.run_in_executor(None, extract)

    async def autoplay_song(self):
        loop = asyncio.get_running_loop()
        queries = ["popular Hindi songs", "Punjabi hit songs", "Bollywood hits", "English pop hits"]
        used_urls = set(self.autoplay_history)
        used_urls.update(self.play_history)
        if self.current:
            used_urls.add(self.current.url)

        def extract():
            for query in queries:
                try:
                    options = yt_options()
                    options["extract_flat"] = True
                    options["skip_download"] = True
                    with yt_dlp.YoutubeDL(options) as ydl:
                        info = ydl.extract_info(f"ytsearch10:{query}", download=False)
                    if not info:
                        continue
                    for entry in (info.get("entries") or []):
                        if not entry:
                            continue
                        video_id = entry.get("id")
                        title = entry.get("title") or ""
                        if not video_id or not title:
                            continue
                        url = entry.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
                        if url in used_urls or (self.current and is_same_song(title, self.current.title)):
                            continue
                        thumbnail = entry.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                        return Song(title, url, thumbnail, self.current.requester if self.current else None)
                except Exception as e:
                    pass
            return None

        song = await loop.run_in_executor(None, extract)
        if song:
            self.autoplay_history.append(song.url)
            self.play_history.append(song.url)
        return song

    async def play_next(self):
        async with self.play_lock:
            if not self.voice or not self.voice.is_connected():
                return
            if self.starting:
                return
            self.starting = True

            try:
                if self.loop and self.current:
                    song = self.current
                elif self.queue:
                    song = self.queue.popleft()
                    self.current = song
                elif self.autoplay and self.current:
                    song = await self.autoplay_song()
                    if not song:
                        self.current = None
                        await self.clear_voice_status()
                        return
                    self.current = song
                else:
                    self.current = None
                    await self.clear_voice_status()
                    return

                self.play_token += 1
                token = self.play_token
                print(f"[MUSIC] [PREPARE] {song.title} | token: {token}")

                if self.voice.is_playing() or self.voice.is_paused():
                    self.voice.stop()

                stream = await self.get_audio_stream(song)
                if not stream or token != self.play_token:
                    self.current = None
                    self.starting = False
                    if self.queue or self.autoplay:
                        asyncio.create_task(self.play_next())
                    return

                stream_url = stream["url"]
                headers = stream["headers"]
                header_lines = [f"{k}: {v}" for k, v in headers.items() if v]
                ffmpeg_headers = "\r\n".join(header_lines) + "\r\n"

                # Passing empty options to discord.py to prevent any default flag duplication conflicts
                before_options = f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -headers \"{ffmpeg_headers}\""
                
                # We completely strip out -ar and -ac from string options and let discord.py handle raw PCM safely via standard constructor
                try:
                    source = discord.FFmpegPCMAudio(
                        stream_url,
                        executable=FFMPEG_PATH,
                        before_options=before_options,
                        options="-vn"
                    )
                    source = discord.PCMVolumeTransformer(source, volume=self.volume)
                except Exception as e:
                    print("[MUSIC] [FFMPEG ERROR]", repr(e))
                    return

                def after_play(error):
                    if error:
                        print("[MUSIC] [FFMPEG]", repr(error))
                    try:
                        future = asyncio.run_coroutine_threadsafe(self.finished(token), self.bot.loop)
                        future.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
                    except Exception as e:
                        pass

                if token != self.play_token:
                    try:
                        source.cleanup()
                    except Exception:
                        pass
                    return

                self.song_start_time = time.monotonic()
                try:
                    self.voice.play(source, after=after_play)
                except Exception as e:
                    print("[MUSIC] [ERROR] voice.play:", repr(e))
                    try:
                        source.cleanup()
                    except Exception:
                        pass
                    return

                print(f"[MUSIC] [PLAYING] {song.title}")
                await self.voice_status(f"🎵 {song.title}")
                await self.send_now_playing()

            except Exception as e:
                print("[MUSIC] [PLAYBACK ERROR]", repr(e))
            finally:
                self.starting = False

    async def finished(self, token):
        if token != self.play_token:
            return
        await asyncio.sleep(0.05)
        if token != self.play_token or not self.voice or not self.voice.is_connected():
            return
        if self.voice.is_playing() or self.voice.is_paused():
            return
        await self.play_next()

    async def send_now_playing(self):
        if not self.text_channel or not self.current:
            return
        song = self.current
        requester = song.requester.mention if song.requester else "Unknown"
        embed = discord.Embed(
            title="🎵 HSL-CORP MUSIC",
            description=(
                f"## 🎶 NOW PLAYING\n\n**[{song.title}]({song.url})**\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Requested by: {requester}\n"
                f"🔊 Volume: {int(self.volume * 100)}%\n"
                f"🔁 Loop: {'🟢 ON' if self.loop else '🔴 OFF'}\n"
                f"🤖 Autoplay: {'🟢 ON' if self.autoplay else '🔴 OFF'}\n"
                "━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.blurple()
        )
        if song.thumbnail:
            embed.set_image(url=song.thumbnail)
        embed.set_thumbnail(url=HSL_GIF)
        embed.set_footer(text="HSL & CORPORATION • Music System")
        view = MusicControlView(self)
        try:
            if self.now_playing_message:
                await self.now_playing_message.edit(embed=embed, view=view)
            else:
                self.now_playing_message = await self.text_channel.send(embed=embed, view=view)
        except Exception:
            self.now_playing_message = None


# =========================================================
# CONTROL VIEW
# =========================================================

class MusicControlView(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(label="Pause", emoji="⏯️", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction, button):
        voice = self.player.voice
        if not voice:
            return await interaction.response.send_message("❌ Music is not playing.", ephemeral=True)
        if voice.is_playing():
            voice.pause()
            button.label = "Resume"
            await interaction.response.edit_message(view=self)
        elif voice.is_paused():
            voice.resume()
            button.label = "Pause"
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ Music is not playing.", ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.success)
    async def skip(self, interaction, button):
        player = self.player
        if not player.voice:
            return await interaction.response.send_message("❌ Music is not playing.", ephemeral=True)
        await interaction.response.defer()
        async with player.skip_lock:
            player.invalidate()
            if player.voice.is_playing() or player.voice.is_paused():
                player.voice.stop()
            player.starting = False
            await player.play_next()

    @discord.ui.button(label="Loop", emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction, button):
        self.player.loop = not self.player.loop
        status = "🟢 ON" if self.player.loop else "🔴 OFF"
        await interaction.response.send_message(f"🔁 Loop: **{status}**", ephemeral=True)
        await self.player.send_now_playing()

    @discord.ui.button(label="Autoplay", emoji="🤖", style=discord.ButtonStyle.secondary)
    async def autoplay(self, interaction, button):
        self.player.autoplay = not self.player.autoplay
        status = "🟢 ON" if self.player.autoplay else "🔴 OFF"
        await interaction.response.send_message(f"🤖 Autoplay: **{status}**", ephemeral=True)
        await self.player.send_now_playing()

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction, button):
        await interaction.response.defer()
        player = self.player
        player.invalidate()
        player.queue.clear()
        player.current = None
        player.starting = False
        player.autoplay_history.clear()
        player.play_history.clear()
        if player.voice:
            await player.clear_voice_status()
            if player.voice.is_playing() or player.voice.is_paused():
                player.voice.stop()
            try:
                await player.voice.disconnect()
            except Exception:
                pass
        player.voice = None
        player.text_channel = None
        player.now_playing_message = None


# =========================================================
# MUSIC COG
# =========================================================

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.play_command_locks = {}

    def get_player(self, guild_id):
        if guild_id not in self.players:
            self.players[guild_id] = MusicPlayer(self.bot)
        return self.players[guild_id]

    def get_play_lock(self, guild_id):
        if guild_id not in self.play_command_locks:
            self.play_command_locks[guild_id] = asyncio.Lock()
        return self.play_command_locks[guild_id]

    @commands.hybrid_command(name="play", description="Play a YouTube song")
    async def play(self, ctx, *, query: str):
        if not ctx.guild:
            return await ctx.send("❌ Server only.")
        if not ctx.author.voice:
            return await ctx.send("❌ Please join a voice channel first.", delete_after=4)

        player = self.get_player(ctx.guild.id)
        lock = self.get_play_lock(ctx.guild.id)

        async with lock:
            voice_channel = ctx.author.voice.channel
            player.text_channel = ctx.channel

            try:
                if ctx.voice_client:
                    player.voice = ctx.voice_client
                    if player.voice.channel != voice_channel:
                        await player.voice.move_to(voice_channel)
                else:
                    player.voice = await voice_channel.connect()
            except Exception as e:
                return await ctx.send("❌ Failed to connect to voice channel.", delete_after=5)

            loading = await ctx.send("🔎 **Searching YouTube...**")
            song = await player.resolve_song(query, ctx.author)
            try:
                await loading.delete()
            except Exception:
                pass

            if not song:
                return await ctx.send("❌ **YouTube could not find this song.**", delete_after=5)

            was_playing = player.starting or (player.voice and (player.voice.is_playing() or player.voice.is_paused())) or player.current is not None or bool(player.queue)
            player.play_history.append(song.url)
            player.queue.append(song)

            if was_playing:
                position = len(player.queue)
                return await ctx.send(f"🎵 **Added to queue:** `{song.title}` (Position: {position})", delete_after=8)

            await player.play_next()

    @commands.hybrid_command(name="skip", description="Skip current song")
    async def skip(self, ctx):
        if not ctx.guild:
            return
        player = self.get_player(ctx.guild.id)
        if not player.voice:
            return await ctx.send("❌ Music is not playing.", delete_after=4)
        async with player.skip_lock:
            player.invalidate()
            if player.voice.is_playing() or player.voice.is_paused():
                player.voice.stop()
            player.starting = False
            await player.play_next()

    @commands.hybrid_command(name="stop", description="Stop music")
    async def stop(self, ctx):
        player = self.get_player(ctx.guild.id)
        player.invalidate()
        player.queue.clear()
        player.current = None
        player.starting = False
        if player.voice:
            if player.voice.is_playing() or player.voice.is_paused():
                player.voice.stop()
            try:
                await player.voice.disconnect()
            except Exception:
                pass
        player.voice = None
        await ctx.send("⏹️ **Music stopped & queue cleared.**", delete_after=4)


async def setup(bot):
    await bot.add_cog(Music(bot))
    print("[MUSIC] [OK] Ultra-fast music cog loaded.")