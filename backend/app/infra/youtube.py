from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, parse, request


class YouTubeDataApiClientError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class YouTubeVideoMetadata:
    video_id: str
    channel_id: str
    channel_title: str
    title: str
    description: str
    published_at: str | None
    duration: str | None
    tags: list[str]
    thumbnails: dict[str, object]
    default_language: str | None
    default_audio_language: str | None
    category_id: str | None
    live_broadcast_content: str | None
    statistics: dict[str, object]

    def to_metadata_dict(self) -> dict[str, object]:
        return {
            "video_id": self.video_id,
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "title": self.title,
            "description": self.description,
            "published_at": self.published_at,
            "duration": self.duration,
            "tags": list(self.tags),
            "thumbnails": dict(self.thumbnails),
            "default_language": self.default_language,
            "default_audio_language": self.default_audio_language,
            "category_id": self.category_id,
            "live_broadcast_content": self.live_broadcast_content,
            "statistics": dict(self.statistics),
        }

    def build_index_text(self) -> str:
        parts: list[str] = [self.title, self.channel_title, self.description]
        if self.tags:
            parts.append(" ".join(self.tags))
        if self.duration:
            parts.append(f"Duration: {self.duration}")
        if self.category_id:
            parts.append(f"Category: {self.category_id}")
        if self.default_language:
            parts.append(f"Language: {self.default_language}")
        if self.default_audio_language:
            parts.append(f"Audio language: {self.default_audio_language}")
        if self.live_broadcast_content:
            parts.append(f"Live broadcast: {self.live_broadcast_content}")
        if self.published_at:
            parts.append(f"Published at: {self.published_at}")
        if self.statistics:
            statistic_bits = [f"{key}: {value}" for key, value in self.statistics.items()]
            parts.append("Statistics: " + ", ".join(statistic_bits))
        return "\n".join(part.strip() for part in parts if part and part.strip())

    def build_summary(self) -> str:
        headline = f'YouTube video "{self.title}" by {self.channel_title}.'
        details: list[str] = []
        if self.duration:
            details.append(f"Duration {self.duration}")
        if self.published_at:
            details.append(f"published {self.published_at}")
        if self.live_broadcast_content and self.live_broadcast_content != "none":
            details.append(f"broadcast status {self.live_broadcast_content}")
        if not details:
            return headline
        return headline + " " + ", ".join(details) + "."


@dataclass(frozen=True)
class YouTubeChannelMetadata:
    channel_id: str
    title: str
    description: str
    published_at: str | None
    thumbnails: dict[str, object]
    custom_url: str | None

    def to_metadata_dict(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "title": self.title,
            "description": self.description,
            "published_at": self.published_at,
            "thumbnails": dict(self.thumbnails),
            "custom_url": self.custom_url,
        }

    def build_index_text(self) -> str:
        parts: list[str] = [self.title, self.description]
        if self.published_at:
            parts.append(f"Published at: {self.published_at}")
        if self.custom_url:
            parts.append(f"Custom URL: {self.custom_url}")
        return "\n".join(part.strip() for part in parts if part and part.strip())

    def build_summary(self) -> str:
        headline = f'YouTube channel "{self.title}".'
        if not self.published_at:
            return headline
        return headline + f" Published {self.published_at}."


@dataclass(frozen=True)
class YouTubeChannelLookup:
    query_param: str
    query_value: str


class YouTubeDataApiClient:
    def __init__(self, *, api_key: str, timeout_sec: int = 10) -> None:
        self._api_key = api_key.strip()
        self._timeout_sec = timeout_sec

    def fetch_video_metadata(self, *, url: str) -> YouTubeVideoMetadata:
        if not self._api_key:
            raise YouTubeDataApiClientError("YOUTUBE_API_KEY is not configured")

        video_id = extract_youtube_video_id(url)
        if not video_id:
            raise YouTubeDataApiClientError(f"Unsupported YouTube video URL: {url}")

        payload = self._request_json(
            endpoint="videos",
            params={
                "part": "snippet,contentDetails,statistics",
                "id": video_id,
            },
        )

        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise YouTubeDataApiClientError(f"YouTube video metadata not found for video_id={video_id}")

        item = items[0]
        if not isinstance(item, dict):
            raise YouTubeDataApiClientError("YouTube Data API returned an invalid video item", retryable=True)

        snippet = item.get("snippet")
        if not isinstance(snippet, dict):
            raise YouTubeDataApiClientError("YouTube Data API video response did not include snippet")

        content_details = item.get("contentDetails")
        if content_details is None:
            content_details = {}
        if not isinstance(content_details, dict):
            raise YouTubeDataApiClientError("YouTube Data API video response returned invalid contentDetails")

        statistics = item.get("statistics")
        if statistics is None:
            statistics = {}
        if not isinstance(statistics, dict):
            raise YouTubeDataApiClientError("YouTube Data API video response returned invalid statistics")

        item_video_id = item.get("id")
        channel_id = snippet.get("channelId")
        channel_title = snippet.get("channelTitle")
        title = snippet.get("title")
        description = snippet.get("description", "")
        if not all(isinstance(value, str) and value for value in (item_video_id, channel_id, channel_title, title)):
            raise YouTubeDataApiClientError("YouTube Data API video response omitted required metadata fields")
        if not isinstance(description, str):
            raise YouTubeDataApiClientError("YouTube Data API video description was not text")

        item_video_id = str(item_video_id)
        channel_id = str(channel_id)
        channel_title = str(channel_title)
        title = str(title)

        tags_raw = snippet.get("tags")
        tags = [tag for tag in tags_raw if isinstance(tag, str)] if isinstance(tags_raw, list) else []
        thumbnails_raw = snippet.get("thumbnails")
        thumbnails = thumbnails_raw if isinstance(thumbnails_raw, dict) else {}

        return YouTubeVideoMetadata(
            video_id=item_video_id,
            channel_id=channel_id,
            channel_title=channel_title,
            title=title,
            description=description,
            published_at=_as_optional_string(snippet.get("publishedAt")),
            duration=_as_optional_string(content_details.get("duration")),
            tags=tags,
            thumbnails=thumbnails,
            default_language=_as_optional_string(snippet.get("defaultLanguage")),
            default_audio_language=_as_optional_string(snippet.get("defaultAudioLanguage")),
            category_id=_as_optional_string(snippet.get("categoryId")),
            live_broadcast_content=_as_optional_string(snippet.get("liveBroadcastContent")),
            statistics={key: value for key, value in statistics.items() if isinstance(key, str)},
        )

    def fetch_channel_metadata(self, *, url: str) -> YouTubeChannelMetadata:
        if not self._api_key:
            raise YouTubeDataApiClientError("YOUTUBE_API_KEY is not configured")

        channel_lookup = extract_youtube_channel_lookup(url)
        if channel_lookup is None:
            raise YouTubeDataApiClientError(f"Unsupported YouTube channel URL: {url}")

        payload = self._request_json(
            endpoint="channels",
            params={
                "part": "snippet",
                channel_lookup.query_param: channel_lookup.query_value,
            },
        )

        items = payload.get("items")
        if not isinstance(items, list) or not items:
            raise YouTubeDataApiClientError(
                f"YouTube channel metadata not found for {channel_lookup.query_param}={channel_lookup.query_value}"
            )

        item = items[0]
        if not isinstance(item, dict):
            raise YouTubeDataApiClientError("YouTube Data API returned an invalid channel item", retryable=True)

        snippet = item.get("snippet")
        if not isinstance(snippet, dict):
            raise YouTubeDataApiClientError("YouTube Data API channel response did not include snippet")

        channel_id = item.get("id")
        title = snippet.get("title")
        description = snippet.get("description", "")
        if not all(isinstance(value, str) and value for value in (channel_id, title)):
            raise YouTubeDataApiClientError("YouTube Data API channel response omitted required metadata fields")
        if not isinstance(description, str):
            raise YouTubeDataApiClientError("YouTube Data API channel description was not text")

        channel_id = str(channel_id)
        title = str(title)

        thumbnails_raw = snippet.get("thumbnails")
        thumbnails = thumbnails_raw if isinstance(thumbnails_raw, dict) else {}

        return YouTubeChannelMetadata(
            channel_id=channel_id,
            title=title,
            description=description,
            published_at=_as_optional_string(snippet.get("publishedAt")),
            thumbnails=thumbnails,
            custom_url=_as_optional_string(snippet.get("customUrl")),
        )

    def _request_json(self, *, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        query = parse.urlencode({**params, "key": self._api_key})
        target_url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{query}"
        http_request = request.Request(target_url, headers={"Accept": "application/json"}, method="GET")

        try:
            with request.urlopen(http_request, timeout=self._timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise YouTubeDataApiClientError(
                f"YouTube Data API request failed with HTTP {exc.code}: {detail}",
                retryable=exc.code == 429 or 500 <= exc.code < 600,
            ) from exc
        except error.URLError as exc:
            raise YouTubeDataApiClientError(
                f"YouTube Data API request failed: {exc.reason}",
                retryable=True,
            ) from exc

        if not isinstance(payload, dict):
            raise YouTubeDataApiClientError("YouTube Data API response was not a JSON object", retryable=True)

        return payload


def extract_youtube_video_id(url: str) -> str | None:
    parsed_url = parse.urlsplit(url)
    hostname = (parsed_url.hostname or "").lower()
    path_parts = [part for part in parsed_url.path.split("/") if part]

    if hostname == "youtu.be":
        return path_parts[0] if path_parts else None

    if hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed_url.path == "/watch":
            query_params = parse.parse_qs(parsed_url.query)
            video_ids = query_params.get("v")
            if video_ids:
                return video_ids[0]
        if path_parts[:1] in (["shorts"], ["embed"], ["live"]):
            return path_parts[1] if len(path_parts) > 1 else None

    return None


def extract_youtube_channel_lookup(url: str) -> YouTubeChannelLookup | None:
    parsed_url = parse.urlsplit(url)
    hostname = (parsed_url.hostname or "").lower()
    path_parts = [part for part in parsed_url.path.split("/") if part]

    if hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        return None

    if not path_parts:
        return None

    first_part = path_parts[0]
    if first_part == "channel" and len(path_parts) > 1:
        return YouTubeChannelLookup(query_param="id", query_value=path_parts[1])
    if first_part.startswith("@") and len(first_part) > 1:
        return YouTubeChannelLookup(query_param="forHandle", query_value=first_part[1:])
    if first_part == "user" and len(path_parts) > 1:
        return YouTubeChannelLookup(query_param="forUsername", query_value=path_parts[1])
    if first_part == "c" and len(path_parts) > 1:
        return YouTubeChannelLookup(query_param="forHandle", query_value=path_parts[1])

    return None


def _as_optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
