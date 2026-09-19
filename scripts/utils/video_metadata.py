"""Extract playable video and platform-subtitle metadata from TikHub payloads."""


STREAM_CODECS = ("h264", "h265", "av1", "h266")


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _stream_url(container):
    if not isinstance(container, dict):
        return ""

    stream = container.get("stream") or (container.get("media") or {}).get("stream") or {}
    if not isinstance(stream, dict):
        return ""

    for codec in STREAM_CODECS:
        variants = stream.get(codec) or []
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            url = variant.get("master_url") or variant.get("masterUrl") or ""
            if url:
                return url
    return ""


def extract_video_metadata(raw):
    """Return the playable video URL and fresh Chinese subtitle URL when present."""
    result = {"video_url": "", "subtitle_url": "", "subtitle_language": ""}

    if not isinstance(raw, (dict, list)):
        return result

    video_info = None
    for item in _walk(raw):
        direct_url = item.get("videoUrl") or item.get("video_url") or ""
        if direct_url and not result["video_url"]:
            result["video_url"] = direct_url

        if video_info is None and isinstance(item.get("video_info_v2"), dict):
            video_info = item["video_info_v2"]

    if isinstance(video_info, dict):
        media = video_info.get("media") or {}
        result["video_url"] = result["video_url"] or _stream_url(media)
        video = media.get("video") if isinstance(media, dict) else {}
        subtitles = video.get("subtitles") if isinstance(video, dict) else {}
        zh_cn = subtitles.get("zh-CN") if isinstance(subtitles, dict) else []
        if isinstance(zh_cn, list):
            for subtitle in zh_cn:
                if isinstance(subtitle, dict) and subtitle.get("url"):
                    result["subtitle_url"] = subtitle["url"]
                    result["subtitle_language"] = "zh-CN"
                    break

    if not result["video_url"]:
        for item in _walk(raw):
            url = _stream_url(item)
            if url:
                result["video_url"] = url
                break

    return result
