from faster_whisper import WhisperModel


# Load the model once when the service starts.
model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)  #this loads the pretrained model


def transcribe_audio(audio_path: str):
    segments, info = model.transcribe(
        audio_path,
        beam_size=5
    )

    transcript_segments = []

    for segment in segments: #whisper segment into json friendly structure
        
        transcript_segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip()
        })

    full_text = " ".join(
        segment["text"]
        for segment in transcript_segments
    )

    return { # info tells about the metadata of the transcription process
        "language": info.language,
        "language_probability": info.language_probability,
        "text": full_text,
        "segments": transcript_segments
    }