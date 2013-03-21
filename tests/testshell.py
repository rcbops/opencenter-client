import unittest
import opencenterclient
import opencenterclient.shell


class TestShell(unittest.TestCase):

    def test_deep_update(self):

        #simple merge test
        self.assertEqual({1: 1, 2: 2}, {1: 1, 2: 2})

        a = {
            'b': {
                'c': 0,
                'x': 2
            },
            'F': {
                1: 1,
                2: 2,
                3: 3
            }
        }

        b = {
            'b': {
                'd': 1,
                'x': None
            },
            'F': None
        }

        c = {
            'b': {
                'c': 0,
                'd': 1
            }
        }

        #deep merge test
        self.assertEqual(c, opencenterclient.shell.deep_update(a, b))
