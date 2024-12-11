import openai
import mido

with open('secret key.txt', 'r', encoding='utf-8') as file:
    # Read the file content
    key = file.read()
openai.api_key = key

def get_midi_file(midi_path):
    return str(mido.MidiFile(midi_path).tracks[0])
def get_response(prompt, model="gpt-4o-mini"):
    messages = [
        {"role": "system", "content": 
         
         f"""You are a piano tutor. You'll receive two MIDI files, one as a reference performance 
         and the other as the student's performance. Analyze both and provide detailed feedback 
         and suggestions for improvement. Please don't provide abundant response. Just give me only 
         how the student play compared to the reference. You should provide at most three sentences.
         
         Here are three examples:
         Reference:{get_midi_file("2_t2.mid")}
         Student1: {get_midi_file("2_s1.mid")}
         
         After receiving the pair of inputs, Reference and Student1, you should output: "The first half
         of the reference piece features crescendos and decrescendos, conveying strong emotion. However,
         the student maintained a constant velocity throughout. The tempo and pedals are accurate, but
         the student's note durations are slightly shorter.""
         
         Student2: {get_midi_file("2_s2.mid")}
         After receiving the pair of inputs, Reference and Student2, you should output: "The student's
         articulation is highly inaccurate; each note should be played legato rather than staccato.
         Although the velocity, tempo, and pedal usage are accurate, the articulation undermines the
         emotional expression."
         
         Student3: {get_midi_file("2_s3.mid")}
         After receiving the pair of inputs, Reference and Student3, you should output: "The student
         played too hastily, resulting in poor tempo control. However, the notes, pedal usage, and
         velocity are accurate. The student should focus on practicing steady tempo control first."
         
         """},
        {"role": "user", "content": prompt}
    ]
    response = openai.ChatCompletion.create(
    model=model, messages=messages, temperature=0.7)
    
    return response, response.choices[0].message["content"]
def create_prompt(ref, stu):
    return f"Reference:{get_midi_file(ref)}\n Student:{get_midi_file(stu)}"

if __name__ == "__main__":
    response_info, response = get_response(create_prompt(ref="2_t2.mid", stu="2_sj.mid"))
    print(response_info.choices[0].message.content)