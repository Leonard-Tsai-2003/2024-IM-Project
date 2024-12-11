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
from midiutil import MIDIFile
import os
from game_ChatGPT_comment import *

BPM_global = 108
    
class DynamicMusicSheet:
    def __init__(self):
        # Screen Info Initialization
        pygame.init()
        pygame.font.init()
        screen_info = pygame.display.Info()
        self.screen_width, self.screen_height = screen_info.current_w, screen_info.current_h
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.RESIZABLE)
        pygame.display.set_caption("Dynamic Music Sheet - Real-time Visualization")
        
        # Tolerance Param Initialization
        self.time_tolerance = 0.2
        self.velocity_tolerance = 20
        self.pedal_tolerance = 0.2
        self.pedal_start_tolerance = 2  # New tolerance for pedal start time
        self.pedal_duration_tolerance = 0.2

        # Scoring-related initialization
        self.bar_scores = defaultdict(lambda: {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0})
        self.overall_score = {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'note_count': 0}
        # note count is the amount of all notes, 
        #count is the amount of correct notes
        
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
        # self.midi_record_thread = None
        self.recording_start_timestamp = None
        self.active_notes = {}  # Track currently active notes
        
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
        self.reference_path = '2_t2.mid'

        self.ref_notes, self.ref_control = self.load_reference_midi(self.reference_path)
        self.list_midi_controllers(self.reference_path)
        self.list_all_midi_details(self.reference_path)
        self.total_duration = max([end for _, _, end, _ in self.ref_notes])

        # 嘗試使用系統字體
        self.font_title = pygame.font.SysFont("Verdana", 20)  # Verdana 是一個清晰的系統字體
        self.font_note = pygame.font.SysFont("Verdana", 10)
        self.font_report = pygame.font.SysFont("Verdana", 15)
        self.legend_font = pygame.font.SysFont(None, 22)

        # 測試字體效果（若不存在會默認）
        if not pygame.font.match_font("Verdana"):
            print("Verdana 字體未找到，將使用默認字體。")
            self.font_title = pygame.font.Font(None, 20)
            self.font_note = pygame.font.Font(None, 7)
            self.font_report = pygame.font.Font(None, 7)
        
        self.setup_ui_elements()
        
        # Metronome Initialization
        self.metronome_duration = 0.1
        self.beat_sound = self.generate_beat_sound(duration=self.metronome_duration)
        self.is_playing_metronome = False
        self.metronome_thread = None
        self.bpm_text = ''
        self.bpm_input_active = False  # To track if BPM input is active

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
                    time = control.time * tempo_ratio
                    adjusted_control.append((control.number, control.value, time))
            
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
            
    def list_midi_controllers(self, reference_path):
        try:
            # Load the MIDI file using mido
            midi_file = mido.MidiFile(reference_path)
            controllers = set()
            
            for track in midi_file.tracks:
                for msg in track:
                    if msg.type == 'control_change':
                        controllers.add((msg.control, msg.value))
            
            # Display all unique controllers and their values
            print(f"Controllers found in {reference_path}:")
            for control, value in sorted(controllers):
                print(f"Control Number: {control}, Value: {value}")
                
        except Exception as e:
            print(f"Error: {e}")
        
    def list_all_midi_details(self, reference_path):
        try:
            # Load the MIDI file
            midi_file = mido.MidiFile(reference_path)
            
            # Display general file information
            print(f"File Name: {reference_path}")
            print(f"File Type: {midi_file.type}")
            print(f"Ticks per beat: {midi_file.ticks_per_beat}")
            print(f"Length (seconds): {midi_file.length}")
            print(f"Number of Tracks: {len(midi_file.tracks)}\n")
            
            # Track details
            for i, track in enumerate(midi_file.tracks):
                print(f"Track {i + 1}:")
                print(f"  Name: {track.name}")
                print(f"  Length (number of messages): {len(track)}")
                
                for msg in track:
                    if msg.is_meta:
                        # Meta messages (e.g., time signature, key signature, tempo)
                        print(f"    Meta Message: {msg}")
                    else:
                        # Regular MIDI messages (note_on, note_off, etc.)
                        print(f"    MIDI Message: {msg}")

                    # Detailed parsing for specific message types
                    if msg.type == 'time_signature':
                        print(f"      Time Signature: {msg.numerator}/{msg.denominator}")
                    elif msg.type == 'key_signature':
                        print(f"      Key Signature: {msg.key}")
                    elif msg.type == 'set_tempo':
                        tempo_bpm = mido.tempo2bpm(msg.tempo)
                        print(f"      Tempo: {tempo_bpm} BPM")
                    elif msg.type in ['note_on', 'note_off']:
                        print(f"      Note: {msg.note}, Velocity: {msg.velocity}, Time: {msg.time}")
                    elif msg.type == 'control_change':
                        print(f"      Control: {msg.control}, Value: {msg.value}")
                    elif msg.type == 'program_change':
                        print(f"      Program Change: Program {msg.program}")
                    elif msg.type == 'pitchwheel':
                        print(f"      Pitchwheel: {msg.pitch}")
                print("\n")
        
        except Exception as e:
            print(f"Error: {e}")

    def setup_ui_elements(self):
        self.record_button_rect = pygame.Rect(20, 20, 100, 40)
        self.show_button_rect = pygame.Rect(20, 70, 100, 40)
        self.bpm_button_rect = pygame.Rect(140, 20, 120, 40)  # Add BPM button
        self.bpm_input_rect = pygame.Rect(140, 70, 100, 40)   # Position BPM input below the button
        self.close_button_rect = pygame.Rect(self.screen_width - 60, self.screen_height - 60, 100, 40)

    def draw_rounded_rect(self, surface, color, rect, radius=10):
        pygame.draw.rect(surface, color, rect, border_radius=radius)

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

                    # Create a detailed event structure
                    midi_event = {
                        'type': 'note_on' if status == 144 and velocity > 0 else 
                            'note_off' if (status == 128 or (status == 144 and velocity == 0)) else
                            'control_change' if status == 176 else 'other',
                        'note': note_number,
                        'velocity': velocity,
                        'timestamp': timestamp,
                        'status': status
                    }
                    # Append to recorded events
                    self.recorded_events.append(midi_event)

                    # Existing processing for visualization
                    if status == 144 and velocity > 0:
                        note_start_time = current_time - self.start_time
                        self.student_notes[note_number] = (note_start_time, velocity)
                    elif status == 128 or (status == 144 and velocity == 0):
                        if note_number in self.student_notes:
                            note_start_time, start_velocity = self.student_notes.pop(note_number)
                            note_end_time = current_time - self.start_time
                            self.compare_and_visualize((note_number, note_start_time, note_end_time, start_velocity), self.time_tolerance, self.velocity_tolerance)
                    elif status == 176 and velocity >= 0:  # Control change event
                        if note_number == 64:  # Pedal
                            if velocity > 0:  # Pedal pressed
                                control_start_time = current_time - self.start_time
                                self.student_control_pressed_time = control_start_time
                            elif velocity == 0:  # Pedal released
                                control_end_time = current_time - self.start_time
                                control_start_time = self.student_control_pressed_time
                                if self.student_control_pressed_time >= 0:
                                    self.compare_pedal_and_visulaize((control_start_time, control_end_time), self.pedal_tolerance)
            time.sleep(0.001)

    def calculate_note_score(self, student_note, ref_note):
        pitch_diff = abs(student_note[0] - ref_note[0])
        pitch_score = max(0, 100 - pitch_diff * 2)
        velocity_diff = abs(student_note[3] - ref_note[3])
        velocity_score = max(0, 100 - velocity_diff * 2)  # Deduct 2 points for each velocity difference
        timing_diff = abs(student_note[1] - ref_note[1])
        timing_score = max(0, 100 - timing_diff * 200)  # Deduct 20 points for each 0.1s difference

        return {
            'pitch': pitch_score,
            'velocity': velocity_score,
            'timing': timing_score
        }
             
    def update_scores(self, note_score, bar_number):
        for aspect in ['pitch', 'velocity', 'timing']:
            self.bar_scores[bar_number][aspect] += note_score[aspect]
            self.bar_scores[bar_number]['count'] += 1
            self.overall_score[aspect] += note_score[aspect]
        self.overall_score['count'] += 1

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
        student_duration = student_note[2] - student_note[1]  # end_time - start_time
        ref_duration = ref_note[2] - ref_note[1]
        
        # Calculate duration ratio
        if ref_duration > 0:
            duration_ratio = min(student_duration / ref_duration, ref_duration / student_duration)
            return duration_ratio * 100
        return 0

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
        
        # Find closest reference note with matching pitch
        for ref_pitch, ref_start, ref_end, ref_velocity in self.ref_notes:
            if ref_pitch == pitch:
                time_diff = abs(start_time - ref_start)
                if time_diff < closest_time_diff and time_diff <= tolerance:
                    closest_time_diff = time_diff
                    closest_ref_note = (ref_pitch, ref_start, ref_end, ref_velocity)
        
        if closest_ref_note:
            ref_pitch, ref_start, ref_end, ref_velocity = closest_ref_note
            vel_diff = ref_velocity - velocity
            if abs(vel_diff) <= velocity_tolerance:
                color = self.colors['correct']
            elif vel_diff < -velocity_tolerance:
                color = self.colors['too_hard']
            else:
                color = self.colors['too_light']
            self.note_list.append((pitch, start_time, end_time, True, color, velocity))

            # Calculate and update scores
            note_score = self.calculate_note_score(student_note, closest_ref_note)
            duration_score = self.calculate_duration_score(student_note, closest_ref_note)
            
            bar_number = int(start_time // (240 / self.BPM))  # Assuming 4/4 time signature
            self.update_scores(note_score, bar_number)
            self.update_duration_scores(duration_score, bar_number)
        else:
            self.note_list.append((pitch, start_time, end_time, False, self.colors['incorrect'], velocity))
        
        self.overall_score['note_count'] += 1

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


    def generate_performance_report(self):
        # Calculate basic scores
        avg_pitch = self.overall_score['pitch'] / self.overall_score['note_count'] if self.overall_score['note_count'] > 0 else 0
        avg_velocity = self.overall_score['velocity'] / self.overall_score['count'] if self.overall_score['count'] > 0 else 0
        avg_timing = self.overall_score['timing'] / self.overall_score['count'] if self.overall_score['count'] > 0 else 0
        avg_duration = self.overall_score.get('duration', 0) / self.overall_score['count'] if self.overall_score['count'] > 0 else 0
        
        # Calculate overall average including duration
        overall_avg = (avg_pitch + avg_velocity + avg_timing + avg_duration) / 4
        sentiment_avg = (avg_velocity + avg_timing + avg_duration) / 3

        # Initialize report string
        #report = f"Overall Performance Score: {overall_avg:.2f}/100\n\n"
        report = f"Note Accuracy: {avg_pitch:.2f} %\n\n"
        report += f"Detail Score: {sentiment_avg:.2f} / 100\n"
        report += f" : Velocity Control: {avg_velocity:.2f} / 100\n"
        report += f" : Timing Precision: {avg_timing:.2f} / 100\n"
        report += f" : Duration Accuracy: {avg_duration:.2f} / 100\n\n"
        
        # Add duration statistics
        duration_stats = self.get_duration_statistics()
        if duration_stats:
            report += f"Velocity, Timing, Duration notes Analyzed: {duration_stats['total_notes_analyzed']}/{duration_stats['total_notes_played']}\n\n"

        # Add performance feedback
        if overall_avg >= 90:
            report += "Excellent performance! Your playing was highly accurate with consistent note durations."
        elif overall_avg >= 80:
            report += "Great job! Your performance was very good with minor areas for improvement in note durations."
        elif overall_avg >= 70:
            report += "Good effort! Focus on maintaining consistent note lengths to match the reference."
        else:
            report += "Keep practicing! Pay attention to the duration of each note and try to match the reference timing."

        self.performance_report = report

    def generate_overall_comment(self):
        # Generate the response
        response_info, response = get_response(f"Reference:{get_midi_file(self.reference_path)}\n Student:{self.student_midi_file}")
        self.overall_comment = response_info.choices[0].message.content
        
        # Split the comment into words and group by every 10 words
        words = self.overall_comment.split()
        formatted_comment = '\n'.join([' '.join(words[i:i+10]) for i in range(0, len(words), 10)])

        # Add formatted comment to performance report
        self.performance_report += f"\n\n{formatted_comment}"
        
        # Print the formatted comment
        print(formatted_comment)

        
        
    
    def draw_legends(self):
        legend_height = 30
        
        legend_width = 180
        start_y = 20
        start_x = self.screen_width - legend_width - 10
        circle_radius = 8  # 圓形的半徑
        padding = 8  # 框框內的間距
        spacing = 4  # 圖例之間的間距

        # 計算框框的高度
        total_height = len(self.legends) * legend_height + (len(self.legends) - 1) * spacing + padding * 2

        # 畫出框框背景
        pygame.draw.rect(
            self.screen, 
            (220, 220, 220),  # 淺灰色背景
            pygame.Rect(start_x - padding, start_y - padding, legend_width + padding * 2, total_height),
            border_radius=10  # 圓角
        )

        for i, (label, color) in enumerate(self.legends):
            y = start_y + i * (legend_height + spacing)
            
            # 畫圓形
            circle_center = (start_x + circle_radius, y + circle_radius)  # 圓心位置
            pygame.draw.circle(self.screen, color, circle_center, circle_radius)
            
            # 渲染並繪製文字
            text = self.legend_font.render(label, True, (0, 0, 0))
            self.screen.blit(text, (start_x + circle_radius * 2 + 10, y + 2.5))  # 文字位置稍微往右移


    def draw_visualization(self):
        # Draw reference notes
        self.y_intercept = self.screen_height/2
        self.x_intercept = self.screen_width/10
        self.ref_color = (200, 200, 200)
        # Calculate scaling factor based on total_duration
        self.scaling_factor = (self.screen_width - self.x_intercept * 2) / self.total_duration

        for pitch, start, end, velocity in self.ref_notes:
            y = self.y_intercept - (pitch - 50) * 10 
            x = self.x_intercept + start * self.scaling_factor
            width = (end - start) * self.scaling_factor
            pygame.draw.rect(self.screen, self.ref_color, (x, y, width, 8))
            text = self.font_note.render(f'P{pitch} V{velocity}', True, (0, 0, 0))
            self.screen.blit(text, (x, y - 20))

        # Draw student notes
        for note in self.note_list:
            pitch, start_time, end_time, correct, color, velocity = note
            y = self.y_intercept - (pitch - 50) * 10 
            x = self.x_intercept + start_time * self.scaling_factor
            width = (end_time - start_time) * self.scaling_factor
            pygame.draw.rect(self.screen, color, (x, y, width, 8))
            text = self.font_note.render(f'P{pitch} V{velocity}', True, (0, 0, 0))
            self.screen.blit(text, (x, y + 10))

            
        # Draw bar scores
        for bar_number, scores in self.bar_scores.items():
            avg_score = sum(scores[aspect] for aspect in ['pitch', 'velocity', 'timing']) / (3 * scores['count']) if scores['count'] > 0 else 0
            x = self.x_intercept + bar_number * (240 / self.BPM) * 100
            y = self.screen_height + 100
            text = self.font_note.render(f'Bar {bar_number + 1}: {avg_score:.2f}', True, (0, 0, 0))
            self.screen.blit(text, (x, y))

        # Draw reference control (only pedal for now)
        pedal_pressed_time = 0
        for number, value, time in self.ref_control:
            if number == 64:
                if value == 0: #release (draw)
                    y1 = self.y_intercept + 70
                    y2 = self.y_intercept + 80
                    x1 = self.x_intercept + pedal_pressed_time * self.scaling_factor
                    x2 = self.x_intercept + time * self.scaling_factor
                    points = [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]
                    pygame.draw.lines(self.screen, self.ref_color, False, points, width = 3) #width default 1
                    
                elif value > 0: #pressed
                    pedal_pressed_time = time
            else:
                continue

        # Draw student control (only pedal for now)
        for pedal in self.pedal_list:
            pedal_start_time, pedal_end_time, correctness, color = pedal
            y1 = self.y_intercept + 90
            y2 = self.y_intercept + 100
            x1 = self.x_intercept + pedal_start_time * self.scaling_factor
            x2 = self.x_intercept + pedal_end_time * self.scaling_factor
            points = [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]
            pygame.draw.lines(self.screen, color, False, points, width=3)
            

    def toggle_recording(self):
        if self.is_recording.is_set():
            self.stop_recording()
        else:
            self.start_recording()
            
    def show_countdown(self, dots_left):
        # Define position, size of dots, and colors
        outer_radius = 10
        spacing = 30  # Space between dots
        start_x = self.screen_width / 2 - 2.5 * spacing
        y = self.screen_height / 10  # Adjust y-coordinate as needed

        # Clear the entire area before drawing
        self.hide_countdown()

        # Draw each dot with a filled "vanishing" effect
        for i in range(4):  # Always draw the four outer circles
            x = start_x + i * (outer_radius * 2 + spacing)
            pygame.draw.circle(self.screen, (0, 0, 0), (x, y), outer_radius)  # Black outer circle
            
            # If the dot should remain partially filled, draw the inner part in the background color
            if i >= dots_left:
                pygame.draw.circle(self.screen, (190, 190, 190), (x, y), outer_radius - 3)  # Vanished middle part

        pygame.display.flip()  # Update display to show the dots

    def hide_countdown(self):
        # Clear the area where dots are displayed
        outer_radius = 10
        spacing = 30
        start_x = self.screen_width / 2 - 2.5 * spacing
        y = self.screen_height / 10  # Same y-coordinate as used in show_countdown

        # Calculate total width of dots area
        total_width = (outer_radius * 2 + spacing) * 4 - spacing  # 4 dots and spaces between them

        # Fill with background color to clear
        self.screen.fill((190, 190, 190), (start_x - outer_radius, y - outer_radius, total_width, outer_radius * 2))




    def start_recording(self):
        """Start recording with proper initialization"""
        self.note_list.clear()
        self.pedal_list.clear()
        self.student_control_pressed_time = -1
        self.student_notes.clear()
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
        self.start_metronome()
        
        # Start MIDI processing thread
        self.midi_thread = threading.Thread(target=self.process_midi_input)
        self.midi_thread.daemon = True
        self.midi_thread.start()
        
    def stop_recording(self):
        """Stop recording and save MIDI file"""
        self.is_recording.clear()
        self.stop_metronome()
        
        # Wait for threads to finish
        if self.midi_thread:
            self.midi_thread.join()
            self.midi_thread = None
            
        # Save the recorded MIDI file
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"performance_{timestamp}.mid"
        self.student_midi_file = self.save_recorded_midi(filename)
        
        # Generate performance report
        self.generate_performance_report()
        print(self.performance_report)

        self.generate_overall_comment()

    def draw_dynamic_line(self):
        if self.is_recording.is_set():
            current_time = time.time() - self.recording_start_timestamp
            line_x_position = self.x_intercept + current_time * self.scaling_factor
            pygame.draw.line(self.screen, (128, 128, 128), (line_x_position, 0), (line_x_position, self.screen_height), 2)
            
    def draw_report(self):
        # Draw a semi-transparent background
        s = pygame.Surface((self.screen_width, self.screen_height))
        s.set_alpha(80)  # Semi-transparent background
        s.fill((255, 255, 255))  # White background
        self.screen.blit(s, (0, 0))

        # Draw the performance report text
        report_lines = self.performance_report.split('\n')
        for i, line in enumerate(report_lines):
            text = self.font_report.render(line, True, (0, 0, 0))
            self.screen.blit(text, (20, self.screen_height - 400 + i * 20))

        # Draw the close button with hover effect
        close_button_x = (self.screen_width - 100) // 2
        close_button_y = self.screen_height - 100
        self.close_button_rect = pygame.Rect(close_button_x, close_button_y, 100, 40)

        mouse_pos = pygame.mouse.get_pos()

        # Change color if mouse is over the close button
        if self.close_button_rect.collidepoint(mouse_pos):
            button_color = (173, 216, 230)  # Light blue on hover
        else:
            button_color = (200, 200, 200)  # Gray as default

        pygame.draw.rect(self.screen, button_color, self.close_button_rect)  # Close button background
        close_text = self.font_title.render("Close", True, (0, 0, 0))  # Close button text
        self.screen.blit(close_text, self.close_button_rect.move(10, 10))

    def update_bpm(self, new_bpm):
        self.BPM = new_bpm
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
        self.overall_score = {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'note_count': 0}
        self.performance_report = ""
        self.bpm_text = ''  # Clear the BPM text input



    def run(self):
            running = True
            clock = pygame.time.Clock()
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if self.record_button_rect.collidepoint(event.pos):
                            self.toggle_recording()
                            if not self.is_recording.is_set():
                                self.showing_report = True
                        elif self.showing_report and self.close_button_rect.collidepoint(event.pos):
                            self.showing_report = False
                            # Reset scores and clear notes for a new session
                            self.bar_scores.clear()
                            self.overall_score = {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'note_count': 0}
                            self.note_list.clear()
                            self.pedal_list.clear()
                            self.student_control_pressed_time = -1
                        elif self.show_button_rect.collidepoint(event.pos):
                            self.showing_report = not self.showing_report
                        elif self.bpm_button_rect.collidepoint(event.pos):
                            self.bpm_input_active = True
                            self.bpm_text = ''
                    elif event.type == pygame.KEYDOWN:
                        if self.bpm_input_active:
                            if event.key == pygame.K_RETURN:
                                try:
                                    new_bpm = int(self.bpm_text)
                                    self.bpm_input_active = False
                                    self.update_bpm(new_bpm)
                                except ValueError:
                                    pass
                            elif event.key == pygame.K_BACKSPACE:
                                self.bpm_text = self.bpm_text[:-1]
                            else:
                                self.bpm_text += event.unicode

                self.screen.fill((190, 190, 190))
                
                # Draw UI elements with rounded iOS-style buttons
                mouse_pos = pygame.mouse.get_pos()

                # Change color if mouse is over the close button
                if self.close_button_rect.collidepoint(mouse_pos):
                    buttonn_color = (173, 216, 230)  # Light blue on hover
                else:
                    buttonn_color = (200, 200, 200)  # Gray as default

                show_text = "Show" if self.is_recording.is_set() else "UnShow"
                show_active = self.show_button_rect.collidepoint(mouse_pos)
                self.draw_button_with_shadow(self.screen, self.show_button_rect, show_text, self.font_title, active=show_active)

                
                record_text = "Stop" if self.is_recording.is_set() else "Start"
                record_active = self.record_button_rect.collidepoint(mouse_pos)
                self.draw_button_with_shadow(self.screen, self.record_button_rect, record_text, self.font_title, active=record_active)

                bpm_active = self.bpm_button_rect.collidepoint(mouse_pos)
                self.draw_button_with_shadow(self.screen, self.bpm_button_rect, "Set BPM", self.font_title, active=bpm_active)

                # Draw the current BPM label below the BPM button
                bpm_label_rect = self.bpm_button_rect.move(0, 50)
                bpm_label_text = self.font_title.render(f"BPM: {self.BPM}", True, (0, 0, 0))
                self.screen.blit(bpm_label_text, bpm_label_rect.move(10, 10))

                if self.bpm_input_active:
                    self.bpm_input_rect.topleft = (self.bpm_button_rect.right + 10, self.bpm_button_rect.top)
                    pygame.draw.rect(self.screen, (255, 255, 255), self.bpm_input_rect)
                    bpm_surface = self.font_title.render(self.bpm_text or '', True, (0, 0, 0))
                    self.screen.blit(bpm_surface, self.bpm_input_rect.move(10, 10))

                self.draw_legends()
                self.draw_visualization()
                self.draw_dynamic_line()

                if self.showing_report:
                    self.draw_report()

                pygame.display.flip()
                clock.tick(30)

            self.stop_recording()
            if self.midi_input:
                self.midi_input.close()
            pygame.quit()
            
if __name__ == "__main__":
    app = DynamicMusicSheet()
    app.run()