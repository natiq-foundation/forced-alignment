import requests
import torch
import tempfile
from pydub import AudioSegment
from ctc_forced_aligner import (
    load_audio,
    load_alignment_model,
    generate_emissions,
    preprocess_text,
    get_alignments,
    get_spans,
    postprocess_results,
)
import os

def download_and_convert_mp3_to_wav(mp3_url: str) -> str:
    response = requests.get(mp3_url)
    if response.status_code != 200:
        return "failed to download"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as mp3_file:
        mp3_file.write(response.content)
        mp3_path = mp3_file.name
    wav_path = mp3_path.replace(".mp3", ".wav")
    audio = AudioSegment.from_mp3(mp3_path)
    audio.export(wav_path, format="wav")
    os.remove(mp3_path)
    return wav_path

def align_audio(mp3_url, text, batch_size = 4, romanize = True, language = "ar"):
    wav_path = download_and_convert_mp3_to_wav(mp3_url)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    alignment_model, alignment_tokenizer = load_alignment_model(
        device,
        dtype=torch.float16 if device == "cuda" else torch.float32,
    )
    audio_waveform = load_audio(wav_path, alignment_model.dtype, alignment_model.device)
    os.remove(wav_path)
    text = text.strip().replace("\n", " ")
    emissions, stride = generate_emissions(
        alignment_model, audio_waveform, batch_size=batch_size
    )
    tokens_starred, text_starred = preprocess_text(
        text,
        romanize=romanize,
        language=language,
    )
    segments, scores, blank_token = get_alignments(
        emissions,
        tokens_starred,
        alignment_tokenizer,
    )
    spans = get_spans(tokens_starred, segments, blank_token)
    word_timestamps = postprocess_results(text_starred, spans, stride, scores)
    return word_timestamps