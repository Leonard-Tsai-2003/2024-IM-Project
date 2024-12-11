import pygame
import pygame.midi
import threading
import time
import pretty_midi
import numpy as np
import mido
from collections import defaultdict
from midiutil import MIDIFile
import os

class DynamicMusicSheet:
    def __init__(self):
        # Screen Info Initialization
        pygame.init()
        screen_info = pygame.display.Info()
        self.screen_width, self.screen_height = screen_info.current_w, screen_info.current_h
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Dynamic Music Sheet - Real-time Visualization")
        
        # Tolerance Param Initialization
        self.time_tolerance = 0.13
        self.velocity_tolerance = 20

        # Add countdown dots initialization
        self.countdown_dots = []
        self.countdown_start_time = None

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
        
        # Midi Details Initialization
        self.BPM = 108
        self.ticks_per_beat = 480
        self.ticks_per_second = (self.ticks_per_beat * self.BPM) / 60
        self.student_notes = {}
        self.note_list = []
        self.midi_thread = None
        self.start_time = None
        self.is_recording = threading.Event()
        
        # Reference Midi File Initialization
        self.reference_path = '2_t2.mid'

        self.ref_notes = self.load_reference_midi(self.reference_path)
        self.list_midi_controllers(self.reference_path)
        self.list_all_midi_details(self.reference_path)

        # Fonts Initialization
        self.font_title = pygame.font.Font(None, 36)
        self.font_note = pygame.font.Font(None, 15)
        self.font_report = pygame.font.Font(None, 25)
        
        self.setup_ui_elements()
        
        # Metronome Initialization
        self.metronome_duration = 0.1
        self.beat_sound = self.generate_beat_sound(duration=self.metronome_duration)
        self.is_playing_metronome = False
        self.metronome_thread = None
        self.bpm_text = ''

        # Notes Colors Initialization
        self.colors = {
            'correct': (144, 238, 144),  # light green
            'incorrect': (255, 0, 0),    # red
            'too_hard': (255, 255, 0),   # yellow
            'too_light': (0, 255, 255)   # cyan
        }

        # Notes Legend Initialization
        self.legend_font = pygame.font.Font(None, 24)
        self.legends = [
            ("Correct", self.colors['correct']),
            ("Incorrect", self.colors['incorrect']),
            ("Too hard", self.colors['too_hard']),
            ("Too light", self.colors['too_light']),
            (f"Time tolerance: {self.time_tolerance:.2f}s", (150, 150, 150)),
            (f"Velocity tolerance: {self.velocity_tolerance}", (150, 150, 150))
        ]


    def load_reference_midi(self, reference_path):
        try:
            ref_midi = pretty_midi.PrettyMIDI(reference_path)
            ref_notes = [(note.pitch, note.start, note.end, note.velocity) for instrument in ref_midi.instruments for note in instrument.notes]
            first_note_start = min(note[1] for note in ref_notes)
            adjusted_notes = [(pitch, start - first_note_start, end - first_note_start, velocity) for pitch, start, end, velocity in ref_notes]
            return adjusted_notes
        except Exception as e:
            print(f"Error loading reference MIDI: {e}")
            return []
        
        
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
        self.bpm_input_rect = pygame.Rect(140, 20, 100, 40)
        self.close_button_rect = pygame.Rect(self.screen_width - 60, self.screen_height - 60, 100, 40)

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
                    if status == 144 and velocity > 0:
                        note_start_time = current_time - self.start_time
                        self.student_notes[note_number] = (note_start_time, velocity)
                    elif status == 128 or (status == 144 and velocity == 0):
                        if note_number in self.student_notes:
                            note_start_time, start_velocity = self.student_notes.pop(note_number)
                            note_end_time = current_time - self.start_time
                            self.compare_and_visualize((note_number, note_start_time, note_end_time, start_velocity), self.time_tolerance, self.velocity_tolerance)


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
        
        return {
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
        report += f"Detail Score: {sentiment_avg:.2f}/100\n"
        report += f" - Velocity Control: {avg_velocity:.2f}/100\n"
        report += f" - Timing Precision: {avg_timing:.2f}/100\n"
        report += f" - Duration Accuracy: {avg_duration:.2f}/100\n\n"
        
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
        
    def draw_legends(self):
        legend_height = 30
        legend_width = 200
        start_y = 10
        start_x = self.screen_width - legend_width - 10

        for i, (label, color) in enumerate(self.legends):
            y = start_y + i * (legend_height + 5)
            
            # Draw color box
            pygame.draw.rect(self.screen, color, (start_x, y, 20, 20))
            
            # Render and draw text
            text = self.legend_font.render(label, True, (0, 0, 0))
            self.screen.blit(text, (start_x + 30, y))

    def draw_visualization(self):
        # Draw reference notes
        self.y_intercept = self.screen_height/2
        self.x_intercept = self.screen_width/10

        for pitch, start, end, velocity in self.ref_notes:
            y = self.y_intercept - (pitch - 50) * 10 
            x = self.x_intercept + start * 100
            width = (end - start) * 100
            pygame.draw.rect(self.screen, (200, 200, 200), (x, y, width, 8))
            text = self.font_note.render(f'P{pitch} V{velocity}', True, (0, 0, 0))
            self.screen.blit(text, (x, y - 20))

        # Draw student notes
        for note in self.note_list:
            pitch, start_time, end_time, correct, color, velocity = note
            y = self.y_intercept - (pitch - 50) * 10 
            x = self.x_intercept + start_time * 100
            width = (end_time - start_time) * 100
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
            

    def toggle_recording(self):
        if self.is_recording.is_set():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """
        Modified start_recording to improve initial metronome timing
        """
        self.note_list.clear()
        self.student_notes.clear()
        self.is_recording.set()
        
        # Play countdown beats with precise timing
        countdown_start = time.time()
        beat_interval = 60.0 / self.BPM
        
        for i in range(5):
            while time.time() < countdown_start + (i * beat_interval):
                time.sleep(0.001)
            self.beat_sound.play()
        
        # Start the actual recording after the countdown
        self.recording_start_time = pygame.time.get_ticks()
        self.start_metronome()
        self.midi_thread = threading.Thread(target=self.process_midi_input)
        self.midi_thread.daemon = True
        self.midi_thread.start()

    def stop_recording(self):
        self.is_recording.clear()
        self.stop_metronome()
        if self.midi_thread:
            self.midi_thread.join()
            self.midi_thread = None
        self.generate_performance_report()
        print(self.performance_report)  # Print the report to console

    def draw_dynamic_line(self):
        if self.is_recording.is_set():
            current_time = pygame.time.get_ticks() - self.recording_start_time
            line_x_position = (self.x_intercept + 1.3 * current_time // (self.screen_width/self.BPM)) % self.screen_width
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

        # Draw the close button clearly
        close_button_x = (self.screen_width - 100) // 2
        close_button_y = self.screen_height - 100
        self.close_button_rect = pygame.Rect(close_button_x, close_button_y, 100, 40)

        pygame.draw.rect(self.screen, (200, 200, 200), self.close_button_rect)  # Close button background
        close_text = self.font_title.render("Close", True, (0, 0, 0))  # Close button text
        self.screen.blit(close_text, self.close_button_rect.move(10, 10))




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
                        self.overall_score = {'pitch': 0, 'velocity': 0, 'timing': 0, 'count': 0, 'note_count' : 0}
                        self.note_list.clear()
                elif event.type == pygame.KEYDOWN:
                    if self.bpm_input_rect.collidepoint(pygame.mouse.get_pos()):
                        if event.key == pygame.K_RETURN:
                            try:
                                self.BPM = int(self.bpm_text)
                                self.bpm_text = ''
                            except ValueError:
                                pass
                        elif event.key == pygame.K_BACKSPACE:
                            self.bpm_text = self.bpm_text[:-1]
                        else:
                            self.bpm_text += event.unicode

            self.screen.fill((180, 180, 180))
            
            # 在繪製報告之前新增倒數點的繪製
            # Draw countdown dots if in countdown phase
            if self.countdown_start_time is not None and not self.is_recording.is_set():
                self.draw_countdown_dots()

            # Draw UI elements
            button_color = (255, 0, 0) if self.is_recording.is_set() else (0, 255, 0)
            pygame.draw.rect(self.screen, button_color, self.record_button_rect)
            text = self.font_title.render("Stop" if self.is_recording.is_set() else "Start", True, (0, 0, 0))
            self.screen.blit(text, self.record_button_rect.move(10, 10))
            
            pygame.draw.rect(self.screen, (200, 200, 200), self.bpm_input_rect)
            bpm_surface = self.font_title.render(self.bpm_text or str(self.BPM), True, (0, 0, 0))
            self.screen.blit(bpm_surface, self.bpm_input_rect.move(10, 10))

            self.draw_legends()

            # Draw visualization
            self.draw_visualization()
            self.draw_dynamic_line()

            # If we're showing the report, draw it and the close button
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
