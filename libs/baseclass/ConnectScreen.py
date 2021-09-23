from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDFillRoundFlatButton
from kivy.animation import Animation
from kivy.uix.screenmanager import Screen
from kivymd.uix.behaviors import RoundedRectangularElevationBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.clock import Clock
from kivy import utils
from threading import Thread
from time import sleep

from .DeepMomRequestResponse import DeepMomResponseState as DMRes_state
from .DeepMomRequestResponse import DeepMomRequest as DMReq
from .DeepMomRequestResponse import DeepMomRequestState as DMReq_state


class ConnectScreen(Screen):
    def __init__(self, in_queue, out_queue, **kwargs):
        super(ConnectScreen, self).__init__(**kwargs)
        self._in_queue = in_queue
        self._out_queue = out_queue
        self._button_press = False
        self._broker_ip = 'localhost'
        self._broker_port = 1883
        self._user_id = None
        self._user_passwd = None
        self.dialog = MDDialog(buttons=[MDFlatButton(text='OK', on_release=self.dialog_dismiss, text_color=utils.get_color_from_hex('#FFFFFFFF'))])
        self._thread = Thread(target=self.thread_work)
        self._thread_terminate = False
        self._thread.daemon = True
        self._thread.start()

    def connect_press(self):
        self.ids.using_account_check_box.unselected_color = utils.get_color_from_hex('#607D8B')
        if self.ids.using_account_check_box.active:
            if not len(self.ids.user_id.text) or not len(self.ids.user_passwd.text):
                self.dialog.text = 'Enter your user ID or password'
                self.dialog.open()
                return
            else:
                self._user_id = self.ids.user_id.text
                self._user_passwd = self.ids.user_passwd.text
                self._broker_ip = self.ids.broker_ip.text if len(self.ids.broker_ip.text) else 'localhost'
                self._broker_port = self.ids.broker_port.text if len(self.ids.broker_port.text) else 1883
        else:
            self._user_id = None
            self._user_passwd = None
            self._broker_ip = self.ids.broker_ip.text if len(self.ids.broker_ip.text) else 'localhost'
            self._broker_port = self.ids.broker_port.text if len(self.ids.broker_port.text) else 1883

        connect_req_arg = {'broker_ip': self._broker_ip, 'broker_port': self._broker_port,
                           'user_id': self._user_id, 'user_passwd': self._user_passwd}

        self._button_press = not self._button_press

        if self._button_press:
            self._out_queue.put(DMReq(DMReq_state.CONNECT_REQUEST, connect_req_arg))
            self.ids.spinner.active = True
            self.ids.user_id.disabled = True
            self.ids.user_passwd.disabled = True
            self.ids.broker_ip.disabled = True
            self.ids.broker_port.disabled = True
            self.ids.using_account_check_box.disabled = True
            self.ids.connect_button.text = 'Cancel'

        else:
            self._out_queue.put(DMReq(DMReq_state.CANCEL_REQUEST))
            self.ids.spinner.active = False
            self.ids.user_id.disabled = False
            self.ids.user_passwd.disabled = False
            self.ids.broker_ip.disabled = False
            self.ids.broker_port.disabled = False
            self.ids.using_account_check_box.disabled = False
            self.ids.connect_button.text = 'Connect'

    def check_press(self):
        self.ids.using_account_check_box.unselected_color = utils.get_color_from_hex('#607D8B')
        if self.ids.using_account_check_box.active:
            animate = Animation(pos_hint={'center_x': .5, 'center_y': .5}, duration=.2)
            animate.start(self.ids.option_text_field_2)
            animate = Animation(size=(0, 450), duration=.2)
            animate += Animation(size=(400, 450), duration=.2)
            animate.start(self.ids.option_text_field_1)
            self.ids.user_id.disabled = False
            self.ids.user_passwd.disabled = False
            self.ids.user_id.hint_text = 'Enter Your ID'
            self.ids.user_passwd.hint_text = 'Enter Your Password'
        else:
            self.ids.user_id.disabled = True
            self.ids.user_passwd.disabled = True
            self.ids.user_id.text = ''
            self.ids.user_passwd.text = ''
            self.ids.user_id.hint_text = ''
            self.ids.user_passwd.hint_text = ''
            animate = Animation(size=(0, 0), duration=.2)
            animate.start(self.ids.option_text_field_1)
            animate = Animation(pos_hint={'center_x': .5, 'center_y': .65}, duration=.2)
            animate.start(self.ids.option_text_field_2)
            self.ids.spinner.active = False

    def subscribe_press(self, args):
        try:
            int(self.ids.epoch.text)
            if not len(self.ids.mqtt_topic.text):
                self.dialog.text = 'Enter Your MQTT Topic'
                self.dialog.open()
            elif not len(self.ids.epoch.text):
                self.dialog.text = 'Enter Epochs'
                self.dialog.open()
            else:
                self._out_queue.put(DMReq(DMReq_state.SUBSCRIBE_REQUEST, [self.ids.mqtt_topic.text, self.ids.epoch.text]))
        except ValueError:
            self.dialog.text = 'Epoch is must be integer'
            self.dialog.open()

    def thread_work(self):
        while not self._thread_terminate:
            if not self._in_queue.empty():
                response = self._in_queue.get()

                self._button_press = False
                self.ids.spinner.active = False
                self.ids.using_account_check_box.disabled = False
                self.ids.connect_button.text = 'Connect'

                if response.response_state == DMRes_state.CONNECT_OK:
                    self._thread_terminate = True

                    animate = Animation(size=(630, 300), duration=.3)
                    animate.start(self.ids.base_Float)

                    self.ids.option_text_field_1.remove_widget(self.ids.user_id)
                    self.ids.option_text_field_1.remove_widget(self.ids.user_passwd)

                    self.ids.option_text_field_2.remove_widget(self.ids.broker_ip)
                    self.ids.option_text_field_2.remove_widget(self.ids.broker_port)
                    self.ids.option_text_field_2.remove_widget(self.ids.connect_button)
                    self.ids.option_text_field_2.remove_widget(self.ids.using_account_check_box)
                    self.ids.option_text_field_2.remove_widget(self.ids.explain_label)

                    _btn = MDFillRoundFlatButton(text='Subscribe', font_size=16, pos_hint={'center_x': .5, 'center_y': .15}, size_hint_x=.4,
                                                 theme_text_color='Custom', text_color=utils.get_color_from_hex('#26283A'),
                                                 on_release=self.subscribe_press)

                    self.ids.base_Float.add_widget(_btn)
                    animate = Animation(size=(630, 270), duration=.3)
                    animate.start(self.ids.mqtt_topic_wrapper)
                    self.ids.mqtt_topic.disabled = False
                    self.ids.epoch.disabled = False
                    self.ids.mqtt_topic.hint_text = 'Enter your MQTT Topic'
                    self.ids.mqtt_topic.focus = True
                    self.ids.epoch.hint_text = 'Enter Epochs'
                elif response.response_state == DMRes_state.CONNECT_CANCEL:
                    print('CONNECTION REQUEST CANCEL')
                    pass
                elif response.response_state == DMRes_state.CONNECT_FAIL:
                    self.dialog.text = '[font=./assets/fonts/tway_air.ttf]' + str(response.error_log) + '[/font]'
                    self.dialog.open()
                    self.ids.using_account_check_box.unselected_color = utils.get_color_from_hex('#607D8B')
                    self.ids.spinner.active = False
                    self.ids.user_id.disabled = False
                    self.ids.user_passwd.disabled = False
                    self.ids.broker_ip.disabled = False
                    self.ids.broker_port.disabled = False
                    self.ids.using_account_check_box.disabled = False
                    self.ids.connect_button.text = 'Connect'
                    pass
                else:
                    raise ValueError
            else:
                sleep(.1)

    def dialog_dismiss(self, arg):
        self.dialog.dismiss()
        self.ids.using_account_check_box.unselected_color = utils.get_color_from_hex('#607D8B')


