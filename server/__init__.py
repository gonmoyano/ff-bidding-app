"""Server-side addon implementation."""

from typing import Type
from ayon_server.addons import BaseServerAddon
from ayon_server.settings import BaseSettingsModel, SettingsField
from ayon_server.actions import (
    ActionExecutor,
    ExecuteResponseModel,
    SimpleActionManifest,
)


class FireframeProdigySettings(BaseSettingsModel):
    """Settings for Fireframe Prodigy Addon."""
    
    enabled: bool = SettingsField(
        True,
        title="Enabled",
        description="Enable/disable the addon"
    )
    
    sg_url: str = SettingsField(
        "",
        title="Shotgrid URL",
        description="Your Shotgrid instance URL"
    )
    
    sg_script_name: str = SettingsField(
        "",
        title="Script Name",
        description="Shotgrid API script name"
    )
    
    sg_api_key: str = SettingsField(
        "",
        title="API Key",
        description="Shotgrid API key",
        scope=["studio"]
    )
    
    output_directory: str = SettingsField(
        "",
        title="Output Directory",
        description="Default directory for packages",
        scope=["site"]
    )
    
    auto_create_folders: bool = SettingsField(
        True,
        title="Auto Create Folders",
        description="Automatically create AYON folders"
    )


DEFAULT_VALUES = {
    "enabled": True,
    "sg_url": "",
    "sg_script_name": "",
    "sg_api_key": "",
    "output_directory": "",
    "auto_create_folders": True
}


IDENTIFIER_PREFIX = "ff_bidding_app"


class FireframeProdigyAddon(BaseServerAddon):
    """Server-side addon."""

    settings_model: Type[FireframeProdigySettings] = FireframeProdigySettings
    
    async def get_default_settings(self):
        """Get default settings."""
        settings_model_cls = self.get_settings_model()
        return settings_model_cls(**DEFAULT_VALUES)
    
    async def get_simple_actions(
        self,
        project_name: str | None = None,
        variant: str = "production",
    ) -> list[SimpleActionManifest]:
        """Return list of actions."""
        output = []
        
        output.append(
            SimpleActionManifest(
                identifier=f"{IDENTIFIER_PREFIX}.open_manager",
                label="Open Fireframe Prodigy",
                icon={"type": "material-symbols", "name": "folder_data"},
                order=100,
                entity_type="project",
                allow_multiselection=False,
            )
        )
        
        return output
    
    async def execute_action(
        self,
        executor: "ActionExecutor",
    ) -> "ExecuteResponseModel":
        """Execute an action."""
        project_name = executor.context.project_name
        
        if executor.identifier == f"{IDENTIFIER_PREFIX}.open_manager":
            return await executor.get_launcher_action_response(
                args=[
                    "addon", "ff_bidding_app", "open-manager",
                    "--project", project_name,
                ]
            )
        
        raise ValueError(f"Unknown action: {executor.identifier}")
