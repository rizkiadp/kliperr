import os
import json
import cv2
import numpy as np
import mediapipe as mp
import whisper
import yt_dlp
import torch
import shutil
import imageio_ffmpeg
from groq import Groq
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
from moviepy.config import change_settings
from dotenv import load_dotenv
from colorama import Fore, Style, init
import subprocess

# Inisialisasi
init(autoreset=True)
load_dotenv() 

# Default Config
DEFAULT_CONFIG = {
    "JUMLAH_KLIP": 3,
    "FONT_SIZE": 70,
    "FONT_COLOR": '#FFD700',
    "FONT_COLOR_ALT": 'white',
    "STROKE_COLOR": 'black',
    "STROKE_WIDTH": 3,
    "FONT_TYPE": 'Arial-Bold',
    "FONT_TYPE": 'Arial-Bold',
    "POSISI_TEKS_Y": 0.75,
    "IMAGEMAGICK_BINARY": None # Auto-detect or set manually
}

# --- PATCH FFMPEG FOR WHISPER ---
# Whisper relies on 'ffmpeg' being in PATH.
# We explicitly copy imageio_ffmpeg's binary to the current directory as 'ffmpeg.exe'
# This is the most robust way to ensure subprocess.Popen("ffmpeg") works on Windows.
# duplicate import check?
try:
    import shutil
    import subprocess
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    # Destination in current directory
    dest_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
    
    if not os.path.exists(dest_ffmpeg):
        print(f"[INIT] Copying ffmpeg from {ffmpeg_exe} to {dest_ffmpeg}...")
        shutil.copy2(ffmpeg_exe, dest_ffmpeg)
    
    # Add CWD to PATH explicitly
    os.environ["PATH"] += os.pathsep + os.getcwd()
    
    # Verify
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[INIT] FFmpeg is ready and executable.")
    except Exception as e:
        print(f"[INIT] Warning: FFmpeg command test failed: {e}")

except Exception as e:
    print(f"[INIT] FFmpeg setup failed: {e}")
# --------------------------------

class KliperrGenerator:
    def __init__(self, api_key, config=None, logger_callback=None):
        self.api_key = api_key
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger_callback = logger_callback
        self.stop_requested = False
        
        # Setup Directories
        self.TEMP_DIR = "temp"
        self.OUT_DIR = "hasil_shorts"
        if not os.path.exists(self.TEMP_DIR): os.makedirs(self.TEMP_DIR)
        if not os.path.exists(self.OUT_DIR): os.makedirs(self.OUT_DIR)
        
        # Setup ImageMagick
        if self.config.get("IMAGEMAGICK_BINARY"):
            change_settings({"IMAGEMAGICK_BINARY": self.config["IMAGEMAGICK_BINARY"]})

        # Initialize Clients
        self.groq_client = Groq(api_key=self.api_key) if self.api_key else None

    def log(self, msg, type="info"):
        """Mengirim log ke callback (GUI) atau print ke console (CLI)"""
        if self.logger_callback:
            self.logger_callback(msg, type)
        else:
            if type == "error":
                print(f"{Fore.RED}[ERROR] {Style.RESET_ALL}{msg}")
            elif type == "success":
                print(f"{Fore.GREEN}[SUCCESS] {Style.RESET_ALL}{msg}")
            else:
                print(f"{Fore.CYAN}[INFO] {Style.RESET_ALL}{msg}")

    def get_video_info(self, url):
        """Ambil metadata video tanpa download"""
        # Check if local file
        if os.path.exists(url) and os.path.isfile(url):
            try:
                clip = VideoFileClip(url)
                dur = clip.duration
                clip.close()
                return {
                    'title': os.path.basename(url),
                    'thumbnail': None, # Local file handling needed for thumb
                    'duration': str(int(dur)) + "s",
                    'view_count': 'Local'
                }
            except:
                return {'title': os.path.basename(url), 'duration': 'Unknown', 'thumbnail': None}

        ydl_opts = {'quiet': True, 'no_warnings': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title'),
                    'thumbnail': info.get('thumbnail'),
                    'duration': info.get('duration_string'),
                    'view_count': info.get('view_count')
                }
        except Exception as e:
            self.log(f"Gagal memuat info: {e}", "error")
            return None

    def download_video(self, url):
        self.log(f"Mendownload Video: {url}")
        output_path = f"{self.TEMP_DIR}/source_video.mp4"
        if os.path.exists(output_path): os.remove(output_path)

        # Get FFmpeg binary from imageio-ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            'outtmpl': f"{self.TEMP_DIR}/raw_video.%(ext)s",
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': ffmpeg_exe, # Explicitly set ffmpeg path
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['web_creator', 'tv_embedded'] 
                }
            },
            'nocheckcertificate': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            for file in os.listdir(self.TEMP_DIR):
                if file.startswith("raw_video") and file.endswith(".mp4"):
                    shutil.move(os.path.join(self.TEMP_DIR, file), output_path)
                    return True
            return False
        except Exception as e:
            self.log(f"Gagal Download: {e}", "error")
            return False

    def transcribe_full(self, audio_path):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.log(f"Engine Transkripsi berjalan di: {device.upper()}")
        
        try:
            model = whisper.load_model("base", device=device)
            result = model.transcribe(audio_path, language='id', task='transcribe', fp16=False, word_timestamps=True)
            return result
        except Exception as e:
            self.log(f"Error Transkripsi: {e}", "error")
            return None

    def analyze_hooks_with_groq(self, transcript_text, num_clips):
        if self.stop_requested: return []
        
        # Limit user to ~12k chars to avoid TPM limit (approx 3-4k tokens + prompt)
        safe_text = transcript_text[:12000]
        self.log(f"Mengirim {len(safe_text)} karakter ke AI Groq...")

        prompt = f"""
        You are a professional Video Editor specializing in viral gossip and drama. Analyze this transcript.
        Find exactly {num_clips} viral segments for TikTok (30-60 seconds each).
        
        CRITERIA:
        1. PRIORITIZE GOSIP PANAS (HOT GOSSIP), DRAMA, CONTROVERSY, and SHOCKING REVELATIONS.
        2. Look for emotional moments, arguments, or secrets being revealed.
        3. Must have a strong viral hook.
        4. Must be self-contained context.
        5. Ignore boring, educational, or flat parts.
        
        TRANSCRIPT:
        {safe_text} ... (truncated)
        
        OUTPUT STRICT JSON ONLY:
        [
          {{ "start": 120.0, "end": 160.0, "title": "Judul_Klip_1" }},
          {{ "start": 300.5, "end": 350.0, "title": "Judul_Klip_2" }}
        ]
        """

        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.6,
                response_format={"type": "json_object"},
            )
            result_content = chat_completion.choices[0].message.content
            data = json.loads(result_content)
            
            if isinstance(data, list): return data
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list): return v
            return []
        except Exception as e:
            self.log(f"Groq API Error: {e}", "error")
            return []

    def create_hormozi_subtitle(self, word_data, vid_w, vid_h):
        try:
            from PIL import Image, ImageDraw, ImageFont
            from moviepy.editor import ImageClip
        except ImportError:
            return None

        raw_text = word_data.get('word', word_data.get('text', '')).strip()
        if not raw_text: return None

        text = raw_text.upper()
        # Config
        text_color = self.config['FONT_COLOR_ALT'] if len(text) <= 3 else self.config['FONT_COLOR']
        stroke_color = self.config['STROKE_COLOR']
        stroke_width = self.config['STROKE_WIDTH']
        font_size = self.config['FONT_SIZE']
        
        # Create PIL Image
        # Estimate size? For now create a large canvas
        # or use exact text size if font available.
        # Fallback to default font if custom not found?
        try:
            # Try to load Arial or similar
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
            
        # Measure text using getbbox (left, top, right, bottom)
        dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = dummy_draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        # Add padding
        pad = 20
        img_w, img_h = w + pad*2, h + pad*2
        
        # Draw
        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw text centered
        # xy is top-left usually for text
        draw.text((pad, pad), text, font=font, fill=text_color, 
                  stroke_width=stroke_width, stroke_fill=stroke_color)
        
        # Convert to numpy for MoviePy
        img_np = np.array(img)
        
        pos_y = self.config['POSISI_TEKS_Y']
        if pos_y <= 1: pos_y = int(vid_h * pos_y)
        
        return (ImageClip(img_np)
                .set_position(('center', pos_y))
                .set_start(word_data['start'])
                .set_end(word_data['end']))

    def process_single_clip(self, source_video, start_t, end_t, clip_name, segment_words, external_audio=None):
        if self.stop_requested: return
        self.log(f"Memproses: {clip_name}")

        try:
            full_clip = VideoFileClip(source_video)
            if end_t > full_clip.duration: end_t = full_clip.duration
            clip = full_clip.subclip(start_t, end_t)

            # Replace audio if external provided
            if external_audio:
                from moviepy.editor import AudioFileClip
                ext_audio_clip = AudioFileClip(external_audio).subclip(start_t, end_t)
                clip = clip.set_audio(ext_audio_clip)

            # 1. Face Tracking & Cropping
            temp_sub = f"{self.TEMP_DIR}/temp_{clip_name}.mp4"
            clip.write_videofile(temp_sub, codec='libx264', audio_codec='aac', logger=None)

            centers = []
            width = clip.w
            fps = clip.fps

            try:
                mp_face = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.6)
                cap = cv2.VideoCapture(temp_sub)
                real_fps = cap.get(cv2.CAP_PROP_FPS)
                if real_fps > 0: fps = real_fps
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                
                while True:
                    if self.stop_requested: break
                    ret, frame = cap.read()
                    if not ret: break
                    results = mp_face.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    x_c = width // 2
                    if results.detections:
                        for det in results.detections:
                            bbox = det.location_data.relative_bounding_box
                            x_c = int((bbox.xmin + bbox.width/2) * width)
                            break 
                    centers.append(x_c)
                cap.release()
            except Exception as e:
                self.log(f"Face Tracking Warning: {e}. Fallback to Center", "error")
                centers = []

            if self.stop_requested: return

             # Smoothing
            if not centers: centers = [width//2]
            window = 15
            if len(centers) > window:
                centers = np.convolve(centers, np.ones(window)/window, mode='same')

            def crop_fn(get_frame, t):
                idx = int(t * fps)
                safe_idx = min(idx, len(centers)-1)
                cx = centers[safe_idx]
                img = get_frame(t)
                h, w = img.shape[:2]
                target_width = int(h * 9/16)
                x1 = int(cx - target_width/2)
                x1 = max(0, min(w - target_width, x1))
                return img[:, x1:x1+target_width]

            final_clip = clip.fl(crop_fn, apply_to=['mask']).resize(height=1920)

            # 2. Subtitles
            subs = []
            vid_w, vid_h = final_clip.w, final_clip.h
            valid_words = [w for w in segment_words if w['start'] >= start_t and w['end'] <= end_t]

            for w in valid_words:
                if self.stop_requested: return
                word_data = {
                    'word': w.get('word', w.get('text', '')),
                    'start': w['start'] - start_t,
                    'end': w['end'] - start_t
                }
                try:
                    txt_clip = self.create_hormozi_subtitle(word_data, vid_w, vid_h)
                    if txt_clip: subs.append(txt_clip)
                except Exception as e:
                    print(f"Sub Error: {e}")
                    continue

            final = CompositeVideoClip([final_clip] + subs)

            # Output
            safe_name = "".join([c for c in clip_name if c.isalnum() or c=='_'])
            output_filename = f"{self.OUT_DIR}/{safe_name}.mp4"
            
            if not self.stop_requested:
                final.write_videofile(output_filename, codec='libx264', audio_codec='aac', fps=24, preset='fast', threads=4, logger=None, pixel_format='yuv420p')
            
            full_clip.close()
            final.close()
            
            if os.path.exists(temp_sub): os.remove(temp_sub)
            if not self.stop_requested:
                self.log(f"Disimpan: {output_filename}", "success")
            
        except Exception as e:
            self.log(f"Gagal memproses klip {clip_name}: {e}", "error")

    def run_process(self, input_source, external_audio=None):
        self.stop_requested = False
        
        if not self.api_key:
            self.log("API Key Groq tidak ditemukan!", "error")
            return

        is_local_file = os.path.exists(input_source) and os.path.isfile(input_source)
        source_path = ""

        if is_local_file:
            self.log(f"Menggunakan file lokal: {input_source}")
            source_path = input_source
        else:
            # Assume URL
            if not self.download_video(input_source): return
            if self.stop_requested: return
            source_path = f"{self.TEMP_DIR}/source_video.mp4"

        # 2. Transkrip
        try:
            if external_audio and os.path.exists(external_audio):
                self.log(f"Menggunakan audio eksternal: {external_audio}")
                audio_path = external_audio
                # Verify audio duration matches video? For now assume synced.
            else:
                video = VideoFileClip(source_path)
                audio_path = f"{self.TEMP_DIR}/source_audio.wav"
                video.audio.write_audiofile(audio_path, verbose=False, logger=None)
                video.close()
        except Exception as e:
            self.log(f"Gagal memproses audio: {e}", "error")
            return

        self.log("Sedang mentranskripsi audio...")
        if self.stop_requested: return
        whisper_result = self.transcribe_full(audio_path)
        if not whisper_result: return

        full_text = ""
        for seg in whisper_result['segments']:
            full_text += f"[{seg['start']:.1f}] {seg['text']}\n"
        all_words = [w for seg in whisper_result['segments'] for w in seg['words']]

        # 3. Analisis AI
        self.log("AI sedang mencari Hooks...")
        if self.stop_requested: return
        clips_data = self.analyze_hooks_with_groq(full_text, self.config['JUMLAH_KLIP'])

        if not clips_data:
            self.log("AI tidak menemukan klip.", "error")
            return

        self.log(f"Ditemukan {len(clips_data)} Klip!", "success")
        
        # 4. Proses Editing
        for i, data in enumerate(clips_data):
            if self.stop_requested: break
            self.log(f"Memproses Klip {i+1}/{len(clips_data)}: {data.get('title')}")
            self.process_single_clip(
                source_path,
                float(data['start']),
                float(data['end']),
                f"Short_{i+1}_{data.get('title', 'Clip')}",
                all_words,
                external_audio=audio_path if external_audio else None
            )

        if not self.stop_requested:
            self.log(f"Semua selesai! Cek folder '{self.OUT_DIR}'", "success")
        else:
            self.log("Proses dibatalkan oleh pengguna.", "error")

    def stop(self):
        self.stop_requested = True
        self.log("Sedang membatalkan proses... Mohon tunggu sebentar.", "error")


def main():
    # CLI version wrapped around class
    api_key = os.getenv("GROQ_API_KEY")
    url = "https://www.youtube.com/watch?v=1ziIpehWMiI" # Default CLI URL
    
    app = KliperrGenerator(api_key)
    print(f"\n{Fore.YELLOW}=== AI AUTO SHORTS (LOCAL CLI) ==={Style.RESET_ALL}\n")
    app.run_process(url)

if __name__ == "__main__":
    main()