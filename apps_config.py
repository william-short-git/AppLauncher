"""
Configuration file for EngineeringHub managed applications.
To add a new application, simply append a dictionary to the APPS list below.
"""

from typing import List, Dict, Any

APPS: List[Dict[str, Any]] = [
    {
        "id": "vscode",
        "name": "Visual Studio Code",
        "icon": "💻",
        "icon_path": "icons/vscode.png",
        "category": "Development",
        "app_name": "Visual Studio Code",
        "cask": "visual-studio-code",
        "source": "brew",
        "desc": "Code editing, debugging, and extension ecosystem",
    },
    {
        "id": "antigravity",
        "name": "Antigravity",
        "icon": "🪐",
        "icon_path": "icons/antigravity.png",
        "category": "AI / Development",
        "app_name": "Antigravity",
        "source": "web",
        "desc": "Advanced agentic coding assistant & development platform",
        "url": "https://antigravity.google/",
    },
    {
        "id": "kicad",
        "name": "KiCad",
        "icon": "🔌",
        "icon_path": "icons/kicad.png",
        "category": "EDA / PCB Design",
        "app_name": "KiCad",
        "cask": "kicad",
        "source": "github",
        "repo": "KiCad/kicad-source-mirror",
        "desc": "Schematic capture (Updates pulled from GitHub releases)",
    },
    {
        "id": "ltspice",
        "name": "LTspice",
        "icon": "⚡",
        "icon_path": "icons/ltspice.png",
        "category": "Simulation",
        "app_name": "LTspice",
        "cask": "ltspice",
        "source": "brew",
        "desc": "High-performance SPICE simulation and circuit analysis",
    },
    {
        "id": "fusion",
        "name": "Autodesk Fusion",
        "icon": "🏗️",
        "icon_path": "icons/fusion.png",
        "category": "CAD / CAM",
        "app_name": "Autodesk Fusion 360",
        "cask": "autodesk-fusion",
        "source": "student",
        "desc": "Managed securely via Autodesk Education portal",
        "url": "https://www.autodesk.com/education/edu-software/overview",
    },
    {
        "id": "freecad",
        "name": "FreeCAD",
        "icon": "🛠️",
        "icon_path": "icons/freecad.png",
        "category": "Open-Source CAD",
        "app_name": "FreeCAD",
        "cask": "freecad",
        "source": "github",
        "repo": "FreeCAD/FreeCAD",
        "desc": "Parametric 3D modeler (Updates pulled from GitHub)",
    },
]
