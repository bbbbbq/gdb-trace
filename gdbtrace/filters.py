from __future__ import annotations

from .state import GdbTraceError
from .trace_model import TraceEvent


def _rebase_depth(events: list[TraceEvent]) -> list[TraceEvent]:
    if not events:
        return []
    min_depth = min(event.depth for event in events)
    if min_depth == 0:
        return events
    return [
        TraceEvent(
            kind=event.kind,
            depth=event.depth - min_depth,
            function=event.function,
            pc=event.pc,
            instruction=event.instruction,
            registers=event.registers,
        )
        for event in events
    ]


def _match_marker(event: TraceEvent, marker: str) -> bool:
    return event.pc == marker or event.function == marker


def _apply_window(events: list[TraceEvent], start: str, stop: str) -> list[TraceEvent]:
    start_index = 0
    if start:
        for idx, event in enumerate(events):
            if _match_marker(event, start):
                start_index = idx
                break
        else:
            raise GdbTraceError(f"start marker not found: {start}")

    stop_index = len(events) - 1
    if stop:
        for idx in range(start_index, len(events)):
            if _match_marker(events[idx], stop):
                stop_index = idx
                break
        else:
            raise GdbTraceError(f"stop marker not found: {stop}")

    return events[start_index : stop_index + 1]


def _collect_subtree(events: list[TraceEvent], root_index: int) -> list[TraceEvent]:
    root = events[root_index]
    if root.kind != "call":
        return [root]
    result = [root]
    for event in events[root_index + 1 :]:
        result.append(event)
        if event.kind == "ret" and event.depth == root.depth and event.function == root.function:
            break
    return result


def _apply_function_filter(events: list[TraceEvent], pattern: str) -> list[TraceEvent]:
    if not pattern:
        return events

    for index, event in enumerate(events):
        if pattern in event.function and event.kind == "call":
            return _collect_subtree(events, index)

    matching = [event for event in events if pattern in event.function]
    if matching:
        return matching

    raise GdbTraceError(f"function filter matched no events: {pattern}")


def _parse_range(filter_range: str) -> tuple[int, int]:
    start_text, sep, stop_text = filter_range.partition(":")
    if not sep or not start_text or not stop_text:
        raise GdbTraceError("filter-range must be in <start:end> format")
    try:
        start_value = int(start_text, 16)
        stop_value = int(stop_text, 16)
    except ValueError as exc:
        raise GdbTraceError("filter-range must contain hexadecimal addresses") from exc
    if start_value > stop_value:
        raise GdbTraceError("filter-range start must be <= end")
    return start_value, stop_value


def _apply_address_range(events: list[TraceEvent], filter_range: str) -> list[TraceEvent]:
    if not filter_range:
        return events

    start_value, stop_value = _parse_range(filter_range)
    matching_indexes = [
        index
        for index, event in enumerate(events)
        if event.kind == "inst" and event.pc and start_value <= int(event.pc, 16) <= stop_value
    ]
    if not matching_indexes:
        raise GdbTraceError(f"filter-range matched no events: {filter_range}")

    return events[matching_indexes[0] : matching_indexes[-1] + 1]


def apply_filters(
    events: list[TraceEvent],
    *,
    start: str = "",
    stop: str = "",
    filter_func: str = "",
    filter_range: str = "",
) -> list[TraceEvent]:
    filtered = _apply_window(events, start, stop)
    filtered = _apply_function_filter(filtered, filter_func)
    filtered = _apply_address_range(filtered, filter_range)
    return _rebase_depth(filtered)
