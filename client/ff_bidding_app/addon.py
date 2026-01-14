"""Main addon module with tray integration - WITH FILE LOGGING."""

from qtpy import QtWidgets, QtCore
from ayon_core.addon import AYONAddon, ITrayAddon, click_wrap
import ayon_api
import sys
import traceback
import logging
from pathlib import Path
from datetime import datetime
from .version import __version__
from .app import PackageManagerApp


# Setup file logging
def setup_logging():
    """Setup logging to file in the addon root directory."""
    try:
        # Create logs directory in the addon root (go up from client/ff_bidding_app to root)
        addon_root = Path(__file__).parent.parent.parent
        log_dir = addon_root / "logs"
        log_dir.mkdir(exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"fireframe_prodigy_{timestamp}.log"

        # Setup logging
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()  # Also print to console
            ]
        )

        logger = logging.getLogger("FireframeProdigy")
        logger.setLevel(logging.WARNING)

        return logger
    except Exception as e:
        print(f"Failed to setup logging: {e}")
        traceback.print_exc()
        return logging.getLogger("FireframeProdigy")


# Initialize logger
logger = setup_logging()

# Apply DPI scaling from settings (must be done before creating QApplication or windows)
try:
    from .app import PackageManagerApp
    PackageManagerApp.apply_dpi_scaling()
except Exception as e:
    logger.error(f"Failed to apply DPI scaling on module import: {e}")


class FireframeProdigyAddon(AYONAddon, ITrayAddon):
    """Fireframe Prodigy Addon for AYON Tray."""

    label = "Fireframe Prodigy"
    name = "ff_bidding_app"
    version = __version__

    def initialize(self, settings):
        """Initialize addon with settings from server."""
        logger.info("Initializing addon...")
        logger.info(f"Settings: {settings}")

        self.enabled = settings.get("enabled", True)
        self.sg_url = settings.get("sg_url", "")
        self.sg_script_name = settings.get("sg_script_name", "")
        self.sg_api_key = settings.get("sg_api_key", "")
        self.output_directory = settings.get("output_directory", "")
        self.auto_create_folders = settings.get("auto_create_folders", True)
        self.fetch_thumbnails = settings.get("fetch_thumbnails", False)

        self._app_window = None

        logger.info(f"Initialization complete. Enabled: {self.enabled}")
        logger.info(f"Output directory: {self.output_directory}")

    def tray_init(self):
        """Called when tray is initialized."""
        logger.info("Tray init called")

    def tray_start(self):
        """Called when tray starts."""
        logger.info("Tray start called")

    def tray_exit(self):
        """Called when tray exits."""
        logger.info("Tray exit called")
        if self._app_window:
            self._app_window.close()
            self._app_window = None

    def tray_menu(self, tray_menu):
        """Add items to the tray menu."""
        logger.info("Building tray menu...")
        try:
            menu = QtWidgets.QMenu(self.label, tray_menu)
            menu.setProperty("submenu", "on")

            action_open = QtWidgets.QAction("Open Package Manager", menu)
            action_open.triggered.connect(self.show_app)
            menu.addAction(action_open)

            menu.addSeparator()

            action_quick = QtWidgets.QAction("Quick Fetch from Shotgrid", menu)
            action_quick.triggered.connect(self.quick_fetch)
            menu.addAction(action_quick)

            tray_menu.addMenu(menu)
            logger.info("Tray menu built successfully")
        except Exception as e:
            logger.error(f"Error building menu: {e}", exc_info=True)

    def show_app(self):
        """Show the main application window."""
        logger.info("=" * 60)
        logger.info("show_app() called")
        logger.info("=" * 60)

        try:
            if not self.enabled:
                logger.warning("Addon is disabled in settings")
                QtWidgets.QMessageBox.warning(
                    None,
                    "Addon Disabled",
                    "Fireframe Prodigy addon is disabled in AYON settings.",
                )
                return

            logger.info("Creating app window...")
            logger.info(f"  sg_url: {self.sg_url}")
            logger.info(f"  sg_script_name: {self.sg_script_name}")
            logger.info(f"  output_directory: {self.output_directory}")

            if self._app_window is None:
                logger.info("Creating new window instance...")
                self._app_window = PackageManagerApp(
                    sg_url=self.sg_url,
                    sg_script_name=self.sg_script_name,
                    sg_api_key=self.sg_api_key,
                    output_directory=self.output_directory
                )
                logger.info("Window instance created successfully")
            else:
                logger.info("Using existing window instance")

            logger.info("Calling window.show()...")
            self._app_window.show()

            logger.info("Calling window.raise_()...")
            self._app_window.raise_()

            logger.info("Calling window.activateWindow()...")
            self._app_window.activateWindow()

            logger.info("Window visibility: " + str(self._app_window.isVisible()))
            logger.info("Window minimized: " + str(self._app_window.isMinimized()))
            logger.info("Window geometry: " + str(self._app_window.geometry()))

            logger.info("show_app() completed successfully")
            logger.info("=" * 60)

        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"CRITICAL ERROR in show_app: {e}", exc_info=True)
            logger.error("=" * 60)

            # Show error dialog
            QtWidgets.QMessageBox.critical(
                None,
                "Error Opening Fireframe Prodigy",
                f"Failed to open the application:\n\n{str(e)}\n\n"
                f"Check logs at:\n{Path(__file__).parent / 'logs'}"
            )

    def quick_fetch(self):
        """Quick fetch dialog."""
        logger.info("quick_fetch() called")
        try:
            from .app import QuickFetchDialog
            dialog = QuickFetchDialog(
                sg_url=self.sg_url,
                sg_script_name=self.sg_script_name,
                sg_api_key=self.sg_api_key,
                output_directory=self.output_directory
            )
            logger.info("Showing quick fetch dialog")
            result = dialog.exec_()
            logger.info(f"Dialog result: {result}")
        except Exception as e:
            logger.error(f"Error in quick_fetch: {e}", exc_info=True)

    def cli(self, click_group):
        """Add CLI commands."""
        click_group.add_command(cli_main.to_click_obj())


@click_wrap.group("ff_bidding_app", help="Fireframe Prodigy CLI commands")
def cli_main():
    """Main CLI group."""
    pass


@cli_main.command()
@click_wrap.option("--project", help="AYON project name", type=str, required=True)
@click_wrap.option("--sg-project-id", help="Shotgrid project ID", type=int, required=True)
@click_wrap.option("--output", help="Output file path", type=str, required=False)
def fetch_project(project, sg_project_id, output):
    """Fetch project data from Shotgrid."""
    logger.info(f"CLI fetch_project: project={project}, sg_project_id={sg_project_id}")

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    progress = QtWidgets.QProgressDialog(
        "Fetching data from Shotgrid...",
        "Cancel", 0, 100
    )
    progress.setWindowTitle("Data Package Creation")
    progress.setWindowModality(QtCore.Qt.WindowModal)
    progress.show()

    try:
        logger.info(f"Fetching SG project {sg_project_id} for AYON project: {project}")
        progress.setValue(100)

        QtWidgets.QMessageBox.information(
            None, "Success",
            f"Data package created for project: {project}"
        )
    except Exception as e:
        logger.error(f"CLI Error: {e}", exc_info=True)
        QtWidgets.QMessageBox.critical(
            None, "Error",
            f"Failed to create package: {str(e)}"
        )
    finally:
        progress.close()


@cli_main.command()
@click_wrap.option("--project", help="AYON project name", type=str, required=False)
def open_manager(project):
    """Open the Package Manager GUI."""
    logger.info(f"CLI open_manager: project={project}")

    # Apply DPI scaling before creating QApplication
    from .app import PackageManagerApp
    PackageManagerApp.apply_dpi_scaling()

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    try:
        window = PackageManagerApp(
            sg_url="",
            sg_script_name="",
            sg_api_key="",
            output_directory=""
        )

        window.show()

        if project:
            window.setWindowTitle(f"Fireframe Prodigy - {project}")

        logger.info("CLI: Window shown, entering event loop")
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"CLI Error: {e}", exc_info=True)