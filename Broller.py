import tkinter as tk
from tkinter import ttk, messagebox
import random
import re

# --- 1. CONNECT TO RESOLVE ---
try:
    resolve = app.GetResolve()
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    media_pool = project.GetMediaPool()
    
    timeline_fps = project.GetSetting("timelineFrameRate")
    FPS = float(timeline_fps) if timeline_fps else 24.0
    
except NameError:
    print("Error: 'app' not found. Please run this script INSIDE DaVinci Resolve.")
    resolve, project, media_pool = None, None, None
    FPS = 24.0

# --- HELPER: Timecode to Frames ---
def parse_timecode_to_frames(timecode_str):
    try:
        parts = re.split('[:;]', timecode_str)
        if len(parts) != 4: return 0
        h, m, s, f = map(int, parts)
        return int((h * 3600 + m * 60 + s) * FPS + f)
    except Exception:
        return 0

# --- MAIN LOGIC ---
class BRollGenerator:
    # Color scheme
    BG_DARK = "#1e1e1e"
    BG_MEDIUM = "#2d2d2d"
    BG_LIGHT = "#3c3c3c"
    FG_PRIMARY = "#ffffff"
    FG_SECONDARY = "#a0a0a0"
    ACCENT = "#4a9eff"
    ACCENT_HOVER = "#6bb3ff"

    def __init__(self, root):
        self.root = root
        self.root.title("B-Roll Generator")
        self.root.geometry("480x680")
        self.root.configure(bg=self.BG_DARK)
        self.root.resizable(True, True)
        self.root.minsize(400, 500)

        self.clip_configs = {}
        self.used_segments = {}

        # Configure ttk styles
        self.setup_styles()
        self.setup_ui()
        self.scan_media_pool()

    def setup_styles(self):
        """Configure ttk widget styles for consistent appearance"""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("TCombobox",
                       fieldbackground=self.BG_LIGHT,
                       background=self.BG_LIGHT,
                       foreground=self.FG_PRIMARY)

    def log(self, message):
        """Prints to console and updates UI label"""
        print(f"[LOG] {message}")
        self.lbl_status.config(text=message)
        self.root.update()

    def truncate_filename(self, name, max_length=35):
        """Truncate filename with ellipsis in the middle if too long"""
        if len(name) <= max_length:
            return name
        # Keep extension visible
        if '.' in name:
            base, ext = name.rsplit('.', 1)
            available = max_length - len(ext) - 4  # 4 for "..." and "."
            if available > 6:
                half = available // 2
                return f"{base[:half]}...{base[-half:]}.{ext}"
        # Fallback: simple truncation
        half = (max_length - 3) // 2
        return f"{name[:half]}...{name[-half:]}"

    def setup_ui(self):
        # Main container with padding
        main_frame = tk.Frame(self.root, bg=self.BG_DARK)
        main_frame.pack(fill="both", expand=True, padx=12, pady=8)

        # === SOURCE CLIPS SECTION ===
        clips_header = tk.Frame(main_frame, bg=self.BG_DARK)
        clips_header.pack(fill="x", pady=(0, 6))

        tk.Label(clips_header, text="Source Clips", font=("Arial", 11, "bold"),
                bg=self.BG_DARK, fg=self.FG_PRIMARY).pack(side="left")

        self.lbl_count = tk.Label(clips_header, text="0 selected",
                                  font=("Arial", 9), bg=self.BG_DARK, fg=self.FG_SECONDARY)
        self.lbl_count.pack(side="right")

        # Clip list container
        list_container = tk.Frame(main_frame, bg=self.BG_MEDIUM, bd=0)
        list_container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(list_container, bg=self.BG_MEDIUM,
                               highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(list_container, orient="vertical",
                                      command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.BG_MEDIUM)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # Set fixed width for scrollable frame to prevent horizontal expansion
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame,
                                                        anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Bind canvas resize to update scrollable frame width
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Selection buttons
        btn_frame = tk.Frame(main_frame, bg=self.BG_DARK)
        btn_frame.pack(fill="x", pady=(6, 0))

        btn_style = {"font": ("Arial", 9), "bg": self.BG_LIGHT, "fg": self.FG_PRIMARY,
                    "activebackground": self.BG_MEDIUM, "activeforeground": self.FG_PRIMARY,
                    "bd": 0, "padx": 12, "pady": 4, "cursor": "hand2"}

        tk.Button(btn_frame, text="Select All", command=self.select_all,
                 **btn_style).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Select None", command=self.select_none,
                 **btn_style).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="Refresh", command=self.scan_media_pool,
                 **btn_style).pack(side="left")

        # === SETTINGS SECTION ===
        settings_frame = tk.Frame(main_frame, bg=self.BG_MEDIUM, bd=0)
        settings_frame.pack(fill="x", pady=(12, 0))

        settings_inner = tk.Frame(settings_frame, bg=self.BG_MEDIUM)
        settings_inner.pack(fill="x", padx=12, pady=10)

        # Row 1: Destination Track
        row1 = tk.Frame(settings_inner, bg=self.BG_MEDIUM)
        row1.pack(fill="x", pady=(0, 8))

        tk.Label(row1, text="Destination Track", font=("Arial", 9),
                bg=self.BG_MEDIUM, fg=self.FG_PRIMARY).pack(side="left")

        self.track_var = tk.StringVar()
        self.combo_tracks = ttk.Combobox(row1, textvariable=self.track_var,
                                         state="readonly", width=14)
        self.combo_tracks.pack(side="right")

        # Row 2: Clip Duration
        row2 = tk.Frame(settings_inner, bg=self.BG_MEDIUM)
        row2.pack(fill="x", pady=(0, 8))

        tk.Label(row2, text="Clip Duration (sec)", font=("Arial", 9),
                bg=self.BG_MEDIUM, fg=self.FG_PRIMARY).pack(side="left")

        dur_inputs = tk.Frame(row2, bg=self.BG_MEDIUM)
        dur_inputs.pack(side="right")

        self.entry_min = tk.Entry(dur_inputs, width=5, bg=self.BG_LIGHT,
                                  fg=self.FG_PRIMARY, insertbackground=self.FG_PRIMARY, bd=1)
        self.entry_min.insert(0, "2")
        self.entry_min.pack(side="left")

        tk.Label(dur_inputs, text=" – ", font=("Arial", 9),
                bg=self.BG_MEDIUM, fg=self.FG_SECONDARY).pack(side="left")

        self.entry_max = tk.Entry(dur_inputs, width=5, bg=self.BG_LIGHT,
                                  fg=self.FG_PRIMARY, insertbackground=self.FG_PRIMARY, bd=1)
        self.entry_max.insert(0, "5")
        self.entry_max.pack(side="left")

        # Row 3: Duplicate Prevention
        row3 = tk.Frame(settings_inner, bg=self.BG_MEDIUM)
        row3.pack(fill="x")

        self.prevent_duplicates = tk.BooleanVar(value=False)
        chk_dup = tk.Checkbutton(row3, text="Prevent duplicate segments",
                                 variable=self.prevent_duplicates, font=("Arial", 9),
                                 bg=self.BG_MEDIUM, fg=self.FG_PRIMARY,
                                 activebackground=self.BG_MEDIUM, activeforeground=self.FG_PRIMARY,
                                 selectcolor=self.BG_LIGHT)
        chk_dup.pack(side="left")

        # === TARGET DURATION SECTION ===
        target_frame = tk.Frame(main_frame, bg=self.BG_MEDIUM, bd=0)
        target_frame.pack(fill="x", pady=(8, 0))

        target_inner = tk.Frame(target_frame, bg=self.BG_MEDIUM)
        target_inner.pack(fill="x", padx=12, pady=10)

        self.dur_mode = tk.StringVar(value="match")

        radio_style = {"font": ("Arial", 9), "bg": self.BG_MEDIUM, "fg": self.FG_PRIMARY,
                      "activebackground": self.BG_MEDIUM, "activeforeground": self.FG_PRIMARY,
                      "selectcolor": self.BG_LIGHT}

        rb1 = tk.Radiobutton(target_inner, text="Match Track 1 length",
                            variable=self.dur_mode, value="match", **radio_style)
        rb1.pack(anchor="w")

        fixed_row = tk.Frame(target_inner, bg=self.BG_MEDIUM)
        fixed_row.pack(anchor="w", pady=(4, 0))

        rb2 = tk.Radiobutton(fixed_row, text="Fixed duration:",
                            variable=self.dur_mode, value="fixed", **radio_style)
        rb2.pack(side="left")

        self.entry_total = tk.Entry(fixed_row, width=6, bg=self.BG_LIGHT,
                                    fg=self.FG_PRIMARY, insertbackground=self.FG_PRIMARY, bd=1)
        self.entry_total.insert(0, "60")
        self.entry_total.pack(side="left", padx=(4, 0))

        tk.Label(fixed_row, text="sec", font=("Arial", 9),
                bg=self.BG_MEDIUM, fg=self.FG_SECONDARY).pack(side="left", padx=(4, 0))

        # === GENERATE BUTTON ===
        self.btn_run = tk.Button(main_frame, text="Generate B-Roll",
                                font=("Arial", 11, "bold"), bg=self.ACCENT, fg=self.FG_PRIMARY,
                                activebackground=self.ACCENT_HOVER, activeforeground=self.FG_PRIMARY,
                                bd=0, pady=10, cursor="hand2", command=self.generate)
        self.btn_run.pack(fill="x", pady=(12, 0))

        # === STATUS BAR ===
        self.lbl_status = tk.Label(self.root, text="Ready", font=("Arial", 8),
                                   bg=self.BG_LIGHT, fg=self.FG_SECONDARY,
                                   anchor="w", padx=8, pady=4)
        self.lbl_status.pack(side="bottom", fill="x")

    def _on_canvas_configure(self, event):
        """Update scrollable frame width when canvas is resized"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def update_count(self):
        count = sum(1 for name, cfg in self.clip_configs.items() if cfg['var'].get())
        total = len(self.clip_configs)
        self.lbl_count.config(text=f"{count} of {total} selected")

    def select_all(self):
        for name, cfg in self.clip_configs.items():
            cfg['var'].set(True)
            # Show configure button (using grid)
            if 'btn_config' in cfg:
                cfg['btn_config'].grid()
        self.update_count()

    def select_none(self):
        for name, cfg in self.clip_configs.items():
            cfg['var'].set(False)
            # Hide configure button and close config if open
            if 'btn_config' in cfg:
                cfg['btn_config'].grid_remove()
            if cfg['expanded']:
                cfg['config_frame'].pack_forget()
                cfg['expanded'] = False
        self.update_count()

    def toggle_clip_config(self, clip_name):
        """Toggle the visibility of per-clip configuration frame"""
        cfg = self.clip_configs[clip_name]

        # Close any other open config first
        for name, other_cfg in self.clip_configs.items():
            if name != clip_name and other_cfg['expanded']:
                other_cfg['config_frame'].pack_forget()
                other_cfg['expanded'] = False

        if cfg['expanded']:
            cfg['config_frame'].pack_forget()
            cfg['expanded'] = False
        else:
            # Pack config frame right after the clip row (inside the container)
            cfg['config_frame'].pack(fill="x", after=cfg['clip_row'])
            cfg['expanded'] = True

    def reset_clip_range(self, clip_name):
        """Reset clip range to full duration"""
        cfg = self.clip_configs[clip_name]
        cfg['range_start'].set(0.0)
        cfg['range_end'].set(cfg['total_duration'])

    def validate_clip_range(self, clip_name):
        """Validate that start < end and both are within bounds"""
        cfg = self.clip_configs[clip_name]
        start = cfg['range_start'].get()
        end = cfg['range_end'].get()
        duration = cfg['total_duration']

        if start < 0:
            cfg['range_start'].set(0.0)
        if end > duration:
            cfg['range_end'].set(duration)
        if start >= end:
            # Reset to valid range
            cfg['range_start'].set(0.0)
            cfg['range_end'].set(duration)
            messagebox.showwarning("Invalid Range", f"Start time must be less than end time.\nResetting to full clip range.")

    def validate_clip_lengths(self):
        """Check if any selected clips have usable range < max duration"""
        try:
            max_duration = float(self.entry_max.get())
        except ValueError:
            return True  # Let generate() handle this error

        short_clips = []

        for name, cfg in self.clip_configs.items():
            if cfg['var'].get() and not cfg['is_still']:  # If selected and not a still image
                usable_range = cfg['range_end'].get() - cfg['range_start'].get()
                if usable_range < max_duration:
                    short_clips.append({
                        'name': name,
                        'usable': usable_range,
                        'required': max_duration
                    })

        if short_clips:
            # Show warning dialog with list, return True if user confirms
            msg = "The following clips are shorter than Max Duration:\n\n"
            for sc in short_clips:
                msg += f"• {sc['name']}: {sc['usable']:.1f}s available\n"
            msg += "\nThese clips will be used at their maximum available length."

            return messagebox.askyesno("Short Clips Detected", msg + "\n\nContinue anyway?")

        return True

    def _has_overlap(self, clip_name, new_start, new_end):
        """Check if [new_start, new_end) overlaps with any used segment of this clip"""
        if clip_name not in self.used_segments:
            return False

        for seg_start, seg_end in self.used_segments[clip_name]:
            # Overlap condition: NOT (new is completely before OR completely after existing)
            if not (new_end <= seg_start or new_start >= seg_end):
                return True

        return False

    def scan_media_pool(self):
        if not media_pool: return

        self.log("Scanning...")

        # Clear existing clips
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.clip_configs = {}
        root_folder = media_pool.GetRootFolder()

        def get_clips_recursive(folder):
            found = []
            clips = folder.GetClipList()
            for clip in clips:
                c_type = clip.GetClipProperty("Type")
                if "Timeline" in c_type:
                    continue
                if "Video" in c_type or "Image" in c_type or "Stills" in c_type:
                    found.append((clip, folder))
            subfolders = folder.GetSubFolderList()
            for sub in subfolders:
                found.extend(get_clips_recursive(sub))
            return found

        all_clips = get_clips_recursive(root_folder)
        self.log(f"Found {len(all_clips)} clips")

        if not all_clips:
            empty_label = tk.Label(self.scrollable_frame, text="No clips found",
                                   font=("Arial", 9), bg=self.BG_MEDIUM, fg=self.FG_SECONDARY)
            empty_label.pack(pady=20)
        else:
            for clip, folder in all_clips:
                clip_name = clip.GetName()
                c_type = clip.GetClipProperty("Type")
                is_still = "Still" in c_type or "Image" in c_type

                # Parse duration
                if is_still:
                    duration_sec = float('inf')
                    duration_str = "∞"
                else:
                    dur = clip.GetClipProperty("Duration")
                    if dur:
                        duration_frames = parse_timecode_to_frames(dur)
                        duration_sec = duration_frames / FPS
                        minutes = int(duration_sec // 60)
                        seconds = int(duration_sec % 60)
                        duration_str = f"{minutes}:{seconds:02d}"
                    else:
                        duration_sec = 0
                        duration_str = "0:00"

                # Create container frame
                container = tk.Frame(self.scrollable_frame, bg=self.BG_MEDIUM)
                container.pack(fill="x", pady=1)

                # Main clip row using grid for fixed positioning
                clip_row = tk.Frame(container, bg=self.BG_MEDIUM)
                clip_row.pack(fill="x", padx=8, pady=4)
                clip_row.grid_columnconfigure(1, weight=1)  # Make middle column expand

                # Checkbox (column 0)
                var = tk.BooleanVar(value=False)

                # Truncate filename for display
                display_name = self.truncate_filename(clip_name)

                # Configure button style
                btn_style = {"font": ("Arial", 8), "bg": self.BG_LIGHT, "fg": self.FG_PRIMARY,
                            "activebackground": self.BG_DARK, "activeforeground": self.FG_PRIMARY,
                            "bd": 0, "padx": 8, "pady": 2, "cursor": "hand2"}

                # Configure button (column 2) - always in grid, visibility controlled
                btn_config = tk.Button(clip_row, text="Configure",
                                       command=lambda cn=clip_name: self.toggle_clip_config(cn),
                                       **btn_style)
                # Place in grid but hide initially
                btn_config.grid(row=0, column=2, padx=(8, 0))
                btn_config.grid_remove()  # Hide but keep position

                # Callback to show/hide configure button
                def on_checkbox_toggle(v=var, btn=btn_config, cn=clip_name):
                    if v.get():
                        btn.grid()  # Show button (position preserved)
                    else:
                        btn.grid_remove()  # Hide button (position preserved)
                        # Also close config if open
                        if cn in self.clip_configs and self.clip_configs[cn]['expanded']:
                            self.clip_configs[cn]['config_frame'].pack_forget()
                            self.clip_configs[cn]['expanded'] = False
                    self.update_count()

                chk = tk.Checkbutton(clip_row, text=f"{display_name}  ({duration_str})",
                                     variable=var, anchor="w", command=on_checkbox_toggle,
                                     font=("Arial", 9), bg=self.BG_MEDIUM, fg=self.FG_PRIMARY,
                                     activebackground=self.BG_MEDIUM, activeforeground=self.FG_PRIMARY,
                                     selectcolor=self.BG_LIGHT)
                chk.grid(row=0, column=0, columnspan=2, sticky="w")

                # Configuration panel (hidden by default)
                config_frame = tk.Frame(container, bg=self.BG_LIGHT)

                config_inner = tk.Frame(config_frame, bg=self.BG_LIGHT)
                config_inner.pack(fill="x", padx=12, pady=8)

                if is_still:
                    # Still images - show info only
                    tk.Label(config_inner, text="Still image (no range settings)",
                            font=("Arial", 8), bg=self.BG_LIGHT, fg=self.FG_SECONDARY).pack(side="left")
                    range_start = tk.DoubleVar(value=0.0)
                    range_end = tk.DoubleVar(value=999999.0)
                else:
                    # Video clips - range inputs
                    range_start = tk.DoubleVar(value=0.0)
                    range_end = tk.DoubleVar(value=duration_sec)

                    entry_style = {"width": 7, "bg": self.BG_MEDIUM, "fg": self.FG_PRIMARY,
                                  "insertbackground": self.FG_PRIMARY, "bd": 1}

                    tk.Label(config_inner, text="Use range:", font=("Arial", 8),
                            bg=self.BG_LIGHT, fg=self.FG_SECONDARY).pack(side="left")

                    entry_start = tk.Entry(config_inner, textvariable=range_start, **entry_style)
                    entry_start.pack(side="left", padx=(8, 0))
                    entry_start.bind("<FocusOut>", lambda e, cn=clip_name: self.validate_clip_range(cn))

                    tk.Label(config_inner, text="–", font=("Arial", 8),
                            bg=self.BG_LIGHT, fg=self.FG_SECONDARY).pack(side="left", padx=4)

                    entry_end = tk.Entry(config_inner, textvariable=range_end, **entry_style)
                    entry_end.pack(side="left")
                    entry_end.bind("<FocusOut>", lambda e, cn=clip_name: self.validate_clip_range(cn))

                    tk.Label(config_inner, text="sec", font=("Arial", 8),
                            bg=self.BG_LIGHT, fg=self.FG_SECONDARY).pack(side="left", padx=(4, 12))

                    btn_reset = tk.Button(config_inner, text="Reset",
                                         command=lambda cn=clip_name: self.reset_clip_range(cn),
                                         font=("Arial", 8), bg=self.BG_MEDIUM, fg=self.FG_PRIMARY,
                                         activebackground=self.BG_DARK, activeforeground=self.FG_PRIMARY,
                                         bd=0, padx=6, pady=1, cursor="hand2")
                    btn_reset.pack(side="left")

                # Store configuration
                self.clip_configs[clip_name] = {
                    'var': var,
                    'clip': clip,
                    'folder': folder,
                    'total_duration': duration_sec,
                    'range_start': range_start,
                    'range_end': range_end,
                    'config_frame': config_frame,
                    'clip_row': clip_row,
                    'container': container,
                    'btn_config': btn_config,
                    'expanded': False,
                    'is_still': is_still
                }

        self.update_count()

        # Update track options
        try:
            timeline = project.GetCurrentTimeline()
            if timeline:
                track_count = timeline.GetTrackCount("video")
                options = ["New Track"]
                for i in range(2, track_count + 1):
                    options.append(f"Track {i}")
                self.combo_tracks['values'] = options
                self.combo_tracks.current(0)
        except Exception:
            self.combo_tracks['values'] = ["New Track"]
            self.combo_tracks.current(0)

        self.log("Ready")

    def generate(self):
        """Orchestrator - validates and delegates to sub-methods"""
        timeline = self._validate_and_get_timeline()
        if not timeline:
            return

        dest_track_idx, current_pos = self._setup_destination_track(timeline)
        if dest_track_idx == 0:
            return

        frames_to_fill = self._calculate_fill_duration(timeline, current_pos)
        if frames_to_fill <= 0:
            return

        valid_clips = self._prepare_clip_pool()
        if not valid_clips:
            return

        # Validate clip lengths before generation
        if not self.validate_clip_lengths():
            return  # User cancelled after seeing warning

        # Get min/max settings
        try:
            min_f = int(float(self.entry_min.get()) * FPS)
            max_f = int(float(self.entry_max.get()) * FPS)
        except ValueError:
            messagebox.showerror("Error", "Invalid min/max seconds.")
            return

        # Run the generation loop
        self._run_generation_loop(timeline, dest_track_idx, current_pos,
                                  frames_to_fill, valid_clips, min_f, max_f)

    def _validate_and_get_timeline(self):
        """Check project connection and timeline availability"""
        if not project:
            messagebox.showerror("Error", "Not connected to Resolve.")
            return None

        timeline = project.GetCurrentTimeline()
        if not timeline:
            messagebox.showerror("Error", "Please open a timeline first.")
            return None

        return timeline

    def _get_track_end_time(self, timeline, track_idx):
        """Get the end frame of a specific track"""
        items = timeline.GetItemListInTrack("video", track_idx)
        if not items:
            return timeline.GetStartFrame()
        return max([item.GetEnd() for item in items])

    def _setup_destination_track(self, timeline):
        """Create new track or find existing, return (track_idx, start_pos)"""
        selection = self.track_var.get()
        dest_track_idx = 0
        current_timeline_pos = timeline.GetStartFrame()

        if selection == "New Track":
            timeline.AddTrack("video")
            timeline.AddTrack("audio")  # Adding matched audio track
            dest_track_idx = timeline.GetTrackCount("video")
            current_timeline_pos = timeline.GetStartFrame()
        else:
            try:
                # Parse "Track n" -> n
                dest_track_idx = int(selection.split(" ")[1])

                # Start adding from the END of this track
                current_timeline_pos = self._get_track_end_time(timeline, dest_track_idx)
            except:
                messagebox.showerror("Error", f"Invalid track selection: {selection}")
                return 0, 0

        self.log(f"Targeting Video Track {dest_track_idx} starting at frame {current_timeline_pos}")
        return dest_track_idx, current_timeline_pos

    def _calculate_fill_duration(self, timeline, current_pos):
        """Determine frames_to_fill based on match/fixed mode"""
        frames_to_fill = 0

        if self.dur_mode.get() == "match":
            track1_end = self._get_track_end_time(timeline, 1)
            frames_to_fill = track1_end - current_pos
            if frames_to_fill <= 0:
                messagebox.showinfo("Info", "Selected track is already longer than Track 1. Nothing to add.")
                return 0
        else:
            # Fixed Seconds
            try:
                frames_to_fill = int(float(self.entry_total.get()) * FPS)
            except ValueError:
                messagebox.showerror("Error", "Invalid total seconds.")
                return 0

        return frames_to_fill

    def _prepare_clip_pool(self):
        """Validate selected clips and build working list"""
        source_clips = [(cfg['clip'], cfg['folder'])
                       for name, cfg in self.clip_configs.items() if cfg['var'].get()]

        if not source_clips:
            messagebox.showwarning("Warning", "No clips selected!")
            return []

        valid_clips = []
        for clip, folder in source_clips:
            clip_name = clip.GetName()
            if clip_name in self.clip_configs:
                valid_clips.append((clip, folder))

        if not valid_clips:
            messagebox.showerror("Error", "No valid clips found.")
            return []

        return valid_clips

    def _run_generation_loop(self, timeline, dest_track_idx, current_pos,
                            frames_to_fill, valid_clips, min_f, max_f):
        """Main placement loop with duplicate tracking"""
        # Initialize tracking
        self.used_segments = {}
        filled_so_far = 0
        clips_added = 0
        consecutive_failures = 0

        try:
            while filled_so_far < frames_to_fill:
                if not valid_clips:
                    self.log("All clips exhausted!")
                    break

                # 1. Select random clip from pool
                clip, folder = random.choice(valid_clips)
                clip_name = clip.GetName()
                cfg = self.clip_configs[clip_name]

                # 2. Calculate usable range (respecting user-defined limits)
                if cfg['is_still']:
                    # Still image - no range restrictions
                    slice_frames = random.randint(min_f, max_f)
                    slice_frames = min(slice_frames, frames_to_fill - filled_so_far)

                    # Record Frame = Start pos + what we've added so far
                    record_pos = current_pos + filled_so_far

                    clip_info = {
                        "mediaPoolItem": clip,
                        "mediaType": 1,
                        "trackIndex": dest_track_idx,
                        "recordFrame": record_pos
                    }

                    # Change directory to support bins
                    media_pool.SetCurrentFolder(folder)

                    # Append slice to timeline
                    items = media_pool.AppendToTimeline([clip_info])

                    if items and items[0]:
                        items[0].Resize(slice_frames)

                        filled_so_far += slice_frames
                        clips_added += 1
                        consecutive_failures = 0

                        progress = (filled_so_far / frames_to_fill) * 100
                        self.log(f"Added {clip_name} on V{dest_track_idx} ({progress:.1f}%)")
                    else:
                        consecutive_failures += 1
                        self.log(f"FAILED to append {clip_name}")
                        if consecutive_failures >= 5:
                            break

                    continue

                # 3. For video clips: respect range constraints
                range_start_frames = int(cfg['range_start'].get() * FPS)
                range_end_frames = int(cfg['range_end'].get() * FPS)
                usable_duration = range_end_frames - range_start_frames

                if usable_duration <= 0:
                    # Skip clips with invalid ranges
                    valid_clips.remove((clip, folder))
                    self.log(f"Skipping {clip_name} - invalid range")
                    continue

                # 4. Determine slice size
                slice_frames = random.randint(min_f, max_f)
                slice_frames = min(slice_frames, usable_duration)
                slice_frames = min(slice_frames, frames_to_fill - filled_so_far)

                # 5. Find non-overlapping segment (if duplicate prevention enabled)
                if self.prevent_duplicates.get():
                    segment_found = False

                    for attempt in range(10):  # Max 10 retries per clip
                        if usable_duration < slice_frames:
                            # Clip too short for desired slice
                            break

                        start_offset = range_start_frames + random.randint(0, usable_duration - slice_frames)
                        end_offset = start_offset + slice_frames

                        # Check for overlap
                        if not self._has_overlap(clip_name, start_offset, end_offset):
                            segment_found = True
                            break

                    if not segment_found:
                        # Clip exhausted - remove from pool and continue with others
                        valid_clips.remove((clip, folder))
                        self.log(f"All segments used for {clip_name}, skipping...")

                        if not valid_clips:
                            # No more clips available
                            self.log("All clips exhausted!")
                            break

                        consecutive_failures = 0  # Reset since this isn't a failure
                        continue
                else:
                    # No duplicate prevention - use any random segment
                    if usable_duration < slice_frames:
                        slice_frames = usable_duration

                    start_offset = range_start_frames + random.randint(0, max(0, usable_duration - slice_frames))
                    end_offset = start_offset + slice_frames

                # 6. Record Frame = Start pos + what we've added so far
                record_pos = current_pos + filled_so_far

                clip_info = {
                    "mediaPoolItem": clip,
                    "startFrame": start_offset,
                    "endFrame": end_offset,
                    "mediaType": 1,
                    "trackIndex": dest_track_idx,
                    "recordFrame": record_pos
                }

                # Change directory to support bins
                media_pool.SetCurrentFolder(folder)

                # Append slice to timeline
                items = media_pool.AppendToTimeline([clip_info])

                if items and items[0]:
                    filled_so_far += slice_frames
                    clips_added += 1
                    consecutive_failures = 0

                    # Record used segment
                    if self.prevent_duplicates.get():
                        if clip_name not in self.used_segments:
                            self.used_segments[clip_name] = []
                        self.used_segments[clip_name].append((start_offset, end_offset))

                    progress = (filled_so_far / frames_to_fill) * 100
                    self.log(f"Added {clip_name} on V{dest_track_idx} ({progress:.1f}%)")
                else:
                    consecutive_failures += 1
                    self.log(f"FAILED to append {clip_name}")
                    if consecutive_failures >= 5:
                        break

            messagebox.showinfo("Done", f"Added {clips_added} clips to V{dest_track_idx}")
        except Exception as e:
            self.log(f"CRITICAL ERROR: {str(e)}")
            messagebox.showerror("Error", str(e))
        finally:
            # Restore media pool folder to root
            if media_pool:
                root = media_pool.GetRootFolder()
                media_pool.SetCurrentFolder(root)

            self.log("Done.")

if __name__ == "__main__":
    if resolve:
        root = tk.Tk()
        root.attributes("-topmost", True) 
        app_gui = BRollGenerator(root)
        root.mainloop()