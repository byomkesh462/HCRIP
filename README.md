# Hoichoi Downloader

A Python-based downloader for movies and TV shows from [Hoichoi.tv](https://www.hoichoi.tv). It supports:

- 🧠 Automatic metadata extraction
- 🎞️ Download via HLS (.m3u8) or direct MP4 (RAW) if available
- 🗃️ Auto muxing with subtitles and audio using `mkvmerge`
- 🎯 Full support for movies and multi-season series
- 🎛️ Parallel segmented downloading with progress bars (via `rich`)

---

## ⚙️ Requirements

- Python 3.8+
- Dependencies:
  - `aiohttp`, `aiofiles`, `rich`, `m3u8`
  - External tool: `mkvmerge` (from [MKVToolNix](https://mkvtoolnix.download/))
  - (Optional) `ffmpeg` for HLS merging

## 📥 Clone this Repository

```bash
git clone https://github.com/beenabird/Hoichoi-Ripper.git
cd Hoichoi-Ripper

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## 📁 Project Structure

```
.
├── hoichoi.py         # Main interface for URL input and control
├── dl.py              # Async downloader (HLS/MP4 with multi-thread)
├── config.json        # API config and naming templates
├── requirements.txt   # Python dependencies
├── .gitignore         # Git ignore rules
```

---

## 🚀 Usage

### 🔹 Download a Movie
```bash
python hoichoi.py "https://www.hoichoi.tv/movies/abc" --download
```

### 🔹 Download a Series
```bash
python hoichoi.py "https://www.hoichoi.tv/shows/xyz" --download
```

### 🔹 Downlaod RAW MP4 (if available)
```bash
python hoichoi.py "<hoichoi-url>" --download --raw
```

### 🔹 Customize Output Folder & Tag
```bash
python hoichoi.py "<url>" --download -o my_downloads --tag CUSTOM
```

---

## 📝 Notes

- RAW files are attempted only if `--raw` is passed.
- Subtitles (SRT) and audio languages are auto-detected if available.
- Final files are named using customizable templates in `config.json`.
- You **must** have `mkvmerge` in your PATH for muxing to work.

---

## 📦 License

MIT License — Free to use and modify.
