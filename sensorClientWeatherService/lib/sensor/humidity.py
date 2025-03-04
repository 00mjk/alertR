#!/usr/bin/env python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import os
from typing import Optional
from .number import _NumberSensor
from ..globalData import SensorDataType
from ..globalData.sensorObjects import SensorDataInt


class HumidityPollingSensor(_NumberSensor):
    """
    Class that controls one humidity sensor.
    """

    def __init__(self):
        _NumberSensor.__init__(self)

        self._unit = "%"

        # Used for logging.
        self._log_tag = os.path.basename(__file__)

        # Set sensor to hold float data.
        self.sensorDataType = SensorDataType.INT
        self.data = SensorDataInt(-1000, self._unit)

        # Instance of data collector thread.
        self.dataCollector = None

        self.country = None
        self.city = None
        self.lon = None
        self.lat = None

        # As long as errors occurring during the fetching of data are encoded as negative values,
        # we need the lowest value that we use for our threshold check.
        self._sane_lowest_value = 0

        # This sensor type string is used for log messages.
        self._log_desc = "Humidity"

    def _get_data(self) -> Optional[SensorDataInt]:
        data = None
        try:
            data = SensorDataInt(self.dataCollector.getHumidity(self.country, self.city, self.lon, self.lat),
                                 self._unit)

        except Exception as e:
            self._log_exception(self._log_tag, "Unable to get humidity data from provider.")

        return data

    def initialize(self) -> bool:
        if not super().initialize():
            return False

        self.state = 1 - self.triggerState

        self._optional_data = {"country": self.country,
                               "city": self.city,
                               "lon": self.lon,
                               "lat": self.lat,
                               "type": "humidity"}

        return True
