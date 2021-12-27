import serial, serial.tools.list_ports
import time


def check_new_device(wait=10):
	ignor_list = serial.tools.list_ports.comports()
	current_port = None
	timeout = time.time()
	while not current_port:
		if time.time()-timeout >= wait:
			return None
		ports = serial.tools.list_ports.comports()
		for port in ports:
			if port not in ignor_list:
				return port.device


class COMDevice:
	def __init__(self, speed=9600):
		self.work_port = None
		self.speed = speed
		self.word = ''
		self.word_complete = False

	def connect(self, port):
		try:
			self.work_port = serial.Serial(port, self.speed)
		except Exception as e:
			print(e)

	def read_word(self):
		if self.word_complete:
			self.word = ''
			self.word_complete = False

		if data := self.read():
			data = data.decode('UTF-8')

			if data != '\r' and data != '\n':
				self.word += data
			elif data == '\n':
				self.word_complete = True
				return self.word


	def send(self, data):
		if self.work_port:
			self.work_port.write(data.encode())

	def read(self):
		if self.work_port:
			return self.work_port.read()