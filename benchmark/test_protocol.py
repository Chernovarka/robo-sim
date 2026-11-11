import unittest
from xml.etree import ElementTree as ET

from make_worlds import make_world
from spec import BODY_COUNTS, SCENARIOS, body_positions
from report import evaluate


class SelectionTests(unittest.TestCase):
    def test_positions_are_deterministic(self):
        self.assertEqual(body_positions(8, 'drop'), body_positions(8, 'drop'))
        self.assertEqual(len(body_positions(32, 'rest')), 32)

    def test_scene_body_count_and_timestep(self):
        for scenario in SCENARIOS:
            for count in BODY_COUNTS:
                root = ET.fromstring(make_world(count, scenario))
                self.assertEqual(len(root.findall('.//model')) - 1, count)
                self.assertEqual(root.findtext('.//physics/max_step_size'), '0.01')

    def test_scenes_have_no_navigation_components(self):
        for scenario in SCENARIOS:
            xml = make_world(8, scenario)
            self.assertNotIn('waypoint', xml)
            self.assertNotIn('obstacle', xml)
            self.assertNotIn('lidar', xml)

    def test_pilot_does_not_select_winners(self):
        trials = []
        for scenario in SCENARIOS:
            for count in BODY_COUNTS:
                for repetition in range(3):
                    for engine in ('pybullet', 'mujoco', 'gazebo'):
                        trials.append({'scenario': scenario, 'count': count, 'repetition': repetition,
                                       'engine': engine, 'valid': True,
                                       'measurements': {'steps_per_second': 100.0,
                                                        'memory_peak_bytes': 1000000,
                                                        'core_cpu_s': 0.5}})
        summary = evaluate(trials)
        self.assertTrue(summary['complete'])
        self.assertFalse(summary['ranking'])

    def test_cannot_select_winners_from_missing_data(self):
        summary = evaluate([{'scenario': 'drop', 'count': 1, 'repetition': 0,
                             'engine': 'pybullet', 'valid': True, 'measurements': {}}])
        self.assertFalse(summary['complete'])
        self.assertFalse(summary['ranking'])


if __name__ == '__main__':
    unittest.main()
