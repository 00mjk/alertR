import os
import time
from unittest import TestCase
from lib.globalData.sensorObjects import SensorObjSensorAlert, SensorObjStateChange
from lib.sensor.ping import PingSensor


class TestPingSensor(TestCase):

    def _create_base_sensor(self) -> PingSensor:
        sensor = PingSensor()
        sensor.id = 1
        sensor.description = "Test Ping"
        sensor.alertDelay = 0
        sensor.triggerAlert = True
        sensor.triggerAlertNormal = True
        sensor.triggerState = 1
        sensor.alertLevels = [1]
        self._sensors.append(sensor)
        return sensor

    def setUp(self):
        self._sensors = []

    def tearDown(self):
        for sensor in self._sensors:
            sensor.exit()

    def test_basic_sensor_alert_normal(self):
        """
        Tests if a Sensor Alert is triggered through a reachable host.
        """
        target_cmd = os.path.join("/",
                                  "bin",
                                  "ping")

        sensor = self._create_base_sensor()

        sensor.timeout = 5
        sensor.intervalToCheck = 60
        sensor.host = "localhost"
        sensor.execute = target_cmd

        sensor.initialize()
        sensor.state = 1

        sensor.start()

        # Make sure sensor is in correct initial state.
        self.assertEqual(1, sensor.state)

        time.sleep(4)

        events = sensor.get_events()
        self.assertEqual(1, len(events))
        self.assertEqual(SensorObjSensorAlert, type(events[0]))
        self.assertEqual(0, events[0].state)
        self.assertTrue(events[0].hasOptionalData)
        self.assertEqual("reachable", events[0].optionalData["reason"])

        # Make sure sensor state has changed.
        self.assertEqual(0, sensor.state)

    def test_basic_sensor_alert_triggered(self):
        """
        Tests if a Sensor Alert is triggered through an unreachable host.
        """
        target_cmd = os.path.join("/",
                                  "bin",
                                  "ping")

        sensor = self._create_base_sensor()

        sensor.timeout = 5
        sensor.intervalToCheck = 60
        sensor.host = "hostdoesnotexistiamsure"
        sensor.execute = target_cmd

        sensor.initialize()
        sensor.start()

        # Make sure sensor is in correct initial state.
        self.assertEqual(0, sensor.state)

        time.sleep(4)

        events = sensor.get_events()
        self.assertEqual(1, len(events))
        self.assertEqual(SensorObjSensorAlert, type(events[0]))
        self.assertEqual(1, events[0].state)
        self.assertTrue(events[0].hasOptionalData)
        self.assertEqual("notreachable", events[0].optionalData["reason"])

        # Make sure sensor state has changed.
        self.assertEqual(1, sensor.state)

    def test_basic_state_change_normal(self):
        """
        Tests if a state change is triggered through a reachable host.
        """
        target_cmd = os.path.join("/",
                                  "bin",
                                  "ping")

        sensor = self._create_base_sensor()
        sensor.triggerAlertNormal = False

        sensor.timeout = 5
        sensor.intervalToCheck = 60
        sensor.host = "localhost"
        sensor.execute = target_cmd

        sensor.initialize()
        sensor.state = 1

        sensor.start()

        # Make sure sensor is in correct initial state.
        self.assertEqual(1, sensor.state)

        time.sleep(4)

        events = sensor.get_events()
        self.assertEqual(1, len(events))
        self.assertEqual(SensorObjStateChange, type(events[0]))
        self.assertEqual(0, events[0].state)

        # Make sure sensor state has changed.
        self.assertEqual(0, sensor.state)

    def test_basic_state_change_triggered(self):
        """
        Tests if a state change is triggered through an unreachable host.
        """
        target_cmd = os.path.join("/",
                                  "bin",
                                  "ping")

        sensor = self._create_base_sensor()
        sensor.triggerAlert = False

        sensor.timeout = 5
        sensor.intervalToCheck = 60
        sensor.host = "hostdoesnotexistiamsure"
        sensor.execute = target_cmd

        sensor.initialize()
        sensor.start()

        # Make sure sensor is in correct initial state.
        self.assertEqual(0, sensor.state)

        time.sleep(4)

        events = sensor.get_events()
        self.assertEqual(1, len(events))
        self.assertEqual(SensorObjStateChange, type(events[0]))
        self.assertEqual(1, events[0].state)

        # Make sure sensor state has changed.
        self.assertEqual(1, sensor.state)

    def test_not_executable(self):
        """
        Tests if a sensor alert is triggered if ping execution fails.
        """
        target_cmd = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "ping_scripts",
                                  "not_executable.py")

        sensor = self._create_base_sensor()

        sensor.timeout = 5
        sensor.intervalToCheck = 60
        sensor.host = "localhost"
        sensor.execute = target_cmd

        sensor.initialize()
        sensor.start()

        # Make sure sensor is in correct initial state.
        self.assertEqual(0, sensor.state)

        time.sleep(1.5)

        events = sensor.get_events()
        self.assertEqual(1, len(events))
        self.assertEqual(SensorObjSensorAlert, type(events[0]))
        self.assertEqual(1, events[0].state)
        self.assertTrue(events[0].hasOptionalData)
        self.assertEqual("Unable to execute process", events[0].optionalData["message"])
        self.assertEqual("processerror", events[0].optionalData["reason"])

        # Make sure sensor state has not changed.
        self.assertEqual(0, sensor.state)

    def test_timeout(self):
        """
        Tests if a sensor alert is triggered if ping times out.
        """
        target_cmd = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "ping_scripts",
                                  "timeout.py")

        sensor = self._create_base_sensor()

        sensor.timeout = 2
        sensor.intervalToCheck = 60
        sensor.host = "localhost"
        sensor.execute = target_cmd

        sensor.initialize()
        sensor.start()

        # Make sure sensor is in correct initial state.
        self.assertEqual(0, sensor.state)

        time.sleep(5)

        events = sensor.get_events()
        self.assertEqual(1, len(events))
        self.assertEqual(SensorObjSensorAlert, type(events[0]))
        self.assertEqual(1, events[0].state)
        self.assertTrue(events[0].hasOptionalData)
        self.assertEqual("Timeout", events[0].optionalData["message"])
        self.assertEqual("processtimeout", events[0].optionalData["reason"])

        # Make sure sensor state has changed.
        self.assertEqual(1, sensor.state)
