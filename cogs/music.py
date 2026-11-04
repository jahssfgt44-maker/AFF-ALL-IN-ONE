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

    "js_runtimes": {
        "deno": {}
    },

    "remote_components": [
        "ejs:github"
    ],
}


def yt_options():

    options = dict(BASE_YTDLP)

    options["http_headers"] = dict(
        BASE_YTDLP["http_headers"]
    )

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

    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

    remove_words = [
        "official",
        "video",
        "audio",
        "lyrics",
        "lyric",
        "music",
        "song",
        "full",
        "hd",
        "4k",
        "8k",
        "remix",
        "mix",
        "slowed",
        "reverb",
        "sped",
        "speed up",
        "nightcore",
        "lofi",
        "lo-fi",
        "cover",
        "live",
        "version",
        "visualizer",
        "visualiser",
        "edit",
        "extended",
        "bass boosted",
        "bassboosted",
        "shorts",
        "short",
    ]

    for word in remove_words:

        text = re.sub(
            r"\b" + re.escape(word) + r"\b",
            " ",
            text
        )

    text = re.sub(
        r"\([^)]*\)",
        " ",
        text
    )

    text = re.sub(
        r"\[[^\]]*\]",
        " ",
        text
    )

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def title_tokens(text):

    normalized = normalize_title(text)

    if not normalized:
        return set()

    stop_words = {
        "the",
        "a",
        "an",
        "of",
        "and",
        "to",
        "in",
        "on",
        "for",
        "is",
        "with",
        "from",
        "by",
        "at",
        "this",
        "that",
    }

    return {
        x
        for x in normalized.split()
        if len(x) >= 2
        and x not in stop_words
    }


def is_same_song(candidate_title, old_title):

    if not candidate_title or not old_title:
        return False

    a = normalize_title(candidate_title)
    b = normalize_title(old_title)

    if not a or not b:
        return False

    if a == b:
        return True

    if len(a) >= 5 and a in b:
        return True

    if len(b) >= 5 and b in a:
        return True

    a_tokens = title_tokens(a)
    b_tokens = title_tokens(b)

    if not a_tokens or not b_tokens:
        return False

    overlap = (
        len(a_tokens & b_tokens)
        /
        max(
            1,
            min(
                len(a_tokens),
                len(b_tokens)
            )
        )
    )

    return overlap >= 0.75


# =========================================================
# SONG
# =========================================================

class Song:

    def __init__(
        self,
        title,
        url,
        thumbnail,
        requester
    ):

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


    # =====================================================
    # TOKEN
    # =====================================================

    def invalidate(self):

        self.play_token += 1

        print(
            f"[MUSIC] [TOKEN] -> {self.play_token}"
        )

        return self.play_token


    # =====================================================
    # VOICE STATUS
    # =====================================================

    async def voice_status(self, text):

        if not self.voice:
            return

        if not self.voice.channel:
            return

        try:

            channel_id = self.voice.channel.id

            url = (
                "https://discord.com/api/v10/"
                f"channels/{channel_id}/voice-status"
            )

            headers = {
                "Authorization":
                    f"Bot {self.bot.http.token}",
                "Content-Type":
                    "application/json",
            }

            timeout = aiohttp.ClientTimeout(total=5)

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.put(
                    url,
                    headers=headers,
                    json={
                        "status": str(text)[:500]
                    }
                ) as response:

                    if response.status not in (200, 204):

                        print(
                            "[MUSIC] [WARN] Voice status:",
                            response.status
                        )

        except Exception as e:

            print(
                "[MUSIC] [WARN] Voice status:",
                repr(e)
            )


    async def clear_voice_status(self):

        await self.voice_status("")


    # =====================================================
    # FAST SONG SEARCH
    # =====================================================

    async def resolve_song(
        self,
        query,
        requester
    ):

        loop = asyncio.get_running_loop()

        def extract():

            query_text = str(query).strip()

            if not query_text:
                return None

            try:

                # -----------------------------------------
                # DIRECT URL
                # -----------------------------------------

                if query_text.startswith(
                    (
                        "http://",
                        "https://"
                    )
                ):

                    options = yt_options()

                    options.update({
                        "skip_download": True,
                        "noplaylist": True,
                        "extract_flat": True,
                    })

                    with yt_dlp.YoutubeDL(
                        options
                    ) as ydl:

                        info = ydl.extract_info(
                            query_text,
                            download=False
                        )

                    if not info:
                        return None

                    if "entries" in info:

                        entries = [
                            x
                            for x in (
                                info.get("entries")
                                or []
                            )
                            if x
                        ]

                        if not entries:
                            return None

                        info = entries[0]

                    video_id = info.get("id")

                    url = (
                        info.get("webpage_url")
                        or info.get("original_url")
                    )

                    if not url and video_id:

                        url = (
                            "https://www.youtube.com/"
                            f"watch?v={video_id}"
                        )

                    if not url:
                        return None

                    # =================================================
                    # THUMBNAIL FALLBACK
                    # =================================================

                    thumbnail = info.get("thumbnail")

                    if not thumbnail and video_id:
                        thumbnail = (
                            f"https://i.ytimg.com/vi/"
                            f"{video_id}/hqdefault.jpg"
                        )

                    return Song(
                        info.get(
                            "title",
                            "Unknown Song"
                        ),
                        url,
                        thumbnail,
                        requester
                    )

                # -----------------------------------------
                # FAST SEARCH
                # -----------------------------------------

                options = yt_options()

                options["extract_flat"] = True
                options["skip_download"] = True
                options["noplaylist"] = True

                with yt_dlp.YoutubeDL(
                    options
                ) as ydl:

                    info = ydl.extract_info(
                        f"ytsearch1:{query_text}",
                        download=False
                    )

                if not info:
                    return None

                entries = (
                    info.get("entries")
                    or []
                )

                if not entries:
                    return None

                entry = entries[0]

                if not entry:
                    return None

                title = entry.get("title") or ""

                video_id = entry.get("id")

                if not title or not video_id:
                    return None

                lower = title.lower()

                if any(
                    bad in lower
                    for bad in (
                        "shorts",
                        "live stream",
                        "full movie",
                    )
                ):
                    return None

                url = (
                    entry.get("webpage_url")
                    or
                    f"https://www.youtube.com/"
                    f"watch?v={video_id}"
                )

                # =================================================
                # THUMBNAIL FALLBACK
                # =================================================

                thumbnail = entry.get("thumbnail")

                if not thumbnail:
                    thumbnail = (
                        f"https://i.ytimg.com/vi/"
                        f"{video_id}/hqdefault.jpg"
                    )

                return Song(
                    title,
                    url,
                    thumbnail,
                    requester
                )

            except Exception as e:

                print(
                    "[MUSIC] [SEARCH ERROR]",
                    repr(e)
                )

                return None

        return await loop.run_in_executor(
            None,
            extract
        )


    # =====================================================
    # AUDIO STREAM
    # =====================================================

    async def get_audio_stream(self, song):

        loop = asyncio.get_running_loop()

        def extract():

            strategies = [
                {
                    "player_client": [
                        "web_embedded"
                    ]
                },
                {
                    "player_client": [
                        "android_vr"
                    ]
                },
            ]

            for index, strategy in enumerate(
                strategies,
                1
            ):

                try:

                    print(
                        "[MUSIC] [STREAM]",
                        f"{index}/{len(strategies)}",
                        song.title
                    )

                    options = yt_options()

                    options.update({

                        "skip_download": True,

                        "noplaylist": True,

                        "extract_flat": False,

                        "format": (
                            "bestaudio[protocol^=http]"
                            "/bestaudio"
                        ),

                    })

                    options["extractor_args"] = {
                        "youtube": strategy
                    }

                    with yt_dlp.YoutubeDL(
                        options
                    ) as ydl:

                        info = ydl.extract_info(
                            song.url,
                            download=False
                        )

                    if not info:
                        continue

                    if "entries" in info:

                        entries = [
                            x
                            for x in (
                                info.get("entries")
                                or []
                            )
                            if x
                        ]

                        if not entries:
                            continue

                        info = entries[0]

                    stream_url = info.get("url")

                    if not stream_url:

                        formats = (
                            info.get("formats")
                            or []
                        )

                        audio_formats = [
                            f
                            for f in formats
                            if f.get("url")
                            and f.get("acodec")
                            not in (None, "none")
                            and f.get("vcodec")
                            in (None, "none")
                        ]

                        if audio_formats:

                            audio_formats.sort(
                                key=lambda f:
                                (
                                    f.get("abr")
                                    or 0
                                ),
                                reverse=True
                            )

                            stream_url = (
                                audio_formats[0]
                                .get("url")
                            )

                    if not stream_url:
                        continue

                    headers = dict(
                        info.get(
                            "http_headers"
                        )
                        or {}
                    )

                    headers.setdefault(
                        "User-Agent",
                        USER_AGENT
                    )

                    headers.setdefault(
                        "Referer",
                        "https://www.youtube.com/"
                    )

                    return {
                        "url": stream_url,
                        "headers": headers
                    }

                except Exception as e:

                    print(
                        "[MUSIC] [STREAM ERROR]",
                        repr(e)
                    )

            return None

        return await loop.run_in_executor(
            None,
            extract
        )


    # =====================================================
    # AUTOPLAY
    # =====================================================

    async def autoplay_song(self):

        loop = asyncio.get_running_loop()

        queries = [
            "popular Hindi songs",
            "Punjabi hit songs",
            "Bollywood hits",
            "English pop hits",
        ]

        used_urls = set(
            self.autoplay_history
        )

        used_urls.update(
            self.play_history
        )

        if self.current:
            used_urls.add(
                self.current.url
            )

        def extract():

            for query in queries:

                try:

                    options = yt_options()

                    options["extract_flat"] = True
                    options["skip_download"] = True

                    with yt_dlp.YoutubeDL(
                        options
                    ) as ydl:

                        info = ydl.extract_info(
                            f"ytsearch10:{query}",
                            download=False
                        )

                    if not info:
                        continue

                    entries = (
                        info.get("entries")
                        or []
                    )

                    for entry in entries:

                        if not entry:
                            continue

                        video_id = entry.get("id")

                        if not video_id:
                            continue

                        title = (
                            entry.get("title")
                            or ""
                        )

                        if not title:
                            continue

                        url = (
                            entry.get("webpage_url")
                            or
                            f"https://www.youtube.com/"
                            f"watch?v={video_id}"
                        )

                        if url in used_urls:
                            continue

                        if self.current and is_same_song(
                            title,
                            self.current.title
                        ):
                            continue

                        lower = title.lower()

                        bad_words = (
                            "slowed",
                            "reverb",
                            "sped up",
                            "nightcore",
                            "8d audio",
                            "remix",
                            "cover",
                            "karaoke",
                            "instrumental",
                            "lofi",
                            "bass boosted",
                            "live concert",
                            "shorts",
                        )

                        if any(
                            word in lower
                            for word in bad_words
                        ):
                            continue

                        # =================================================
                        # THUMBNAIL FALLBACK
                        # =================================================

                        thumbnail = entry.get("thumbnail")

                        if not thumbnail:
                            thumbnail = (
                                f"https://i.ytimg.com/vi/"
                                f"{video_id}/hqdefault.jpg"
                            )

                        return Song(
                            title,
                            url,
                            thumbnail,
                            (
                                self.current.requester
                                if self.current
                                else None
                            )
                        )

                except Exception as e:

                    print(
                        "[MUSIC] [AUTOPLAY ERROR]",
                        repr(e)
                    )

            return None

        song = await loop.run_in_executor(
            None,
            extract
        )

        if song:

            self.autoplay_history.append(
                song.url
            )

            self.play_history.append(
                song.url
            )

            print(
                "[MUSIC] [AUTOPLAY]",
                song.title
            )

        return song


    # =====================================================
    # PLAY NEXT
    # =====================================================

    async def play_next(self):

        async with self.play_lock:

            if (
                not self.voice
                or
                not self.voice.is_connected()
            ):
                return

            if self.starting:
                return

            self.starting = True

            try:

                # -----------------------------------------
                # SELECT SONG
                # -----------------------------------------

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

                # -----------------------------------------
                # NEW TOKEN
                # -----------------------------------------

                self.play_token += 1
                token = self.play_token

                print(
                    "[MUSIC] [PREPARE]",
                    song.title,
                    "| token:",
                    token
                )

                # -----------------------------------------
                # STOP OLD SOURCE
                # -----------------------------------------

                if (
                    self.voice.is_playing()
                    or
                    self.voice.is_paused()
                ):

                    self.voice.stop()

                # -----------------------------------------
                # GET STREAM
                # -----------------------------------------

                stream = await self.get_audio_stream(
                    song
                )

                if not stream:

                    print(
                        "[MUSIC] [ERROR] "
                        "Audio stream unavailable:",
                        song.title
                    )

                    self.current = None

                    self.starting = False

                    if self.queue or self.autoplay:

                        asyncio.create_task(
                            self.play_next()
                        )

                    return

                # -----------------------------------------
                # TOKEN CHECK
                # -----------------------------------------

                if token != self.play_token:
                    return

                stream_url = stream["url"]

                headers = dict(
                    stream.get("headers")
                    or {}
                )

                headers.setdefault(
                    "User-Agent",
                    USER_AGENT
                )

                headers.setdefault(
                    "Referer",
                    "https://www.youtube.com/"
                )

                header_lines = [
                    f"{k}: {v}"
                    for k, v in headers.items()
                    if v
                ]

                ffmpeg_headers = (
                    "\r\n".join(header_lines)
                    + "\r\n"
                )

                # -----------------------------------------
                # FFMPEG
                # -----------------------------------------

                before_options = (
                    "-nostdin "
                    "-reconnect 1 "
                    "-reconnect_streamed 1 "
                    "-reconnect_at_eof 1 "
                    "-reconnect_on_network_error 1 "
                    "-reconnect_on_http_error "
                    "403,404,408,429,500,502,503,504 "
                    "-reconnect_delay_max 3 "
                    "-rw_timeout 10000000 "
                    "-headers "
                    f"\"{ffmpeg_headers}\""
                )

                ffmpeg_options = (
                    "-vn "
                    "-loglevel warning "
                    "-ar 48000 "
                    "-ac 2 "
                    "-bufsize 512k"
                )

                try:

                    source = discord.FFmpegPCMAudio(
                        stream_url,
                        executable=FFMPEG_PATH,
                        before_options=before_options,
                        options=ffmpeg_options
                    )

                    source = (
                        discord.PCMVolumeTransformer(
                            source,
                            volume=self.volume
                        )
                    )

                except Exception as e:

                    print(
                        "[MUSIC] [FFMPEG ERROR]",
                        repr(e)
                    )

                    return

                # -----------------------------------------
                # CALLBACK
                # -----------------------------------------

                def after_play(error):

                    if error:

                        print(
                            "[MUSIC] [FFMPEG]",
                            repr(error)
                        )

                    try:

                        future = (
                            asyncio
                            .run_coroutine_threadsafe(
                                self.finished(token),
                                self.bot.loop
                            )
                        )

                        def callback(f):

                            try:
                                f.exception()

                            except Exception:
                                pass

                        future.add_done_callback(
                            callback
                        )

                    except Exception as e:

                        print(
                            "[MUSIC] [CALLBACK]",
                            repr(e)
                        )

                # -----------------------------------------
                # FINAL TOKEN
                # -----------------------------------------

                if token != self.play_token:

                    try:
                        source.cleanup()
                    except Exception:
                        pass

                    return

                # -----------------------------------------
                # PLAY
                # -----------------------------------------
                self.song_start_time = time.monotonic()
                self.total_paused = 0
                try:

                    self.voice.play(
                        source,
                        after=after_play
                    )

                except Exception as e:

                    print(
                        "[MUSIC] [ERROR] voice.play:",
                        repr(e)
                    )

                    try:
                        source.cleanup()
                    except Exception:
                        pass

                    return

                print(
                    "[MUSIC] [PLAYING]",
                    song.title
                )

                await self.voice_status(
                    f"🎵 {song.title}"
                )

                await self.send_now_playing()

            except Exception as e:

                print(
                    "[MUSIC] [PLAYBACK ERROR]",
                    repr(e)
                )

            finally:

                self.starting = False


    # =====================================================
    # FINISHED
    # =====================================================

    async def finished(self, token):

        if token != self.play_token:
            return

        await asyncio.sleep(0.05)

        if token != self.play_token:
            return

        if (
            not self.voice
            or
            not self.voice.is_connected()
        ):
            return

        if (
            self.voice.is_playing()
            or
            self.voice.is_paused()
        ):
            return

        print(
            "[MUSIC] [FINISHED]",
            self.current.title
            if self.current
            else "Unknown"
        )

        await self.play_next()


    # =====================================================
    # NOW PLAYING
    # =====================================================

    async def send_now_playing(self):

        if (
            not self.text_channel
            or
            not self.current
        ):
            return

        song = self.current

        requester = (
            song.requester.mention
            if song.requester
            else "Unknown"
        )

        embed = discord.Embed(
            title="🎵 HSL-CORP MUSIC",
            description=(
                "## 🎶 NOW PLAYING\n\n"
                f"**[{song.title}]"
                f"({song.url})**\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Requested by: {requester}\n"
                f"🔊 Volume: "
                f"{int(self.volume * 100)}%\n"
                f"🔁 Loop: "
                f"{'🟢 ON' if self.loop else '🔴 OFF'}\n"
                f"🤖 Autoplay: "
                f"{'🟢 ON' if self.autoplay else '🔴 OFF'}\n"
                "━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.blurple()
        )

        # =====================================================
        # YOUTUBE SONG IMAGE
        # =====================================================

        if song.thumbnail:

            embed.set_image(
                url=song.thumbnail
            )

        embed.set_thumbnail(
            url=HSL_GIF
        )

        embed.set_footer(
            text="HSL & CORPORATION • Music System"
        )

        view = MusicControlView(
            self
        )

        try:

            if self.now_playing_message:

                await self.now_playing_message.edit(
                    embed=embed,
                    view=view
                )

            else:

                self.now_playing_message = (
                    await self.text_channel.send(
                        embed=embed,
                        view=view
                    )
                )

        except discord.NotFound:

            self.now_playing_message = None

        except Exception as e:

            print(
                "[MUSIC] [NOW PLAYING]",
                repr(e)
            )


# =========================================================
# CONTROL VIEW
# =========================================================

class MusicControlView(
    discord.ui.View
):

    def __init__(self, player):

        super().__init__(
            timeout=None
        )

        self.player = player


    # =====================================================
    # PAUSE / RESUME
    # =====================================================

    @discord.ui.button(
        label="Pause",
        emoji="⏯️",
        style=discord.ButtonStyle.primary
    )
    async def pause_resume(
        self,
        interaction,
        button
    ):

        voice = self.player.voice

        if not voice:

            return await interaction.response.send_message(
                "❌ Music is not playing.",
                ephemeral=True
            )

        if voice.is_playing():

            voice.pause()

            button.label = "Resume"

            await interaction.response.edit_message(
                view=self
            )

        elif voice.is_paused():

            voice.resume()

            button.label = "Pause"

            await interaction.response.edit_message(
                view=self
            )

        else:

            await interaction.response.send_message(
                "❌ Music is not playing.",
                ephemeral=True
            )


    # =====================================================
    # SKIP
    # =====================================================

    @discord.ui.button(
        label="Skip",
        emoji="⏭️",
        style=discord.ButtonStyle.success
    )
    async def skip(
        self,
        interaction,
        button
    ):

        player = self.player

        if not player.voice:

            return await interaction.response.send_message(
                "❌ Music is not playing.",
                ephemeral=True
            )

        if player.skip_lock.locked():

            return await interaction.response.send_message(
                "⚠️ Skip already processing.",
                ephemeral=True
            )

        await interaction.response.defer()

        async with player.skip_lock:

            player.invalidate()

            if (
                player.voice.is_playing()
                or
                player.voice.is_paused()
            ):

                player.voice.stop()

            player.starting = False

            await player.play_next()


    # =====================================================
    # LOOP
    # =====================================================

    @discord.ui.button(
        label="Loop",
        emoji="🔁",
        style=discord.ButtonStyle.secondary
    )
    async def loop(
        self,
        interaction,
        button
    ):

        self.player.loop = not self.player.loop

        status = (
            "🟢 ON"
            if self.player.loop
            else "🔴 OFF"
        )

        await interaction.response.send_message(
            f"🔁 Loop: **{status}**",
            ephemeral=True
        )

        await self.player.send_now_playing()


    # =====================================================
    # AUTOPLAY
    # =====================================================

    @discord.ui.button(
        label="Autoplay",
        emoji="🤖",
        style=discord.ButtonStyle.secondary
    )
    async def autoplay(
        self,
        interaction,
        button
    ):

        self.player.autoplay = (
            not self.player.autoplay
        )

        status = (
            "🟢 ON"
            if self.player.autoplay
            else "🔴 OFF"
        )

        await interaction.response.send_message(
            f"🤖 Autoplay: **{status}**",
            ephemeral=True
        )

        await self.player.send_now_playing()


    # =====================================================
    # STOP
    # =====================================================

    @discord.ui.button(
        label="Stop",
        emoji="⏹️",
        style=discord.ButtonStyle.danger
    )
    async def stop(
        self,
        interaction,
        button
    ):

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

            if (
                player.voice.is_playing()
                or
                player.voice.is_paused()
            ):

                player.voice.stop()

            try:
                await player.voice.disconnect()
            except Exception:
                pass

        player.voice = None
        player.text_channel = None
        player.now_playing_message = None

        try:

            await interaction.message.edit(
                content=(
                    "⏹️ **Music stopped "
                    "& queue cleared.**"
                ),
                embed=None,
                view=None
            )

        except Exception:
            pass


# =========================================================
# MUSIC COG
# =========================================================

class Music(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.players = {}
        self.play_command_locks = {}


    # =====================================================
    # PLAYER
    # =====================================================

    def get_player(self, guild_id):

        if guild_id not in self.players:

            self.players[guild_id] = (
                MusicPlayer(self.bot)
            )

        return self.players[guild_id]


    # =====================================================
    # PLAY LOCK
    # =====================================================

    def get_play_lock(self, guild_id):

        if guild_id not in self.play_command_locks:

            self.play_command_locks[guild_id] = (
                asyncio.Lock()
            )

        return self.play_command_locks[guild_id]


    # =====================================================
    # PLAY
    # =====================================================

    @commands.hybrid_command(
        name="play",
        description="Play a YouTube song"
    )
    async def play(
        self,
        ctx,
        *,
        query: str
    ):

        if not ctx.guild:

            return await ctx.send(
                "❌ Server only."
            )

        if not ctx.author.voice:

            return await ctx.send(
                "❌ Please join a voice channel first.",
                delete_after=4
            )

        player = self.get_player(
            ctx.guild.id
        )

        lock = self.get_play_lock(
            ctx.guild.id
        )

        async with lock:

            voice_channel = (
                ctx.author.voice.channel
            )

            request_key = (
                f"{ctx.author.id}:"
                f"{query.strip().lower()}"
            )

            now = time.monotonic()

            if (
                player.last_play_request
                ==
                request_key
                and
                now -
                player.last_play_request_time
                < 3
            ):

                return await ctx.send(
                    "⚠️ Same play request already received.",
                    delete_after=3
                )

            player.last_play_request = request_key
            player.last_play_request_time = now

            player.text_channel = ctx.channel

            # -----------------------------------------
            # VOICE
            # -----------------------------------------

            try:

                if ctx.voice_client:

                    player.voice = ctx.voice_client

                    if (
                        player.voice.channel
                        != voice_channel
                    ):

                        await player.voice.move_to(
                            voice_channel
                        )

                else:

                    player.voice = (
                        await voice_channel.connect()
                    )

            except Exception as e:

                print(
                    "[MUSIC] [VOICE]",
                    repr(e)
                )

                return await ctx.send(
                    "❌ Failed to connect to voice channel.",
                    delete_after=5
                )

            # -----------------------------------------
            # LOADING
            # -----------------------------------------

            loading = await ctx.send(
                "🔎 **Searching YouTube...**"
            )

            started = time.monotonic()

            song = await player.resolve_song(
                query,
                ctx.author
            )

            search_time = (
                time.monotonic()
                -
                started
            )

            print(
                f"[MUSIC] [SEARCH] "
                f"{search_time:.2f}s -> "
                f"{query}"
            )

            if not song:

                try:

                    await loading.edit(
                        content=(
                            "❌ **YouTube could not find "
                            "this song.**"
                        )
                    )

                except Exception:
                    pass

                return

            try:
                await loading.delete()
            except Exception:
                pass

            player.last_manual_query = query

            # -----------------------------------------
            # STATE
            # -----------------------------------------

            was_playing = (
                player.starting
                or
                (
                    player.voice
                    and
                    (
                        player.voice.is_playing()
                        or
                        player.voice.is_paused()
                    )
                )
                or
                player.current is not None
                or
                bool(player.queue)
            )

            player.play_history.append(
                song.url
            )

            player.queue.append(
                song
            )

            # -----------------------------------------
            # QUEUE
            # -----------------------------------------

            if was_playing:

                position = len(
                    player.queue
                )

                embed = discord.Embed(
                    title="🎵 ADDED TO QUEUE",
                    description=(
                        f"**[{song.title}]"
                        f"({song.url})**\n\n"
                        f"👤 {ctx.author.mention}\n"
                        f"📍 Position: `{position}`"
                    ),
                    color=discord.Color.green()
                )

                if song.thumbnail:

                    embed.set_image(
                        url=song.thumbnail
                    )

                embed.set_thumbnail(
                    url=HSL_GIF
                )

                return await ctx.send(
                    embed=embed,
                    delete_after=8
                )

            # -----------------------------------------
            # START
            # -----------------------------------------

            await player.play_next()


    # =====================================================
    # SKIP
    # =====================================================

    @commands.hybrid_command(
        name="skip",
        description="Skip current song"
    )
    async def skip(self, ctx):

        if not ctx.guild:
            return

        player = self.get_player(
            ctx.guild.id
        )

        if not player.voice:

            return await ctx.send(
                "❌ Music is not playing.",
                delete_after=4
            )

        if player.skip_lock.locked():

            return await ctx.send(
                "⚠️ Skip already processing.",
                delete_after=3
            )

        async with player.skip_lock:

            player.invalidate()

            if (
                player.voice.is_playing()
                or
                player.voice.is_paused()
            ):

                player.voice.stop()

            player.starting = False

            await player.play_next()

        # Delete prefix command

        try:

            if ctx.message:
                await ctx.message.delete()

        except Exception:
            pass


    # =====================================================
    # PAUSE
    # =====================================================

    @commands.hybrid_command(
        name="pause",
        description="Pause music"
    )
    async def pause(self, ctx):

        player = self.get_player(
            ctx.guild.id
        )

        if (
            player.voice
            and
            player.voice.is_playing()
        ):

            player.voice.pause()

            return await ctx.send(
                "⏸️ **Music paused.**",
                delete_after=3
            )

        await ctx.send(
            "❌ Music is not playing.",
            delete_after=3
        )


    # =====================================================
    # RESUME
    # =====================================================

    @commands.hybrid_command(
        name="resume",
        description="Resume music"
    )
    async def resume(self, ctx):

        player = self.get_player(
            ctx.guild.id
        )

        if (
            player.voice
            and
            player.voice.is_paused()
        ):

            player.voice.resume()

            return await ctx.send(
                "▶️ **Music resumed.**",
                delete_after=3
            )

        await ctx.send(
            "❌ Music is not paused.",
            delete_after=3
        )


    # =====================================================
    # STOP
    # =====================================================

    @commands.hybrid_command(
        name="stop",
        description="Stop music"
    )
    async def stop(self, ctx):

        player = self.get_player(
            ctx.guild.id
        )

        player.invalidate()

        player.queue.clear()

        player.current = None

        player.starting = False

        player.autoplay_history.clear()
        player.play_history.clear()

        if player.voice:

            await player.clear_voice_status()

            if (
                player.voice.is_playing()
                or
                player.voice.is_paused()
            ):

                player.voice.stop()

            try:
                await player.voice.disconnect()
            except Exception:
                pass

        player.voice = None
        player.text_channel = None
        player.now_playing_message = None

        await ctx.send(
            "⏹️ **Music stopped & queue cleared.**",
            delete_after=4
        )


    # =====================================================
    # QUEUE
    # =====================================================

    @commands.hybrid_command(
        name="queue",
        description="Show music queue"
    )
    async def queue(self, ctx):

        player = self.get_player(
            ctx.guild.id
        )

        if not player.queue:

            return await ctx.send(
                "📭 **Queue is empty.**",
                delete_after=4
            )

        lines = []

        for index, song in enumerate(
            list(player.queue)[:15],
            1
        ):

            lines.append(
                f"`{index}.` "
                f"**{song.title[:70]}**"
            )

        embed = discord.Embed(
            title="📜 HSL-CORP MUSIC QUEUE",
            description="\n".join(lines),
            color=discord.Color.blurple()
        )

        embed.set_thumbnail(
            url=HSL_GIF
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # VOLUME
    # =====================================================

    @commands.hybrid_command(
        name="volume",
        description="Change music volume"
    )
    async def volume(
        self,
        ctx,
        amount: int
    ):

        if amount < 0 or amount > 200:

            return await ctx.send(
                "❌ Volume must be between `0` and `200`.",
                delete_after=4
            )

        player = self.get_player(
            ctx.guild.id
        )

        player.volume = amount / 100

        if (
            player.voice
            and
            player.voice.source
        ):

            source = player.voice.source

            if isinstance(
                source,
                discord.PCMVolumeTransformer
            ):

                source.volume = amount / 100

        await ctx.send(
            f"🔊 **Volume set to {amount}%**",
            delete_after=4
        )


    # =====================================================
    # LOOP
    # =====================================================

    @commands.hybrid_command(
        name="loop",
        description="Toggle loop"
    )
    async def loop(self, ctx):

        player = self.get_player(
            ctx.guild.id
        )

        player.loop = not player.loop

        status = (
            "🟢 ON"
            if player.loop
            else "🔴 OFF"
        )

        await ctx.send(
            f"🔁 **Loop: {status}**",
            delete_after=4
        )


    # =====================================================
    # AUTOPLAY
    # =====================================================

    @commands.hybrid_command(
        name="autoplay",
        description="Toggle autoplay"
    )
    async def autoplay(self, ctx):

        player = self.get_player(
            ctx.guild.id
        )

        player.autoplay = not player.autoplay

        status = (
            "🟢 ON"
            if player.autoplay
            else "🔴 OFF"
        )

        await ctx.send(
            f"🤖 **Autoplay: {status}**",
            delete_after=4
        )

        if (
            player.autoplay
            and
            player.voice
            and
            player.current
            and
            not player.voice.is_playing()
            and
            not player.voice.is_paused()
        ):

            await player.play_next()


    # =====================================================
    # NOW PLAYING
    # =====================================================

    @commands.hybrid_command(
        name="nowplaying",
        description="Show current song"
    )
    async def nowplaying(self, ctx):

        player = self.get_player(
            ctx.guild.id
        )

        if not player.current:

            return await ctx.send(
                "❌ Nothing is playing.",
                delete_after=4
            )

        await player.send_now_playing()


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Music(bot)
    )

    print(
        "[MUSIC] [OK] Ultra-fast music cog loaded."
    )