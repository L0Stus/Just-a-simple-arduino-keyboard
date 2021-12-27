from tkinter import *
from tkinter import ttk, messagebox
from threading import Thread
from os import mkdir
from os.path import exists
from pynput.keyboard import Key, Listener, Controller
import pyautogui
import connect, time

action_names = {
	'P': 'Нажата',
	'R': 'Отпущена'
}

actions = ['P', 'R']

controller = Controller()

all_keys_pressed = {}

def key_press(key):
	spec_keys = Key.__dict__['_member_map_']
	if f'{key}' in spec_keys:
		controller.press(spec_keys[key])
	else:
		controller.press(key)
	all_keys_pressed[key] = None

def key_release(key):
	spec_keys = Key.__dict__['_member_map_']
	if f'{key}' in spec_keys:
		controller.release(spec_keys[key])
	else:
		controller.release(key)
	if key in all_keys_pressed:
		del all_keys_pressed[key]

def key_comb(key_list):
	keys = key_list.split('+')
	for key in keys:
		key_press(key)
	for key in keys:
		key_release(key)

func_names = ['Нажать', 'Отпустить', 'Комбинация']

funcs = [key_press, key_release, key_comb]

class ButtonLabel:
	def __init__(self, parent, text, func, fg='blue'):
		self.label = Label(parent, text=text, fg=fg, font = 'SegoeUI 9 underline')
		self.ENABLED = False
		self.func = func
		self.label.bind('<Button-1>', self.call_func)
		self.label.bind('<Enter>', self._add_conf_hover)
		self.label.bind('<Leave>', self._add_conf_leave)

	def call_func(self, a):
		if self.ENABLED:
			self.func(a)

	def pack(self, *args, **kwargs):
		self.label.pack(*args, **kwargs)

	def enable(self):
		self.ENABLED = True
		self.label['font'] = 'SegoeUI 9 underline'
		self.label['state'] = 'normal'
		self.label['cursor'] = 'hand2'

	def disable(self):
		self.ENABLED = False
		self.label['state'] = 'disabled'
		self.label['cursor'] = ''

	def _add_conf_hover(self, action):
		if self.ENABLED:
			self.label['font'] = 'SegoeUI 9'

	def _add_conf_leave(self, action):
		if self.ENABLED:
			self.label['font'] = 'SegoeUI 9 underline'

class App(Tk):
	def __init__(self, name):
		Tk.__init__(self)
		self.name = name
		self.title(name)
		self.geometry('500x300')
		self.resizable(False, False)
		self.protocol("WM_DELETE_WINDOW", self.close)

		self.support_baudrates = [9600, 14400, 19200, 28800, 31250, 38400, 57600, 115200, 1000000, 2000000]
		self.set_speed = IntVar()
		self.set_speed.set(len(self.support_baudrates)-2)

		self.menu = Menu(self)
		self.config(menu=self.menu)
		self.menu.add_cascade(label='Подключить', command=self.connect_thread)

		baudrate = Menu(self.menu, tearoff=0)
		for i, speed in enumerate(self.support_baudrates):
			baudrate.add_radiobutton(label=speed, value=i, variable=self.set_speed, command=self.update_speed)

		self.menu.add_cascade(label='Скорость', menu=baudrate, underline=False)
		self.menu.add_cascade(label='О приложении', command=self.about)

		self.mainframe = Frame(self)
		self.mainframe.pack(fill=BOTH, padx=5, pady=5)

		self.status_title = StringVar()
		self.status_title.set('Устройство не подключено')
		self.status_label = Label(self, textvariable=self.status_title, bd=1, bg='white', fg='#222222', anchor=W, padx=5)
		self.status_label.pack(side=BOTTOM, fill=X)

		columns = ('#1', '#2')
		self.treeview = ttk.Treeview(self.mainframe, style='Treeview', show='headings', columns=columns)
		self.treeview.column('#1', anchor=CENTER)
		self.treeview.column('#2', anchor=CENTER)
		self.treeview.heading('#1', text='Кнопка контроллера')
		self.treeview.heading('#2', text='Действие')

		ysb = ttk.Scrollbar(self.mainframe, orient=VERTICAL, command=self.treeview.yview)
		self.treeview.configure(yscrollcommand=ysb.set)
		ysb.pack(side=RIGHT, fill=Y)
		self.treeview.pack(fill=BOTH)
		self.treeview.bind('<<TreeviewSelect>>', self.selected)

		self.bottom_frame = Frame(self)
		self.bottom_frame.pack(fill=BOTH, padx=10, pady=5)

		self.add_config_button = ButtonLabel(self.bottom_frame, text='Добавить', func=self.add_config_window)
		self.add_config_button.pack(side=LEFT, anchor=W)
		self.add_config_button.disable()

		self.is_active = BooleanVar()
		self.active = Checkbutton(self.bottom_frame, text='Обработка клавиш', var=self.is_active, state='disabled', command=self.check_active)
		self.active.pack(side=RIGHT, anchor=W)

		self.clear_all_button = ButtonLabel(self.bottom_frame, text='Очистить всё', func=self.clear_all)
		self.clear_all_button.pack(side=LEFT, padx=10)
		self.clear_all_button.disable()

		self.current_action = None
		self.timeout = 10
		self.WAIT = False

		self.device = None
		self.d_port = None
		self.d_name = None
		self.baud_speed = None
		self.update_speed()
		self.ignor_list = []
		self.CONNECTED = False

		self.PATH = 'C:/devices/'
		if not exists(self.PATH): mkdir(self.PATH)
		self.conf_path = None
		self.configs = {}

	def release_all_keys(self):
		for key in all_keys_pressed:
			key_release(key)

	def close(self):
		self.release_all_keys()
		self.destroy()

	def clear_all(self, a):
		confirm = messagebox.askyesno(title='Очистить всё', message=f'Очистить все настойки для контроллреа "{self.d_name}"?')
		if confirm:
			self.configs.clear()
			print(self.configs)
			self.save_configs_to_file()
			self.redraw_treeview()

	def get_selected(self):
		selection = self.treeview.selection()
		index = self.treeview.item(selection)['text']
		return index

	def selected(self, a):
		if not self.is_active.get():
			index = self.get_selected()
			keys_list = [x for x in self.configs]
			action_type = keys_list[index]
			func = self.configs[action_type]['func']
			f_args = self.configs[action_type]['args']
			self.add_config_window(action=None, call_type='Edit', action_type=action_type, func=func, f_args=f_args)

	def check_active(self):
		if self.is_active.get():
			self.add_config_button.disable()
			self.clear_all_button.disable()
		else:
			if self.CONNECTED:
				self.add_config_button.enable()
				self.clear_all_button.enable()

	def get_action_name(self, action):
		try:
			name = f'{action_names[action[:1]]} {action[1:]}'
		except:
			name = action
		return name

	def add_config_window(self, action, call_type='New', action_type=None, func=None, f_args=None):
		if self.CONNECTED:
			self.key_action = None
			action_names_list = list(action_names)
			entry_default = StringVar()
			if self.current_action:
				self.key_action = self.current_action

			def close():
				self.add_config_button.enable()
				self.clear_all_button.enable()
				self.active['state'] = 'normal'
				self.listener.stop()
				window.destroy()

			def unfocus(a):
				window.focus()

			def key_pressed(key):
				def key_name(key):
					key = str(key)
					if '.' in key:
						return key[key.index('.')+1:]
					else:
						return key[1:-1]
						
				if func_variants.current() == 2:
					if len(self.key_press) < 60:
						self.key_press.append(key_name(key))
					keys_press_title.set('+'.join([str(x).split('.')[-1] for x in self.key_press]))
				else:
					self.key_press = [key_name(key)]
					keys_press_title.set(str(self.key_press[-1]).split('.')[-1])

			def keys_listen():
				with Listener(on_press=None, on_release=key_pressed) as self.listener:
					self.listener.join()

			def variant_clear(a):
				self.key_press = []
				keys_press_title.set('Клавиши не выбраны')

			def set_action(a):
				self.key_action = actions[action_variants.current()]

			def save():
				if button_id.get() and keys_press_title.get() != 'Клавиши не выбраны':
					if call_type == 'New':
						self.add_config(f'{actions[action_variants.current()]}{button_id.get()}', func_variants.current(), '+'.join(self.key_press))
						if func_variants.current() == 0:
							self.add_config(f'{actions[1]}{button_id.get()}', 1, '+'.join(self.key_press))
					else:
						self.edit_config(f'{actions[action_variants.current()]}{button_id.get()}', func_variants.current(), '+'.join(self.key_press))
					self.redraw_treeview()
					close()
				else:
					messagebox.showwarning(title='Настройки', message='Необходимо заполнить все поля')

			def setting_del():
				index = self.get_selected()
				keys_list = [x for x in self.configs]
				action_type = keys_list[index]
				self.del_config(action_type)
				self.redraw_treeview()
				close()

			window = Toplevel()
			if call_type == 'New':
				window.title('Добавление настроек')
			else:
				window.title('Редактирование настроек')
			window.geometry('400x230')
			window.grab_set()
			self.active['state'] = 'disabled'
			unfocus(None)
			window.protocol("WM_DELETE_WINDOW", close)
			self.add_config_button.disable()
			self.clear_all_button.disable()

			frame_action = LabelFrame(window, text='Действие на контроллере:', fg='#555555', padx=3, pady=9)
			frame_action.pack(fill=BOTH, side=TOP, padx=3, pady=6)

			action_variants = ttk.Combobox(frame_action, state='readonly')
			action_variants['values'] = tuple(action_names.values())
			action_variants.current(0)
			action_variants.pack(side=LEFT)
			action_variants.bind("<<ComboboxSelected>>", set_action)

			button_id = Entry(frame_action, textvariable=entry_default, width=10)
			button_id.pack(side=RIGHT)
			button_id.bind('<Return>', unfocus)
			Label(frame_action, text='ID кнопки:').pack(side=RIGHT)

			if self.key_action:
				action_variants.current(action_names_list.index(self.key_action[:1]))
				entry_default.set(self.key_action[1:])

			if action_type:
				action_variants.current(action_names_list.index(action_type[:1]))
				entry_default.set(action_type[1:])

			frame_func = LabelFrame(window, text='Выполнить действие:', fg='#555555', padx=3, pady=6)
			frame_func.pack(fill=BOTH, side=TOP, padx=3, pady=3)

			ff_top = Frame(frame_func)
			ff_bottom = Frame(frame_func)
			ff_top.pack(fill=BOTH)
			ff_bottom.pack(fill=BOTH)

			func_variants = ttk.Combobox(ff_top, state='readonly')
			func_variants['values'] = ('Нажать клавишу', 'Отпустить клавишу', 'Комбинация клавиш')
			func_variants.current(0)
			func_variants.pack(side=LEFT)
			func_variants.bind("<<ComboboxSelected>>", variant_clear)

			self.key_press = []
			keys_press_title = StringVar()
			keys_press_title.set('Клавиши не выбраны')
			Label(ff_top, textvariable=keys_press_title).pack(side=RIGHT)

			if func:
				func_variants.current(func)
			if f_args:
				keys_press_title.set(f_args)

			clearb = ButtonLabel(ff_bottom, text='Очистить', func=variant_clear)
			clearb.pack(side=BOTTOM, anchor=NE)
			clearb.enable()

			frame_save = Frame(window)
			frame_save.pack(fill=BOTH, padx=3, pady=3)

			help_label = Label(frame_save, text='Подсказка: Нажмите на клавиши,\nкоторые хотите назначить', fg='#555555', justify=LEFT)
			help_label.pack(side=LEFT, pady=1)

			if call_type != 'New':
				Button(frame_save, text='Удалить', command=setting_del).pack(side=RIGHT, pady=5, padx=1)

			button_save = Button(frame_save, text='Сохранить', command=save)
			button_save.pack(side=RIGHT, pady=5, padx=1)

			thread = Thread(target=keys_listen, daemon=True)
			thread.start()

	def update_speed(self):
		self.baud_speed = self.support_baudrates[self.set_speed.get()]

	def wait_device(self):
		self.WAIT = True
		self.status_title.set('Ожидание подключения устройства')
		self.menu.entryconfigure(1, label='Ожидание')
		port = connect.check_new_device(self.timeout)
		if port:
			self.d_port = port
			self.device = connect.COMDevice(self.baud_speed)
			time.sleep(0.1)
			self.device.connect(self.d_port)
			self.status_title.set(f'Устройство подключено к порту {self.d_port}')
			return True
		else:
			messagebox.showwarning(title='Таймаут соединения', message='Вышло время ожидания подключения контроллера. Попробуйте переподключить устройство.')
			self.status_title.set(f'Не удалось подключить устройство')
			return False

	def connect_device(self):
		if self.wait_device():
			self.WAIT = False
			timeout = time.time()
			result = None
			while result is None:
				if time.time()-timeout >= self.timeout:
					messagebox.showwarning(title='Таймаут соединения', message='Вышло время ожидания идентификатора контроллера. Проверьте правильноть программы контроллера.')
					result = False
				else:
					try:
						data = self.device.read_word()
						if data:
							if data[:1] == 'C':
								self.d_name = data[1:]
								self.device.send('1')
								self.status_title.set(f'Контроллер "{self.d_name}" готов к работе')
								self.CONNECTED = True
								self.conf_path = self.PATH+self.d_name+'.conf'
								self.add_config_button.enable()
								self.clear_all_button.enable()
								self.get_configs_from_file()
								self.redraw_treeview()
								self.menu.entryconfigure(1, label='✓ Подключено')
								self.title(f'Контроллер {self.d_name}')
								self.active['state'] = 'normal'
								self.start_thread(self.update)
								result = True
					except:
						messagebox.showerror(title='Проблема чтения с устройства', message='Проблема чтения информации, присылаемой котроллером.')
			return result
		else:
			self.WAIT = False
			self.menu.entryconfigure(1, label='Подключить')

	def connect_thread(self):
		if not self.CONNECTED:
			if self.WAIT is False:
				self.start_thread(self.connect_device)
			else:
				self.status_title.set('Устройство уже ожидается')
		else:
			self.status_title.set(f'Устройство уже подключено')
		
	def check_config_file(self):
		if exists(self.conf_path):
			return True
		else:
			return False

	def get_configs_from_file(self):
		if self.check_config_file():
			with open(self.conf_path, 'r') as config:
				conf_data = str(config.read())
			if conf_data:
				for string in conf_data.split(';\n'):
					try:
						if string:
							dev_action, react_type, react_data = string.split(',')
							self.configs[dev_action] = {'func':react_type, 'args':react_data}
					except:
						self.status_title.set('Возникли ошибки при импорте настроек')
		else:
			self.status_title.set('Контроллер не настроен')

	def save_configs_to_file(self):
		try:
			with open(self.conf_path, 'w') as config:
				for action in self.configs:
					string = f"{action},{self.configs[action]['func']},{self.configs[action]['args']};\n"
					config.write(string)
			self.status_title.set('Настройки сохранены')
		except:
			self.status_title.set('Ошибка при сохранении настроек')

	def add_config(self, action, func, args):
		rewrite = True
		if action in self.configs:
			confirm = messagebox.askyesno(title='Переназначить настройки?', message=f'Для события "{self.get_action_name(action)[:17]}" уже есть настройки, хотите их изменить на "{func_names[int(self.configs[action]["func"])]} {self.configs[action]["args"]}"?')
			if confirm == False:
				rewrite = False
		if rewrite is True:
			self.configs[action] = {'func':func, 'args':args}
			self.save_configs_to_file()
			self.status_title.set('Настройки сохранены')

	def edit_config(self, action, func, args):
		self.configs[action] = {'func':func, 'args':args}
		self.save_configs_to_file()
		self.status_title.set('Настройки сохранены')

	def del_config(self, action):
		if action in self.configs:
			del self.configs[action]
			self.status_title.set('Настройки удалены')
			self.save_configs_to_file()

	def redraw_treeview(self):
		self.treeview.delete(*self.treeview.get_children()) 

		if self.configs:
			for i, action in enumerate(self.configs):
				self.treeview.insert('', i+1, text=i, values=(self.get_action_name(action)[:17], f'{func_names[int(self.configs[action]["func"])]} \"{self.configs[action]["args"]}\"'))
		else:
			self.treeview.insert('', END, text='12', values=('-', '-'), tags=('add',))

	def update(self):
		quit = False
		while not quit:
			try:
				self.current_action = self.device.read_word()
				if self.current_action:
					if self.current_action in self.configs:
						if self.is_active.get():
							funcs[int(self.configs[self.current_action]['func'])](self.configs[self.current_action]['args'])
					self.status_title.set(self.get_action_name(self.current_action))
			except:
				self.status_title.set('Устройство отключено')
				self.CONNECTED = False
				self.add_config_button.disable()
				self.clear_all_button.disable()
				self.release_all_keys()
				self.active['state'] = 'disabled'
				self.title(self.name)
				self.treeview.delete(*self.treeview.get_children())
				self.menu.entryconfigure(1, label='Подключить', foreground='black')
				quit = True

	def start_thread(self, f):
		self.thread = Thread(target=f, daemon=True)
		self.thread.start()

	def about(self):
		messagebox.showinfo(title='О приложении', message='Nano USB Controller\nАвтор: Kobozev Timofey\nДля проекта "Клавиатура кодера"')
