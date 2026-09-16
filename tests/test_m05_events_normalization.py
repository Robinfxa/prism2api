"""Tests for M05 Event Normalization and Delta Streaming (T27-T34)."""

import pytest
from prism2api.runtime.events import EventNormalizer, EventType


def test_t27_t28_delta_streaming_and_append_only():
    """T27/T28: Sequential TextDeltas accumulate text buffer correctly."""
    normalizer = EventNormalizer(run_id="run_1")
    normalizer.add_event(EventType.TEXT_DELTA, {"text": "Hello "})
    normalizer.add_event(EventType.TEXT_DELTA, {"text": "world!"})

    assert normalizer.text_buffer == "Hello world!"
    assert normalizer.seq_counter == 2
    assert normalizer.validate_append_only("Hello world! How are you?")
    assert not normalizer.validate_append_only("Rewritten text")
