import os
import shutil # it's in standard library, no need to pip install
import pretty_midi
from emopia.emopia_parts import *
import numpy as np
import matplotlib.pyplot as plt
import time
plt.rcParams["figure.dpi"] = 400
from copy import deepcopy
import mido
import math
from collections import defaultdict

def split_midi_by_bars(input_file, output_dir=None):
    # Load the MIDI file
    if type(input_file) == str:
        midi_data = pretty_midi.PrettyMIDI(input_file)
    else:
        midi_data = input_file
    
    if output_dir != None:
        # Create the output directory if it doesn't exist
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)
    
    # Get the time signature to determine bar length
    if midi_data.time_signature_changes:
        time_sig = midi_data.time_signature_changes[0]
        beats_per_bar = time_sig.numerator
    else:
        # Default to 4/4 if no time signature is found
        beats_per_bar = 4

    # Get the original tempo(s)
    tempo_times, tempos = midi_data.get_tempo_changes()
    original_tempo = tempos[0]  # Assuming a single, constant tempo
    print(f"Original Tempo: {original_tempo} BPM")
    bar_duration = 4 * 60 / original_tempo

    adjusted_notes = []
    for instrument in midi_data.instruments:
         for note in instrument.notes:
            # Scale the start and end times
            start = note.start * 1 # no desired bpm, therefore tempo ratio = 1
            end = note.end * 1 # for more details, check load_reference_midi oin game_simple.py
            adjusted_notes.append((note.pitch, start, end, note.velocity))
            
    first_note_start = min(note[1] for note in adjusted_notes)

    # Iterate through each bar
    bar_start = first_note_start # start time of the bar
    bar_number = 1

    bar_inference_values = []
    while bar_start < midi_data.get_end_time():
        # Create a new PrettyMIDI object for each bar
        bar_midi = pretty_midi.PrettyMIDI()

        # Copy instruments and slice each instrument's notes by time
        for instrument in midi_data.instruments:
            new_instrument = pretty_midi.Instrument(program=instrument.program, is_drum=instrument.is_drum)
            for note in instrument.notes:
                # Check if the note is within the current bar
                if bar_start <= note.start < bar_start + bar_duration:
                    # Shift note timing to start from 0
                    shifted_note = pretty_midi.Note(
                        velocity=note.velocity,
                        pitch=note.pitch,
                        start=note.start - bar_start,
                        end=note.end - bar_start
                    )
                    new_instrument.notes.append(shifted_note)
            # Add the instrument to the new bar MIDI
            bar_midi.instruments.append(new_instrument)

        if output_dir != None:
            # Save each bar as a separate MIDI file in the subdirectory
            output_path = os.path.join(output_dir, f"bar_{bar_number}.mid")
            bar_midi.write(output_path)
            print(f"Saved bar {bar_number} to {output_path}")
        else:
            if len(bar_midi.instruments[0].notes) == 0:
                pred_value = np.zeros(4)
            else:
                pred_label, pred_value = get_ar_vl_inference(bar_midi)
            bar_inference_values.append(pred_value)
        
        # Move to the next bar
        bar_start += bar_duration
        bar_number += 1

    return bar_inference_values

def mido_to_pretty_midi(mido_obj):
    """
    Convert a mido.MidiFile object to a pretty_midi.PrettyMIDI object
    
    Args:
        mido_obj (mido.MidiFile): The mido MIDI file object to convert
        
    Returns:
        pretty_midi.PrettyMIDI: The converted PrettyMIDI object
    """
    # Create a new PrettyMIDI object
    pm = pretty_midi.PrettyMIDI(resolution=mido_obj.ticks_per_beat)
    
    # Initialize variables for timing conversion
    current_time = 0
    current_tempo = 500000  # Default tempo (120 BPM in microseconds per beat)
    tempo_changes = []  # Store tempo changes as (time, tempo) pairs
    
    # Dictionary to store active notes: (channel, note) -> (start_time, velocity)
    active_notes = {}
    
    # Keep track of instruments for each channel
    channel_programs = defaultdict(lambda: 0)  # Default to program 0 (piano)
    channel_is_drum = defaultdict(lambda: False)  # Default to not drum
    
    def tick_to_second(tick):
        """Convert absolute tick to absolute second based on tempo"""
        return tick * current_tempo / (mido_obj.ticks_per_beat * 1000000)
    
    # Create a program map for all channels
    for track in mido_obj.tracks:
        absolute_time = 0
        for msg in track:
            absolute_time += msg.time
            
            if msg.type == 'program_change':
                channel_programs[msg.channel] = msg.program
                
            elif msg.type == 'set_tempo':
                current_tempo = msg.tempo
                print("Student BPM:", current_tempo)
                tempo_changes.append((absolute_time, msg.tempo))

    
    pm = pretty_midi.PrettyMIDI(resolution=mido_obj.ticks_per_beat, initial_tempo=60000000 / current_tempo)
    # Create instruments for each channel that has notes
    instruments = {}
    
    # Process all tracks
    for track in mido_obj.tracks:
        absolute_time = 0
        
        for msg in track:
            absolute_time += msg.time
            current_time = tick_to_second(absolute_time)
            
            if msg.type == 'note_on' and msg.velocity > 0:
                # Note onset
                active_notes[(msg.channel, msg.note)] = (current_time, msg.velocity)
                
                # Create instrument if it doesn't exist
                if msg.channel not in instruments:
                    program = channel_programs[msg.channel]
                    is_drum = (msg.channel == 9)  # Channel 10 (0-based 9) is reserved for drums
                    instrument = pretty_midi.Instrument(
                        program=program,
                        is_drum=is_drum,
                        name=f'Channel {msg.channel}'
                    )
                    instruments[msg.channel] = instrument
                    pm.instruments.append(instrument)
                
            elif msg.type in ['note_off', 'note_on'] and (msg.channel, msg.note) in active_notes:
                # Note offset (note_off or note_on with velocity 0)
                start_time, velocity = active_notes.pop((msg.channel, msg.note))
                
                # Create the note
                note = pretty_midi.Note(
                    velocity=velocity,
                    pitch=msg.note,
                    start=start_time,
                    end=current_time
                )
                
                # Add note to the appropriate instrument
                if msg.channel in instruments:
                    instruments[msg.channel].notes.append(note)
            
            elif msg.type == 'time_signature':
                pm.time_signature_changes.append(pretty_midi.TimeSignature(
                    numerator=msg.numerator,
                    denominator=msg.denominator,
                    time=current_time
                ))
        

    # Sort notes in each instrument
    for instrument in pm.instruments:
        instrument.notes.sort(key=lambda x: x.start)
    
    return pm


def draw_ar_vl_path(reference, student, output_path=None):
    def transform_to_arousal_valence_softmax(quadrant_scores):
        """
        Transforms a 4-dimensional quadrant score into a 2-dimensional (valence, arousal) point.
        """
        ## Step 1: softmax
        softmax_s = np.exp(quadrant_scores) / np.exp(quadrant_scores).sum()

        ## Step 2: radius
        r = softmax_s.max()

        ## Step 3: theta
        quadrant_angle_proxy = np.array([np.pi/4, 3*np.pi/4, 5*np.pi/4, 7*np.pi/4])
        y_proxy = softmax_s * np.sin(quadrant_angle_proxy)
        x_proxy = softmax_s * np.cos(quadrant_angle_proxy)
        theta = np.arctan2(y_proxy.sum(), x_proxy.sum()) + 2 * np.pi

        ## Step 4: All zeros exception
        if np.sum(quadrant_scores) == 0:
            r = 0
            theta = 0
        return r, theta
    def transform_to_arousal_valence_centroid(quadrant_scores):
        """
        Transforms a 4-dimensional quadrant score into a 2-dimensional (valence, arousal) point.
        """
        # Convert polar to Cartesian for calculations
        def polar_to_cartesian(r, theta):
            return r * math.cos(theta), r * math.sin(theta)

        def cartesian_to_polar(x, y):
            return math.sqrt(x**2 + y**2), math.atan2(y, x)

        def compute_intersections(scores):
            # Transform scores s_i into r_i
            r = np.array([s + 8 for s in scores])
            
            # Define theta_i
            theta = [(2 * i + 1) * math.pi / 4 for i in range(4)]

            # Find the max point
            max_index = r.argmax()
            max_point = (r[max_index], theta[max_index])

            # Define prev_index and next_index
            prev_index = (max_index - 1) % 4
            next_index = (max_index + 1) % 4

            prev_point = (r[prev_index], theta[prev_index])
            next_point = (r[next_index], theta[next_index])

            max_cart = polar_to_cartesian(*max_point)
            prev_cart = polar_to_cartesian(*prev_point)
            next_cart = polar_to_cartesian(*next_point)

            # Calculate lines and intersections
            if max_index % 2 == 1:  # Case 1: max_index is odd
                # Line 1: prev -> max (intersects y-axis)
                slope1 = (max_cart[1] - prev_cart[1]) / (max_cart[0] - prev_cart[0])
                y_intercept = max_cart[1] - slope1 * max_cart[0]
                intersect1_cart = (0, y_intercept)

                # Line 2: max -> next (intersects x-axis)
                slope2 = (next_cart[1] - max_cart[1]) / (next_cart[0] - max_cart[0])
                x_intercept = -max_cart[1] / slope2 + max_cart[0]
                intersect2_cart = (x_intercept, 0)
            else:  # Case 2: max_index is even
                # Line 1: prev -> max (intersects x-axis)
                slope1 = (max_cart[1] - prev_cart[1]) / (max_cart[0] - prev_cart[0])
                x_intercept = -prev_cart[1] / slope1 + prev_cart[0]
                intersect1_cart = (x_intercept, 0)

                # Line 2: max -> next (intersects y-axis)
                slope2 = (next_cart[1] - max_cart[1]) / (next_cart[0] - max_cart[0])
                y_intercept = max_cart[1] - slope2 * max_cart[0]
                intersect2_cart = (0, y_intercept)

            # Convert intersections back to polar coordinates
            intersect1_polar = cartesian_to_polar(*intersect1_cart)
            intersect2_polar = cartesian_to_polar(*intersect2_cart)

            return max_point, intersect1_polar, intersect2_polar

        def calculate_centroid(polar_points):
            """Calculate the centroid of a quadrilateral defined by polar coordinates."""
            # Convert polar points to Cartesian coordinates
            cartesian_points = [polar_to_cartesian(r, theta) for r, theta in polar_points]
            
            # Calculate the average x and y
            x_centroid = sum([x for x, y in cartesian_points]) / 4
            y_centroid = sum([y for x, y in cartesian_points]) / 4
            
            # Convert centroid back to polar coordinates
            r_centroid, theta_centroid = cartesian_to_polar(x_centroid, y_centroid)
            print(r_centroid, theta_centroid)
            
            return r_centroid, theta_centroid
        
        max_point, intersection1, intersection2 = compute_intersections(quadrant_scores)
        r_centroid, theta_centroid = calculate_centroid([intersection1, max_point, intersection2, (0,0)])
        return r_centroid, theta_centroid

    # Plotting in polar coordinates
    plt.figure(figsize=(6, 6))
    ax = plt.subplot(projection='polar')

    def draw_polar_coordinates(inference_values, ax, color, label, mode):
        if mode == "softmax":
            arousal_valence_points = [transform_to_arousal_valence_softmax(np.array(scores)) for scores in inference_values]
            # Extract valence and arousal coordinates
            r, theta = zip(*arousal_valence_points)
        else:
            arousal_valence_points = [transform_to_arousal_valence_centroid(np.array(scores)) for scores in inference_values]
            # Extract valence and arousal coordinates
            r, theta = zip(*arousal_valence_points)
            r = np.array(r)
            r /= r.max()

        

        ax.scatter(theta, r, s=50, color=color, label=label, alpha=0.7)  # Set color and size for each point

        for i in range(1, len(theta)):
            ax.annotate(
                "",
                xy=(theta[i], r[i]), 
                xytext=(theta[i-1], r[i-1]),
                arrowprops=dict(facecolor=color, edgecolor=color, shrink=0.05, width=.25, headwidth=2),
                color=color
            )
        for i in range(len(theta)):
            ax.text(
                theta[i], r[i], 
                f'{i+1}',    # text to display
                color='white',
                fontsize=8, # optional: adjust font size
                ha='center', # horizontal alignment
                va='center'  # vertical alignment
            )


    draw_polar_coordinates(reference, ax, "grey", "Reference", "softmax")
    draw_polar_coordinates(student, ax, "blue", "Student", "softmax")

    # draw_polar_coordinates(reference, ax, "black", "Reference_centroid", "centroid")
    # draw_polar_coordinates(student, ax, "red", "Student_centroid", "centroid")


    ax.set_title("Polar Plot of Arousal-Valence Points Based on Inference Values", va='bottom')
    ax.tick_params(axis='y', labelsize=7)

    # Define axis and quadrant labels
    axis_labels = ["High Valence", "High Arousal", "Low Valence", "Low Arousal"]
    quadrant_labels = ["Excited, Happy (Q1)", "Angry, Tense (Q2)", "Depressed, Tired (Q3)", "Calm, Relaxed (Q4)"]

    # Define angles for axis labels and quadrant labels
    angles = [0, np.pi/2, np.pi, 3*np.pi/2]

    # Set axis labels
    ax.set_xticks(angles)
    ax.set_xticklabels(axis_labels)

    # Set quadrant labels
    for angle, label in zip(angles, quadrant_labels):
        ax.text(angle+np.pi/4, ax.get_ylim()[1] + 0.5, label, ha='center', va='center', fontsize=10, color="darkblue", weight="bold")

    # Legend
    ax.legend()

    if output_path != None:
        plt.savefig(f"{output_path}", transparent=True, bbox_inches="tight")
        return_path = output_path
    else:
        return_path = f"./emopia/{time.strftime('%Y%m%d-%H%M%S')}.png"
        plt.savefig(return_path, transparent=True, bbox_inches="tight")
    
    return return_path

    # plt.show()


if __name__ == "__main__":
    # split_midi_by_bars("../2_s2.mid",  output_dir="output_bars")
    # split_midi_by_bars("../2_s2.mid")
    draw_ar_vl_path(split_midi_by_bars("../2_t2.mid"), 
                    split_midi_by_bars(mido_to_pretty_midi("../performance_20241113-133539.mid")))
