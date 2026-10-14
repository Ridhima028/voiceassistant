from faster_whisper import WhisperModel

from config import MAX_DURATION_SECONDS, MAX_DURATION_MINUTES


class AudioTooLongError(Exception):
    """Raised when the audio exceeds MAX_DURATION_MINUTES, before we waste
    CPU time transcribing something that's going to be rejected anyway."""
    pass


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

    # info.duration is populated as soon as Whisper loads the audio header —
    # BEFORE it does the expensive work of iterating/decoding every segment.
    # So checking here lets us bail out early on an overly long file.
    if info.duration > MAX_DURATION_SECONDS:
        raise AudioTooLongError(
            f"Audio is {info.duration / 60:.1f} minutes long, "
            f"which exceeds the {MAX_DURATION_MINUTES}-minute limit."
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
        "duration": info.duration,
        "text": full_text,
        "segments": transcript_segments
    }