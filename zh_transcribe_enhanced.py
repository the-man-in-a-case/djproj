#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple

import torch
import whisper
from tqdm import tqdm
from rich import print
from pydub import AudioSegment

# VAD
import webrtcvad
import collections
import contextlib
import wave

# ============================ 基础工具 ============================

def has_cuda() -> bool:
    try:
        return torch.cuda.is_available()
    except Exception:
        return False

def run_ffmpeg_cmd(cmd: list):
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def convert_to_wav_16k_mono(src: str, dst: str):
    """统一转 16kHz/16-bit/mono WAV"""
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-ac", "1", "-ar", "16000", "-vn",
        "-c:a", "pcm_s16le",
        dst
    ]
    run_ffmpeg_cmd(cmd)

# ============================ 音频增强（关键新增） ============================

def enhance_audio_with_ffmpeg(src_wav: str, dst_wav: str,
                              level: str = "medium",
                              use_arnndn: bool = False,
                              rnnoise_model: str = None):
    """
    通过 FFmpeg 滤镜做语音增强：
      - 带通: highpass + lowpass
      - 去齿音: deesser
      - 频域降噪: afftdn（默认）；若提供 rnnoise/arnndn 模型则切 arnndn
      - 语音归一: speechnorm
      - 响度校准: loudnorm
    level: light / medium / strong
    """
    # 频段建议：人声大多集中 120Hz ~ 7.5kHz
    hp = {"light": 80, "medium": 120, "strong": 150}[level]
    lp = {"light": 8000, "medium": 7600, "strong": 7200}[level]

    # 去齿音阈值
    deess = {"light": 4, "medium": 6, "strong": 8}[level]

    # 降噪强度（afftdn 的噪声抑制量）
    # 说明：afftdn 参数随 FFmpeg 版本可能有细微差异，以下为常用可用组合
    afftdn = {
        "light": "afftdn=nr=8:nt=w",     # 轻度频域降噪
        "medium": "afftdn=nr=12:nt=w",
        "strong": "afftdn=nr=18:nt=w"
    }[level]

    # speechnorm 提升说话清晰与动态一致性
    # e=6（能量门限）, r=恢复速度, l=预延时
    speechnorm = "speechnorm=e=6:r=0.0001:l=1"

    # 响度标准化（适中响度，避免过驱动）
    loudnorm = "loudnorm=I=-20:TP=-1.5:LRA=11"

    # 如果提供了神经降噪模型，优先使用 arnndn（效果好于 afftdn）
    denoise_chain = afftdn
    if use_arnndn and rnnoise_model:
        # 常见模型：rnnoise 官方模型、speech_enhancement.mnn 等
        # 需与 FFmpeg 支持的 arnndn 版本/模型匹配
        denoise_chain = f"arnndn=m='{rnnoise_model}'"

    # 合成滤镜链：带通 -> 去齿音 -> 降噪 -> 归一 -> 响度
    afilters = [
        f"highpass=f={hp}",
        f"lowpass=f={lp}",
        f"deesser=i={deess}",
        denoise_chain,
        speechnorm,
        loudnorm
    ]
    af_str = ",".join(afilters)

    cmd = [
        "ffmpeg", "-y", "-i", src_wav,
        "-ac", "1", "-ar", "16000",
        "-af", af_str,
        "-c:a", "pcm_s16le",
        dst_wav
    ]
    run_ffmpeg_cmd(cmd)

# ============================ VAD 切分 ============================

class Frame(object):
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration

def read_wave(path):
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        assert wf.getnchannels() == 1, "VAD 需要单声道"
        assert wf.getsampwidth() == 2, "需要 16-bit PCM"
        assert wf.getframerate() == 16000, "需要 16kHz"
        frames = wf.readframes(wf.getnframes())
        return frames, wf.getframerate()

def frame_generator(frame_duration_ms, audio, sample_rate):
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / (2 * sample_rate))
    while offset + n <= len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n

def vad_collect(sample_rate, frame_ms, pad_ms, vad, frames, merge_gap=0.3, min_len=0.4):
    """返回合并/清理后的 (start, end) 片段"""
    import collections
    rb = collections.deque(maxlen=int(pad_ms / frame_ms))
    triggered = False
    voiced_frames = []
    segments = []
    start_time = 0.0

    for fr in frames:
        is_speech = vad.is_speech(fr.bytes, sample_rate)
        if not triggered:
            rb.append((fr, is_speech))
            if sum(1 for _, s in rb if s) > 0.9 * rb.maxlen:
                triggered, start_time = True, rb[0][0].timestamp
                voiced_frames.extend(f for f, _ in rb)
                rb.clear()
        else:
            voiced_frames.append(fr)
            rb.append((fr, is_speech))
            if sum(1 for _, s in rb if not s) > 0.9 * rb.maxlen:
                end = fr.timestamp + fr.duration
                if end - start_time >= min_len:
                    segments.append((start_time, end))
                triggered, voiced_frames = False, []
                rb.clear()

    if triggered and voiced_frames:
        end = voiced_frames[-1].timestamp + voiced_frames[-1].duration
        if end - start_time >= min_len:
            segments.append((start_time, end))

    # 合并近段
    merged = []
    for s, e in segments:
        if not merged:
            merged.append([s, e])
        else:
            if s - merged[-1][1] <= merge_gap:
                merged[-1][1] = e
            else:
                merged.append([s, e])
    return [(float(s), float(e)) for s, e in merged]

def cut_by_segments(wav_path: str, segments: List[Tuple[float, float]], out_dir: Path) -> List[Path]:
    audio = AudioSegment.from_wav(wav_path)
    outs = []
    for i, (s, e) in enumerate(segments):
        start_ms = int(s * 1000)
        end_ms = int(e * 1000)
        clip = audio[start_ms:end_ms]
        outp = out_dir / f"chunk_{i:04d}.wav"
        clip.export(outp, format="wav", parameters=["-ac", "1", "-ar", "16000"])
        outs.append(outp)
    return outs

# ============================ SRT 输出 ============================

def srt_time(x: float) -> str:
    h = int(x // 3600); m = int((x % 3600) // 60); s = int(x % 60)
    ms = int((x - int(x)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def write_srt(segments: List[Dict[str, Any]], srt_path: str):
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n{srt_time(seg['start'])} --> {srt_time(seg['end'])}\n{seg['text'].strip()}\n\n")

# ============================ 主流程（含增强） ============================

def transcribe_one(
    model,
    media_path: str,
    out_dir: Path,
    use_vad: bool = True,
    vad_level: int = 3,
    initial_prompt: str = "以下是标准普通话的录音转写，请直接输出中文，不要翻译：",
    temperature: float = 0.0,
    enhance: bool = True,
    enhance_level: str = "medium",
    rnnoise_model: str = None
):
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        # 1) 统一转 wav 16k mono
        raw_wav = os.path.join(td, "raw_16k.wav")
        convert_to_wav_16k_mono(media_path, raw_wav)

        # 2) 前处理增强（可选）
        proc_wav = os.path.join(td, "enhanced.wav")
        if enhance:
            use_arnndn = bool(rnnoise_model and Path(rnnoise_model).exists())
            enhance_audio_with_ffmpeg(raw_wav, proc_wav,
                                      level=enhance_level,
                                      use_arnndn=use_arnndn,
                                      rnnoise_model=rnnoise_model)
        else:
            proc_wav = raw_wav

        # 3) VAD 切分（可选）
        chunk_paths = [Path(proc_wav)]
        if use_vad:
            audio_bytes, sr = read_wave(proc_wav)
            vad = webrtcvad.Vad(vad_level)  # 0-3，越大越“严格”
            frames = list(frame_generator(30, audio_bytes, sr))
            segments = vad_collect(sr, 30, 300, vad, frames, merge_gap=0.3, min_len=0.4)
            if segments:
                vad_dir = Path(td) / "vad_chunks"
                vad_dir.mkdir(exist_ok=True)
                chunk_paths = cut_by_segments(proc_wav, segments, vad_dir)

        # 4) Whisper 参数
        kwargs = dict(
            task="transcribe",
            language="zh",
            temperature=temperature,
            condition_on_previous_text=True,
            initial_prompt=initial_prompt,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
        )

        # 5) 逐段转写+时间轴对齐
        all_segments = []
        offset = 0.0
        for cp in tqdm(chunk_paths, desc=f"转写 {Path(media_path).name}"):
            result = model.transcribe(str(cp), **kwargs)
            segs = result.get("segments", [])
            dur = AudioSegment.from_wav(cp).duration_seconds
            for s in segs:
                all_segments.append({
                    "start": float(s["start"]) + offset,
                    "end": float(s["end"]) + offset,
                    "text": s["text"]
                })
            offset += dur

        # 6) 写出
        stem = Path(media_path).stem
        txt_path = out_dir / f"{stem}.txt"
        srt_path = out_dir / f"{stem}.srt"
        json_path = out_dir / f"{stem}.json"

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("".join([s["text"].strip() for s in all_segments]).strip() + "\n")

        write_srt(all_segments, str(srt_path))

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"segments": all_segments}, f, ensure_ascii=False, indent=2)

        print(f"[green]✔ 转写完成：[/green]{media_path}")
        print(f"    TXT : {txt_path}")
        print(f"    SRT : {srt_path}")
        print(f"    JSON: {json_path}")

def main():
    parser = argparse.ArgumentParser(description="高效中文转写（Whisper + 增强 + 可选VAD）")
    parser.add_argument("input", help="输入文件/文件夹")
    parser.add_argument("-o", "--out", default="transcripts", help="输出目录")
    parser.add_argument("--model", default="medium",
                        choices=["tiny","base","small","medium","large","large-v2","large-v3"])
    parser.add_argument("--no-vad", action="store_true", help="关闭 VAD")
    parser.add_argument("--vad-level", type=int, default=3, choices=[0,1,2,3], help="VAD 激进程度（默认3）")
    parser.add_argument("--temp", type=float, default=0.0, help="temperature（默认0更稳定）")
    parser.add_argument("--prompt", type=str,
                        default="以下是标准普通话的录音转写，请直接输出中文，不要翻译：")

    # 新增增强相关参数
    parser.add_argument("--no-enhance", action="store_true", help="关闭增强/降噪")
    parser.add_argument("--enhance-level", default="medium", choices=["light","medium","strong"],
                        help="增强强度（默认 medium）")
    parser.add_argument("--rnnoise-model", type=str, default=None,
                        help="可选：FFmpeg arnndn/RNNoise 模型路径（提供则启用神经降噪）")

    args = parser.parse_args()

    device = "cuda" if has_cuda() else "cpu"
    fp16 = device == "cuda"
    print(f"[bold]设备[/bold]: {device} | [bold]fp16[/bold]: {fp16} | [bold]模型[/bold]: {args.model} | "
          f"[bold]增强[/bold]: {not args.no_enhance}({args.enhance_level}) | [bold]VAD[/bold]: {not args.no_vad}")

    model = whisper.load_model(args.model, device=device)
    if device == "cuda":
        model = model.to(device)

    # 收集媒体文件
    in_path = Path(args.input)
    exts = {".wav",".mp3",".m4a",".aac",".flac",".ogg",".wma",".mp4",".mkv",".mov",".avi"}
    files: List[Path] = []
    if in_path.is_file():
        files = [in_path]
    else:
        for p in sorted(in_path.rglob("*")):
            if p.suffix.lower() in exts:
                files.append(p)
    if not files:
        print("[red]未找到可处理的音/视频文件。[/red]")
        sys.exit(1)

    out_dir = Path(args.out)
    for f in files:
        try:
            transcribe_one(
                model=model,
                media_path=str(f),
                out_dir=out_dir,
                use_vad=(not args.no_vad),
                vad_level=args.vad_level,
                initial_prompt=args.prompt,
                temperature=args.temp,
                enhance=(not args.no_enhance),
                enhance_level=args.enhance_level,
                rnnoise_model=args.rnnoise_model,
            )
        except subprocess.CalledProcessError:
            print(f"[red]FFmpeg 处理失败：[/red]{f}")
        except Exception as e:
            print(f"[red]处理失败：[/red]{f} | 错误：{e}")

if __name__ == "__main__":
    main()
