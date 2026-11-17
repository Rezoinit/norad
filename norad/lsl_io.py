"""Small helpers around pylsl shared by sources, recorder and live view."""
import pylsl

_FMT = {"float32": pylsl.cf_float32, "double64": pylsl.cf_double64, "string": pylsl.cf_string}


def make_outlet(name: str, channels: list[str], srate: float, fmt: str = "float32",
                source_id: str = "", stype: str | None = None) -> pylsl.StreamOutlet:
    info = pylsl.StreamInfo(name, stype or name, len(channels), srate, _FMT[fmt], source_id or name)
    chs = info.desc().append_child("channels")
    for label in channels:
        chs.append_child("channel").append_child_value("label", label)
    return pylsl.StreamOutlet(info)


def find_streams(wait: float = 1.0) -> list[pylsl.StreamInfo]:
    """Our own streams plus any marker stream (e.g. PsychoPy)."""
    return [i for i in pylsl.resolve_streams(wait)
            if i.name().startswith("norad_") or i.type() == "Markers"]


def channel_labels(info: pylsl.StreamInfo) -> list[str]:
    labels, ch = [], info.desc().child("channels").child("channel")
    while not ch.empty():
        labels.append(ch.child_value("label"))
        ch = ch.next_sibling()
    if len(labels) != info.channel_count() or not all(labels):
        labels = [f"ch{i}" for i in range(info.channel_count())]
    return labels
