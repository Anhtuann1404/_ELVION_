"""Evaluate a local acoustic wake prototype against the private enrollment corpus."""
import argparse
import io
import json
from pathlib import Path
import sqlite3
from time import perf_counter
import wave

import numpy as np
from scipy.fft import dct
from scipy.spatial.distance import cdist

from elvion.storage.traces import default_data_dir
from elvion.voice.continuous.wakeword import KeywordWakeWordDetector


def features(audio):
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
            raise ValueError('Expected mono PCM at 16 kHz')
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(float)
    return pcm_features(samples)


def pcm_features(samples):
    if len(samples) < 400:
        return None
    frames = np.lib.stride_tricks.sliding_window_view(samples, 400)[::160]
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    floor, peak = np.quantile(rms, [0.2, 0.95])
    active = np.flatnonzero(rms >= max(100, floor * 2, peak * 0.10))
    if len(active) < 12:
        return None
    frames = frames[max(0, active[0] - 3):active[-1] + 4]
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(400), n=512)) ** 2
    mel = np.linspace(2595 * np.log10(1 + 80 / 700), 2595 * np.log10(1 + 7600 / 700), 26)
    edges = 700 * (10 ** (mel / 2595) - 1)
    hz = np.fft.rfftfreq(512, 1 / 16000)
    filters = np.maximum(0, np.minimum((hz - edges[:-2, None]) / np.diff(edges)[:-1, None],
                                      (edges[2:, None] - hz) / np.diff(edges)[1:, None]))
    coefficients = dct(np.log(np.maximum(spectrum @ filters.T, 1)), type=2, norm='ortho')[:, 1:13]
    return coefficients / np.maximum(np.linalg.norm(coefficients, axis=1, keepdims=True), 1e-6)


def distance(a, b):
    costs = cdist(a, b, metric='sqeuclidean')
    previous = np.full(len(b) + 1, np.inf)
    previous[0] = 0
    for row in costs:
        current = np.full_like(previous, np.inf)
        diagonal_or_vertical = np.minimum(previous[:-1] + 2 * row, previous[1:] + row)
        horizontal_cost = np.cumsum(row)
        current[1:] = horizontal_cost + np.minimum.accumulate(diagonal_or_vertical - horizontal_cost)
        previous = current
    return float(previous[-1] / (len(a) + len(b)))


def score(clip, references):
    if clip is None:
        return float('inf')
    distances = sorted(distance(clip, ref) for ref in references)
    return float(np.median(distances[:3]))


def acoustic_match(window, references, threshold):
    clip = pcm_features(np.frombuffer(window, dtype='<i2').astype(float))
    return score(clip, references) <= threshold


def replay(audio, references, threshold):
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        pcm = wav.readframes(wav.getnframes())
    # Allow a final complete window after the user finishes the phrase.
    pcm += bytes(48000)
    now = 100.0
    elapsed = []

    def verify(window):
        start = perf_counter()
        matched = acoustic_match(window, references, threshold)
        elapsed.append((perf_counter() - start) * 1000)
        return 'elvion' if matched else ''

    detector = KeywordWakeWordDetector(verifier=verify, clock=lambda: now,
                                       ambient_window_seconds=1.5, min_check_interval=0.4)
    for end in range(640, len(pcm) + 1, 640):
        now = 100 + end / 32000
        if detector.detect(pcm[max(0, end - 48000):end]).detected:
            return end / 32000, elapsed
    return None, elapsed


def read_samples(path):
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        return db.execute('''SELECT r.split,s.kind,s.audio FROM samples s
                             JOIN sessions r ON r.id=s.session_id''').fetchall()


def fit(rows):
    train = [features(audio) for split, kind, audio in rows if split == 'train' and kind == 'control']
    references = [clip for clip in train if clip is not None]
    negatives = [features(audio) for split, kind, audio in rows if split == 'train' and kind == 'dictation']
    if len(references) < 4 or not negatives:
        raise ValueError('Need four usable training calls and at least one training negative')
    positive_scores = [score(clip, references[:i] + references[i + 1:]) for i, clip in enumerate(references)]
    negative_scores = [score(clip, references) for clip in negatives]
    # Choose the most permissive training threshold that rejects every training negative.
    threshold = float(min(max(positive_scores), np.nextafter(min(negative_scores), -np.inf)))
    report = {'train_positive_usable': len(references), 'train_positive_total': len(train),
              'threshold': float(threshold),
              'train_positive_loo_accepted': sum(v <= threshold for v in positive_scores),
              'train_negative_rejected': sum(v > threshold for v in negative_scores),
              'train_negative_total': len(negative_scores)}
    return references, threshold, report


def evaluate(path, *, streaming=False):
    rows = read_samples(path)
    references, threshold, report = fit(rows)
    for kind, label in [('control', 'positive'), ('dictation', 'negative')]:
        scores = [score(features(audio), references) for split, k, audio in rows
                  if split == 'held_out' and k == kind]
        report['held_out_' + label] = {'accepted': sum(v <= threshold for v in scores), 'total': len(scores)}
        if streaming:
            results = [replay(audio, references, threshold) for split, k, audio in rows
                       if split == 'held_out' and k == kind]
            times = [time for time, _ in results if time is not None]
            latencies = [ms for _, checks in results for ms in checks]
            report['replay_' + label] = {
                'accepted': len(times), 'total': len(results),
                'median_seconds_from_clip_start': round(float(np.median(times)), 3) if times else None,
                'median_score_ms': round(float(np.median(latencies)), 1) if latencies else None,
                'max_score_ms': round(max(latencies), 1) if latencies else None,
            }
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=default_data_dir() / 'wake-voice' / 'corpus.sqlite3')
    parser.add_argument('--streaming', action='store_true')
    args = parser.parse_args()
    print(json.dumps(evaluate(args.database, streaming=args.streaming), indent=2))
