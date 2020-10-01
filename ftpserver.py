# commands
#   LIST <path>, information of a directory or file,
#   	or information of current remote directory if not specified
#   RETR <file_name>, download file from current remote directory
#	QUIT, quit connection
#	PWD, get current remote directory
#   CDUP, change to parent remote directory
#   CWD <path>, change current remote directory
#   MKD, make a directory in remote server
#   RMD <dir_name>, remove a directory in remote server
#   DELE <file_name>, delete a file in remote server 

import socket
import os
import sys
import threading
import time
import logging
import json

class FTPThreadServer(threading.Thread):
	def __init__(self, (client, client_address), local_ip, data_port):
		self.client = client
		self.client_address = client_address
		self.cwd = os.getcwd()
		self.data_address = (local_ip, data_port)
		self.current_user = None

		threading.Thread.__init__(self)

	def start_datasock(self):
		try:
			print 'Creating data socket on' + str(self.data_address) + '...'
			logger.info('Creating data socket on' + str(self.data_address) + '...')
			
			# create TCP for data socket
			self.datasock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.datasock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

			self.datasock.bind(self.data_address)
			self.datasock.listen(5)
			
			print 'Data socket is started. Listening to' + str(self.data_address) + '...'
			logger.info('Data socket is started. Listening to' + str(self.data_address) + '...')
			self.client.send('125 Data connection already open; transfer starting.\r\n')

			return self.datasock.accept()
		except Exception, e:
			print 'ERROR: test ' + str(self.client_address) + ': ' + str(e)
			logger.error(' test ' + str(self.client_address) + ': ' + str(e))
			self.close_datasock()
			self.client.send('425 Cannot open data connection.\r\n')
			
	def close_datasock(self):
		print 'Closing data socket connection...'
		logger.info('Closing data socket connection...')
		try:
			self.datasock.close()
		except:
			pass

	def run(self):
		try :
			print 'client connected: ' + str(self.client_address) + '\n'
			logger.info('client connected: ' + str(self.client_address) + '\n')

			while True:
				cmd = self.client.recv(1024)
				if not cmd: break
				print 'commands from ' + str(self.client_address) + ': ' + cmd
				logger.info('commands from ' + str(self.client_address) + ': ' + cmd)
				try:
					if self.current_user == None:
						if not(cmd[:4] == 'HELP' or cmd[:4] == "USER" or cmd[:4] == "PASS"):
							self.client.send('332 Need account for login.')
							continue
					func = getattr(self, cmd[:4].strip().upper())
					func(cmd)
				except AttributeError, e:
					print 'ERROR: ' + str(self.client_address) + ': Invalid Command.'
					logger.error(' ' + str(self.client_address) + ': Invalid Command.')
					self.client.send('550 Invalid Command\r\n')
		except Exception, e:
			print 'ERROR: ' + str(self.client_address) + ': ' + str(e)
			logger.error(' ' + str(self.client_address) + ': ' + str(e))
			self.QUIT('')

	def HELP(self, cmd):
		help_text = "214\nUser [name], Its argument is used to specify the user's string. It is used for user authentication."
		self.client.send(str(help_text))

	def USER(self, cmd):
		username = cmd[4:].strip()

		with open('config.json') as json_file:
		    data = json.load(json_file)

		flag = False
		for user in data['users']:
			if user['user'] == username:
				self.current_user = username
				self.client.send('331 User name okay, need password.\r\n')
				flag = True
				break
		
		if flag == False:
			self.client.send('430 Invalid username or password.\r\n')

	def PASS(self, cmd):
		password = cmd[4:].strip()

		if(self.current_user == None):
			self.client.send('503 Bad sequence of command.\r\n')
		else:
			with open('config.json') as json_file:
			    data = json.load(json_file)

			flag = False
			for user in data['users']:
				if user['user'] == self.current_user:
					if user['password'] == password:
						self.client.send('230 User logged in, proceed.\r\n')
						flag = True
						break
			
			if flag == False:
				self.client.send('430 Invalid username or password.\r\n')

	def QUIT(self, cmd):
		try:
			self.client.send('221 Successful Quit.\r\n')
		except:
			pass
		finally:
			print 'Closing connection from ' + str(self.client_address) + '...'
			logger.info('Closing connection from ' + str(self.client_address) + '...')
			self.close_datasock()
			self.client.close()
			quit()

	def LIST(self, cmd):
		print 'LIST', self.cwd
		logger.info('LIST', self.cwd)
		(client_data, client_address) = self.start_datasock()

		try:
			listdir = os.listdir(self.cwd)
			if not len(listdir):
				max_length = 0
			else:
				max_length = len(max(listdir, key=len))

			header = '| %*s | %9s | %12s | %20s | %11s | %12s |' % (max_length, 'Name', 'Filetype', 'Filesize', 'Last Modified', 'Permission', 'User/Group')
			table = '%s\n%s\n%s\n' % ('-' * len(header), header, '-' * len(header))
			client_data.send(table)
			
			for i in listdir:
				path = os.path.join(self.cwd, i)
				stat = os.stat(path)
				data = '| %*s | %9s | %12s | %20s | %11s | %12s |\n' % (max_length, i, 'Directory' if os.path.isdir(path) else 'File', str(stat.st_size) + 'B', time.strftime('%b %d, %Y %H:%M', time.localtime(stat.st_mtime))
					, oct(stat.st_mode)[-4:], str(stat.st_uid) + '/' + str(stat.st_gid)) 
				client_data.send(data)
			
			table = '%s\n' % ('-' * len(header))
			client_data.send(table)
			
			self.client.send('226 List transfer done.\r\n')
		except Exception, e:
			print 'ERROR: ' + str(self.client_address) + ': ' + str(e)
			logger.error(' ' + str(self.client_address) + ': ' + str(e))
			self.client.send('426 Connection closed; transfer aborted.\r\n')
		finally: 
			client_data.close()
			self.close_datasock()

	def PWD(self, cmd):
		self.client.send('257 \"%s\".\r\n' % self.cwd)

	def CWD(self, cmd):
		dest = os.path.join(self.cwd, cmd[4:].strip())
		if (os.path.isdir(dest)):
			self.cwd = dest
			self.client.send('250 Successful Change.\r\n')
		else:
			print 'ERROR: ' + str(self.client_address) + ': No such file or directory.'
			logger.error(' ' + str(self.client_address) + ': No such file or directory.')
			self.client.send('550 \"' + dest + '\": No such file or directory.\r\n')

	def CDUP(self, cmd):
		dest = os.path.abspath(os.path.join(self.cwd, '..'))
		if (os.path.isdir(dest)):
			self.cwd = dest
			self.client.send('250 OK \"%s\".\r\n' % self.cwd)
		else:
			print 'ERROR: ' + str(self.client_address) + ': No such file or directory.'
			self.client.send('550 \"' + dest + '\": No such file or directory.\r\n')		

	def MKD(self, cmd):
		path = cmd[4:].strip()
		dirname = os.path.join(self.cwd, path)
		try:
			if not path:
				self.client.send('501 Syntax error in parameters or arguments.\r\n')
			else:
				os.mkdir(dirname)
				self.client.send('250 ' + dirname + 'created.' + '.\r\n')
		except Exception, e:
			print 'ERROR: ' + str(self.client_address) + ': ' + str(e)
			logger.error(' ' + str(self.client_address) + ': ' + str(e))
			self.client.send('550 Failed to create directory ' + dirname + '.')

	def RMD(self, cmd):
		path = cmd[4:].strip()
		dirname = os.path.join(self.cwd, path)
		try:
			if not path:
				self.client.send('501 Syntax error in parameters or arguments.\r\n')
			else:
				os.rmdir(dirname)
				self.client.send('250 ' + dirname + 'deleted.' + '.\r\n')
		except Exception, e:
			print 'ERROR: ' + str(self.client_address) + ': ' + str(e)
			logger.error(' ' + str(self.client_address) + ': ' + str(e))
			self.client.send('550 Failed to delete directory ' + dirname + '.')
			
	def DELE(self, cmd):
		path = cmd[4:].strip()
		filename = os.path.join(self.cwd, path)
		try:
			if not path:
				self.client.send('501 Syntax error in parameters or arguments.\r\n')
			else:
				os.remove(filename)
				self.client.send('250 File deleted: ' + filename + '.\r\n')
		except Exception, e:
			print 'ERROR: ' + str(self.client_address) + ': ' + str(e)
			self.client.send('550 Failed to delete file ' + filename + '.')
		
	def RETR(self, cmd):
		path = cmd[4:].strip()
		if not path:
			self.client.send('501 Syntax error in parameters or arguments.\r\n')
			return

		fname = os.path.join(self.cwd, path)
		(client_data, client_address) = self.start_datasock()
		if not os.path.isfile(fname):
			self.client.send('550 File not found.\r\n')
		else:
			try:
				file_read = open(fname, "r")
				data = file_read.read(1024)

				while data:
					client_data.send(data)
					data = file_read.read(1024)

				self.client.send('226 Successful Download.\r\n')
			except Exception, e:
				print 'ERROR: ' + str(self.client_address) + ': ' + str(e)
				logger.error(' ' + str(self.client_address) + ': ' + str(e))
				self.client.send('426 Connection closed; transfer aborted.\r\n')
			finally:
				client_data.close()
				self.close_datasock()
				file_read.close()

class FTPserver:
	def __init__(self, port, data_port):
		# server address at localhost
		self.address = '0.0.0.0'

		self.port = int(port)
		self.data_port = int(data_port)

	def start_sock(self):
		# create TCP socket
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		server_address = (self.address, self.port)

		try:
			print 'Creating data socket on', self.address, ':', self.port, '...'
			logger.info('Creating data socket on', self.address, ':', self.port, '...')
			self.sock.bind(server_address)
			self.sock.listen(5)
			print 'Server is up. Listening to', self.address, ':', self.port
			logger.info('Server is up. Listening to', self.address, ':', self.port)
		except Exception, e:
			print 'Failed to create server on', self.address, ':', self.port, 'because', str(e.strerror)
			logger.info('Failed to create server on', self.address, ':', self.port, 'because', str(e.strerror))
			quit()

	def start(self):
		self.start_sock()

		try:
			while True:
				print 'Waiting for a connection'
				logger.info('Waiting for a connection')
				thread = FTPThreadServer(self.sock.accept(), self.address, self.data_port)
				thread.daemon = True
				thread.start()
		except KeyboardInterrupt:
			print 'Closing socket connection'
			logger.info('Closing socket connection')
			self.sock.close()
			quit()


# Main
logger = logging.getLogger('myapp')
hdlr = logging.FileHandler('myapp.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 
logger.setLevel(logging.DEBUG)

port = raw_input("Port - if left empty, default port is 10021: ")
if not port:
	port = 10021

data_port = raw_input("Data port - if left empty, default port is 10020: ")
if not data_port:
	data_port = 10020

server = FTPserver(port, data_port)
server.start()
