import gi
gi.require_versions({
    'Gtk':'4.0',
    'Adw':'1'
})

from gi.repository import Gtk, Adw, Gio
from modules.gmail import Gmail

HORIZONTAL=Gtk.Orientation.HORIZONTAL
VERTICAL=Gtk.Orientation.VERTICAL

def handle(gm: Gmail):
    print("Reading emails")
    print(gm.update_database())

class GmailUI(Gtk.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        if app.theme is not None:
            settings = Gtk.Settings.get_default()
            settings.set_property("gtk-theme-name", app.theme)

        super().__init__(show_menubar=True, application=app)
        
        self.set_default_size(600, 550)
        self.set_size_request(600, 550)
        
        self.set_title("Gmail")

        header = Adw.HeaderBar.new()
        self.set_titlebar(header)

        self.main_box = Gtk.Box.new(VERTICAL,10)

        self.set_child(self.main_box)
        Gmail().connect('authentication-finish', handle)
        self.present()

class GmailApplication(Adw.Application):
    def __init__(self, theme=None):
        super().__init__(application_id="com.github.axel.GmailC",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.theme = theme

    def do_activate(self):
        self.win = self.props.active_window
        if not self.win:
            self.win = GmailUI(self)
        
        self.create_action('quit', self.exit_app, ['<primary>q'])
    
    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
    
    def do_shutdown(self) -> None:
        Gtk.Application.do_shutdown(self)

    
    def exit_app(self, action, param):
        self.quit()
    
    def create_action(self, name, callback, shortcuts=None):
        action = Gio.SimpleAction.new(name, None)
        action.connect('activate', callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f'app.{name}', shortcuts)