"""Structural checks for the observation-only manifest."""

from dataclasses import replace
import importlib
import socket
import subprocess
import unittest
from unittest.mock import patch

from benchmarks.web_observation_cases.cases import CASES, check_cases, manifest_sha256


class WebObservationCasesTests(unittest.TestCase):
    def test_manifest_structure_and_split(self):
        self.assertEqual(len(check_cases()), 24)
        self.assertEqual({split: sum(c.split == split for c in CASES)
                          for split in ('dev', 'held_out')}, {'dev': 12, 'held_out': 12})
        self.assertEqual(len({c.url for c in CASES}), 6)
        self.assertTrue(all(c.capture_status == 'provisional' and
                            c.expected_status == 'undetermined' for c in CASES))

    def test_duplicate_and_invalid_metadata(self):
        with self.assertRaises(ValueError):
            check_cases(CASES + (CASES[0],))
        for changes in ({'split': 'test'}, {'role': 'heading'}, {'target': ''},
                        {'capture_status': 'provisional', 'expected_status': 'found'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                check_cases((replace(CASES[0], **changes),) + CASES[1:])

    def test_url_rejections_and_domain_separation(self):
        bad_urls = ('http://docs.python.org/3/tutorial/index.html',
                    'https://user:pass@docs.python.org/3/tutorial/index.html',
                    'https://localhost/page', 'https://127.0.0.1/page',
                    'https://[::1]/page', 'https://10.2.3.4/page',
                    'https://192.168.1.1/page', 'https://host.local/page')
        for url in bad_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                check_cases((replace(CASES[0], url=url),) + CASES[1:])
        with self.assertRaises(ValueError):
            check_cases((replace(CASES[12], url=CASES[0].url),) + CASES[13:])

    def test_hash_is_deterministic_and_sensitive(self):
        self.assertEqual(manifest_sha256(), manifest_sha256(tuple(CASES)))
        self.assertNotEqual(manifest_sha256(),
                            manifest_sha256((replace(CASES[0], target='Other'),) + CASES[1:]))

    def test_import_has_no_browser_network_or_model_side_effect(self):
        with (patch.object(socket.socket, 'connect', side_effect=AssertionError('network')),
              patch.object(subprocess, 'Popen', side_effect=AssertionError('process'))):
            importlib.reload(importlib.import_module('benchmarks.web_observation_cases.cases'))


if __name__ == '__main__':
    unittest.main()
