#!/usr/bin/env python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import sys
import os
import stat
from lib import ServerCommunication, ConnectionWatchdog, Receiver
from lib import SMTPAlert
from lib import ScreenUpdater
from lib import Console
from lib import GlobalData
from lib import ManagerEventHandler
import logging
import time
import random
import xml.etree.ElementTree

asciiLogo = "" \
    + "         ,,,,,,,,,,,,,,,,,`` +                                     \n" \
    + "        ;@@@@@@@@@@@@@@@@@@@@@                                     \n" \
    + "        @                 @@  @                                    \n" \
    + "       @@                  @ @@                                    \n" \
    + "       @                   #@ ,@                                   \n" \
    + "      @+                    @  @                                   \n" \
    + "     .@                     :@ '#                                  \n" \
    + "     @.          @           @'@@                                  \n" \
    + "    '@           @@@          @:@@                                 \n" \
    + "    @           @ @@          @@ @                                 \n" \
    + "   @@           # @@@          @                          @@@@#;   \n" \
    + "   @           @  :@@          +@@ @                      @@@@@@@# \n" \
    + "  @;           #   @@@          @@@@@                     @@    ,@`\n" \
    + " ,@           @    ;@@          .@  @                .    @@     @+\n" \
    + " @`           #     @@#          @' @                @    @@     @.\n" \
    + "+@       `,;@@@@@@@@@@@@+:,,,,,,,,@,@,,,,,,,,,,,,,,,,@,,,,@@,,,,@@,\n" \
    + " @           #       @@@         @@ @   @@@@`  @ @@. @@@@ @@@@@@.  \n" \
    + " +@         @        #@@         @  @  @+   @  @@    @    @@  `@@` \n" \
    + "  @`        #         @@:       @;  @  @    @  @     @    @@    +@ \n" \
    + "  .@       @          @@@      ,@   @  @+@@@@  @     @    @@     @,\n" \
    + "   @'      #           @@,     @`   @  @       @     @    @@     @+\n" \
    + "    @     @            @@@    #@    @  +@   `  @     @    @@     @@\n" \
    + "    @@   +@@            @@'   @     @   '@@@`  @     `@@@ @@     @@\n" \
    + "     @   ````````````````````@#````````````````````````````````````\n" \
    + "     ;@                      @                                     \n" \
    + "      @,                    @,                                     \n" \
    + "      `@                   :@                                      \n" \
    + "       @+                  @                                       \n" \
    + "        @                 @@                                       \n" \
    + "        #@;;;;;;;;;;;;;;;;@                                        \n" \
    + "         @@@@@@@@@@@@@@@@@+                                        \n"


# Function creates a path location for the given user input.
def make_path(input_location: str) -> str:
    # Do nothing if the given location is an absolute path.
    if input_location[0] == "/":
        return input_location
    # Replace ~ with the home directory.
    elif input_location[0] == "~":
        pos = -1
        for i in range(1, len(input_location)):
            if input_location[i] == "/":
                continue
            pos = i
            break
        if pos == -1:
            return os.environ["HOME"]
        return os.path.join(os.environ["HOME"], input_location[pos:])
    # Assume we have a given relative path.
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), input_location)


if __name__ == '__main__':

    print(asciiLogo)

    # generate object of the global needed data
    globalData = GlobalData()

    log_tag = os.path.basename(__file__)

    # parse config file, get logfile configurations
    # and initialize logging
    try:
        configRoot = xml.etree.ElementTree.parse(globalData.configFile).getroot()

        logfile = make_path(str(configRoot.find("general").find("log").attrib["file"]))

        # parse chosen log level
        tempLoglevel = str(configRoot.find("general").find("log").attrib["level"])
        tempLoglevel = tempLoglevel.upper()
        if tempLoglevel == "DEBUG":
            loglevel = logging.DEBUG
        elif tempLoglevel == "INFO":
            loglevel = logging.INFO
        elif tempLoglevel == "WARNING":
            loglevel = logging.WARNING
        elif tempLoglevel == "ERROR":
            loglevel = logging.ERROR
        elif tempLoglevel == "CRITICAL":
            loglevel = logging.CRITICAL
        else:
            raise ValueError("No valid log level in config file.")

        # initialize logging
        logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                            datefmt='%m/%d/%Y %H:%M:%S',
                            filename=logfile,
                            level=loglevel)

    except Exception as e:
        print("Config could not be parsed.")
        print(e)
        sys.exit(1)

    # parse the rest of the config with initialized logging
    try:

        # Check file permission of config file (do not allow it to be accessible by others).
        config_stat = os.stat(globalData.configFile)
        if (config_stat.st_mode & stat.S_IROTH
                or config_stat.st_mode & stat.S_IWOTH
                or config_stat.st_mode & stat.S_IXOTH):
            raise ValueError("Config file is accessible by others. Please remove file permissions for others.")

        # check if config and client version are compatible
        version = float(configRoot.attrib["version"])
        if version != globalData.version:
            raise ValueError("Config version '%.3f' not "
                             % version
                             + "compatible with client version '%.3f'."
                             % globalData.version)

        # parse server configurations
        server = str(configRoot.find("general").find("server").attrib["host"])
        serverPort = int(configRoot.find("general").find("server").attrib["port"])

        # Get TLS/SSL configurations.
        ssl_enabled = (str(configRoot.find("general").find("ssl").attrib["enabled"]).upper() == "TRUE")
        server_ca_file = None
        client_cert_file = None
        client_key_file = None
        if ssl_enabled:
            server_ca_file = os.path.abspath(make_path(str(configRoot.find("general").find("ssl").find("server").attrib[
                                                             "caFile"])))
            if os.path.exists(server_ca_file) is False:
                raise ValueError("Server CA does not exist.")

            certificate_required = (str(configRoot.find("general").find("ssl").find("client").attrib[
                                           "certificateRequired"]).upper() == "TRUE")

            if certificate_required is True:
                client_cert_file = os.path.abspath(
                                 make_path(str(configRoot.find("general").find("ssl").find("client").attrib["certFile"])))
                client_key_file = os.path.abspath(
                                make_path(str(configRoot.find("general").find("ssl").find("client").attrib["keyFile"])))
                if (os.path.exists(client_cert_file) is False
                        or os.path.exists(client_key_file) is False):
                    raise ValueError("Client certificate or key does not exist.")

                key_stat = os.stat(client_key_file)
                if (key_stat.st_mode & stat.S_IROTH
                        or key_stat.st_mode & stat.S_IWOTH
                        or key_stat.st_mode & stat.S_IXOTH):
                    raise ValueError("Client key is accessible by others. Please remove file permissions for others.")

        else:
            logging.warning("[%s] TLS/SSL is disabled. Do NOT use this setting in a production environment."
                            % log_tag)

        # get user credentials
        username = str(configRoot.find("general").find("credentials").attrib["username"])
        password = str(configRoot.find("general").find("credentials").attrib["password"])

        # Get connection settings.
        temp = (str(configRoot.find("general").find("connection").attrib["persistent"]).upper() == "TRUE")
        if temp:
            globalData.persistent = 1
        else:
            globalData.persistent = 0

        # parse smtp options if activated
        smtpActivated = (str(configRoot.find("smtp").find("general").attrib["activated"]).upper() == "TRUE")
        smtpServer = ""
        smtpPort = -1
        smtpFromAddr = ""
        smtpToAddr = ""
        if smtpActivated is True:
            smtpServer = str(configRoot.find("smtp").find("server").attrib["host"])
            smtpPort = int(configRoot.find("smtp").find("server").attrib["port"])
            smtpFromAddr = str(configRoot.find("smtp").find("general").attrib["fromAddr"])
            smtpToAddr = str(configRoot.find("smtp").find("general").attrib["toAddr"])

        # get manager settings
        globalData.description = str(configRoot.find("manager").find("general").attrib["description"])

        # get display options for the console
        globalData.timeShowSensorAlert = int(configRoot.find("manager").find(
                                         "console").attrib["timeShowSensorAlert"])
        globalData.maxCountShowSensorAlert = int(configRoot.find("manager").find(
                                             "console").attrib["maxCountShowSensorAlert"])
        globalData.maxCountShowSensorsPerPage = int(configRoot.find("manager").find(
                                                "console").attrib["maxCountShowSensorsPerPage"])
        globalData.maxCountShowAlertsPerPage = int(configRoot.find("manager").find(
                                               "console").attrib["maxCountShowAlertsPerPage"])
        globalData.maxCountShowManagersPerPage = int(configRoot.find("manager").find(
                                                 "console").attrib["maxCountShowManagersPerPage"])
        globalData.maxCountShowAlertLevelsPerPage = int(configRoot.find("manager").find(
                                                    "console").attrib["maxCountShowAlertLevelsPerPage"])

    except Exception as e:
        logging.exception("[%s] Could not parse config." % log_tag)
        sys.exit(1)

    random.seed()

    # check if smtp is activated => generate object to send eMail alerts
    if smtpActivated is True:
        globalData.smtpAlert = SMTPAlert(smtpServer, smtpPort, smtpFromAddr, smtpToAddr)
    else:
        globalData.smtpAlert = None

    globalData.screenUpdater = ScreenUpdater(globalData)

    # Generate object for the communication to the server and connect to it.
    globalData.serverComm = ServerCommunication(server,
                                                serverPort,
                                                server_ca_file,
                                                username,
                                                password,
                                                client_cert_file,
                                                client_key_file,
                                                ManagerEventHandler(globalData),
                                                globalData)
    connectionRetries = 1
    logging.info("[%s] Connecting to server." % log_tag)
    print("Connecting to server at '%s:%d'." % (server, serverPort))
    while True:
        # check if 5 unsuccessful attempts are made to connect
        # to the server and if smtp alert is activated
        # => send eMail alert
        if (globalData.smtpAlert is not None
                and (connectionRetries % 5) == 0):
            globalData.smtpAlert.sendCommunicationAlert(connectionRetries)

        if globalData.serverComm.initialize() is True:
            # if smtp alert is activated
            # => send email that communication problems are solved
            if globalData.smtpAlert is not None:
                globalData.smtpAlert.sendCommunicationAlertClear()

            connectionRetries = 1
            break

        connectionRetries += 1

        logging.critical("[%s] Connecting to server failed. Try again in 5 seconds." % log_tag)
        print("Connecting to server failed. Try again in 5 seconds.")
        time.sleep(5)

    # when connected => generate watchdog object to monitor the
    # server connection
    logging.info("[%s] Starting watchdog thread." % log_tag)
    watchdog = ConnectionWatchdog(globalData.serverComm,
                                  globalData.pingInterval,
                                  globalData.smtpAlert)
    # set thread to daemon
    # => threads terminates when main thread terminates
    watchdog.daemon = True
    watchdog.start()

    # generate receiver to handle incoming data (for example status updates)
    logging.info("[%s] Starting receiver thread." % log_tag)
    receiver = Receiver(globalData.serverComm)
    # set thread to daemon
    # => threads terminates when main thread terminates
    receiver.daemon = True
    receiver.start()

    logging.info("[%s] Client started." % log_tag)

    # generate the console object and start it
    # (does not return unless it is exited)
    globalData.console = Console(globalData)
    globalData.console.startConsole()
