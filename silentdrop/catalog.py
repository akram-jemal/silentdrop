"""Public entry points reviewed for direct, account-free access checks."""

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Service:
    slug: str
    name: str
    category: str
    url: str
    markers: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    video_url: str | None = None

    @property
    def hosts(self) -> frozenset[str]:
        host = urlsplit(self.url).hostname
        assert host is not None
        return frozenset((host, *self.aliases))


SERVICES = (
    Service(
        "snapchat",
        "Snapchat",
        "Social",
        "https://www.snapchat.com/",
        ("Snapchat",),
        ("snapchat.com",),
    ),
    Service(
        "instagram",
        "Instagram",
        "Social",
        "https://www.instagram.com/",
        ("Instagram",),
        ("instagram.com",),
    ),
    Service(
        "facebook",
        "Facebook",
        "Social",
        "https://www.facebook.com/",
        ("Facebook",),
        ("facebook.com",),
    ),
    Service("reddit", "Reddit", "Social", "https://www.reddit.com/", ("Reddit",), ("reddit.com",)),
    Service("x", "X", "Social", "https://x.com/", ("X", "Twitter"), ("www.x.com",)),
    Service(
        "threads",
        "Threads",
        "Social",
        "https://www.threads.com/",
        ("Threads",),
        ("threads.com", "www.threads.net", "threads.net"),
    ),
    Service("bluesky", "Bluesky", "Social", "https://bsky.app/", ("Bluesky",)),
    Service("pinterest", "Pinterest", "Social", "https://www.pinterest.com/", ("Pinterest",)),
    Service("telegram-web", "Telegram Web", "Chat", "https://web.telegram.org/", ("Telegram",)),
    Service("whatsapp-web", "WhatsApp Web", "Chat", "https://web.whatsapp.com/", ("WhatsApp",)),
    Service("discord", "Discord", "Chat", "https://discord.com/", ("Discord",)),
    Service(
        "messenger",
        "Messenger",
        "Chat",
        "https://www.messenger.com/",
        ("Messenger",),
        ("messenger.com", "www.facebook.com"),
    ),
    Service("signal", "Signal", "Chat", "https://signal.org/", ("Signal",), ("www.signal.org",)),
    Service(
        "youtube",
        "YouTube",
        "Video",
        "https://www.youtube.com/",
        ("YouTube",),
        video_url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
    ),
    Service(
        "tiktok",
        "TikTok",
        "Video",
        "https://www.tiktok.com/",
        ("TikTok",),
        video_url="https://www.tiktok.com/@scout2015/video/6718335390845095173",
    ),
    Service("twitch", "Twitch", "Video", "https://www.twitch.tv/", ("Twitch",)),
    Service(
        "netflix", "Netflix", "Video", "https://www.netflix.com/", ("Netflix",), ("netflix.com",)
    ),
    Service(
        "disney-plus",
        "Disney+",
        "Video",
        "https://www.disneyplus.com/",
        ("Disney+",),
        ("disneyplus.com",),
    ),
    Service(
        "prime-video",
        "Prime Video",
        "Video",
        "https://www.primevideo.com/",
        ("Prime Video",),
        ("primevideo.com",),
    ),
    Service(
        "hbo-max",
        "HBO Max",
        "Video",
        "https://www.hbomax.com/",
        ("HBO Max",),
        ("hbomax.com", "www.max.com", "max.com"),
    ),
    Service("hulu", "Hulu", "Video", "https://www.hulu.com/", ("Hulu",), ("hulu.com",)),
    Service("spotify", "Spotify", "Music", "https://open.spotify.com/", ("Spotify",)),
    Service(
        "soundcloud",
        "SoundCloud",
        "Music",
        "https://soundcloud.com/",
        ("SoundCloud",),
        ("www.soundcloud.com",),
    ),
    Service("apple-music", "Apple Music", "Music", "https://music.apple.com/", ("Apple Music",)),
    Service("deezer", "Deezer", "Music", "https://www.deezer.com/", ("Deezer",), ("deezer.com",)),
    Service("steam", "Steam", "Gaming", "https://store.steampowered.com/", ("Steam",)),
    Service("roblox", "Roblox", "Gaming", "https://www.roblox.com/", ("Roblox",), ("roblox.com",)),
    Service(
        "epic-games", "Epic Games Store", "Gaming", "https://store.epicgames.com/", ("Epic Games",)
    ),
    Service("xbox", "Xbox", "Gaming", "https://www.xbox.com/", ("Xbox",), ("xbox.com",)),
    Service(
        "playstation",
        "PlayStation",
        "Gaming",
        "https://www.playstation.com/",
        ("PlayStation",),
        ("playstation.com",),
    ),
)

SERVICE_BY_SLUG = {service.slug: service for service in SERVICES}
