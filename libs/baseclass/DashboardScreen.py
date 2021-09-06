from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.graphics import Color, Line
from kivymd.app import MDApp
from kivymd.uix.behaviors import HoverBehavior
from kivymd.theming import ThemableBehavior
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy import utils
from kivy_garden.graph import Graph, SmoothLinePlot


class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super(DashboardScreen, self).__init__(**kwargs)
        self.hover_graph = HoverGraph()
        self.ids.hover_graph_canvas.add_widget(self.hover_graph)
        self.ids.toolbar.ids.label_title.font_name = "asset/fonts/KOTRA_BOLD.ttf"
        self.ids.toolbar.ids.label_title.font_size = 26
        self.ids.toolbar.ids.label_title.pos_hint = {'center_x': .5, 'center_y': .5}


class HoverGraph(FloatLayout, ThemableBehavior, HoverBehavior):
    def __init__(self, epoch=500, **kwargs):
        super(HoverGraph, self).__init__(**kwargs)
        Window.bind(mouse_pos=self.mouse_pos)
        Window.bind(on_resize=self.on_resize)
        self.enter_flag = False
        self.touch_flag = False
        self.epoch = epoch
        self.current_epoch = 0

        self.graph = Graph(x_ticks_minor=5, x_ticks_major=self.epoch / 10, y_ticks_major=1.5 / 6, y_grid_label=True, x_grid_label=True,
                           border_color=(0, 0, 0, 0), tick_color=(0, 0, 0, .5), font_size=12, padding=10,
                           label_options={"color": utils.get_color_from_hex("#000000FF"), "font_name": "asset/fonts/tway_air.ttf"},
                           x_grid=False, y_grid=True, xmin=0, xmax=self.epoch, ymin=0, ymax=1.5, draw_border=False)

        # self.accuracy_plot = LinePlot(color=utils.get_color_from_hex('#61A0FCCC'), line_width=1.2)
        # self.loss_plot = LinePlot(color=utils.get_color_from_hex('#69973CCC'), line_width=1.2)
        # self.val_accuracy_plot = LinePlot(color=utils.get_color_from_hex('#FFC727CC'), line_width=1.2)
        # self.val_loss_plot = LinePlot(color=utils.get_color_from_hex('#CC2500CC'), line_width=1.2)

        self.accuracy_plot = SmoothLinePlot(color=utils.get_color_from_hex('#3B689BCC'))
        self.val_accuracy_plot = SmoothLinePlot(color=utils.get_color_from_hex('#16A364CC'))
        self.loss_plot = SmoothLinePlot(color=utils.get_color_from_hex('##FC444FCC'))
        self.val_loss_plot = SmoothLinePlot(color=utils.get_color_from_hex('#F5AA31CC'))

        self.graph.add_plot(self.accuracy_plot)
        self.graph.add_plot(self.val_accuracy_plot)
        self.graph.add_plot(self.loss_plot)
        self.graph.add_plot(self.val_loss_plot)
        self.ids.graph_plot.add_widget(self.graph)

        # self.accuracy_plot.points = [(i, random()) for i in range(0, self.current_epoch)]
        # self.val_accuracy_plot.points = [(i, random()) for i in range(0, self.current_epoch)]
        # self.loss_plot.points = [(i, random() * 1.5) for i in range(0, self.current_epoch)]
        # self.val_loss_plot.points = [(i, random() * 1.5) for i in range(0, self.current_epoch)]

        self.half_graph_padding = self.graph.padding / 2
        self.ids.tooltips.opacity = 0

        # TODO check the size
        self.offset_x = 10
        self.offset_y = 10

    def draw_line(self, mouse_pos):

        plot_dict = {0: self.accuracy_plot, 1: self.loss_plot, 2: self.val_accuracy_plot, 3: self.val_loss_plot}
        # plot_dict = {0: self.accuracy_plot}
        graph_x_start = self.offset_x + self.graph.view_pos[0]
        graph_x_end = graph_x_start + self.graph.view_size[0]
        graph_y_start = self.offset_y + self.graph.view_pos[1]
        graph_y_end = graph_y_start + self.graph.view_size[1]

        if (graph_x_start <= mouse_pos[0] <= graph_x_end) and (graph_y_start <= mouse_pos[1] <= graph_y_end):
            self.ids.hover_plot.canvas.clear()
            Window.set_system_cursor('crosshair')
            step = self.graph.view_size[0] / self.epoch
            with self.ids.hover_plot.canvas:
                idx = round((mouse_pos[0] - graph_x_start) / step)
                if idx < self.current_epoch:
                    if self.touch_flag:
                        for value in plot_dict.values():
                            y_len = ((value.points[idx][1] * self.graph.view_size[1]) / self.graph.ymax) + graph_y_start
                            x_len = (step * idx) + graph_x_start
                            Color(.15, .15, .15, .8)
                            Line(circle=(x_len, y_len, 3), width=1.5)
                        if idx < self.epoch * .85:
                            self.ids.tooltips.pos = (mouse_pos[0] + 15, mouse_pos[1] - 55)
                        else:
                            self.ids.tooltips.pos = (mouse_pos[0] - self.ids.tooltips.width - 15, mouse_pos[1] - 55)

                        self.ids.accuracy_tip.text = '[color=3B689B]●[/color] Acc: ' + str(round(self.accuracy_plot.points[idx][1], 6))
                        self.ids.val_accuracy_tip.text = '[color=16A364]●[/color] ValAcc: ' + str(round(self.val_accuracy_plot.points[idx][1], 6))
                        self.ids.loss_tip.text = '[color=fc444f]●[/color] Loss: ' + str(round(self.loss_plot.points[idx][1], 6))
                        self.ids.val_loss_tip.text = '[color=f5aa31]●[/color] ValLoss: ' + str(round(self.val_loss_plot.points[idx][1], 6))
                        self.ids.idx_legend_label.text = 'Index: ' + str(idx)
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

    def on_resize(self, *args):
        self.offset_x = 10
        self.offset_y = 10


if __name__ == '__main__':
    Window.size = (1200, 628)


    class MyApp(MDApp):
        def __init__(self, **kwargs):
            super(MyApp, self).__init__(**kwargs)
            self.sm = ScreenManager()
            self.dashboard_screen = DashboardScreen(name='dashboard')
            self.sm.add_widget(self.dashboard_screen)

        def build(self):
            self.icon = '../../asset/images/logo_128.png'
            return self.sm


    MyApp().run()
