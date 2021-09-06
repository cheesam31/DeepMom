import os
import sys
from pathlib import Path

from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.lang import Builder

from time import sleep
from queue import Queue
from threading import Thread

import paho.mqtt.client as mqtt

from libs.baseclass.ConnectScreen import ConnectScreen
from libs.baseclass.DashboardScreen import DashboardScreen
from libs.baseclass.DeepMomRequestResponse import DeepMomResponse as DMRes
from libs.baseclass.DeepMomRequestResponse import DeepMomResponseState as DMRes_state
from libs.baseclass.DeepMomRequestResponse import DeepMomRequestState as DMReq_state

if getattr(sys, "frozen", False):  # bundle mode with PyInstaller
    os.environ["DeepMom_ROOT"] = sys._MEIPASS
else:
    os.environ["DeepMom_ROOT"] = str(Path(__file__).parent)

KV_DIR = f"{os.environ['DeepMom_ROOT']}/libs/kv/"

for kv_file in os.listdir(KV_DIR):
    with open(os.path.join(KV_DIR, kv_file), encoding="utf-8") as kv:
        Builder.load_string(kv.read())


class DeepMomApp(MDApp):
    def __init__(self, **kwargs):
        super(DeepMomApp, self).__init__()
        self._connect_screen_in_queue = Queue()
        self._connect_screen_out_queue = Queue()
        self._connect_screen = ConnectScreen(name="connect", in_queue=self._connect_screen_in_queue, out_queue=self._connect_screen_out_queue)
        self._dashboard_screen = DashboardScreen(name='dashboard')
        self._client = mqtt.Client()
        self._broker_connection_subscribe_flag = False
        self._connection_damon_thread = Thread(target=self.connection_damon)
        self._connection_damon_thread.daemon = True
        self._connect_req_thread = None
        self._user_cancel_count = 0
        self._scree_manager = ScreenManager()
        self._scree_manager.add_widget(self._connect_screen)
        self._scree_manager.add_widget(self._dashboard_screen)
        self._client.on_connect = self.on_connect
        self._client.on_subscribe = self.on_subscribe
        self.icon = 'asset/images/logo_128.png'

    def build(self):
        Window.size = (1200, 628)
        self._connection_damon_thread.start()
        self._scree_manager.current = 'connect'
        return self._scree_manager

    def connection_damon(self):
        while not self._broker_connection_subscribe_flag:
            if not self._connect_screen_out_queue.empty():
                requset = self._connect_screen_out_queue.get()
                if requset.request_state == DMReq_state.CONNECT_REQUEST:
                    self._connect_req_thread = Thread(target=self.connect_req, args=(requset.args,))
                    self._connect_req_thread.daemon = True
                    self._connect_req_thread.start()
                elif requset.request_state == DMReq_state.CANCEL_REQUEST:
                    self._user_cancel_count += 1
                    self._connect_screen_in_queue.put(DMRes(DMRes_state.CONNECT_CANCEL))
                    del self._connect_req_thread
                elif requset.request_state == DMReq_state.SUBSCRIBE_REQUEST:
                    self._client.subscribe(requset.args)
                    self._broker_connection_subscribe_flag = True
                    #del self._connect_req_thread
                else:
                    sleep(.1)
            else:
                sleep(.1)

    def connect_req(self, args):
        if (args['user_id'] is not None) and (args['user_passwd'] is not None):
            self._client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
            self._client.username_pw_set(username=args['user_id'], password=args['user_passwd'])
        try:
            self._client.loop_start()
            self._client.connect(args['broker_ip'], int(args['broker_port']), 60)
        except Exception as ex:
            if self._user_cancel_count:
                self._user_cancel_count -= 1
            else:
                self._connect_screen_in_queue.put(DMRes(DMRes_state.CONNECT_FAIL, ex))
            self._client.loop_stop()

    def on_connect(self, client, userdata, flags, rc):
        self._connect_screen_in_queue.put(DMRes(DMRes_state.CONNECT_OK))
        # self._mq_client.on_message = self.on_message

    def on_message(self, client, userdata, msg):
        pass
        # learn_curve = json.loads(msg.payload.decode('utf-8'))
        # print("{}/1000".format(self.plot_screen.epoch))

    def on_subscribe(self, client, userdata, mid, granted_qos):
        self._scree_manager.current = 'dashboard'


if __name__ == '__main__':
    DeepMomApp().run()
