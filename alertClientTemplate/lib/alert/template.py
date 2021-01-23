#!/usr/bin/env python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import logging
import os
from typing import Optional
from .core import _Alert
from ..globalData import ManagerObjSensorAlert, ManagerObjProfile


# This class represents an example alert
# (for example a GPIO on a Raspberry Pi which should be set to high
# or code that executes an external command).
class TemplateAlert(_Alert):

    def __init__(self):
        _Alert.__init__(self)

        # State of the alert (0 = "normal"; 1 = "triggered").
        self.state = None  # type: Optional[int]

        self._log_tag = os.path.basename(__file__)

    # this function is called once when the alert client has connected itself
    # to the server (should be use to initialize everything that is needed
    # for the alert)
    def initialize(self):

        # set the state of the alert to "normal"
        self.state = 0

        print("Initialize: initialized")

        # PLACE YOUR CODE HERE

    def alert_triggered(self, sensor_alert: ManagerObjSensorAlert):

        if self.state == 0:
            # Set state of alert to "triggered"
            self.state = sensor_alert.state

            logging.info("[%s]: Alert '%d' change to state %d." % (self._log_tag, self.id, self.state))

        print("Sensor Alert 'Triggered': trigger alert")

        # PLACE YOUR CODE HERE

    def alert_normal(self, sensor_alert: ManagerObjSensorAlert):

        if self.state == 1:
            # Set state of alert to "normal"
            self.state = sensor_alert.state

            logging.info("[%s]: Alert '%d' change to state %d." % (self._log_tag, self.id, self.state))

        print("Sensor Alert 'Normal': trigger alert")

        # PLACE YOUR CODE HERE

    def alert_profile_change(self, profile: ManagerObjProfile):

        logging.info("[%s]: Alert '%d' process system profile change." % (self._log_tag, self.id))

        print("Profile Change to '%d'" % profile.id)

        # PLACE YOUR CODE HERE
