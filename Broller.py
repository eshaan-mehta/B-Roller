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
    def __init__(self, root):
        self.root = root
        self.root.title("B-Roll Generator (Timecode Fix)")
        self.root.geometry("500x700")

        self.clip_configs = {}  # New data structure for clip configuration
        self.used_segments = {}  # Track used segments for duplicate prevention

        self.setup_ui()
        self.scan_media_pool()

    def log(self, message):
        """Prints to console and updates UI label"""
        print(f"[LOG] {message}")
        self.lbl_status.config(text=message)
        self.root.update()

    def setup_ui(self):
        # 1. Clip Selection Area
        lbl_list = tk.Label(self.root, text="1. Select Source Clips:", font=("Arial", 10, "bold"))
        lbl_list.pack(pady=(10, 5), anchor="w", padx=10)
        
        list_container = tk.Frame(self.root, bd=1, relief="sunken")
        list_container.pack(fill="both", expand=True, padx=10)
        
        self.canvas = tk.Canvas(list_container)
        self.scrollbar = tk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Selection Tools
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Button(btn_frame, text="Select All", command=self.select_all).pack(side="left", padx=(0, 5))
        tk.Button(btn_frame, text="Select None", command=self.select_none).pack(side="left", padx=(0, 5))
        tk.Button(btn_frame, text="Refresh Clips", command=self.scan_media_pool).pack(side="left")
        self.lbl_count = tk.Label(btn_frame, text="Selected: 0", fg="blue", font=("Arial", 10, "bold"))
        self.lbl_count.pack(side="right")
        
        # 2. Settings Area
        lbl_settings = tk.Label(self.root, text="2. Configuration:", font=("Arial", 10, "bold"))
        lbl_settings.pack(pady=(15, 5), anchor="w", padx=10)
        
        frame_settings = tk.LabelFrame(self.root, text="Clip Settings")
        frame_settings.pack(fill="x", padx=10)
        
        # -- Track Selection (NEW) --
        tk.Label(frame_settings, text="Dest Track:").grid(row=0, column=0, padx=5, pady=5)
        self.track_var = tk.StringVar()
        self.combo_tracks = ttk.Combobox(frame_settings, textvariable=self.track_var, state="readonly", width=15)
        self.combo_tracks.grid(row=0, column=1, columnspan=2, sticky="w")
        
        # -- Min/Max --
        tk.Label(frame_settings, text="Min Sec:").grid(row=1, column=0, padx=5, pady=5)
        self.entry_min = tk.Entry(frame_settings, width=5)
        self.entry_min.insert(0, "2.0")
        self.entry_min.grid(row=1, column=1, sticky="w")

        tk.Label(frame_settings, text="Max Sec:").grid(row=1, column=2, padx=5, pady=5)
        self.entry_max = tk.Entry(frame_settings, width=5)
        self.entry_max.insert(0, "5.0")
        self.entry_max.grid(row=1, column=3, sticky="w")

        # -- Duplicate Prevention --
        self.prevent_duplicates = tk.BooleanVar(value=False)
        tk.Checkbutton(frame_settings, text="Prevent Duplicate Segments",
                       variable=self.prevent_duplicates).grid(row=2, column=0, columnspan=4,
                                                              sticky="w", padx=5, pady=5)
        
        # 3. Track Duration
        frame_dur = tk.LabelFrame(self.root, text="Target Duration Logic")
        frame_dur.pack(fill="x", padx=10, pady=10)
        
        self.dur_mode = tk.StringVar(value="match")
        
        rb1 = tk.Radiobutton(frame_dur, text="Fill to Match Track 1 End", variable=self.dur_mode, value="match")
        rb1.pack(anchor="w")
        
        frame_manual = tk.Frame(frame_dur)
        frame_manual.pack(anchor="w")
        
        rb2 = tk.Radiobutton(frame_manual, text="Add Fixed Seconds:", variable=self.dur_mode, value="fixed")
        rb2.pack(side="left")
        
        self.entry_total = tk.Entry(frame_manual, width=8)
        self.entry_total.insert(0, "60")
        self.entry_total.pack(side="left", padx=5)

        # 4. Status Bar
        self.lbl_status = tk.Label(self.root, text="Ready", bd=1, relief="sunken", anchor="w")
        self.lbl_status.pack(side="bottom", fill="x")

        # 5. Generate Button
        self.btn_run = tk.Button(self.root, text="GENERATE B-ROLL", bg="white", font=("Arial", 11, "bold"),
                                    command=self.generate)
        self.btn_run.pack(fill="x", padx=20, pady=10, ipady=5)
        
    def update_count(self):
        count = sum(1 for name, cfg in self.clip_configs.items() if cfg['var'].get())
        total = len(self.clip_configs)
        self.lbl_count.config(text=f"Selected: {count} / {total}")

    def select_all(self):
        for name, cfg in self.clip_configs.items():
            cfg['var'].set(True)
            if 'btn_config' in cfg:
                cfg['btn_config'].grid()
        self.update_count()

    def select_none(self):
        for name, cfg in self.clip_configs.items():
            cfg['var'].set(False)
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
            cfg['config_frame'].pack(fill="x", padx=20, pady=2, after=cfg['clip_row'])
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

        self.log("Scanning Media Pool & Tracks...")
        
        # 1. Update Clips
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        self.clip_configs = {}
        root_folder = media_pool.GetRootFolder()

        def get_clips_recursive(folder):
            found = []
            clips = folder.GetClipList()
            for clip in clips:
                c_type = clip.GetClipProperty("Type")
                if "Timeline" in c_type: continue
                if "Video" in c_type or "Image" in c_type or "Stills" in c_type:
                    found.append((clip, folder))
            subfolders = folder.GetSubFolderList()
            for sub in subfolders:
                found.extend(get_clips_recursive(sub))
            return found

        all_clips = get_clips_recursive(root_folder)
        self.log(f"Found {len(all_clips)} clips.")

        if not all_clips:
            tk.Label(self.scrollable_frame, text="No Video Clips Found!").pack()
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

                # Create container frame that holds both clip row and config
                container = tk.Frame(self.scrollable_frame)
                container.pack(fill="x", padx=5, pady=2)

                # Create main clip row frame using grid for fixed button position
                clip_row = tk.Frame(container)
                clip_row.pack(fill="x")
                clip_row.grid_columnconfigure(0, weight=1)

                # Checkbox and label
                var = tk.BooleanVar(value=False)

                chk = tk.Checkbutton(clip_row, text=f"{clip_name} ({duration_str})",
                                     variable=var, anchor="w")
                chk.grid(row=0, column=0, sticky="w")

                # Configure button - always in column 1, toggle visibility with grid_remove
                btn_config = tk.Button(clip_row, text="⚙ Configure", font=("Arial", 8),
                                       command=lambda cn=clip_name: self.toggle_clip_config(cn))
                btn_config.grid(row=0, column=1, padx=5)
                btn_config.grid_remove()  # Hidden initially, position reserved

                # Callback to show/hide configure button based on selection
                def on_checkbox_toggle(v=var, btn=btn_config, cn=clip_name):
                    if v.get():
                        btn.grid()  # Shows in same grid position
                    else:
                        btn.grid_remove()  # Hides but keeps position
                        # Also close config if open
                        if cn in self.clip_configs and self.clip_configs[cn]['expanded']:
                            self.clip_configs[cn]['config_frame'].pack_forget()
                            self.clip_configs[cn]['expanded'] = False
                    self.update_count()

                # Now configure the checkbox command
                chk.config(command=on_checkbox_toggle)

                # Hidden configuration frame (dark theme)
                config_frame = tk.Frame(container, bg="#2d2d2d")

                if is_still:
                    # For still images, show disabled inputs
                    tk.Label(config_frame, text="Start:", bg="#2d2d2d", fg="white").pack(side="left", padx=5)
                    entry_start = tk.Entry(config_frame, width=8, state="disabled",
                                           bg="#3c3c3c", fg="#a0a0a0", disabledbackground="#3c3c3c",
                                           disabledforeground="#a0a0a0", bd=1)
                    entry_start.insert(0, "N/A")
                    entry_start.pack(side="left")

                    tk.Label(config_frame, text="End:", bg="#2d2d2d", fg="white").pack(side="left", padx=5)
                    entry_end = tk.Entry(config_frame, width=8, state="disabled",
                                         bg="#3c3c3c", fg="#a0a0a0", disabledbackground="#3c3c3c",
                                         disabledforeground="#a0a0a0", bd=1)
                    entry_end.insert(0, "N/A")
                    entry_end.pack(side="left")

                    range_start = tk.DoubleVar(value=0.0)
                    range_end = tk.DoubleVar(value=999999.0)
                else:
                    # For video clips, create functional inputs
                    range_start = tk.DoubleVar(value=0.0)
                    range_end = tk.DoubleVar(value=duration_sec)

                    tk.Label(config_frame, text="Start:", bg="#2d2d2d", fg="white").pack(side="left", padx=5)
                    entry_start = tk.Entry(config_frame, textvariable=range_start, width=8,
                                           bg="#3c3c3c", fg="white", insertbackground="white", bd=1)
                    entry_start.pack(side="left")
                    entry_start.bind("<FocusOut>", lambda e, cn=clip_name: self.validate_clip_range(cn))

                    tk.Label(config_frame, text="sec  End:", bg="#2d2d2d", fg="white").pack(side="left", padx=5)
                    entry_end = tk.Entry(config_frame, textvariable=range_end, width=8,
                                         bg="#3c3c3c", fg="white", insertbackground="white", bd=1)
                    entry_end.pack(side="left")
                    entry_end.bind("<FocusOut>", lambda e, cn=clip_name: self.validate_clip_range(cn))

                    tk.Label(config_frame, text="sec", bg="#2d2d2d", fg="white").pack(side="left", padx=5)

                    btn_reset = tk.Button(config_frame, text="Reset", font=("Arial", 8),
                                          bg="#3c3c3c", fg="white",
                                          activebackground="#4a4a4a", activeforeground="white",
                                          highlightbackground="#2d2d2d",
                                          command=lambda cn=clip_name: self.reset_clip_range(cn))
                    btn_reset.pack(side="left", padx=10)

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
                    'btn_config': btn_config,
                    'expanded': False,
                    'is_still': is_still
                }

        self.update_count()

        # 2. Update Tracks (Logic: New Track OR Existing Tracks except V1)
        try:
            timeline = project.GetCurrentTimeline()
            if timeline:
                track_count = timeline.GetTrackCount("video")
                # Options: "New Track", then "Track 2", "Track 3" ... (Skip 1)
                options = ["New Track"]
                for i in range(2, track_count + 1):
                    options.append(f"Track {i}")
                
                self.combo_tracks['values'] = options
                self.combo_tracks.current(0) # Default to New Track
        except Exception:
            self.combo_tracks['values'] = ["New Track"]
            self.combo_tracks.current(0)

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