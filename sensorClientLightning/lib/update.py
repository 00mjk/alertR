#!/usr/bin/python2

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: http://blog.h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Public License, version 2.

import socket
import ssl
import httplib
import threading
import os
import time
import logging
import json
import hashlib
import tempfile
import shutil


# internal class that is used as an enum to represent the type of file update
class _FileUpdateType:
	NEW = 1
	DELETE = 2
	MODIFY = 3


# HTTPSConnection like class that verifies server certificates
class VerifiedHTTPSConnection(httplib.HTTPSConnection):
	# needs socket and ssl lib
	def __init__(self, host, port=None, servercert_file=None, 
		key_file=None, cert_file=None, strict=None, 
		timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
		httplib.HTTPSConnection.__init__(self, host, port, key_file, 
			cert_file, strict, timeout)
		self.servercert_file = servercert_file

	# overwrites the original version of httplib (python 2.6)
	def connect(self):
		"Connect to a host on a given (SSL) port."

		sock = socket.create_connection((self.host, self.port), self.timeout)
		if self._tunnel_host:
			self.sock = sock
			self._tunnel()

		# the only thing that has to be changed in the original function from
		# httplib (tell ssl.wrap_socket to verify server certificate)
		self.sock = ssl.wrap_socket(sock, self.key_file, 
			self.cert_file, cert_reqs=ssl.CERT_REQUIRED, 
			ca_certs=self.servercert_file)


# this class checks in specific intervals for updates and notifies
# the user about new versions of this client
class UpdateChecker(threading.Thread):

	def __init__(self, host, port, serverPath, caFile, interval,
		emailNotification, globalData):
		threading.Thread.__init__(self)

		# used for logging
		self.fileName = os.path.basename(__file__)

		# get global configured data
		self.globalData = globalData
		self.version = self.globalData.version
		self.rev = self.globalData.rev
		self.smtpAlert = self.globalData.smtpAlert

		# set interval for update checking
		self.checkInterval = interval

		# create an updater process
		self.updater = Updater(host, port, serverPath, caFile,
			self.globalData)

		self.emailNotification = emailNotification

		# needed to keep track of the newest version
		self.newestVersion = self.version
		self.newestRev = self.rev


	def run(self):

		updateFailCount = 0

		while True:

			time.sleep(self.checkInterval)

			# check if updates failed at least 10 times in a row
			# => log and notify user
			if updateFailCount >= 10:

				logging.error("[%s]: Update checking failed for %d "
					% (self.fileName, updateFailCount)
					+ "times in a row.")

				if self.emailNotification is True:
					self.smtpAlert.sendUpdateCheckFailureAlert(
						updateFailCount, self.globalData.name)

			logging.info("[%s]: Checking for a new version." % self.fileName)

			if self.updater.getNewestVersionInformation() is False:
				updateFailCount += 1
				continue

			# check if updates failed at least 10 times in a row before
			# => problems are now resolved => log and notify user
			if updateFailCount >= 10:
				logging.info("[%s]: Update problems resolved."
					% self.fileName)

				if self.emailNotification is True:
					self.smtpAlert.sendUpdateCheckFailureAlertClear(
						updateFailCount, self.globalData.name)

			updateFailCount = 0

			# check if the version on the server is newer than the used
			# (or last known) one
			# => notify user about the new version
			if (self.updater.newestVersion > self.newestVersion or
				(self.updater.newestRev > self.newestRev
				and self.updater.newestVersion == self.newestVersion)):

				logging.warning("[%s]: New version %.3f-%d available "
					% (self.fileName, self.updater.newestVersion,
					self.updater.newestRev)
					+ "(current version: %.3f-%d)."
					% (self.version, self.rev))

				# update newest known version
				self.newestVersion = self.updater.newestVersion
				self.newestRev = self.updater.newestRev

				if self.emailNotification is True:
					self.smtpAlert.sendUpdateCheckNewVersion(self.version,
						self.rev, self.newestVersion, self.newestRev,
						self.globalData.name)

			else:

				logging.info("[%s]: No new version available."
					% self.fileName)







class Updater:


	def __init__(self, host, port, serverPath, caFile, globalData):

		# used for logging
		self.fileName = os.path.basename(__file__)

		# the updater object is not thread safe
		self.updaterLock = threading.Semaphore(1)

		# get global configured data
		self.globalData = globalData
		self.version = self.globalData.version
		self.rev = self.globalData.rev
		self.smtpAlert = self.globalData.smtpAlert
		self.instance = self.globalData.instance

		# set update server configuration
		self.host = host
		self.port = port
		self.serverPath = serverPath
		self.caFile = caFile

		# needed to keep track of the newest version
		self.newestVersion = self.version
		self.newestRev = self.rev
		self.newestFiles = None
		self.lastChecked = 0.0
		self.repoInstanceLocation = None




		# TODO
		self.chunkSize = 4096



	# internal function that acquires the lock
	def _acquireLock(self):
		logging.debug("[%s]: Acquire lock." % self.fileName)
		self.updaterLock.acquire()


	# internal function that releases the lock
	def _releaseLock(self):
		logging.debug("[%s]: Release lock." % self.fileName)
		self.updaterLock.release()


	# internal function that checks which files are new and which files have
	# to be updated
	#
	# return a dict of files that are affected by this update (and how) or None
	def _checkFilesToUpdate(self):

		# check if the last version information check was done shortly before
		# => if not get the newest version information
		if (time.time() - self.lastChecked) > 60:
			if self._getNewestVersionInformation() is False:
				logging.error("[%s]: Not able to get version "
					% self.fileName
					+ "information for checking files.")
				return None

		counterUpdate = 0
		counterNew = 0

		# get the absolute location to this instance
		instanceLocation = os.path.dirname(os.path.abspath(__file__)) + "/../"

		# get all files that have to be updated
		filesToUpdate = dict()
		for clientFile in self.newestFiles.keys():

			# check if file already exists
			# => check if file has to be updated
			if os.path.exists(instanceLocation + clientFile):

				f = open(instanceLocation + clientFile, 'r')
				sha256Hash = self._sha256File(f)
				f.close()

				# check if file has changed
				# => if not ignore it
				if sha256Hash == self.newestFiles[clientFile]:

					logging.debug("[%s]: Not changed: '%s'"
						% (self.fileName, clientFile))

					continue

				# => if it has changed add it to the list of files to update
				else:

					logging.debug("[%s]: New version: '%s'"
						% (self.fileName, clientFile))

					filesToUpdate[clientFile] = _FileUpdateType.MODIFY
					counterUpdate += 1

			# => if the file does not exist, just add it
			else:

				logging.debug("[%s]: New file: '%s'"
					% (self.fileName, clientFile))

				filesToUpdate[clientFile] = _FileUpdateType.NEW
				counterNew += 1

		logging.info("[%s]: Files to modify: %d; New files: %d"
			% (self.fileName, counterUpdate, counterNew))

		return filesToUpdate


	# internal function that checks the needed permissions to
	# perform the update
	#
	# return True or False
	def _checkFilePermissions(self, filesToUpdate):

		# get the absolute location to this instance
		instanceLocation = os.path.dirname(os.path.abspath(__file__)) + "/../"

		# check permissions for each file that is affected by this update
		for clientFile in filesToUpdate.keys():

			# check if the file just has to be modified
			if filesToUpdate[clientFile] == _FileUpdateType.MODIFY:

				# check if the file is not writable
				# => cancel update
				if not os.access(instanceLocation + clientFile, os.W_OK):
					logging.error("[%s]: File '%s' is not writable."
						% (self.fileName, clientFile))
					return False

				logging.debug("[%s]: File '%s' is writable."
						% (self.fileName, clientFile))


			# check if the file is new and has to be created
			elif filesToUpdate[clientFile] == _FileUpdateType.NEW:

				logging.debug("[%s]: Checking write permissions for new "
					% self.fileName
					+ "file: '%s'"
					% clientFile)

				folderStructure = clientFile.split("/")

				# check if the new file is located in the root directory
				# of the instance
				# => check root directory of the instance for write permissions
				if len(folderStructure) == 1:
					if not os.access(instanceLocation, os.W_OK):
						logging.error("[%s]: Folder './' is not "
							% self.fileName
							+ "writable.")
						return False

					logging.debug("[%s]: Folder './' is writable."
						% self.fileName)

				# if new file is not located in the root directory
				# of the instance
				# => check all folders on the way to the new file for write
				# permissions
				else:
					tempPart = ""
					for filePart in folderStructure:

						# check if folder exists
						if os.path.exists(instanceLocation + tempPart
							+ "/" + filePart):

							# check if folder is not writable
							# => cancel update
							if not os.access(instanceLocation + tempPart
								+ "/" + filePart, os.W_OK):
								logging.error("[%s]: Folder '.%s/%s' is not "
									% (self.fileName, tempPart, filePart)
									+ "writable.")
								return False

							logging.debug("[%s]: Folder '.%s/%s' is writable."
								% (self.fileName, tempPart, filePart))

							tempPart += "/"
							tempPart += filePart


			# check if the file has to be deleted
			elif filesToUpdate[clientFile] == _FileUpdateType.DELETE:
				raise NotImplementedError("Feature not yet implemented.")


		return True


	# internal function that creates sub directories in the target directory
	# for the given file location
	#
	# return True or False
	def _createSubDirectories(self, fileLocation, targetDirectory):

		folderStructure = fileLocation.split("/")
		if len(folderStructure) != 1:

			try:

				i = 0
				tempPart = ""
				while i < (len(folderStructure) - 1):

					# check if the sub directory already exists
					# => if not create it
					if not os.path.exists(targetDirectory + tempPart + "/"
						+ folderStructure[i]):

						logging.debug("[%s]: Creating directory '%s/%s/%s'."
							% (self.fileName, targetDirectory, tempPart,
							folderStructure[i]))

						os.mkdir(targetDirectory + tempPart + "/"
							+ folderStructure[i])

					# if the sub directory already exists then check
					# if it is a directory
					# => raise an exception if it is not
					elif not os.path.isdir(targetDirectory + tempPart + "/"
						+ folderStructure[i]):

						raise ValueError("Location '%s' already exists "
							% (tempPart + "/" + folderStructure[i])
							+ "and is not a directory.")

					# only log if sub directory already exists
					else:
						logging.debug("[%s]: Directory '%s/%s/%s' already "
							% (self.fileName, targetDirectory, tempPart,
							folderStructure[i])
							+ "exists.")

					tempPart += "/"
					tempPart += folderStructure[i]

					i += 1

			except Exception as e:

				logging.exception("[%s]: Creating directory structure for "
					% self.fileName
					+ "'%s' failed."
					% fileLocation)

				return False

		return True


	# internal function that downloads the given file into the download
	# directory and checks if the given hash is correct
	#
	# return True or False
	def _downloadFile(self, fileLocation, fileHash, downloadDirectory):

		downloadDirectory += "/"

		# create sub directories (if needed)
		if (self._createSubDirectories(fileLocation, downloadDirectory)
			is False):

			logging.error("[%s]: Creating sub directories for '%s' failed."
				% (self.fileName, fileLocation))

			return False


		# create temporary file for download
		fileHandle = None
		try:

			# check if the file to download already exists
			if os.path.exists(downloadDirectory + fileLocation):

				raise ValueError("File '%s/%s' already exists."
					% (downloadDirectory, fileLocation))

			fileHandle = open(downloadDirectory + fileLocation, 'wb')

		except:

			logging.exception("[%s]: Creating file '%s/%s' failed."
				% (self.fileName, downloadDirectory, fileLocation))

			return False


		# download file from server
		conn = VerifiedHTTPSConnection(self.host, self.port, self.caFile)
		try:

			conn.request("GET", self.serverPath + "/"
				+ self.repoInstanceLocation + "/" + fileLocation)
			response = conn.getresponse()

			# check if server responded correctly
			# => download file
			if response.status == 200:

				while True:
					chunk = response.read(self.chunkSize)

					if not chunk:
						break

					fileHandle.write(chunk)
				fileHandle.close()

			else:
				raise ValueError("Server response code not 200 (was %d)."
					% response.status)

			conn.close()

		except Exception as e:
			logging.exception("[%s]: Downloading file '%s' from the "
				% (self.fileName, fileLocation)
				+ "server failed.")

			return False


		# calculate sha256 hash of the downloaded file
		fileHandle = open(downloadDirectory + fileLocation, 'r')
		sha256Hash = self._sha256File(fileHandle)
		fileHandle.close()

		# check if downloaded file has the correct hash
		if sha256Hash != fileHash:

			logging.error("[%s]: File '%s' does not have the correct hash."
				% (self.fileName, fileLocation))

			return False

		logging.debug("[%s]: Successfully downloaded file: '%s'"
			% (self.fileName, fileLocation))

		return True


	# internal function that calculates the sha256 hash of the file
	def _sha256File(self, fileHandle):
		fileHandle.seek(0)
		sha256 = hashlib.sha256()
		while True:
			data = fileHandle.read(128)
			if not data:
				break
			sha256.update(data)
		return sha256.hexdigest()


	# internal function that gets the newest version information from the
	# online repository
	#
	# return True or False
	def _getNewestVersionInformation(self):

		conn = VerifiedHTTPSConnection(self.host, self.port, self.caFile)

		# get repository information from the server
		repoInfoString = ""
		try:

			conn.request("GET", self.serverPath + "/repoInfo.json")
			response = conn.getresponse()

			# check if server responded correctly
			if response.status == 200:
				repoInfoString = response.read()

			else:
				raise ValueError("Server response code not 200 (was %d)."
					% response.status)

		except Exception as e:
			logging.exception("[%s]: Getting repository information failed."
				% self.fileName)

			return False


		# parse repository information string
		try:
			jsonData = json.loads(repoInfoString)

			if not isinstance(jsonData, dict):
				raise ValueError("Received repository information is "
					+ "not of type dict.")

			if not self.instance in jsonData["instances"].keys():
				raise ValueError("Instance '%s' is not managed by "
					% self.instance
					+ "used repository.")

			self.repoInstanceLocation = str(
				jsonData["instances"][self.instance])

		except Exception as e:
			logging.exception("[%s]: Parsing repository information failed."
				% self.fileName)

			return False


		# get version string from the server
		versionString = ""
		try:

			conn.request("GET", self.serverPath + "/"
				+ self.repoInstanceLocation + "/version.json")
			response = conn.getresponse()

			# check if server responded correctly
			if response.status == 200:
				versionString = response.read()

			else:
				raise ValueError("Server response code not 200 (was %d)."
					% response.status)

		except Exception as e:
			logging.exception("[%s]: Getting version information failed."
				% self.fileName)

			return False


		# parse version information string
		try:
			jsonData = json.loads(versionString)

			version = float(jsonData["version"])
			rev = int(jsonData["rev"])

			newestFiles = jsonData["files"]

			if not isinstance(newestFiles, dict):
				raise ValueError("Key 'files' is not of type dict.")

		except Exception as e:
			logging.exception("[%s]: Parsing version information failed."
				% self.fileName)

			return False

		logging.debug("[%s]: Newest version information: %.3f-%d."
			% (self.fileName, version, rev))

		# check if the version on the server is newer than the used one
		# => update information
		if (version > self.newestVersion or
			(rev > self.newestRev and version == self.newestVersion)):

			# update newest known version information
			self.newestVersion = version
			self.newestRev = rev
			self.newestFiles = newestFiles

		self.lastChecked = time.time()

		return True


	# function that gets the newest version information from the
	# online repository
	def getNewestVersionInformation(self):

		self._acquireLock()

		result = self._getNewestVersionInformation()

		self._releaseLock()

		return result


	# function that updates this instance of the alertR infrastructure
	def updateInstance(self):

		self._acquireLock()

		# check all files that have to be updated
		filesToUpdate = self._checkFilesToUpdate()

		if filesToUpdate is None:
			logging.error("[%s] Checking files for update failed."
				% self.fileName)

			self._releaseLock()

			return False

		if len(filesToUpdate) == 0:

			logging.info("[%s] No files have to be updated."
				% self.fileName)

			self._releaseLock()

			return True

		# check file permissions of the files that have to be updated
		if self._checkFilePermissions(filesToUpdate) is False:

			logging.info("[%s] Checking file permissions failed."
				% self.fileName)

			self._releaseLock()

			return False


		# create temp directory for the update process
		tempDir = tempfile.mkdtemp(prefix=self.instance)

		# download all files that have to be updated
		for fileToUpdate in filesToUpdate.keys():

			# only download file if it is new or has to be modified
			if (filesToUpdate[fileToUpdate] == _FileUpdateType.NEW
				or filesToUpdate[fileToUpdate] == _FileUpdateType.MODIFY):

				# download new files, if one file fails
				# => delete temp directory and abort update process
				if (self._downloadFile(fileToUpdate,
					self.newestFiles[fileToUpdate], tempDir) is False):

					logging.error("[%s]: Downloading files from the "
						% self.fileName
						+ "repository failed. Aborting update process.")

					shutil.rmtree(tempDir)

					self._releaseLock()

					return False

		# get the absolute location to this instance
		instanceLocation = os.path.dirname(os.path.abspath(__file__)) + "/../"

		for fileToUpdate in filesToUpdate.keys():

			# check if the file has to be deleted
			if filesToUpdate[fileToUpdate] == _FileUpdateType.DELETE:
				raise NotImplementedError("Not yet implemented.")

			# check if the file is new
			# => create all sub directories (if they are missing)
			elif filesToUpdate[fileToUpdate] == _FileUpdateType.NEW:
				self._createSubDirectories(fileToUpdate, instanceLocation)

			# copy file to correct location
			try:

				logging.debug("[%s]: Copying file '%s' to final destination."
					% (self.fileName, fileToUpdate))

				shutil.copyfile(tempDir + "/" + fileToUpdate,
					instanceLocation + "/" + fileToUpdate)
			except Exception as e:
				logging.exception("[%s]: Copying file '%s' failed."
				% (self.fileName, fileToUpdate))

				self._releaseLock()

				return False

			# check if the hash of the copied file is correct
			f = open(instanceLocation + "/" + fileToUpdate, 'r')
			sha256Hash = self._sha256File(f)
			f.close()
			if sha256Hash != self.newestFiles[fileToUpdate]:
				logging.error("[%s]: Hash of file '%s' is not correct "
				% (self.fileName, fileToUpdate)
				+ "after copying.")

				self._releaseLock()

				return False
		
		# delete temp directory before returning
		shutil.rmtree(tempDir)

		self._releaseLock()

		return True


		# TODO
		# creating a file and copying it can cause a possible race condition
		# better try using:
		# tempfile.mkstemp()
		# shutil.copyfileobj(fsrc, fdst[, length])