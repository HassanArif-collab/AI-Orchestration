"""Tests for packages/core/json_utils.py — JSON utilities."""

import pytest
import json


class TestExtractJsonObject:
    """Tests for extract_json_object()."""

    def test_simple_object(self):
        from packages.core.json_utils import extract_json_object
        text = '{"key": "value"}'
        result = extract_json_object(text)
        assert result == '{"key": "value"}'

    def test_object_with_surrounding_text(self):
        from packages.core.json_utils import extract_json_object
        text = 'Here is the result: {"key": "value"} and more text'
        result = extract_json_object(text)
        assert result == '{"key": "value"}'

    def test_nested_object(self):
        from packages.core.json_utils import extract_json_object
        text = '{"outer": {"inner": "value"}}'
        result = extract_json_object(text)
        data = json.loads(result)
        assert data["outer"]["inner"] == "value"

    def test_object_with_arrays(self):
        from packages.core.json_utils import extract_json_object
        text = '{"items": [1, 2, 3], "name": "test"}'
        result = extract_json_object(text)
        data = json.loads(result)
        assert data["items"] == [1, 2, 3]

    def test_no_object_returns_none(self):
        from packages.core.json_utils import extract_json_object
        result = extract_json_object("No JSON here")
        assert result is None

    def test_empty_string(self):
        from packages.core.json_utils import extract_json_object
        result = extract_json_object("")
        assert result is None

    def test_returns_first_object(self):
        from packages.core.json_utils import extract_json_object
        text = '{"first": 1} {"second": 2}'
        result = extract_json_object(text)
        data = json.loads(result)
        assert data["first"] == 1

    def test_handles_escaped_quotes(self):
        from packages.core.json_utils import extract_json_object
        text = '{"key": "value with \\"quotes\\""}'
        result = extract_json_object(text)
        data = json.loads(result)
        assert 'quotes' in data["key"]

    def test_ignores_braces_in_strings(self):
        from packages.core.json_utils import extract_json_object
        text = '{"text": "Use {brackets} carefully"}'
        result = extract_json_object(text)
        assert result is not None
        data = json.loads(result)
        assert "{brackets}" in data["text"]

    def test_multiline_json(self):
        from packages.core.json_utils import extract_json_object
        text = '''The result is:
        {
            "name": "test",
            "value": 42
        }
        End of output.'''
        result = extract_json_object(text)
        data = json.loads(result)
        assert data["name"] == "test"
        assert data["value"] == 42

    def test_complex_nested_structure(self):
        from packages.core.json_utils import extract_json_object
        text = '{"a": {"b": [{"c": 1}, {"c": 2}]}, "d": null}'
        result = extract_json_object(text)
        data = json.loads(result)
        assert data["a"]["b"][0]["c"] == 1

    def test_llm_output_with_explanation(self):
        from packages.core.json_utils import extract_json_object
        text = """Based on my analysis, here are the findings:

{
    "confidence": 0.85,
    "findings": [
        "Finding 1",
        "Finding 2"
    ],
    "metadata": {
        "source_count": 5
    }
}

I hope this helps!"""
        result = extract_json_object(text)
        data = json.loads(result)
        assert data["confidence"] == 0.85
        assert len(data["findings"]) == 2


class TestExtractJsonArray:
    """Tests for extract_json_array()."""

    def test_simple_array(self):
        from packages.core.json_utils import extract_json_array
        text = '[1, 2, 3]'
        result = extract_json_array(text)
        assert result == '[1, 2, 3]'

    def test_array_with_surrounding_text(self):
        from packages.core.json_utils import extract_json_array
        text = 'Results: [{"id": 1}, {"id": 2}] end'
        result = extract_json_array(text)
        data = json.loads(result)
        assert len(data) == 2

    def test_no_array_returns_none(self):
        from packages.core.json_utils import extract_json_array
        result = extract_json_array('{"key": "value"}')
        assert result is None

    def test_nested_arrays(self):
        from packages.core.json_utils import extract_json_array
        text = '[[1, 2], [3, 4]]'
        result = extract_json_array(text)
        data = json.loads(result)
        assert data == [[1, 2], [3, 4]]

    def test_empty_array(self):
        from packages.core.json_utils import extract_json_array
        result = extract_json_array('[]')
        assert result == '[]'

    def test_array_of_objects(self):
        from packages.core.json_utils import extract_json_array
        text = '[{"name": "a"}, {"name": "b"}]'
        result = extract_json_array(text)
        data = json.loads(result)
        assert data[0]["name"] == "a"
