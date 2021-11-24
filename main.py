import os
import sys
from pathlib import Path

from kivymd.app import MDApp
from kivy.uix.screenmanager import ScreenManager
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.lang import Builder
from kivymd.uix.button import MDRectangleFlatButton
from kivymd.uix.dialog import MDDialog
from kivy import utils
from datetime import datetime
from datetime import timedelta
from time import sleep
from queue import Queue
from threading import Thread
from math import ceil
import json
import pandas
import numpy
import paho.mqtt.client as mqtt

from kivy_garden.graph import LinePlot

from libs.baseclass.ConnectScreen import ConnectScreen
from libs.baseclass.DashboardScreen import DashboardScreen, EpochSetting
from libs.baseclass.DeepMomRequestResponse import DeepMomResponse as DMRes
from libs.baseclass.DeepMomRequestResponse import DeepMomResponseState as DMRes_state
from libs.baseclass.DeepMomRequestResponse import DeepMomRequestState as DMReq_state

if getattr(sys, 'frozen', False):  # bundle mode with PyInstaller
    os.environ['DeepMom_ROOT'] = sys._MEIPASS
else:
    os.environ['DeepMom_ROOT'] = str(Path(__file__).parent)

KV_DIR = f'{os.environ["DeepMom_ROOT"]}/libs/kv/'

for kv_file in os.listdir(KV_DIR):
    with open(os.path.join(KV_DIR, kv_file), encoding='utf-8') as kv:
        Builder.load_string(kv.read())


class DeepMomApp(MDApp):
    def __init__(self, **kwargs):
        super(DeepMomApp, self).__init__()
        self._connect_screen_in_queue = Queue()
        self._connect_screen_out_queue = Queue()
        self._connect_screen = ConnectScreen(name='connect', in_queue=self._connect_screen_in_queue, out_queue=self._connect_screen_out_queue)
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
        self._epoch_dialog = MDDialog(title="Setting number of epochs",
                                      type="custom",
                                      content_cls=EpochSetting(),
                                      buttons=[
                                          MDRectangleFlatButton(text="Confirm",
                                                                on_release=self.epoch_button_release,
                                                                on_text_validate=self.epoch_button_release)])
        self.finish_flag = False
        self.previous_time = timedelta(seconds=0)
        self.ETA_time = timedelta(seconds=0)
        self.time_freq = timedelta(seconds=0)
        self._epoch = 500
        self._current_epoch = 0
        self._color_dict = {'red': 'fc444f', 'blue': '3b689b', 'green': '16a364', 'yellow': 'f5aa31'}
        self._best_dict = {'accuracy': 0, 'loss': 0, 'val_accuracy': 0, 'val_loss': 0}
        self.test_dict = {}
        self._learn_curve_parameter = {}

    def wrap_color(self, color, str_value):
        return '[color={}]'.format(self._color_dict[color]) + str_value + '[/color]'

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
                    self._dashboard_screen.ids.topic_label.text = requset.args[0]
                    self._dashboard_screen.ids.current_epoch_label.text = '0 / {}'.format(requset.args[1])
                    self._dashboard_screen.ids.acc_hover_graph.ids.graph.xmax = int(requset.args[1])
                    self._dashboard_screen.ids.loss_hover_graph.ids.graph.xmax = int(requset.args[1])
                    self._dashboard_screen.ids.acc_hover_graph.epoch = int(requset.args[1])
                    self._dashboard_screen.ids.loss_hover_graph.epoch = int(requset.args[1])
                    self._dashboard_screen.ids.acc_hover_graph.ids.graph.x_ticks_major = int(requset.args[1]) / 10
                    self._dashboard_screen.ids.loss_hover_graph.ids.graph.x_ticks_major = int(requset.args[1]) / 10
                    self._epoch = int(requset.args[1])
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
        if not self.finish_flag:
            learn_curve = json.loads(msg.payload.decode('utf-8'))
            self.time_freq = datetime.now() - self.previous_time
            self.previous_time = datetime.now()

            if not self._current_epoch:
                self.time_freq = timedelta(0)
                if not ('val_accuracy' in learn_curve and 'val_loss' in learn_curve):
                    del self._dashboard_screen.ids.loss_hover_graph.plot_dict['validation']
                    del self._dashboard_screen.ids.acc_hover_graph.plot_dict['validation']
                    del self._learn_curve_parameter['val_accuracy']
                    del self._learn_curve_parameter['val_loss']

                for _key, _value in self._learn_curve_parameter.items():
                    self._best_dict[_key] = learn_curve[_key]
                    _value['best'].text = self.wrap_color(_value['color'], '● ') + '{:.4f}'.format(round(learn_curve[_key], 4))

        self._current_epoch += 1
        self._dashboard_screen.ids.acc_hover_graph.current_epoch = self._current_epoch
        self._dashboard_screen.ids.loss_hover_graph.current_epoch = self._current_epoch
        self._dashboard_screen.ids.progress_bar.value = self._current_epoch / self._epoch * 100
        self._dashboard_screen.ids.current_epoch_label.text = '{} / {}'.format(self._current_epoch, self._epoch)
        self._dashboard_screen.ids.percent_epoch_label.text = '{:.2f}%'.format(round(self._current_epoch / self._epoch * 100, 2))

        if 'val_loss' in learn_curve:
            self._dashboard_screen.ids.loss_hover_graph.ids.graph.ymax = \
                ceil(max(learn_curve['loss'], learn_curve['val_loss'], self._dashboard_screen.ids.loss_hover_graph.ids.graph.ymax))
        else:
            self._dashboard_screen.ids.loss_hover_graph.ids.graph.ymax = \
                ceil(max(learn_curve['loss'], self._dashboard_screen.ids.loss_hover_graph.ids.graph.ymax))

        for _key, _value in self._learn_curve_parameter.items():
            self._best_dict[_key] = _value['best_func'](learn_curve[_key], self._best_dict[_key])
            _value['best'].text = self.wrap_color(_value['color'], '● ') + '{:.4f}'.format(round(self._best_dict[_key], 4))
            _value['plot'].points.append((self._current_epoch, learn_curve[_key]))
            _value['data'].text = '{:.6f}'.format(round(learn_curve[_key], 6))

            if self._current_epoch >= 2:
                rate_vale = float(learn_curve[_key]) - _value['plot'].points[self._current_epoch - 2][1]
                if rate_vale < 0:
                    _value['rate'].text = self.wrap_color('red', '▼' + '{:.6f}'.format(round(abs(rate_vale), 6)))
                else:
                    _value['rate'].text = self.wrap_color('green', '▲' + '{:.6f}'.format(round(rate_vale, 6)))

                self.ETA_time = timedelta(seconds=self.time_freq.total_seconds() * (self._epoch - self._current_epoch))
                hours, remainder = divmod(self.ETA_time.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)

                if self.ETA_time.days:
                    self._dashboard_screen.ids.ETA_label.text = \
                        '{}Days '.format(self.ETA_time.days) + \
                        '/ {:.3f} [size=12]epoch per sec[/size]'.format(round(self.time_freq.total_seconds(), 3))
                else:
                    self._dashboard_screen.ids.ETA_label.text = \
                        '{:02}:{:02}:{:02} '.format(int(hours), int(minutes), int(seconds)) + \
                        '/ {:.3f} [size=12]epoch per sec[/size]'.format(round(self.time_freq.total_seconds(), 3))

        if self._current_epoch == self._epoch:
            self.finish_flag = True
            self._dashboard_screen.ids.ETA_label.text = 'Finish'

    def discard_data(self, args):
        del self._dashboard_screen.ids.loss_hover_graph.plot_dict
        del self._dashboard_screen.ids.acc_hover_graph.plot_dict
        del self._learn_curve_parameter
        del self._best_dict

        for _value in {'loss': self._dashboard_screen.ids.loss_hover_graph, 'acc': self._dashboard_screen.ids.acc_hover_graph}.values():
            _value.ids.graph.remove_plot(_value.value_plot)
            _value.ids.graph.remove_plot(_value.value_validation_plot)

        del self._dashboard_screen.ids.loss_hover_graph.value_plot
        del self._dashboard_screen.ids.loss_hover_graph.value_validation_plot
        del self._dashboard_screen.ids.acc_hover_graph.value_plot
        del self._dashboard_screen.ids.acc_hover_graph.value_validation_plot

        self.widget_init(None)

        for _value in self._learn_curve_parameter.values():
            _value['data'].text = '-'
            _value['rate'].text = '-'
            _value['best'].text = self.wrap_color(_value['color'], '● ') + '-'

        self._current_epoch = 0
        self._dashboard_screen.ids.acc_hover_graph.current_epoch = 0
        self._dashboard_screen.ids.loss_hover_graph.current_epoch = 0
        
        self._dashboard_screen.ids.progress_bar.value = 0
        self._dashboard_screen.ids.current_epoch_label.text = '0 / {}'.format(self._epoch)
        self._dashboard_screen.ids.percent_epoch_label.text = '00.00%'

        self._time_freq = timedelta(seconds=0)
        self.previous_time = timedelta(seconds=0)
        self.ETA_time = timedelta(seconds=0)
        self._dashboard_screen.ids.ETA_label.text = '00:00:00 / 0.000 [size=12]epoch per sec[/size]'

        self.finish_flag = False

    def export_file(self, args):
        try:
            data_frame = pandas.DataFrame(columns=['accuracy', 'validation_accuracy', 'loss', 'validation_loss'])
            data_frame['accuracy'] = \
                numpy.array(self._dashboard_screen.ids.acc_hover_graph.value_plot.points)[:, 1]
            data_frame['validation_accuracy'] = \
                numpy.array(self._dashboard_screen.ids.acc_hover_graph.value_validation_plot.points)[:, 1]
            data_frame['loss'] = \
                numpy.array(self._dashboard_screen.ids.loss_hover_graph.value_plot.points)[:, 1]
            data_frame['validation_loss'] = \
                numpy.array(self._dashboard_screen.ids.loss_hover_graph.value_validation_plot.points)[:, 1]
            data_frame.to_csv('learning_curve.csv', na_rep='NaN', columns=['accuracy', 'validation_accuracy', 'loss', 'validation_loss'], index=False)
        except ValueError:
            data_frame = pandas.DataFrame(columns=['accuracy', 'validation_accuracy', 'loss', 'validation_loss'])
            data_frame.to_csv('learning_curve.csv', na_rep='NaN', columns=['accuracy', 'validation_accuracy', 'loss', 'validation_loss'], index=False)

    def set_epochs(self, args):
        self._epoch_dialog.open()

    def epoch_button_release(self, args):
        try:
            epochs = int(self._epoch_dialog.content_cls.ids.epochs_text.text)
            if epochs == 0 or (epochs <= self._current_epoch):
                raise ValueError

            self._dashboard_screen.ids.progress_bar.value = self._current_epoch / self._epoch * 100
            self._dashboard_screen.ids.percent_epoch_label.text = '{:.2f}%'.format(round(self._current_epoch / self._epoch * 100, 2))
            self._dashboard_screen.ids.current_epoch_label.text = '{} / {}'.format(self._current_epoch, epochs)
            self._dashboard_screen.ids.loss_hover_graph.ids.graph.xmax = epochs
            self._dashboard_screen.ids.loss_hover_graph.ids.graph.x_ticks_major = epochs / 10
            self._dashboard_screen.ids.acc_hover_graph.ids.graph.xmax = epochs
            self._dashboard_screen.ids.acc_hover_graph.ids.graph.x_ticks_major = epochs / 10
            self._epoch = epochs
            self._epoch_dialog.dismiss()

        except ValueError:
            warn_dialog = MDDialog(title='Input must be integer or must be bigger than 0 and current epochs', type='alert')
            warn_dialog.open()

    def estimated_time_arrival_clock(self, args):
        if not self.finish_flag and (self._current_epoch >= 2):
            self.ETA_time = self.ETA_time - timedelta(seconds=1)
            hours, remainder = divmod(self.ETA_time.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            if self.ETA_time.days:
                self._dashboard_screen.ids.ETA_label.text = '{}Days '.format(self.ETA_time.days) + \
                                                            '/ {:.3f} [size=12]epoch per sec[/size]'.format(round(self.time_freq.total_seconds(), 3))
            else:
                self._dashboard_screen.ids.ETA_label.text = '{:02}:{:02}:{:02} '.format(int(hours), int(minutes), int(seconds)) + \
                                                            '/ {:.3f} [size=12]epoch per sec[/size]'.format(round(self.time_freq.total_seconds(), 3))

    def widget_init(self, arg):
        self._dashboard_screen.ids.loss_hover_graph.value_plot = LinePlot(color=utils.get_color_from_hex('#FC444FFF'), line_width=1.2)
        self._dashboard_screen.ids.loss_hover_graph.value_validation_plot = LinePlot(color=utils.get_color_from_hex('#F5AA31D9'), line_width=1.2)
        self._dashboard_screen.ids.acc_hover_graph.value_plot = LinePlot(color=utils.get_color_from_hex('#3B689BFF'), line_width=1.2)
        self._dashboard_screen.ids.acc_hover_graph.value_validation_plot = LinePlot(color=utils.get_color_from_hex('#16A364D9'), line_width=1.2)

        self._dashboard_screen.ids.loss_hover_graph.ids.legend_label.text = self.wrap_color('red', '●') + ' Loss'
        self._dashboard_screen.ids.loss_hover_graph.ids.legend_val_label.text = self.wrap_color('yellow', '●') + ' Val Loss'
        self._dashboard_screen.ids.acc_hover_graph.ids.legend_label.text = self.wrap_color('blue', '●') + ' Acc'
        self._dashboard_screen.ids.acc_hover_graph.ids.legend_val_label.text = self.wrap_color('green', '●') + ' Val Acc'

        for _value in {'loss': self._dashboard_screen.ids.loss_hover_graph, 'acc': self._dashboard_screen.ids.acc_hover_graph}.values():
            _value.ids.graph.add_plot(_value.value_plot)
            _value.ids.graph.add_plot(_value.value_validation_plot)
            _value.ids.tooltips.opacity = 0
            _value.ids.idx_legend.opacity = 0

        self._dashboard_screen.ids.loss_hover_graph.plot_dict = \
            {
                'value':
                    {
                        'plot': self._dashboard_screen.ids.loss_hover_graph.value_plot,
                        'index_prefix': '[color=fc444f]●[/color] Loss: ',
                        'tooltip': self._dashboard_screen.ids.loss_hover_graph.ids.value_tip,
                    },
                'validation':
                    {
                        'plot': self._dashboard_screen.ids.loss_hover_graph.value_validation_plot,
                        'index_prefix': '[color=f5aa31]●[/color] Val Loss: ',
                        'tooltip': self._dashboard_screen.ids.loss_hover_graph.ids.value_val_tip,
                    },

            }

        self._dashboard_screen.ids.acc_hover_graph.plot_dict = \
            {
                'value':
                    {
                        'plot': self._dashboard_screen.ids.acc_hover_graph.value_plot,
                        'index_prefix': '[color=3B689B]●[/color] Acc: ',
                        'tooltip': self._dashboard_screen.ids.acc_hover_graph.ids.value_tip,
                    },
                'validation':
                    {
                        'plot': self._dashboard_screen.ids.acc_hover_graph.value_validation_plot,
                        'index_prefix': '[color=16A364]●[/color] ValAcc: ',
                        'tooltip': self._dashboard_screen.ids.acc_hover_graph.ids.value_val_tip,
                    }

            }

        self._learn_curve_parameter = \
            {
                'accuracy':
                    {
                        'plot': self._dashboard_screen.ids.acc_hover_graph.value_plot,
                        'data': self._dashboard_screen.ids.acc_data_label,
                        'rate': self._dashboard_screen.ids.acc_rate_label,
                        'best': self._dashboard_screen.ids.max_acc_label,
                        'search_result': self._dashboard_screen.ids.search_acc_label,
                        'best_func': max,
                        'color': 'blue',
                    },
                'loss':
                    {
                        'plot': self._dashboard_screen.ids.loss_hover_graph.value_plot,
                        'data': self._dashboard_screen.ids.loss_data_label,
                        'rate': self._dashboard_screen.ids.loss_rate_label,
                        'best': self._dashboard_screen.ids.min_loss_label,
                        'search_result': self._dashboard_screen.ids.search_loss_label,
                        'best_func': min,
                        'color': 'red',
                    },
                'val_accuracy':
                    {
                        'plot': self._dashboard_screen.ids.acc_hover_graph.value_validation_plot,
                        'data': self._dashboard_screen.ids.val_acc_data_label,
                        'rate': self._dashboard_screen.ids.val_acc_rate_label,
                        'best': self._dashboard_screen.ids.max_val_acc_label,
                        'search_result': self._dashboard_screen.ids.search_val_acc_label,
                        'best_func': max,
                        'color': 'green',
                    },
                'val_loss':
                    {
                        'plot': self._dashboard_screen.ids.loss_hover_graph.value_validation_plot,
                        'data': self._dashboard_screen.ids.val_loss_data_label,
                        'rate': self._dashboard_screen.ids.val_loss_rate_label,
                        'best': self._dashboard_screen.ids.min_val_loss_label,
                        'search_result': self._dashboard_screen.ids.search_val_loss_label,
                        'best_func': min,
                        'color': 'yellow',
                    },
            }
        self._best_dict = {'accuracy': 0, 'loss': 0, 'val_accuracy': 0, 'val_loss': 0}

    def search_value_via_index(self):
        try:
            for _value in self._learn_curve_parameter.values():
                _value['search_result'].text = \
                    '{:.8f}'.format(round(_value['plot'].points[int(self._dashboard_screen.ids.search_text_field.text) - 1][1], 8))
        except Exception as ex:
            print(ex)

    def build(self):
        Window.size = (1300, 650)
        self.icon = 'assets/images/logo_64.png'
        self.theme_cls.primary_palette = 'BlueGray'
        self.theme_cls.theme_style = 'Dark'
        self._connection_damon_thread.start()
        self._scree_manager.current = 'connect'
        self._connect_screen.ids.broker_ip.focus = True
        Clock.schedule_once(self.widget_init)
        Clock.schedule_interval(self.estimated_time_arrival_clock, 1)
        return self._scree_manager


if __name__ == '__main__':
    DeepMomApp().run()
