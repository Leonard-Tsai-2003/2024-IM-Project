import pygame
import pygame.midi
import pygame.font
import threading
import time
import pretty_midi
import numpy as np
import mido
import textwrap
from collections import defaultdict
import os
import random
import cv2
import imageio
from fpdf import FPDF
from PIL import Image
import math
from game_ChatGPT_comment import *
from emopia.ar_vl_plot import *

BPM_global = 108
class FireParticle:
    def __init__(self, x, y):
        self.x = x + random.uniform(-15, 15)  # Slight horizontal spread
        self.y = y + random.uniform(0, 1)   # Start slightly below the combo position
        self.radius = random.uniform(1, 6)
        self.color = (255, random.randint(100, 150), 0, 255)  # Orange to yellow colors
        self.velocity_x = random.uniform(-0.5, 0.5)
        self.velocity_y = random.uniform(-1.5, -3.0)  # Upward movement
        self.alpha_decay = random.uniform(2, 5)
        self.radius_decay = random.uniform(0.05, 0.1)
        self.lifespan = random.randint(30, 60)

    def update(self):
        self.x += self.velocity_x
        self.y += self.velocity_y
        self.velocity_y += 0.05  # Gravity effect
        new_alpha = max(0, self.color[3] - self.alpha_decay)
        self.color = (
            self.color[0],
            self.color[1],
            self.color[2],
            new_alpha
        )
        self.radius = max(0, self.radius - self.radius_decay)
        self.lifespan -= 1

    def is_alive(self):
        return self.lifespan > 0 and self.color[3] > 0 and self.radius > 0





class TargetLineParticle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        # Smaller radius range for more subtle effect
        self.radius = random.uniform(1, 2.5)
        
        # Lighter gray with higher transparency for subtle smoke
        self.color = (150, 150, 150, 100)
        
        # Slower horizontal movement
        self.velocity_x = random.uniform(-0.15, 0.15)
        
        # Slower upward movement with lower height
        self.velocity_y = random.uniform(-0.6, -0.3)
        
        # Slower fade for longer-lasting effect
        self.alpha_decay = random.uniform(0.3, 0.8)
        
        # Slower size reduction
        self.radius_decay = 0.02
        
        # Longer lifespan to compensate for slower movement
        self.lifespan = random.randint(90, 150)

    def update(self):
        # Slower movement
        self.x += self.velocity_x
        self.y += self.velocity_y
        
        # Very slight gravity effect
        self.velocity_y += 0.002
        
        # Gradual fade
        new_alpha = max(0, self.color[3] - self.alpha_decay)
        self.color = (
            self.color[0],
            self.color[1],
            self.color[2],
            new_alpha
        )
        
        # Gradual size reduction
        self.radius = max(0.5, self.radius - self.radius_decay)
        
        # Decrease lifespan
        self.lifespan -= 1

    def is_alive(self):
        return self.color[3] > 0 and self.radius > 0.5 and self.lifespan > 0


class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = random.uniform(2, 5)  # More precise control over size
        self.color = (105, 105, 105, 200)  # Dark gray with higher transparency for smoke
        self.velocity_x = random.uniform(-0.3, 0.3)  # Slight horizontal movement
        self.velocity_y = random.uniform(-1.5, -0.8)  # Faster upward movement
        self.alpha_decay = random.uniform(0.5, 1.5)  # Smooth fading
        self.radius_decay = 0.05  # Slight radius reduction
        self.lifespan = random.randint(60, 120)  # Frames before the particle disappears

    def update(self):
        self.x += self.velocity_x
        self.y += self.velocity_y
        # Apply a slight gravity effect to slow upward movement over time
        self.velocity_y += 0.005
        # Fade the particle
        new_alpha = max(0, self.color[3] - self.alpha_decay)
        self.color = (
            self.color[0],
            self.color[1],
            self.color[2],
            new_alpha
        )
        # Reduce the radius to simulate dissipation
        self.radius = max(1, self.radius - self.radius_decay)
        # Decrease lifespan
        self.lifespan -= 1

    def is_alive(self):
        return self.color[3] > 0 and self.radius > 1 and self.lifespan > 0


class DynamicMusicSheet:
    def __init__(self):
        # Screen Info Initialization
        pygame.init()
        pygame.font.init()
        screen_info = pygame.display.Info()
        self.screen_width, self.screen_height = screen_info.current_w, screen_info.current_h
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
        pygame.display.set_caption("Dynamic Music Sheet - Real-time Visualization")
        
        # Load the logo image
        self.logo = pygame.image.load("logo.jpg")

        # Get the original dimensions of the logo
        original_width, original_height = self.logo.get_size()

        # Define the desired width or height, maintaining aspect ratio
        desired_width = 225  # Set your desired width
        scaling_factor = desired_width / original_width
        new_width = int(original_width * scaling_factor)
        new_height = int(original_height * scaling_factor)

        # Resize the logo while keeping its shape
        self.logo = pygame.transform.smoothscale(self.logo, (new_width, new_height))


        
        self.particles = []  # List to hold active particles
        self.should_smoke = {}  # 新增：追踪哪些音符應該產生煙霧效果

        
        # Tolerance Param Initialization
        self.time_tolerance = 0.2
        self.velocity_tolerance = 20
        self.pedal_tolerance = 0.2
        self.pedal_start_tolerance = 2  # New tolerance for pedal start time
        self.pedal_duration_tolerance = 0.2

        # Scoring-related initialization
        self.bar_scores = defaultdict(lambda: {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'duration': 0})
        self.overall_score = {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'note_count': 0}
        # note count is the amount of all notes, 
        # count is the amount of correct notes
        
        self.performance_report = ""
        
        # Add a new attribute for the close button
        self.close_button_rect = None
        self.showing_report = False
        
        # Midi Input Info Initialization
        pygame.midi.init()
        try:
            self.midi_input = pygame.midi.Input(pygame.midi.get_default_input_id())
        except pygame.midi.MidiException:
            print("No MIDI input device found!")
            self.midi_input = None
        
        # Modified MIDI recording attributes
        self.recorded_events = []
        self.recording_start_timestamp = None
        self.active_notes = {}  # Track currently active notes
        self.released_notes = []  # Track recently released notes for visualization
        
        # Midi Details Initialization
        self.BPM = BPM_global
        self.ticks_per_beat = 480
        self.ticks_per_second = (self.ticks_per_beat * self.BPM) / 60
        self.student_notes = {}
        self.student_control_pressed_time = -1
        self.note_list = []
        self.pedal_list = []
        self.midi_thread = None
        self.start_time = None
        self.is_recording = threading.Event()
        
        # Reference Midi File Initialization
        self.reference_path = '3_t3.mid'

        self.ref_notes, self.ref_control = self.load_reference_midi(self.reference_path)
        self.total_duration = max([end for _, _, end, _ in self.ref_notes])

        # Set fixed keyboard range from A0 to C8 (MIDI notes 21 to 108)
        self.min_pitch = 21  # A0
        self.max_pitch = 108  # C8
        self.total_keys = self.max_pitch - self.min_pitch + 1  # 88 keys

        # Attempt to use system font
        self.font_title = pygame.font.SysFont("Verdana", 15, bold = True)
        self.font_report_title = pygame.font.SysFont("Verdana", 30, bold = True) # changed 1204
        self.font_note = pygame.font.SysFont("Verdana", 13)
        self.font_report = pygame.font.SysFont("Verdana", 15)
        self.legend_font = pygame.font.SysFont(None, 22)

        # Test font availability
        if not pygame.font.match_font("Verdana"):
            print("Verdana font not found, using default font.")
            self.font_title = pygame.font.Font(None, 20)
            self.font_report_title = pygame.font.Font(None, 56)
            self.font_note = pygame.font.Font(None, 7)
            self.font_report = pygame.font.Font(None, 7)
        
        self.setup_ui_elements()
        
        # Metronome Initialization
        self.metronome_duration = 0.1
        self.beat_sound = self.generate_beat_sound(duration=self.metronome_duration)
        self.is_playing_metronome = False
        self.metronome_thread = None
        self.bpm_text = ''
        self.time_tolerance_text = ''
        self.bpm_input_active = False  # To track if BPM input is active
        self.time_tolerance_input_active = False  # To track if time tolerance input is active
        self.show_settings_menu = False  # To track if settings menu is open

        # Notes Colors Initialization
        self.colors = {
            'correct': (144, 238, 144),  # light green
            'incorrect': (255, 0, 0),    # red
            'too_hard': (255, 255, 0),   # yellow
            'too_light': (0, 255, 255)   # cyan
        }

        # Notes Legend Initialization
        self.legends = [
            ("Correct", self.colors['correct']),
            ("Incorrect", self.colors['incorrect']),
            ("Too hard", self.colors['too_hard']),
            ("Too light", self.colors['too_light']),
            (f"Time tolerance: {self.time_tolerance:.2f}s", (150, 150, 150)),
            (f"Velocity tolerance: {self.velocity_tolerance}", (150, 150, 150)),
            (f"Pedal tolerance: {self.pedal_start_tolerance:.2f}s", (150, 150, 150))
        ]

        # Overall Comment Initialization
        self.student_midi_file = None
        self.overall_comment = ""

        # Initialize falling notes start time
        self.falling_notes_start_time = None
        
        self.erased_notes = {}  # Tracks notes being erased (key: note_number, value: True)
        
        self.reference_pitch = 60  # MIDI pitch for C4 (middle C)
        self.show_syllables = True
        # Add this in the __init__ method of DynamicMusicSheet
        self.pitch_class_to_syllable = {
            0: 'Do',   # C
            2: 'Re',   # D
            4: 'Mi',   # E
            5: 'Fa',   # F
            7: 'So',   # G
            9: 'La',   # A
            11: 'Si'   # B
        }

        
        #target line
        self.target_line_y = self.screen_height - 200
        

        # Load and prepare GIF
        self.gif_path = "1126.gif"  # Replace with the correct path
        self.gif_frames, self.gif_durations = self.load_and_resize_gif(self.gif_path, desired_width=180)
        self.current_frame_index = 0
        self.gif_last_update = pygame.time.get_ticks()
        self.gif_display_width = 180
        self.gif_position = (self.screen_width - self.gif_display_width - 10, 220)  # Right side, near the top

        self.clock = pygame.time.Clock()
        
        self.current_combo = 0  # Tracks the current combo
        self.max_combo = 0      # Tracks the maximum combo achieved
        self.combo_position = (self.screen_width - self.gif_display_width+76, 210)  # Position for the combo display
        self.font_combo = pygame.font.SysFont("Terminal", 18, bold = True)  # Font for the combo display
        #self.combo_position = (self.screen_width - self.gif_display_width // 2 - 10, 240)
        
        self.combo_last_increase_time = None
        self.fire_particles = []  # List to hold fire particles
        
        self.show_combo = True  # 是否顯示 combo 數字
        self.show_gif = True  # 是否顯示 GIF 動畫
        self.animation_menu_active = False  # 是否顯示動畫設定菜單
        ...
        self.animation_button_rect = pygame.Rect(
            10, 70 + 4 * (self.button_height + self.button_spacing), 120, self.button_height
        )

        # variables for scrollable report
        self.scroll_y = 0
        self.surface_height = 0
        self.scroll_speed = 0
        self.print_button_rect = None
        self.report_surface = None
        self.emulate_close_button_rect = None
        self.emulate_print_button_rect = None
        self.y_intercept = self.screen_height/2
        self.x_intercept = self.screen_width/10
        self.scaling_factor = 1.3 * 1000 // (self.screen_width/self.BPM)
        self.showing_report_settings_menu = False  # To track if settings menu is open
        self.report_time_tolerance_text = ''
        self.report_velocity_tolerance_text = ''
        self.report_time_tolerance_input_active = False  # To track if BPM input is active
        self.report_velocity_tolerance_input_active = False  # To track if time tolerance input is active
        self.scroll_x = 0 #for the horizontal scrollable report notes

        #fixing duration score
        self.ref_duration_list = []


        
        
    def load_and_resize_gif(self, gif_path, desired_width):
        """
        Load a GIF, resize each frame to the desired width, and return the frames and their durations.
        """
        gif = imageio.mimread(gif_path, memtest=False)
        gif_reader = imageio.get_reader(gif_path)
        gif_meta = gif_reader.get_meta_data()

        # Ensure gif_durations is a list
        gif_duration = gif_meta.get('duration', 100)  # Default duration: 100ms
        gif_durations = [gif_duration] * len(gif) if isinstance(gif_duration, int) else gif_duration

        # Adjust the frame durations to make the GIF play faster
        speed_factor = 1  # Increase this value to make the GIF faster
        adjusted_gif_durations = [max(1, int(duration / speed_factor)) for duration in gif_durations]

        resized_frames = []
        for frame in gif:
            # Convert frame to a PIL image for better compatibility
            pil_frame = Image.fromarray(frame).convert("RGBA")
            scaling_factor = desired_width / pil_frame.width
            new_width = int(pil_frame.width * scaling_factor)
            new_height = int(pil_frame.height * scaling_factor)

            # Resize the frame
            resized_pil_frame = pil_frame.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert back to a Pygame surface
            frame_surface = pygame.image.fromstring(resized_pil_frame.tobytes(), resized_pil_frame.size, "RGBA")
            resized_frames.append(frame_surface)

        return resized_frames, adjusted_gif_durations



    def generate_fire_particles(self):
        if self.current_combo >= 10:
            x, y = self.combo_position
            # Generate multiple particles per frame for a denser effect
            for _ in range(2):
                self.fire_particles.append(FireParticle(x, y + 20))  # Slightly adjust y if needed




    def update_and_draw_fire_particles(self):
        for particle in self.fire_particles[:]:
            particle.update()
            if particle.is_alive():
                # Create a surface for each particle with per-pixel alpha
                particle_surface = pygame.Surface((particle.radius * 2, particle.radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(
                    particle_surface,
                    particle.color,
                    (particle.radius, particle.radius),
                    int(particle.radius)
                )
                # Blit the particle onto the main screen
                self.screen.blit(
                    particle_surface,
                    (particle.x - particle.radius, particle.y - particle.radius),
                    special_flags=pygame.BLEND_ADD
                )
            else:
                self.fire_particles.remove(particle)
        # Limit the total number of particles to prevent performance issues
        MAX_FIRE_PARTICLES = 500
        if len(self.fire_particles) > MAX_FIRE_PARTICLES:
            self.fire_particles = self.fire_particles[-MAX_FIRE_PARTICLES:]

    def draw_animation_menu(self):
        """繪製動畫設定菜單"""
        # 菜單背景
        menu_width = 300
        menu_height = 150
        menu_x = (self.screen_width - menu_width) // 2
        menu_y = (self.screen_height - menu_height) // 2
        menu_rect = pygame.Rect(menu_x, menu_y, menu_width, menu_height)
        pygame.draw.rect(self.screen, (240, 240, 240), menu_rect, border_radius=10)

        # 顯示 combo 選項
        combo_checkbox_rect = pygame.Rect(menu_x + 20, menu_y + 30, 20, 20)
        pygame.draw.rect(self.screen, (255, 255, 255), combo_checkbox_rect)
        if self.show_combo:
            # 計算圓心位置和半徑
            center_x = combo_checkbox_rect.left + combo_checkbox_rect.width // 2
            center_y = combo_checkbox_rect.top + combo_checkbox_rect.height // 2
            radius = combo_checkbox_rect.width // 4  # 圓點的半徑，設為框寬度的四分之一

            # 繪製圓點
            pygame.draw.circle(self.screen, (0, 0, 0), (center_x, center_y), radius)

        combo_label = self.font_title.render("Show Combo", True, (0, 0, 0))
        self.screen.blit(combo_label, (combo_checkbox_rect.right + 10, combo_checkbox_rect.top))

        gif_checkbox_rect = pygame.Rect(menu_x + 20, menu_y + 70, 20, 20)
        pygame.draw.rect(self.screen, (255, 255, 255), gif_checkbox_rect)  # 繪製方框

        # 顯示 gif 選項
        if self.show_gif:
            # 計算圓心和半徑
            center_x = gif_checkbox_rect.left + gif_checkbox_rect.width // 2
            center_y = gif_checkbox_rect.top + gif_checkbox_rect.height // 2
            radius = gif_checkbox_rect.width // 4  # 圓點的半徑，設為框寬度的四分之一

            # 繪製圓點
            pygame.draw.circle(self.screen, (0, 0, 0), (center_x, center_y), radius)

        gif_label = self.font_title.render("Show Astronout", True, (0, 0, 0))
        self.screen.blit(gif_label, (gif_checkbox_rect.right + 10, gif_checkbox_rect.top))


        # OK 按鈕
        ok_button_rect = pygame.Rect(menu_x + 100, menu_y + 110, 80, 30)
        pygame.draw.rect(self.screen, (200, 200, 200), ok_button_rect, border_radius=5)
        ok_text = self.font_title.render("OK", True, (0, 0, 0))
        self.screen.blit(ok_text, (ok_button_rect.x + 20, ok_button_rect.y + 5))

        # 處理點擊事件
        mouse_pos = pygame.mouse.get_pos()
        mouse_click = pygame.mouse.get_pressed()
        if mouse_click[0]:  # 檢查左鍵按下
            if combo_checkbox_rect.collidepoint(mouse_pos):
                self.show_combo = not self.show_combo
            elif gif_checkbox_rect.collidepoint(mouse_pos):
                self.show_gif = not self.show_gif
            elif ok_button_rect.collidepoint(mouse_pos):
                self.animation_menu_active = False
                
    def draw_gif(self):
        """
        Draw the current frame of the GIF and update the frame based on timing.
        The GIF is stuck at the first frame when combo is under 15, and animates when combo is 15 or more.
        """
        if self.current_combo < 10:
            # Combo is less than 15, show the first frame only
            frame_to_display = self.gif_frames[161]
        else:
            # Combo is 15 or greater, animate the GIF
            current_time = pygame.time.get_ticks()
            if current_time - self.gif_last_update > self.gif_durations[self.current_frame_index]:
                self.current_frame_index = (self.current_frame_index + 1) % len(self.gif_frames)
                self.gif_last_update = current_time
            frame_to_display = self.gif_frames[self.current_frame_index]

        # Draw the frame at the desired position
        self.screen.blit(frame_to_display, self.gif_position)






    def load_reference_midi(self, reference_path):
        try:
            ref_midi = pretty_midi.PrettyMIDI(reference_path)
            
            # Get the original tempo(s)
            tempo_times, tempos = ref_midi.get_tempo_changes()
            original_tempo = tempos[0]  # Assuming a single, constant tempo
            print(f"Original Tempo: {original_tempo} BPM")
            
            # Set the desired BPM
            desired_bpm = self.BPM  # Use the BPM set in your application
            print(f"Desired Tempo: {desired_bpm} BPM")
            
            # Calculate the scaling factor
            tempo_ratio = original_tempo / desired_bpm
            
            # Adjust note timings
            adjusted_notes = []
            for instrument in ref_midi.instruments:
                for note in instrument.notes:
                    # Scale the start and end times
                    start = note.start * tempo_ratio
                    end = note.end * tempo_ratio
                    adjusted_notes.append((note.pitch, start, end, note.velocity))
            
            # Adjust control change timings
            adjusted_control = []
            for instrument in ref_midi.instruments:
                for control in instrument.control_changes:
                    # Scale the control event times
                    time_ = control.time * tempo_ratio
                    adjusted_control.append((control.number, control.value, time_))
            
            # Adjust timings relative to the first note
            first_note_start = min(note[1] for note in adjusted_notes)
            adjusted_notes = [(pitch, start - first_note_start, end - first_note_start, velocity)
                            for pitch, start, end, velocity in adjusted_notes]
            adjusted_control = [(number, value, time - first_note_start)
                                for number, value, time in adjusted_control]
            
            # Extract reference pedal events
            self.ref_pedal_events = []
            pedal_pressed_time = None
            for number, value, time in adjusted_control:
                if number == 64:
                    if value > 0:
                        # Pedal pressed
                        pedal_pressed_time = time
                    elif value == 0 and pedal_pressed_time is not None:
                        # Pedal released
                        pedal_event = (pedal_pressed_time, time)
                        self.ref_pedal_events.append(pedal_event)
                        pedal_pressed_time = None

            return adjusted_notes, adjusted_control
        except Exception as e:
            print(f"Error loading reference MIDI: {e}")
            return [], []

    def setup_midi_recording(self):
        """Initialize MIDI recording"""
        self.recorded_events = []
        self.active_notes = {}
        self.released_notes = []
        self.recording_start_timestamp = time.time()
     
    def save_recorded_midi(self, filename="recorded_performance.mid"):
        """Save recorded MIDI events to a file with proper timing"""
        if not self.recorded_events:
            print("No MIDI events recorded")
            return

        # Create new MIDI file
        midi_file = mido.MidiFile()
        track = mido.MidiTrack()
        midi_file.tracks.append(track)
        
        # Add tempo message
        tempo = mido.bpm2tempo(self.BPM)
        track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
        
        # Convert events to MIDI messages with proper timing
        last_time = 0
        for event in sorted(self.recorded_events, key=lambda x: x['timestamp']):
            # Convert absolute timestamp to relative ticks
            current_time = event['timestamp']
            delta_time = current_time - last_time
            ticks = int(delta_time * midi_file.ticks_per_beat * (self.BPM / 60))
            
            if event['type'] == 'note_on':
                msg = mido.Message('note_on', 
                                 note=event['note'],
                                 velocity=event['velocity'],
                                 time=ticks)
                track.append(msg)
                
            elif event['type'] == 'note_off':
                msg = mido.Message('note_off',
                                 note=event['note'],
                                 velocity=0,
                                 time=ticks)
                track.append(msg)
                
            elif event['type'] == 'control_change':
                msg = mido.Message('control_change',
                                 control=event['note'],
                                 value=event['velocity'],
                                 time=ticks)
                track.append(msg)
                
            last_time = current_time
        
        # Save the file
        try:
            midi_file.save(filename)
            file_size = os.path.getsize(filename)
            print(f"Recording saved as {filename} (Size: {file_size} bytes)")
            
            # Print debug information
            print(f"Total events recorded: {len(self.recorded_events)}")
            print(f"BPM: {self.BPM}")
            print(f"Duration: {last_time:.2f} seconds")
            
            # Verify file content
            loaded_file = mido.MidiFile(filename)
            print(f"Tracks in saved file: {len(loaded_file.tracks)}")
            print(f"Messages in main track: {len(loaded_file.tracks[0])}")
            
        except Exception as e:
            print(f"Error saving MIDI file: {e}")
            
        return midi_file



    def setup_ui_elements(self):
        self.button_width = 80
        self.button_height = 30
        self.button_spacing = 10

        self.record_button_rect = pygame.Rect(10, 70, self.button_width, self.button_height)
        self.show_button_rect = pygame.Rect(10, 70 + self.button_height + self.button_spacing, self.button_width, self.button_height)
        self.settings_button_rect = pygame.Rect(
            10, 70 + 2 * (self.button_height + self.button_spacing), 100, self.button_height
        )
        self.syllable_button_rect = pygame.Rect(
            10, 70 + 3 * (self.button_height + self.button_spacing), 150, self.button_height
        )

        self.close_button_rect = pygame.Rect(self.screen_width - 60, self.screen_height - 60, 100, 40)
        self.animation_button_rect = pygame.Rect(
            10, 70 + 4 * (self.button_height + self.button_spacing), 120, self.button_height
        )


    def create_gradient_surface(self, width, height, top_color, bottom_color):
        # Create a surface with per-pixel alpha
        gradient = pygame.Surface((width, max(height, 1)), pygame.SRCALPHA)  # Ensure height is at least 1
        
        # Draw the gradient onto the surface
        for y in range(int(height)):
            ratio = y / height if height > 0 else 0
            r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
            g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
            b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
            pygame.draw.line(gradient, (r, g, b), (0, y), (width, y))
        
        gradient.set_alpha(180)  # Adjust transparency if needed
        return gradient



    def draw_rounded_rect(self, surface, color, rect, radius=10):
        pygame.draw.rect(surface, color, rect, border_radius=radius)
        
    def draw_smoke_effect(self, x, y, key_width):
        """
        Generate smoke effect evenly across the key's width.
        """
        # Increase particle generation rate for continuous smoke effect
        for _ in range(12):  # Increased from 8 to 12 for denser smoke
            # Randomly position particles across the entire width of the key
            particle_x = x + random.uniform(0, key_width)
            # Add some vertical variation for a more natural effect
            particle_y = y - 10 + random.uniform(-5, 5)
            self.particles.append(Particle(particle_x, particle_y))
#



    def draw_button_with_shadow(self, surface, rect, text, font, active=False):
        shadow_offset = 4  # Offset for shadow
        shadow_color = (100, 100, 100)  # Shadow color

        # Draw shadow
        shadow_rect = rect.move(shadow_offset, shadow_offset)
        self.draw_rounded_rect(surface, shadow_color, shadow_rect, radius=15)

        # Determine color based on active state
        if active:
            button_color = (200, 230, 255)  # Light blue
            text_color = (0, 102, 204)
        else:
            button_color = (230, 240, 250)  # Soft blue gradient
            text_color = (50, 50, 50)

        # Draw button background with rounded corners
        self.draw_rounded_rect(surface, button_color, rect, radius=15)

        # Draw button text
        text_surface = font.render(text, True, text_color)
        text_rect = text_surface.get_rect(center=rect.center)
        surface.blit(text_surface, text_rect)
        
    def generate_beat_sound(self, frequency=450, duration=0.05, volume=0.5):
        """
        Generate a shorter, crisper metronome sound
        """
        sample_rate = 44100
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, False)
        
        # Use a sharper attack and decay for better timing precision
        sine_wave = np.sin(2 * np.pi * frequency * t)
        
        # Create shorter fade in/out for crisper sound
        fade_samples = int(sample_rate * 0.01)  # 10ms fade
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        envelope = np.ones_like(sine_wave)
        envelope[:len(fade_in)] = fade_in
        envelope[-len(fade_out):] = fade_out
        
        smooth_wave = sine_wave * envelope
        
        stereo_wave = np.column_stack((smooth_wave, smooth_wave)) * volume * 32767
        stereo_wave = stereo_wave.astype(np.int16)
        
        return pygame.sndarray.make_sound(stereo_wave)
    
    def play_metronome(self):
        """
        Improved metronome timing using time-based correction
        """
        beat_interval = 60.0 / self.BPM
        next_beat_time = time.time()
        
        while self.is_playing_metronome:
            current_time = time.time()
            
            if current_time >= next_beat_time:
                self.beat_sound.play()
                # Calculate next beat time based on the original start time
                next_beat_time += beat_interval
                
                # If we're running behind, reset the next beat time
                if current_time > next_beat_time + beat_interval:
                    next_beat_time = current_time + beat_interval
            
            # Shorter sleep interval for more precise timing
            time.sleep(0.001)

    def start_metronome(self):
        if not self.is_playing_metronome:
            self.is_playing_metronome = True
            self.metronome_thread = threading.Thread(target=self.play_metronome)
            self.metronome_thread.daemon = True
            self.metronome_thread.start()

    def stop_metronome(self):
        if self.is_playing_metronome:
            self.is_playing_metronome = False
            if self.metronome_thread.is_alive():
                self.metronome_thread.join()
                    
    def process_midi_input(self):
        if not self.midi_input:
            return
        
        self.start_time = time.time()
        while self.is_recording.is_set():
            if self.midi_input.poll():
                midi_events = self.midi_input.read(10)
                for event in midi_events:
                    status = event[0][0]
                    note_number = event[0][1]
                    velocity = event[0][2]
                    current_time = time.time()
                    timestamp = current_time - self.recording_start_timestamp
                    
                    # 詳細 MIDI 事件結構
                    midi_event = {
                        'type': 'note_on' if status == 144 and velocity > 0 else
                                'note_off' if (status == 128 or (status == 144 and velocity == 0)) else
                                'control_change' if status == 176 else 'other',
                        'note': note_number,
                        'velocity': velocity,
                        'timestamp': timestamp,
                        'status': status
                    }
                    self.recorded_events.append(midi_event)
                    
                    # Note ON 事件
                    if status == 144 and velocity > 0:
                        note_start_time = current_time - self.start_time
                        student_note = (note_number, note_start_time, note_start_time, velocity) # anything related to start, start or start_time, start_time
                        color = self.compare_and_visualize(student_note, self.time_tolerance, self.velocity_tolerance)
                        
                        # 更新 active_notes
                        self.active_notes[note_number] = {
                            'start_time': note_start_time,
                            'velocity': velocity,
                            'correct': color == self.colors['correct']
                        }
                        
                        # 檢查是否應該產生煙霧效果
                        if self.is_note_at_target_line(note_number):
                            self.should_smoke[note_number] = True
                        
                    # Note OFF 事件
                    elif status == 128 or (status == 144 and velocity == 0):
                        if note_number in self.active_notes:
                            self.active_notes.pop(note_number)
                            if note_number in self.should_smoke:
                                del self.should_smoke[note_number]
                    
                    # Control Change 事件 #changelog1127 : added back control changes
                    elif status == 176 and velocity >= 0:
                         if note_number == 64:  # Pedal
                            if velocity > 0:  # Pedal pressed
                                self.student_control_pressed_time = timestamp
                            elif velocity == 0:  # Pedal released
                                control_end_time = timestamp
                                control_start_time = self.student_control_pressed_time
                                if self.student_control_pressed_time >= 0:
                                    self.compare_pedal_and_visulaize((control_start_time, control_end_time))
                        
            time.sleep(0.001)



    def calculate_note_score(self, student_note, ref_note):
        pitch_diff = abs(student_note[0] - ref_note[0])
        pitch_score = max(0, 100 - pitch_diff * 2)

        velocity_diff = abs(student_note[3] - ref_note[3])
        velocity_score = max(0, 100 - velocity_diff * 2)  # Deduct 2 points for each velocity difference

        timing_diff = abs(student_note[1] - ref_note[1])
        timing_score = max(0, 100 - timing_diff * 200)  # Deduct 20 points for each 0.1s difference

        # Debug: Output individual score calculations
        print(f"Note score calculation: pitch={pitch_score}, velocity={velocity_score}, timing={timing_score}")

        return {
            'pitch': pitch_score,
            'velocity': velocity_score,
            'timing': timing_score
        }

             
    def update_scores(self, note_score, bar_number):
        # Update bar-specific scores
        for aspect in ['pitch', 'velocity', 'timing']:
            self.bar_scores[bar_number][aspect] += note_score[aspect]
            self.bar_scores[bar_number]['count'] += 1
            self.overall_score[aspect] += note_score[aspect]

        # Increment overall score count
        self.overall_score['count'] += 1

        # Debug: Output score updates
        print(f"Updated scores for bar {bar_number}: {self.bar_scores[bar_number]}")


    def calculate_duration_score(self, student_note, ref_note):
        """
        Calculate duration score based on note length comparison.
        Only calculates for notes with matching pitch.

        Parameters:
        student_note: tuple (pitch, start_time, end_time, velocity)
        ref_note: tuple (pitch, start_time, end_time, velocity)

        Returns:
        float: duration score between 0 and 100
        """
        # Only calculate if pitches match
        if student_note[0] != ref_note[0]:
            return 0

        # Calculate durations
        student_duration = student_note[2] - student_note[1]
        ref_duration = ref_note[2] - ref_note[1]
        self.ref_duration_list.append(ref_duration)

        # Ensure durations are positive
        if student_duration <= 0 or ref_duration <= 0:
            return 0

        # Calculate duration ratio
        duration_ratio = min(student_duration / ref_duration, ref_duration / student_duration)

        # Scale ratio to a score between 0 and 100
        return duration_ratio * 100

    def update_duration_scores(self, duration_score, bar_number):
        """
        Update the running duration scores for both bar-specific and overall metrics
        """
        if 'duration' not in self.bar_scores[bar_number]:
            self.bar_scores[bar_number]['duration'] = 0
        if 'duration' not in self.overall_score:
            self.overall_score['duration'] = 0
        
        self.bar_scores[bar_number]['duration'] += duration_score
        self.overall_score['duration'] += duration_score

    def get_duration_statistics(self):
        """
        Generate statistics about note duration accuracy in the performance
        """
        total_notes = len(self.note_list)
        if total_notes == 0:
            return None
            
        total_duration_ratio = 0
        analyzed_notes = 0
        
        for student_note in self.note_list:
            # Find matching reference note
            ref_note = None
            for ref in self.ref_notes:
                if abs(student_note[1] - ref[1]) < self.time_tolerance and student_note[0] == ref[0]:
                    ref_note = ref
                    break
                    
            if ref_note:
                score = self.calculate_duration_score(
                    (student_note[0], student_note[1], student_note[2], student_note[5]),
                    ref_note
                )
                if score > 0:  # Only count notes where we actually calculated a duration
                    total_duration_ratio += score
                    analyzed_notes += 1
        
        return { # score output
            'average_duration_score': total_duration_ratio / analyzed_notes if analyzed_notes > 0 else 0,
            'total_notes_analyzed': analyzed_notes,
            'total_notes_played': total_notes
        }
                
    def compare_and_visualize(self, student_note, tolerance=0.1, velocity_tolerance=20):
        pitch, start_time, end_time, velocity = student_note
        closest_ref_note = None
        closest_time_diff = float('inf')

        # Debug: Print the student note being processed
        #print(f"[DEBUG] Processing student note: {student_note}")

        # Find the closest reference note with matching pitch within tolerance
        for ref_pitch, ref_start, ref_end, ref_velocity in self.ref_notes:
            if ref_pitch == pitch:  # Match the pitch first
                time_diff = abs(start_time - ref_start)
                if time_diff < closest_time_diff and time_diff <= tolerance:
                    closest_time_diff = time_diff
                    closest_ref_note = (ref_pitch, ref_start, ref_end, ref_velocity)

        # If a match is found, process further
        if closest_ref_note:
            ref_pitch, ref_start, ref_end, ref_velocity = closest_ref_note

            # Debug: Output the matching reference note details
            #print(f"[DEBUG] Matched student note {student_note} with reference note {closest_ref_note}")

            # Determine the color for visualization
            color = self.colors['correct']  # Green (correct note)
            self.current_combo += 1  # Increment combo
            self.max_combo = max(self.max_combo, self.current_combo)  # Update max combo
            self.combo_last_increase_time = time.time()  # Record the time of combo increase

            # Add the note to the visualization list
            self.note_list.append((pitch, start_time, end_time, True, color, velocity))

            # Calculate scores for the matched note
            note_score = self.calculate_note_score(student_note, closest_ref_note)
            duration_score = self.calculate_duration_score(student_note, closest_ref_note)

            # Determine bar number for tracking
            bar_duration = 240 / self.BPM  # Assuming 4/4 time signature
            bar_number = int(start_time // bar_duration)

            # Update scores
            self.update_scores(note_score, bar_number)
            self.update_duration_scores(duration_score, bar_number)

            # Debug: Output the duration score for this note
            #print(f"[DEBUG] Duration score={duration_score}")
        else:
            # No match found, mark the note as incorrect
            #print(f"[DEBUG] No match found for student note: {student_note}")
            self.note_list.append((pitch, start_time, end_time, False, self.colors['incorrect'], velocity))
            self.current_combo = 0  # Reset combo on incorrect note
            self.combo_last_increase_time = None  # Reset combo increase time

        # Increment overall note count
        self.overall_score['note_count'] += 1

        # Debug: Output current combo and max combo
        #print(f"[DEBUG] Current Combo: {self.current_combo}, Max Combo: {self.max_combo}")



    def draw_combo(self):
        combo_text = f"{self.current_combo}"
        x, y = self.combo_position

        # 基礎字體大小與最大字體大小
        base_font_size = 30
        max_font_size = 100  # 定義最大字體大小

        # 根據 combo 數值調整字體大小
        if self.current_combo > 10:
            # 超過 10 後字體隨 combo 增大
            dynamic_font_size = min(base_font_size + (self.current_combo - 10) * 2, max_font_size)
        else:
            # combo ≤ 10 使用基礎字體大小
            dynamic_font_size = base_font_size

        # 動態縮放效果
        if self.combo_last_increase_time is not None:
            elapsed_time = time.time() - self.combo_last_increase_time
            shrink_duration = 0.15  # 縮放效果的持續時間
            if elapsed_time < shrink_duration:
                # 計算縮放比例，基於 ease-out 動畫效果
                t = elapsed_time / shrink_duration
                scale = 0.8 + 0.2 * t * (2 - t)  # Ease-out quadratic
                font_size = int(dynamic_font_size * scale)
            else:
                font_size = dynamic_font_size
        else:
            font_size = dynamic_font_size

        # 主字體
        main_font = pygame.font.SysFont("Verdana", font_size, bold=True)

        # 設定字體顏色
        if self.current_combo < 10:
            main_color = (138, 212, 250)  # 淺藍色
        else:
            main_color = (246, 201, 162)  # 淺橘色

        glow_color = (255, 0, 0)  # 紅色發光效果

        # 創建發光效果
        glow_layers = 15
        for i in range(glow_layers, 0, -1):
            glow_font_size = font_size + i * 2
            glow_font = pygame.font.SysFont("Terminal", int(glow_font_size), bold=True)
            glow_surface = glow_font.render(combo_text, True, glow_color)

            alpha = int(50 / i)
            glow_surface.set_alpha(alpha)

            glow_rect = glow_surface.get_rect(center=(x, y))
            self.screen.blit(glow_surface, glow_rect)

        # 繪製主字體
        main_surface = main_font.render(combo_text, True, main_color)
        main_rect = main_surface.get_rect(center=(x, y))
        self.screen.blit(main_surface, main_rect)








    def compare_pedal_and_visulaize(self, student_control, tolerance=0.1):
        pedal_start_time, pedal_end_time = student_control

        tolerance = self.pedal_start_tolerance
        # Compare with reference pedal events
        matching_ref_pedal = None
        for ref_start_time, ref_end_time in self.ref_pedal_events:
            start_time_diff = abs(pedal_start_time - ref_start_time)
            duration_diff = abs((pedal_end_time - pedal_start_time) - (ref_end_time - ref_start_time))

            if start_time_diff <= self.pedal_start_tolerance and duration_diff <= self.pedal_duration_tolerance:
                matching_ref_pedal = (ref_start_time, ref_end_time)
                break

        if matching_ref_pedal:
            # Correct pedal event
            correctness = True
            color = self.colors['correct']
        else:
            # Incorrect pedal event
            correctness = False
            color = self.colors['incorrect']

        # Visualize
        self.pedal_list.append((pedal_start_time, pedal_end_time, correctness, color))

    def calculate_overall_duartion(self):
        #note_list structure (pitch, start, new_end, correct, color, velocity)
        temp_note_list = [x for x in self.note_list if x[3]] # all correct notes
        temp_ref_list = self.ref_duration_list
        overall_duration_score = 0
        for (_, stu_start, stu_end, _, _, _), ref_duration in zip(temp_note_list, temp_ref_list):
            student_duration = stu_end - stu_start
            if student_duration <= 0 or ref_duration <= 0:
                return 0
            duration_ratio = min(student_duration / ref_duration, ref_duration / student_duration) * 100
            overall_duration_score += duration_ratio
        return overall_duration_score

    def generate_performance_report(self):
        # Calculate basic scores
        avg_pitch = self.overall_score['pitch'] / self.overall_score['note_count'] if self.overall_score['note_count'] > 0 else 0
        avg_velocity = self.overall_score['velocity'] / self.overall_score['count'] if self.overall_score['count'] > 0 else 0
        avg_timing = self.overall_score['timing'] / self.overall_score['count'] if self.overall_score['count'] > 0 else 0
        overall_duration_score = self.calculate_overall_duartion()
        avg_duration = overall_duration_score / self.overall_score['count'] if self.overall_score['count'] > 0 else 0

        # Calculate overall average including all aspects
        overall_avg = (avg_pitch + avg_velocity + avg_timing + avg_duration) / 4
        sentiment_avg = (avg_velocity + avg_timing + avg_duration) / 3

        # Start building the report with Performance Metrics title
        report = "Performance Metrics\n\n"  # Bold styling handled by rendering font bold
        report += f"Note Accuracy: {avg_pitch:.2f}%\n\n"
        report += f"Detail Scores (Sentiment Analysis): {sentiment_avg:.2f} / 100\n"
        report += f"  - Velocity Control: {avg_velocity:.2f} / 100\n"
        report += f"  - Timing Precision: {avg_timing:.2f} / 100\n"
        report += f"  - Duration Accuracy: {avg_duration:.2f} / 100\n\n"

        duration_stats = self.get_duration_statistics()
        if duration_stats:
            report += f"Notes Analyzed (Velocity, Timing, Duration): {duration_stats['total_notes_analyzed']}/{duration_stats['total_notes_played']}\n\n"

        # Add performance feedback
        if overall_avg >= 90:
            report += "Excellent performance! Your playing was highly accurate with consistent note durations."
        elif overall_avg >= 80:
            report += "Great job! Your performance was very good with minor areas for improvement."
        elif overall_avg >= 70:
            report += "Good effort! Focus on maintaining consistent note lengths to match the reference."
        else:
            report += "Keep practicing! Pay attention to timing and note durations to improve further."

        self.performance_report = report
        print("Performance Report Generated:")
        print(report)


    def generate_overall_comment(self):
        # Generate the response
        response_info, response = get_response(f"Reference:{get_midi_file(self.reference_path)}\n Student:{self.student_midi_file}")
        self.overall_comment = response_info.choices[0].message.content
            
        words = self.overall_comment.split()
        formatted_comment = '\n'.join([' '.join(words[i:i+10]) for i in range(0, len(words), 10)])

        # Add formatted comment to performance report with "AI comments" heading
        self.performance_report += f"\n\n\nAI Comments\n\n{formatted_comment}"

        # Print the formatted comment
        
        self.performance_report += f"\n\n\nColor Representation"
        print(formatted_comment)


    def generate_ar_vl_path(self):
        draw_ar_vl_path(split_midi_by_bars(self.reference_path), 
                        split_midi_by_bars(mido_to_pretty_midi(self.student_midi_file)))


    def draw_legends(self):
        legend_height = 30
        legend_width = 220
        start_y = 20
        start_x = self.screen_width - legend_width - 10
        circle_radius = 8  # Circle radius
        padding = 8  # Padding inside the box
        spacing = 4  # Spacing between legends

        # Update legends with current time tolerance
        self.legends[4] = (f"Time tolerance: {self.time_tolerance:.2f}s", (150, 150, 150))

        # Calculate the height of the box
        total_height = len(self.legends) * legend_height + (len(self.legends) - 1) * spacing + padding * 2

        # Draw box background
        pygame.draw.rect(
            self.screen, 
            (220, 220, 220),  # Light gray background
            pygame.Rect(start_x - padding, start_y - padding, legend_width + padding * 2, total_height),
            border_radius=10  # Rounded corners
        )

        for i, (label, color) in enumerate(self.legends):
            y = start_y + i * (legend_height + spacing)
            
            # Draw circle
            circle_center = (start_x + circle_radius, y + circle_radius)  # Circle center position
            pygame.draw.circle(self.screen, color, circle_center, circle_radius)
            
            # Render and draw text
            text = self.legend_font.render(label, True, (0, 0, 0))
            self.screen.blit(text, (start_x + circle_radius * 2 + 10, y + 2.5))  # Slightly adjust text position

    def draw_piano_keyboard(self):
        # Piano dimensions
        keyboard_height = 200
        keyboard_y = self.screen_height - keyboard_height

        # Calculate key widths
        self.white_key_width = self.screen_width / 52
        self.black_key_width = self.white_key_width * 0.7
        self.black_key_height = keyboard_height * 0.6

        WHITE = (255, 255, 255)
        BLACK = (0, 0, 0)

        # Prepare key positions
        self.key_x_positions = {}

        white_key_x = 0
        midi_note = self.min_pitch

        while midi_note <= self.max_pitch:
            is_white = self.is_white_key(midi_note)

            if is_white:
                # Draw white key
                pygame.draw.rect(self.screen, WHITE,
                                (white_key_x, keyboard_y, self.white_key_width - 1, keyboard_height))
                pygame.draw.rect(self.screen, BLACK,
                                (white_key_x, keyboard_y, self.white_key_width - 1, keyboard_height), 1)

                # Record x position
                self.key_x_positions[midi_note] = white_key_x

                # Label the C notes
                if midi_note % 12 == 0:  # Check if the note is C
                    octave = (midi_note // 12) - 1
                    label = f"C{octave}"
                    text_surface = self.font_note.render(label, True, (0, 0, 0))
                    text_x = white_key_x + (self.white_key_width - text_surface.get_width()) / 2
                    text_y = keyboard_y + keyboard_height - text_surface.get_height() - 5
                    self.screen.blit(text_surface, (text_x, text_y))

                white_key_x += self.white_key_width
                midi_note += 1
            else:
                # Black key
                black_x = white_key_x - self.white_key_width * 0.7

                # Draw black key
                pygame.draw.rect(self.screen, BLACK,
                                (black_x, keyboard_y, self.black_key_width, self.black_key_height))

                # Record x position
                self.key_x_positions[midi_note] = black_x

                midi_note += 1

        

        # Define a larger duration tolerance
        duration_tolerance = 5.0  # 您可以根据需要调整这个值

        # Get current time in performance
        if self.falling_notes_start_time is not None:
            current_time = time.time() - self.falling_notes_start_time
        else:
            current_time = 0

        # Initialize the incorrect note detection flag
        incorrect_note_detected = False

        # Highlight active notes
        for note_number in self.active_notes:
            x = self.key_x_positions.get(note_number)
            if x is not None:
                is_white = self.is_white_key(note_number)
                if is_white:
                    key_width = self.white_key_width - 1
                    key_height = keyboard_height
                    key_y = keyboard_y
                else:
                    key_width = self.black_key_width
                    key_height = self.black_key_height
                    key_y = keyboard_y

                # Determine correctness dynamically based on current time and note duration
                correctness = False
                for ref_pitch, ref_start, ref_end, ref_velocity in self.ref_notes:
                    if ref_pitch == note_number:
                        # Allow the note to be held longer without being incorrect
                        if (ref_start - self.time_tolerance) <= current_time <= (ref_end + duration_tolerance):
                            correctness = True
                            break  # Found a matching note, no need to check further

                # Set key color based on dynamic correctness
                if correctness:
                    key_color = (0, 255, 0)  # Green
                else:
                    key_color = (255, 0, 0)  # Red
                    incorrect_note_detected = True  # An incorrect note is being pressed

                # Draw the key with the highlight color
                s = pygame.Surface((key_width, key_height), pygame.SRCALPHA)
                s.fill((*key_color, 100))  # Semi-transparent
                self.screen.blit(s, (x, key_y))

        # After processing all active notes, reset combo if incorrect note is detected
        if incorrect_note_detected:
            self.current_combo = 0
            self.combo_last_increase_time = None  # Reset combo increase time








    def is_note_at_target_line(self, note_number):
        """
        檢查指定音符是否在目標線上，並且正在被按下
        """
        if self.falling_notes_start_time is None:
            return False
            
        current_time = time.time() - self.falling_notes_start_time
        # 擴大容差範圍以確保更好的檢測
        target_tolerance = 0.1  # 容差範圍（秒）
        
        # 檢查音符是否存在於 active_notes 中（表示正在被按下）
        is_note_active = note_number in self.active_notes and self.active_notes[note_number]['velocity'] > 0
        
        if not is_note_active:
            return False
        
        # 檢查是否有對應的參考音符在目標線上
        for pitch, start, end, velocity in self.ref_notes:
            if pitch == note_number:
                # 計算音符與目標線的距離
                time_until_hit = start - current_time
                
                # 檢查音符是否在目標線範圍內
                if abs(time_until_hit) <= target_tolerance:
                    return True
                    
        return False


    def draw_target_line_smoke_effect(self):
        """
        Generate a continuous, subtle smoking effect along the target line.
        """
        # Fewer particles for a lighter effect
        for _ in range(8):
            particle_x = random.uniform(0, self.screen_width)
            # Lower vertical variation
            particle_y = self.target_line_y + random.uniform(-2, 20)
            self.particles.append(TargetLineParticle(particle_x, particle_y))
            
    def draw_visualization(self):
        """
        Visualize falling notes, highlight active notes, and add continuous smoke effect to the target line.
        """
        # Add continuous smoke effect to the target line
        self.draw_target_line_smoke_effect()

        # Update and draw smoke particles
        self.update_smoke_particles()
        
        self.note_speed = 150  # Pixels per second
        if self.falling_notes_start_time is not None:
            current_time = time.time() - self.falling_notes_start_time
        else:
            current_time = 0

        # Draw reference notes
        for pitch, start, end, velocity in self.ref_notes:
            if pitch < self.min_pitch or pitch > self.max_pitch:
                continue

            time_until_hit = start - current_time
            y = self.target_line_y - (time_until_hit * self.note_speed)
            duration = end - start
            height = int(duration * self.note_speed)

            rect_bottom = y
            rect_top = y - height

            if rect_top >= self.target_line_y:
                continue

            x = self.key_x_positions.get(pitch)
            if x is not None:
                is_white = self.is_white_key(pitch)
                key_width = self.white_key_width if is_white else self.black_key_width

                # Check if smoke effect should be generated for individual notes
                if pitch in self.active_notes and pitch in self.should_smoke:
                    note_data = self.active_notes[pitch]
                    if note_data['velocity'] > 0 and abs(rect_bottom - self.target_line_y) <= self.note_speed * 0.1:
                        self.draw_smoke_effect(x, self.target_line_y, key_width)

                # Draw gradient surface for the note with rounded corners
                if rect_bottom > self.target_line_y:
                    height -= rect_bottom - self.target_line_y
                    rect_bottom = self.target_line_y
                rect_top = rect_bottom - height

                if rect_bottom < 0 or rect_top > self.screen_height:
                    continue

                # Create a gradient surface with rounded corners
                top_color = (0, 200, 255)
                bottom_color = (0, 100, 255)
                note_surface = self.create_gradient_surface(int(key_width), int(height), top_color, bottom_color)
                
                # Clip the surface to fit rounded corners
                rounded_note_surface = pygame.Surface((int(key_width), int(height)), pygame.SRCALPHA)
                pygame.draw.rect(rounded_note_surface, (0, 0, 0, 0), rounded_note_surface.get_rect(), border_radius=5)
                rounded_note_surface.blit(note_surface, (0, 0))
                
                self.screen.blit(rounded_note_surface, (x, rect_top))

                if self.show_syllables and is_white:
                    # Calculate the syllable for the note based on pitch class
                    pitch_class = pitch % 12
                    syllable = self.pitch_class_to_syllable.get(pitch_class, '')

                    if syllable:
                        syllable_text = self.font_note.render(syllable, True, (255, 255, 255))
                        syllable_x = x + key_width // 2 - syllable_text.get_width() // 2
                        syllable_y = rect_bottom - syllable_text.get_height() - 5
                        self.screen.blit(syllable_text, (syllable_x, syllable_y))






    def draw_smoke_layer(self):
        """
        Draw a semi-transparent smoke layer that fades out over time.
        """
        smoke_surface = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        smoke_surface.fill((50, 50, 50, 30))  # Dark gray with low opacity
        self.screen.blit(smoke_surface, (0, 0))

    def update_smoke_particles(self):
        """
        Update and render smoke particles with improved visual effects.
        """
        for particle in self.particles[:]:
            particle.update()
            if particle.is_alive():
                # Create a surface for each particle with per-pixel alpha
                particle_surface = pygame.Surface((particle.radius * 2, particle.radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(
                    particle_surface,
                    particle.color,
                    (particle.radius, particle.radius),
                    int(particle.radius)
                )
                # Blit the particle onto the main screen with additive blending for a glowing effect
                self.screen.blit(
                    particle_surface,
                    (particle.x - particle.radius, particle.y - particle.radius),
                    special_flags=pygame.BLEND_ADD
                )
            else:
                self.particles.remove(particle)
        
        # Limit the total number of particles to prevent performance issues
        MAX_PARTICLES = 500
        if len(self.particles) > MAX_PARTICLES:
            self.particles = self.particles[-MAX_PARTICLES:]


    def is_white_key(self, midi_note_number):
        # Returns True if the note is a white key
        return midi_note_number % 12 in [0, 2, 4, 5, 7, 9, 11]

    def toggle_recording(self):
        if self.is_recording.is_set():
            self.stop_recording()
        else:
            self.start_recording()
            
    def show_countdown(self, dots_left):
        # Define position, size of dots, and colors
        outer_radius = 10
        spacing = 30  # Space between dots
        start_x = 250
        y = 30 # Adjust y-coordinate as needed

        # Clear the entire area before drawing
        self.hide_countdown()

        # Draw each dot with a filled "vanishing" effect
        for i in range(4):  # Always draw the four outer circles
            x = start_x + i * (outer_radius * 2 + spacing)
            pygame.draw.circle(self.screen, (105,105, 105), (x, y), outer_radius)  # Black outer circle
            
            # If the dot should remain partially filled, draw the inner part in the background color
            if i >= dots_left:
                pygame.draw.circle(self.screen, (190, 190, 190), (x, y), outer_radius - 3)  # Vanished middle part

        pygame.display.flip()  # Update display to show the dots

    def hide_countdown(self):
        # Clear the area where dots are displayed
        outer_radius = 10
        spacing = 30
        start_x = 250
        y = 30  # Same y-coordinate as used in show_countdown

        # Calculate total width of dots area
        total_width = (outer_radius * 2 + spacing) * 4 - spacing  # 4 dots and spaces between them

        # Fill with background color to clear
        self.screen.fill((30, 30, 30), (start_x - outer_radius, y - outer_radius, total_width, outer_radius * 2))

    def start_recording(self):
        """Start recording with proper initialization"""
        
        self.current_combo = 0
        self.max_combo = 0
        
        self.note_list.clear()
        self.pedal_list.clear()
        self.should_smoke = {}  # 重置煙霧效果追踪
        self.student_control_pressed_time = -1
        self.student_notes.clear()
        self.bar_scores.clear()
        self.overall_score = {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'note_count': 0, 'duration': 0}
        self.performance_report = ""
        self.is_recording.set()
        
        # Initialize MIDI recording
        self.setup_midi_recording()
        
        # Play countdown beats
        countdown_start = time.time()
        beat_interval = 60.0 / self.BPM
        
        for i in range(4, -1, -1):  # Countdown from 4 to 1
            self.show_countdown(i)  # Show dots for the countdown
            while time.time() < countdown_start + ((4 - i) * beat_interval):
                time.sleep(0.001)
            self.beat_sound.play()
            self.hide_countdown()  # Hide previous dots after each beat

        # Start recording time and threads
        self.recording_start_time = pygame.time.get_ticks()
        self.recording_start_timestamp = time.time()
        
        # **Initialize falling notes start time**
        self.falling_notes_start_time = time.time()
        
        self.start_metronome()
        
        # Start MIDI processing thread
        self.midi_thread = threading.Thread(target=self.process_midi_input)
        self.midi_thread.daemon = True
        self.midi_thread.start()

        
    def stop_recording(self):
        """Stop recording and save MIDI file"""
        self.is_recording.clear()
        self.stop_metronome()
        
        # **Reset falling notes start time**
        self.falling_notes_start_time = None
        
        # Wait for threads to finish
        if self.midi_thread:
            self.midi_thread.join()
            self.midi_thread = None
            
        # Save the recorded MIDI file
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"performance_{timestamp}.mid"
        self.student_midi_file = self.save_recorded_midi(filename)
        
        # Generate performance report
        self.re_adjust_note_list()
        self.generate_performance_report()
        self.generate_overall_comment()
        if self.student_midi_file is not None:
            self.generate_ar_vl_path()
        else:
            print("ERROR: Student performance did not write to file")
        print(self.performance_report)
        

    def draw_dynamic_line(self):
        """Draw the target line where notes should be hit."""
        pygame.draw.line(self.screen, (255, 255, 255), (0, self.target_line_y), (self.screen_width, self.target_line_y), 2)

    def get_ref_midi_end_time(self):
        try:
            end_time =  max([end for _, _, end, _ in self.ref_notes])
            return end_time
        except Exception as e:
            print(f"Error loading reference MIDI: {e}")
            return -1
        
    def create_file_if_not_exist(self, path):
        # Extract the directory from the path
        directory = os.path.dirname(path)

        # Create the directory if it doesn't exist
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Create the file (if it doesn't exist)
        if not os.path.exists(path):
            with open(path, 'w') as file:
                file.write("")  # Create an empty file
        
    # Function to save the entire content surface to a multi-page PDF
    def save_content_to_pdf(self, surface):
        # Create a PDF
        pdf = FPDF()
        pdf_width_setup = 794
        pdf_height_setup = 1122
        screenshot_to_pdf_page_ratio = pdf_width_setup / self.screen_width
        # Number of pages required to cover the content height
        page_surface_y = pdf_height_setup / screenshot_to_pdf_page_ratio
        #num_pages = int((self.surface_height + self.screen_height - 1) // page_surface_y + 1)
        num_pages = int((self.surface_height) // page_surface_y + 1)

        for page_num in range(num_pages):
            # Define the area of content to capture
            page_surface = pygame.Surface((self.screen_width, page_surface_y))
            page_surface.blit(surface, (0, 0), (0, page_num * page_surface_y, self.screen_width, page_surface_y))# x * ratio = 1122

            # Save the page image temporarily
            page_image_path = f"./temporary_files/page_{page_num}.png" #changed 1204
            self.create_file_if_not_exist(page_image_path)
            pygame.image.save(page_surface, page_image_path)
            
            # Open the saved image and get dimensions
            image = Image.open(page_image_path)
            image = image.resize((pdf_width_setup, pdf_height_setup))
            width, height = image.size
            # Convert pixel dimensions to mm for PDF (assuming 96 dpi)
            pdf_width, pdf_height = width * 0.2645, height * 0.2645  # pixels to mm

            # Add a new page to the PDF and insert the image
            pdf.add_page()
            pdf.image(page_image_path, 0, 0, pdf_width, pdf_height)

        # Output the final PDF
        pdf_path = "./temporary_files/output_full_content_multipage.pdf"
        self.create_file_if_not_exist(pdf_path)
        pdf.output(pdf_path)
        print("PDF has been output")

    def report_compare_with_tolerance(self, tolerance=0.1, velocity_tolerance=20): #to update note_list color when entering report / updating tolerance in report settings 
        temp_note_list = []
        for note in self.note_list:
            pitch, start_time, end_time, correct, color, velocity = note
            closest_ref_note = None
            closest_time_diff = float('inf')

            # Debug: Print the student note being processed
            #print(f"[DEBUG] (report_compare) Processing student note: {note}")

            # Find the closest reference note with matching pitch within tolerance
            for ref_pitch, ref_start, ref_end, ref_velocity in self.ref_notes:
                if ref_pitch == pitch:  # Match the pitch first
                    time_diff = abs(start_time - ref_start)
                    if time_diff < closest_time_diff and time_diff <= tolerance:
                        closest_time_diff = time_diff
                        closest_ref_note = (ref_pitch, ref_start, ref_end, ref_velocity)

            # If a match is found, process further
            if closest_ref_note:
                ref_pitch, ref_start, ref_end, ref_velocity = closest_ref_note

                # Debug: Output the matching reference note details
                #print(f"[DEBUG] (report_compare) Matched student note {note} with reference note {closest_ref_note}")

                # Calculate velocity difference
                vel_diff = ref_velocity - velocity

                # Determine the color for visualization based on velocity tolerance
                if abs(vel_diff) <= velocity_tolerance:
                    color = self.colors['correct']
                elif vel_diff < -velocity_tolerance:
                    color = self.colors['too_hard']
                else:
                    color = self.colors['too_light']

                # Add the note to the visualization list (cut down in this function # see compare_and_visualize)
                #self.note_list.append((pitch, start_time, end_time, True, color, velocity))
                temp_note_list.append((pitch, start_time, end_time, True, color, velocity))
            else:
                # No match found, mark the note as incorrect
                #print(f"[DEBUG] (report_compare) No match found for student note: {note}")
                #self.note_list.append((pitch, start_time, end_time, False, self.colors['incorrect'], velocity))
                temp_note_list.append((pitch, start_time, end_time, False, self.colors['incorrect'], velocity))
        #return temp_note_list
        self.note_list = temp_note_list

    def find_note_segment_off(self, note_pitch, note_time):#pitch, start
        temp_segment = [x for x in self.recorded_events if x["timestamp"] > note_time and x["type"] == "note_off" and x["note"] == note_pitch]
        if(len(temp_segment)==0):
            return None
        minObject = min(temp_segment, key=lambda x:x["timestamp"])
        return minObject

    def re_adjust_note_list(self):
        temp_note_list = []
        for note in self.note_list:
            pitch, start, end, correct, color, velocity = note
            new_end = self.find_note_segment_off(pitch, start)["timestamp"]
            temp_note_list.append((pitch, start, new_end, correct, color, velocity))
        self.note_list = temp_note_list
        
                
    def draw_tooltip(self, surface, text, x, y):
        """Draw a tooltip box with given text at the specified (x, y) position."""
        padding = 5
        font = self.font_note
        text_surface = font.render(text, True, (0, 0, 0))
        w = text_surface.get_width() + padding * 2
        h = text_surface.get_height() + padding * 2

        # Position tooltip slightly offset from the mouse pointer
        tooltip_x = x + 20
        tooltip_y = y + 20

        # Draw background and border
        pygame.draw.rect(surface, (255, 255, 225), (tooltip_x, tooltip_y, w, h))
        pygame.draw.rect(surface, (0, 0, 0), (tooltip_x, tooltip_y, w, h), 1)

        # Draw text
        surface.blit(text_surface, (tooltip_x + padding, tooltip_y + padding))
        

    def draw_report(self):
        self.y_intercept = self.screen_height * 1 / 4
        self.x_intercept = self.screen_width / 10

        # calculation of the height of the report 
        ref_midi_end_time = self.get_ref_midi_end_time()
        bar_duration = (240 / self.BPM)
        amount_of_bars = int(ref_midi_end_time // bar_duration) + 1
        amount_of_lines = (amount_of_bars // 4) + 1
        self.surface_height = self.y_intercept + self.screen_height * 2 / 3 * (amount_of_lines + 1) 

        self.report_surface = pygame.Surface((self.screen_width, self.surface_height))
        self.report_surface.fill((255, 255, 255))  # White background
        self.scroll_speed = self.screen_height * 2 / 8

        self.scaling_factor = 1.3 * 1000 // (self.screen_width / self.BPM)
        self.pitch_y_diff = self.screen_height / 120
        self.control_y_diff = self.screen_height / 4 + self.screen_height / 12

        # Draw the performance report and scores at the top
        # Parse report lines
        report_lines = self.performance_report.split('\n')
        line_height = 20
        header_y = 20

        for i, line in enumerate(report_lines):
            # If the line is "Performance Metrics" or "AI comments", use a bold font
            if line.strip() == "Performance Metrics" or line.strip() == "AI Comments" or line.strip() == "Color Representation":
                text_surface = self.font_report_title.render(line, True, (0, 0, 0))
            else:
                text_surface = self.font_report.render(line, True, (0, 0, 0))

            self.report_surface.blit(text_surface, (20, header_y + i * line_height))


        # After drawing the report text, we start drawing the notes lower down
        # Move the music visualization down after the report text
        visualize_offset_y = header_y + (len(report_lines) * line_height) + 40
        # Adjust the intercept so that notes start below the report text
        base_y_intercept = self.y_intercept + visualize_offset_y

        mouse_pos = pygame.mouse.get_pos()
        mouse_x, mouse_y = mouse_pos
        mouse_y_adjusted = mouse_y + self.scroll_y  # Adjust for scrolling

        # Store note rects for hover detection
        note_rects = []  # Each item: (rect, pitch, velocity)

        #1211: making the horizontal scrollable surface for the notes
        self.horizontal_scroll_surface_width = self.screen_width * amount_of_lines
        self.horizontal_scroll_surface_height = self.screen_height * 2 / 3
        self.horizontal_scroll_surface = pygame.Surface((self.horizontal_scroll_surface_width, self.horizontal_scroll_surface_height))
        self.horizontal_scroll_surface.fill((255, 255, 255))  # White background
        self.horizontal_scroll_speed = self.screen_width * 2 / 8
        self.horizontal_scroll_surface_mouse_pos_rect = pygame.Rect(0, visualize_offset_y - self.scroll_y, self.screen_width, (self.screen_height * 2 / 3))

        # Draw reference notes (gray)
        for pitch, start, end, velocity in self.ref_notes:
            y = (self.screen_height * 2 / 9) - (pitch - 71) * self.pitch_y_diff # 2/3 * 2/3 * 1/2
            x = self.x_intercept + start * self.scaling_factor
            width = (end - start) * self.scaling_factor
            rect = pygame.Rect(x, y, width, 8)
            pygame.draw.rect(self.horizontal_scroll_surface, (190, 190, 190), rect)

        # Draw student notes with their assigned colors
        for note in self.note_list:
            pitch, start, end, correct, color, velocity = note
            y = (self.screen_height * 2 / 9) - (pitch - 71) * self.pitch_y_diff
            x = self.x_intercept + start * self.scaling_factor
            width = (end - start) * self.scaling_factor
            rect = pygame.Rect(x, y, width, 8)
            pygame.draw.rect(self.horizontal_scroll_surface, color, rect)

            # Store info for hover tooltips
            note_rects.append((rect, pitch, velocity))

        # Draw reference pedal (gray)
        first_control = True
        last_control = -1
        for number, value, time in self.ref_control:
            if number == 64:
                if value == 0: # release
                    if first_control:
                        y1 = (self.screen_height * 2 / 9) + self.control_y_diff
                        y2 = y1 + 10
                        x1 = self.x_intercept
                        x2 = self.x_intercept + time * self.scaling_factor
                        points = [(x1, y2), (x2, y2), (x2, y1)]
                        pygame.draw.lines(self.horizontal_scroll_surface, (190, 190, 190), False, points, width=3)
                        first_control = False
                    else:
                        y1 = (self.screen_height * 2 / 9) + self.control_y_diff
                        y2 = y1 + 10
                        x1 = self.x_intercept + pedal_pressed_time * self.scaling_factor
                        x2 = self.x_intercept + time * self.scaling_factor
                        points = [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]
                        pygame.draw.lines(self.horizontal_scroll_surface, (190, 190, 190), False, points, width=3)
                elif value > 0: # pressed
                    pedal_pressed_time = time
                    if first_control:
                        first_control = False
                last_control = value
            else:
                continue
        if last_control > 0: # pedal pressed and unreleased
            y1 = (self.screen_height * 2 / 9) + self.control_y_diff
            y2 = y1 + 10
            x1 = self.x_intercept + pedal_pressed_time * self.scaling_factor
            x2 = self.x_intercept + (bar_duration * 4) * amount_of_lines * self.scaling_factor
            points = [(x1, y1), (x1, y2), (x2, y2)]
            pygame.draw.lines(self.horizontal_scroll_surface, (190, 190, 190), False, points, width=3)

        # Student pedal
        for pedal in self.pedal_list:
            pedal_start_time, pedal_end_time, correctness, color = pedal
            y1 = (self.screen_height * 2 / 9) + self.control_y_diff + 5
            y2 = y1 + 10
            x1 = self.x_intercept + pedal_start_time * self.scaling_factor
            x2 = self.x_intercept + pedal_end_time  * self.scaling_factor
            points = [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]
            pygame.draw.lines(self.horizontal_scroll_surface, color, False, points, width=3)

        # Draw the close, print, and settings buttons at the bottom
        close_button_x = (self.screen_width - 100) // 4
        close_button_y = self.surface_height - 100
        self.close_button_rect = pygame.Rect(close_button_x, close_button_y, 100, 40)

        print_button_x = (self.screen_width - 100) * 2 // 4
        print_button_y = self.surface_height - 100
        self.print_button_rect = pygame.Rect(print_button_x, print_button_y, 100, 40)

        settings_button_x = (self.screen_width - 100) * 3 // 4
        settings_button_y = self.surface_height - 100
        self.report_settings_button_rect = pygame.Rect(settings_button_x, settings_button_y, 100, 40)

        self.emulate_close_button_rect = pygame.Rect(close_button_x, close_button_y - self.scroll_y, 100, 40)
        self.emulate_print_button_rect = pygame.Rect(print_button_x, print_button_y - self.scroll_y, 100, 40)
        self.emulate_report_settings_button_rect = pygame.Rect(settings_button_x, settings_button_y - self.scroll_y, 100, 40)

        mouse_pos = pygame.mouse.get_pos()
        # Check hover states for buttons
        if self.emulate_close_button_rect.collidepoint(mouse_pos):
            close_color = (173, 216, 230)
        else:
            close_color = (200, 200, 200)

        if self.emulate_print_button_rect.collidepoint(mouse_pos):
            print_color = (173, 216, 230)
        else:
            print_color = (200, 200, 200)

        if self.emulate_report_settings_button_rect.collidepoint(mouse_pos):
            settings_color = (173, 216, 230)
        else:
            settings_color = (200, 200, 200)

        self.draw_button_with_shadow(self.report_surface, self.close_button_rect, "Close", self.font_title, active=False)
        self.draw_button_with_shadow(self.report_surface, self.print_button_rect, "Print", self.font_title, active=False)
        self.draw_button_with_shadow(self.report_surface, self.report_settings_button_rect, "Settings", self.font_title, active=False)

        # Check if mouse is hovering over a note
        for rect, pitch, velocity in note_rects:
            #y = self.y_intercept + self.screen_height / 4 - (pitch - 71) * self.pitch_y_diff
            #x = self.x_intercept + start * self.scaling_factor
            # on horizontal_scroll_surface
            adjusted_rect = pygame.Rect(rect.x - self.scroll_x, rect.y + visualize_offset_y - self.scroll_y, rect.width, rect.height)
            if adjusted_rect.collidepoint(mouse_pos):
                # Show tooltip
                pitch_class = pitch % 12
                syllable = self.pitch_class_to_syllable.get(pitch_class, '')
                tooltip_text = f"P{pitch} V{velocity} {syllable}"
                self.draw_tooltip(self.horizontal_scroll_surface, tooltip_text, mouse_x + self.scroll_x, mouse_y - visualize_offset_y + self.scroll_y)
                break

        #boundary of horizontal scroll surface
        testing = True
        if testing:
            pygame.draw.line(self.horizontal_scroll_surface, (0, 0, 0), (0, 0), (self.horizontal_scroll_surface_width, 0), 3)
            pygame.draw.line(self.horizontal_scroll_surface, (0, 0, 0), (0, self.horizontal_scroll_surface_height - 1)
                             , (self.horizontal_scroll_surface_width, self.horizontal_scroll_surface_height - 1), 3)

        self.screen.blit(self.report_surface, (0, -self.scroll_y))
        self.screen.blit(self.horizontal_scroll_surface, (-self.scroll_x, visualize_offset_y - self.scroll_y))


    def update_bpm_and_tolerance(self, new_bpm, new_time_tolerance):
        self.BPM = new_bpm
        self.time_tolerance = new_time_tolerance
        self.ticks_per_second = (self.ticks_per_beat * self.BPM) / 60
        # Reload reference MIDI with new BPM
        self.ref_notes, self.ref_control = self.load_reference_midi(self.reference_path)
        # Recalculate total duration
        self.total_duration = max([end for _, _, end, _ in self.ref_notes])
        # Update beat sound
        self.beat_sound = self.generate_beat_sound(duration=self.metronome_duration)
        # Clear previous data
        self.note_list.clear()
        self.pedal_list.clear()
        self.student_control_pressed_time = -1
        self.student_notes.clear()
        self.bar_scores.clear()
        self.overall_score = {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'note_count': 0, 'duration': 0}
        self.performance_report = ""
        self.bpm_text = ''  # Clear the BPM text input
        self.time_tolerance_text = ''  # Clear the time tolerance input

    def draw_settings_menu(self):
        # Semi-transparent background
        s = pygame.Surface((self.screen_width, self.screen_height))
        s.set_alpha(150)
        s.fill((0, 0, 0))
        self.screen.blit(s, (0, 0))

        # Settings menu box
        menu_width = 300
        menu_height = 200
        menu_x = (self.screen_width - menu_width) // 2
        menu_y = (self.screen_height - menu_height) // 2
        menu_rect = pygame.Rect(menu_x, menu_y, menu_width, menu_height)
        pygame.draw.rect(self.screen, (240, 240, 240), menu_rect, border_radius=10)

        # BPM input
        bpm_label = self.font_title.render("BPM:", True, (0, 0, 0))
        self.screen.blit(bpm_label, (menu_x + 20, menu_y + 30))
        bpm_input_rect = pygame.Rect(menu_x + 100, menu_y + 25, 150, 30)
        pygame.draw.rect(self.screen, (255, 255, 255), bpm_input_rect, border_radius=5)
        bpm_text_surface = self.font_title.render(self.bpm_text, True, (0, 0, 0))
        self.screen.blit(bpm_text_surface, (bpm_input_rect.x + 5, bpm_input_rect.y + 5))

        # Time tolerance input
        tolerance_label = self.font_title.render("Time Tol:", True, (0, 0, 0))
        self.screen.blit(tolerance_label, (menu_x + 20, menu_y + 80))
        tolerance_input_rect = pygame.Rect(menu_x + 100, menu_y + 75, 150, 30)
        pygame.draw.rect(self.screen, (255, 255, 255), tolerance_input_rect, border_radius=5)
        tolerance_text_surface = self.font_title.render(self.time_tolerance_text, True, (0, 0, 0))
        self.screen.blit(tolerance_text_surface, (tolerance_input_rect.x + 5, tolerance_input_rect.y + 5))
        
        # OK button
        ok_button_rect = pygame.Rect(menu_x + 50, menu_y + 130, 80, 30)
        cancel_button_rect = pygame.Rect(menu_x + 170, menu_y + 130, 80, 30)

        mouse_pos = pygame.mouse.get_pos()

        # OK Button
        if ok_button_rect.collidepoint(mouse_pos):
            ok_color = (173, 216, 230)
        else:
            ok_color = (200, 200, 200)
        pygame.draw.rect(self.screen, ok_color, ok_button_rect, border_radius=5)
        ok_text = self.font_title.render("OK", True, (0, 0, 0))
        self.screen.blit(ok_text, (ok_button_rect.x + 20, ok_button_rect.y + 5))

        # Cancel Button
        if cancel_button_rect.collidepoint(mouse_pos):
            cancel_color = (173, 216, 230)
        else:
            cancel_color = (200, 200, 200)
        pygame.draw.rect(self.screen, cancel_color, cancel_button_rect, border_radius=5)
        cancel_text = self.font_title.render("Cancel", True, (0, 0, 0))
        self.screen.blit(cancel_text, (cancel_button_rect.x + 5, cancel_button_rect.y + 5))

        self.bpm_input_rect = bpm_input_rect
        self.tolerance_input_rect = tolerance_input_rect
        self.ok_button_rect = ok_button_rect
        self.cancel_button_rect = cancel_button_rect

    def report_settings_update_both_tolerance(self, new_time_tolerance, new_velocity_tolerance): # to change time and velocity tolerance value
        self.time_tolerance = new_time_tolerance
        self.velocity_tolerance = new_velocity_tolerance

    def draw_report_settings_menu(self):
        # Semi-transparent background
        s = pygame.Surface((self.screen_width, self.screen_height))
        s.set_alpha(150)
        s.fill((0, 0, 0))
        self.screen.blit(s, (0, 0))

        # Settings menu box
        menu_width = 300
        menu_height = 200
        menu_x = (self.screen_width - menu_width) // 2
        menu_y = (self.screen_height - menu_height) // 2
        menu_rect = pygame.Rect(menu_x, menu_y, menu_width, menu_height)
        pygame.draw.rect(self.screen, (240, 240, 240), menu_rect, border_radius=10)

        # Time tolerance input
        tolerance_label = self.font_title.render("Time Tol:", True, (0, 0, 0))
        self.screen.blit(tolerance_label, (menu_x + 20, menu_y + 30))
        tolerance_input_rect = pygame.Rect(menu_x + 100, menu_y + 25, 150, 30)
        pygame.draw.rect(self.screen, (255, 255, 255), tolerance_input_rect, border_radius=5)
        tolerance_text_surface = self.font_title.render(self.report_time_tolerance_text, True, (0, 0, 0))
        self.screen.blit(tolerance_text_surface, (tolerance_input_rect.x + 5, tolerance_input_rect.y + 5))

        # Velocity Tolerance input
        velocity_tolerance_label = self.font_title.render("Velo Tol:", True, (0, 0, 0))
        self.screen.blit(velocity_tolerance_label, (menu_x + 20, menu_y + 80))
        velocity_tolerance_input_rect = pygame.Rect(menu_x + 100, menu_y + 75, 150, 30)
        pygame.draw.rect(self.screen, (255, 255, 255), velocity_tolerance_input_rect, border_radius=5)
        velocity_tolerance_text_surface = self.font_title.render(self.report_velocity_tolerance_text, True, (0, 0, 0))
        self.screen.blit(velocity_tolerance_text_surface, (velocity_tolerance_input_rect.x + 5, velocity_tolerance_input_rect.y + 5))

        # OK button
        ok_button_rect = pygame.Rect(menu_x + 50, menu_y + 130, 80, 30)
        cancel_button_rect = pygame.Rect(menu_x + 170, menu_y + 130, 80, 30)

        mouse_pos = pygame.mouse.get_pos()

        # OK Button
        if ok_button_rect.collidepoint(mouse_pos):
            ok_color = (173, 216, 230)
        else:
            ok_color = (200, 200, 200)
        pygame.draw.rect(self.screen, ok_color, ok_button_rect, border_radius=5)
        ok_text = self.font_title.render("OK", True, (0, 0, 0))
        self.screen.blit(ok_text, (ok_button_rect.x + 20, ok_button_rect.y + 5))

        # Cancel Button
        if cancel_button_rect.collidepoint(mouse_pos):
            cancel_color = (173, 216, 230)
        else:
            cancel_color = (200, 200, 200)
        pygame.draw.rect(self.screen, cancel_color, cancel_button_rect, border_radius=5)
        cancel_text = self.font_title.render("Cancel", True, (0, 0, 0))
        self.screen.blit(cancel_text, (cancel_button_rect.x + 5, cancel_button_rect.y + 5))

        self.report_time_tolerance_input_rect = tolerance_input_rect
        self.report_velocity_tolerance_input_rect = velocity_tolerance_input_rect
        self.report_ok_button_rect = ok_button_rect
        self.report_cancel_button_rect = cancel_button_rect
        
    def run(self):
        running = True
        clock = pygame.time.Clock()

        while running:
            self.screen_width, self.screen_height = pygame.display.get_surface().get_size()

            self.target_line_y = self.screen_height - 200

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = event.pos

                    if self.record_button_rect.collidepoint(mouse_pos) and not self.show_settings_menu and not self.animation_menu_active:
                        self.toggle_recording()
                        if not self.is_recording.is_set():
                            self.showing_report = True
                            #self.re_adjust_note_list() # moved to stop_recording()
                            self.report_compare_with_tolerance(self.time_tolerance, self.velocity_tolerance) #compare note_list with tolerance to get new color

                    elif self.showing_report and not self.showing_report_settings_menu:#main/report #draw_report
                        if self.emulate_close_button_rect.collidepoint(mouse_pos): #close button
                            self.showing_report = False
                            self.reset_for_new_session()

                        elif self.emulate_print_button_rect.collidepoint(mouse_pos): #print button
                            print("clicked")
                            self.save_content_to_pdf(self.report_surface)

                        elif self.emulate_report_settings_button_rect.collidepoint(mouse_pos): # settings button
                            self.showing_report_settings_menu = True
                            self.report_time_tolerance_input_active = False
                            self.report_velocity_tolerance_input_active = False
                            self.report_time_tolerance_text = str(self.time_tolerance)
                            self.report_velocity_tolerance_text = str(self.velocity_tolerance)
                            

                    elif self.showing_report and self.showing_report_settings_menu: #main/report/settings #draw_report_settings
                        if self.report_time_tolerance_input_rect.collidepoint(mouse_pos): #main/report/settings/timetolerance
                            self.report_time_tolerance_input_active = True
                            self.report_velocity_tolerance_input_active = False

                        elif self.report_velocity_tolerance_input_rect.collidepoint(mouse_pos): #main/report/settings/timetolerance
                            self.report_time_tolerance_input_active = False
                            self.report_velocity_tolerance_input_active = True

                        elif self.report_ok_button_rect.collidepoint(mouse_pos):
                            try:
                                new_time_tolerance = float(self.report_time_tolerance_text)
                                new_velocity_tolerance = float(self.report_velocity_tolerance_text)
                                #self.update_bpm_and_tolerance(new_bpm, new_time_tolerance)
                                self.report_settings_update_both_tolerance(new_time_tolerance, new_velocity_tolerance)
                                self.report_compare_with_tolerance(self.time_tolerance, self.velocity_tolerance) #compare note_list with new tolerance to get new color
                            except ValueError:
                                print("Invalid input for BPM or time tolerance.")
                            self.showing_report_settings_menu = False

                        elif self.report_cancel_button_rect.collidepoint(mouse_pos):
                            self.showing_report_settings_menu = False
                            self.report_time_tolerance_input_active = False
                            self.report_velocity_tolerance_input_active = False

                    elif self.show_button_rect.collidepoint(mouse_pos) and not self.show_settings_menu and not self.animation_menu_active:
                        self.showing_report = not self.showing_report
                    elif self.settings_button_rect.collidepoint(mouse_pos) and not self.show_settings_menu and not self.animation_menu_active:
                        self.show_settings_menu = True
                        self.bpm_input_active = False
                        self.time_tolerance_input_active = False
                        self.bpm_text = str(self.BPM)
                        self.time_tolerance_text = str(self.time_tolerance)
                    elif self.syllable_button_rect.collidepoint(mouse_pos) and not self.animation_menu_active:
                        self.show_syllables = not self.show_syllables
                    elif self.animation_button_rect.collidepoint(mouse_pos):
                        self.animation_menu_active = True
                    elif self.show_settings_menu:
                        if self.bpm_input_rect.collidepoint(mouse_pos):
                            self.bpm_input_active = True
                            self.time_tolerance_input_active = False
                        elif self.tolerance_input_rect.collidepoint(mouse_pos):
                            self.time_tolerance_input_active = True
                            self.bpm_input_active = False
                        elif self.ok_button_rect.collidepoint(mouse_pos):
                            try:
                                new_bpm = int(self.bpm_text)
                                new_time_tolerance = float(self.time_tolerance_text)
                                self.update_bpm_and_tolerance(new_bpm, new_time_tolerance)
                            except ValueError:
                                print("Invalid input for BPM or time tolerance.")
                            self.show_settings_menu = False
                        elif self.cancel_button_rect.collidepoint(mouse_pos):
                            self.show_settings_menu = False
                            self.bpm_input_active = False
                            self.time_tolerance_input_active = False
                elif event.type == pygame.KEYDOWN:
                    if self.show_settings_menu:
                        if self.bpm_input_active:
                            self.handle_text_input(event, target="bpm")
                        elif self.time_tolerance_input_active:
                            self.handle_text_input(event, target="time_tolerance")
                    elif self.showing_report and self.showing_report_settings_menu:
                        if self.report_time_tolerance_input_active:
                            self.handle_text_input(event, target="report_settings_time_tolerance")
                        elif self.report_velocity_tolerance_input_active:
                            self.handle_text_input(event, target="report_settings_velocity_tolerance")

                elif event.type == pygame.MOUSEWHEEL:
                    mouse_pos = pygame.mouse.get_pos()
                    #horizontal_scroll_surface_mouse_pos_rect
                    if self.showing_report:
                        if self.horizontal_scroll_surface_mouse_pos_rect.collidepoint(mouse_pos):
                            self.scroll_x -= event.y * self.horizontal_scroll_speed
                            self.scroll_x = max(0, min(self.scroll_x, self.horizontal_scroll_surface_width - self.screen_width))  # Keep scroll within bounds
                        else:
                            self.scroll_y -= event.y * self.scroll_speed
                            self.scroll_y = max(0, min(self.scroll_y, self.surface_height - self.screen_height))  # Keep scroll within bounds

            # 清空畫面
            self.screen.fill((0, 0, 0))
            
            # Display the logo in the top-left corner
            self.screen.blit(self.logo, (0, 0))  # Coordinates (10, 10) for some padding from the edges
            
            # 更新和繪製火焰粒子
            if self.show_combo:
                self.update_and_draw_fire_particles()

            # 繪製鋼琴鍵盤和其他視覺效果
            self.draw_piano_keyboard()
            self.draw_visualization()
            self.draw_dynamic_line()
            
            # 繪製 GIF
            if self.show_gif:
                self.draw_gif()

            # 繪製 combo 數字
            if self.show_combo:
                self.generate_fire_particles()
                self.draw_combo()

            # 顯示按鈕
            mouse_pos = pygame.mouse.get_pos()
            record_text = "Stop" if self.is_recording.is_set() else "Start"
            record_active = self.record_button_rect.collidepoint(mouse_pos)
            self.draw_button_with_shadow(self.screen, self.record_button_rect, record_text, self.font_title, active=record_active)

            show_text = "Show" if not self.showing_report else "UnShow"
            show_active = self.show_button_rect.collidepoint(mouse_pos)
            self.draw_button_with_shadow(self.screen, self.show_button_rect, show_text, self.font_title, active=show_active)

            settings_active = self.settings_button_rect.collidepoint(mouse_pos)
            self.draw_button_with_shadow(self.screen, self.settings_button_rect, "Settings", self.font_title, active=settings_active)

            syllable_text = "Hide Syllables" if self.show_syllables else "Show Syllables"
            syllable_active = self.syllable_button_rect.collidepoint(mouse_pos)
            self.draw_button_with_shadow(self.screen, self.syllable_button_rect, syllable_text, self.font_title, active=syllable_active)

            animation_active = self.animation_button_rect.collidepoint(mouse_pos)
            self.draw_button_with_shadow(self.screen, self.animation_button_rect, "Animation", self.font_title, active=animation_active)
            
            # Draw BPM and Time Tolerance labels
            bpm_label = self.font_title.render(f"BPM: {self.BPM}", True, (255, 255, 255))
            self.screen.blit(bpm_label, (self.settings_button_rect.left + 10, self.settings_button_rect.bottom + 90))

            tolerance_label = self.font_title.render(f"Time Tolerance: {self.time_tolerance:.2f} sec", True, (255, 255, 255))
            self.screen.blit(tolerance_label, (self.settings_button_rect.left + 10, self.settings_button_rect.bottom + 110))

            # 顯示動畫選單
            if self.animation_menu_active:
                self.draw_animation_menu()

            # 畫出設定和報告
            if self.showing_report:
                self.draw_report()
                if self.showing_report_settings_menu:
                    self.draw_report_settings_menu()
            if self.show_settings_menu:
                self.draw_settings_menu()

            pygame.display.flip()
            clock.tick(60)

        self.stop_recording()
        if self.midi_input:
            self.midi_input.close()
        pygame.quit()





    def handle_text_input(self, event, target):
        if event.key == pygame.K_RETURN:
            if target == "bpm":
                self.bpm_input_active = False
            elif target == "time_tolerance":
                self.time_tolerance_input_active = False
            elif target == "report_settings_time_tolerance":
                self.report_time_tolerance_input_active = False
            elif target == "report_settings_velocity_tolerance":
                self.report_velocity_tolerance_input_active = False

        elif event.key == pygame.K_BACKSPACE:
            if target == "bpm":
                self.bpm_text = self.bpm_text[:-1]
            elif target == "time_tolerance":
                self.time_tolerance_text = self.time_tolerance_text[:-1]
            elif target == "report_settings_time_tolerance":
                self.report_time_tolerance_text = self.report_time_tolerance_text[:-1]
            elif target == "report_settings_velocity_tolerance":
                self.report_velocity_tolerance_text = self.report_velocity_tolerance_text[:-1]
        else:
            if target == "bpm":
                self.bpm_text += event.unicode
            elif target == "time_tolerance":
                self.time_tolerance_text += event.unicode
            elif target == "report_settings_time_tolerance":
                self.report_time_tolerance_text += event.unicode
            elif target == "report_settings_velocity_tolerance":
                self.report_velocity_tolerance_text += event.unicode

    def reset_for_new_session(self):
        self.bar_scores.clear()
        self.overall_score = {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'note_count': 0, 'duration': 0}
        self.note_list.clear()
        self.pedal_list.clear()
        self.student_control_pressed_time = -1
        self.falling_notes_start_time = None


        
if __name__ == "__main__":
    app = DynamicMusicSheet()
    app.run()

