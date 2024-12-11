import pretty_midi
import torch
from argparse import ArgumentParser, Namespace
torch.manual_seed(123)

from pathlib import Path
import torch.nn as nn
from omegaconf import DictConfig, OmegaConf
from torch.nn.utils.rnn import pad_packed_sequence, pack_padded_sequence, PackedSequence
from emopia.package.processor import encode_midi
from emopia.package.net import SAN
import os

RANGE_NOTE_ON = 128
RANGE_NOTE_OFF = 128
RANGE_VEL = 32
RANGE_TIME_SHIFT = 100

START_IDX = {
    'note_on': 0,
    'note_off': RANGE_NOTE_ON,
    'time_shift': RANGE_NOTE_ON + RANGE_NOTE_OFF,
    'velocity': RANGE_NOTE_ON + RANGE_NOTE_OFF + RANGE_TIME_SHIFT
}


class SustainAdapter:
    def __init__(self, time, type):
        self.start =  time
        self.type = type


class SustainDownManager:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.managed_notes = []
        self._note_dict = {} # key: pitch, value: note.start

    def add_managed_note(self, note: pretty_midi.Note):
        self.managed_notes.append(note)

    def transposition_notes(self):
        for note in reversed(self.managed_notes):
            try:
                note.end = self._note_dict[note.pitch]
            except KeyError:
                note.end = max(self.end, note.end)
            self._note_dict[note.pitch] = note.start


# Divided note by note_on, note_off
class SplitNote:
    def __init__(self, type, time, value, velocity):
        ## type: note_on, note_off
        self.type = type
        self.time = time
        self.velocity = velocity
        self.value = value

    def __repr__(self):
        return '<[SNote] time: {} type: {}, value: {}, velocity: {}>'\
            .format(self.time, self.type, self.value, self.velocity)


class Event:
    def __init__(self, event_type, value):
        self.type = event_type
        self.value = value

    def __repr__(self):
        return '<Event type: {}, value: {}>'.format(self.type, self.value)

    def to_int(self):
        return START_IDX[self.type] + self.value

    @staticmethod
    def from_int(int_value):
        info = Event._type_check(int_value)
        return Event(info['type'], info['value'])

    @staticmethod
    def _type_check(int_value):
        range_note_on = range(0, RANGE_NOTE_ON)
        range_note_off = range(RANGE_NOTE_ON, RANGE_NOTE_ON+RANGE_NOTE_OFF)
        range_time_shift = range(RANGE_NOTE_ON+RANGE_NOTE_OFF,RANGE_NOTE_ON+RANGE_NOTE_OFF+RANGE_TIME_SHIFT)

        valid_value = int_value

        if int_value in range_note_on:
            return {'type': 'note_on', 'value': valid_value}
        elif int_value in range_note_off:
            valid_value -= RANGE_NOTE_ON
            return {'type': 'note_off', 'value': valid_value}
        elif int_value in range_time_shift:
            valid_value -= (RANGE_NOTE_ON + RANGE_NOTE_OFF)
            return {'type': 'time_shift', 'value': valid_value}
        else:
            valid_value -= (RANGE_NOTE_ON + RANGE_NOTE_OFF + RANGE_TIME_SHIFT)
            return {'type': 'velocity', 'value': valid_value}
        
def _divide_note(notes):
    result_array = []
    notes.sort(key=lambda x: x.start)

    for note in notes:
        on = SplitNote('note_on', note.start, note.pitch, note.velocity)
        off = SplitNote('note_off', note.end, note.pitch, None)
        result_array += [on, off]
    return result_array


def _merge_note(snote_sequence):
    note_on_dict = {}
    result_array = []

    for snote in snote_sequence:
        # print(note_on_dict)
        if snote.type == 'note_on':
            note_on_dict[snote.value] = snote
        elif snote.type == 'note_off':
            try:
                on = note_on_dict[snote.value]
                off = snote
                if off.time - on.time == 0:
                    continue
                result = pretty_midi.Note(on.velocity, snote.value, on.time, off.time)
                result_array.append(result)
            except:
                print('info removed pitch: {}'.format(snote.value))
    return result_array


def _snote2events(snote: SplitNote, prev_vel: int):
    result = []
    if snote.velocity is not None:
        modified_velocity = snote.velocity // 4
        if prev_vel != modified_velocity:
            result.append(Event(event_type='velocity', value=modified_velocity))
    result.append(Event(event_type=snote.type, value=snote.value))
    return result


def _event_seq2snote_seq(event_sequence):
    timeline = 0
    velocity = 0
    snote_seq = []

    for event in event_sequence:
        if event.type == 'time_shift':
            timeline += ((event.value+1) / 100)
        if event.type == 'velocity':
            velocity = event.value * 4
        else:
            snote = SplitNote(event.type, timeline, event.value, velocity)
            snote_seq.append(snote)
    return snote_seq


def _make_time_sift_events(prev_time, post_time):
    time_interval = int(round((post_time - prev_time) * 100))
    results = []
    while time_interval >= RANGE_TIME_SHIFT:
        results.append(Event(event_type='time_shift', value=RANGE_TIME_SHIFT-1))
        time_interval -= RANGE_TIME_SHIFT
    if time_interval == 0:
        return results
    else:
        return results + [Event(event_type='time_shift', value=time_interval-1)]


def _control_preprocess(ctrl_changes):
    sustains = []

    manager = None
    for ctrl in ctrl_changes:
        if ctrl.value >= 64 and manager is None:
            # sustain down
            manager = SustainDownManager(start=ctrl.time, end=None)
        elif ctrl.value < 64 and manager is not None:
            # sustain up
            manager.end = ctrl.time
            sustains.append(manager)
            manager = None
        elif ctrl.value < 64 and len(sustains) > 0:
            sustains[-1].end = ctrl.time
    return sustains

# replace _note_preprocess for generative midi
def _note_preprocess(susteins, notes):
    note_stream = []
    if susteins:
        for sustain in susteins:
            for note_idx, note in enumerate(notes):
                if note.start < sustain.start:
                    note_stream.append(note)
                elif note.start > sustain.end:
                    notes = notes[note_idx:]
                    sustain.transposition_notes()
                    break
                else:
                    sustain.add_managed_note(note)
        for sustain in susteins:
            note_stream += sustain.managed_notes
    else:
        note_stream = notes
    note_stream.sort(key= lambda x: x.start)
    return note_stream
    

def encode_midi(file_path):
    events = []
    notes = []
    if type(file_path) == str:
        mid = pretty_midi.PrettyMIDI(midi_file=file_path)
    else: # file_path is a pretty MIDI file
        mid = file_path

    for inst in mid.instruments:
        inst_notes = inst.notes
        # ctrl.number is the number of sustain control. If you want to know abour the number type of control,
        # see https://www.midi.org/specifications-old/item/table-3-control-change-messages-data-bytes-2
        ctrls = _control_preprocess([ctrl for ctrl in inst.control_changes if ctrl.number == 64])
        notes += _note_preprocess(ctrls, inst_notes)

    dnotes = _divide_note(notes)

    dnotes.sort(key=lambda x: x.time)
    cur_time = 0
    cur_vel = 0
    for snote in dnotes:
        events += _make_time_sift_events(prev_time=cur_time, post_time=snote.time)
        events += _snote2events(snote=snote, prev_vel=cur_vel)
        # events += _make_time_sift_events(prev_time=cur_time, post_time=snote.time)

        cur_time = snote.time
        cur_vel = snote.velocity

    return [e.to_int() for e in events]


def predict(args):# -> None:
    ignore = """
    device = args.cuda if args.cuda and torch.cuda.is_available() else 'cpu'
    if args.cuda:
        print('GPU name: ', torch.cuda.get_device_name(device=args.cuda))"""
    device = 'cpu'
    config_path = Path("emopia/best_weight", args["types"], args["task"], "hparams.yaml")
    checkpoint_path = Path("emopia/best_weight", args["types"], args["task"], "best.ckpt")
    config = OmegaConf.load(config_path)
    label_list = list(config.task.labels)
    if True:
        model = SAN( 
            num_of_dim= config.task.num_of_dim, 
            vocab_size= config.midi.pad_idx+1, 
            lstm_hidden_dim= config.hparams.lstm_hidden_dim, 
            embedding_size= config.hparams.embedding_size, 
            r= config.hparams.r)
        state_dict = torch.load(checkpoint_path, map_location=torch.device(device))#args.cuda))
        new_state_map = {model_key: model_key.split("model.")[1] for model_key in state_dict.get("state_dict").keys()}
        new_state_dict = {new_state_map[key]: value for (key, value) in state_dict.get("state_dict").items() if key in new_state_map.keys()}
        model.load_state_dict(new_state_dict)
        model.eval()
    model = model.to(device)

    quantize_midi = encode_midi(args["file_path"])
    model_input = torch.LongTensor(quantize_midi).unsqueeze(0)
    prediction = model(model_input).to(device)

    pred_label = label_list[prediction.squeeze(0).max(0)[1].detach().cpu().numpy()]
    pred_value = prediction.squeeze(0).detach().cpu().numpy()
    print("========")
    print(args["file_path"], " is emotion", pred_label)
    print("Inference values: ", pred_value)

    return pred_label, pred_value


ignore = '''if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--types", default="midi_like", type=str, choices=["midi_like", "remi", "wav"])
    parser.add_argument("--task", default="ar_va", type=str, choices=["ar_va", "arousal", "valence"])
    parser.add_argument("--file_path", default="./dataset/sample_data/Sakamoto_MerryChristmasMr_Lawrence.mid", type=str)
    parser.add_argument('--cuda', default='cuda:0', type=str)
    args = parser.parse_args()
    _, _ = predict(args)'''

def get_ar_vl_inference(midi_file_or_path):
    args = {"types": "midi_like", "task": "ar_va", "file_path": midi_file_or_path}
    temp_pred_label, temp_pred_value = predict(args)
    # print(temp_pred_label, temp_pred_value)
    return temp_pred_label, temp_pred_value

if __name__ == "__main__":
    pred_label = []
    pred_value = []
    filenames = os.listdir("../output_bars")
    filenames = sorted(filenames, key=lambda x: int(x.split('_')[1].split('.')[0]))
    for file in filenames:
        args = {"types": "midi_like", "task": "ar_va", "file_path": "../output_bars/" + file}
        temp_pred_label, temp_pred_value = predict(args)
        pred_label.append(temp_pred_label)
        pred_value.append(temp_pred_value.tolist())

    print(pred_value)
    # get_ar_vl_inference("../2_s2.mid")