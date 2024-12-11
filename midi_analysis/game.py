import pygame
import pygame.midi
import threading
import time
import matplotlib.pyplot as plt
import matplotlib.backends.backend_agg as agg
import matplotlib.patches as mpatches
import pretty_midi
import numpy as np
from matplotlib.figure import Figure

class DynamicMusicSheet:
    def __init__(self):
        pygame.init()
        screen_info = pygame.display.Info()
        self.screen_width, self.screen_height = screen_info.current_w, screen_info.current_h
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Dynamic Music Sheet - Real-time Visualization")
        
        pygame.midi.init()
        try:
            self.midi_input = pygame.midi.Input(pygame.midi.get_default_input_id())
        except pygame.midi.MidiException:
            print("No MIDI input device found!")
            self.midi_input = None
        
        self.BPM = 125
        self.ticks_per_beat = 480
        self.ticks_per_second = (self.ticks_per_beat * self.BPM) / 60
        self.student_notes = {}
        self.note_list = []
        self.midi_thread = None
        self.start_time = None
        self.is_recording = threading.Event()
        
        self.reference_path = '0_t2.mid'
        self.ref_notes = self.load_reference_midi(self.reference_path)
        
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(self.screen_width / 100, self.screen_height / 125))
        self.init_visualization()

        self.font = pygame.font.Font(None, 36)
        self.setup_ui_elements()
        
        self.beat_sound = self.generate_beat_sound()
        self.is_playing_metronome = False
        self.metronome_thread = None
        self.bpm_text = ''

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

    def init_visualization(self):
        self.ax1.clear()
        self.ax2.clear()
        correct_patch = mpatches.Patch(color='lightgreen', label='Correct')
        extra_patch = mpatches.Patch(color='red', label='Incorrect')
        too_hard = mpatches.Patch(color='yellow', label='Too hard')
        too_light = mpatches.Patch(color='cyan', label='Too light')
        self.ax1.legend(handles=[correct_patch, extra_patch, too_hard, too_light], loc='upper right')
        self.ax2.legend(handles=[correct_patch, extra_patch, too_hard, too_light], loc='upper right')
        
        for pitch, start, end, velocity in self.ref_notes:
            self.ax1.barh(pitch, end - start, left=start, height=1, color='lightgreen')
            self.ax1.text(start + 0.1, pitch + 1, f'P{pitch}\nT{start:.2f}\nV{velocity}', va='bottom', fontsize=8, ha='left')
        
        max_time = max(end for _, _, end, _ in self.ref_notes) if self.ref_notes else 10
        for ax in [self.ax1, self.ax2]:
            ax.set_xlim(0, max_time)
            ax.set_ylim(50, 80)
        self.ax1.set_title("Reference MIDI")
        self.ax2.set_title("Student Performance")
        plt.tight_layout()

    def setup_ui_elements(self):
        self.record_button_rect = pygame.Rect(20, 20, 100, 40)
        self.bpm_input_rect = pygame.Rect(140, 20, 100, 40)
        self.canvas = agg.FigureCanvasAgg(self.fig)

    def generate_beat_sound(self, frequency=450, duration=0.1, volume=0.5):
        sample_rate = 44100
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, False)
        
        # Generate sine wave
        sine_wave = np.sin(2 * np.pi * frequency * t)
        
        # Create fade-in and fade-out envelopes
        fade_in = np.linspace(0, 1, int(sample_rate * 0.05))  # 5% fade-in
        fade_out = np.linspace(1, 0, int(sample_rate * 0.05))  # 5% fade-out
        envelope = np.ones_like(sine_wave)
        envelope[:len(fade_in)] = fade_in
        envelope[-len(fade_out):] = fade_out
        
        # Apply the envelope to the sine wave for smooth transitions
        smooth_wave = sine_wave * envelope
        
        # Create stereo sound
        stereo_wave = np.column_stack((smooth_wave, smooth_wave)) * volume * 32767
        stereo_wave = stereo_wave.astype(np.int16)
        
        return pygame.sndarray.make_sound(stereo_wave)


    def play_metronome(self):
        beat_interval = 60 / self.BPM
        while self.is_playing_metronome:
            self.beat_sound.play()
            time.sleep(beat_interval)  # Sleep for the duration of one beat

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
                            self.compare_and_visualize((note_number, note_start_time, note_end_time, start_velocity))

    def compare_and_visualize(self, student_note, tolerance=0.1, velocity_tolerance=20):
        pitch, start_time, end_time, velocity = student_note
        closest_ref_note = None
        closest_time_diff = float('inf')
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
                color = 'lightgreen'
            elif vel_diff < -velocity_tolerance:
                color = 'yellow'
            else:
                color = 'cyan'
            self.note_list.append((pitch, start_time, end_time, True, color, velocity))
        else:
            self.note_list.append((pitch, start_time, end_time, False, 'red', velocity))

    def update_visualization(self):
        self.ax2.clear()
        self.ax2.set_title("Student Performance")
        correct_patch = mpatches.Patch(color='lightgreen', label='Correct')
        extra_patch = mpatches.Patch(color='red', label='Incorrect')
        too_hard = mpatches.Patch(color='yellow', label='Too hard')
        too_light = mpatches.Patch(color='cyan', label='Too light')
        self.ax2.legend(handles=[correct_patch, extra_patch, too_hard, too_light], loc='upper right')
        max_time = max(end for _, _, end, _ in self.ref_notes) if self.ref_notes else 10
        self.ax2.set_xlim(0, max_time)
        self.ax2.set_ylim(50, 80)
        for note in self.note_list:
            pitch, start_time, end_time, correct, color, velocity = note
            duration = end_time - start_time
            self.ax2.barh(pitch, duration, left=start_time, height=1, color=color, alpha=0.7)
            self.ax2.text(start_time + 0.1, pitch + 1, f'P{pitch}\nT{start_time:.2f}\nV{velocity}', va='bottom', fontsize=8, ha='left')
        self.canvas.draw()
        renderer = self.canvas.get_renderer()
        raw_data = renderer.tostring_rgb()
        size = self.canvas.get_width_height()
        return pygame.image.fromstring(raw_data, size, "RGB")

    def toggle_recording(self):
        if self.is_recording.is_set():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        self.note_list.clear()
        self.student_notes.clear()
        self.is_recording.set()
        for _ in range(4):
            self.beat_sound.play()
            time.sleep(60 / self.BPM)
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

    def draw_dynamic_line(self):
        if self.is_recording.is_set():
            current_time = pygame.time.get_ticks() - self.recording_start_time
            beats_passed = (current_time / 1000) * (self.BPM / 60)
            # line_x_position = (beats_passed % 8) * (self.screen_width / 8)
            line_x_position = (current_time // 10) % self.screen_width  # Modulo to wrap around the screen
            pygame.draw.line(self.screen, (128, 128, 128), (line_x_position, 0), (line_x_position, self.screen_height), 2)

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
                    elif self.bpm_input_rect.collidepoint(event.pos):
                        self.bpm_text = ''
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
            self.screen.fill((255, 255, 255))
            button_color = (255, 0, 0) if self.is_recording.is_set() else (0, 255, 0)
            pygame.draw.rect(self.screen, button_color, self.record_button_rect)
            text = self.font.render("Stop" if self.is_recording.is_set() else "Start", True, (0, 0, 0))
            self.screen.blit(text, self.record_button_rect.move(10, 10))
            pygame.draw.rect(self.screen, (200, 200, 200), self.bpm_input_rect)
            bpm_surface = self.font.render(self.bpm_text or str(self.BPM), True, (0, 0, 0))
            self.screen.blit(bpm_surface, self.bpm_input_rect.move(10, 10))
            plot_surface = self.update_visualization()
            self.screen.blit(plot_surface, (0, 100))
            #self.draw_dynamic_line()
            pygame.display.flip()
            clock.tick(30)
        self.stop_recording()
        if self.midi_input:
            self.midi_input.close()
        pygame.quit()

if __name__ == "__main__":
    app = DynamicMusicSheet()
    app.run()
