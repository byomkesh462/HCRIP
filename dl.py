import os
import re
import sys
import time
import asyncio
import argparse
import platform
import shutil
import aiohttp
import aiofiles

from urllib.parse import urljoin
from typing import List, Tuple
from rich.table import Table
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn
)
from rich.console import Console
from rich import box

# Optional M3U8 support
try:
    import m3u8
except ImportError:
    m3u8 = None

console = Console()

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

FFMPEG_CMD = shutil.which("ffmpeg") or "ffmpeg"

# — Defaults —————————————————————————————————————————————————————————————————
DEFAULT_SOURCE_URL      = os.getenv("SOURCE_URL", "")
DEFAULT_MAX_CONNECTIONS = 200
DEFAULT_MP4_CONNECTIONS = 16
DEFAULT_CONNECT_TIMEOUT = 20
DEFAULT_OUTPUT_DIR      = "downloads"
SEGMENT_CHUNK_SIZE      = 8 * 1024 * 1024
FILE_CHUNK_SIZE         = 1 * 1024 * 1024
RETRIES                 = 3
# ——————————————————————————————————————————————————————————————————————————————

async def fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
        resp.raise_for_status()
        return await resp.text()

async def get_content_length(session: aiohttp.ClientSession, url: str) -> int:
    async with session.head(url, timeout=aiohttp.ClientTimeout(total=DEFAULT_CONNECT_TIMEOUT)) as resp:
        resp.raise_for_status()
        return int(resp.headers.get('content-length', 0))

async def download_chunk(session: aiohttp.ClientSession, url: str, start: int, end: int, part_file: str, progress: Progress, task_id: int):
    headers = {'Range': f"bytes={start}-{end}"}
    for attempt in range(1, RETRIES+1):
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=None)) as resp:
                resp.raise_for_status()
                async with aiofiles.open(part_file, 'wb') as f:
                    async for chunk in resp.content.iter_chunked(SEGMENT_CHUNK_SIZE):
                        await f.write(chunk)
                        progress.update(task_id, advance=len(chunk))
            return
        except Exception as e:
            console.print(f"[yellow]Attempt {attempt} failed for {part_file}: {e}[/]")
    console.print(f"[red]Giving up on {part_file} after {RETRIES} attempts[/]")

async def merge_parts(final_file: str, parts: List[str]):
    async with aiofiles.open(final_file, 'wb') as out:
        for part in parts:
            async with aiofiles.open(part, 'rb') as pf:
                while chunk := await pf.read(FILE_CHUNK_SIZE):
                    await out.write(chunk)
            os.remove(part)

async def parse_variants(master_url: str, master_text: str) -> List[Tuple[int,int,str,str,str,str]]:
    variants = []
    if m3u8:
        playlist = m3u8.loads(master_text, uri=master_url)
        for idx, pl in enumerate(playlist.playlists, start=1):
            si     = pl.stream_info
            bw     = si.bandwidth or 0
            res    = f"{si.resolution[0]}x{si.resolution[1]}" if si.resolution else "unknown"
            fps    = str(int(si.frame_rate))         if si.frame_rate else "unknown"
            codecs = si.codecs                       or "unknown"
            variants.append((idx, bw, res, fps, codecs, pl.absolute_uri))
    else:
        lines = master_text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                info = line
                uri  = lines[i+1].strip() if i+1 < len(lines) else ""
                if uri and not uri.startswith("#"):
                    bw     = int(re.search(r"BANDWIDTH=(\d+)", info).group(1)) if "BANDWIDTH" in info else 0
                    res    = re.search(r"RESOLUTION=(\d+x\d+)", info).group(1)      if "RESOLUTION" in info else "unknown"
                    fps    = re.search(r"FRAME-RATE=([\d\.]+)", info).group(1)      if "FRAME-RATE" in info else "unknown"
                    codecs = re.search(r'CODECS="([^"]+)"', info).group(1)         if "CODECS" in info else "unknown"
                    variants.append((len(variants)+1, bw, res, fps, codecs, urljoin(master_url, uri)))
    return variants

async def select_variant(variants):
    # Display available tracks
    table = Table(title="Found Tracks", show_header=True, header_style="bold magenta", box=box.ROUNDED)
    table.add_column("Index", style="cyan", no_wrap=True)
    table.add_column("Resolution", justify="right")
    table.add_column("FPS", justify="right")
    table.add_column("Bitrate (Kbps)", justify="right")
    table.add_column("Codecs", overflow="fold")

    for idx, bw, res, fps, codecs, _ in variants:
        table.add_row(str(idx), res, fps, f"{bw // 1000}", codecs)

    console.print(table)
    console.print()  # blank line for spacing

    # Check if preferred resolution is set
    preferred_res = getattr(main, "preferred_resolution", None)
    if preferred_res:
        # Convert resolution like "1080" to "1920x1080" format for matching
        target_height = int(preferred_res)
        
        # First try exact match
        for variant in variants:
            _, _, res, _, _, _ = variant
            if "x" in res:
                _, height = map(int, res.split("x"))
                if height == target_height:
                    console.print(f"[green]Selected {res} (exact match for {preferred_res}p)[/]\n")
                    return variant
        
        # If no exact match, find closest resolution
        closest = None
        min_diff = float('inf')
        for variant in variants:
            _, _, res, _, _, _ = variant
            if "x" in res:
                _, height = map(int, res.split("x"))
                diff = abs(height - target_height)
                if diff < min_diff:
                    min_diff = diff
                    closest = variant
        
        if closest:
            _, _, res, _, _, _ = closest
            console.print(f"[yellow]Selected {res} (closest match to {preferred_res}p)[/]\n")
            return closest
        
        # Fallback to highest quality if no resolution could be parsed
        console.print(f"[yellow]Could not find matching resolution, defaulting to highest quality[/]\n")
        return variants[0]

    # If no preferred resolution, ask user to select
    choice = None
    valid = [str(i) for i in range(1, len(variants)+1)]
    while choice not in valid:
        choice = console.input(f"[bold green]Select stream[/] [1–{len(variants)}]: ")
    console.print()  # blank line

    return variants[int(choice)-1]

async def get_segment_urls(media_text: str, playlist_url: str) -> List[str]:
    base = playlist_url.rsplit("/", 1)[0] + "/"
    lines = media_text.splitlines()
    urls  = []
    for i, line in enumerate(lines):
        if line.startswith("#EXTINF") and i+1 < len(lines):
            uri = lines[i+1].strip()
            if uri and not uri.startswith("#"):
                urls.append(urljoin(base, uri))
    return urls

async def main():
    source_url   = getattr(main, "source_url", DEFAULT_SOURCE_URL)
    max_conn     = getattr(main, "max_connections", DEFAULT_MAX_CONNECTIONS)
    mp4_conn     = getattr(main, "mp4_connections", DEFAULT_MP4_CONNECTIONS)
    output_dir   = getattr(main, "output_dir", DEFAULT_OUTPUT_DIR)
    output_name  = getattr(main, "output_name", None)

    if not source_url:
        console.print("[red]Error: no source URL provided[/]")
        return

    os.makedirs(output_dir, exist_ok=True)
    start = time.time()
    conn  = aiohttp.TCPConnector(limit=max_conn)
    async with aiohttp.ClientSession(connector=conn,
                                     timeout=aiohttp.ClientTimeout(total=DEFAULT_CONNECT_TIMEOUT)) as session:

        if source_url.lower().endswith(".mp4"):
            # MP4 branch
            total   = await get_content_length(session, source_url)
            console.print(f"[bold]Total size:[/] {total/1024**2:.2f} MB")
            console.print()

            part_sz = total // mp4_conn
            parts   = []
            base    = output_name or os.path.basename(source_url).rsplit(".",1)[0]
            for i in range(mp4_conn):
                s  = i * part_sz
                e  = (s + part_sz - 1) if i < mp4_conn-1 else total-1
                pf = os.path.join(output_dir, f"{base}.part{i}")
                parts.append((s, e, pf))

            task_desc = f"[bright_blue]MP4 {base}[/]"
            with Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console
            ) as p:
                tid = p.add_task(task_desc, total=total)
                await asyncio.gather(*(download_chunk(session, source_url, s, e, pf, p, tid) for s,e,pf in parts))

            console.print()  # space before merge
            final_mp4 = os.path.join(output_dir, f"{base}.mp4")
            await merge_parts(final_mp4, [pf for _,_,pf in parts])
            console.print(f"[yellow] ✓ Done [/]")
            console.print()

        else:
            # HLS branch
            console.print("Parsing Tracks…\n")

            master_text = await fetch_text(session, source_url)
            variants    = await parse_variants(source_url, master_text)
            idx, bw, res, fps, codecs, variant_url = await select_variant(variants)

            # remember resolution for naming
            main.selected_quality = res

            console.print(f"Selected stream: {res} @ {fps} fps | {bw//1000} Kbps\n")

            console.print(f"Downloading {res} segments…\n")
            media_text = await fetch_text(session, variant_url)
            segments   = await get_segment_urls(media_text, variant_url)
            sizes      = await asyncio.gather(*(get_content_length(session, seg) for seg in segments))
            total      = sum(sizes)

            console.print(f"[bold]Total size:[/] {total/1024**2:.2f} MB\n")
            task_desc = f"[bright_blue]VID {res}[/]"

            # download all TS segments
            with Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console
            ) as download_prog:
                tid = download_prog.add_task(task_desc, total=total)
                await asyncio.gather(
                    *(download_chunk(
                        session, seg, 0, sz-1,
                        os.path.join(output_dir, os.path.basename(seg)),
                        download_prog, tid
                    ) for seg, sz in zip(segments, sizes))
                )

            console.print("[yellow] ✓ Done [/]\n")

            # write concat list
            list_file = os.path.join(output_dir, "segments.txt")
            async with aiofiles.open(list_file, 'w') as lf:
                for seg in segments:
                    fn = os.path.basename(seg)
                    await lf.write(f"file '{fn}'\n")

            # merge TS → MP4 with progress
            mp4_file = os.path.join(
                output_dir,
                f"{(output_name or os.path.basename(variant_url).rsplit('.',1)[0])}.mp4"
            )
            cmd = [
                FFMPEG_CMD, "-y", "-f", "concat", "-safe", "0",
                "-i", list_file, "-c", "copy", mp4_file
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            with Progress(
                TextColumn("[bold green]Merging[/]"),
                BarColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console
            ) as merge_prog:
                mid = merge_prog.add_task("merge", total=total)
                while proc.returncode is None:
                    if os.path.exists(mp4_file):
                        merge_prog.update(mid, completed=os.path.getsize(mp4_file))
                    await asyncio.sleep(0.1)
                if os.path.exists(mp4_file):
                    merge_prog.update(mid, completed=os.path.getsize(mp4_file))

            rc = await proc.wait()
            if rc != 0:
                console.print(f"[red]❌ Merge failed (exit {rc})[/]")
                return

            # cleanup TS and list file
            for fn in os.listdir(output_dir):
                if fn.endswith(".ts"):
                    try:
                        os.remove(os.path.join(output_dir, fn))
                    except OSError:
                        pass
            try:
                os.remove(list_file)
            except OSError:
                pass

            console.print("[yellow] ✓ Cleaned [/]\n")
            console.print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async HLS/MP4 downloader")
    parser.add_argument("url", nargs="?", help="Manifest (.m3u8) or MP4 URL")
    parser.add_argument("-o", "--output-dir",    default=DEFAULT_OUTPUT_DIR,      help="Where to save files")
    parser.add_argument("-c", "--max-connections",type=int, default=DEFAULT_MAX_CONNECTIONS, help="HTTP connections")
    parser.add_argument("--mp4-connections",     type=int, default=DEFAULT_MP4_CONNECTIONS, help="Connections for MP4")
    args = parser.parse_args()

    if args.url:
        main.source_url    = args.url
    main.output_dir      = args.output_dir
    main.max_connections = args.max_connections
    main.mp4_connections = args.mp4_connections

    asyncio.run(main())