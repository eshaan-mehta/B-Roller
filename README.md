# DaVinci Resolve B-Roll Generator

This is a Python script for DaVinci Resolve that automatically generates B-roll footage using clips from your Media Pool. This tool speeds up editing workflows by eliminating the need to manually scrub through clips for BRoll. Just select the videos you want to create B-roll from, your desired duration, length and destination track and the tool will insert a variety of clips from your files.

## Features

* **Native GUI:** Built with `tkinter`, provides and easy-to-use to use interface in Davinci Resolve
* **Smart Media Filtering:** Automatically detects video and static image files while ignoring Timelines and Audio-only files to prevent errors.
* **Flexible Track Targeting:**
    * Create a **New Track** automatically.
    * Append to any **Existing Track** (excluding Track 1 to protect the A-Roll/Main Edit).
* **Intelligent Gap Filling:**
    * **Match Track 1:** Automatically calculates the duration of your main edit and fills the B-roll track to match.
    * **Fixed Duration:** Specify an exact length (e.g., 60 seconds) to generate.
    * **Smart Append:** If adding to an existing track, it detects the current endpoint and appends from there.
* **Randomization Engine:**
    * Selects random start points within source clips (random seeking).
    * Varies clip duration based on user-defined Min/Max bounds.
* **Safe Insertion:** Uses "Video Only" insertion logic to prevent audio track collisions and sync issues.

## Prerequisites

* **DaVinci Resolve** (Free or Studio version 16+).
* **Python 3.6+** (Usually pre-installed with DaVinci Resolve).

> **Note:** This script relies on the DaVinci Resolve Scripting API (`DaVinciResolveScript`). It must be run from *inside* Resolve to function correctly.

## Installation

1.  Download the `BRoller.py` file from this repository.
2.  Move the file to the DaVinci Resolve **Utility Scripts** folder:

    * **Windows:**
        `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Fusion\Scripts\Utility\`
    * **macOS:**
        `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`
    * **Linux:**
        `/opt/resolve/Fusion/Scripts/Utility/`

3.  Restart DaVinci Resolve.

## Usage

1.  Open your project in DaVinci Resolve and open the **Edit Page**.
2.  Go to the top menu bar: **Workspace** > **Scripts** > **BRoller**.
3.  The GUI window will appear.

### Step-by-Step Workflow

1.  **Select Clips:** The window lists all valid video/image clips found in your Media Pool. Check the boxes next to the clips you want to include in the randomization pool.
2.  **Choose Destination:**
    * **New Track:** Creates a new Video and Audio track and places footage there.
    * **Track X:** Appends footage to the end of an existing track.
3.  **Configure Timing:**
    * **Min/Max Sec:** Determines how long each slice of video will be (e.g., between 2s and 5s).
    * **Target Duration:** Choose to match the length of your main edit (Track 1) or generate a specific amount of footage.
4.  **Generate:** Click **GENERATE B-ROLL TRACK**.

## How It Works

This script interacts with the Resolve API to perform operations that would be tedious by hand:

1.  **Scanning:** It recurses through the Media Pool folders to build a list of valid `MediaPoolItems`.
2.  **Calculation:** It determines the timeline's start timecode and the target fill length.
3.  **The Loop:**
    * It picks a random clip from your selection.
    * It calculates a random duration from the specified bounds.
    * It randomly seeks to a point within a selected file to start the slice, ensuring the slice fits within the file bounds, and provides a variety of clips.
4.  **Insertion:** It uses the `AppendToTimeline` API method with a constructed dictionary to add the slice to the destination track.

## Known Limitations

* **API Performance:** Large Media Pools (1000+ items) may take a moment to scan upon opening the script.
* **Static Images:** While images are supported, they cannot be "slipped" (random seek) as they have no timecode. The script simply resizes them to the requested duration.
* **Track 1 Protection:** The script intentionally disables selecting "Track 1" as a destination to prevent accidental overwriting of the main timeline.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
