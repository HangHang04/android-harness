from __future__ import annotations

import unittest

from android_harness.ui import (
    content_signature,
    find_nodes,
    jaccard_overlap,
    parse_hierarchy,
    preferred_text_matches,
)

XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
        package="com.example" content-desc="" clickable="false" enabled="true"
        scrollable="false" selected="false" focused="false" bounds="[0,0][1080,2400]">
    <node index="0" text="Weather" resource-id="com.example:id/title"
          class="android.widget.TextView" package="com.example" content-desc="Forecast"
          clickable="true" enabled="true" scrollable="false" selected="false"
          focused="false" bounds="[100,200][500,300]" />
    <node index="1" text="Weather report" resource-id="com.example:id/body"
          class="android.widget.TextView" package="com.example" content-desc=""
          clickable="false" enabled="true" scrollable="false" selected="false"
          focused="false" bounds="[100,400][800,500]" />
  </node>
</hierarchy>
"""


class UiTests(unittest.TestCase):
    def test_parses_nodes_and_centers(self) -> None:
        nodes = parse_hierarchy(XML)
        self.assertEqual(3, len(nodes))
        weather = nodes[1]
        self.assertEqual((300, 250), weather.center)
        self.assertTrue(weather.clickable)
        self.assertEqual("Forecast", weather.content_desc)

    def test_prefers_exact_matches_before_substrings(self) -> None:
        nodes = parse_hierarchy(XML)
        matches, match_type = preferred_text_matches(nodes, "Weather")
        self.assertEqual("exact", match_type)
        self.assertEqual(1, len(matches))
        self.assertEqual("Weather", matches[0].text)

    def test_supports_resource_and_class_filters(self) -> None:
        nodes = parse_hierarchy(XML)
        matches = find_nodes(
            nodes,
            "Weather",
            resource_id="com.example:id/title",
            class_name="android.widget.TextView",
            clickable=True,
        )
        self.assertEqual(1, len(matches))

    def test_content_signature_is_stable(self) -> None:
        first = content_signature(parse_hierarchy(XML), 2400)
        second = content_signature(parse_hierarchy(XML), 2400)
        self.assertEqual(first, second)

    def test_jaccard_overlap(self) -> None:
        self.assertEqual(0.5, jaccard_overlap(frozenset({"a", "b"}), frozenset({"b"})))
        self.assertEqual(1.0, jaccard_overlap(frozenset(), frozenset()))


if __name__ == "__main__":
    unittest.main()
