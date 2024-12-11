import pygame
import pygame.midi
import threading
import time
import matplotlib.pyplot as plt
import matplotlib.backends.backend_agg as agg
import matplotlib.patches as mpatches
import pretty_midi
from matplotlib.figure import Figure

# %matplotlib inline
plt.rcParams["figure.dpi"] = 100

class DynamicMusicSheet:
    def __init__(self):
        pygame.init()
        # Get the display screen dimensions
        screen_info = pygame.display.Info()
        self.screen_width, self.screen_height = screen_info.current_w, screen_info.current_h

        # Set up the screen to match the display's dimensions
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))

        pygame.display.set_caption("Dynamic Music Sheet - Real-time Visualization")
        
        # Initialize MIDI input
        pygame.midi.init()
        try:
            self.midi_input = pygame.midi.Input(pygame.midi.get_default_input_id())
        except pygame.midi.MidiException:
            print("No MIDI input device found!")
            self.midi_input = None
        
        # MIDI processing variables
        self.BPM = 96
        self.ticks_per_beat = 480
        self.ticks_per_second = (self.ticks_per_beat * self.BPM) / 60
        self.student_notes = {}
        self.note_list = []
        
        # Threading and timing
        self.midi_thread = None
        self.start_time = None
        self.is_recording = threading.Event()
        self.recording_duration = 10
        
        # Load reference MIDI
        self.reference_path = '0_t2.mid'  # Make sure this file exists
        self.ref_notes = self.load_reference_midi(self.reference_path)
        
        # Matplotlib setup
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(self.screen_width/100, self.screen_height/125))
        self.init_visualization()
        
        # UI elements
        self.font = pygame.font.Font(None, 36)
        self.setup_ui_elements()
    
    def load_reference_midi(self, reference_path):
        try:
            ref_midi = pretty_midi.PrettyMIDI(reference_path)
            ref_notes = [(note.pitch, note.start, note.end, note.velocity) 
                         for instrument in ref_midi.instruments 
                         for note in instrument.notes]
            return ref_notes  # Remove trimming for now
        except Exception as e:
            print(f"Error loading reference MIDI: {e}")
            return []
    
    def init_visualization(self):
        self.ax1.clear()
        self.ax2.clear()
        
        # Add legend first
        correct_patch = mpatches.Patch(color='lightgreen', label='Correct')
        extra_patch = mpatches.Patch(color='red', label='Incorrect')
        too_hard = mpatches.Patch(color='yellow', label='Too hard')
        too_light = mpatches.Patch(color='cyan', label='Too light')
        
        self.ax1.legend(handles=[correct_patch, extra_patch, too_hard, too_light], 
                        loc='upper right')
        self.ax2.legend(handles=[correct_patch, extra_patch, too_hard, too_light], 
                        loc='upper right')
        
        # Draw reference notes
        for pitch, start, end, velocity in self.ref_notes:
            self.ax1.barh(pitch, end - start, left=start, height=1, color='lightgreen')
            self.ax1.text(start + 0.1, pitch + 1, f'P{pitch}\nT{start:.2f}\nV{velocity}', 
                         va='bottom', fontsize=8, ha='left')
        
        max_time = max(end for _, _, end, _ in self.ref_notes) if self.ref_notes else 10
        
        for ax in [self.ax1, self.ax2]:
            ax.set_xlim(0, max_time)
            ax.set_ylim(50, 80)
        
        self.ax1.set_title("Reference MIDI")
        self.ax2.set_title("Student Performance")
        
        plt.tight_layout()
    
    def setup_ui_elements(self):
        self.record_button_rect = pygame.Rect(20, 20, 100, 40)
        self.canvas = agg.FigureCanvasAgg(self.fig)
    
    def process_midi_input(self):
        if not self.midi_input:
            return
        
        self.start_time = time.time()
        last_time = self.start_time
        
        while self.is_recording.is_set():
            if time.time() - self.start_time >= self.recording_duration:
                self.is_recording.clear()
                break
                
            if self.midi_input.poll():
                midi_events = self.midi_input.read(10)
                for event in midi_events:
                    status = event[0][0]
                    note_number = event[0][1]
                    velocity = event[0][2]
                    current_time = time.time()
                    
                    if status == 144 and velocity > 0:  # Note On
                        note_start_time = current_time - self.start_time
                        self.student_notes[note_number] = (note_start_time, velocity)
                    elif status == 128 or (status == 144 and velocity == 0):  # Note Off
                        if note_number in self.student_notes:
                            note_start_time, start_velocity = self.student_notes.pop(note_number)
                            note_end_time = current_time - self.start_time
                            self.compare_and_visualize((note_number, note_start_time, 
                                                       note_end_time, start_velocity))
    
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
                color = 'yellow'  # Too hard
            else:
                color = 'cyan'    # Too light
            
            self.note_list.append((pitch, start_time, end_time, True, color, velocity))
        else:
            self.note_list.append((pitch, start_time, end_time, False, 'red', velocity))
    
    def update_visualization(self):
        self.ax2.clear()
        self.ax2.set_title("Student Performance")
        
        # Add legend first
        correct_patch = mpatches.Patch(color='lightgreen', label='Correct')
        extra_patch = mpatches.Patch(color='red', label='Incorrect')
        too_hard = mpatches.Patch(color='yellow', label='Too hard')
        too_light = mpatches.Patch(color='cyan', label='Too light')
        self.ax2.legend(handles=[correct_patch, extra_patch, too_hard, too_light], 
                        loc='upper right')
        
        max_time = max(end for _, _, end, _ in self.ref_notes) if self.ref_notes else 10
        self.ax2.set_xlim(0, max_time)
        self.ax2.set_ylim(50, 80)
        
        for note in self.note_list:
            pitch, start_time, end_time, correct, color, velocity = note
            duration = end_time - start_time
            self.ax2.barh(pitch, duration, left=start_time, height=1, color=color, alpha=0.7)
            self.ax2.text(start_time + 0.1, pitch + 1, 
                         f'P{pitch}\nT{start_time:.2f}\nV{velocity}', 
                         va='bottom', fontsize=8, ha='left')
        
        self.canvas.draw()
        renderer = self.canvas.get_renderer()
        raw_data = renderer.tostring_rgb()
        size = self.canvas.get_width_height()
        
        return pygame.image.fromstring(raw_data, size, "RGB")
    
    def toggle_recording(self):
        if self.is_recording.is_set():
            self.is_recording.clear()
            if self.midi_thread:
                self.midi_thread.join()
                self.midi_thread = None
        else:
            self.note_list.clear()
            self.student_notes.clear()
            self.is_recording.set()
            self.recording_start_time = pygame.time.get_ticks()
            self.midi_thread = threading.Thread(target=self.process_midi_input)
            self.midi_thread.daemon = True
            self.midi_thread.start()
    
    def draw_dynamic_line(self):
        if self.is_recording.is_set():
            # Get the current time or another parameter to determine the vertical line's x-position
            current_time = pygame.time.get_ticks() - self.recording_start_time  # Time in milliseconds
            line_x_position = (current_time // 7.5) % self.screen_width  # Modulo to wrap around the screen

            # Draw the vertical line
            pygame.draw.line(self.screen, (128,128,128), (line_x_position, 0), (line_x_position, self.screen_height), 2)


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
            
            self.screen.fill((255, 255, 255))
            
            # Draw UI elements
            button_color = (255, 0, 0) if self.is_recording.is_set() else (0, 255, 0)
            pygame.draw.rect(self.screen, button_color, self.record_button_rect)
            text = self.font.render("Stop" if self.is_recording.is_set() else "Start", 
                                   True, (0, 0, 0))
            self.screen.blit(text, self.record_button_rect.move(10, 10))
            
            # Update and draw matplotlib visualization
            plot_surface = self.update_visualization()
            self.screen.blit(plot_surface, (0, 100))
            
            # Draw the dynamic vertical line
            self.draw_dynamic_line()

            pygame.display.flip()
            clock.tick(30)
        
        self.is_recording.clear()
        if self.midi_thread:
            self.midi_thread.join()
        if self.midi_input:
            self.midi_input.close()
        pygame.quit()

if __name__ == "__main__":
    app = DynamicMusicSheet()
    app.run()