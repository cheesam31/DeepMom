import os
import sys
from pathlib import Path

from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.lang import Builder

from datetime import datetime
from datetime import timedelta
from time import sleep
from queue import Queue
from threading import Thread
import json

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
        self._client.on_message = self.on_message
        self.check_validation = False
        self._using_validation = True
        self.finish_flag = False
        self.previous_time = timedelta(seconds=0)
        self.ETA_time = timedelta(seconds=0)
        self._info_dict = {"max_acc": 0, "min_loss": 0, "max_val_acc": 0, "min_val_loss": 0}
        self._learn_curve_parameter = {"accuracy": self._dashboard_screen.hover_graph.accuracy_plot,
                                       "loss": self._dashboard_screen.hover_graph.loss_plot,
                                       "val_accuracy": self._dashboard_screen.hover_graph.val_accuracy_plot,
                                       "val_loss": self._dashboard_screen.hover_graph.val_loss_plot}

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
                    self._client.subscribe(requset.args[0])
                    self._dashboard_screen.hover_graph.graph.xmax = int(requset.args[1])
                    self._dashboard_screen.hover_graph.graph.x_ticks_major = int(requset.args[1]) / 10
                    self._dashboard_screen.hover_graph.epoch = int(requset.args[1])
                    self._dashboard_screen.ids.progress_epochs.text = "0 / {} Epochs".format(requset.args[1])
                    self._scree_manager.current = 'dashboard'
                    self._broker_connection_subscribe_flag = True
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

    def on_message(self, client, userdata, msg):
        learn_curve = json.loads(msg.payload.decode('utf-8'))
        time_freq = datetime.now() - self.previous_time
        self.previous_time = datetime.now()

        if not self.check_validation:
            time_freq = timedelta(0)
            self._dashboard_screen.ids.remain_time.text = 'Calc...'
            if not ("val_accuracy" in learn_curve and "val_loss" in learn_curve):
                self._dashboard_screen.hover_graph.not_validation()
                self._using_validation = False
                self._learn_curve_parameter.clear()
                self._learn_curve_parameter = {"accuracy": self._dashboard_screen.hover_graph.accuracy_plot,
                                               "loss": self._dashboard_screen.hover_graph.loss_plot}
            else:
                self._info_dict["max_val_acc"] = learn_curve["val_accuracy"]
                self._info_dict["min_val_loss"] = learn_curve["val_loss"]
                self._dashboard_screen.ids.max_val_acc.text = str(round(learn_curve["val_accuracy"], 4))
                self._dashboard_screen.ids.min_val_loss.text = str(round(learn_curve["val_loss"], 4))
                self._using_validation = True

            self._info_dict["max_acc"] = learn_curve["accuracy"]
            self._info_dict["min_loss"] = learn_curve["loss"]
            self._dashboard_screen.ids.max_acc.text = str(round(self._info_dict["max_acc"], 4))
            self._dashboard_screen.ids.min_loss.text = str(round(self._info_dict["min_loss"], 4))
            self.check_validation = True

        self._dashboard_screen.hover_graph.current_epoch += 1

        for _key, _value in self._learn_curve_parameter.items():
            _value.points.append((self._dashboard_screen.hover_graph.current_epoch, learn_curve[_key]))

        if self._using_validation:
            self._info_dict["max_val_acc"] = learn_curve["val_accuracy"] if self._info_dict["max_val_acc"] < learn_curve["val_accuracy"] else \
                self._info_dict["max_val_acc"]
            self._info_dict["min_val_loss"] = learn_curve["val_loss"] if self._info_dict["min_val_loss"] > learn_curve["val_loss"] else \
                self._info_dict["min_val_loss"]
            self._dashboard_screen.ids.max_val_acc.text = str(round(self._info_dict["max_val_acc"], 4))
            self._dashboard_screen.ids.min_val_loss.text = str(round(self._info_dict["min_val_loss"], 4))

        self._info_dict["max_acc"] = learn_curve["accuracy"] if self._info_dict["max_acc"] < learn_curve["accuracy"] else self._info_dict["max_acc"]
        self._info_dict["min_loss"] = learn_curve["loss"] if self._info_dict["min_loss"] > learn_curve["loss"] else self._info_dict["min_loss"]

        self._dashboard_screen.ids.max_acc.text = str(round(self._info_dict["max_acc"], 4))
        self._dashboard_screen.ids.min_loss.text = str(round(self._info_dict["min_loss"], 4))

        if self._dashboard_screen.hover_graph.current_epoch >= 2:
            self.ETA_time = timedelta(
                seconds=time_freq.total_seconds() * (self._dashboard_screen.hover_graph.epoch - self._dashboard_screen.hover_graph.current_epoch))
            hours, remainder = divmod(self.ETA_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if self.ETA_time.days:
                self._dashboard_screen.ids.remain_time.text = "{}Days".format(self.ETA_time.days)
            else:
                self._dashboard_screen.ids.remain_time.text = '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))

        value = self._dashboard_screen.hover_graph.current_epoch / self._dashboard_screen.hover_graph.epoch * 100
        self._dashboard_screen.ids.progress_bar.value = value
        self._dashboard_screen.ids.progress_value.text = "[b]{}[/b]%".format(round(value, 2))
        self._dashboard_screen.ids.progress_epochs.text = "{} / {} Epochs".format(self._dashboard_screen.hover_graph.current_epoch,
                                                                                  self._dashboard_screen.hover_graph.epoch)

        if self._dashboard_screen.hover_graph.current_epoch == self._dashboard_screen.hover_graph.epoch:
            self.finish_flag = True
            self._dashboard_screen.ids.remain_time.text = "Finish"

    def export_file(self, args):
        pass

    def discard_data(self, args):
        pass

    def set_epochs(self, args):
        pass

    def estimated_time_arrival_clock(self, args):
        if not self.finish_flag and (self._dashboard_screen.hover_graph.current_epoch >= 2):
            self.ETA_time = self.ETA_time - timedelta(seconds=1)
            hours, remainder = divmod(self.ETA_time.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            if self.ETA_time.days:
                self._dashboard_screen.ids.remain_time.text = "{}Days".format(self.ETA_time.days)
            else:
                self._dashboard_screen.ids.remain_time.text = '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))

    def build(self):
        Window.size = (1200, 650)
        self.icon = 'asset/images/logo_64.png'
        self._connection_damon_thread.start()
        self._scree_manager.current = 'connect'
        Clock.schedule_interval(self.estimated_time_arrival_clock, 1)
        return self._scree_manager


if __name__ == '__main__':
    DeepMomApp().run()
