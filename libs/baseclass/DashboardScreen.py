from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.core.window import Window
from kivy.graphics import Color, Line, Ellipse, Triangle
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.behaviors import HoverBehavior
from kivymd.theming import ThemableBehavior
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy import utils
from kivy_garden.graph import Graph, LinePlot


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super(DashboardScreen, self).__init__(**kwargs)


class HoverGraph(FloatLayout, ThemableBehavior, HoverBehavior):
    def __init__(self, **kwargs):
        super(HoverGraph, self).__init__(**kwargs)
        Window.bind(mouse_pos=self.mouse_pos)
        self.enter_flag = False
        self.touch_flag = False
        self.epoch = 500
        self.current_epoch = 0
        self.value_plot = None
        self.value_validation_plot = None
        self.plot_dict = {}

    def draw_line(self, mouse_pos):
        graph_x_start = self.x + self.ids.graph.view_pos[0]
        graph_x_end = graph_x_start + self.ids.graph.view_size[0]
        graph_y_start = self.y + self.ids.graph.view_pos[1]
        graph_y_end = graph_y_start + self.ids.graph.view_size[1]
        if (graph_x_start <= mouse_pos[0] <= graph_x_end) and (graph_y_start <= mouse_pos[1] <= graph_y_end):
            self.ids.hover_plot.canvas.clear()
            Window.set_system_cursor('crosshair')
            step = self.ids.graph.view_size[0] / self.epoch
            with self.ids.hover_plot.canvas:
                idx = round((mouse_pos[0] - graph_x_start) / step)
                if idx == 0:
                    idx = 1
                if idx <= self.current_epoch:
                    if self.touch_flag:
                        for value in self.plot_dict.values():
                            y_pos = ((value['plot'].points[idx - 1][1] * self.ids.graph.view_size[1]) / self.ids.graph.ymax) + graph_y_start
                            x_pos = (step * idx) + graph_x_start
                            if self.ids.graph.ymin <= value['plot'].points[idx - 1][1] <= self.ids.graph.ymax:
                                Color(.85, .85, .85, .8)
                                Line(circle=(x_pos, y_pos, 2.5), width=1.25)
                            value['tooltip'].text = value['index_prefix'] + str(round(value['plot'].points[idx - 1][1], 6))
                        if idx < self.epoch * .85:
                            self.ids.tooltips.pos = (mouse_pos[0] + 15, mouse_pos[1] - 55)
                        else:
                            self.ids.tooltips.pos = (mouse_pos[0] - self.ids.tooltips.width - 15, mouse_pos[1] - 55)
                        self.ids.idx_legend_label.text = str(idx)
                        self.ids.tooltips.opacity = 1
                        self.ids.idx_legend.opacity = 1
                        self.ids.legend.opacity = 0
                else:
                    self.ids.tooltips.opacity = 0
                    self.ids.idx_legend.opacity = 0
                    self.ids.legend.opacity = 1
                Color(0, 0, 0, .5)
                Line(points=[mouse_pos[0], graph_y_start, mouse_pos[0], graph_y_end], width=1)
        else:
            self.ids.hover_plot.canvas.clear()
            self.ids.tooltips.opacity = 0
            Window.set_system_cursor('arrow')
            self.enter_flag = True

    def mouse_pos(self, window, pos):
        if self.enter_flag:
            self.draw_line(pos)

    def on_touch_down(self, event):
        self.touch_flag = not self.touch_flag
        self.ids.idx_legend.opacity = 0
        self.ids.tooltips.opacity = 0
        self.ids.legend.opacity = 1

    def on_enter(self):
        self.ids.hover_plot.canvas.clear()
        self.ids.idx_legend.opacity = 0
        self.ids.tooltips.opacity = 0
        self.ids.legend.opacity = 1
        Window.set_system_cursor('arrow')
        self.enter_flag = True

    def on_leave(self):
        self.ids.hover_plot.canvas.clear()
        self.ids.idx_legend.opacity = 0
        self.ids.tooltips.opacity = 0
        self.ids.legend.opacity = 1
        Window.set_system_cursor('arrow')
        self.enter_flag = False


class EpochSetting(BoxLayout):
    pass


if __name__ == '__main__':
    Window.size = (1200, 628)


    class MyApp(MDApp):
        def __init__(self, **kwargs):
            super(MyApp, self).__init__(**kwargs)
            self.sm = ScreenManager()
            self.dashboard_screen = DashboardScreen(name='dashboard')
            self.sm.add_widget(self.dashboard_screen)

        def build(self):
            self.dashboard_screen.ids.loss_hover_graph.ids.tooltips.opacity = 0
            self.dashboard_screen.ids.loss_hover_graph.ids.idx_legend.opacity = 0
            self.dashboard_screen.ids.acc_hover_graph.ids.tooltips.opacity = 0
            self.dashboard_screen.ids.acc_hover_graph.ids.idx_legend.opacity = 0
            return self.sm


    MyApp().run()
