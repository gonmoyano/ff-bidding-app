# Fireframe Prodigy (FF Bidding App) - User Manual

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Main Interface Overview](#main-interface-overview)
4. [Working with Projects and RFQs](#working-with-projects-and-rfqs)
5. [Bidding View](#bidding-view)
   - [VFX Breakdown Tab](#vfx-breakdown-tab)
   - [Assets Tab](#assets-tab)
   - [Rates Tab](#rates-tab)
   - [Costs Tab](#costs-tab)
6. [Packages View](#packages-view)
7. [Delivery View](#delivery-view)
8. [Settings and Configuration](#settings-and-configuration)
9. [Keyboard Shortcuts](#keyboard-shortcuts)
10. [Troubleshooting](#troubleshooting)

---

## Introduction

**Fireframe Prodigy** (also known as FF Bidding App) is a professional VFX bidding and project estimation tool designed for VFX studios. The application helps manage Request for Quotes (RFQs), create detailed cost breakdowns, track pricing through rate cards, and deliver packages to vendors.

### Key Features

- **ShotGrid Integration**: Seamlessly sync with ShotGrid for project, asset, and shot data management
- **AYON Integration**: Deploy as an addon with tray integration for pipeline workflows
- **VFX Scene Breakdown**: Manage detailed breakdowns with cost calculations per discipline
- **Asset Bidding**: Track and cost individual assets within bids
- **Rate Card Management**: Create and manage price lists with hourly rates
- **Package Creation**: Generate JSON data packages for vendor delivery
- **Google Drive Integration**: Optional cloud sharing capabilities

### System Requirements

- AYON Server >= 1.0.0 (for AYON integration)
- AYON Launcher >= 1.0.0 (for AYON integration)
- Python 3.9+
- Valid ShotGrid credentials

---

## Getting Started

### Launching the Application

#### From AYON Tray (Recommended)

1. Click the **AYON Tray** icon in your system tray
2. Navigate to: **FF Package Manager** → **Open Package Manager**
3. The application window will open

#### From Command Line

```bash
# As AYON addon
ayon addon ff_bidding_app open-manager --project ProjectName

# Standalone mode
python run_standalone.py
```

### Initial Configuration

Before using the application, ensure your ShotGrid credentials are configured:

1. Click the **Settings** button (gear icon) in the top-right corner
2. Enter your ShotGrid URL, Script Name, and API Key
3. Click **Save** to apply settings

---

## Main Interface Overview

The application uses a modern dark theme interface with three main views:

```
┌─────────────────────────────────────────────────────────────────┐
│ [View Selector ▼]                              [⚙ Settings]    │
├─────────────────────────────────────────────────────────────────┤
│ Project: [Dropdown ▼]  RFQ: [Dropdown ▼]     [Load from SG]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                      Main Content Area                          │
│                                                                 │
│                   (Changes based on View)                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### View Selector

Use the dropdown in the top-left to switch between views:

| View | Purpose |
|------|---------|
| **Bidding** | Primary workflow for creating and managing bids |
| **Packages** | Create and manage data packages |
| **Delivery** | Share packages with vendors |

### Top Toolbar

- **Project Dropdown**: Select the active project
- **RFQ Dropdown**: Select the active Request for Quote
- **Load from ShotGrid**: Refresh project and RFQ data from ShotGrid
- **Settings Button**: Open application settings

---

## Working with Projects and RFQs

### Loading Projects

1. Click **Load from ShotGrid** to fetch available projects
2. Select a project from the **Project** dropdown
3. The RFQ dropdown will populate with available RFQs for that project

### Creating a New RFQ

1. With a project selected, click the **+** button next to the RFQ dropdown
2. In the **Create New RFQ** dialog:
   - Enter an **RFQ Name**
   - Check initialization options:
     - ☑ Create Bid
     - ☑ Create VFX Breakdown
     - ☑ Create Bid Assets
     - ☑ Create Price List
3. Click **Create** to generate the RFQ and linked entities

### Managing RFQ Vendors

1. Select an RFQ from the dropdown
2. Click the **Configure RFQs** button (or right-click the RFQ dropdown)
3. In the dialog, click **Manage Vendors**
4. Add or remove vendors from the list
5. Click **Save** to apply changes

### Renaming an RFQ

1. Right-click the RFQ in the dropdown
2. Select **Rename RFQ**
3. Enter the new name and click **OK**

### Viewing Project Details

Click the **Project Details** button to view:
- Project ID, Name, and Status
- RFQ ID, Code, and Status

---

## Bidding View

The Bidding View is the primary workspace for creating and managing bids. It contains four main tabs:

### Bid Selector

At the top of the Bidding View, the **Bid Selector Widget** allows you to:

- Select from existing bids using the dropdown
- Create new bids with the **+** button
- View linked entities (VFX Breakdown, Bid Assets, Price List)
- Configure currency settings (symbol and position)

#### Currency Settings

1. Click the **$** button in the Bid Selector
2. Select your currency symbol: $, €, £, or ¥
3. Choose position: Before ($100) or After (100$)
4. Settings are saved per-bid

---

### VFX Breakdown Tab

The VFX Breakdown tab manages scene and shot bidding data with detailed cost estimates.

#### Interface Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ [+ Add Scene] [- Remove] [↻ Refresh]        [Search...]        │
├────────────────────────────────────────────────────────────────┬┤
│ Shot | Scene | Status | Model | Tex | Rig | Anim | Lgt | Comp ││
├────────────────────────────────────────────────────────────────┤│
│ SH_001 | SC_010 | Bid  |  40  | 20  |  -  |  80  | 60  |  40  ││
│ SH_002 | SC_010 | Bid  |  20  | 10  |  -  |  60  | 40  |  30  ││
│ SH_003 | SC_020 | Hold |  -   |  -  |  -  |  -   |  -  |   -  ││
└────────────────────────────────────────────────────────────────┴┘
```

#### Adding Scenes/Shots

1. Click **+ Add Scene** to add a new row
2. Fill in the shot code and scene assignment
3. Enter estimated hours for each discipline:
   - **Model**: 3D modeling hours
   - **Tex**: Texturing hours
   - **Rig**: Rigging hours
   - **Anim**: Animation hours
   - **Lgt**: Lighting hours
   - **FX**: Effects hours
   - **Comp**: Compositing hours

#### Editing Cells

- **Single Click**: Select cell
- **Double Click**: Edit cell value
- **Tab/Enter**: Move to next cell
- Changes sync automatically to ShotGrid in the background

#### Copy/Paste

- **Ctrl+C**: Copy selected cells
- **Ctrl+V**: Paste cells (validates data before pasting)
- Supports multi-cell selection and paste from Excel

#### Status Values

Each shot can have a status:
- **Bid**: Included in the bid
- **Hold**: On hold (not counted in totals)
- **Omit**: Omitted from bid
- **Cut**: Cut from project

#### Undo/Redo

- **Ctrl+Z**: Undo last change
- **Ctrl+Y**: Redo last undone change

---

### Assets Tab

The Assets tab manages bid assets and individual asset items with associated costs.

#### Creating Bid Assets

1. Click **+ Add Bid Assets** button
2. Enter a name for the bid assets group
3. Optionally link to an existing asset from the project
4. Click **Create**

#### Adding Asset Items

1. Select a Bid Assets group
2. Click **+ Add Item**
3. Fill in asset details:
   - **Code**: Asset identifier
   - **Description**: Asset description
   - **Type**: Asset type (Character, Prop, Vehicle, Environment, etc.)
   - **Cost**: Estimated cost

#### Copying Assets

1. Select an existing Bid Assets group
2. Click **Copy From...**
3. Select assets to copy
4. Modify as needed

---

### Rates Tab

The Rates tab manages price lists and line items that define hourly rates for each discipline.

#### Interface Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Price Lists                    │ Line Items                     │
├────────────────────────────────┼────────────────────────────────┤
│ ☑ Standard Rates              │ Code      │ Rate    │ Formula  │
│   Premium Rates                │ Model     │ $150/hr │ =A1*B1   │
│   Discount Rates               │ Texture   │ $120/hr │ =A2*B2   │
│                                │ Animation │ $175/hr │ =A3*B3   │
└────────────────────────────────┴────────────────────────────────┘
```

#### Creating a Price List

1. Click **+ New Price List** button
2. Enter a name for the price list
3. Optionally select a parent price list to inherit from
4. Click **Create**

#### Adding Line Items

1. Select a price list
2. Click **+ Add Line Item**
3. Enter the discipline code and hourly rate
4. Optionally add a formula for calculated pricing

#### Formula Support

Line items support Excel-compatible formulas:
- Cell references: `=A1`, `=B2`
- Basic math: `=A1*B1+C1`
- Functions: `=SUM(A1:A10)`, `=IF(A1>100,A1*0.9,A1)`

#### Copying Price Lists

1. Select an existing price list
2. Click **Copy Price List**
3. Enter a new name
4. Modify rates as needed

---

### Costs Tab

The Costs tab provides a comprehensive view of all costs associated with the bid.

#### Cost Categories

1. **VFX Shot Work Costs**: Calculated from VFX Breakdown × Rate Card
2. **Asset Costs**: Sum of all asset item costs
3. **Line Item Costs**: Additional line items with formulas

#### Viewing Cost Details

- Click on any cost category to expand details
- Costs are automatically calculated and updated
- Currency formatting follows bid settings

#### Totals Bar

The bottom of the Costs tab displays running totals:
- **VFX Total**: Sum of all VFX work
- **Assets Total**: Sum of all asset costs
- **Grand Total**: Combined total for the bid

---

## Packages View

The Packages view allows you to create and manage data packages for vendor delivery.

### Interface Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Packages List        │ Package Contents                        │
├──────────────────────┼──────────────────────────────────────────┤
│ ☐ RFQ_2024_Package  │ ├─ manifest.json                         │
│ ☑ VFX_Breakdown_v1  │ ├─ vfx_breakdown/                        │
│   Assets_Package     │ │  ├─ scenes.json                        │
│                      │ │  └─ shots.json                         │
│                      │ └─ assets/                               │
│                      │    └─ items.json                         │
└──────────────────────┴──────────────────────────────────────────┘
```

### Creating a Package

1. Click **+ Create Package** button
2. Select which data to include:
   - ☑ VFX Breakdown
   - ☑ Bid Assets
   - ☑ Price List
   - ☑ Images/Documents
3. Enter a package name
4. Click **Create**

### Package Contents

Each package contains:
- **manifest.json**: Package metadata (name, date, version)
- **Entity Data**: JSON files with bid, breakdown, and asset data
- **Attachments**: Images and documents if selected

### Previewing Packages

- Click a package to view its contents in the tree view
- Double-click files to preview (images, documents)
- Expand folders to see nested contents

### Managing Packages

- **Rename**: Right-click → Rename
- **Delete**: Right-click → Delete
- **Export**: Click **Export** to save to a folder

---

## Delivery View

The Delivery view handles sharing packages with assigned vendors.

### Interface Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Assigned Vendors          │ Delivery Status                     │
├───────────────────────────┼─────────────────────────────────────┤
│ ☑ Vendor A               │ Package: VFX_Breakdown_v1           │
│ ☑ Vendor B               │ Status: Ready to Send               │
│ ☐ Vendor C               │ [📤 Upload to Drive] [📧 Send Link] │
└───────────────────────────┴─────────────────────────────────────┘
```

### Selecting Vendors

1. Check the vendors who should receive the package
2. Only vendors assigned to the RFQ are available

### Sharing Packages

#### Manual Export

1. Select a package
2. Click **Export Package**
3. Choose a destination folder
4. The package will be zipped for easy sharing

#### Google Drive Upload (if configured)

1. Select a package and vendors
2. Click **Upload to Drive**
3. Progress will be shown during upload
4. Share links will be generated automatically

### Delivery Status

Track the status of each delivery:
- **Pending**: Not yet sent
- **Uploading**: Currently uploading to Drive
- **Sent**: Successfully delivered
- **Failed**: Error during delivery (click for details)

---

## Settings and Configuration

Access settings by clicking the gear icon in the top-right corner.

### General Settings

| Setting | Description |
|---------|-------------|
| **DPI Scale** | UI scaling factor (1.0, 1.25, 1.5, 2.0) |
| **Default Currency** | Global currency symbol |
| **Thumbnail Cache** | Cache location and expiration |

### ShotGrid Connection

| Setting | Description |
|---------|-------------|
| **ShotGrid URL** | Your ShotGrid instance URL |
| **Script Name** | API script name |
| **API Key** | API key for authentication |

### Column Settings

Customize table column visibility and order:
1. Right-click any table header
2. Select **Configure Columns**
3. Check/uncheck columns to show/hide
4. Drag to reorder
5. Click **Save**

### Sort Templates

Save frequently used sort configurations:
1. Sort the table as desired
2. Click **Save Sort Template**
3. Enter a template name
4. Access saved templates from the dropdown

---

## Keyboard Shortcuts

### General

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save current changes |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+Q` | Quit application |
| `F5` | Refresh from ShotGrid |

### Table Navigation

| Shortcut | Action |
|----------|--------|
| `Tab` | Move to next cell |
| `Shift+Tab` | Move to previous cell |
| `Enter` | Confirm edit and move down |
| `Escape` | Cancel current edit |
| `Ctrl+C` | Copy selection |
| `Ctrl+V` | Paste |
| `Ctrl+A` | Select all |

### Selection

| Shortcut | Action |
|----------|--------|
| `Click` | Select single cell |
| `Shift+Click` | Extend selection |
| `Ctrl+Click` | Add to selection |
| `Arrow Keys` | Navigate cells |

---

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to ShotGrid

**Solutions**:
1. Verify your internet connection
2. Check ShotGrid URL is correct (include `https://`)
3. Confirm API credentials are valid
4. Check if ShotGrid is accessible from your network

### Data Not Syncing

**Problem**: Changes not appearing in ShotGrid

**Solutions**:
1. Check the status bar for sync errors
2. Click **Refresh** to force a sync
3. Verify you have write permissions in ShotGrid
4. Check the application logs for error details

### UI Scaling Issues

**Problem**: Interface elements appear too small/large

**Solutions**:
1. Go to Settings → General
2. Adjust the **DPI Scale** value
3. Restart the application for changes to take effect

### Formula Errors

**Problem**: Formula cells show errors

**Solutions**:
1. Check for circular references (A1 referencing A1)
2. Verify cell references exist (A1, B2, etc.)
3. Ensure proper formula syntax (start with `=`)
4. Check for division by zero

### Package Export Failures

**Problem**: Cannot export or zip packages

**Solutions**:
1. Verify destination folder is writable
2. Ensure sufficient disk space
3. Close any applications using the package files
4. Try a different destination folder

### Google Drive Upload Issues

**Problem**: Cannot upload to Google Drive

**Solutions**:
1. Verify Google API credentials are configured
2. Re-authenticate if token has expired
3. Check internet connection
4. Ensure you have Drive write permissions

---

## Appendix

### Data Entities Reference

| Entity Type | ShotGrid ID | Description |
|-------------|-------------|-------------|
| RFQ | CustomEntity01 | Request for Quote container |
| Bidding Scene | CustomEntity02 | VFX scene/shot breakdown |
| Line Item | CustomEntity03 | Price list line item |
| Vendor | CustomEntity05 | Vendor information |
| Bid | CustomEntity06 | Bid/proposal |
| Asset Item | CustomEntity07 | Individual asset in bid |
| Bid Assets | CustomEntity08 | Asset bidding group |
| Price List | CustomEntity10 | Pricing template |

### Settings File Location

User settings are stored at:
```
~/.ff_bidding_app/settings.json
```

### Log Files

Application logs are stored at:
```
<app_directory>/logs/ff_package_manager_<timestamp>.log
```

### Support

For issues and feature requests, please visit:
https://github.com/anthropics/claude-code/issues

---

*Version: 0.0.1+dev*
*Last Updated: January 2026*
