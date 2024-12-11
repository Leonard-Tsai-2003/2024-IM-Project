import os
import shutil # it's in standard library, no need to pip install
import pretty_midi

def split_midi_by_bars(input_file, output_dir):
    # Load the MIDI file
    midi_data = pretty_midi.PrettyMIDI(input_file)
    
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

    # Get the tempo to calculate bar duration
    ignore = '''tempo = bpm
    seconds_per_beat = 60 / tempo
    bar_duration = beats_per_bar * seconds_per_beat'''
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

        # Save each bar as a separate MIDI file in the subdirectory
        output_path = os.path.join(output_dir, f"bar_{bar_number}.mid")
        bar_midi.write(output_path)
        print(f"Saved bar {bar_number} to {output_path}")
        
        # Move to the next bar
        bar_start += bar_duration
        bar_number += 1

# Usage example
split_midi_by_bars("2_s2.mid", "output_bars")
